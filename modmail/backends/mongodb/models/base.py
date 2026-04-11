"""Shared base types for MongoDB Beanie document models."""

from __future__ import annotations

import datetime
from typing import Annotated

from pydantic import BeforeValidator

__all__ = ["BSON_ENCODERS", "UTCTimestamp"]


def _to_utc_datetime(v: object) -> datetime.datetime:
    """Normalize `v` to a UTC-aware [`datetime`][datetime.datetime].

    Args:
        v: A [`datetime`][datetime.datetime] (naive or aware), or a numeric Unix timestamp.

    Returns:
        datetime.datetime: UTC-aware datetime.

    Raises:
        ValueError: If `v` is not a recognized type.
    """
    if isinstance(v, (int, float)):
        return datetime.datetime.fromtimestamp(v, tz=datetime.UTC)
    if isinstance(v, datetime.datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=datetime.UTC)
        return v.astimezone(datetime.UTC)
    raise ValueError(f"Expected datetime or numeric timestamp, got {type(v)!r}")


def _datetime_to_timestamp(v: datetime.datetime) -> int:
    """Encode a [`datetime`][datetime.datetime] as a Unix epoch seconds integer for BSON storage.

    Returns:
        int: Seconds since the Unix epoch.
    """
    return int(v.timestamp())


UTCTimestamp = Annotated[
    datetime.datetime,
    BeforeValidator(_to_utc_datetime),
]
"""[`datetime`][datetime.datetime] stored as Unix epoch seconds (`int`), returned as UTC-aware.

Naive datetimes on write are assumed to be UTC. Storage as `int` is enforced via each Beanie
document's `Settings.bson_encoders`, since Beanie bypasses Pydantic serializers when encoding BSON.
"""

BSON_ENCODERS: dict[type, object] = {datetime.datetime: _datetime_to_timestamp}
"""BSON encoder map that stores [`datetime`][datetime.datetime] as Unix epoch seconds.

Add to every Beanie document's `Settings.bson_encoders`.
"""
