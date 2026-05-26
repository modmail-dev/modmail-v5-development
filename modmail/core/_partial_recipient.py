"""Lightweight Discord-user-compatible wrapper backed by stored DB data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    import datetime

    from ..backends import TicketUserModel
    from .bot import Bot

__all__ = ["PartialRecipient"]


class PartialRecipient:
    """Ticket recipient built from stored [`TicketUserModel`][] data.

    Provides the Discord-like attribute surface used throughout [`TicketView`][] without
    ever calling `fetch_user()`.  DM delivery goes through [`bot.create_dm`][] with a
    [`discord.Object`][] (which only requires the user's ID), so no live user object is
    needed.
    """

    __slots__ = ("_bot", "_model")

    def __init__(self, bot: Bot, model: TicketUserModel) -> None:
        """Attach the bot and the stored user model.

        Args:
            bot: The [`Bot`][] instance used for DM channel creation.
            model: Stored snapshot of the user's profile.
        """
        self._bot = bot
        self._model = model

    @property
    def user_model(self) -> TicketUserModel:
        """The underlying stored [`TicketUserModel`][]."""
        return self._model

    @property
    def id(self) -> int:
        """Discord snowflake user ID."""
        return self._model.user_id

    @property
    def name(self) -> str:
        """Username handle."""
        return self._model.user_name

    @property
    def display_name(self) -> str:
        """Display name as last seen (global name or username)."""
        return self._model.display_name

    @property
    def mention(self) -> str:
        """Discord mention string (`<@id>`)."""
        return f"<@{self.id}>"

    @property
    def created_at(self) -> datetime.datetime:
        """Account creation time derived from the Discord snowflake."""
        return discord.utils.snowflake_time(self.id)

    @property
    def display_avatar(self) -> str:
        """Display avatar URL as last seen."""
        return self._model.avatar

    def is_reachable(self) -> bool:
        """Whether the bot should attempt to DM this user.

        Delegates to [`ReachabilityRegistry.is_reachable`][], which returns `True`
        when the user is not marked unreachable, or when the unreachable timeout
        has expired.

        Returns:
            bool: `True` if a DM delivery should be attempted.
        """
        return self._bot.reachability.is_reachable(self.id)

    def mark_unreachable(self) -> None:
        """Mark this recipient as unreachable in the in-memory registry.

        The expiry logic in [`ReachabilityRegistry.is_reachable`][] will
        automatically clear the flag after the configured timeout.
        """
        self._bot.reachability.mark_unreachable(self.id)

    def mark_reachable(self) -> None:
        """Clear any unreachable record for this recipient.

        Called when the user proves reachability by sending a DM.
        """
        self._bot.reachability.mark_reachable(self.id)

    async def send(self, *args: Any, **kwargs: Any) -> discord.Message:
        """Open or reuse the user's DM channel and send a message.

        Uses [`bot.create_dm`][] with a [`discord.Object`][] so that no `fetch_user()`
        API call is required.

        Args:
            *args: Positional arguments forwarded to `.send()`.
            **kwargs: Keyword arguments forwarded to `.send()`.

        Returns:
            discord.Message: The sent message.

        Raises:
            discord.Forbidden: If the user has DMs disabled or has blocked the bot.
            discord.HttpException: If an error occurs sending the message or creating the DM channel.
        """
        # create_dm() uses LRU to cache the dm channels
        channel = await self._bot.create_dm(discord.Object(id=self.id))
        return await self._bot.send_message(*args, channel=channel, **kwargs)

    def __str__(self) -> str:
        """Return the display name.

        Returns:
            str: The user's display name as last seen.
        """
        return self.display_name

    def __eq__(self, other: object) -> bool:
        """Compare by Discord user ID.

        Returns:
            bool: `True` if both objects share the same Discord snowflake ID,
                `NotImplemented` if `other` is not a supported type.
        """
        if isinstance(other, discord.abc.Snowflake | PartialRecipient):
            return self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        """Hash by Discord user ID.

        Returns:
            int: Hash of the Discord snowflake user ID.
        """
        return hash(self.id)

    def __repr__(self) -> str:
        """Return a debug representation.

        Returns:
            str: A string showing the user ID, username, and reachability.
        """
        return f"<PartialRecipient id={self.id} name={self.name!r} unreachable={not self.is_reachable()}>"
