"""SQLAlchemy ORM models for the SQL backend.

Notes:
    Modules from this directory should not import from ``modmail.core.*``
    to avoid circular import issues.
"""

from __future__ import annotations

from .activity_model import SQLActivityTable
from .instance_lock_model import SQLInstanceLockTable
from .permission_override_model import SQLPermissionOverrideTable
from .profile_model import SQLProfileTable
from .settings_model import SQLSettingsTable
from .ticket_dm_message_model import SQLTicketDMMessageTable
from .ticket_message_model import SQLTicketMessageTable
from .ticket_model import SQLTicketTable
from .ticket_recipient_model import SQLTicketRecipientTable
from .ticket_user_model import SQLTicketUserTable

__all__ = [
    "SQLActivityTable",
    "SQLInstanceLockTable",
    "SQLPermissionOverrideTable",
    "SQLProfileTable",
    "SQLSettingsTable",
    "SQLTicketDMMessageTable",
    "SQLTicketMessageTable",
    "SQLTicketRecipientTable",
    "SQLTicketTable",
    "SQLTicketUserTable",
]
