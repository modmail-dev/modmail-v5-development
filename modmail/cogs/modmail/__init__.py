"""The main Modmail cog module that provides core Modmail functionality.

This module initializes the Modmail cog which handles ticket creation, user messages,
and other primary Modmail functions. It serves as the entry point for the Modmail
functionality and registers all related commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from modmail.core import Bot, Cog, _, create_cog

from .commands import all_commands
from .listeners import all_listeners

if TYPE_CHECKING:

    class Modmail(Cog):  # Makes linters happy
        """Core Modmail commands cog for the Modmail bot."""

else:
    Modmail = create_cog(
        "Modmail",
        all_commands=all_commands,
        other_methods=all_listeners,
        help_name=_("ftl-view-help-category-modmail-name"),
        help_description=_("ftl-view-help-category-modmail-description"),
        help_color=discord.Color.blurple(),
    )


__all__ = ["Modmail", "setup"]


async def setup(bot: Bot) -> None:
    """Register the Modmail cog with the bot.

    This function is called automatically by discord.py when loading the extension.

    Args:
        bot: The Modmail bot instance.
    """
    await bot.add_cog(Modmail(bot))
