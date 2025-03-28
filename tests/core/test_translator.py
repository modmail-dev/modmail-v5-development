from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import discord
import pytest
from discord.app_commands import locale_str
from pytest_mock import MockerFixture

# noinspection PyProtectedMember
from modmail.core import Translator, _

# noinspection PyProtectedMember
from modmail.core.translator import HasLocaleStr


class MockFluentLocalization:
    """Mock implementation of FluentLocalization for testing.

    Simulates the behavior of the Fluent localization system with predefined
    translations and simple string formatting.

    Attributes:
        locales: List of locale codes in preferred order.
    """

    def __init__(self, locales: list[str]) -> None:
        """Initialize the mock localization with supported locales.

        Args:
            locales: List of locale codes in preferred order.
        """
        self.locales = locales
        self._translations = {
            "test.greeting": {
                "en": "Hello, {name}!",
                "es": "¡Hola, {name}!",
                "fr": "Bonjour, {name}!",
            },
            "test.farewell": {
                "en": "Goodbye!",
                "es": "¡Adiós!",
                # fr missing intentionally to test fallbacks
            },
        }

    def format_value(self, message_id: str, args: dict[str, Any] | None = None) -> str:
        """Format the message ID with the provided arguments.

        Applies localization using the predefined translations and formats
        placeholders based on the provided arguments.

        Args:
            message_id: The identifier for the message to be translated.
            args: Dictionary of arguments to format into the translated string.

        Returns:
            The formatted message in the appropriate locale, or the message_id
            if no translation is found.
        """
        args = args or {}
        locale = self.locales[0]

        if message_id not in self._translations:
            return message_id  # Return the message ID if not found

        if locale not in self._translations[message_id]:
            # Try fallback to the second locale if available
            if len(self.locales) > 1 and self.locales[1] in self._translations[message_id]:
                locale = self.locales[1]
            else:
                return message_id

        result = self._translations[message_id][locale]

        # Simple formatting for placeholders
        for key, value in args.items():
            if key != "_string":
                placeholder = f"{{{key}}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value))

        return result


class MockLocaleStr(HasLocaleStr):
    """Mock object that implements the HasLocaleStr protocol.

    Used for testing objects that can be converted to locale_str.
    """

    def __init__(self, message: str) -> None:
        """Initialize the mock object with a message.

        Args:
            message: The string message to be converted to locale_str.
        """
        self._message = message

    def __locale_str__(self) -> locale_str:
        """Convert this object to a locale_str.

        Returns:
            A locale_str representation of this object.
        """
        return locale_str(self._message, _string=self._message)


@pytest.fixture
def mock_fluent_setup(mocker: MockerFixture) -> None:
    """Set up mocks for FluentLocalization and CONFIG."""
    # Mock CONFIG object
    mock_config = mocker.MagicMock()
    mock_config.default_locale = "en"
    mock_config.allowed_locales = ["en", "es", "fr"]
    mocker.patch("modmail.core.translator.CONFIG", mock_config)

    # Mock FluentLocalization
    mock_l10n_en = MockFluentLocalization(["en"])
    mock_l10n_es = MockFluentLocalization(["es", "en"])
    mock_l10n_fr = MockFluentLocalization(["fr", "en"])

    # Mock all_l10n dictionary
    mock_all_l10n = {"en": mock_l10n_en, "es": mock_l10n_es, "fr": mock_l10n_fr}
    mocker.patch("modmail.core.translator.all_l10n", mock_all_l10n)


@pytest.mark.asyncio
async def test_translator_translate_basic(mock_fluent_setup: None) -> None:
    """Test basic translation functionality with different locales."""
    translator = Translator()

    # Create a locale_str with extras containing the Fluent message ID
    string = locale_str("Hello, World!", _string="test.greeting", name="World")

    # Test with different locales
    result_en = await translator.translate(string, discord.Locale.american_english)
    assert result_en == "Hello, World!"  # Default locale returns the original string

    result_es = await translator.translate(string, discord.Locale.spain_spanish)
    assert result_es == "¡Hola, World!"

    result_fr = await translator.translate(string, "fr")
    assert result_fr == "Bonjour, World!"

    # Test with string locale identifier
    result_es_str = await translator.translate(string, "es")
    assert result_es_str == "¡Hola, World!"


@pytest.mark.asyncio
async def test_translator_fallback(mock_fluent_setup: None) -> None:
    """Test fallback to default locale when translation is missing."""
    translator = Translator()

    # Use a message ID that doesn't have a French translation
    string = locale_str("Goodbye!", _string="test.farewell")

    # French should fall back to English
    result_fr = await translator.translate(string, "fr")
    assert result_fr == "Goodbye!"

    # Spanish has its own translation
    result_es = await translator.translate(string, "es")
    assert result_es == "¡Adiós!"


