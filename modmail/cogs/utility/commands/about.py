"""
modmail.cogs.utility.commands.about
===================================
This module contains the about command for the Modmail bot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from modmail.core import Bot, _, lazy_hybrid_group

__all__ = ["about_command"]

if TYPE_CHECKING:
    from .. import Utility


@lazy_hybrid_group(
    name=_("cmd-about-name"), fallback=_("cmd-about-fallback-name"), description=_("cmd-about-description")
)
async def about_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    Show information about the Modmail bot.
    """
    await self.reply(ctx, "Modmail!")


@about_command.command(
    name=_("cmd-about-version-name"), description=_("cmd-about-version-description"), with_app_command=False
)
async def about_version_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    Show the version of the Modmail bot.
    """
    await self.reply(ctx, _("cmd-about-version-message", version=self.bot.version), auto_embed=True)
