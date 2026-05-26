"""Base classes for context-aware Discord UI components."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import weakref
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

import discord
from discord.app_commands import locale_str

from ..i18n import _
from .ephemeral import using_ephemeral
from .locale import locale_for

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .bot import Bot

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

    class _Common:
        """Shared locale keys and styles for views."""

        BACK = _("view.common.btn.back")
        PREV = _("view.common.btn.prev")
        NEXT = _("view.common.btn.next")
        CANCEL = _("view.common.btn.cancel")
        # @param current: The current page number.
        # @param total: The total page count.
        PAGE = _("view.common.page")
        # @param name: The label text for the back button.
        BACK_CUSTOM = _("view.common.btn.back_custom")

        BACK_STYLE = discord.ButtonStyle.primary
        NAV_STYLE = discord.ButtonStyle.secondary
        CANCEL_STYLE = discord.ButtonStyle.danger

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
        interaction: Invoking interaction for locale capture. `None` uses `config.default_locale`.
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

    def _back_btn(self, callback: Any, *, name: str | None = None) -> discord.ui.Button[Any]:
        """Build a primary back button.

        When *name* is provided the label is built from
        [`_Common.BACK_CUSTOM`][] (`← {name}`).  Otherwise, the label
        defaults to [`_Common.BACK`][] (`← Back`).

        Args:
            callback: Async callable invoked on click.
            name: Optional category/context name to include in the label text.

        Returns:
            The configured back button.
        """
        if name is not None:
            label = self._t(self._Common.BACK_CUSTOM, name=name)
        else:
            label = self._t(self._Common.BACK)
        btn: discord.ui.Button[Any] = discord.ui.Button(label=label, style=self._Common.BACK_STYLE)
        btn.callback = callback
        return btn

    def _cancel_btn(self, callback: Any) -> discord.ui.Button[Any]:
        """Build a danger-styled cancel button with label from [`_Common.CANCEL`][].

        Returns:
            The configured cancel button.
        """
        btn: discord.ui.Button[Any] = discord.ui.Button(
            label=self._t(self._Common.CANCEL), style=self._Common.CANCEL_STYLE
        )
        btn.callback = callback
        return btn

    def _btn(
        self,
        label: str | locale_str,
        style: discord.ButtonStyle,
        callback: Any,
        *,
        disabled: bool = False,
    ) -> discord.ui.Button[Any]:
        """Generic button builder.

        Args:
            label: Button text. A [`locale_str`][] is translated via [`self._t`][] before use.
            style: The button's visual style.
            callback: Async callable invoked on click.
            disabled: Whether the button starts in a disabled state.

        Returns:
            The configured button.
        """
        if isinstance(label, locale_str):
            label = self._t(label)
        btn: discord.ui.Button[Any] = discord.ui.Button(label=label, style=style, disabled=disabled)
        btn.callback = callback
        return btn

    def _gather_interactive(self) -> list[discord.ui.Button[Any] | discord.ui.Select[Any]]:
        """Collect all interactive items from the component tree via walk_children.

        Used by the default [`on_timeout`][] to disable all interactive elements.

        Returns:
            A list of interactive items (buttons, selects, etc.) currently in the view.
        """
        return [item for item in self.walk_children() if isinstance(item, (discord.ui.Button, discord.ui.Select))]

    def _disable_buttons(self) -> bool:
        """Disable all interactive buttons in the view.

        Returns:
            `True` if any buttons were disabled, `False` if they were already all disabled.
        """
        changed = False
        for item in self._gather_interactive():
            if not item.disabled:
                item.disabled = True
                changed = True
        return changed

    async def on_timeout(self) -> None:
        """Disable all interactive items and update the message when the view expires."""
        changed = self._disable_buttons()
        if changed:
            await self._update_message()


class PaginatedLayoutView[T, CT: Mapping[Any, Any]](BaseLayoutView, ABC):
    """Base class for paginated list views with a universal render engine.

    Type parameter `T` is the item type in `_items`. `CT` is the context type
    returned by `_make_context()` and stored in `_context`.

    Subclass responsibilities:
    - Implement `_make_context()` to return a context dict.
    - Implement `_render_body()` to return content children.
    - Override `_accent_color` property for custom container accent.
    - Override `_build_nav_back()` to add a back button to the paginator.
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
        super().__init__(bot, author, interaction=interaction, timeout=timeout)
        self._context: CT = self._make_context()
        self._items: Sequence[T] = []
        self._page: int = 0
        self._page_size: int = 15
        self._title: str | None = None

    @abstractmethod
    def _make_context(self) -> CT:
        """Build the context dict used for rendering the current page.

        The context is stored in `_context` and accessed by subclasses during
        rendering. It carries state such as the current page mode and lookup
        keys.
        """

    @abstractmethod
    def _render_body(self, items: Sequence[T]) -> list[discord.ui.Item[Any]]:
        """Return content children for the current page (body only, no header or nav).

        Args:
            items: Items visible on the current page (`_page_items`).
        """

    def _build_nav_back(self) -> discord.ui.Button[Any] | None:
        """Override to provide a back button in the paginator row.

        Returns:
            A back button, or `None` when no back navigation is needed.
        """
        return None

    @property
    def _accent_color(self) -> discord.Color:
        """Override to customize the Container accent color."""
        return discord.Color.blurple()

    @property
    def total_pages(self) -> int:
        """Total pages based on `_items` and `_page_size`."""
        return max(1, math.ceil(len(self._items) / self._page_size))

    @property
    def _page_items(self) -> Sequence[T]:
        """Items visible on the current page."""
        start = self._page * self._page_size
        return self._items[start : start + self._page_size]

    def _clamp_page(self) -> None:
        """Snap `_page` to a valid range."""
        self._page = max(0, min(self._page, self.total_pages - 1))

    def _build_header(self, title: str) -> str:
        """Return `### {title}` with optional page indicator."""
        header = f"### {title}"
        if self.total_pages > 1:
            indicator = self._t(self._Common.PAGE, current=self._page + 1, total=self.total_pages)
            header = f"{header}  \u00b7  {indicator}"
        return header

    def _paginator_row(
        self, *, back_btn: discord.ui.Button[Any] | None = None
    ) -> discord.ui.ActionRow[Any] | None:
        """Build nav action row. None when single-page and no back_btn.

        Args:
            back_btn: Optional back button built via `_back_btn()`.

        Returns:
            The action row, or `None` if there are no buttons to show.
        """
        has_back = back_btn is not None
        has_nav = self.total_pages > 1

        if not has_back and not has_nav:
            return None

        row: discord.ui.ActionRow[Any] = discord.ui.ActionRow()

        if has_back:
            row.add_item(back_btn)

        if has_nav:

            async def on_prev(interaction: discord.Interaction) -> None:
                self._render_page(page=self._page - 1)
                await self._update_message(interaction)

            async def on_next(interaction: discord.Interaction) -> None:
                self._render_page(page=self._page + 1)
                await self._update_message(interaction)

            prev_btn = discord.ui.Button[Any](
                label=self._t(self._Common.PREV),
                style=self._Common.NAV_STYLE,
                disabled=self._page <= 0,
            )
            prev_btn.callback = on_prev
            row.add_item(prev_btn)

            next_btn = discord.ui.Button[Any](
                label=self._t(self._Common.NEXT),
                style=self._Common.NAV_STYLE,
                disabled=self._page + 1 >= self.total_pages,
            )
            next_btn.callback = on_next
            row.add_item(next_btn)
        return row

    def _render_page(
        self,
        *,
        page: int | None = None,
        title: str | None = None,
        items: Sequence[T] | None = None,
        page_size: int | None = None,
    ) -> None:
        """Clamp page, clear items, call `_render_body()`, wrap in Container.

        Optional kwargs are applied to instance state before rendering.
        When called from paginator callbacks (no args), existing state is reused.

        Args:
            page: If provided, replaces `_page` before clamping.
            title: If provided, replaces `_title`.
            items: If provided, replaces `_items`.
            page_size: If provided, replaces `_page_size`.

        The header and paginator are auto-added:
        - If `_title` is set, a header `TextDisplay` and `Separator` are prepended.
        - `_paginator_row()` is appended if it returns a row.
        """
        if page is not None:
            self._page = page
        if title is not None:
            self._title = title
        if items is not None:
            self._items = items
        if page_size is not None:
            self._page_size = page_size
        self._clamp_page()
        self.clear_items()
        children = self._render_body(self._page_items)
        if self._title is not None:
            children.insert(0, discord.ui.TextDisplay(self._build_header(self._title)))
            children.insert(1, discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        nav = self._paginator_row(back_btn=self._build_nav_back())
        if nav is not None:
            children.append(nav)
        self.add_item(discord.ui.Container(*children, accent_color=self._accent_color))

    def _render_custom_page(self, *containers: discord.ui.Container[Any]) -> None:
        """Clear and replace all items with the given containers.

        Args:
            containers: One or more `Container` instances to display.
        """
        self.clear_items()
        for container in containers:
            self.add_item(container)


class BaseModal(_ViewMixin, discord.ui.Modal):
    """Base class for modals with locale and author support.

    Args:
        bot: The bot instance.
        author: The user who invoked the command — only they can submit the modal.
        title: Modal title (up to 45 characters). A [`locale_str`][] is translated using the
            captured locale.
        interaction: Invoking interaction for locale capture. `None` uses `config.default_locale`.
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
