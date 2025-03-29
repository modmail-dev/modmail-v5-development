from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from modmail.config.models import Config, LoggingConfig, PermissionConfig


class TestConfig:
    def test_version_validation(self, valid_config_dict: dict[str, Any]) -> None:
        """Test that version validation works correctly."""
        # Valid version
        config = Config(**valid_config_dict)
        assert config.version == "1.0"

        # Invalid version
        valid_config_dict["version"] = "0.0abc"
        with pytest.raises(ValidationError, match="Invalid config version"):
            Config(**valid_config_dict)

        valid_config_dict["version"] = "0.0"
        with pytest.raises(ValidationError, match="Invalid config version"):
            Config(**valid_config_dict)

    def test_locale_validation(self, valid_config_dict: dict[str, Any]) -> None:
        """Test that locale validation works correctly."""
        # Default locale in allowed locales should work
        # Valid custom setup
        valid_config_dict["default_locale"] = "de"
        valid_config_dict["allowed_locales"] = ["de"]
        config = Config(**valid_config_dict)
        assert config.default_locale == "de"
        assert config.allowed_locales == {"de"}

        # Invalid: default locale not in allowed locales
        valid_config_dict["default_locale"] = "en"
        valid_config_dict["allowed_locales"] = ["de"]
        with pytest.raises(ValidationError, match="The default locale must be in allowed_locales"):
            Config(**valid_config_dict)

        # Invalid: empty allowed locales
        valid_config_dict["allowed_locales"] = []
        with pytest.raises(ValidationError, match="at least 1 item"):
            Config(**valid_config_dict)

    def test_database_config_selection(self, valid_config_dict: dict[str, Any]) -> None:
        """Test that the correct database config is selected based on database_type."""
        # Test MongoDB config
        valid_config_dict["database_type"] = "mongodb"
        valid_config_dict["mongodb_config"] = {"uri": "mongodb://localhost:27017/modmail"}

        config = Config(**valid_config_dict)
        assert config.database_type == "mongodb"
        assert config.mongodb_config is not None
        assert config.sql_config is None
        assert config.mongodb_config.uri.get_secret_value() == "mongodb://localhost:27017/modmail"

        # Test SQL config
        valid_config_dict["database_type"] = "sql"
        valid_config_dict["sql_config"] = {"uri": "sqlite:///modmail-test.db"}

        config = Config(**valid_config_dict)
        assert config.database_type == "sql"
        assert config.sql_config is not None
        assert config.mongodb_config is None
        assert config.sql_config.uri.get_secret_value() == "sqlite:///modmail-test.db"

    def test_bad_database_config(self, valid_config_dict: dict[str, Any]) -> None:
        """Test that an invalid database config raises an error."""
        # Missing database type
        valid_config_dict["database_type"] = "sql"
        valid_config_dict["sql_config"] = None  # No SQL config provided
        with pytest.raises(ValidationError, match=r"sql_config.uri"):
            Config(**valid_config_dict)

        valid_config_dict["database_type"] = "mongodb"
        valid_config_dict["mongodb_config"] = None  # No MongoDB config provided
        with pytest.raises(ValidationError, match=r"mongodb_config.uri"):
            Config(**valid_config_dict)

    def test_default_configs(self, valid_config_dict: dict[str, Any]) -> None:
        """Test that default configs are created when not specified."""
        config = Config(**valid_config_dict)

        # Check that permission has default values
        assert isinstance(config.permission, PermissionConfig)
        assert isinstance(config.permission.discord_admin_bypass, bool)

        # Check that logging has default values
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.logging.enabled, bool)

    def test_default_configs_with_none(self, valid_config_dict: dict[str, Any]) -> None:
        """Test that default configs are created when not specified."""
        valid_config_dict["permission"] = None
        valid_config_dict["logging"] = None
        config = Config(**valid_config_dict)

        # Check that permission has default values
        assert isinstance(config.permission, PermissionConfig)
        assert isinstance(config.permission.discord_admin_bypass, bool)

        # Check that logging has default values
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.logging.enabled, bool)
