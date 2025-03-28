"""Provides a uniform interface between backend models.

This module exports common abstractions and models for database backend implementations.

Note:
    Modules from this directory should not import from modmail.core.*
    to avoid circular import issues.
"""

from __future__ import annotations

from .abc import *
from .models import *
