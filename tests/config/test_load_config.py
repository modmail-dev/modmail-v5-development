from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_mock import MockerFixture

from modmail.config.loader import load_config
from modmail.config.models import Config


@pytest.fixture
def valid_config_dict() -> dict[str, Any]:
    """Return a valid configuration dictionary for testing."""
    return {
        "version": "1.0",
        "bot": {
            "token": "MTIzNDU2Nzg5MDEyMzQ1Njc4.abcdef.ghijklmnopqrstuvwxyz1234567890",
            "staff_server_id": 123456789012345,
        },
        "database_type": "sql",
        "sql_config": {"uri": "sqlite:///modmail.db"},
    }


@pytest.fixture
def config_file_path(tmp_path: Path, valid_config_dict: dict[str, Any]) -> Path:
    """Create a temporary config file with valid content."""
    config_path = tmp_path / "config.yaml"
    with config_path.open("w") as f:
        yaml.dump(valid_config_dict, f)
    return config_path


def test_load_config_file_not_found() -> None:
    """Test that load_config returns None when file is not found."""
    result = load_config("nonexistent_file.yaml")
    assert result is None


def test_load_config_permission_error(mocker: MockerFixture) -> None:
    """Test that load_config returns None when a permission error occurs."""
    mock_open = mocker.patch("builtins.open", side_effect=PermissionError("Permission denied"))

    result = load_config("config.yaml")

    assert result is None
    mock_open.assert_called_once_with("config.yaml", "r")


def test_load_config_os_error(mocker: MockerFixture) -> None:
    """Test that load_config returns None when an OS error occurs."""
    mock_open = mocker.patch("builtins.open", side_effect=OSError("Some OS error"))

    result = load_config("config.yaml")

    assert result is None
    mock_open.assert_called_once_with("config.yaml", "r")


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    """Test that load_config returns None when given invalid YAML content."""
    # Create an invalid YAML file
    config_path = tmp_path / "invalid_config.yaml"
    with config_path.open("w") as f:
        f.write("This is not valid YAML")

    result = load_config(str(config_path))

    assert result is None


def test_load_config_validation_error(mocker: MockerFixture, tmp_path: Path) -> None:
    """Test that load_config returns None when configuration fails validation."""
    mock_logger = mocker.patch("modmail.config.loader.logger")

    # Create a config with valid YAML but invalid values
    config_path = tmp_path / "invalid_values.yaml"
    with config_path.open("w") as f:
        yaml.dump(
            {"version": "invalid_version", "bot": {"token": "invalid_token"}, "database_type": "unknown_db_type"},
            f,
        )

    result = load_config(str(config_path))

    assert result is None
    mock_logger.critical.assert_called_once()
    assert "Invalid config file at" in mock_logger.critical.call_args[0][0]


def test_load_config_success(config_file_path: Path) -> None:
    """Test that load_config correctly processes a valid configuration file."""
    result = load_config(str(config_file_path))

    assert isinstance(result, Config)
    assert result.version == "1.0"
    assert result.database_type == "sql"
    assert result.bot.token.get_secret_value() == "MTIzNDU2Nzg5MDEyMzQ1Njc4.abcdef.ghijklmnopqrstuvwxyz1234567890"
    assert result.bot.staff_server_id == 123456789012345
    assert result.sql_config is not None
    assert result.sql_config.uri.get_secret_value() == "sqlite:///modmail.db"
    assert result.mongodb_config is None
