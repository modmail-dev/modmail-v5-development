"""Base classes for context-aware Discord UI components."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import weakref
from typing import TYPE_CHECKING, Any, ClassVar

import discord
from discord.app_commands import locale_str

from .ephemeral import using_ephemeral
from .locale import locale_for

if TYPE_CHECKING:
    from .bot import Bot

__all__ = ["BaseLayoutView", "BaseModal"]

logger = logging.getLogger(__name__)


class _ViewMixin:
    """Shared behavior for [`BaseLayoutView`][] and [`BaseModal`][].

    Note:
        Internal mixin — subclass [`BaseLayoutView`][] or [`BaseModal`][] instead.
    """

    _bot: Bot
    """The bot instance."""
    _author: discord.Member | discord.User
    """The user who invoked the command, used to gate interactions."""
    _locale: str
    """Translation locale captured at construction via [`locale_for`][]."""
    _interaction: discord.Interaction | None
    """The invoking interaction, stored for passing to child modals or views."""
    _message: discord.Message | None
    _response_locks: ClassVar[weakref.WeakValueDictionary[int, asyncio.Lock]] = weakref.WeakValueDictionary()

    @property
    def message(self) -> discord.Message | None:
        """The sent message, set by the caller after sending."""
        return self._message

    @message.setter
    def message(self, value: discord.Message | None) -> None:
        self._message = value

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction originates from the command invoker."""
        return interaction.user == self._author

    def _t(
        self,
        string: locale_str,
        interaction: discord.Interaction[Any] | None = None,
        *,
        escape: bool | None = None,
        **kwargs: Any,
    ) -> str:
        """Translate `string` using the construction-time locale, or an interaction's locale.

        Args:
            string: The [`locale_str`][] from [`_`][], [`_n`][], or [`_c`][].
            interaction: When given and registered via [`ephemeral_scope`][], uses its locale
                instead of the construction-time locale.
            escape: When not `None`, overrides the construction-time escape flag.
            **kwargs: Additional formatting kwargs merged on top of construction-time kwargs.

        Returns:
            Translated string.
        """
        if interaction is None:
            locale = self._locale
        elif using_ephemeral(interaction):
            locale = locale_for(interaction)
        else:
            locale = locale_for(None)

        return self._bot.translate(string, locale=locale, escape=escape, **kwargs)

    def _response_lock_for(self, interaction: discord.Interaction) -> asyncio.Lock:
        """Return the per-interaction response lock, creating it on first use."""
        if (lock := self._response_locks.get(interaction.id)) is None:
            lock = asyncio.Lock()
            self._response_locks[interaction.id] = lock
        return lock

    def _delete_message(self, interaction: discord.Interaction | None = None) -> None:
        """Fire-and-forget delete of `interaction.message` or [`message`][]."""
        if interaction is None or interaction.is_expired():
            target = self.message
        else:
            target = interaction.message or self.message

        if target is None:
            return

        async def delete() -> None:
            with contextlib.suppress(discord.HTTPException):
                await target.delete()

        self._bot.spawn_task(delete(), name=f"delete_message:{target.id}")

    def defer(self, interaction: discord.Interaction) -> None:
        """Fire-and-forget defer — no-op if the response is already done."""
        if interaction.is_expired() or interaction.response.is_done():
            return

        async def respond() -> None:
            async with self._response_lock_for(interaction):
                if interaction.is_expired() or interaction.response.is_done():
                    return
                with contextlib.suppress(discord.HTTPException):
                    await interaction.response.defer()

        self._bot.spawn_task(respond(), name=f"defer:{interaction.id}")

    async def send(
        self,
        interaction: discord.Interaction,
        content: str | locale_str | None = None,
        *,
        ephemeral: bool | None = None,
        delete_after: float | None = 6.0,
        **kwargs: Any,
    ) -> None:
        """Send a response to a view interaction.

        Args:
            interaction: The interaction to respond to.
            content: Text or [`locale_str`][] to send.
            ephemeral: `True` for ephemeral. `None` follows the active [`ephemeral_scope`][].
            delete_after: Seconds before auto-deletion (`None` to keep).
            **kwargs: Forwarded to the underlying Discord send call.
        """
        if "view" in kwargs:
            delete_after = None

        if ephemeral is None:
            ephemeral = using_ephemeral(interaction)

        if ephemeral:
            locale = locale_for(interaction)
        else:
            locale = locale_for(None)

        pos_args: list[str] = []
        if content is not None:
            if isinstance(content, locale_str):
                content = self._bot.translate(content, locale=locale)
            pos_args.append(content)

        async with self._response_lock_for(interaction):
            if not interaction.is_expired() and not interaction.response.is_done():
                with contextlib.suppress(discord.HTTPException):
                    await interaction.response.send_message(
                        *pos_args, ephemeral=ephemeral, delete_after=delete_after, **kwargs
                    )
                return

        with contextlib.suppress(discord.HTTPException):
            if interaction.is_expired():
                if not isinstance(interaction.channel, discord.abc.Messageable):
                    return
                # Try to send to the channel directly
                msg = await self._bot.send_message(
                    content, channel=interaction.channel, ephemeral=ephemeral, fail_silently=True, **kwargs
                )
                if msg and delete_after is not None:
                    await msg.delete(delay=delete_after)
            else:
                if delete_after is not None:
                    msg = await interaction.followup.send(*pos_args, ephemeral=ephemeral, wait=True, **kwargs)
                    await msg.delete(delay=delete_after)
                else:
                    await interaction.followup.send(*pos_args, ephemeral=ephemeral, wait=False, **kwargs)
        return

    async def send_ephemeral(
        self,
        interaction: discord.Interaction,
        content: str | locale_str | None = None,
        *,
        delete_after: float | None = 6.0,
        **kwargs: Any,
    ) -> None:
        """Send a private response visible only to the interaction user.

        Args:
            interaction: The interaction to respond to.
            content: Text or [`locale_str`][] to send, or `None` for component-only responses.
            delete_after: Seconds before auto-deletion (`None` to keep).
            **kwargs: Forwarded to [`send`][].
        """
        await self.send(interaction, content, ephemeral=True, delete_after=delete_after, **kwargs)


