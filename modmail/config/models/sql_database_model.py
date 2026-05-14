"""SQL database configuration model for Modmail.

This module defines the configuration model for the SQL database used by the Modmail bot.
It includes validation logic to ensure the SQL connection URI is correctly specified.
"""

from __future__ import annotations

from pydantic import BaseModel, SecretStr, field_validator

__all__ = ["SQLDatabaseConfig"]

# Maps dialect names to their required async driver.  Users may omit the driver
# suffix (e.g. "postgresql://...") and Modmail injects it automatically.
# "postgres" is a common alias for "postgresql" and is normalized on load.
_DIALECT_DRIVERS: dict[str, str] = {
    "sqlite": "aiosqlite",
    "postgresql": "asyncpg",
    "postgres": "asyncpg",
    "mysql": "asyncmy",
    "mariadb": "asyncmy",
}

# Dialects whose bare name should be normalized to a canonical form understood
# by SQLAlchemy (e.g. "postgres" → "postgresql").
_DIALECT_ALIASES: dict[str, str] = {
    "postgres": "postgresql",
}


class SQLDatabaseConfig(BaseModel):
    """Configuration model for the SQL database.

    Attributes:
        uri: The SQL connection URI.  The async driver suffix (e.g.
            ``+asyncpg``) is injected automatically if omitted, so
            ``postgresql://...`` and ``postgresql+asyncpg://...`` are
            both accepted.  The ``postgres`` dialect alias is also
            normalized to ``postgresql``.
    """

    uri: SecretStr  # the SQL connection URI
    # TODO: support individual uri parts (username, password, host, port, database)
    # instead of a single URI

    @field_validator("uri")
    @classmethod
    def inject_async_driver(cls, v: SecretStr) -> SecretStr:
        """Parse the URI, validate the dialect, and inject the async driver.

        Splits on the first ``://`` to extract the scheme, manipulates it
        directly, then reassembles.  Dialect aliases such as ``postgres`` are
        normalized to their canonical SQLAlchemy name.

        Args:
            v: The raw SQL connection URI from config.

        Returns:
            The URI with a canonical dialect name and async driver suffix.

        Raises:
            ValueError: If the URI has no scheme, or the dialect is not
                recognized.
        """
        raw = v.get_secret_value()
        scheme, sep, rest = raw.partition("://")

        if not sep:
            raise ValueError(
                f"Invalid SQL URI: no scheme found in {raw!r}. "
                "Expected format: 'dialect://...' or 'dialect+driver://...'."
            )

        # scheme may be "dialect" or "dialect+driver".
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
        driver = existing_driver or required_driver
        new_scheme = f"{canonical_dialect}+{driver}"

        if new_scheme == scheme:
            return v

        return SecretStr(f"{new_scheme}://{rest}")
