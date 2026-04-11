"""Command collection for the utility cog.

This module imports and collects all command functions from the utility cog submodules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .about import about_command
from .profile import profile_command
from .status import status_command

if TYPE_CHECKING:
    from modmail.core import LazyHybridCommand

__all__ = [
    "about_command",
    "all_commands",
    "profile_command",
    "status_command",
]

all_commands: list[LazyHybridCommand[Any]] = [
    about_command,
    status_command,
    profile_command,
]
