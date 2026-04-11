"""Common Pydantic model for a DM delivery record in a ticket."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .ticket_user_model import TicketUserModel

__all__ = ["TicketDMMessageModel"]


class TicketDMMessageModel(BaseModel):
    """Common immutable model for one DM delivery of a ticket message.

    Since a ticket can have multiple recipients, one [TicketMessageModel][]{ data-preview }
    has one of these per recipient.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    message_id: int
    """Discord message ID in the recipient's DM channel."""
    ticket_message_id: int
    """Discord message ID in the staff-side ticket channel."""
    recipient: TicketUserModel
    """[TicketUserModel][]{ data-preview } who received this DM."""
