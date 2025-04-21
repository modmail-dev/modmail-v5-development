"""Defines the MongoDB thread user document model.

This module contains the MongoDBThreadUserDocument class, which represents
the thread user document in the MongoDB database. This document stores
information about users involved in threads.
"""

from __future__ import annotations

from beanie import Document

from modmail.backends.common import ThreadUserModel

__all__ = ["MongoDBThreadUserDocument"]


class MongoDBThreadUserDocument(Document):
    """Represents a MongoDB thread user document.

    This document stores information about users involved in threads.

    Attributes:
        id: The unique identifier of the user.
        user_name: The name of the user.
    """

    id: int  # pyright: ignore [reportIncompatibleVariableOverride, reportGeneralTypeIssues]
    user_name: str

    class Settings:
        """Settings for the MongoDB thread user document."""

        name = "ThreadUser"
        validate_on_save = True

    async def get_model(self) -> ThreadUserModel:
        """Converts the MongoDBThreadUserDocument to a ThreadUserModel.

        Returns:
            The converted ThreadUserModel.
        """
        return ThreadUserModel(
            user_id=self.id,
            user_name=self.user_name,
        )
