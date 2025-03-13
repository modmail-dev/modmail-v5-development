"""
modmail.backends.sql.models.activity_model
==========================================
This module defines the SQLAlchemy model for the activity table.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .settings_model import Settings

__all__ = ["Activity", "ActivityType"]


class ActivityType(enum.Enum):
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ActivityType]
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(2048))
    settings: Mapped[Settings] = relationship(back_populates="activity", single_parent=True)
