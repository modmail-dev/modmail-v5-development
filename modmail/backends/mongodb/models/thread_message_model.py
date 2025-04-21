"""MongoDB Thread Message Document Model.

This module defines the MongoDBThreadMessageDocument class, which represents a
thread message document in the MongoDB database. This document stores information
about messages in a thread, including the author, content, and metadata such as
creation and deletion timestamps.
"""

from __future__ import annotations

from datetime import datetime

from beanie import Document, Link
from pydantic import BaseModel
from pymongo import ASCENDING, IndexModel

from modmail.enum import ThreadMessageType

from .thread_user_model import MongoDBThreadUserDocument

__all__ = ["MongoDBThreadDMMessageModel", "MongoDBThreadMessageDocument"]


class MongoDBThreadDMMessageModel(BaseModel):
    """Represents a MongoDB thread DM message model.

    This model stores information about direct messages in a thread.

    Attributes:
        message_id: The ID of the message in the DM channel.
        recipient_id: The ID of the recipient user in the thread.
    """

    message_id: int
    recipient_id: int  # beanie does not support Link[MongoDBThreadUserDocument] in nested models


class MongoDBThreadMessageDocument(Document):
    """Represents a MongoDB thread message document.

    This document stores information about messages in a thread, including the
    author, content, and metadata such as creation and deletion timestamps.

    Attributes:
        bot_id: The unique identifier of the bot.
        thread_key: The unique key for the thread.
        message_id: The ID of the message in the thread channel.
        dm_messages: List of direct messages associated with this thread message.
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
    thread_key: str

    message_id: int  # in the thread channel
    dm_messages: list[MongoDBThreadDMMessageModel]

    author: Link[MongoDBThreadUserDocument]
    content: str
    created_at: datetime
    edited_at: datetime | None = None
    edited_by: Link[MongoDBThreadUserDocument] | None = None
    deleted_at: datetime | None = None
    deleted_by: Link[MongoDBThreadUserDocument] | None = None

    type: ThreadMessageType

    class Settings:
        """Settings for the MongoDB thread message document."""

        name = "ThreadMessage"
        validate_on_save = True
        indexes = [
            IndexModel(
                [("bot_id", ASCENDING), ("thread_key", ASCENDING), ("message_id", ASCENDING)],
                unique=True,
                name="thread_message_unique",
            )
        ]
