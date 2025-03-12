"""
modmail.config.models.mongodb_database_model
============================================
This module defines the configuration model for the MongoDB database used by the Modmail bot.
It includes validation logic to ensure the MongoDB connection URI and database name are correctly specified.
"""

from __future__ import annotations

import logging

import pymongo.errors
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pymongo import uri_parser

__all__ = [
    "MongoDBDatabaseConfig",
]

logger = logging.getLogger(__name__)


# noinspection PyNestedDecorators
class MongoDBDatabaseConfig(BaseModel):
    """
    Configuration model for the MongoDB database.

    Attributes:
        uri (str): The MongoDB connection URI.
        database (str): The name of the database.
        tls_allow_invalid_certificates (bool): Whether to allow invalid TLS certificates.
    """

    uri: str  # the MongoDB connection URI
    database: str = Field("", validate_default=True)  # default is 'modmail'
    tls_allow_invalid_certificates: bool = False

    @field_validator("uri")
    @classmethod
    def check_uri_is_valid(cls, v: str) -> str:
        """
        Validates that the MongoDB connection URI is valid.
        """
        try:
            parsed_uri = uri_parser.parse_uri(v)
        except pymongo.errors.ConfigurationError as e:
            if "The DNS query name does not exist" in str(e):
                raise ValueError(
                    "Invalid MongoDB connection URI: The DNS query name does not exist. "
                    "Did you copy your MongoDB connection URI correctly?"
                )
            raise ValueError(f"Invalid MongoDB connection URI: {e}.")

        if parsed_uri["password"] and parsed_uri["password"][0] == "<" and parsed_uri["password"][-1] == ">":
            raise ValueError(
                "Invalid MongoDB connection URI: Did you forget to remove the <> around your password? "
                "If that's not a mistake, the password must be escaped according to RFC 3986."
            )
        return v

    @field_validator("database")
    @classmethod
    def use_database_name_or_from_uri(cls, v: str, info: ValidationInfo) -> str:
        """
        If the database name is not provided, it will be parsed from the MongoDB connection URI.
        """
        if v:
            return v

        try:
            # Check if the URI contains a database name.
            parsed_uri = uri_parser.parse_uri(info.data["uri"])
        except KeyError:
            raise ValueError("URI not found in the database config.")

        if parsed_uri["database"]:
            return parsed_uri["database"]
        return "modmail"
