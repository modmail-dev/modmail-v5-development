"""Component v2 views for Modmail prompts and interactions."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import discord
from discord.app_commands import locale_str

from ..translator import _

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from .context import Context

__all__ = ["PromptChoicesView", "PromptView"]

logger = logging.getLogger(__name__)


class PromptView(discord.ui.LayoutView):
    """Component v2 layout view for a text-input prompt.

    Renders the prompt text and a cancel button as a card.

    Warning:
        Set `message` after sending, before `wait()`. Without it, buttons
        won't be disabled on timeout.

    Examples:
        ```python
        view = PromptView(ctx=ctx, content="What is your name?", timeout=120.0)
        message = await channel.send(view=view)
        view.message = message
        timed_out = await view.wait()
        reply = view.result  # None if canceled or timed out
        ```
    """

    def __init__(
        self,
        *,
        ctx: Context,
        content: str | locale_str,
        timeout: float,
    ) -> None:
        """Build the card layout with the prompt text and cancel button.

        Args:
            ctx: The command context used for translation, author, and channel.
            content: Prompt text shown inside the card (supports Discord Markdown).
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
            content = ctx.translate(content)

        cancel_btn: discord.ui.Button[PromptView] = discord.ui.Button(
            label=ctx.translate(_("ftl-view-prompt-cancel-label")),
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
        """Allow only the invoking user to interact with this view.

        Args:
            interaction: The incoming interaction.

        Returns:
            bool: `True` if the interaction is from the expected user.
        """
        return interaction.user == self._user

    async def wait(self) -> bool:
        """Register the message listener and wait for a reply, cancel, or timeout.

        Returns:
            bool: `True` if the prompt timed out, `False` otherwise.

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
    """Component v2 layout view presenting labeled choices as buttons inside a styled card.

    The prompt text, a visual separator, and choice buttons are rendered together in a
    single `Container`.

    Warning:
        Set `message` after sending, before `wait()`. Without it, buttons
        won't be disabled on timeout.

    Examples:
        ```python
        view = PromptChoicesView(ctx=ctx, content="Pick one:", choices=["A", "B", "C"], timeout=120.0)
        message = await channel.send(view=view)
        view.message = message
        timed_out = await view.wait()
        index = view.result  # None if canceled or timed out
        ```
    """

    def __init__(
        self,
        *,
        ctx: Context,
        content: str | locale_str,
        choices: list[str | locale_str],
        timeout: float,
    ) -> None:
        """Build the card layout with the prompt text and choice buttons.

        Args:
            ctx: The command context used for translation and author checks.
            content: Prompt text shown inside the card (supports Discord Markdown).
            choices: Ordered list of button labels for each selectable option.
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
            content = ctx.translate(content)

        action_row: discord.ui.ActionRow[PromptChoicesView] = discord.ui.ActionRow()
        for i, label in enumerate(choices):
            if isinstance(label, locale_str):
                label = ctx.translate(label)
            btn: discord.ui.Button[PromptChoicesView] = discord.ui.Button(
                label=label, style=discord.ButtonStyle.primary
            )
            btn.callback = self._make_choice_callback(i)
            action_row.add_item(btn)
            self._buttons.append(btn)

        cancel: discord.ui.Button[PromptChoicesView] = discord.ui.Button(
            label=ctx.translate(_("ftl-view-prompt-cancel-label")), style=discord.ButtonStyle.danger
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
        """Return an async callback that records `index` as the result.

        Args:
            index: The choice index this callback represents.

        Returns:
            Callable: An async callable suitable for [`Button.callback`][discord.ui.Button.callback].
        """

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
        """Allow only the invoking user to interact with this view.

        Args:
            interaction: The incoming interaction.

        Returns:
            bool: `True` if the interaction is from the expected user.
        """
        return interaction.user == self._user

    async def wait(self) -> bool:
        """Wait for a choice, cancel interaction, or timeout.

        Returns:
            bool: `True` if the prompt timed out, `False` otherwise.
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
