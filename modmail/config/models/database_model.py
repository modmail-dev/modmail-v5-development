"""Database configuration model."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, SecretStr, ValidationInfo, field_validator

if TYPE_CHECKING:
    from typing import Literal

__all__ = ["DatabaseConfig"]

logger = logging.getLogger(__name__)

_DIALECT_DRIVERS: dict[str, str] = {
    "sqlite": "aiosqlite",
    "postgresql": "asyncpg",
    "postgres": "asyncpg",
    "mysql": "asyncmy",
    "mariadb": "asyncmy",
}

_DIALECT_ALIASES: dict[str, str] = {
    "postgres": "postgresql",
}

_MONGO_PREFIXES = ("mongodb://", "mongodb+srv://")


class DatabaseConfig(
    BaseModel,
    frozen=True,
    str_strip_whitespace=True,
    coerce_numbers_to_str=True,
    use_attribute_docstrings=True,
):
    """Configuration model for the database connection."""

    uri: SecretStr
    """The database connection URI. Supports both SQL and MongoDB URIs."""
    database: str = ""
    """Database name (MongoDB only). Falls back to the URI database or `modmail`."""
    tls_allow_invalid_certificates: bool = False
    """Allow invalid TLS certificates (MongoDB only, not recommended)."""

    @property
    def backend_type(self) -> Literal["sql", "mongodb"]:
        """Return the backend type based on the connection URI.

        Returns:
            `"mongodb"` if the URI starts with `mongodb://` or `mongodb+srv://`,
            otherwise `"sql"`.
        """
        if self.uri.get_secret_value().startswith(_MONGO_PREFIXES):
            return "mongodb"
        return "sql"

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: SecretStr) -> SecretStr:
        """Validate and canonicalize the database connection URI.

        For MongoDB URIs, validates via `pymongo.uri_parser`. For SQL URIs,
        injects the required async driver if not specified.

        Args:
            v: The URI to validate.

        Returns:
            The validated (possibly canonicalized) URI.

        Raises:
            ValueError: If the URI is malformed or uses an unsupported dialect/driver.
        """
        uri = v.get_secret_value()
        if uri.startswith(_MONGO_PREFIXES):
            return cls._validate_mongodb_uri(uri)
        return cls._validate_sql_uri(uri)

    @classmethod
    def _validate_mongodb_uri(cls, uri: str) -> SecretStr:
        import pymongo.errors
        from pymongo import uri_parser

        try:
            parsed_uri = uri_parser.parse_uri(uri)
        except pymongo.errors.ConfigurationError as e:
            raise ValueError(f"Invalid MongoDB connection URI: {e}.") from e

        if parsed_uri["password"] and parsed_uri["password"][0] == "<" and parsed_uri["password"][-1] == ">":
            raise ValueError(
                "Invalid MongoDB connection URI: Did you forget to remove the <> around your password? "
                "If that's not a mistake, the password must be escaped according to RFC 3986."
            )
        return SecretStr(uri)

    @classmethod
    def _validate_sql_uri(cls, uri: str) -> SecretStr:
        scheme, sep, rest = uri.partition("://")

        if not sep:
            raise ValueError(
                f"Invalid SQL URI: no scheme found in {uri!r}. "
                "Expected format: 'dialect://...' or 'dialect+driver://...'."
            )

        dialect, _, existing_driver = scheme.lower().partition("+")

        if dialect not in _DIALECT_DRIVERS:
            raise ValueError(
                f"Unrecognized SQL dialect {dialect!r} in URI. "
                f"Supported dialects: {', '.join(sorted(_DIALECT_DRIVERS))}."
            )

        required_driver = _DIALECT_DRIVERS[dialect]
        if existing_driver and existing_driver != required_driver:
            raise ValueError(
                f"Unsupported driver {existing_driver!r} for dialect {dialect!r}. "
                f"Only {required_driver!r} is supported."
            )

        canonical_dialect = _DIALECT_ALIASES.get(dialect, dialect)
        new_scheme = f"{canonical_dialect}+{required_driver}"
        return SecretStr(f"{new_scheme}://{rest}")

    @field_validator("database")
    @classmethod
    def _resolve_database(cls, value: str, info: ValidationInfo) -> str:
        if value:
            return value
        uri = info.data["uri"].get_secret_value()
        if uri.startswith(_MONGO_PREFIXES):
            default = "modmail"
            from pymongo import uri_parser

            try:
                parsed = uri_parser.parse_uri(uri)
                return parsed.get("database") or default
            except Exception:
                return default
        return value