class BaseLayoutView(_ViewMixin, discord.ui.LayoutView):
    """Base class for Component v2 layout views with locale and author support.

    Args:
        bot: The bot instance.
        author: The user who invoked the command — only they can interact with the view.
        interaction: Invoking interaction for locale capture. `None` uses `CONFIG.default_locale`.
        timeout: Seconds before the view stops accepting interactions.
    """

    def __init__(
        self,
        bot: Bot,
        author: discord.Member | discord.User,
        *,
        interaction: discord.Interaction[Any] | None,
        timeout: float | None = 180.0,
    ) -> None:
        """See class docstring."""
        self._bot = bot
        self._author = author
        self._interaction = interaction
        self._locale: str = locale_for(interaction) if using_ephemeral(interaction) else locale_for(None)
        self._message: discord.Message | None = None
        super().__init__(timeout=timeout)

    def _update_message(self, interaction: discord.Interaction | None = None) -> asyncio.Task[None]:
        """Fire-and-forget view edit, using `edit_message` or falling back to [`message`][].edit.

        When `interaction` is provided and its response slot is free, claims it with
        `edit_message`. Otherwise edits [`message`][] directly. Both paths suppress HTTP errors.

        The returned task can be awaited to ensure the edit completes before proceeding —
        useful when subsequent code depends on the message reflecting the new view state.

        Args:
            interaction: Optional interaction whose response slot can be used for the edit.

        Returns:
            The scheduled edit task.
        """

        async def edit() -> None:
            if interaction is not None:
                async with self._response_lock_for(interaction):
                    if not interaction.is_expired() and not interaction.response.is_done():
                        with contextlib.suppress(discord.HTTPException):
                            await interaction.response.edit_message(view=self)
                        return
            if self.message is not None:
                with contextlib.suppress(discord.HTTPException):
                    # Keep the same allowed_mentions as the original message
                    # discord API resets allowed mentions to all on edit,
                    # while discord.py uses none by default (set in Bot.__init__)
                    allowed_mentions = discord.AllowedMentions.none()
                    if self.message.mention_everyone:
                        allowed_mentions.everyone = True
                    if self.message.mentions:
                        allowed_mentions.users = self.message.mentions
                    if self.message.role_mentions:
                        allowed_mentions.roles = self.message.role_mentions
                    await self.message.edit(view=self, allowed_mentions=allowed_mentions)

        if interaction is not None:
            msg_id = interaction.id
        elif self.message is not None:
            msg_id = self.message.id
        else:
            msg_id = None
        return self._bot.spawn_task(edit(), name=f"update_message:{msg_id or '?'}")


class BaseModal(_ViewMixin, discord.ui.Modal):
    """Base class for modals with locale and author support.

    Args:
        bot: The bot instance.
        author: The user who invoked the command — only they can submit the modal.
        title: Modal title (up to 45 characters). A [`locale_str`][] is translated using the
            captured locale.
        interaction: Invoking interaction for locale capture. `None` uses `CONFIG.default_locale`.
        timeout: Seconds before the modal stops accepting input.
    """

    def __init__(
        self,
        bot: Bot,
        author: discord.Member | discord.User,
        *,
        title: str | locale_str,
        interaction: discord.Interaction[Any] | None,
        timeout: float | None = None,
    ) -> None:
        """See class docstring."""
        self._bot = bot
        self._author = author
        self._interaction = interaction
        self._locale: str = locale_for(interaction) if using_ephemeral(interaction) else locale_for(None)
        self._message: discord.Message | None = None
        super().__init__(title=self._t(title) if isinstance(title, locale_str) else title, timeout=timeout)
