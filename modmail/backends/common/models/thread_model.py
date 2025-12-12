"""Pydantic model for a thread in the Modmail system.

This model contains information about the thread, including its participants,
status, and metadata.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from string import ascii_letters, digits

from pydantic import BaseModel, ConfigDict

from modmail.enum import ThreadStatus

from .thread_user_model import ThreadUserModel

__all__ = ["ThreadModel"]


class ThreadModel(BaseModel):
    """Represents a thread in the Modmail system.

    This model contains information about the thread, including its participants,
    status, and metadata.

    Attributes:
        bot_id: The unique identifier of the bot.
        key: The unique key for the thread (12 characters long).
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

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    key: str

    recipients: list[ThreadUserModel]
    channel_id: int

    created_at: datetime
    created_by: ThreadUserModel

    closed_at: datetime | None = None
    closed_by: ThreadUserModel | None = None

    status: ThreadStatus
    title: str | None = None
    nsfw: bool = False

    @staticmethod
    def generate_key() -> str:
        """Generates a unique key for the thread.

        Returns:
            A unique key for the thread.
        """
        length = 12
        return "".join(secrets.choice(ascii_letters + digits) for _ in range(length))
