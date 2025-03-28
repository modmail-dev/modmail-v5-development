"""Provides MongoDB models.

This module aggregates all MongoDB models used by the backend for data storage
and retrieval.

Note:
    Modules from this directory should not import from modmail.core.*
    to avoid circular import issues.
"""

from __future__ import annotations

from .profile_model import *
from .settings_model import *
