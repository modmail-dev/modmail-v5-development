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
    """Display name captured at ticket time."""
    avatar: str
    """Display avatar URL captured at ticket time."""

    @classmethod
    def from_user(cls, user: discord.User | discord.Member | discord.ClientUser) -> TicketUserModel:
        """Construct a [TicketUserModel][]{ data-preview } from a discord.py user or member object.

        Args:
            user: The Discord user or member.

        Returns:
            TicketUserModel: Constructed from the user's Discord ID, display name, and
            display avatar URL.
        """
        return cls(user_id=user.id, user_name=user.name, avatar=str(user.display_avatar))
