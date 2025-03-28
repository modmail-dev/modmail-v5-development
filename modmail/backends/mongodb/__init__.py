"""Provides MongoDB related classes and functions.

This package contains MongoDB client implementation and related utilities for
database operations.
"""

from __future__ import annotations

from .client import MongoDBClient

__all__ = [
    "MongoDBClient",
]
