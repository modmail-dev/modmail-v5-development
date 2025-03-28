"""
modmail.core.internals.cog
==========================
A subclass of discord.py's command.ext.Cog.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from ... import CONFIG
from .embed import EmbedProxy

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

    async def reply(
        self,
        ctx: commands.Context[Bot],
        content: str | app_commands.locale_str | None,
        *,
        auto_embed: bool = False,
        **kwargs: Any,
    ) -> discord.Message:
        """
        Reply to a command context with a message.

        :param ctx: The command context.
        :param content: The message to send.
        :param auto_embed: Whether to automatically embed the message.
        :param kwargs: Additional keyword arguments to pass to the reply method.
        """
        # Same reply logic as ctx.send()
        if ctx.interaction is None:
            return await self.send(ctx, content, auto_embed=auto_embed, reference=ctx.message, **kwargs)
        else:
            return await self.send(ctx, content, auto_embed=auto_embed, **kwargs)

    async def send(
        self,
        ctx: commands.Context[Bot],
        content: str | app_commands.locale_str | None,
        *,
        auto_embed: bool = False,
        **kwargs: Any,
    ) -> discord.Message:
        """
        Send a message with the command context.
        :param ctx: The command context.
        :param content: The message to send.
        :param auto_embed: Whether to automatically embed the message.
        :param kwargs: Additional keyword arguments to pass to the .send() method.
        """

        if ctx.interaction:
            locale: discord.Locale | str = ctx.interaction.locale
        else:
            locale = CONFIG.default_locale

        if auto_embed:
            if "embed" in kwargs or "embeds" in kwargs:
                pass  # Ignore auto_embed if embed or embeds are already in kwargs
            elif content is None:
                pass  # Ignore auto_embed if there's no content
            else:
                # Create a "default style" embed with the content
                embed = EmbedProxy(description=content)  # TODO: Format with colour/style
                kwargs["embed"] = await embed.to_embed(self.bot.translator, locale)
                content = None

        # Translate the message if it's a locale_str
        if isinstance(content, app_commands.locale_str):
            translated_message = await self.bot.translator.translate(content, locale)
            if translated_message is not None:
                content = translated_message
            else:
                logger.warning("Failed to translate message: %s", content)
                content = content.message

        # Translate embed and embeds in kwargs
        if "embed" in kwargs:
            embed = kwargs["embed"]
            if isinstance(embed, EmbedProxy):
                kwargs["embed"] = await embed.to_embed(self.bot.translator, locale)

        if "embeds" in kwargs:
            embeds: list[discord.Embed] = []
            for embed in kwargs["embeds"]:
                if isinstance(embed, EmbedProxy):
                    embeds.append(await embed.to_embed(self.bot.translator, locale))
                else:
                    embeds.append(embed)
            kwargs["embeds"] = embeds

        return await ctx.send(content, **kwargs)

    # TODO: implement caching
    async def translate(self, ctx: commands.Context[Bot], string: app_commands.locale_str) -> str:
        """
        Translate a message using the bot's Translator.

        :param ctx: The command context.
        :param string: The string to translate.
        :return: The translated string or None if translation isn't available.
        """
        if ctx.interaction:
            locale: discord.Locale | str = ctx.interaction.locale
        else:
            locale = CONFIG.default_locale
        message = await self.bot.translator.translate(string, locale)
        if message is None:
            logger.warning("Failed to translate message: %s", string)
            return string.message
        return message

    # TODO: Add a before invoke hook (here or in bot) that checks if using ctx.send() and warns to use cog.send().


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
        methods.update(command.get_commands(name))

    cog = type(name, (Cog,), methods, group_auto_locale_strings=False)
    return cog
