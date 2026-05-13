"""Core functionality for the Modmail bot.

This module contains the core classes and functions used throughout the bot,
including the bot implementation, internal utilities, permission management,
and translation services.
"""

from __future__ import annotations

try:  # Check if modmail is initialized
    from .. import CONFIG
except RuntimeError as e:  # pragma: no cover
    raise RuntimeError("Did you forget to first run modmail.init()?") from e
else:
    del CONFIG

from .bot import *
from .commands import *
from .context import *
from .converters import *
from .embed import *
from .permission import *
from .staff_guild import *
from .translator import *
from .ui import *
