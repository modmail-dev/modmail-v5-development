"""[`Context`][] — a [`commands.Context`][] subclass with Modmail-specific helpers and attributes."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, overload

import discord
from discord.app_commands import locale_str
from discord.ext import commands

from .translator import _

if TYPE_CHECKING:
    from collections.abc import Callable

    from .bot import Bot
    from .translator import FluentTypes, HasLocaleStr

__all__ = ["Context"]

logger = logging.getLogger(__name__)

type AnyStr = str | locale_str


class Context(commands.Context[Any]):
    """Command context with Modmail-specific attributes."""

    if TYPE_CHECKING:
        bot: Bot

    perm_check_reason: str
    """Outcome of the permission check for this invocation (absent if the check has not yet run)."""

    async def send_message(
        self,
        content: AnyStr | None = None,
        *,
        auto_embed: bool = True,
        original_message: discord.Message | None = None,
        **kwargs: Any,
    ) -> discord.Message:
        """Send a message to this context's channel; delegates to [`Bot.send_message`][].

        Args:
            content: Text or locale string to send.
            auto_embed: Wrap plain `content` in an embed automatically.
            original_message: Edit this message instead of sending a new one.
            **kwargs: Forwarded to [`Bot.send_message`][].

        Returns:
            The sent [`discord.Message`][].
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
        """Reply to the invoking message, or send normally for slash commands.

        Args:
            content: Text or locale string to send.
            auto_embed: Wrap plain `content` in an embed automatically.
            **kwargs: Forwarded to [`Bot.send_message`][].

        Returns:
            The sent [`discord.Message`][].
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
        """Send a [`PromptView`][] card and wait for the user to type a reply.

        Waits until the user sends a message in the same channel or clicks cancel.

        Args:
            content: Prompt text shown inside the card.
            reply: Send as a reply to the invoking message (`True`) or as a standalone message.
            wait_for: Seconds before the prompt times out.
            **kwargs: Forwarded to the underlying send call.

        Returns:
            `(prompt_message, user_reply)` — the second item is `None` if canceled or timed out.

        Raises:
            asyncio.CancelledError: If the wait is interrupted externally (not by the cancel button).
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
        """Send a [`PromptChoicesView`][] card and wait for the user to pick a choice.

        Renders the prompt text and one button per choice entry, plus a cancel button.

        Args:
            content: Prompt text displayed inside the card.
            choices: Labels for each selectable button.
            reply: Send as a reply to the invoking message (`True`) or as a standalone message.
            wait_for: Seconds before the prompt times out.
            **kwargs: Forwarded to the underlying send call.

        Returns:
            `(prompt_message, selected_index)` — the second item is `None` if canceled or timed out.
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

    @overload
    def t(
        self,
        string: str,
        /,
        locale: discord.Locale | str | None = ...,
        **kwargs: FluentTypes | HasLocaleStr | locale_str,
    ) -> str: ...

    @overload
    def t(self, string: locale_str, /, locale: discord.Locale | str | None = ...) -> str: ...
    def t(
        self,
        string: str | locale_str,
        /,
        locale: discord.Locale | str | None = None,
        **kwargs: FluentTypes | HasLocaleStr | locale_str,
    ) -> str:
        """Translate `string` into the interaction's locale, or `locale` if given.

        Accepts either a bare FTL message ID (`str`) or a pre-built [`locale_str`][].
        When a key string is passed, `kwargs` are forwarded to the FTL bundle.
        When a [`locale_str`][] is passed, `kwargs` are not accepted.

        Args:
            string: FTL message ID or a [`locale_str`][] produced by [`_`][].
            locale: Override locale. Defaults to the interaction locale.
            **kwargs: FTL variables (only used when `string` is a bare key).

        Returns:
            Translated string in the resolved locale.
        """
        if isinstance(string, str):
            if not string.startswith("ftl-"):  # ftl: ignore
                logger.debug("Context.t called with a non-locale string: %r", string)
            string = _(string, **kwargs)
        return self.bot.translate(string, ctx_or_locale=locale if locale is not None else self)


class PromptView(discord.ui.LayoutView):
    """Component v2 card that waits for the user to type a reply.

    Renders a text prompt and a cancel button. The caller must set `message` after
    sending, otherwise buttons won't be disabled on timeout.
    """

    def __init__(
        self,
        *,
        ctx: Context,
        content: str | locale_str,
        timeout: float,
    ) -> None:
        """Build the card layout.

        Args:
            ctx: Used for translation, author check, and channel filtering.
            content: Prompt text shown inside the card.
            timeout: Seconds before the view stops accepting interactions.
        """
        super().__init__(timeout=timeout)
        self.result: discord.Message | None = None
        """The user's typed reply (`None` if canceled or timed out)."""
        self.message: discord.Message | None = None
        """The sent prompt message (set by the caller after sending, used for cleanup on timeout)."""
        self.canceled = False
        """`True` if the user clicked the cancel button (as opposed to a timeout or external
        cancellation)."""
        self._bot = ctx.bot
        self._channel_id = ctx.channel.id
        self._user = ctx.author
        self._wait_task: asyncio.Task[discord.Message] | None = None

        if isinstance(content, locale_str):
            content = ctx.t(content)

        cancel_btn: discord.ui.Button[PromptView] = discord.ui.Button(
            label=ctx.t("ftl-view-prompt-cancel-label"),
            style=discord.ButtonStyle.danger,
        )
        cancel_btn.callback = self._on_cancel
        self._cancel_btn = cancel_btn

        self.add_item(
            discord.ui.Container(
                discord.ui.Section(
                    discord.ui.TextDisplay(content),
                    accessory=cancel_btn,
                ),
            )
        )

    def _disable_buttons(self) -> None:
        """Disable all interactive buttons in the view."""
        self._cancel_btn.disabled = True

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        """Cancel the wait task, delete the prompt message, and stop the view."""
        self.canceled = True
        if self._wait_task is not None:
            self._wait_task.cancel()
        await interaction.response.defer()
        if interaction.message:
            await interaction.message.delete()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction comes from the invoking user.

        Args:
            interaction: The incoming interaction.
        """
        return interaction.user == self._user

    async def wait(self) -> bool:
        """Register the message listener and wait for a reply, cancel, or timeout.

        Returns:
            `True` if the prompt timed out, `False` otherwise.

        Raises:
            asyncio.CancelledError: If an external cancellation interrupts the wait
                (not caused by the user clicking cancel).
        """
        if self.message is None:
            logger.debug("%s.wait() called without message set; timeout cleanup skipped", type(self).__name__)

        def check(m: discord.Message) -> bool:
            return m.author.id == self._user.id and m.channel.id == self._channel_id

        wait_task: asyncio.Task[discord.Message] = asyncio.create_task(
            self._bot.wait_for("message", check=check, timeout=self.timeout)
        )
        self._wait_task = wait_task

        timed_out = False
        try:
            self.result = await wait_task
        except TimeoutError:
            timed_out = True
        except asyncio.CancelledError:
            if not self.canceled:
                raise
        finally:
            wait_task.cancel()
            self.stop()

        # On cancel, _on_cancel already deleted the message; on timeout, on_timeout
        # handles the edit. On success, disable buttons here.
        if not self.canceled and not timed_out and self.message is not None:
            self._disable_buttons()
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)

        return timed_out

    async def on_timeout(self) -> None:
        """Disable all buttons when the view times out."""
        if self.message is not None:
            self._disable_buttons()
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)


class PromptChoicesView(discord.ui.LayoutView):
    """Component v2 card presenting labeled choices as buttons.

    Renders the prompt text, a separator, and one button per choice. The caller must
    set `message` after sending, otherwise buttons won't be disabled on timeout.
    """

    def __init__(
        self,
        *,
        ctx: Context,
        content: str | locale_str,
        choices: list[str | locale_str],
        timeout: float,
    ) -> None:
        """Build the card layout.

        Args:
            ctx: Used for translation and author check.
            content: Prompt text shown inside the card.
            choices: Ordered list of button labels.
            timeout: Seconds before the view stops accepting interactions.
        """
        super().__init__(timeout=timeout)
        self.result: int | None = None
        """Index of the chosen option, or `None` if canceled or timed out."""
        self.message: discord.Message | None = None
        """The prompt message (set by the caller after sending, used for cleanup on timeout)."""
        self._user = ctx.author
        self._buttons: list[discord.ui.Button[PromptChoicesView]] = []

        if isinstance(content, locale_str):
            content = ctx.t(content)

        action_row: discord.ui.ActionRow[PromptChoicesView] = discord.ui.ActionRow()
        for i, label in enumerate(choices):
            if isinstance(label, locale_str):
                label = ctx.t(label)
            btn: discord.ui.Button[PromptChoicesView] = discord.ui.Button(
                label=label, style=discord.ButtonStyle.primary
            )
            btn.callback = self._make_choice_callback(i)
            action_row.add_item(btn)
            self._buttons.append(btn)

        cancel: discord.ui.Button[PromptChoicesView] = discord.ui.Button(
            label=ctx.t("ftl-view-prompt-cancel-label"), style=discord.ButtonStyle.danger
        )
        cancel.callback = self._on_cancel
        action_row.add_item(cancel)
        self._buttons.append(cancel)

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(content),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                action_row,
            )
        )

    def _disable_buttons(self) -> None:
        """Disable all interactive buttons in the view."""
        for btn in self._buttons:
            btn.disabled = True

    def _make_choice_callback(self, index: int) -> Callable[..., Any]:
        """Return an async callback that records `index` as the result and stops the view."""

        async def callback(interaction: discord.Interaction) -> None:
            self.result = index
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            self.stop()

        return callback

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        """Delete the prompt message and stop the view."""
        await interaction.response.defer()
        if interaction.message:
            await interaction.message.delete()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction comes from the invoking user.

        Args:
            interaction: The incoming interaction.
        """
        return interaction.user == self._user

    async def wait(self) -> bool:
        """Wait for a choice, cancel, or timeout.

        Returns:
            `True` if timed out, `False` otherwise.
        """
        if self.message is None:
            logger.debug("%s.wait() called without message set; timeout cleanup skipped", type(self).__name__)
        return await super().wait()

    async def on_timeout(self) -> None:
        """Disable all buttons when the view times out."""
        if self.message is not None:
            self._disable_buttons()
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)
