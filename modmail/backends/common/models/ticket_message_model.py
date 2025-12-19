"""Pydantic model for ticket messages.

This module defines the TicketMessageModel class, which represents a message in a
ticket. It includes attributes such as the author, content, and metadata like
creation and deletion timestamps.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from modmail.enum import TicketMessageType

from .ticket_dm_message_model import TicketDMMessageModel
from .ticket_user_model import TicketUserModel

__all__ = ["TicketMessageModel"]


class TicketMessageModel(BaseModel):
    """Represents a message in a ticket.

    This model stores information about messages in a ticket, including the
    author, content, and metadata such as creation and deletion timestamps.

    Attributes:
        bot_id: The unique identifier of the bot.
        ticket_key: The unique key for the ticket.
        message_id: The ID of the message in the ticket channel.
        dm_messages: List of direct messages associated with this ticket message.
        author: The author of the message (user).
        content: The content of the message.
        created_at: The timestamp when the message was created.
        edited_at: The timestamp when the message was last edited (if applicable).
        edited_by: The user who last edited the message (if applicable).
        deleted_at: The timestamp when the message was deleted (if applicable).
        deleted_by: The user who deleted the message (if applicable).
        type: The type of the message (e.g., normal, system).
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    ticket_key: str

    message_id: int  # in the ticket channel
    dm_messages: list[TicketDMMessageModel]

    author: TicketUserModel
    content: str
    created_at: datetime
    edited_at: datetime | None = None
    edited_by: TicketUserModel | None = None
    deleted_at: datetime | None = None
    deleted_by: TicketUserModel | None = None

    type: TicketMessageType
