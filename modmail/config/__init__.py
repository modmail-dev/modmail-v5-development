"""Configuration package for the Modmail bot.

This package contains the configuration loading and model definitions for the Modmail bot.
It includes functionality to load configuration from various sources and validate them
using Pydantic models.

Note:
    Modules from this directory should not import from modmail.core.*
    to avoid circular import issues.
"""

from __future__ import annotations

from .loader import load_config
from .models import Config

__all__ = [
    "Config",
    "load_config",
]
