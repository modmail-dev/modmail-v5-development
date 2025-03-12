"""
modmail.cogs.utility.commands.about
===================================
This module contains the about command for the Modmail bot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.commands import lazy_hybrid_command

__all__ = ["about_command"]

if TYPE_CHECKING:
    from discord.ext import commands

    from ....core.bot import Bot
    from .. import Utility


@lazy_hybrid_command(name="about")
async def about_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    await ctx.reply("Modmail!")
