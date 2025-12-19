"""MongoDB Ticket Message Document Model.

This module defines the MongoDBTicketMessageDocument class, which represents a
ticket message document in the MongoDB database. This document stores information
about messages in a ticket, including the author, content, and metadata such as
creation and deletion timestamps.
"""

from __future__ import annotations

from datetime import datetime

from beanie import Document, Link
from pydantic import BaseModel
from pymongo import ASCENDING, IndexModel

from modmail.enum import TicketMessageType

from .ticket_user_model import MongoDBTicketUserDocument

__all__ = ["MongoDBTicketDMMessageModel", "MongoDBTicketMessageDocument"]


class MongoDBTicketDMMessageModel(BaseModel):
    """Represents a MongoDB ticket DM message model.

    This model stores information about direct messages in a ticket.

    Attributes:
        message_id: The ID of the message in the DM channel.
        recipient_id: The ID of the recipient user in the ticket.
    """

    message_id: int
    recipient_id: int  # beanie does not support Link[MongoDBTicketUserDocument] in nested models


class MongoDBTicketMessageDocument(Document):
    """Represents a MongoDB ticket message document.

    This document stores information about messages in a ticket, including the
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
        type: The type of the message.
    """

    bot_id: int
    ticket_key: str

    message_id: int  # in the ticket channel
    dm_messages: list[MongoDBTicketDMMessageModel]

    author: Link[MongoDBTicketUserDocument]
    content: str
    created_at: datetime
    edited_at: datetime | None = None
    edited_by: Link[MongoDBTicketUserDocument] | None = None
    deleted_at: datetime | None = None
    deleted_by: Link[MongoDBTicketUserDocument] | None = None

    type: TicketMessageType

    class Settings:
        """Settings for the MongoDB ticket message document."""

        name = "TicketMessage"
        validate_on_save = True
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("ticket_key", ASCENDING), ("message_id", ASCENDING)],
                unique=True,
                name="ticket_message_unique",
            ),
            IndexModel(
                [("bot_id", ASCENDING), ("ticket_key", ASCENDING), ("type", ASCENDING)],
                name="ticket_message_type_lookup",
            ),
            IndexModel(
                [("bot_id", ASCENDING), ("ticket_key", ASCENDING), ("author", ASCENDING)],
                name="ticket_message_author_lookup",
            ),
        ]
