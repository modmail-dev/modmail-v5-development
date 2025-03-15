"""
modmail.cogs.utility
====================
This module contains the utility Cog for the Modmail bot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modmail.core import Cog, create_cog

from .commands import all_commands

if TYPE_CHECKING:
    from modmail.core import Bot


__all__ = ["Utility", "setup"]

if TYPE_CHECKING:  # Makes linters happy

    class Utility(Cog): ...

else:
    Utility = create_cog("Utility", all_commands)


async def setup(bot: Bot) -> None:
    await bot.add_cog(Utility(bot))
