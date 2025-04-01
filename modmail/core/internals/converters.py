"""Module for custom converters used in the bot.

This module provides custom converters for command arguments, such as stripping
whitespace from strings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from ..bot import Bot

__all__ = ["Str"]


class StrStripConverter:
    """A converter that strips whitespace from strings."""

    @classmethod
    async def convert(cls, ctx: commands.Context[Bot], value: str) -> str:
        """Convert a string by stripping whitespace.

        Args:
            ctx: The command context.
            value: The string to convert.

        Returns:
            The stripped string.
        """
        return value.strip()

    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> str:
        """Transform a string by stripping whitespace.

        Args:
            interaction: The interaction context.
            value: The string to transform.

        Returns:
            The stripped string.
        """
        return value.strip()


type Str = Annotated[str, StrStripConverter]
