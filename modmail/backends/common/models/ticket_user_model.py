"""Common Pydantic model for a user referenced in a ticket."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from pydantic import AwareDatetime, BaseModel, ConfigDict

if TYPE_CHECKING:
    import discord

__all__ = ["TicketUserModel"]

# TODO: Make the timeout configurable via bot settings.
_UNREACHABLE_TIMEOUT: datetime.timedelta = datetime.timedelta(minutes=30)


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
    unreachable: bool = False
    """Whether the bot has failed to deliver DMs to this user (e.g. DMs disabled or bot blocked)."""
    unreachable_at: AwareDatetime | None = None
    """UTC timestamp of when `unreachable` was last set to `True` (`None` when reachable)."""

    def is_reachable(self) -> bool:
        """Whether the bot should attempt to DM this user.

        Returns `True` when the user is not marked unreachable, or when enough time
        has passed since the last failed delivery that a retry is warranted.  This
        prevents permanently silencing a user whose DMs were only temporarily broken.

        Returns:
            bool: `True` if a DM delivery should be attempted.
        """
        if not self.unreachable:
            return True
        if self.unreachable_at is None:
            # No timestamp recorded — always retry rather than silently skip.
            return True
        return datetime.datetime.now(datetime.UTC) - self.unreachable_at > _UNREACHABLE_TIMEOUT

    @classmethod
    def from_user(cls, user: discord.User | discord.Member | discord.ClientUser) -> TicketUserModel:
        """Construct a [TicketUserModel][]{ data-preview } from a discord.py user or member object.

        This method also resets the unreachable status.

        Args:
            user: The Discord user or member.

        Returns:
            TicketUserModel: Snapshot of the user's current Discord profile.
        """
        return cls(
            user_id=user.id,
            user_name=user.name,
            display_name=user.display_name,
            avatar=str(user.display_avatar),
            unreachable=False,
            unreachable_at=None,
        )
