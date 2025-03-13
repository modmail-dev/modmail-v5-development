"""
modmail.config.models.sql_database_model
========================================
This module defines the configuration model for the SQL database used by the Modmail bot.
It includes validation logic to ensure the SQL connection URI is correctly specified.
"""

from __future__ import annotations

from pydantic import BaseModel, SecretStr, field_validator

__all__ = [
    "SQLDatabaseConfig",
]


# noinspection PyNestedDecorators
class SQLDatabaseConfig(BaseModel):
    """
    Configuration model for the SQL database.

    Attributes:
        uri (str): The SQL connection URI.
    """

    uri: SecretStr  # the SQL connection URI
    # TODO: support individual uri parts (username, password, host, port, database) instead of a single URI

    @field_validator("uri")
    @classmethod
    def check_uri_is_valid(cls, v: str) -> str:
        """
        Validates that the SQL connection URI is valid.
        """
        # TODO: Add validation logic for SQL connection URI
        return v
