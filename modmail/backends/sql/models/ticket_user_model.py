"""SQLAlchemy model for the ticket user table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, select
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
    """Display name captured at ticket time."""
    avatar: Mapped[str] = mapped_column(String(512))
    """Display avatar URL captured at ticket time."""

    def to_model(self) -> TicketUserModel:
        """Convert this row to a [TicketUserModel][]{ data-preview }.

        Returns:
            TicketUserModel: The converted common user model.
        """
        return TicketUserModel(
            user_id=self.user_id,
            user_name=self.user_name,
            avatar=self.avatar,
        )

    @classmethod
    async def put_many(cls, *models: TicketUserModel, session: AsyncSession) -> None:
        """Insert any users not already present in the `ticket_user` table.

        Deduplicates by [`user_id`][], then issues a single statement for dialects
        that support conflict-free bulk insert (SQLite, PostgreSQL, MySQL/MariaDB),
        or falls back to a `SELECT` + bulk `INSERT` for other dialects.

        Note:
            Must be called inside an active `session.begin()` block.

        Args:
            *models: [TicketUserModel][]{ data-preview } records to ensure exist,
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
            {"user_id": u.user_id, "user_name": u.user_name, "avatar": u.avatar} for u in unique_users.values()
        ]

        dialect_name = session.get_bind().dialect.name
        if dialect_name == "sqlite":
            await session.execute(sqlite_insert(cls).values(values).on_conflict_do_nothing())
        elif dialect_name == "postgresql":
            await session.execute(postgresql_insert(cls).values(values).on_conflict_do_nothing())
        elif dialect_name in {"mysql", "mariadb"}:
            await session.execute(mysql_insert(cls).values(values).prefix_with("IGNORE"))
        else:
            existing_ids = set(
                (await session.execute(select(cls.user_id).where(cls.user_id.in_(unique_users.keys()))))
                .scalars()
                .all()
            )
            session.add_all(
                cls(user_id=u.user_id, user_name=u.user_name, avatar=u.avatar)
                for u in unique_users.values()
                if u.user_id not in existing_ids
            )
