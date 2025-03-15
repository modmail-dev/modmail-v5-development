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


@lazy_hybrid_group(name="about", fallback="info")
async def about_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    Show information about the Modmail bot.
    """
    await ctx.reply("Modmail!")


@about_command.command(name="version", with_app_command=False)
async def about_version_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    Show the version of the Modmail bot.
    """
    await ctx.reply(f"Modmail version: {self.bot.version}!")
