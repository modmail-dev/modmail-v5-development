from __future__ import annotations

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture

import modmail


class TestInit:
    def test_version_exists_and_valid(self) -> None:
        """Test that the version string is defined and follows semver format."""
        assert hasattr(modmail, "__version__")
        assert isinstance(modmail.__version__, str)
        # This shouldn't raise an exception:
        Version(modmail.__version__)

    def test_init_loads_config(self, mocker: MockerFixture) -> None:
        """Test that init() loads the configuration properly."""
        mock_config = mocker.MagicMock()
        mock_load_config = mocker.patch("modmail.load_config", return_value=mock_config)

        modmail.init("test_config.yaml")

        # Verify config was loaded with correct path
        mock_load_config.assert_called_once_with("test_config.yaml")
        # Verify global CONFIG was set
        assert modmail.CONFIG is mock_config

    def test_init_fails_gracefully(self, mocker: MockerFixture) -> None:
        """Test that init() handles config loading failures."""
        mocker.patch("modmail.load_config", return_value=None)

        with pytest.raises(SystemExit):
            modmail.init("invalid_config.yaml")

    def test_init_sets_up_logging(self, mocker: MockerFixture) -> None:
        """Test that init() sets up logging when configured to do so."""
        mock_config = mocker.MagicMock()
        mock_config.logging.enabled = True
        mocker.patch("modmail.load_config", return_value=mock_config)

        mock_setup_logging = mocker.patch("modmail.logging.setup_logging")

        modmail.init("valid_config.yaml")

        # Verify logging setup was called
        mock_setup_logging.assert_called_once()

    def test_init_skips_logging_setup_when_disabled(self, mocker: MockerFixture) -> None:
        """Test that init() doesn't set up logging when it's disabled."""
        mock_config = mocker.MagicMock()
        mock_config.logging.enabled = False
        mocker.patch("modmail.load_config", return_value=mock_config)

        mock_setup_logging = mocker.patch("modmail.logging.setup_logging")

        modmail.init("valid_config.yaml")

        # Verify logging setup was not called
        mock_setup_logging.assert_not_called()


class TestRunBot:
    def test_run_bot_creates_and_runs_bot(self, mocker: MockerFixture) -> None:
        """Test that run_bot() instantiates and runs the bot."""
        mock_bot = mocker.MagicMock()
        mock_bot_class = mocker.patch("modmail.core.Bot", return_value=mock_bot)
        mock_load_config = mocker.patch.object(modmail, "load_config", return_value=modmail.CONFIG)

        del modmail.CONFIG
        modmail.run_bot()

        # Check that configs are loaded
        # noinspection PyUnreachableCode
        mock_load_config.assert_called_once_with("config.yaml")

        # Check bot was instantiated and run
        mock_bot_class.assert_called_once()
        mock_bot.run_bot.assert_called_once()
