"""SQL database configuration model for Modmail.

This module defines the configuration model for the SQL database used by the Modmail bot.
It includes validation logic to ensure the SQL connection URI is correctly specified.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, SecretStr, field_validator

__all__ = ["SQLDatabaseConfig"]

# Maps dialect names to their required async driver.  Users may omit the driver
# suffix (e.g. "postgresql://...") and Modmail injects it automatically.
# "postgres" is a common alias for "postgresql" and is normalised on load.
_DIALECT_DRIVERS: dict[str, str] = {
    "sqlite": "aiosqlite",
    "postgresql": "asyncpg",
    "postgres": "asyncpg",
    "mysql": "asyncmy",
    "mariadb": "asyncmy",
}

# Dialects whose bare name should be normalised to a canonical form understood
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
            normalised to ``postgresql``.
    """

    uri: SecretStr  # the SQL connection URI
    # TODO: support individual uri parts (username, password, host, port, database)
    # instead of a single URI

    @field_validator("uri")
    @classmethod
    def inject_async_driver(cls, v: SecretStr) -> SecretStr:
        """Parse the URI, validate the dialect, and inject the async driver.

        Uses :func:`urllib.parse.urlsplit` for standards-compliant parsing so
        that any valid URI structure (query strings, IPv6 hosts, encoded
        credentials, triple-slash SQLite paths, etc.) is handled correctly.
        The async driver suffix is appended to the scheme when absent, and
        dialect aliases such as ``postgres`` are normalised to their canonical
        SQLAlchemy name.

        Args:
            v: The raw SQL connection URI from config.

        Returns:
            The URI with a canonical dialect name and async driver suffix.

        Raises:
            ValueError: If the URI has no scheme, or the dialect is not
                recognised.
        """
        raw = v.get_secret_value()
        parsed = urlsplit(raw)

        if not parsed.scheme:
            raise ValueError(
                f"Invalid SQL URI: no scheme found in {raw!r}. "
                "Expected format: 'dialect://...' or 'dialect+driver://...'."
            )

        # The scheme may be "dialect" or "dialect+driver".
        # str.partition splits on the first "+" only, returning ("", "", "") tail
        # when "+" is absent — no length checks or magic numbers needed.
        dialect, _, existing_driver = parsed.scheme.lower().partition("+")

        if dialect not in _DIALECT_DRIVERS:
            raise ValueError(
                f"Unrecognised SQL dialect {dialect!r} in URI. "
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

        if new_scheme == parsed.scheme:
            return v

        return SecretStr(urlunsplit((new_scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment)))
