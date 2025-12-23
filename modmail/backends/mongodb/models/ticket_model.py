"""Document model for tickets in MongoDB.

This module defines the MongoDBTicketDocument class,
 which represents a ticket document in the MongoDB database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import cast

from beanie import Document, Link
from pymongo import ASCENDING, IndexModel

from modmail.backends.common import TicketModel
from modmail.enum import TicketStatus

from .ticket_user_model import MongoDBTicketUserDocument

__all__ = ["MongoDBTicketDocument"]


class MongoDBTicketDocument(Document):
    """Represents a MongoDB ticket document.

    This document stores information about tickets in the bot system.

    Attributes:
        bot_id: The unique identifier of the bot.
        key: The unique key for the ticket.
        recipients: List of users involved in the ticket.
        channel_id: The ID of the channel associated with the ticket.
        created_at: The timestamp when the ticket was created.
        created_by: The user who created the ticket.
        status: The current status of the ticket (open, closed, etc.).
        closed_by: The user who closed the ticket (if applicable).
        closed_at: The timestamp when the ticket was closed (if applicable).
        log_channel_message_id: The ID of the thread info message when sent to log channel.
        title: An optional title for the ticket.
        nsfw: A boolean indicating if the ticket is NSFW (not safe for work).
    """

    bot_id: int
    key: str

    recipients: list[Link[MongoDBTicketUserDocument]]
    channel_id: int

    created_at: datetime
    created_by: Link[MongoDBTicketUserDocument]

    closed_at: datetime | None = None
    closed_by: Link[MongoDBTicketUserDocument] | None = None

    log_channel_message_id: int | None = None

    status: TicketStatus
    title: str | None = None
    nsfw: bool = False

    class Settings:
        """Settings for the MongoDB ticket document."""

        name = "Ticket"
        validate_on_save = True
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("key", ASCENDING)],
                unique=True,
                name="ticket_unique",
            ),
            IndexModel(
                [("bot_id", ASCENDING), ("channel_id", ASCENDING)],
                unique=True,
                name="ticket_channel_unique",
            ),
        ]

    async def get_model(self) -> TicketModel:
        """Converts the MongoDBTicketDocument to a TicketModel.

        Returns:
            The converted TicketModel.
        """
        await self.fetch_all_links()  # Make sure all links are fetched

        recipients = await asyncio.gather(*[
            cast(MongoDBTicketUserDocument, recipient).get_model() for recipient in self.recipients
        ])
        created_by = await cast(MongoDBTicketUserDocument, self.created_by).get_model()
        closed_by = await cast(MongoDBTicketUserDocument, self.closed_by).get_model() if self.closed_by else None

        return TicketModel(
            bot_id=self.bot_id,
            key=self.key,
            recipients=recipients,
            channel_id=self.channel_id,
            created_at=self.created_at,
            created_by=created_by,
            status=self.status,
            closed_by=closed_by,
            closed_at=self.closed_at,
            log_channel_message_id=self.log_channel_message_id,
            title=self.title,
            nsfw=self.nsfw,
        )
