"""Common Pydantic model for an instance lock record."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict

__all__ = ["InstanceLockModel"]


class InstanceLockModel(BaseModel):
    """Common immutable model for one instance lock record."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    bot_id: int
    """Discord application ID of the bot that owns this lock."""
    instance_id: str
    """UUID string identifying the running process instance."""
    acquired_at: AwareDatetime
    """UTC-aware timestamp when the lock was first acquired."""
    heartbeat_at: AwareDatetime
    """Most recent heartbeat timestamp, used to detect stale locks."""
    hostname: str
    """Network hostname of the machine holding the lock."""
    pid: int
    """OS process ID of the lock holder on [`hostname`][]."""
