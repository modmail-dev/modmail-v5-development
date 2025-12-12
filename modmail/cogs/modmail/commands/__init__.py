"""Commands for the Modmail cog.

This module collects and exports all command functions that will be registered
with the Modmail cog. It serves as a central registry for all available commands
and simplifies the process of adding new commands to the cog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .close import close_command
from .reply import reply_command
from .sclose import sclose_command
from .setup import setup_command

if TYPE_CHECKING:
    from modmail.core import LazyHybridCommand

__all__ = [
    "all_commands",
]

all_commands: list[LazyHybridCommand[Any]] = [
    setup_command,
    reply_command,
    close_command,
    sclose_command,
]
