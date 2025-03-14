"""
modmail.backends.sql.models.activity_model
==========================================
This module defines the SQLAlchemy model for the activity table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modmail.backends import ActivityType

from .base import SQLBase

if TYPE_CHECKING:
    from .settings_model import SQLSettingsModel

__all__ = ["SQLActivityModel"]


class SQLActivityModel(SQLBase):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ActivityType]
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(2048))
    settings: Mapped[SQLSettingsModel] = relationship(back_populates="activity", single_parent=True)
