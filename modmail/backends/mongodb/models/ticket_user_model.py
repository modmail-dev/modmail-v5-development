"""Defines the MongoDB ticket user document model.

This module contains the MongoDBTicketUserDocument class, which represents
the ticket user document in the MongoDB database. This document stores
information about users involved in tickets.
"""

from __future__ import annotations

from beanie import Document

from modmail.backends.common import TicketUserModel

__all__ = ["MongoDBTicketUserDocument"]


class MongoDBTicketUserDocument(Document):
    """Represents a MongoDB ticket user document.

    This document stores information about users involved in tickets.

    Attributes:
        id: The unique identifier of the user.
        user_name: The name of the user.
    """

    id: int  # pyright: ignore [reportIncompatibleVariableOverride, reportGeneralTypeIssues]
    user_name: str

    class Settings:
        """Settings for the MongoDB ticket user document."""

        name = "TicketUser"
        validate_on_save = True

    async def get_model(self) -> TicketUserModel:
        """Converts the MongoDBTicketUserDocument to a TicketUserModel.

        Returns:
            The converted TicketUserModel.
        """
        return TicketUserModel(
            user_id=self.id,
            user_name=self.user_name,
        )
