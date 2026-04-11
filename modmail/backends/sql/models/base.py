"""Declarative base for all SQLAlchemy ORM models.

Defines [`SQLBase`][] with shared [`MetaData`][sqlalchemy.schema.MetaData]
and naming conventions for constraints.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Annotated, Any

from sqlalchemy import BigInteger, Enum, MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy.types import TypeDecorator

from modmail.enum import (
    AccessLevel,
    ActivityType,
    PermissionOverrideValue,
    ProfileType,
    StatusType,
    TicketMessageType,
    TicketStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Dialect


__all__ = ["TABLE_OPTS", "SQLBase", "Snowflake", "UTCTimestamp"]

Snowflake = Annotated[int, mapped_column(BigInteger, autoincrement=False)]
"""Discord snowflake ID stored as `BIGINT`."""

TABLE_OPTS: dict[str, Any] = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
    "mysql_row_format": "DYNAMIC",
    "mariadb_engine": "InnoDB",
    "mariadb_charset": "utf8mb4",
    "mariadb_collate": "utf8mb4_unicode_ci",
    "mariadb_row_format": "DYNAMIC",
}
"""MySQL/MariaDB table options applied to every model via `__table_args__`.

- `utf8mb4` is real 4-byte UTF-8 — MySQL's `utf8` is a broken 3-byte variant.
- `utf8mb4_unicode_ci` is UCA 4.0, compatible with MySQL 5.7+ and MariaDB.
- `DYNAMIC` row format is the InnoDB default since MySQL 5.7 / MariaDB 10.2.
"""


class UTCTimestamp(TypeDecorator[datetime.datetime]):
    """[`datetime`][datetime.datetime] stored as Unix epoch seconds (`BIGINT`), returned as UTC-aware.

    Naive datetimes on write are assumed to be UTC.
    """

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: datetime.datetime | None, dialect: Dialect) -> int | None:
        """Convert a [`datetime`][datetime.datetime] to a UTC Unix timestamp.

        Args:
            value: The datetime to store.
            dialect: The active SQLAlchemy dialect.

        Returns:
            int: Seconds since the Unix epoch.
            None: If `value` is `None`.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            return int(value.replace(tzinfo=datetime.UTC).timestamp())
        return int(value.astimezone(datetime.UTC).timestamp())

    def process_result_value(self, value: int | None, dialect: Dialect) -> datetime.datetime | None:
        """Convert a stored Unix timestamp to a UTC-aware [`datetime`][datetime.datetime].

        Args:
            value: The raw integer from the database driver.
            dialect: The active SQLAlchemy dialect.

        Returns:
            datetime.datetime: A UTC-aware datetime.
            None: If `value` is `None`.
        """
        if value is None:
            return None
        return datetime.datetime.fromtimestamp(value, tz=datetime.UTC)


class SQLBase(DeclarativeBase, AsyncAttrs):
    """Declarative base for all SQLAlchemy ORM models."""

    type_annotation_map: dict[Any, Any] = {
        datetime.datetime: UTCTimestamp(),
        AccessLevel: Enum(AccessLevel, create_constraint=True),
        ActivityType: Enum(ActivityType, create_constraint=True),
        PermissionOverrideValue: Enum(PermissionOverrideValue, create_constraint=True),
        ProfileType: Enum(ProfileType, create_constraint=True),
        StatusType: Enum(StatusType, create_constraint=True),
        TicketMessageType: Enum(TicketMessageType, create_constraint=True),
        TicketStatus: Enum(TicketStatus, create_constraint=True),
    }
    """SQLAlchemy type overrides shared by all subclass models.

    Maps [`datetime`][datetime.datetime] to [UTCTimestamp][]{ data-preview } and each project
    enum to a native `Enum` column with a `CHECK` constraint for dialects that lack native enum
    support (e.g. SQLite).
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

    # Subclasses with a `__table_args__` tuple must include `TABLE_OPTS` as the trailing dict.
    __table_args__ = TABLE_OPTS
