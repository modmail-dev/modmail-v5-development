"""A subclass of discord.py's command.ext.Cog with extended functionality.

This module provides a custom Cog implementation that extends Discord.py's
standard Cog with additional features such as localization, embedded messages,
and improved context handling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

import discord
from discord import app_commands
from discord.ext import commands

from ... import CONFIG
from ..translator import _
from .embed import EmbedProxy

if TYPE_CHECKING:
    from collections.abc import Callable

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
        auto_embed: bool = True,
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
        # Same reply logic as ctx.reply()
        if ctx.interaction is None:
            if kwargs.get("reference") is None:
                kwargs["reference"] = ctx.message
            return await self.send(ctx, content, auto_embed=auto_embed, **kwargs)
        return await self.send(ctx, content, auto_embed=auto_embed, **kwargs)

    async def send(
        self,
        ctx: commands.Context[Bot] | discord.abc.Messageable,
        content: str | app_commands.locale_str | None,
        *,
        auto_embed: bool = True,
        original_message: discord.Message | None = None,
        **kwargs: Any,
    ) -> discord.Message:
        """Send a message using the command context.

        Handles translation of locale strings, automatic embedding, and
        proper context-based sending.

        Args:
            ctx: The command context to use for sending or a messageable object.
            content: The message content to send.
            auto_embed: Whether to automatically convert the content to an embed.
            original_message: The original message if editing a message instead of sending a new one.
            **kwargs: Additional keyword arguments to pass to the send method.

        Returns:
            The sent Discord message object.
        """
        locale: discord.Locale | str = CONFIG.default_locale

        if isinstance(ctx, commands.Context):
            if TYPE_CHECKING:
                ctx = cast("commands.Context[Bot]", ctx)
            # Only use user locale if ephemeral and has interaction
            if ctx.interaction is not None and kwargs.get("ephemeral"):
                locale = ctx.interaction.locale

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
            content = await self.translate(ctx, content, locale=locale)

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

        if original_message is not None:
            kwargs.pop("reference", None)  # Remove reference if it exists
            return await original_message.edit(content=content, **kwargs)
        return await ctx.send(content, **kwargs)

    # TODO: implement caching
    async def translate(
        self,
        ctx: commands.Context[Bot] | discord.abc.Messageable,
        string: app_commands.locale_str,
        *,
        locale: discord.Locale | str | None = None,
    ) -> str:
        """Translate a message using the bot's Translator.

        Determines the appropriate locale from the context and translates the string.

        Args:
            ctx: The command context containing locale information or a messageable object.
            string: The locale string to translate.
            locale: The locale to use for translation. If None, uses the context's locale.

        Returns:
            The translated string or the original message if translation fails.
        """
        if locale is None:
            locale = CONFIG.default_locale
            if isinstance(ctx, commands.Context):
                if TYPE_CHECKING:
                    ctx = cast("commands.Context[Bot]", ctx)
                if ctx.interaction is not None:
                    locale = ctx.interaction.locale

        message = await self.bot.translator.translate(string, locale)
        if message is None:
            logger.warning("Failed to translate message: %s", string)
            return string.message
        return message

    async def prompt(
        self,
        ctx: commands.Context[Bot],
        content: str | app_commands.locale_str | None,
        *,
        auto_embed: bool = False,
        reply: bool = True,
        wait_for: float | int = 120.0,
        **kwargs: Any,
    ) -> tuple[discord.Message, discord.Message | None]:
        """Prompt the user with a message.

        Args:
            ctx: The command context to use for sending.
            content: The message content to send.
            auto_embed: Whether to automatically convert the content to an embed.
            reply: Whether to use ctx.reply() instead of ctx.send().
            wait_for: The time in seconds to wait for a response before timing out.
            **kwargs: Additional keyword arguments to pass to the send method.

        Returns:
            A tuple of the prompt message and the user's response Discord message object
            if they responded, else None.
        """
        ui_cancel_label = await self.translate(ctx, _("ftl-view-prompt-cancel-label"))

        class CancelButtonView(discord.ui.View):
            """A view with a cancel button for user interaction."""

            def __init__(self) -> None:
                """Initialize the CancelButtonView with a timeout."""
                super().__init__(timeout=wait_for)

            async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
                """Check if the interaction is from the user who invoked the command.

                Args:
                    interaction: The interaction to check.

                Returns:
                    True if the interaction is from the user who invoked the command, False otherwise.
                """
                return interaction.user == ctx.author

            async def on_timeout(self) -> None:
                """Handle the timeout of the view.

                This method is called when the view times out.
                """
                try:
                    await prompt_message.edit(view=None)
                finally:
                    self.stop()

            @discord.ui.button(label=ui_cancel_label, style=discord.ButtonStyle.danger)
            async def cancel(
                self, interaction: discord.Interaction, button: discord.ui.Button[CancelButtonView]
            ) -> None:
                """Handle the cancel button interaction.

                Args:
                    interaction: The interaction that triggered the button.
                    button: The button that was pressed.
                """
                try:
                    future.cancel("User cancelled the prompt.")
                    await interaction.response.defer()
                    await prompt_message.delete()  # Delete the prompt message
                finally:
                    self.stop()

        view = CancelButtonView()
        if reply:
            prompt_message = await self.reply(ctx, content, auto_embed=auto_embed, view=view, **kwargs)
        else:
            prompt_message = await self.send(ctx, content, auto_embed=auto_embed, view=view, **kwargs)

        def check(m: discord.Message) -> bool:
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        # Similar to bot.wait_for(), but we're creating the wait_for manually here
        # to allow future.cancel()
        future = self.bot.loop.create_future()
        try:
            listeners: list[Any] = self.bot._listeners["message"]  # pyright: ignore [reportUnknownVariableType, reportUnknownMemberType, reportPrivateUsage]
        except KeyError:
            listeners = []
            self.bot._listeners["message"] = listeners  # pyright: ignore [reportUnknownMemberType, reportPrivateUsage]
        listeners.append((future, check))

        try:
            message = await asyncio.wait_for(future, wait_for)
        except TimeoutError:
            await self.reply(ctx, _("ftl-msg-prompt-timeout"))
            return prompt_message, None
        finally:
            view.stop()
        await prompt_message.edit(view=None)
        return prompt_message, message

    async def prompt_choices(
        self,
        ctx: commands.Context[Bot],
        content: str | app_commands.locale_str | None,
        choices: list[str | app_commands.locale_str],
        *,
        auto_embed: bool = False,
        reply: bool = True,
        wait_for: float | int = 120.0,
        **kwargs: Any,
    ) -> tuple[discord.Message, int | None]:
        """Prompt the user with a message and ask to choose a choice via buttons.

        Args:
            ctx: The command context to use for sending.
            content: The message content to send.
            choices: The list of choices to present to the user.
            auto_embed: Whether to automatically convert the content to an embed.
            reply: Whether to use ctx.reply() instead of ctx.send().
            wait_for: The time in seconds to wait for a response before timing out.
            **kwargs: Additional keyword arguments to pass to the send method.

        Returns:
            A tuple of the prompt message and the index of the chosen choice if the user chose one,
            else None.
        """
        choices_labels = [
            await self.translate(ctx, choice) if isinstance(choice, app_commands.locale_str) else choice
            for choice in choices
        ]
        reply_method = self.reply
        ui_cancel_label = await self.translate(ctx, _("ftl-view-prompt-cancel-label"))

        class PromptChoiceView(discord.ui.View):
            """A view with buttons for user to choose from multiple choices."""

            def __init__(self) -> None:
                """Initialize the PromptChoiceView with choices and a timeout."""
                self.result: int | None = None
                super().__init__(timeout=wait_for)

                # Create buttons for each choice
                for i, label in enumerate(choices_labels):

                    def create_button(i: int, label: str) -> discord.ui.Button[PromptChoiceView]:
                        """Create a button for a choice.

                        Args:
                            i: The index of the choice.
                            label: The label of the button.

                        Returns:
                            The created button.
                        """
                        button = discord.ui.Button[PromptChoiceView](
                            label=label, style=discord.ButtonStyle.primary
                        )

                        async def button_callback(interaction: discord.Interaction) -> None:
                            """Handle the button interaction.

                            Args:
                                interaction: The interaction that triggered the button.
                            """
                            self.result = i
                            try:
                                await interaction.response.defer()
                                await prompt_message.edit(view=None)
                            finally:
                                self.stop()

                        button.callback = button_callback
                        return button

                    self.add_item(create_button(i, label))

                cancel_button = discord.ui.Button[PromptChoiceView](
                    label=ui_cancel_label, style=discord.ButtonStyle.danger
                )

                async def cancel_callback(interaction: discord.Interaction) -> None:
                    """Handle the cancel button interaction.

                    Args:
                        interaction: The interaction that triggered the button.
                    """
                    try:
                        await interaction.response.defer()
                        await prompt_message.delete()  # Delete the prompt message
                    finally:
                        self.stop()

                cancel_button.callback = cancel_callback
                self.add_item(cancel_button)  # Add the cancel button to the end

            async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
                """Check if the interaction is from the user who invoked the command.

                Args:
                    interaction: The interaction to check.

                Returns:
                    True if the interaction is from the user who invoked the command, False otherwise.
                """
                return interaction.user == ctx.author

            async def on_timeout(self) -> None:
                """Handle the timeout of the view.

                This method is called when the view times out.
                """
                try:
                    await reply_method(ctx, _("ftl-msg-prompt-timeout"))
                    await prompt_message.edit(view=None)
                finally:
                    self.stop()

        view = PromptChoiceView()
        if reply:
            prompt_message = await self.reply(ctx, content, auto_embed=auto_embed, view=view, **kwargs)
        else:
            prompt_message = await self.send(ctx, content, auto_embed=auto_embed, view=view, **kwargs)

        await view.wait()
        return prompt_message, view.result

    # TODO: Add a before invoke hook (here or in bot) that checks if using ctx.send()
    # and warns to use cog.send().


def create_cog(
    name: str,
    *,
    all_commands: list[LazyHybridCommand[Any]] | None = None,
    other_methods: list[Callable[..., Any]] | None = None,
) -> type[Cog]:
    """Create a new Cog class dynamically at runtime.

    This function allows for programmatic creation of Cogs, which can be useful
    for modular bot design patterns.

    Args:
        name: The name to give the created cog.
        all_commands: A list of LazyHybridCommand objects to add to the cog.
        other_methods: A list of callable methods to add to the cog.

    Returns:
        A new Cog subclass with the specified name and commands.
    """
    methods: dict[
        str,
        commands.HybridCommand[Any, Any, Any] | commands.HybridGroup[Any, Any, Any] | Callable[..., Any],
    ] = {}

    if all_commands:
        for command in all_commands:
            methods.update(command.get_commands(name))

    if other_methods:
        for method in other_methods:
            methods[method.__name__] = method

    # noinspection PyTypeChecker
    return type(name, (Cog,), methods, group_auto_locale_strings=False)
