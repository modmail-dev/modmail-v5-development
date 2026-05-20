"""[`Context`][] — a [`commands.Context`][] subclass with Modmail-specific helpers and attributes."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.app_commands import locale_str
from discord.ext import commands

from ..enum import RequiredAccessLevel, UserAccessAllowReason, UserAccessDenyReason
from ..i18n import _
from .ephemeral import using_ephemeral
from .locale import locale_for
from .ui import BaseLayoutView

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..enum import AccessLevel
    from .bot import Bot

__all__ = ["Context", "UserAccessResult"]

logger = logging.getLogger(__name__)

type AnyStr = str | locale_str


@dataclasses.dataclass(frozen=True, slots=True)
class UserAccessResult:
    """Outcome of a user access check for a single command invocation.

    Stored on [`Context.user_access`][] after [`Bot.check_user_access`][] runs,
    regardless of whether access was granted or denied.

    Attributes:
        reason: The specific allow or deny reason. Whether access was granted is inferred
            from the type: a [`UserAccessAllowReason`][] means allowed, a
            [`UserAccessDenyReason`][] means denied.
        profile_id: Discord ID of the profile that decided the outcome (`None` for
            non-profile decisions such as owner bypass or insufficient access).
        command_name: Canonical command key involved in the decision — set only for
            profile override decisions (exact or wildcard).
        profile_access_level: The profile's [`AccessLevel`][] at decision time (`None`
            unless `reason` is `level_match`).
        required_level: The [`RequiredAccessLevel`][] the command demanded (`None` unless
            `reason` is `level_match` or `insufficient_access`).
    """

    reason: UserAccessAllowReason | UserAccessDenyReason
    profile_id: int | None = None
    command_name: str | None = None
    profile_access_level: AccessLevel | None = None
    required_level: RequiredAccessLevel | None = None

    @property
    def allowed(self) -> bool:
        """`True` if the user may run the command."""
        return isinstance(self.reason, UserAccessAllowReason)

    def __str__(self) -> str:
        """Return a compact human-readable summary of the access outcome."""
        verdict = "allow" if self.allowed else "deny"
        parts = [f"{verdict}:{self.reason}"]
        if self.profile_id is not None:
            parts.append(f"profile={self.profile_id}")
        if self.command_name is not None:
            parts.append(f"cmd={self.command_name}")
        if self.profile_access_level is not None and self.required_level is not None:
            parts.append(f"level={self.profile_access_level.name}>={self.required_level.name}")
        elif self.required_level is not None:
            parts.append(f"required={self.required_level.name}")
        return " ".join(parts)


class Context(commands.Context[Any]):
    """Command context with Modmail-specific attributes."""

    if TYPE_CHECKING:
        bot: Bot

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize `user_access` to `None`; all other initialization delegated to super."""
        super().__init__(*args, **kwargs)
        self.user_access: UserAccessResult | None = None
        """Access outcome cached by [`Bot._user_access_check`][]."""

    async def send(
        self,
        content: AnyStr | None = None,
        *,
        ephemeral: bool | None = None,
        containerize: bool | None = None,
        container_color: discord.Color | int | None = None,
        **kwargs: Any,
    ) -> discord.Message:
        """Send a message to this context's channel; delegates to [`Bot.send_message`][].

        Args:
            content: Text or locale string to send.
            ephemeral: `True` for ephemeral. `None` follows the active [`ephemeral_scope`][], if any.
            containerize: Wrap plain `content` in a Component V2 container.
            container_color: Accent color for the container's left bar.
            **kwargs: Forwarded to [`Bot.send_message`][].

        Returns:
            The sent [`discord.Message`][].

        Raises:
            BadPermissionsError: If the bot lacks the required permissions.
            discord.HTTPException: If the send or edit request fails.
        """
        return await self.bot.send_message(
            content,
            **kwargs,
            channel=self,
            ephemeral=ephemeral,
            containerize=containerize,
            container_color=container_color,
            fail_silently=False,
        )

    async def reply(
        self,
        content: AnyStr | None = None,
        *,
        ephemeral: bool | None = None,
        containerize: bool | None = None,
        container_color: discord.Color | int | None = None,
        **kwargs: Any,
    ) -> discord.Message:
        """Reply to the invoking message; for slash commands, behaves like [`send`][].

        Args:
            content: Text or locale string to send.
            ephemeral: Same as [`send`][].
            containerize: Wrap plain `content` in a Component V2 container.
            container_color: Accent color for the container's left bar.
            **kwargs: Forwarded to [`Bot.send_message`][].

        Returns:
            The sent [`discord.Message`][].

        Raises:
            BadPermissionsError: If the bot lacks the required permissions.
            discord.HTTPException: If the send or edit request fails.
        """
        if self.interaction is None:
            kwargs.setdefault("reference", self.message)

        return await self.send(
            content, **kwargs, ephemeral=ephemeral, containerize=containerize, container_color=container_color
        )

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
            BadPermissionsError: If the bot lacks the required permissions.
            discord.HTTPException: If the send or edit request fails.
        """
        view = PromptView(
            bot=self.bot,
            author=self.author,
            channel_id=self.channel.id,
            content=content or "",
            timeout=float(wait_for),
        )

        if reply:
            prompt_message = await self.reply(view=view, **kwargs)
        else:
            prompt_message = await self.send(view=view, **kwargs)
        view.message = prompt_message

        timed_out = await view.wait()
        if timed_out:
            await self.reply(_("msg.prompt.timeout"), ephemeral=True)

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

        Raises:
            BadPermissionsError: If the bot lacks the required permissions.
            discord.HTTPException: If the send or edit request fails.
        """
        view = PromptChoicesView(
            bot=self.bot, author=self.author, content=content or "", choices=choices, timeout=float(wait_for)
        )

        if reply:
            prompt_message = await self.reply(view=view, **kwargs)
        else:
            prompt_message = await self.send(view=view, **kwargs)
        view.message = prompt_message

        timed_out = await view.wait()
        if timed_out:
            await self.reply(_("msg.prompt.timeout"), ephemeral=True)

        return prompt_message, view.result

    def t(
        self,
        string: locale_str,
        /,
        *,
        escape: bool | None = None,
        **kwargs: Any,
    ) -> str:
        """Translate `string` — user's locale inside [`ephemeral_scope`][], default locale otherwise.

        Args:
            string: The [`locale_str`][] from [`_`][], [`_n`][], or [`_c`][].
            escape: When not `None`, overrides the construction-time escape flag.
            **kwargs: Additional formatting kwargs merged on top of construction-time kwargs.

        Returns:
            Translated string.
        """
        if using_ephemeral(self.interaction):
            locale = locale_for(self.interaction)
        else:
            locale = locale_for(None)
        return self.bot.translate(string, locale=locale, escape=escape, **kwargs)


