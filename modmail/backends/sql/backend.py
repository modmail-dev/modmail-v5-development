"""SQL database backend for Modmail via async SQLAlchemy drivers."""

from __future__ import annotations

import importlib.util
import logging
from typing import TYPE_CHECKING

from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError, TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from modmail.errors import DatabaseConnectionError

from ..common.db_backend import DBBackend
from ._base import SQLBackendBase
from ._lock import SQLLockMixin
from ._profiles import SQLProfilesMixin
from ._settings import SQLSettingsMixin
from ._tickets import SQLTicketsMixin
from .migration import do_migration

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry

    from modmail.config.models import Config

    # Resolve docs import
    from modmail.errors import InstanceAlreadyRunningError  # pyright: ignore [reportUnusedImport]  # noqa: F401

__all__ = ["SQLBackend"]

logger = logging.getLogger(__name__)

_SUPPORTED_DIALECTS: frozenset[str] = frozenset({"sqlite", "postgresql", "mysql", "mariadb"})


class SQLBackend(
    SQLLockMixin,
    SQLSettingsMixin,
    SQLProfilesMixin,
    SQLTicketsMixin,
    SQLBackendBase,
    DBBackend,
):
    """Concrete [DBBackend][]{ data-preview } assembled from four domain mixins.

    Wires the lock, settings, profile, and ticket mixins together with the
    [AsyncEngine][]{ data-preview }, [session factory][async_sessionmaker]{ data-preview },
    and Alembic migration runner. Dialect-specific session setup is applied on [`_connect`][].
    """

    def __init__(self, config: Config) -> None:
        """Initialize the SQL backend.

        Args:
            config: The bot [Config][]{ data-preview }.
        """
        super().__init__(config)
        self._async_engine: AsyncEngine | None = None
        self._async_sessionmaker: async_sessionmaker[AsyncSession] | None = None

    async def _connect(self) -> None:
        """Connect to the SQL database and run startup procedures.

        Creates the [AsyncEngine][]{ data-preview } and session
        factory, registers dialect-specific connection hooks, verifies connectivity, acquires the
        instance lock, runs Alembic migrations, and starts the heartbeat.

        SQLite registers a `PRAGMA foreign_keys=ON` hook so FK constraints are
        enforced.  MySQL/MariaDB registers a session-init hook that sets
        `time_zone = '+00:00'` and a strict `sql_mode` so both dialects behave
        like PostgreSQL (UTC datetimes, strict type checking, InnoDB FK enforcement).

        Raises:
            ValueError: If the URI dialect is not in [`_SUPPORTED_DIALECTS`][].
            ImportError: If the required async driver package is not installed.
            DatabaseConnectionError: If the connection attempt or engine setup fails.
            InstanceAlreadyRunningError: If the instance is already running.
        """
        uri = self._sql_config.uri.get_secret_value()
        dialect = uri.split("+")[0].split(":")[0].lower()

        if dialect not in _SUPPORTED_DIALECTS:
            raise ValueError(
                f"Unsupported SQL dialect: {dialect!r}. "
                f"Supported dialects: {', '.join(sorted(_SUPPORTED_DIALECTS))}."
            )

        if dialect == "sqlite" and importlib.util.find_spec("aiosqlite") is None:
            raise ImportError(
                "The 'aiosqlite' package is required for SQLite. Install it with: uv sync --extra sqlite"
            )
        if dialect == "postgresql" and importlib.util.find_spec("asyncpg") is None:
            raise ImportError(
                "The 'asyncpg' package is required for PostgreSQL. Install it with: uv sync --extra postgresql"
            )
        if dialect in {"mysql", "mariadb"} and importlib.util.find_spec("asyncmy") is None:
            raise ImportError(
                "The 'asyncmy' package is required for MySQL/MariaDB. Install it with: uv sync --extra mysql"
            )

        self._async_engine = create_async_engine(uri)

        if dialect == "sqlite":

            def set_sqlite_pragma(
                dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
            ) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            event.listen(self._async_engine.sync_engine, "connect", set_sqlite_pragma)

        elif dialect in {"mysql", "mariadb"}:

            def set_mysql_session(
                dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
            ) -> None:
                # Ensure UTC datetimes: MySQL/MariaDB default to server time zone, which
                # may not be UTC.  Setting session time_zone guarantees all DATETIME values
                # written and read in this connection are treated as UTC, matching PostgreSQL
                # TIMESTAMPTZ behavior.
                #
                # STRICT_TRANS_TABLES makes MySQL/MariaDB raise errors on out-of-range or
                # missing values instead of silently truncating, matching PostgreSQL defaults.
                # The remaining flags match the MySQL 8.0+ default strict mode.
                cursor = dbapi_connection.cursor()
                cursor.execute("SET SESSION time_zone = '+00:00'")
                cursor.execute(
                    "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,"
                    "NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
                )
                cursor.close()

            event.listen(self._async_engine.sync_engine, "connect", set_mysql_session)

        self._async_sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except OperationalError as e:
            logger.debug("Failed to connect to SQL database.", exc_info=True)
            error_str = str(e.orig) if e.orig else str(e)
            if dialect == "sqlite" and "unable to open database file" in error_str:
                logger.critical(
                    "Unable to open the SQLite database file. "
                    "Check that the path in your config is correct and the directory exists."
                )
            elif dialect == "sqlite" and "database is locked" in error_str:
                logger.critical(
                    "The SQLite database file is locked by another process. "
                    "Make sure no other bot instance is running against the same file."
                )
            elif dialect == "postgresql" and (
                "could not connect to server" in error_str or "connection refused" in error_str.lower()
            ):
                logger.critical(
                    "Unable to connect to the PostgreSQL server. "
                    "Check that the host, port, and credentials in your config are correct "
                    "and that the server is running."
                )
            elif dialect in {"mysql", "mariadb"} and (
                "can't connect" in error_str.lower() or "connection refused" in error_str.lower()
            ):
                logger.critical(
                    "Unable to connect to the MySQL/MariaDB server. "
                    "Check that the host, port, and credentials in your config are correct "
                    "and that the server is running."
                )
            else:
                logger.critical("An operational database error occurred while connecting: %s", e.orig or e)
            raise DatabaseConnectionError from e
        except SATimeoutError as e:
            logger.debug("Failed to connect to SQL database (pool timeout).", exc_info=True)
            logger.critical("Timed out waiting for a SQL database connection from the pool.")
            raise DatabaseConnectionError from e
        except SQLAlchemyError as e:
            logger.debug("Failed to connect to SQL database.", exc_info=True)
            logger.critical("An unexpected SQL error occurred while connecting to the database.")
            raise DatabaseConnectionError from e
        except Exception as e:
            logger.debug("An unknown error occurred during SQL connection.", exc_info=True)
            logger.critical("An unknown error occurred during SQL connection.")
            raise DatabaseConnectionError from e
        logger.debug("Connected to SQL database.")

        logger.debug("Running database migrations.")
        await do_migration(self._sql_config.uri.get_secret_value())

        # May raise InstanceAlreadyRunningError when another bot is holding the instance lock
        await self._acquire_instance_lock()

    async def _disconnect(self) -> None:
        """Dispose of the database engine and clear the session factory."""
        self._async_sessionmaker = None
        if self._async_engine:
            await self._async_engine.dispose()
            self._async_engine = None
            logger.debug("Disconnected from SQL database.")
