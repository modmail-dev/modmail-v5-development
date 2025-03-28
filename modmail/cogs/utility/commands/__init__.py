from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .about import about_command
from .profile import profile_command
from .status import status_command

if TYPE_CHECKING:
    from modmail.core import LazyHybridCommand

__all__ = [
    "all_commands",
]

all_commands: list[LazyHybridCommand[Any]] = [
    about_command,
    status_command,
    profile_command,
]
