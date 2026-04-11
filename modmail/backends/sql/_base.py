"""Foundation shared by all SQL mixins — the engine, session factory, and bot config."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from modmail.errors import DatabaseConnectionError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from modmail.config.models import Config, SQLDatabaseConfig

__all__ = ["SQLBackendBase"]

logger = logging.getLogger(__name__)


class SQLBackendBase:
    """Base class that provides [`engine`][], [`session`][], and [`_sql_config`][] to every SQL mixin.

    Places this at the base of the MRO so the shared state
    is declared once and available to all domain mixins.
    """

    # These are typed here but initialized in SQLBackend.__init__ via super().__init__
    _async_engine: AsyncEngine | None
    _async_sessionmaker: async_sessionmaker[AsyncSession] | None

    # Inherited from DBBackend via SQLBackend's MRO
    _config: Config
    _instance_id: str

    @property
    def engine(self) -> AsyncEngine:
        """The [AsyncEngine][]{ data-preview } for this backend.

        Raises:
            DatabaseConnectionError: If called before
                [`connect`][....backend.SQLBackend._connect]{ data-preview } or after
                [`disconnect`][....backend.SQLBackend._disconnect]{ data-preview }.
        """
        if self._async_engine is None:
            raise DatabaseConnectionError("SQL engine accessed before connect() was called.")
        return self._async_engine

    @property
    def session(self) -> async_sessionmaker[AsyncSession]:
        """[async_sessionmaker][]{ data-preview } session factory for this backend.

        Raises:
            DatabaseConnectionError: If called before
                [`connect`][....backend.SQLBackend._connect]{ data-preview } or after
                [`disconnect`][....backend.SQLBackend._disconnect]{ data-preview }.
        """
        if self._async_sessionmaker is None:
            raise DatabaseConnectionError("SQL session factory accessed before connect() was called.")
        return self._async_sessionmaker

    @property
    def _sql_config(self) -> SQLDatabaseConfig:
        """The [SQLDatabaseConfig][]{ data-preview } for this `bot_id`.

        Raises:
            AttributeError: If the SQL config was not provided.
        """
        if self._config.sql_config is None:
            raise AttributeError("_sql_config accessed but not provided in config.")
        return self._config.sql_config
