"""SQLAlchemy model for ticket users.

This module defines the SQLTicketUserTable class, which represents
the ticket user table in the database.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from modmail.backends.common import TicketUserModel

from .base import SQLBase

__all__ = ["SQLTicketUserTable"]


class SQLTicketUserTable(SQLBase):
    """SQL model representing a user in a ticket.

    This model stores information about users participating in a ticket,
    including their user ID and name.

    Attributes:
        user_id: The ID of the user in the ticket.
        user_name: The name of the user in the ticket.
    """

    __tablename__ = "ticket_user"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str]

    async def get_model(self) -> TicketUserModel:
        """Get the ticket user model associated with this user.

        Returns:
            TicketUserModel: The ticket user model.
        """
        return TicketUserModel(
            user_id=self.user_id,
            user_name=self.user_name,
        )
