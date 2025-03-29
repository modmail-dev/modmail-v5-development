from __future__ import annotations

from typing import cast

import pytest
from pydantic import SecretStr, ValidationError

from modmail.config.models.mongodb_database_model import MongoDBDatabaseConfig
from modmail.config.models.sql_database_model import SQLDatabaseConfig


class TestMongoDBDatabaseConfig:
    def test_mongodb_uri_validation_success(self) -> None:
        """Test that a valid MongoDB URI is accepted."""
        # Should not raise an exception
        config = MongoDBDatabaseConfig(uri=cast(SecretStr, "mongodb://user:password123@localhost:27017/modmail"))
        assert isinstance(config.uri, SecretStr)
        assert config.uri.get_secret_value() == "mongodb://user:password123@localhost:27017/modmail"

    def test_mongodb_uri_validation_failure(self) -> None:
        """Test that invalid MongoDB URIs are rejected."""
        with pytest.raises(ValidationError):
            MongoDBDatabaseConfig(uri=cast(SecretStr, "invalid-mongodb-uri"))

    def test_password_placeholder_validation(self) -> None:
        """Test that passwords with <> placeholders are rejected."""
        with pytest.raises(ValidationError, match="Did you forget to remove the <>"):
            MongoDBDatabaseConfig(uri=cast(SecretStr, "mongodb://user:<password>@localhost:27017/modmail"))

    def test_database_name_from_uri(self) -> None:
        """Test that database name is extracted from URI if not provided."""
        # No database name provided, should use from URI
        config = MongoDBDatabaseConfig(uri=cast(SecretStr, "mongodb://user:password123@localhost:27017/custom_db"))
        assert config.database == "custom_db"

        # Explicitly set database name should override URI
        config = MongoDBDatabaseConfig(
            uri=cast(SecretStr, "mongodb://user:password123@localhost:27017/custom_db"), database="explicit_db"
        )
        assert config.database == "explicit_db"

        config = MongoDBDatabaseConfig(uri=cast(SecretStr, "mongodb://user:password123@localhost:27017"))
        assert config.database == "modmail"


class TestSQLDatabaseConfig:
    def test_sql_uri_basic(self) -> None:
        """Test basic SQL URI configuration."""
        config = SQLDatabaseConfig(uri=cast(SecretStr, "sqlite:///modmail-test.db"))
        assert isinstance(config.uri, SecretStr)
        assert config.uri.get_secret_value() == "sqlite:///modmail-test.db"

        # PostgreSQL format
        config = SQLDatabaseConfig(uri=cast(SecretStr, "postgresql://user:password@localhost:5432/modmail"))
        assert config.uri.get_secret_value() == "postgresql://user:password@localhost:5432/modmail"

        # MySQL format
        config = SQLDatabaseConfig(uri=cast(SecretStr, "mysql+pymysql://user:password@localhost:3306/modmail"))
        assert config.uri.get_secret_value() == "mysql+pymysql://user:password@localhost:3306/modmail"
