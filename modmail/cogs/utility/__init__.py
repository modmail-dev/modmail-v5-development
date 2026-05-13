"""Utility commands cog for the Modmail bot.

This module contains the Utility cog which provides various utility commands
for managing and interacting with the Modmail bot, including status setting,
profile management, and general information commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from modmail.core import Bot, Cog, _, create_cog

from .commands import all_commands

if TYPE_CHECKING:

    class Utility(Cog):  # Makes linters happy
        """Utility commands cog for the Modmail bot."""

else:
    Utility = create_cog(
        "Utility",
        all_commands=all_commands,
        help_name=_("ftl-view-help-category-utility-name"),
        help_description=_("ftl-view-help-category-utility-description"),
        help_color=discord.Color.teal(),
    )


__all__ = ["Utility", "setup"]


async def setup(bot: Bot) -> None:
    """Register the Utility cog with the bot.

    Args:
        bot: The Modmail bot instance.
    """
    await bot.add_cog(Utility(bot))
