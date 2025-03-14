from __future__ import annotations

from typing import TYPE_CHECKING

from .about import about_command

if TYPE_CHECKING:
    from modmail.core import LazyHybridCommand

__all__ = [
    "all_commands",
]

all_commands: list[LazyHybridCommand] = [
    about_command,
]
