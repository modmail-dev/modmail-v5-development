"""SQLAlchemy model for the instance lock table."""

from __future__ import annotations

import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Snowflake, SQLBase

__all__ = ["SQLInstanceLockTable"]


class SQLInstanceLockTable(SQLBase):
    """SQL model for the per-bot-id instance lock.

    **Primary key:** [`bot_id`][]
    """

    __tablename__ = "instance_lock"

    bot_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    """Discord application ID of the bot that owns this lock."""
    instance_id: Mapped[str] = mapped_column(String(36))
    """UUID string identifying the running process instance."""
    acquired_at: Mapped[datetime.datetime]
    """UTC-aware timestamp when the lock was first acquired."""
    heartbeat_at: Mapped[datetime.datetime]
    """Most recent heartbeat timestamp, used to detect stale locks."""
    hostname: Mapped[str] = mapped_column(String(255))
    """Network hostname of the machine holding the lock."""
    pid: Mapped[int] = mapped_column(Integer())
    """OS process ID of the lock holder on [`hostname`][]."""
