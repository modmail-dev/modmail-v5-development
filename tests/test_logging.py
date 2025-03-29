from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pytest_mock import MockerFixture

# noinspection PyProtectedMember
from modmail.logging import FileFormatter, setup_logging


class TestFileFormatter:
    def test_format_regular_text(self) -> None:
        """Test that FileFormatter correctly handles regular text without markup."""
        formatter = FileFormatter("%(message)s")
        record = logging.LogRecord("test", logging.INFO, "path", 10, "Test message", None, None)

        result = formatter.format(record)
        assert result == "Test message"

    def test_format_markup_text(self) -> None:
        """Test that FileFormatter properly strips rich markup tags from log messages."""
        formatter = FileFormatter("%(message)s")
        record = logging.LogRecord("test", logging.INFO, "path", 10, "[bold]Test[/bold] message", None, None)
        record.markup = True

        result = formatter.format(record)
        assert result == "Test message"  # Markup should be removed


class TestSetupLogging:
    def test_setup_logging(self, mocker: MockerFixture) -> None:
        """Test that the setup_logging runs with no issues."""

        # No loggers should actually be created or changed
        mock_get_logger = mocker.patch("logging.getLogger", return_value=mocker.MagicMock(spec=logging.Logger))
        mocker.patch("logging.handlers.RotatingFileHandler")
        mocker.patch("modmail.logging._LOGGING_IS_SETUP", False)
        setup_logging()
        mock_get_logger.assert_called()

    def test_rotating_file_handler(self, tmp_path: Path) -> None:
        """Test that RotatingFileHandler correctly creates and rotates log files."""
        # Create a temporary directory for log files
        log_path = tmp_path / "test_log.log"

        # Set up configuration with small size limits for testing rotation
        max_size = 2000  # bytes
        backup_count = 2

        test_logger = logging.getLogger("modmail_test.test_logger")
        test_logger.setLevel(logging.CRITICAL)
        logfile_handler = RotatingFileHandler(
            log_path,
            mode="a",
            maxBytes=max_size,
            backupCount=backup_count,
        )
        logfile_handler.setFormatter(FileFormatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s"))
        logfile_handler.setLevel(logging.CRITICAL)
        test_logger.addHandler(logfile_handler)

        # Generate enough logs to trigger rotation
        # We'll create a message slightly smaller than max_size
        message = "X" * (max_size // 10)

        # Log enough messages to create main file + backup files
        for i in range(100):
            test_logger.critical("%s-%d", message, i)

        # Check that the log files exist and respect size/count limits
        log_files = list(tmp_path.glob("test_log.log*"))

        # Should have the main file + backup_count backup files at most
        assert 1 <= len(log_files) <= backup_count + 1

        # Check that each file exists and is at or below the max size
        assert log_path.exists()
        for log_file in log_files:
            assert log_file.stat().st_size <= max_size

        # Clean up the test logger
        logfile_handler.close()
        test_logger.removeHandler(logfile_handler)
