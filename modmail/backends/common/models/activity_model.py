"""
modmail.backends.common.models.activity_model
==============================================
This module defines the Pydantic models for Activity and enumerated types for ActivityType.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict

__all__ = [
    "Activity",
    "ActivityType",
]


class ActivityType(enum.Enum):
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5


class Activity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: ActivityType
    name: str
    url: str | None = None  # url for streaming activity, 'None' not enforced for other types
