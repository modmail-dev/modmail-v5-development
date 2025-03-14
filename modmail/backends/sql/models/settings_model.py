"""
modmail.backends.sql.models.settings_model
==========================================
This module defines the SQLAlchemy model for the settings table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends import StatusType

from .base import SQLBase

if TYPE_CHECKING:
    from .activity_model import SQLActivityModel

__all__ = [
    "SQLSettingsModel",
]


class SQLSettingsModel(SQLBase):
    __tablename__ = "settings"

    bot_id: Mapped[int] = mapped_column(primary_key=True, unique=True)
    last_ran_version: Mapped[str | None] = mapped_column(String(32))
    main_category_id: Mapped[int | None]
    fallback_category_id: Mapped[int | None]
    status: Mapped[StatusType | None]
    activity: Mapped[SQLActivityModel | None] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, single_parent=True, lazy="joined"
    )
