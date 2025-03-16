"""
modmail.backends.common
=======================
This module provides a uniform interface between backend models.

Modules from this directory should not import from modmail.core.* (circular import issues).
"""

from __future__ import annotations

from .abc import *
from .models import *
