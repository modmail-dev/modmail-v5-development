from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pytest
from pytest_mock import MockerFixture

from modmail.config.models.logging_model import LoggingConfig


def test_logging_config_defaults() -> None:
    """Test some default values of LoggingConfig."""
    config = LoggingConfig()

    assert isinstance(config.enabled, bool)
    assert isinstance(config.root_level, int)
    assert isinstance(config.logfile_max_size, int | float)


def test_logging_config_custom_values(mocker: MockerFixture, tmp_path: Path, patch_open: Any) -> None:
    """Test LoggingConfig with custom values."""

    original_func = Path.open

    def open_func(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == "custom.log":
            return original_func(Path(tmp_path / self.name), *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]
        return original_func(self, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]

    mock_open = mocker.patch("pathlib.Path.open", side_effect=open_func, autospec=patch_open)

    config = LoggingConfig(
        enabled=False,
        root_level=logging.WARNING,
        stdout_format="%(levelname)s: %(message)s",
        logfile="custom.log",
        logfile_max_size=1024 * 1024,
        discord_level=logging.ERROR,
        discord_gateway_level=logging.ERROR,
    )

    assert config.enabled is False
    assert config.root_level == logging.WARNING
    assert config.stdout_format == "%(levelname)s: %(message)s"
    assert config.logfile == "custom.log"
    assert config.logfile_max_size == 1024 * 1024
    assert config.discord_level == logging.ERROR
    assert config.discord_gateway_level == logging.ERROR
    assert mock_open.call_count == 1


def test_logging_config_level_normalization() -> None:
    """Test normalization of logging level text to integers."""
    # Test with string level names

    config = LoggingConfig(
        root_level=cast(int, "DEBUG"),
        console_level=cast(int, "INFO"),
        logfile_level=cast(int, "WARNING"),
        discord_level=cast(int, "ERROR"),
        discord_state_level=cast(int, "CRITICAL"),
        discord_http_level=cast(int, "FATAL"),
        discord_gateway_level=cast(int, "NOTSET"),
    )

    assert config.root_level == logging.DEBUG
    assert config.console_level == logging.INFO
    assert config.logfile_level == logging.WARNING
    assert config.discord_level == logging.ERROR
    assert config.discord_state_level == logging.CRITICAL
    assert config.discord_http_level == logging.FATAL
    assert config.discord_gateway_level == logging.NOTSET


def test_logging_config_invalid_level() -> None:
    """Test handling of invalid logging levels."""
    with pytest.raises(ValueError, match="Invalid logging level"):
        LoggingConfig(root_level=cast(int, "INVALID_LEVEL"))


def test_logging_config_invalid_format_specifier() -> None:
    """Test handling of invalid format specifiers."""
    with pytest.raises(ValueError, match="Invalid formatting specifiers"):
        LoggingConfig(stdout_format="%INVALID%")


def test_logging_config_logfile_directory_error(tmp_path: Path) -> None:
    """Test validation when logfile path is a directory."""
    with pytest.raises(ValueError, match="Logfile path is referencing a directory"):
        LoggingConfig(logfile=str(tmp_path))


def test_logging_config_logfile_permission_error(mocker: MockerFixture, patch_open: Any) -> None:
    """Test validation when logfile cannot be opened due to permissions."""

    original_func = Path.open

    def open_func(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == "modmail-restricted-test.log":
            raise PermissionError("Some OS error")
        return original_func(self, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]

    mock_open = mocker.patch("pathlib.Path.open", side_effect=open_func, autospec=patch_open)

    with pytest.raises(ValueError, match="No permissions to open the file"):
        LoggingConfig(logfile="modmail-restricted-test.log")

    mock_open.assert_called_once()


def test_logging_config_logfile_os_error(mocker: MockerFixture, patch_open: Any) -> None:
    """Test validation when logfile encounters an OS error."""

    original_func = Path.open

    def open_func(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == "modmail-error-test.log":
            raise OSError("Some OS error")
        return original_func(self, *args, **kwargs)  # pyright: ignore [reportUnknownVariableType]

    mock_open = mocker.patch("pathlib.Path.open", side_effect=open_func, autospec=patch_open)

    with pytest.raises(ValueError, match="Logfile cannot be written to"):
        LoggingConfig(logfile="modmail-error-test.log")

    mock_open.assert_called_once()


def test_logging_config_none_logfile() -> None:
    """Test behavior when logfile is None."""
    config = LoggingConfig(logfile=None)

    assert config.logfile is None
    assert config.is_logfile_enabled() is False


def test_logging_is_logfile_enabled() -> None:
    """Test is_logfile_enabled method."""
    # When logfile is set
    config1 = LoggingConfig(logfile="modmail.log")
    assert config1.is_logfile_enabled() is True

    # When logfile is None
    config2 = LoggingConfig(logfile=None)
    assert config2.is_logfile_enabled() is False
