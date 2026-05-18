"""Common Pydantic model for a user referenced in a ticket."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import discord

__all__ = ["TicketUserModel"]


class TicketUserModel(BaseModel):
    """Common immutable model for a user referenced in a ticket."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    user_id: int
    """Discord snowflake ID of the user."""
    user_name: str
    """Username handle captured at interaction time."""
    display_name: str
    """Display name (global name or username) captured at interaction time."""
    avatar: str
    """Display avatar URL captured at interaction time."""

    @classmethod
    def from_user(cls, user: discord.User | discord.Member | discord.ClientUser) -> TicketUserModel:
        """Construct a [TicketUserModel][]{ data-preview } from a discord.py user or member object.

        Args:
            user: The Discord user or member.

        Returns:
            TicketUserModel: Snapshot of the user's current Discord profile.
        """
        return cls(
            user_id=user.id,
            user_name=user.name,
            display_name=user.display_name,
            avatar=str(user.display_avatar.with_size(2048)),
        )
