"""Base classes for context-aware Discord UI components."""

from __future__ import annotations

import asyncio
import contextlib
import weakref
from typing import TYPE_CHECKING, Any, ClassVar

import discord

if TYPE_CHECKING:
    from discord.app_commands import locale_str

    from .bot import Bot
    from .context import Context

__all__ = ["BaseLayoutView", "BaseModal"]


class _ViewMixin:
    """Shared behavior for [`BaseLayoutView`][] and [`BaseModal`][].

    Note:
        Internal mixin — subclass [`BaseLayoutView`][] or [`BaseModal`][] instead.
        Concrete subclasses must assign `self._ctx` in their `__init__`.
    """

    _ctx: Context
    _message: discord.Message | None
    _response_locks: ClassVar[weakref.WeakValueDictionary[int, asyncio.Lock]] = weakref.WeakValueDictionary()

    @property
    def message(self) -> discord.Message | None:
        """The sent message, set by the caller after sending."""
        return self._message

    @message.setter
    def message(self, value: discord.Message | None) -> None:
        self._message = value

    @property
    def _bot(self) -> Bot:
        return self._ctx.bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction originates from the command invoker."""
        return interaction.user == self._ctx.author

    def _response_lock_for(self, interaction: discord.Interaction) -> asyncio.Lock:
        """Return the per-interaction response lock, creating it on first use."""
        if (lock := self._response_locks.get(interaction.id)) is None:
            lock = asyncio.Lock()
            self._response_locks[interaction.id] = lock
        return lock

    def _delete_message(self, interaction: discord.Interaction | None = None) -> None:
        """Fire-and-forget delete of `interaction.message` or [`message`][]."""
        target = (interaction.message if interaction is not None else None) or self.message
        if target is None:
            return

        async def delete() -> None:
            with contextlib.suppress(discord.HTTPException):
                await target.delete()

        task = asyncio.create_task(delete())
        self._bot.asyncio_pending_tasks.add(task)
        task.add_done_callback(self._bot.asyncio_pending_tasks.discard)

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

        task = asyncio.create_task(respond())
        self._bot.asyncio_pending_tasks.add(task)
        task.add_done_callback(self._bot.asyncio_pending_tasks.discard)

    async def send(
        self,
        interaction: discord.Interaction,
        content: str | locale_str | None = None,
        *,
        ephemeral: bool = True,
        delete_after: float | None = 6.0,
        **kwargs: Any,
    ) -> discord.WebhookMessage | None:
        """Send an ephemeral response, routing to `interaction.response.send_message` or `followup.send`.

        Args:
            interaction: The interaction to respond to.
            content: Plain string sent as-is, or a [`locale_str`][] translated via [`Context.t`][].
            ephemeral: Whether to send as an ephemeral message.
            delete_after: Seconds before auto-deletion (`None` to keep).
            **kwargs: Forwarded to `interaction.response.send_message` or `followup.send`.

        Returns:
            The webhook message if sent using the followup webhook, else `None`.
        """
        if "view" in kwargs:
            delete_after = None  # Don't auto delete views

        pos_args: list[str] = []
        if content is not None:
            if isinstance(content, discord.app_commands.locale_str):
                content = self._ctx.t(content)
            pos_args.append(content)

        async with self._response_lock_for(interaction):
            if not interaction.is_expired() and not interaction.response.is_done():
                with contextlib.suppress(discord.HTTPException):
                    await interaction.response.send_message(
                        *pos_args, ephemeral=ephemeral, delete_after=delete_after, **kwargs
                    )
                return None

        with contextlib.suppress(discord.HTTPException):
            if delete_after is not None:
                msg = await interaction.followup.send(*pos_args, ephemeral=ephemeral, wait=True, **kwargs)
                await msg.delete(delay=delete_after)
            else:
                msg = await interaction.followup.send(*pos_args, ephemeral=ephemeral, wait=False, **kwargs)
            return msg
        return None


class BaseLayoutView(_ViewMixin, discord.ui.LayoutView):
    """Base class for context-aware Component v2 layout views.

    Stores the command [`Context`][], exposes `._bot`, enforces author-only
    [`interaction_check`][], and provides [`send`][] and [`_update_message`][] helpers.

    Args:
        ctx: The invoking command context.
        timeout: Seconds before the view stops accepting interactions.
    """

    def __init__(self, ctx: Context, *, timeout: float | None = 180.0) -> None:
        """Store `ctx` and initialize the layout view.

        Args:
            ctx: The invoking command context.
            timeout: Seconds before the view stops accepting interactions.
        """
        super().__init__(timeout=timeout)
        self._ctx = ctx
        self._message: discord.Message | None = None

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
                    await self.message.edit(view=self)

        task = asyncio.create_task(edit())
        self._bot.asyncio_pending_tasks.add(task)
        task.add_done_callback(self._bot.asyncio_pending_tasks.discard)
        return task


class BaseModal(_ViewMixin, discord.ui.Modal):
    """Base class for context-aware modals.

    Stores the command [`Context`][], exposes `._bot`, enforces author-only
    [`interaction_check`][], and provides a [`send`][] helper.

    Args:
        ctx: The invoking command context.
        title: The modal title shown to the user (up to 45 characters).
        timeout: Seconds before the modal stops accepting input.
    """

    def __init__(self, ctx: Context, *, title: str, timeout: float | None = None) -> None:
        """Store `ctx` and initialize the modal.

        Args:
            ctx: The invoking command context.
            title: The modal title shown to the user (up to 45 characters).
            timeout: Seconds before the modal stops accepting input.
        """
        super().__init__(title=title, timeout=timeout)
        self._ctx = ctx
        self._message: discord.Message | None = None
