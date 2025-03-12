"""
modmail.config
==============
This package contains the configuration loading and model definitions for the Modmail bot.
It includes functionality to load configuration from various sources and validate them using Pydantic models.
"""

from __future__ import annotations

from .loader import load_config
from .models.config_model import Config

__all__ = [
    "load_config",
    "Config",
]
