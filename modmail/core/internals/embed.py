"""Custom embed proxy system supporting lazy translation of embed content.

This module provides a proxy for discord.Embed that allows for lazy translation
of strings, enabling localization of embed content based on the user's locale.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
from discord.app_commands import locale_str

__all__ = ["EmbedProxy"]

if TYPE_CHECKING:
    from .. import Translator

type AnyStr = str | locale_str


class EmbedProxy:
    """A proxy for discord.Embed that allows for lazy translation of strings.

    This class mimics the interface of discord.Embed but stores locale_str objects
    that can be translated at a later time when the embed is needed.

    Attributes:
        author_icon_url: URL for the author's icon.
        author_name: Name of the author.
        author_url: URL for the author.
        color: Color of the embed as an integer or Discord.Colour.
        colour: Alias for color.
        description: The description of the embed.
        fields: List of fields as tuples of (name, value, inline).
        footer_icon_url: URL for the footer icon.
        footer_text: Text for the footer.
        image_url: URL for the embed image.
        thumbnail_url: URL for the embed thumbnail.
        timestamp: Timestamp for the embed.
        title: The title of the embed.
        url: URL for the embed title.
    """

    __slots__ = (
        "author_icon_url",
        "author_name",
        "author_url",
        "color",
        "colour",
        "description",
        "fields",
        "footer_icon_url",
        "footer_text",
        "image_url",
        "thumbnail_url",
        "timestamp",
        "title",
        "url",
    )

    def __init__(
        self,
        *,
        colour: int | discord.Colour | None = None,
        color: int | discord.Colour | None = None,
        title: AnyStr | None = None,
        url: AnyStr | None = None,
        description: AnyStr | None = None,
        timestamp: datetime.datetime | None = None,
    ) -> None:
        """Initialize the EmbedProxy with optional parameters.

        Args:
            colour: The colour of the embed.
            color: The color of the embed. Alias for colour
            title: The title of the embed.
            url: The URL for the embed title.
            description: The description of the embed.
            timestamp: The timestamp for the embed.
        """
        self.color = color
        self.colour = colour
        self.title = title
        self.url = url
        self.description = description
        self.timestamp = timestamp
        self.footer_text: AnyStr | None = None
        self.footer_icon_url: AnyStr | None = None
        self.image_url: AnyStr | None = None
        self.thumbnail_url: AnyStr | None = None
        self.author_name: AnyStr | None = None
        self.author_url: AnyStr | None = None
        self.author_icon_url: AnyStr | None = None
        self.fields: list[tuple[AnyStr, AnyStr, bool]] = []  # name, value, inline

    async def to_embed(self, translator: Translator, locale: discord.Locale | str) -> discord.Embed:
        """Convert the EmbedProxy to a discord.Embed object with translated strings.

        Args:
            translator: The translator instance to use for translation.
            locale: The locale to translate strings into.

        Returns:
            The translated Discord embed object.
        """

        async def translate(string: AnyStr | None) -> str | None:
            """Translate a string using the translator.

            Args:
                string: The string to translate.

            Returns:
                The translated string, or None if the input was None.
            """
            if string is None:
                return None
            if isinstance(string, locale_str):
                translated_string = await translator.translate(string, locale)
                if translated_string is not None:
                    return translated_string
                return string.message
            return string

        embed = discord.Embed(
            title=await translate(self.title),
            url=await translate(self.url),
            description=await translate(self.description),
            color=self.color,
            colour=self.colour,
            timestamp=self.timestamp,
        )
        if self.footer_text is not None or self.footer_icon_url is not None:
            embed.set_footer(
                text=await translate(self.footer_text), icon_url=await translate(self.footer_icon_url)
            )
        if self.image_url is not None:
            embed.set_image(url=await translate(self.image_url))
        if self.thumbnail_url is not None:
            embed.set_thumbnail(url=await translate(self.thumbnail_url))
        if self.author_name is not None:
            embed.set_author(
                name=await translate(self.author_name),
                url=await translate(self.author_url),
                icon_url=await translate(self.author_icon_url),
            )
        for name, value, inline in self.fields:
            embed.add_field(name=await translate(name), value=await translate(value), inline=inline)
        return embed

    def set_footer(self, *, text: AnyStr | None = None, icon_url: AnyStr | None = None) -> Self:
        """Set the footer of the embed.

        Args:
            text: The footer text.
            icon_url: URL for the footer icon.

        Returns:
            The embed proxy instance for chaining.
        """
        self.footer_text = text
        self.footer_icon_url = icon_url
        return self

    def remove_footer(self) -> Self:
        """Remove the footer from the embed.

        Returns:
            The embed proxy instance for chaining.
        """
        self.footer_text = None
        self.footer_icon_url = None
        return self

    def set_image(self, *, url: AnyStr | None) -> Self:
        """Set the image of the embed.

        Args:
            url: URL for the image.

        Returns:
            The embed proxy instance for chaining.
        """
        self.image_url = url
        return self

    def set_thumbnail(self, *, url: AnyStr | None) -> Self:
        """Set the thumbnail of the embed.

        Args:
            url: URL for the thumbnail.

        Returns:
            The embed proxy instance for chaining.
        """
        self.thumbnail_url = url
        return self

    def set_author(self, *, name: AnyStr, url: AnyStr | None = None, icon_url: AnyStr | None = None) -> Self:
        """Set the author of the embed.

        Args:
            name: The name of the author.
            url: URL for the author.
            icon_url: URL for the author's icon.

        Returns:
            The embed proxy instance for chaining.
        """
        self.author_name = name
        self.author_url = url
        self.author_icon_url = icon_url
        return self

    def remove_author(self) -> Self:
        """Remove the author from the embed.

        Returns:
            The embed proxy instance for chaining.
        """
        self.author_name = None
        self.author_url = None
        self.author_icon_url = None
        return self

    def add_field(self, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        """Add a field to the embed.

        Args:
            name: The name of the field.
            value: The value of the field.
            inline: Whether the field should be inline.

        Returns:
            The embed proxy instance for chaining.
        """
        self.fields.append((name, value, inline))
        return self

    def insert_field_at(self, index: int, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        """Insert a field at a specific position.

        Args:
            index: The index to insert the field at.
            name: The name of the field.
            value: The value of the field.
            inline: Whether the field should be inline.

        Returns:
            The embed proxy instance for chaining.
        """
        self.fields.insert(index, (name, value, inline))
        return self

    def clear_fields(self) -> Self:
        """Remove all fields from the embed.

        Returns:
            The embed proxy instance for chaining.
        """
        self.fields.clear()
        return self

    def remove_field(self, index: int) -> Self:
        """Remove a field at a specific position.

        Args:
            index: The index of the field to remove.

        Returns:
            The embed proxy instance for chaining.
        """
        if 0 <= index < len(self.fields):
            self.fields.pop(index)
        return self

    def set_field_at(self, index: int, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        """Update a field at a specific position.

        Args:
            index: The index of the field to update.
            name: The new name of the field.
            value: The new value of the field.
            inline: Whether the field should be inline.

        Returns:
            The embed proxy instance for chaining.

        Raises:
            IndexError: If the index is out of range.
        """
        if 0 <= index < len(self.fields):
            self.fields[index] = (name, value, inline)
        else:
            raise IndexError("field index out of range")
        return self
