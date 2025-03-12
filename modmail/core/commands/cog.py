"""
modmail.core.commands.cog
=========================
A subclass of discord.py's command.ext.Cog.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from ..bot import Bot

__all__ = [
    "Cog",
]

logger = logging.getLogger(__name__)


class Cog(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        """
        A subclass of discord.py's command.ext.Cog.

        :param bot: The bot instance.
        """
        self.bot = bot

    async def cog_before_invoke(self, ctx: commands.Context[Bot]) -> None:
        logger.debug("User %s is running the %s command.", ctx.author, ctx.command)
        await super().cog_before_invoke(ctx)
