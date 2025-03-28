"""Declarative base class for all SQLAlchemy models.

This module defines the base class used by all SQLAlchemy models in the application,
providing common functionality and configuration.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

__all__ = ["SQLBase"]


class SQLBase(DeclarativeBase, AsyncAttrs):
    """Base class for all SQLAlchemy models.

    This base class provides common SQLAlchemy functionality and configuration
    for all database model classes, including naming conventions for database
    constraints and asynchronous attribute access.
    """

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
