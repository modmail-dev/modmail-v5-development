"""Common Pydantic model for a ticket message."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict

from modmail.enum import TicketMessageType

from .ticket_dm_message_model import TicketDMMessageModel
from .ticket_user_model import TicketUserModel

__all__ = ["TicketMessageModel"]


class TicketMessageModel(BaseModel):
    """Common immutable model for a message in a ticket.

    Since a ticket can have multiple recipients, DM delivery records are
    stored in [`dm_messages`][], one per recipient.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    """Discord application ID of the bot that owns this message."""
    ticket_key: str
    """Key of the parent ticket."""
    message_id: int
    """Discord message ID in the staff-side ticket channel."""
    dm_messages: list[TicketDMMessageModel]
    """[TicketDMMessageModel][]{ data-preview } delivery records for this message, one per recipient."""
    author: TicketUserModel
    """[TicketUserModel][]{ data-preview } who sent the message."""
    content: str
    """Raw text content of the message."""
    created_at: AwareDatetime
    """UTC-aware timestamp when the message was sent."""
    edited_at: AwareDatetime | None = None
    """UTC-aware timestamp of the most recent edit (`None` if [`edited_by`][] is unset)."""
    edited_by: TicketUserModel | None = None
    """[TicketUserModel][]{ data-preview } who made the edit (`None` if [`edited_at`][] is unset)."""
    deleted_at: AwareDatetime | None = None
    """UTC-aware timestamp when the message was deleted (`None` if [`deleted_by`][] is unset)."""
    deleted_by: TicketUserModel | None = None
    """[TicketUserModel][]{ data-preview } who deleted the message (`None` if not deleted)."""
    type: TicketMessageType
    """Message type as a [TicketMessageType][]{ data-preview }."""