class PromptView(BaseLayoutView):
    """Component v2 card that waits for the user to type a reply.

    Renders a text prompt and a cancel button. The caller must set `message` after
    sending, otherwise buttons won't be disabled on timeout.
    """

    def __init__(
        self,
        *,
        bot: Bot,
        author: discord.Member | discord.User,
        channel_id: int,
        content: str | locale_str,
        timeout: float,
    ) -> None:
        """Build the card layout.

        Args:
            bot: The bot instance.
            author: The user who invoked the command, for interaction gating and message
                filtering.
            channel_id: ID of the channel to listen for replies in.
            content: Prompt text shown inside the card.
            timeout: Seconds before the view stops accepting interactions.
        """
        super().__init__(bot, author, interaction=None, timeout=timeout)
        self.result: discord.Message | None = None
        """The user's typed reply (`None` if canceled or timed out)."""
        self.canceled = False
        """`True` if the user clicked the cancel button (as opposed to a timeout or external
        cancellation)."""
        self._channel_id = channel_id
        self._wait_task: asyncio.Task[discord.Message] | None = None

        if isinstance(content, locale_str):
            content = self._t(content)

        cancel_btn: discord.ui.Button[PromptView] = discord.ui.Button(
            label=self._t(_("view.prompt.cancel")),
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
        self.stop()
        self.defer(interaction)
        self.canceled = True
        if self._wait_task is not None:
            self._wait_task.cancel()
        self._delete_message(interaction)

    async def wait(self) -> bool:
        """Register the message listener and wait for a reply, cancel, or timeout.

        Returns:
            `True` if the prompt timed out or the user canceled, `False` if a reply was received.

        Raises:
            asyncio.CancelledError: If an external cancellation interrupts the wait
                (not caused by the user clicking cancel).
        """
        if self.message is None:
            logger.debug("%s.wait() called without message set; timeout cleanup skipped", type(self).__name__)

        def check(m: discord.Message) -> bool:
            return m.author.id == self._author.id and m.channel.id == self._channel_id

        wait_task: asyncio.Task[discord.Message] = asyncio.create_task(
            self._bot.wait_for("message", check=check, timeout=self.timeout)
        )
        self._wait_task = wait_task

        try:
            self.result = await wait_task
        except TimeoutError:
            return True
        except asyncio.CancelledError:
            if not self.canceled:
                raise
            return False
        finally:
            wait_task.cancel()
            self.stop()

        self._disable_buttons()
        self._update_message()
        return False

    async def on_timeout(self) -> None:
        """Disable all buttons when the view times out."""
        self._disable_buttons()
        self._update_message()


class PromptChoicesView(BaseLayoutView):
    """Component v2 card presenting labeled choices as buttons.

    Renders the prompt text, a separator, and one button per choice. The caller must
    set `message` after sending, otherwise buttons won't be disabled on timeout.
    """

    def __init__(
        self,
        *,
        bot: Bot,
        author: discord.Member | discord.User,
        content: str | locale_str,
        choices: list[str | locale_str],
        timeout: float,
    ) -> None:
        """Build the card layout.

        Args:
            bot: The bot instance.
            author: The user who invoked the command, for interaction gating.
            content: Prompt text shown inside the card.
            choices: Ordered list of button labels.
            timeout: Seconds before the view stops accepting interactions.
        """
        super().__init__(bot, author, interaction=None, timeout=timeout)
        self.result: int | None = None
        """Index of the chosen option, or `None` if canceled or timed out."""
        self._buttons: list[discord.ui.Button[PromptChoicesView]] = []

        if isinstance(content, locale_str):
            content = self._t(content)

        action_row: discord.ui.ActionRow[PromptChoicesView] = discord.ui.ActionRow()
        for i, label in enumerate(choices):
            if isinstance(label, locale_str):
                label = self._t(label)
            btn: discord.ui.Button[PromptChoicesView] = discord.ui.Button(
                label=label, style=discord.ButtonStyle.primary
            )
            btn.callback = self._make_choice_callback(i)
            action_row.add_item(btn)
            self._buttons.append(btn)

        cancel: discord.ui.Button[PromptChoicesView] = discord.ui.Button(
            label=self._t(_("view.prompt.cancel")), style=discord.ButtonStyle.danger
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

        async def callback(interaction: discord.Interaction) -> None:  # noqa: RUF029
            self.result = index
            self.stop()
            self._disable_buttons()
            self._update_message(interaction)

        return callback

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        """Delete the prompt message and stop the view."""
        self.stop()
        self.defer(interaction)
        self._delete_message(interaction)

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
        self._disable_buttons()
        self._update_message()
