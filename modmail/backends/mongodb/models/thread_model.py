"""Document model for threads in MongoDB.

This module defines the MongoDBThreadDocument class,
 which represents a thread document in the MongoDB database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import cast

from beanie import Document, Link
from pymongo import ASCENDING, IndexModel

from modmail.backends.common import ThreadModel
from modmail.enum import ThreadStatus

from .thread_user_model import MongoDBThreadUserDocument

__all__ = ["MongoDBThreadDocument"]


class MongoDBThreadDocument(Document):
    """Represents a MongoDB thread document.

    This document stores information about threads in the bot system.

    Attributes:
        bot_id: The unique identifier of the bot.
        key: The unique key for the thread.
        recipients: List of users involved in the thread.
        channel_id: The ID of the channel associated with the thread.
        created_at: The timestamp when the thread was created.
        created_by: The user who created the thread.
        status: The current status of the thread (open, closed, etc.).
        closed_by: The user who closed the thread (if applicable).
        closed_at: The timestamp when the thread was closed (if applicable).
        title: An optional title for the thread.
        nsfw: A boolean indicating if the thread is NSFW (not safe for work).
    """

    bot_id: int
    key: str

    recipients: list[Link[MongoDBThreadUserDocument]]
    channel_id: int

    created_at: datetime
    created_by: Link[MongoDBThreadUserDocument]

    closed_at: datetime | None = None
    closed_by: Link[MongoDBThreadUserDocument] | None = None

    status: ThreadStatus
    title: str | None = None
    nsfw: bool = False

    class Settings:
        """Settings for the MongoDB thread document."""

        name = "Thread"
        validate_on_save = True
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("key", ASCENDING)],
                unique=True,
                name="thread_unique",
            ),
            IndexModel(
                [("bot_id", ASCENDING), ("channel_id", ASCENDING)],
                unique=True,
                name="thread_channel_unique",
            ),
        ]

    async def get_model(self) -> ThreadModel:
        """Converts the MongoDBThreadDocument to a ThreadModel.

        Returns:
            The converted ThreadModel.
        """
        await self.fetch_all_links()  # Make sure all links are fetched

        recipients = await asyncio.gather(*[
            cast(MongoDBThreadUserDocument, recipient).get_model() for recipient in self.recipients
        ])
        created_by = await cast(MongoDBThreadUserDocument, self.created_by).get_model()
        closed_by = await cast(MongoDBThreadUserDocument, self.closed_by).get_model() if self.closed_by else None

        return ThreadModel(
            bot_id=self.bot_id,
            key=self.key,
            recipients=recipients,
            channel_id=self.channel_id,
            created_at=self.created_at,
            created_by=created_by,
            status=self.status,
            closed_by=closed_by,
            closed_at=self.closed_at,
            title=self.title,
            nsfw=self.nsfw,
        )
