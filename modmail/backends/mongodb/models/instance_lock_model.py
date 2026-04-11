"""Beanie document model for instance locks in MongoDB."""

from __future__ import annotations

from beanie import Document
from pymongo import ASCENDING, IndexModel

from .base import BSON_ENCODERS, UTCTimestamp

__all__ = ["MongoDBInstanceLockDocument"]


class MongoDBInstanceLockDocument(Document):
    """MongoDB document representing one instance lock record.

    One document per [`bot_id`][], enforced by a unique index.
    """

    bot_id: int
    """Discord application ID of the bot that owns this lock."""
    instance_id: str
    """UUID string identifying the running process instance."""
    acquired_at: UTCTimestamp
    """UTC-aware timestamp when the lock was first acquired."""
    heartbeat_at: UTCTimestamp
    """Most recent heartbeat timestamp, used to detect stale locks."""
    hostname: str
    """Network hostname of the machine holding the lock."""
    pid: int
    """OS process ID of the lock holder on [`hostname`][]."""

    class Settings:
        """Settings for MongoDB instance lock collection."""

        name = "InstanceLock"
        keep_nulls = False
        validate_on_save = True
        bson_encoders = BSON_ENCODERS
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING)],
                unique=True,
                name="instance_lock_unique",
            )
        ]
