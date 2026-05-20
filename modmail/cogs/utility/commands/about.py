"""About command implementation for the Modmail bot.

This module contains commands that display information about the Modmail bot,
including the main about command and its subcommands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modmail.core import Context, bot_group
from modmail.i18n import _

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["about_command"]


@bot_group(
    name=_("cmd.about.name"),
    fallback=_("cmd.about.fallback"),
    description=_("cmd.about.description"),
)
async def about_command(cog: Utility, ctx: Context) -> None:
    """Show information about the Modmail bot.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """
    await ctx.reply("Modmail!")


@about_command.command(
    name=_("cmd.about.version.name"),
    description=_("cmd.about.version.description"),
    with_app_command=False,
)
async def about_version_command(cog: Utility, ctx: Context) -> None:
    """Show the version of the Modmail bot.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """
    # @param version: Bot version string
    await ctx.reply(_("msg.about.version", version=cog.bot.version))
