"""Pydantic model for a ticket in the Modmail system.

This model contains information about the ticket, including its participants,
status, and metadata.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from string import ascii_letters, digits

from pydantic import BaseModel, ConfigDict

from modmail.enum import TicketStatus

from .ticket_user_model import TicketUserModel

__all__ = ["TicketModel"]


class TicketModel(BaseModel):
    """Represents a ticket in the Modmail system.

    This model contains information about the ticket, including its participants,
    status, and metadata.

    Attributes:
        bot_id: The unique identifier of the bot.
        key: The unique key for the ticket (12 characters long).
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

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    key: str

    recipients: list[TicketUserModel]
    channel_id: int

    created_at: datetime
    created_by: TicketUserModel

    closed_at: datetime | None = None
    closed_by: TicketUserModel | None = None

    log_channel_message_id: int | None = None

    status: TicketStatus
    title: str | None = None
    nsfw: bool = False

    @staticmethod
    def generate_key() -> str:
        """Generates a unique key for the ticket.

        Returns:
            A unique key for the ticket.
        """
        length = 12
        return "".join(secrets.choice(ascii_letters + digits) for _ in range(length))
