"""Lazy-translating [`EmbedProxy`][] that defers locale resolution until send time."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Literal, Self

import discord
from discord.app_commands import locale_str

__all__ = ["EmbedProxy"]

if TYPE_CHECKING:
    from .translator import Translator

type AnyStr = str | locale_str


class EmbedProxy:
    """Builder for [`discord.Embed`][] with lazy locale-string support.

    Stores `locale_str` values as-is; all translation happens inside [`to_embed`][]
    when a locale is known, so one proxy instance can render into any supported locale.

    Attributes:
        color: Embed accent color (alias: `colour`).
        colour: Alias for `color`.
        title: Title text.
        url: URL linked from the title.
        description: Main body text.
        footer_text: Footer text (`None` if not set).
        footer_icon_url: Footer icon URL (`None` if not set).
        image_url: Embed image URL (`None` if not set).
        thumbnail_url: Thumbnail URL (`None` if not set).
        author_name: Author display name (`None` if not set).
        author_url: URL linked from the author name (`None` if not set).
        author_icon_url: Author icon URL (`None` if not set).
        fields: `(name, value, inline)` tuples in insertion order.
        timestamp: Embed timestamp (`None` if not set).
    """

    __slots__ = (
        "_timestamp",
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
        timestamp: datetime.datetime | Literal[True] | None = None,
    ) -> None:
        """Initialize the proxy with common embed fields.

        Args:
            colour: Embed accent color.
            color: Alias for `colour`.
            title: Title text.
            url: URL linked from the title.
            description: Main body text.
            timestamp: Embed timestamp; pass `True` to use the current UTC time.
        """
        self.color = color
        self.colour = colour
        self.title = title
        self.url = url
        self.description = description
        self.footer_text: AnyStr | None = None
        self.footer_icon_url: AnyStr | None = None
        self.image_url: AnyStr | None = None
        self.thumbnail_url: AnyStr | None = None
        self.author_name: AnyStr | None = None
        self.author_url: AnyStr | None = None
        self.author_icon_url: AnyStr | None = None
        self.fields: list[tuple[AnyStr, AnyStr, bool]] = []  # name, value, inline

        if timestamp is True:
            self._timestamp = datetime.datetime.now(datetime.UTC)
        else:
            self._timestamp = timestamp

    def to_embed(self, translator: Translator, locale: discord.Locale | str) -> discord.Embed:
        """Translate all stored strings and return a [`discord.Embed`][].

        Args:
            translator: [`Translator`][] instance used for FTL lookup.
            locale: Target locale for all `locale_str` values.

        Returns:
            A fully resolved [`discord.Embed`][].
        """

        def translate(string: AnyStr | None) -> str | None:
            """Translate `string` and return the result, or `None` when `string` is `None`.

            Returns:
                Translated string or `None`.
            """
            if string is None:
                return None
            if isinstance(string, locale_str):
                translated_string = translator.translate_sync(string, locale)
                if translated_string is not None:
                    return translated_string
                return string.message
            return string

        embed = discord.Embed(
            title=translate(self.title),
            url=translate(self.url),
            description=translate(self.description),
            color=self.color,
            colour=self.colour,
            timestamp=self.timestamp,
        )
        if self.footer_text is not None or self.footer_icon_url is not None:
            embed.set_footer(text=translate(self.footer_text), icon_url=translate(self.footer_icon_url))
        if self.image_url is not None:
            embed.set_image(url=translate(self.image_url))
        if self.thumbnail_url is not None:
            embed.set_thumbnail(url=translate(self.thumbnail_url))
        if self.author_name is not None:
            embed.set_author(
                name=translate(self.author_name),
                url=translate(self.author_url),
                icon_url=translate(self.author_icon_url),
            )
        for name, value, inline in self.fields:
            embed.add_field(name=translate(name), value=translate(value), inline=inline)
        return embed

    @property
    def timestamp(self) -> datetime.datetime | None:
        """Embed timestamp (`None` if not set)."""
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: datetime.datetime | Literal[True] | None) -> None:  # pyright: ignore[reportPropertyTypeMismatch]
        """Set the embed timestamp; pass `True` to use the current UTC time."""
        if value is True:
            self._timestamp = datetime.datetime.now(datetime.UTC)
        else:
            self._timestamp = value

    def set_footer(self, *, text: AnyStr | None = None, icon_url: AnyStr | None = None) -> Self:
        """Set the embed footer.

        Args:
            text: Footer text.
            icon_url: Footer icon URL.

        Returns:
            `self` for chaining.
        """
        self.footer_text = text
        self.footer_icon_url = icon_url
        return self

    def remove_footer(self) -> Self:
        """Clear the embed footer.

        Returns:
            `self` for chaining.
        """
        self.footer_text = None
        self.footer_icon_url = None
        return self

    def set_image(self, *, url: AnyStr | None) -> Self:
        """Set the embed image.

        Args:
            url: Image URL.

        Returns:
            `self` for chaining.
        """
        self.image_url = url
        return self

    def set_thumbnail(self, *, url: AnyStr | None) -> Self:
        """Set the embed thumbnail.

        Args:
            url: Thumbnail URL.

        Returns:
            `self` for chaining.
        """
        self.thumbnail_url = url
        return self

    def set_author(self, *, name: AnyStr, url: AnyStr | None = None, icon_url: AnyStr | None = None) -> Self:
        """Set the embed author.

        Args:
            name: Author display name.
            url: URL linked from the author name.
            icon_url: Author icon URL.

        Returns:
            `self` for chaining.
        """
        self.author_name = name
        self.author_url = url
        self.author_icon_url = icon_url
        return self

    def remove_author(self) -> Self:
        """Clear the embed author.

        Returns:
            `self` for chaining.
        """
        self.author_name = None
        self.author_url = None
        self.author_icon_url = None
        return self

    def add_field(self, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        """Append a field to the embed.

        Args:
            name: Field name.
            value: Field value.
            inline: Whether the field is displayed inline.

        Returns:
            `self` for chaining.
        """
        self.fields.append((name, value, inline))
        return self

    def insert_field_at(self, index: int, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        """Insert a field at a specific index.

        Args:
            index: Position to insert at.
            name: Field name.
            value: Field value.
            inline: Whether the field is displayed inline.

        Returns:
            `self` for chaining.
        """
        self.fields.insert(index, (name, value, inline))
        return self

    def clear_fields(self) -> Self:
        """Remove all fields.

        Returns:
            `self` for chaining.
        """
        self.fields.clear()
        return self

    def remove_field(self, index: int) -> Self:
        """Remove the field at `index` (no-op if out of range).

        Args:
            index: Position of the field to remove.

        Returns:
            `self` for chaining.
        """
        if 0 <= index < len(self.fields):
            self.fields.pop(index)
        return self

    def set_field_at(self, index: int, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        """Replace the field at `index`.

        Args:
            index: Position of the field to replace.
            name: New field name.
            value: New field value.
            inline: Whether the field is displayed inline.

        Returns:
            `self` for chaining.

        Raises:
            IndexError: If `index` is out of range.
        """
        if 0 <= index < len(self.fields):
            self.fields[index] = (name, value, inline)
        else:
            raise IndexError("field index out of range")
        return self
