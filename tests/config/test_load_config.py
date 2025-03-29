from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_mock import MockerFixture

from modmail.config.loader import load_config
from modmail.config.models import Config


@pytest.fixture
def config_file_path(tmp_path: Path, valid_config_dict: dict[str, Any]) -> Path:
    """Create a temporary config YAML file with valid content.

    Args:
        tmp_path: Pytest fixture that provides a temporary directory path.
        valid_config_dict: Fixture providing a valid configuration dictionary.

    Returns:
        Path to the created temporary YAML configuration file.
    """
    config_path = tmp_path / "valid_config.yaml"
    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(valid_config_dict, f)
    return config_path


def test_load_config_file_not_found() -> None:
    """Test that load_config returns None when file is not found."""
    result = load_config("invalid_config.yaml")
    assert result is None


def test_load_config_permission_error(mocker: MockerFixture, patch_open: Any) -> None:
    """Test that load_config returns None when a permission error occurs."""

    original_func = Path.open

    def open_func(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == "invalid-config.yaml":
            raise PermissionError("Permission denied")
        return original_func(self, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]

    mock_open = mocker.patch("pathlib.Path.open", side_effect=open_func, autospec=patch_open)

    result = load_config("invalid-config.yaml")

    assert result is None
    mock_open.assert_called_once()


def test_load_config_os_error(mocker: MockerFixture, patch_open: Any) -> None:
    """Test that load_config returns None when an OS error occurs."""

    original_func = Path.open

    def open_func(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == "invalid-config.yaml":
            raise OSError("Some OS error")
        return original_func(self, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]

    mock_open = mocker.patch("pathlib.Path.open", side_effect=open_func, autospec=patch_open)

    result = load_config("invalid-config.yaml")

    assert result is None
    mock_open.assert_called_once()


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    """Test that load_config returns None when given invalid YAML content."""
    # Create an invalid YAML file
    config_path = tmp_path / "invalid_config.yaml"
    with config_path.open("w", encoding="utf-8") as f:
        f.write("This is not valid YAML")

    result = load_config(str(config_path))

    assert result is None


def test_load_config_validation_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Test that load_config returns None when configuration fails validation."""
    # Create a config with valid YAML but invalid values
    config_path = tmp_path / "invalid_config.yaml"
    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(
            {"version": "invalid_version", "bot": {"token": "invalid_token"}, "database_type": "unknown_db_type"},
            f,
        )

    result = load_config(str(config_path))

    assert result is None
    assert "Invalid config file at" in caplog.text
    assert any(record.levelname == "CRITICAL" for record in caplog.records)


def test_load_config_success(config_file_path: Path, valid_config_dict: dict[str, Any]) -> None:
    """Test that load_config correctly processes a valid configuration file."""
    result = load_config(str(config_file_path))

    assert isinstance(result, Config)
    assert result.version == valid_config_dict["version"]
    assert result.database_type == valid_config_dict["database_type"]
    assert result.bot.token.get_secret_value() == valid_config_dict["bot"]["token"]
    assert result.bot.staff_server_id == valid_config_dict["bot"]["staff_server_id"]
    assert result.sql_config is not None
    assert result.sql_config.uri.get_secret_value() == valid_config_dict["sql_config"]["uri"]
    assert result.mongodb_config is None
