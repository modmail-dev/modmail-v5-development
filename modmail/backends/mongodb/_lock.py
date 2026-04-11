"""Prevents two bot instances from running against the same database simultaneously."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, cast

import pymongo.errors
from beanie import UpdateResponse

from modmail.errors import DatabaseOperationError

from ..common.db_backend import LockInfo
from ._base import MongoDBBackendBase
from .models import MongoDBInstanceLockDocument

if TYPE_CHECKING:
    from beanie.odm.queries.update import UpdateOne
    from pymongo.results import UpdateResult

    from ..common.models import InstanceLockModel

logger = logging.getLogger(__name__)


class MongoDBLockMixin(MongoDBBackendBase):
    """MongoDB mixin implementing the five lock primitives."""

    async def _try_insert_lock(self, lock_data: InstanceLockModel) -> bool:
        """Attempt to insert a new lock document for this `bot_id`.

        Args:
            lock_data: The [InstanceLockModel][]{ data-preview } to insert.

        Returns:
            True: The insert succeeded.
            False: A [DuplicateKeyError][pymongo.errors.DuplicateKeyError]{ data-preview } was raised;
                another instance holds the lock.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            await MongoDBInstanceLockDocument.model_validate(lock_data.model_dump()).insert()
            logger.debug("Lock acquired for bot %d (pid=%d).", lock_data.bot_id, lock_data.pid)
            return True
        except pymongo.errors.DuplicateKeyError:
            logger.debug("Lock insert failed for bot %d — another instance holds it.", lock_data.bot_id)
            return False
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to insert lock document") from exc

    async def _read_lock(self) -> LockInfo | None:
        """Read the current lock document for this `bot_id`.

        Missing or malformed fields are treated as epoch so the lock is always considered stale.

        Returns:
            LockInfo: With UTC-aware datetimes.
            None: If no lock document exists.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            doc = await MongoDBInstanceLockDocument.find_one(
                MongoDBInstanceLockDocument.bot_id == self._config.bot.bot_id
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to read lock document") from exc

        if doc is None:
            return None

        epoch = datetime.datetime(1, 1, 1, tzinfo=datetime.UTC)
        return LockInfo(
            hostname=doc.hostname,
            pid=doc.pid,
            acquired_at=doc.acquired_at,
            heartbeat_at=doc.heartbeat_at or epoch,
        )

    async def _try_takeover_lock(self, stale_cutoff: datetime.datetime, lock_data: InstanceLockModel) -> bool:
        """Atomically overwrite the lock document only when `heartbeat_at` <= `stale_cutoff`.

        Args:
            stale_cutoff: UTC-aware datetime; documents with
                `heartbeat_at` at or before this value
                are considered stale and eligible for takeover.
            lock_data: New [InstanceLockModel][]{ data-preview } to write on a successful takeover.

        Returns:
            True: The document was updated; this instance now owns the lock.
            False: The lock was refreshed by a live instance before this call.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        try:
            result = cast(
                "UpdateResult",
                await cast(
                    "UpdateOne",
                    MongoDBInstanceLockDocument.find_one(
                        MongoDBInstanceLockDocument.bot_id == lock_data.bot_id,
                        MongoDBInstanceLockDocument.heartbeat_at <= stale_cutoff,
                    ).update(
                        {
                            "$set": {
                                "instance_id": lock_data.instance_id,
                                "acquired_at": lock_data.acquired_at,
                                "heartbeat_at": lock_data.heartbeat_at,
                                "hostname": lock_data.hostname,
                                "pid": lock_data.pid,
                            }
                        },
                        response_type=UpdateResponse.UPDATE_RESULT,
                    ),
                ),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to take over lock document") from exc

        succeeded = result.modified_count > 0
        if succeeded:
            logger.debug("Lock takeover succeeded for bot %d (pid=%d).", lock_data.bot_id, lock_data.pid)
        else:
            logger.debug("Lock takeover failed for bot %d — lock was refreshed before takeover.", lock_data.bot_id)
        return succeeded

    async def _delete_lock(self) -> None:
        """Delete this instance's lock document from the collection.

        Targets only the document matching both `bot_id` and this instance's
        unique `instance_id`, so a concurrent takeover is not accidentally undone.
        A no-op if the client is already closed.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        if self._async_mongo_client is None:
            return
        try:
            await MongoDBInstanceLockDocument.find_one(
                MongoDBInstanceLockDocument.bot_id == self._config.bot.bot_id,
                MongoDBInstanceLockDocument.instance_id == self._instance_id,
            ).delete()
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to delete lock document") from exc
        logger.debug("Lock document deleted for bot %d.", self._config.bot.bot_id)

    async def _update_heartbeat(self) -> bool:
        """Set `heartbeat_at` to now for this instance's lock document.

        Returns:
            True: The document was updated; this instance still owns the lock.
            False: No matching document was found.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        if self._async_mongo_client is None:
            return False
        now = datetime.datetime.now(datetime.UTC)
        try:
            result = cast(
                "UpdateResult",
                await cast(
                    "UpdateOne",
                    MongoDBInstanceLockDocument.find_one(
                        MongoDBInstanceLockDocument.bot_id == self._config.bot.bot_id,
                        MongoDBInstanceLockDocument.instance_id == self._instance_id,
                    ).update(
                        {"$set": {"heartbeat_at": now}},
                        response_type=UpdateResponse.UPDATE_RESULT,
                    ),
                ),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to update lock heartbeat") from exc
        still_owner = result.modified_count == 1
        if not still_owner:
            logger.warning(
                "Heartbeat update matched no documents for bot %d — lock may have been taken over.",
                self._config.bot.bot_id,
            )
        return still_owner
