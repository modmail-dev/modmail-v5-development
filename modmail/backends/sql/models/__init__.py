"""
modmail.backends.sql.models
===========================
This module provides the SQLAlchemy models for the SQL backend.

Modules from this directory should not import from modmail.core.* (circular import issues).
"""

from __future__ import annotations

from .activity_model import *
from .permission_override_model import *
from .profile_model import *
from .settings_model import *
