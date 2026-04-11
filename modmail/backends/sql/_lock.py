"""Prevents two bot instances from running against the same database simultaneously."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, cast

import sqlalchemy.exc
from sqlalchemy import delete, update

from modmail.errors import DatabaseOperationError

from ..common.db_backend import LockInfo
from ._base import SQLBackendBase
from .models import SQLInstanceLockTable

if TYPE_CHECKING:
    from typing import Any

    from sqlalchemy.engine import CursorResult

    from ..common.models import InstanceLockModel

logger = logging.getLogger(__name__)


class SQLLockMixin(SQLBackendBase):
    """SQL mixin implementing the five lock primitives."""

    async def _try_insert_lock(self, lock_data: InstanceLockModel) -> bool:
        """Attempt to INSERT a new lock row for this `bot_id`.

        Args:
            lock_data: The [InstanceLockModel][]{ data-preview } to insert.

        Returns:
            True: The insert succeeded.
            False: An [IntegrityError][sqlalchemy.exc.IntegrityError] was raised;
                another instance holds the lock.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session, session.begin():
                session.add(SQLInstanceLockTable(**lock_data.model_dump()))
            logger.debug("Lock acquired for bot %d (pid=%d).", lock_data.bot_id, lock_data.pid)
            return True
        except sqlalchemy.exc.IntegrityError:
            logger.debug("Lock insert failed for bot %d — another instance holds it.", lock_data.bot_id)
            return False
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to insert lock row") from exc

    async def _read_lock(self) -> LockInfo | None:
        """Read the current lock holder row for this `bot_id`.

        Returns:
            LockInfo: With UTC-aware datetimes.
            None: If no lock row exists.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session:
                row = await session.get(SQLInstanceLockTable, self._config.bot.bot_id)
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to read lock row") from exc

        if row is None:
            return None

        def _as_utc(dt: datetime.datetime) -> datetime.datetime:
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=datetime.UTC)

        return LockInfo(
            hostname=row.hostname,
            pid=row.pid,
            acquired_at=_as_utc(row.acquired_at),
            heartbeat_at=_as_utc(row.heartbeat_at),
        )

    async def _try_takeover_lock(self, stale_cutoff: datetime.datetime, lock_data: InstanceLockModel) -> bool:
        """Atomically overwrite the lock row when it is stale.

        Overwrites only when `heartbeat_at` <= `stale_cutoff`.

        Args:
            stale_cutoff: UTC-aware datetime; rows with
                `heartbeat_at` at or before this value
                are considered stale and eligible for takeover.
            lock_data: New [InstanceLockModel][]{ data-preview } to write on a successful takeover.

        Returns:
            True: The UPDATE matched a row; this instance now owns the lock.
            False: The lock was refreshed by a live instance before this call.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            async with self.session() as session, session.begin():
                result = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        update(SQLInstanceLockTable)
                        .where(
                            SQLInstanceLockTable.bot_id == lock_data.bot_id,
                            SQLInstanceLockTable.heartbeat_at <= stale_cutoff,
                        )
                        .values(
                            instance_id=lock_data.instance_id,
                            acquired_at=lock_data.acquired_at,
                            heartbeat_at=lock_data.heartbeat_at,
                            hostname=lock_data.hostname,
                            pid=lock_data.pid,
                        )
                    ),
                )
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to take over lock row") from exc

        succeeded = result.rowcount > 0
        if succeeded:
            logger.debug("Lock takeover succeeded for bot %d (pid=%d).", lock_data.bot_id, lock_data.pid)
        else:
            logger.debug("Lock takeover failed for bot %d — lock was refreshed before takeover.", lock_data.bot_id)
        return succeeded

    async def _delete_lock(self) -> None:
        """Delete this instance's lock row from the database.

        Targets only the row matching both `bot_id` and this
        instance's unique `instance_id`, so a concurrent
        takeover does not cause the new holder's lock to be accidentally removed.
        A no-op if the session is gone.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        if self._async_sessionmaker is None:
            return
        try:
            async with self.session() as session, session.begin():
                await session.execute(
                    delete(SQLInstanceLockTable).where(
                        SQLInstanceLockTable.bot_id == self._config.bot.bot_id,
                        SQLInstanceLockTable.instance_id == self._instance_id,
                    )
                )
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to delete lock row") from exc
        logger.debug("Lock row deleted for bot %d.", self._config.bot.bot_id)

    async def _update_heartbeat(self) -> bool:
        """Set `heartbeat_at` to now for this instance's lock row.

        Returns:
            True: Exactly one row was updated; this instance still owns the lock.
            False: The row no longer belongs to this instance.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        if self._async_sessionmaker is None:
            return False
        now = datetime.datetime.now(datetime.UTC)
        try:
            async with self.session() as session, session.begin():
                result = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        update(SQLInstanceLockTable)
                        .where(
                            SQLInstanceLockTable.bot_id == self._config.bot.bot_id,
                            SQLInstanceLockTable.instance_id == self._instance_id,
                        )
                        .values(heartbeat_at=now)
                    ),
                )
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to update lock heartbeat") from exc

        still_owner = result.rowcount == 1
        if not still_owner:
            logger.warning(
                "Heartbeat update matched no rows for bot %d — lock may have been taken over.",
                self._config.bot.bot_id,
            )
        return still_owner
