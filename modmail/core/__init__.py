"""Core functionality for the Modmail bot.

This module contains the core classes and functions used throughout the bot,
including the bot implementation, internal utilities, permission management,
and translation services.
"""

from __future__ import annotations

try:  # Check if modmail is initialized
    from .. import CONFIG

    del CONFIG
except ImportError as e:  # pragma: no cover
    raise RuntimeError("Did you forget to first run modmail.init()?") from e

from .bot import *
from .internals import *
from .permission import *
from .translator import *
