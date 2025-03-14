"""
modmail.backends.sql.models.activity_model
==========================================
This module defines the SQLAlchemy model for the activity table.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from modmail.backends import ActivityType

from .base import SQLBase

__all__ = ["SQLActivityModel"]


class SQLActivityModel(SQLBase):
    __tablename__ = "activity"

    bot_id: Mapped[int] = mapped_column(ForeignKey("settings.bot_id", ondelete="CASCADE"), primary_key=True)
    type: Mapped[ActivityType]
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(2048))
