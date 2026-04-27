"""Custom command context for Modmail.

Provides a subclass of [`commands.Context`][] that adds Modmail-specific
attributes tracked during command invocation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from discord.app_commands import locale_str
from discord.ext import commands

from ..translator import _
from .views import PromptChoicesView, PromptView

if TYPE_CHECKING:
    import discord

    from .. import Bot

__all__ = ["Context"]

logger = logging.getLogger(__name__)

type AnyStr = str | locale_str


class Context(commands.Context[Any]):
    """Command context with Modmail-specific attributes."""

    if TYPE_CHECKING:
        bot: Bot

    perm_check_reason: str
    """Outcome of the permission check for this invocation
        (absent if the check has not yet run)."""

    async def send_message(
        self,
        content: AnyStr | None = None,
        *,
        auto_embed: bool = True,
        original_message: discord.Message | None = None,
        **kwargs: Any,
    ) -> discord.Message:
        """Send a message to this context's channel.

        Args:
            content: Message content to send.
            auto_embed: Whether to automatically convert the content to an embed.
            original_message: If set, edits this message instead of sending a new one.
            **kwargs: Additional keyword arguments passed to the underlying send or edit.

        Returns:
            The sent [discord.Message][].
        """
        return await self.bot.send_message(
            content, channel=self, auto_embed=auto_embed, original_message=original_message, **kwargs
        )

    async def reply(
        self,
        content: AnyStr | None = None,
        *,
        auto_embed: bool = True,
        **kwargs: Any,
    ) -> discord.Message:
        """Reply to the invoking message.

        Args:
            content: Message content to send.
            auto_embed: Whether to automatically convert the content to an embed.
            **kwargs: Additional keyword arguments passed to the underlying send.

        Returns:
            The sent [discord.Message][].
        """
        if self.interaction is None:
            kwargs.setdefault("reference", self.message)
        kwargs["original_message"] = None
        return await self.bot.send_message(content, channel=self, auto_embed=auto_embed, **kwargs)

    async def prompt(
        self,
        content: AnyStr | None,
        *,
        reply: bool = True,
        wait_for: float | int = 120.0,
        **kwargs: Any,
    ) -> tuple[discord.Message, discord.Message | None]:
        """Send a prompt card and wait for a typed reply.

        The prompt text and cancel button are rendered together in a card. Waits
        until the user sends a message in the same channel or clicks cancel.

        Args:
            content: Prompt text shown inside the card.
            reply: Whether to send as a reply to the invoking message.
            wait_for: Seconds before the prompt times out.
            **kwargs: Additional keyword arguments forwarded to the underlying send.

        Other Parameters:
            auto_embed: Whether to automatically convert the content to an embed.
            original_message: If set, edits this message instead of sending a new one.

        Returns:
            A two-item tuple of the prompt message and the user's typed reply,
            or `None` as the second item if the prompt timed out or was canceled.

        Raises:
            asyncio.CancelledError: If the wait is interrupted by an external
                cancellation (not caused by the user clicking cancel).
        """
        wait_for = float(wait_for)

        view = PromptView(ctx=self, content=content or "", timeout=wait_for)

        if reply:
            prompt_message = await self.reply(auto_embed=False, view=view, **kwargs)
        else:
            prompt_message = await self.send_message(auto_embed=False, view=view, **kwargs)
        view.message = prompt_message

        timed_out = await view.wait()
        if timed_out:
            await self.reply(_("ftl-msg-prompt-timeout"), ephemeral=True)

        return prompt_message, view.result

    async def prompt_choices(
        self,
        content: AnyStr | None,
        choices: list[AnyStr],
        *,
        reply: bool = True,
        wait_for: float | int = 120.0,
        **kwargs: Any,
    ) -> tuple[discord.Message, int | None]:
        """Send a Component v2 prompt card with labeled choice buttons.

        Renders the prompt text and one button per choice, plus a cancel button.
        Waits for the user to interact and returns the selected index.

        Args:
            content: Prompt text displayed inside the card.
            choices: Choices to present as buttons.
            reply: Whether to send as a reply to the invoking message.
            wait_for: Seconds before the prompt times out.
            **kwargs: Additional keyword arguments forwarded to the underlying send.

        Other Parameters:
            auto_embed: Whether to automatically convert the content to an embed.
            original_message: If set, edits this message instead of sending a new one.

        Returns:
            A two-item tuple of the prompt message and the index of the chosen
            option, or `None` as the second item if canceled or timed out.
        """
        wait_for = float(wait_for)

        view = PromptChoicesView(ctx=self, content=content or "", choices=choices, timeout=wait_for)

        if reply:
            prompt_message = await self.reply(auto_embed=False, view=view, **kwargs)
        else:
            prompt_message = await self.send_message(auto_embed=False, view=view, **kwargs)
        view.message = prompt_message

        timed_out = await view.wait()
        if timed_out:
            await self.reply(_("ftl-msg-prompt-timeout"), ephemeral=True)

        return prompt_message, view.result

    def translate(
        self,
        string: locale_str,
        *,
        locale: discord.Locale | str | None = None,
    ) -> str:
        """Translate a locale string using the invoking interaction's locale.

        Args:
            string: The locale string to translate.
            locale: Override locale. If `None`, uses the interaction locale or the bot default.

        Returns:
            The translated string, or the original message if translation fails.
        """
        return self.bot.translate(string, ctx_or_locale=locale if locale is not None else self)
