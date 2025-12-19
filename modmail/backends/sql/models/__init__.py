"""SQLAlchemy models for the SQL backend.

This module provides the SQLAlchemy models for the SQL backend.

Note:
    Modules from this directory should not import from modmail.core.*
    to avoid circular import issues.
"""

from __future__ import annotations

from .activity_model import *
from .permission_override_model import *
from .profile_model import *
from .settings_model import *
from .ticket_dm_message_model import *
from .ticket_message_model import *
from .ticket_model import *
from .ticket_recipient_model import *
from .ticket_user_model import *
