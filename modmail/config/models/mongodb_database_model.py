"""MongoDB database configuration model for Modmail.

This module defines the configuration model for the MongoDB database used by the Modmail bot.
It includes validation logic to ensure the MongoDB connection URI and database name are
correctly specified.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator

__all__ = [
    "MongoDBDatabaseConfig",
]

logger = logging.getLogger(__name__)


class MongoDBDatabaseConfig(BaseModel):
    """Configuration model for the MongoDB database.

    Attributes:
        uri: The MongoDB connection URI, stored securely.
        database: The name of the database to use.
        tls_allow_invalid_certificates: Whether to allow invalid TLS certificates.
    """

    uri: SecretStr  # the MongoDB connection URI
    database: str = Field(default="", validate_default=True)  # default is 'modmail'
    tls_allow_invalid_certificates: bool = False

    @field_validator("uri")
    @classmethod
    def check_uri_is_valid(cls, v: SecretStr) -> SecretStr:
        """Validates that the MongoDB connection URI is valid.

        Args:
            v: The MongoDB connection URI to validate.

        Returns:
            The validated MongoDB connection URI.

        Raises:
            ValueError: If the URI is invalid or contains formatting errors.
        """
        # Local import to avoid dependency issues when database type is not mongodb
        import pymongo.errors
        from pymongo import uri_parser

        uri = v.get_secret_value()
        try:
            parsed_uri = uri_parser.parse_uri(uri)
        except pymongo.errors.ConfigurationError as e:
            # TODO: where is this error raised? (not here I think)
            # if "The DNS query name does not exist" in str(e):
            #     raise ValueError(
            #         "Invalid MongoDB connection URI: The DNS query name does not exist. "
            #         "Did you copy your MongoDB connection URI correctly?"
            #     )
            raise ValueError(f"Invalid MongoDB connection URI: {e}.") from e

        if parsed_uri["password"] and parsed_uri["password"][0] == "<" and parsed_uri["password"][-1] == ">":
            raise ValueError(
                "Invalid MongoDB connection URI: Did you forget to remove the <> around your password? "
                "If that's not a mistake, the password must be escaped according to RFC 3986."
            )
        return v

    @field_validator("database")
    @classmethod
    def use_database_name_or_from_uri(cls, v: str, info: ValidationInfo) -> str:
        """Uses the provided database name or extracts it from the URI.

        If no database name is provided, attempts to parse it from the MongoDB
        connection URI. Falls back to "modmail" if neither source provides a name.

        Args:
            v: The database name value to check.
            info: Validation context containing other field values.

        Returns:
            The database name to use.

        Raises:
            ValueError: If URI field is missing from the database config.
        """
        # Local import to avoid dependency issues when database type is not mongodb
        from pymongo import uri_parser

        if v:
            return v

        try:
            # Check if the URI contains a database name.
            parsed_uri = uri_parser.parse_uri(info.data["uri"].get_secret_value())
        except KeyError as e:
            raise ValueError("URI not found in the database config.") from e

        if parsed_uri["database"]:
            return parsed_uri["database"]
        return "modmail"
