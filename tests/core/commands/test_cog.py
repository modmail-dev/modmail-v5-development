from __future__ import annotations

from typing import Any, cast

import discord
import pytest
from discord import app_commands
from discord.ext import commands
from pytest_mock import MockerFixture

from modmail.core import Bot, Cog, EmbedProxy, create_cog, lazy_hybrid_command


class MockBot:
    """Mock Bot for testing cog functionality."""

    def __init__(self) -> None:
        self.translator = MockTranslator()


class MockTranslator:
    """Mock translator for testing cog translation functionality."""

    @staticmethod
    async def translate(
        string: app_commands.locale_str | str, locale: discord.Locale | str, context: Any = None
    ) -> str | None:
        if isinstance(string, app_commands.locale_str):
            return f"{string.message}_{locale}"
        return string


class MockMessage:
    """Mock message for testing context reply."""

    def __init__(self, content: str | None = "Test message") -> None:
        self.content = content


class MockInteraction:
    """Mock interaction for testing cog methods that use interaction context."""

    def __init__(self) -> None:
        self.locale = discord.Locale.french


class MockContext:
    """Mock context for testing cog methods."""

    def __init__(
        self, *, interaction: MockInteraction | None = None, message: discord.Message | None = None
    ) -> None:
        self.bot = MockBot()
        self.interaction = interaction
        self.message = message or MockMessage()
        self.send_called = False
        self.sent_args: dict[str, Any] = {}
        self.sent_content: str | None = None
        self.kwargs: dict[str, Any] = {}

    async def send(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        self.send_called = True
        self.sent_content = content
        self.sent_args = kwargs
        return cast(discord.Message, MockMessage(content))


@pytest.fixture
async def ctx() -> MockContext:
    """Fixture to provide a mock context."""
    return MockContext()


@pytest.fixture
async def interaction_ctx() -> MockContext:
    """Fixture to provide a mock context with interaction."""
    interaction = MockInteraction()
    ctx = MockContext(interaction=interaction)
    return ctx


@pytest.fixture
async def cog(mocker: MockerFixture) -> Cog:
    """Fixture to provide a cog instance with a mock bot."""
    mock_bot = mocker.MagicMock(spec=Bot)
    mock_bot.translator = MockTranslator()

    # Mock CONFIG
    mock_config = mocker.MagicMock()
    mock_config.default_locale = "en-US"
    mocker.patch("modmail.core.internals.cog.CONFIG", mock_config)

    cog_instance = Cog(mock_bot)
    return cog_instance


@pytest.mark.asyncio
async def test_reply_with_normal_context(cog: Cog, ctx: MockContext) -> None:
    """Test reply method with standard context without interaction."""
    await cog.reply(cast(commands.Context[Bot], ctx), "Test message")

    assert ctx.send_called
    assert ctx.sent_content == "Test message"
    assert "reference" in ctx.sent_args
    assert ctx.sent_args["reference"] == ctx.message


@pytest.mark.asyncio
async def test_reply_with_interaction_context(cog: Cog, interaction_ctx: MockContext) -> None:
    """Test reply method handles interaction contexts properly."""
    await cog.reply(cast(commands.Context[Bot], interaction_ctx), "Test message")

    assert interaction_ctx.send_called
    assert interaction_ctx.sent_content == "Test message"
    assert "reference" not in interaction_ctx.sent_args


@pytest.mark.asyncio
async def test_send_with_locale_str(cog: Cog, ctx: MockContext) -> None:
    """Test send method correctly handles locale_str translation."""
    locale_string = app_commands.locale_str("Test message")
    await cog.send(cast(commands.Context[Bot], ctx), locale_string)

    assert ctx.send_called
    assert ctx.sent_content == "Test message_en-US"


@pytest.mark.asyncio
async def test_send_with_locale_str_translation_none(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test send method falls back to original message when translation fails."""
    locale_string = app_commands.locale_str("Test message")

    # Mock the translator to return None for translation
    cog.bot.translator.translate = mocker.AsyncMock(return_value=None)

    await cog.send(cast(commands.Context[Bot], ctx), locale_string)

    assert ctx.send_called
    assert ctx.sent_content == "Test message"  # Should fallback to the message


@pytest.mark.asyncio
async def test_send_with_auto_embed(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test send method with auto_embed feature properly formats content into an embed."""
    # Create a mock embed proxy and to_embed method
    mock_embed = mocker.MagicMock(spec=discord.Embed)
    mock_to_embed = mocker.AsyncMock(return_value=mock_embed)

    # Patch the EmbedProxy class to return our mocked embed
    mocker.patch.object(EmbedProxy, "to_embed", mock_to_embed)

    await cog.send(cast(commands.Context[Bot], ctx), "Test message", auto_embed=True)

    assert ctx.send_called
    assert ctx.sent_content is None
    assert "embed" in ctx.sent_args
    assert ctx.sent_args["embed"] == mock_embed
    mock_to_embed.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_with_embed_proxy(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test send method correctly converts EmbedProxy to discord.Embed."""
    # Create a mock embed proxy and to_embed method
    mock_embed = mocker.MagicMock(spec=discord.Embed)
    mock_to_embed = mocker.AsyncMock(return_value=mock_embed)

    # Create an embed proxy instance
    embed_proxy = EmbedProxy(title="Test title")

    # Patch the to_embed method
    mocker.patch.object(EmbedProxy, "to_embed", mock_to_embed)

    await cog.send(cast(commands.Context[Bot], ctx), "Test message", embed=embed_proxy)

    assert ctx.send_called
    assert ctx.sent_content == "Test message"
    assert "embed" in ctx.sent_args
    assert ctx.sent_args["embed"] == mock_embed
    mock_to_embed.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_auto_embed_with_existing_embed(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test that auto_embed is ignored when an embed is already provided."""
    # Create a regular discord.Embed
    existing_embed = discord.Embed(title="Existing Embed")

    # Create a mock for EmbedProxy.to_embed to ensure it's not called
    mock_to_embed = mocker.AsyncMock()
    mocker.patch.object(EmbedProxy, "to_embed", mock_to_embed)

    await cog.send(cast(commands.Context[Bot], ctx), "Test message", auto_embed=True, embed=existing_embed)

    assert ctx.send_called
    assert ctx.sent_content == "Test message"  # Content should remain
    assert "embed" in ctx.sent_args
    assert ctx.sent_args["embed"] == existing_embed  # Embed should be unchanged
    mock_to_embed.assert_not_awaited()  # to_embed should not be called


@pytest.mark.asyncio
async def test_send_auto_embed_with_none_content(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test that auto_embed is ignored when content is None."""
    # Create a mock for EmbedProxy.to_embed to ensure it's not called
    mock_to_embed = mocker.AsyncMock()
    mocker.patch.object(EmbedProxy, "to_embed", mock_to_embed)

    await cog.send(cast(commands.Context[Bot], ctx), None, auto_embed=True)

    assert ctx.send_called
    assert ctx.sent_content is None
    assert "embed" not in ctx.sent_args  # No embed should be created
    mock_to_embed.assert_not_awaited()  # to_embed should not be called


@pytest.mark.asyncio
async def test_send_with_embeds_list(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test send method handles lists of embeds with mixed types correctly."""
    # Create mock embeds
    mock_embed1 = mocker.MagicMock(spec=discord.Embed)
    mock_to_embed = mocker.AsyncMock(return_value=mock_embed1)

    # Create a regular discord.Embed and an EmbedProxy
    regular_embed = discord.Embed(title="Regular embed")
    embed_proxy = EmbedProxy(title="Proxy embed")

    # Patch the to_embed method
    mocker.patch.object(EmbedProxy, "to_embed", mock_to_embed)

    await cog.send(cast(commands.Context[Bot], ctx), "Test message", embeds=[regular_embed, embed_proxy])

    assert ctx.send_called
    assert ctx.sent_content == "Test message"
    assert "embeds" in ctx.sent_args
    assert len(ctx.sent_args["embeds"]) == 2
    assert ctx.sent_args["embeds"][0] == regular_embed
    assert ctx.sent_args["embeds"][1] == mock_embed1
    mock_to_embed.assert_awaited_once()


@pytest.mark.asyncio
async def test_translate_method(cog: Cog, ctx: MockContext) -> None:
    """Test translate method correctly uses default locale when not in interaction."""
    locale_string = app_commands.locale_str("Test message")
    result = await cog.translate(cast(commands.Context[Bot], ctx), locale_string)

    assert result == "Test message_en-US"  # The default locale is set to "en-US"


@pytest.mark.asyncio
async def test_translate_method_with_interaction(cog: Cog, interaction_ctx: MockContext) -> None:
    """Test translate method uses interaction locale when available."""
    locale_string = app_commands.locale_str("Test message")
    result = await cog.translate(cast(commands.Context[Bot], interaction_ctx), locale_string)

    assert result == "Test message_fr"  # The locale is set to French in the interaction


@pytest.mark.asyncio
async def test_translate_method_with_locale_str_translation_none(
    cog: Cog, ctx: MockContext, mocker: MockerFixture
) -> None:
    """Test translate method falls back to original message when translation fails."""
    locale_string = app_commands.locale_str("Test message")

    # Mock the translator to return None for translation
    cog.bot.translator.translate = mocker.AsyncMock(return_value=None)

    result = await cog.translate(cast(commands.Context[Bot], ctx), locale_string)
    assert result == "Test message"  # Should fallback to the message


def test_create_cog() -> None:
    """Test create_cog factory function builds a valid cog class with commands."""

    # Create mock commands
    @lazy_hybrid_command()
    async def cmd1(self: Any, ctx: commands.Context[Bot]) -> None:
        """First test command."""
        pass

    @lazy_hybrid_command()
    async def cmd2(self: Any, ctx: commands.Context[Bot]) -> None:
        """Second test command."""
        pass

    # Create cog using factory function
    TestCog = create_cog("TestCog", [cmd1, cmd2])

    # Check that cog was created correctly
    assert issubclass(TestCog, Cog)
    assert TestCog.__name__ == "TestCog"
    assert hasattr(TestCog, "cmd1")
    assert hasattr(TestCog, "cmd2")
