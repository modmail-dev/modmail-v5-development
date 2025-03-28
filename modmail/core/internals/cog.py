"""A subclass of discord.py's command.ext.Cog with extended functionality.

This module provides a custom Cog implementation that extends Discord.py's
standard Cog with additional features such as localization, embedded messages,
and improved context handling.
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
    """A custom Cog class that extends the functionality of discord.py's Cog."""

    def __init__(self, bot: Bot) -> None:
        """Initialize a custom Cog with extended functionality.

        Args:
            bot: The bot instance this cog will be attached to.
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
        """Reply to a command context with a message.

        Works with both traditional commands and slash commands, choosing
        the appropriate reply method based on the context.

        Args:
            ctx: The command context to reply to.
            content: The message content to send.
            auto_embed: Whether to automatically convert the content to an embed.
            **kwargs: Additional keyword arguments to pass to the reply method.

        Returns:
            The sent Discord message object.
        """
        # Same reply logic as ctx.send()
        if ctx.interaction is None:
            return await self.send(ctx, content, auto_embed=auto_embed, reference=ctx.message, **kwargs)
        return await self.send(ctx, content, auto_embed=auto_embed, **kwargs)

    async def send(
        self,
        ctx: commands.Context[Bot],
        content: str | app_commands.locale_str | None,
        *,
        auto_embed: bool = False,
        **kwargs: Any,
    ) -> discord.Message:
        """Send a message using the command context.

        Handles translation of locale strings, automatic embedding, and
        proper context-based sending.

        Args:
            ctx: The command context to use for sending.
            content: The message content to send.
            auto_embed: Whether to automatically convert the content to an embed.
            **kwargs: Additional keyword arguments to pass to the send method.

        Returns:
            The sent Discord message object.
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
        """Translate a message using the bot's Translator.

        Determines the appropriate locale from the context and translates the string.

        Args:
            ctx: The command context containing locale information.
            string: The locale string to translate.

        Returns:
            The translated string or the original message if translation fails.
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
    """Create a new Cog class dynamically at runtime.

    This function allows for programmatic creation of Cogs, which can be useful
    for modular bot design patterns.

    Args:
        name: The name to give the created cog.
        all_commands: A list of LazyHybridCommand objects to add to the cog.

    Returns:
        A new Cog subclass with the specified name and commands.
    """
    methods: dict[str, commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any]] = {}

    for command in all_commands:
        methods.update(command.get_commands(name))

    return type(name, (Cog,), methods, group_auto_locale_strings=False)
