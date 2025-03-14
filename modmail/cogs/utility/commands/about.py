"""
modmail.cogs.utility.commands.about
===================================
This module contains the about command for the Modmail bot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from modmail.core import lazy_hybrid_group, wrap

__all__ = ["about_command"]

if TYPE_CHECKING:
    from modmail.core import Bot

    from .. import Utility


@wrap(commands.guild_only)
@lazy_hybrid_group(name="about")
async def about_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    await ctx.reply("Modmail!")


@about_command.command(name="version")
async def version_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    await ctx.reply(f"Modmail version: {self.bot.version}!")