@pytest.mark.asyncio
async def test_translator_region_specific_locale(mock_fluent_setup: None) -> None:
    """Test handling of region-specific locales like en-US."""
    translator = Translator()

    string = locale_str("Hello, User!", _string="test.greeting", name="User")

    # fr-FR should use the 'fr' locale
    result = await translator.translate(string, "fr-FR")
    assert result == "Bonjour, User!"

    # Made-up locale should default to CONFIG.default_locale
    result = await translator.translate(string, "unknown-LOCALE")
    assert result == "Hello, User!"  # Original string returned (default locale)


@pytest.mark.asyncio
async def test_translator_with_nested_locale_str(mock_fluent_setup: None, mocker: MockerFixture) -> None:
    """Test translation with nested locale_str objects."""
    translator = Translator()

    # Mock the translate method to track calls and return expected values
    original_translate = translator.translate
    mock_translate = mocker.AsyncMock(side_effect=original_translate)
    translator.translate = mock_translate

    # Create a nested locale_str
    nested = MockLocaleStr("Nested")
    string = locale_str("Hello, World!", _string="test.greeting", name=nested)

    result = await translator.translate(string, "es")

    assert mock_translate.call_count == 2
    assert result == "¡Hola, Nested!"


@pytest.mark.asyncio
async def test_translator_non_modmail_string(mock_fluent_setup: None) -> None:
    """Test handling strings that aren't from Modmail (no _string extra)."""
    translator = Translator()

    # String without _string extra
    string = locale_str("Not a Modmail string")

    # Should return None as it's not a Modmail string
    result = await translator.translate(string, "es")
    assert result is None


@pytest.mark.asyncio
async def test_translator_with_unsupported_type(mock_fluent_setup: None) -> None:
    """Test that the translator handles unsupported types by converting them to strings."""
    translator = Translator()

    class CustomClass:
        def __str__(self) -> str:
            return "CustomObject"

    # Create an object with an unsupported type
    custom_obj = CustomClass()

    # Create a locale_str with the custom object in extras
    string = locale_str("Hello, {name}!", _string="test.greeting", name=custom_obj)

    # Translate to Spanish
    result = await translator.translate(string, "es")

    # Verify the custom object was converted to string
    assert result == "¡Hola, CustomObject!"


def test_underscore_function(mock_fluent_setup: None) -> None:
    """Test the _ function that creates locale_str objects."""
    # Test with basic string
    result = _("test.greeting", name="World")
    assert isinstance(result, locale_str)
    assert result.message == "Hello, World!"
    assert result.extras.get("_string") == "test.greeting"
    assert result.extras.get("name") == "World"


def test_underscore_with_various_types(mock_fluent_setup: None) -> None:
    """Test the _ function with various argument types."""
    # Test with different FluentTypes
    result = _(
        "test.greeting",
        name="World",
        number=42,
        decimal=Decimal("3.14"),
        dt=datetime.datetime(2023, 1, 1, 12, 0, tzinfo=datetime.UTC),
        today=datetime.date(2023, 1, 1),
        none_val=None,
    )

    assert result.extras.get("name") == "World"
    assert result.extras.get("number") == 42
    assert result.extras.get("decimal") == Decimal("3.14")
    assert isinstance(result.extras.get("dt"), datetime.datetime)
    assert isinstance(result.extras.get("today"), datetime.date)
    assert result.extras.get("none_val", -1) is None


def test_underscore_with_locale_str_object(mock_fluent_setup: None) -> None:
    """Test the _ function with a nested locale_str object."""
    nested = MockLocaleStr("Nested Value")

    # When _ is called, it should extract the message from the locale_str
    result = _("test.greeting", name=nested)

    assert result.message == "Hello, Nested Value!"
    assert result.extras.get("name") == nested
    assert result.extras.get("_string") == "test.greeting"


def test_underscore_with_unsupported_type(mock_fluent_setup: None) -> None:
    """Test the _ function with an unsupported type (should convert to string)."""

    class CustomClass:
        def __str__(self) -> str:
            return "Custom Object"

    custom_obj = CustomClass()

    # Should issue a warning and convert to string
    with pytest.warns(UserWarning, match="Unsupported type for translation"):
        result = _("test.greeting", name=custom_obj)  # pyright: ignore [reportArgumentType]

    assert result.extras.get("name") == custom_obj
