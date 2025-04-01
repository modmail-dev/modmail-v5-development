from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext import commands
from pytest_mock import MockerFixture

from modmail.core import Bot, Cog, EmbedProxy, Translator, create_cog, lazy_hybrid_command


def translate(
    string: app_commands.locale_str | str, locale: discord.Locale | str, context: Any = None
) -> str | None:
    """Mock-translate the given string to the specified locale.

    Args:
        string: The locale string or regular string to translate.
        locale: The locale to translate to.
        context: Optional context for translation.

    Returns:
        Translated string or None if translation failed.
    """
    if isinstance(string, app_commands.locale_str):
        return f"{string.message}_{locale}"
    return string


@dataclass
class MockMessage:
    """Mock message object for testing context replies.

    Simulates a Discord message.

    Attributes:
        content: The content of the message.
    """

    content: str | None = "Test message"


class MockInteraction:
    """Mock interaction object for testing command interactions.

    Simulates a Discord interaction with locale information.
    """

    def __init__(self) -> None:
        """Initialize the mock interaction with French locale."""
        self.locale = discord.Locale.french


class MockContext:
    """Mock context for testing command handling and responses.

    Tracks sent messages and arguments for verification in tests.

    Attributes:
        bot: The mock bot instance.
        interaction: Optional interaction object.
        message: The message associated with this context.
        send_called: Whether send() has been called.
        sent_args: Arguments passed to the send method.
        sent_content: Content sent through the context.
    """

    def __init__(
        self, *, interaction: MockInteraction | None = None, message: discord.Message | None = None
    ) -> None:
        """Initialize the mock context.

        Args:
            interaction: Optional interaction object to associate with this context.
            message: Optional message object to associate with this context.
        """

        self.bot = MagicMock(spec=Bot)
        self.bot.translator = MagicMock(spec=Translator)
        self.bot.translator.translate = AsyncMock(side_effect=translate)

        self.interaction = interaction
        self.message = message or MockMessage()
        self.send_called = False
        self.sent_args: dict[str, Any] = {}
        self.sent_content: str | None = None

    async def send(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        """Send a message through this context.

        Args:
            content: The content of the message to send.
            **kwargs: Additional keyword arguments for the send operation.

        Returns:
            A mock message with the sent content.
        """
        self.send_called = True
        self.sent_content = content
        self.sent_args = kwargs
        return cast(discord.Message, MockMessage(content))


@pytest.fixture
def ctx() -> MockContext:
    """Provide a standard mock context for testing.

    Returns:
        A mock context instance with no interaction.
    """
    return MockContext()


@pytest.fixture
def interaction_ctx() -> MockContext:
    """Provide a mock context with an interaction for testing.

    Returns:
        A mock context instance with a mock interaction.
    """
    interaction = MockInteraction()
    return MockContext(interaction=interaction)


@pytest.fixture
def cog(mocker: MockerFixture) -> Cog:
    """Provide a configured cog instance for testing.

    Sets up a mock bot and configuration for testing cog functionality.

    Args:
        mocker: PyTest mock fixture for patching.

    Returns:
        An initialized Cog instance with mock dependencies.
    """
    mock_bot = mocker.MagicMock(spec=Bot)
    mock_bot.translator = MagicMock(spec=Translator)
    mock_bot.translator.translate = AsyncMock(side_effect=translate)

    # Mock CONFIG's default_locale
    mocker.patch("modmail.core.internals.cog.CONFIG.default_locale", "en-US")

    return Cog(mock_bot)


@pytest.mark.asyncio
async def test_reply_with_normal_context(cog: Cog, ctx: MockContext) -> None:
    """Test reply method with standard context without interaction."""
    await cog.reply(cast(commands.Context[Bot], ctx), "Test message", auto_embed=False)

    assert ctx.send_called
    assert ctx.sent_content == "Test message"
    assert "reference" in ctx.sent_args
    assert ctx.sent_args["reference"] == ctx.message


@pytest.mark.asyncio
async def test_reply_with_interaction_context(cog: Cog, interaction_ctx: MockContext) -> None:
    """Test reply method handles interaction contexts properly."""
    await cog.reply(cast(commands.Context[Bot], interaction_ctx), "Test message", auto_embed=False)

    assert interaction_ctx.send_called
    assert interaction_ctx.sent_content == "Test message"
    assert "reference" not in interaction_ctx.sent_args


@pytest.mark.asyncio
async def test_reply_with_original_message(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test reply method with standard context without interaction."""

    message = MockMessage()
    message.edit = mocker.AsyncMock()

    await cog.reply(cast(commands.Context[Bot], ctx), "Test message", auto_embed=False, original_message=message)

    assert not ctx.send_called
    message.edit.assert_awaited_once_with(content="Test message")


@pytest.mark.asyncio
async def test_send_with_locale_str(cog: Cog, ctx: MockContext) -> None:
    """Test send method correctly handles locale_str translation."""
    locale_string = app_commands.locale_str("Test message")
    await cog.send(cast(commands.Context[Bot], ctx), locale_string, auto_embed=False)

    assert ctx.send_called
    assert ctx.sent_content == "Test message_en-US"


@pytest.mark.asyncio
async def test_send_with_locale_str_translation_none(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test send method falls back to original message when translation fails."""
    locale_string = app_commands.locale_str("Test message")

    # Mock the translator to return None for translation
    cog.bot.translator.translate = mocker.AsyncMock(return_value=None)

    await cog.send(cast(commands.Context[Bot], ctx), locale_string, auto_embed=False)

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

    @lazy_hybrid_command()
    async def cmd2(self: Any, ctx: commands.Context[Bot]) -> None:
        """Second test command."""

    # Create cog using factory function
    TestCog = create_cog("TestCog", [cmd1, cmd2])  # noqa: N806

    # Check that cog was created correctly
    assert issubclass(TestCog, Cog)
    assert TestCog.__name__ == "TestCog"
    assert hasattr(TestCog, "cmd1")
    assert hasattr(TestCog, "cmd2")


@pytest.mark.asyncio
async def test_prompt_with_response(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test the prompt method when the user provides a response."""
    # Mock discord.ui.View
    mocker.patch.object(discord.ui.View, "wait")
    mocker.patch.object(discord.ui.View, "stop")

    # Mock the prompt message
    prompt_message = MockMessage(content="Prompt message")
    prompt_message.edit = mocker.AsyncMock()

    # Mock message response
    response_message = MockMessage(content="User response")

    # Mock listeners
    cog.bot._listeners = {"message": []}
    mocker.patch("modmail.core.internals.cog._", side_effect=lambda x="text": x)
    cog.bot.loop = mocker.MagicMock(spec=asyncio.BaseEventLoop)

    # Mock asyncio.wait_for to return a response
    wait_for_mock = mocker.patch("asyncio.wait_for", autospec=True)
    wait_for_mock.return_value = response_message

    # Mock a send call to return our mock prompt message
    ctx.send = AsyncMock(return_value=prompt_message)

    # Call the prompt method
    result_prompt, result_response = await cog.prompt(ctx, "Test prompt", wait_for=10.0, auto_embed=False)

    # Verify the prompt was sent with the view
    assert "view" in ctx.send.call_args[1]

    # Verify wait_for was called with the right timeout
    wait_for_mock.assert_awaited_once()
    assert wait_for_mock.call_args[0][1] == 10.0

    # Verify the result returned contains the expected messages
    assert result_prompt == prompt_message
    assert result_response == response_message

    # Verify the view was removed after getting a response
    prompt_message.edit.assert_awaited_once_with(view=None)


@pytest.mark.asyncio
async def test_prompt_timeout(cog: Cog, ctx: MockContext, mocker: MockerFixture) -> None:
    """Test the prompt method when it times out."""
    # Mock discord.ui.View
    mocker.patch.object(discord.ui.View, "wait")
    mocker.patch.object(discord.ui.View, "stop")

    # Mock the prompt message
    prompt_message = MockMessage(content="Prompt message")
    prompt_message.edit = mocker.AsyncMock()

    # Mock listeners
    cog.bot._listeners = {"message": []}
    mocker.patch("modmail.core.internals.cog._", side_effect=lambda x="text": x)
    cog.bot.loop = mocker.MagicMock(spec=asyncio.BaseEventLoop)

    # Mock asyncio.wait_for to timeout
    wait_for_mock = mocker.patch("asyncio.wait_for", autospec=True)
    wait_for_mock.side_effect = TimeoutError("Timeout")

    # Mock a send call to return our mock prompt message
    ctx.send = AsyncMock(return_value=prompt_message)

    # Mock the reply method
    reply_mock = mocker.patch.object(cog, "reply", autospec=True)

    # Call the prompt method
    result_prompt, result_response = await cog.prompt(ctx, "Test prompt", wait_for=10.0, reply=False)

    # Verify the result returned contains the expected message and None response
    assert result_prompt == prompt_message
    assert result_response is None

    # Verify the timeout message was sent
    reply_mock.assert_awaited_once()
    assert "ftl-msg-prompt-timeout" in str(reply_mock.call_args)
