from __future__ import annotations

import datetime
from typing import Any

import discord
import pytest
from discord import app_commands

# noinspection PyProtectedMember
from modmail.core import EmbedProxy, Translator, _


class MockTranslator:
    """Mock translator for testing EmbedProxy translations.

    A simple mock implementation that simulates translation by appending
    the locale to the original message.
    """

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    async def translate(
        self, string: app_commands.locale_str | str, locale: discord.Locale | str, context: Any = None
    ) -> str | None:
        """Simulate translation by appending locale to string as translated text.

        Args:
            string: The string or locale_str to translate.
            locale: The target locale for translation.
            context: Optional context information for translation.

        Returns:
            The "translated" string with locale appended, or None if translation fails.
        """
        if isinstance(string, app_commands.locale_str):
            if string.message == "RETURN_NONE":  # Simulate a case where translation fails
                return None

            if "_string" in string.extras:
                # For locale_str created with _()
                return f"{string.message}_{locale}"
            return f"{string.message}_{locale}"
        return string


@pytest.fixture
def translator() -> MockTranslator:
    """Fixture to provide a mock translator.

    Returns:
        An instance of MockTranslator for testing.
    """
    return MockTranslator()


def test_embed_proxy_basic_initialization() -> None:
    """Test that EmbedProxy initializes with basic properties correctly."""
    embed_proxy = EmbedProxy(
        title="Test Title",
        description="Test Description",
        colour=discord.Colour.blue(),
        url="https://example.com",
        timestamp=datetime.datetime(2023, 1, 1, 12, 0, tzinfo=datetime.UTC),
    )

    assert embed_proxy.title == "Test Title"
    assert embed_proxy.description == "Test Description"
    assert embed_proxy.colour == discord.Colour.blue()
    assert embed_proxy.url == "https://example.com"
    assert isinstance(embed_proxy.timestamp, datetime.datetime)
    assert len(embed_proxy.fields) == 0


@pytest.mark.asyncio
async def test_to_embed_non_localized_conversion(translator: Translator) -> None:
    """Test conversion from EmbedProxy to discord.Embed with non-localized content."""
    embed_proxy = EmbedProxy(title="Test Title", description="Test Description", color=0x00FF00)

    locale = "en-US"
    discord_embed = await embed_proxy.to_embed(translator, locale)

    assert isinstance(discord_embed, discord.Embed)
    assert discord_embed.title == "Test Title"
    assert discord_embed.description == "Test Description"
    assert discord_embed.color == discord.Color(0x00FF00)


@pytest.mark.asyncio
async def test_to_embed_with_locale_str(translator: Translator) -> None:
    """Test EmbedProxy correctly translates locale_str objects during conversion."""
    title_locale_str = _("test.title")
    description_locale_str = _("test.description")

    embed_proxy = EmbedProxy(title=title_locale_str, description=description_locale_str)
    embed_proxy.set_author(name=_("RETURN_NONE"))

    locale = "fr"
    discord_embed = await embed_proxy.to_embed(translator, locale)

    assert isinstance(discord_embed, discord.Embed)
    assert discord_embed.title == f"{title_locale_str.message}_{locale}"
    assert discord_embed.description == f"{description_locale_str.message}_{locale}"
    assert discord_embed.author.name == "RETURN_NONE"


@pytest.mark.asyncio
async def test_embed_footer(translator: Translator) -> None:
    """Test footer setting and translation functionality in EmbedProxy."""
    embed_proxy = EmbedProxy()
    embed_proxy.set_footer(text=_("test.footer"), icon_url="https://example.com/icon.png")

    locale = "de"
    discord_embed = await embed_proxy.to_embed(translator, locale)

    assert discord_embed.footer.text == f"{_('test.footer').message}_{locale}"
    assert discord_embed.footer.icon_url == "https://example.com/icon.png"

    # Test footer removal
    embed_proxy.remove_footer()
    discord_embed = await embed_proxy.to_embed(translator, locale)
    assert discord_embed.footer.text is None


