from __future__ import annotations

import logging

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
        """Test that the logging system initializes correctly with appropriate handlers."""
        mock_get_logger = mocker.patch("logging.getLogger")
        mock_get_logger.side_effect = lambda name="modmail": mocker.MagicMock()
        mocker.patch("logging.handlers.RotatingFileHandler")

        setup_logging()
