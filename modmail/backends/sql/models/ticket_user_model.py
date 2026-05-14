"""SQLAlchemy model for the ticket user table."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Mapped, mapped_column

from modmail.backends.common import TicketUserModel

from .base import Snowflake, SQLBase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["SQLTicketUserTable"]


class SQLTicketUserTable(SQLBase):
    """SQL model for a unique Discord user referenced by tickets and messages.

    Shared across all tickets, with one row per unique user.

    **Primary key:** [`user_id`][]
    """

    __tablename__ = "ticket_user"

    user_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    """Discord snowflake user ID."""
    user_name: Mapped[str] = mapped_column(String(128))
    """Username handle captured at interaction time."""
    display_name: Mapped[str] = mapped_column(String(128))
    """Display name (global name or username) captured at interaction time."""
    avatar: Mapped[str] = mapped_column(String(512))
    """Display avatar URL captured at interaction time."""
    unreachable: Mapped[bool] = mapped_column(Boolean, default=False)
    """Whether the bot has failed to deliver DMs to this user (e.g. DMs disabled or bot blocked)."""
    unreachable_at: Mapped[datetime.datetime | None]
    """UTC timestamp of when `unreachable` was last set to `True` (`None` when reachable)."""

    def to_model(self) -> TicketUserModel:
        """Convert this row to a [TicketUserModel][]{ data-preview }.

        Returns:
            TicketUserModel: The converted common user model.
        """
        return TicketUserModel(
            user_id=self.user_id,
            user_name=self.user_name,
            display_name=self.display_name,
            avatar=self.avatar,
            unreachable=self.unreachable,
            unreachable_at=self.unreachable_at,
        )

    @classmethod
    async def put_many(cls, *models: TicketUserModel, session: AsyncSession) -> None:
        """Upsert users into the `ticket_user` table, updating all mutable fields on conflict.

        Deduplicates by [`user_id`][], then issues a single dialect-specific upsert.
        Mutable columns (everything except the primary key) are derived at call time from the
        table definition, so adding a column to the ORM model is the only change needed.

        Note:
            Must be called inside an active `session.begin()` block.

        Args:
            *models: [TicketUserModel][]{ data-preview } records to upsert,
                possibly with duplicates.
            session: An open [AsyncSession][] with an active transaction.

        Raises:
            RuntimeError: If called outside an active `session.begin()` block.
            sqlalchemy.exc.SQLAlchemyError: If an unexpected database error occurs.
        """
        if not session.in_transaction():
            raise RuntimeError("put_many must be called inside an active session.begin() block")

        if not models:
            return

        unique_users = {u.user_id: u for u in models}
        values = [
            {
                "user_id": u.user_id,
                "user_name": u.user_name,
                "display_name": u.display_name,
                "avatar": u.avatar,
                "unreachable": u.unreachable,
                "unreachable_at": u.unreachable_at,
            }
            for u in unique_users.values()
        ]
        update_cols = [col.key for col in cls.__table__.columns if not col.primary_key]

        dialect_name = session.get_bind().dialect.name
        if dialect_name == "sqlite":
            stmt = sqlite_insert(cls).values(values)
            # stmt.excluded refers to the row that lost the conflict; getattr resolves its columns.
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={col: getattr(stmt.excluded, col) for col in update_cols},
                )
            )
        elif dialect_name == "postgresql":
            stmt = postgresql_insert(cls).values(values)
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={col: getattr(stmt.excluded, col) for col in update_cols},
                )
            )
        elif dialect_name in {"mysql", "mariadb"}:
            stmt = mysql_insert(cls).values(values)
            # stmt.inserted refers to the proposed row values used in ON DUPLICATE KEY UPDATE.
            await session.execute(
                stmt.on_duplicate_key_update(**{col: getattr(stmt.inserted, col) for col in update_cols})
            )
        else:
            # Generic: 1 SELECT + 1 executemany UPDATE + 1 batch INSERT — O(1) round trips.
            # session.execute(update(cls), list) uses SA 2.0 bulk-update-by-PK: WHERE is built
            # from "user_id" in each dict and sent as a single executemany call.
            existing_ids = set(
                (await session.execute(select(cls.user_id).where(cls.user_id.in_(unique_users.keys())))).scalars()
            )
            to_update = [v for v in values if v["user_id"] in existing_ids]
            to_insert = [v for v in values if v["user_id"] not in existing_ids]
            if to_update:
                await session.execute(update(cls), to_update)
            if to_insert:
                session.add_all(cls(**v) for v in to_insert)