@pytest.mark.asyncio
async def test_embed_author(translator: Translator) -> None:
    """Test author setting and translation functionality in EmbedProxy."""
    embed_proxy = EmbedProxy()
    embed_proxy.set_author(
        name=_("test.author"), url="https://example.com/author", icon_url="https://example.com/author-icon.png"
    )

    locale = "es"
    discord_embed = await embed_proxy.to_embed(translator, locale)

    assert discord_embed.author.name == f"{_('test.author').message}_{locale}"
    assert discord_embed.author.url == "https://example.com/author"
    assert discord_embed.author.icon_url == "https://example.com/author-icon.png"

    # Test author removal
    embed_proxy.remove_author()
    discord_embed = await embed_proxy.to_embed(translator, locale)
    assert not hasattr(discord_embed.author, "name") or discord_embed.author.name is None


@pytest.mark.asyncio
async def test_embed_image_and_thumbnail(translator: Translator) -> None:
    """Test image and thumbnail URL setting with translation support."""
    embed_proxy = EmbedProxy()
    embed_proxy.set_image(url=_("https://example.com/image.png"))
    embed_proxy.set_thumbnail(url="https://example.com/thumbnail.png")

    locale = "ja"
    discord_embed = await embed_proxy.to_embed(translator, locale)

    assert discord_embed.image.url == f"https://example.com/image.png_{locale}"
    assert discord_embed.thumbnail.url == "https://example.com/thumbnail.png"


@pytest.mark.asyncio
async def test_field_operations(translator: Translator) -> None:
    """Test comprehensive field manipulation operations and their translation."""
    embed_proxy = EmbedProxy()

    # Add fields
    embed_proxy.add_field(name=_("field1.name"), value=_("field1.value"), inline=True)
    embed_proxy.add_field(name=_("field2.name"), value=_("field2.value"), inline=False)

    assert len(embed_proxy.fields) == 2

    # Insert field
    embed_proxy.insert_field_at(1, name=_("inserted.name"), value=_("inserted.value"))
    assert len(embed_proxy.fields) == 3

    # Set field
    embed_proxy.set_field_at(0, name=_("modified.name"), value=_("modified.value"), inline=False)

    # Remove field
    embed_proxy.remove_field(2)
    assert len(embed_proxy.fields) == 2

    locale = "fr"
    discord_embed = await embed_proxy.to_embed(translator, locale)

    # Check translated fields
    assert len(discord_embed.fields) == 2
    assert discord_embed.fields[0].name == f"{_('modified.name').message}_{locale}"
    assert discord_embed.fields[0].value == f"{_('modified.value').message}_{locale}"
    assert discord_embed.fields[0].inline is False

    assert discord_embed.fields[1].name == f"{_('inserted.name').message}_{locale}"
    assert discord_embed.fields[1].value == f"{_('inserted.value').message}_{locale}"

    # Clear fields
    embed_proxy.clear_fields()
    assert len(embed_proxy.fields) == 0

    discord_embed = await embed_proxy.to_embed(translator, locale)
    assert len(discord_embed.fields) == 0


@pytest.mark.asyncio
async def test_method_chaining(translator: Translator) -> None:
    """Test method chaining functionality in EmbedProxy."""
    locale = "it"

    # Create an embed using method chaining
    embed_proxy = (
        EmbedProxy(title=_("test.title"))
        .set_author(name=_("test.author"))
        .set_footer(text=_("test.footer"))
        .add_field(name=_("field1.name"), value=_("field1.value"))
        .add_field(name=_("field2.name"), value=_("field2.value"))
    )

    # Check that the embed has all the expected properties
    discord_embed = await embed_proxy.to_embed(translator, locale)

    assert discord_embed.title == f"{_('test.title').message}_{locale}"
    assert discord_embed.author.name == f"{_('test.author').message}_{locale}"
    assert discord_embed.footer.text == f"{_('test.footer').message}_{locale}"
    assert len(discord_embed.fields) == 2


def test_set_field_at_index_error() -> None:
    """Test that set_field_at properly raises IndexError with invalid indices."""
    embed_proxy = EmbedProxy()

    with pytest.raises(IndexError, match="field index out of range"):
        embed_proxy.set_field_at(0, name="Test", value="Value")

    # Add a field so index 0 is valid, but 1 isn't
    embed_proxy.add_field(name="Field", value="Value")

    with pytest.raises(IndexError, match="field index out of range"):
        embed_proxy.set_field_at(1, name="Test", value="Value")
