"""
modmail.cogs.utility
====================
This module contains the utility Cog for the Modmail bot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...core.commands import Cog
from .commands import all_commands

if TYPE_CHECKING:
    from discord.ext.commands import HybridCommand  # type: ignore[reportMissingTypeStubs]

    from ...core.bot import Bot

__all__ = ["Utility", "setup"]


utility_methods: dict[str, HybridCommand[Any, Any, Any]] = {
    command.name: command.get_command("Utility") for command in all_commands
}

Utility = type(
    "Utility",
    (Cog,),
    utility_methods,
)


async def setup(bot: Bot) -> None:
    await bot.add_cog(Utility(bot))
