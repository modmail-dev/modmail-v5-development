"""SQL persistence for ticket user records."""

from __future__ import annotations

import datetime

import sqlalchemy.exc
from sqlalchemy import update

from modmail.errors import DatabaseOperationError

from ._base import SQLBackendBase
from .models import SQLTicketUserTable


class SQLUsersMixin(SQLBackendBase):
    """SQL mixin for ticket user persistence."""

    async def set_user_unreachable(self, user_id: int, *, unreachable: bool) -> None:
        """Set the `unreachable` flag and update `unreachable_at` on a ticket user record.

        When `unreachable` is `True`, `unreachable_at` is set to the current UTC time so
        the timeout logic in [`TicketUserModel.is_reachable`][] can expire the flag automatically.
        When `unreachable` is `False`, `unreachable_at` is cleared to `None`.

        Args:
            user_id: Discord snowflake ID of the user.
            unreachable: The value to set.

        Raises:
            DatabaseOperationError: If an unexpected database error occurs.
        """
        unreachable_at = datetime.datetime.now(datetime.UTC) if unreachable else None
        try:
            async with self.session() as session, session.begin():
                await session.execute(
                    update(SQLTicketUserTable)
                    .where(SQLTicketUserTable.user_id == user_id)
                    .values(unreachable=unreachable, unreachable_at=unreachable_at)
                )
        except sqlalchemy.exc.SQLAlchemyError as exc:
            raise DatabaseOperationError("Failed to set user unreachable") from exc
