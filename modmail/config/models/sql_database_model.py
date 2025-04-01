"""SQL database configuration model for Modmail.

This module defines the configuration model for the SQL database used by the Modmail bot.
It includes validation logic to ensure the SQL connection URI is correctly specified.
"""

from __future__ import annotations

from pydantic import BaseModel, SecretStr, field_validator

__all__ = ["SQLDatabaseConfig"]


class SQLDatabaseConfig(BaseModel):
    """Configuration model for the SQL database.

    Attributes:
        uri: The SQL connection URI.
    """

    uri: SecretStr  # the SQL connection URI
    # TODO: support individual uri parts (username, password, host, port, database) instead of a single URI

    @field_validator("uri")
    @classmethod
    def check_uri_is_valid(cls, v: SecretStr) -> SecretStr:
        """Validates that the SQL connection URI is valid.

        Args:
            v: The SQL connection URI to validate.

        Returns:
            The validated SQL connection URI.

        Note:
            Currently a placeholder for future validation implementation.
        """
        # TODO: Add validation logic for SQL connection URI
        return v
