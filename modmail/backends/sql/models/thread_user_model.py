"""SQLAlchemy model for thread users.

This module defines the SQLThreadUserTable class, which represents
the thread user table in the database.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from modmail.backends.common import ThreadUserModel

from .base import SQLBase

__all__ = ["SQLThreadUserTable"]


class SQLThreadUserTable(SQLBase):
    """SQL model representing a user in a thread.

    This model stores information about users participating in a thread,
    including their user ID and name.

    Attributes:
        user_id: The ID of the user in the thread.
        user_name: The name of the user in the thread.
    """

    __tablename__ = "thread_user"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str]

    async def get_model(self) -> ThreadUserModel:
        """Get the thread user model associated with this user.

        Returns:
            ThreadUserModel: The thread user model.
        """
        return ThreadUserModel(
            user_id=self.user_id,
            user_name=self.user_name,
        )
