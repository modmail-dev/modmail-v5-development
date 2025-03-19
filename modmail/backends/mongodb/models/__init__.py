"""
modmail.backends.mongodb.models
===============================
This module provides the MongoDB models for the MongoDB backend.

Modules from this directory should not import from modmail.core.* (circular import issues).
"""

from __future__ import annotations

from .permission_group_model import *
from .settings_model import *
