"""About command implementation for the Modmail bot.

This module contains commands that display information about the Modmail bot,
including the main about command and its subcommands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from modmail.core import Bot, _, lazy_hybrid_group

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["about_command"]


@lazy_hybrid_group(
    name=_("ftl-cmd-about-name"),
    fallback=_("ftl-cmd-about-fallback-name"),
    description=_("ftl-cmd-about-description"),
)
async def about_command(cog: Utility, ctx: commands.Context[Bot]) -> None:
    """Show information about the Modmail bot.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """
    await cog.reply(ctx, "Modmail!")


@about_command.command(
    name=_("ftl-cmd-about-version-name"),
    description=_("ftl-cmd-about-version-description"),
    with_app_command=False,
)
async def about_version_command(cog: Utility, ctx: commands.Context[Bot]) -> None:
    """Show the version of the Modmail bot.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """
    await cog.reply(ctx, _("ftl-cmd-about-version-message", version=cog.bot.version))
