"""
modmail.core
============
The core module contains the core classes and functions that are used throughout the bot.
"""

from __future__ import annotations

try:  # Check if modmail is initialized
    from .. import CONFIG

    del CONFIG
except ImportError as e:
    raise RuntimeError("Did you forget to first run modmail.init()?") from e

from .bot import *
from .commands import *
from .permission import *
from .translator import *
