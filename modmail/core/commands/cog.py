"""
modmail.core.commands.cog
=========================
A subclass of discord.py's command.ext.Cog.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from ... import CONFIG

if TYPE_CHECKING:
    from .. import Bot
    from .command import LazyHybridCommand

__all__ = [
    "Cog",
    "create_cog",
]

logger = logging.getLogger(__name__)


class Cog(commands.Cog, group_auto_locale_strings=False):
    def __init__(self, bot: Bot) -> None:
        """
        A subclass of discord.py's command.ext.Cog.

        :param bot: The bot instance.
        """
        self.bot = bot

    async def cog_before_invoke(self, ctx: commands.Context[Bot]) -> None:
        logger.debug("User %s is running the %s command.", ctx.author, ctx.command)
        await super().cog_before_invoke(ctx)

    async def reply(
        self, ctx: commands.Context[Bot], message: str | app_commands.locale_str, **kwargs: Any
    ) -> None:
        """
        Reply to a command context with a message.

        :param ctx: The command context.
        :param message: The message to send.
        :param kwargs: Additional keyword arguments to pass to the reply method.
        """
        if isinstance(message, app_commands.locale_str):
            if ctx.interaction:
                locale: discord.Locale | str = ctx.interaction.locale
            else:
                locale = CONFIG.default_locale
            translated_message = await self.bot.translator.translate(
                message,
                locale,
                app_commands.TranslationContext(location=app_commands.TranslationContextLocation.other, data=None),
            )
            if translated_message is not None:
                message = translated_message
            else:
                logger.warning("Failed to translate message: %s", message)
                message = message.message
        await ctx.reply(message, **kwargs)


def create_cog(name: str, all_commands: list[LazyHybridCommand[Any]]) -> type[Cog]:
    """
    Create a new Cog class with the given name and methods.
    This is used to create cogs dynamically at runtime.

    :param name: The name of the cog.
    :param all_commands: A list of all commands to be added to the cog.
    :return: A new Cog class with the given name and methods.
    """
    methods: dict[str, commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any]] = {}

    for command in all_commands:
        methods.update(command.get_commands("Utility"))

    cog = type(name, (Cog,), methods, group_auto_locale_strings=False)
    # noinspection PyTypeChecker
    return cog
