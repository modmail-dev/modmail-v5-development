"""Pydantic model for a direct message in a thread.

This module defines the ThreadDMMessageModel class, which represents a direct
message (DM) in a thread.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .thread_user_model import ThreadUserModel

__all__ = ["ThreadDMMessageModel"]


class ThreadDMMessageModel(BaseModel):
    """Represents a direct message in a thread.

    This model stores information about direct messages in a thread.

    Attributes:
        message_id: The ID of the message in the DM channel.
        thread_message_id: The ID of the message in the thread channel.
        recipient: The recipient of the DM message (user).
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    message_id: int  # in the DM channel
    thread_message_id: int  # in the thread channel
    recipient: ThreadUserModel
