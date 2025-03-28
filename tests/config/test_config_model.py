from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from modmail.config.models import Config, LoggingConfig, PermissionConfig


class TestConfig:
    @pytest.fixture
    def minimal_valid_config_data(self) -> dict[str, Any]:
        """Return minimal valid configuration data."""
        return {
            "version": "1.0",
            "bot": {"token": "MTIzNDU2Nzg5MDEyMzQ1.xyz.abc", "staff_server_id": 123456789012345},
            "database_type": "mongodb",
            "mongodb_config": {"uri": "mongodb://localhost:27017/modmail"},
        }

    def test_version_validation(self, minimal_valid_config_data: dict[str, Any]) -> None:
        """Test that version validation works correctly."""
        # Valid version
        config_data = minimal_valid_config_data.copy()
        config = Config(**config_data)
        assert config.version == "1.0"

        # Invalid version
        config_data["version"] = "0.0abc"
        with pytest.raises(ValidationError, match="Invalid config version"):
            Config(**config_data)

        config_data["version"] = "0.0"
        with pytest.raises(ValidationError, match="Invalid config version"):
            Config(**config_data)

    def test_locale_validation(self, minimal_valid_config_data: dict[str, Any]) -> None:
        """Test that locale validation works correctly."""
        # Default locale in allowed locales should work
        # Valid custom setup
        config_data = minimal_valid_config_data.copy()
        config_data["default_locale"] = "de"
        config_data["allowed_locales"] = ["de"]
        config = Config(**config_data)
        assert config.default_locale == "de"
        assert config.allowed_locales == {"de"}

        config_data = minimal_valid_config_data.copy()
        # Invalid: default locale not in allowed locales
        config_data["default_locale"] = "en"
        config_data["allowed_locales"] = ["de"]
        with pytest.raises(ValidationError, match="The default locale must be in allowed_locales"):
            Config(**config_data)

        config_data = minimal_valid_config_data.copy()
        # Invalid: empty allowed locales
        config_data["allowed_locales"] = []
        with pytest.raises(ValidationError, match="at least 1 item"):
            Config(**config_data)

    def test_database_config_selection(self, minimal_valid_config_data: dict[str, Any]) -> None:
        """Test that the correct database config is selected based on database_type."""
        # Test MongoDB config
        config_data = minimal_valid_config_data.copy()
        config_data["database_type"] = "mongodb"
        config_data["mongodb_config"] = {"uri": "mongodb://localhost:27017/modmail"}

        config = Config(**config_data)
        assert config.database_type == "mongodb"
        assert config.mongodb_config is not None
        assert config.sql_config is None
        assert config.mongodb_config.uri.get_secret_value() == "mongodb://localhost:27017/modmail"

        # Test SQL config
        config_data = minimal_valid_config_data.copy()
        config_data["database_type"] = "sql"
        config_data["sql_config"] = {"uri": "sqlite:///modmail.db"}

        config = Config(**config_data)
        assert config.database_type == "sql"
        assert config.sql_config is not None
        assert config.mongodb_config is None
        assert config.sql_config.uri.get_secret_value() == "sqlite:///modmail.db"

    def test_bad_database_config(self, minimal_valid_config_data: dict[str, Any]) -> None:
        """Test that an invalid database config raises an error."""
        # Missing database type
        config_data = minimal_valid_config_data.copy()
        config_data["database_type"] = "sql"
        config_data["sql_config"] = None  # No SQL config provided
        with pytest.raises(ValidationError, match="sql_config.uri"):
            Config(**config_data)

        config_data = minimal_valid_config_data.copy()
        config_data["database_type"] = "mongodb"
        config_data["mongodb_config"] = None  # No MongoDB config provided
        with pytest.raises(ValidationError, match="mongodb_config.uri"):
            Config(**config_data)

    def test_default_configs(self, minimal_valid_config_data: dict[str, Any]) -> None:
        """Test that default configs are created when not specified."""
        config = Config(**minimal_valid_config_data)

        # Check that permission has default values
        assert isinstance(config.permission, PermissionConfig)
        assert isinstance(config.permission.discord_admin_bypass, bool)

        # Check that logging has default values
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.logging.enabled, bool)

    def test_default_configs_with_none(self, minimal_valid_config_data: dict[str, Any]) -> None:
        """Test that default configs are created when not specified."""
        minimal_valid_config_data["permission"] = None
        minimal_valid_config_data["logging"] = None
        config = Config(**minimal_valid_config_data)

        # Check that permission has default values
        assert isinstance(config.permission, PermissionConfig)
        assert isinstance(config.permission.discord_admin_bypass, bool)

        # Check that logging has default values
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.logging.enabled, bool)
