"""Pydantic model for a direct message in a ticket.

This module defines the TicketDMMessageModel class, which represents a direct
message (DM) in a ticket.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .ticket_user_model import TicketUserModel

__all__ = ["TicketDMMessageModel"]


class TicketDMMessageModel(BaseModel):
    """Represents a direct message in a ticket.

    This model stores information about direct messages in a ticket.

    Attributes:
        message_id: The ID of the message in the DM channel.
        ticket_message_id: The ID of the message in the ticket channel.
        recipient: The recipient of the DM message (user).
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    message_id: int  # in the DM channel
    ticket_message_id: int  # in the ticket channel
    recipient: TicketUserModel
