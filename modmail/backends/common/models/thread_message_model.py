"""Pydantic model for thread messages.

This module defines the ThreadMessageModel class, which represents a message in a
thread. It includes attributes such as the author, content, and metadata like
creation and deletion timestamps.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from modmail.enum import ThreadMessageType

from .thread_dm_message_model import ThreadDMMessageModel
from .thread_user_model import ThreadUserModel

__all__ = ["ThreadMessageModel"]


class ThreadMessageModel(BaseModel):
    """Represents a message in a thread.

    This model stores information about messages in a thread, including the
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
        type: The type of the message (e.g., normal, system).
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    thread_key: str

    message_id: int  # in the thread channel
    dm_messages: list[ThreadDMMessageModel]

    author: ThreadUserModel
    content: str
    created_at: datetime
    edited_at: datetime | None = None
    edited_by: ThreadUserModel | None = None
    deleted_at: datetime | None = None
    deleted_by: ThreadUserModel | None = None

    type: ThreadMessageType
