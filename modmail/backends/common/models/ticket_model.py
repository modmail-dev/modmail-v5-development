"""Common Pydantic model for a Modmail ticket."""

from __future__ import annotations

import secrets
from string import ascii_letters, digits

from pydantic import AwareDatetime, BaseModel, ConfigDict

from modmail.enum import TicketStatus

from .ticket_user_model import TicketUserModel

__all__ = ["TicketModel"]


class TicketModel(BaseModel):
    """Common immutable model for a Modmail ticket."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    """Discord application ID of the bot that owns this ticket."""
    key: str
    """Random 12-character alphanumeric ticket identifier."""
    recipients: list[TicketUserModel]
    """Non-staff users who are parties to this ticket."""
    channel_id: int
    """Discord channel or forum-thread ID where staff interact."""
    created_at: AwareDatetime
    """UTC-aware timestamp when the ticket was opened."""
    created_by: TicketUserModel
    """[TicketUserModel][]{ data-preview } who initiated the ticket."""
    closed_at: AwareDatetime | None = None
    """UTC-aware timestamp when closed (`None` if [`closed_by`][] is unset)."""
    closed_by: TicketUserModel | None = None
    """[TicketUserModel][]{ data-preview } who closed the ticket (`None` if [`closed_at`][] is unset)."""
    log_channel_message_id: int | None = None
    """Summary message ID posted to the log channel on closure (`None` if not yet posted)."""
    status: TicketStatus
    """Current lifecycle state as a [TicketStatus][]{ data-preview }."""
    title: str | None = None
    """Human-readable title for the ticket (`None` if unset)."""
    nsfw: bool = False
    """Whether the ticket channel is marked as age-restricted in Discord."""

    @staticmethod
    def generate_key() -> str:
        """Generate a cryptographically random 12-character alphanumeric key.

        Returns:
            str: A unique key suitable for use as a ticket identifier.
        """
        length = 12
        return "".join(secrets.choice(ascii_letters + digits) for _ in range(length))
