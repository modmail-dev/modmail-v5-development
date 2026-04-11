"""Beanie ODM document models for the MongoDB backend.

Notes:
    Modules from this directory should not import from ``modmail.core.*``
    to avoid circular import issues.
"""

from __future__ import annotations

from .base import BSON_ENCODERS, UTCTimestamp
from .instance_lock_model import MongoDBInstanceLockDocument
from .profile_model import MongoDBProfileDocument
from .settings_model import MongoDBActivityModel, MongoDBSettingsDocument
from .ticket_message_model import MongoDBTicketDMMessageModel, MongoDBTicketMessageDocument
from .ticket_model import MongoDBTicketDocument
from .ticket_user_model import MongoDBTicketUserDocument

__all__ = [
    "BSON_ENCODERS",
    "MongoDBActivityModel",
    "MongoDBInstanceLockDocument",
    "MongoDBProfileDocument",
    "MongoDBSettingsDocument",
    "MongoDBTicketDMMessageModel",
    "MongoDBTicketDocument",
    "MongoDBTicketMessageDocument",
    "MongoDBTicketUserDocument",
    "UTCTimestamp",
]
