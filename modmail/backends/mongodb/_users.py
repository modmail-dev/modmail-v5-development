"""MongoDB persistence for ticket user records."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, cast

import pymongo.errors

from modmail.errors import DatabaseOperationError

from ._base import MongoDBBackendBase
from .models import MongoDBTicketUserDocument

if TYPE_CHECKING:
    from beanie.odm.queries.update import UpdateOne


class MongoDBUsersMixin(MongoDBBackendBase):
    """MongoDB mixin for ticket user persistence."""

    async def set_user_unreachable(self, user_id: int, *, unreachable: bool) -> None:
        """Set the `unreachable` flag and update `unreachable_at` on a ticket user document.

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
            await cast(
                "UpdateOne",
                MongoDBTicketUserDocument.find_one(MongoDBTicketUserDocument.id == user_id).update({
                    "$set": {"unreachable": unreachable, "unreachable_at": unreachable_at}
                }),
            )
        except pymongo.errors.PyMongoError as exc:
            raise DatabaseOperationError("Failed to set user unreachable") from exc
