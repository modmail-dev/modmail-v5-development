"""
modmail.core.internals.embed
============================
A module providing a custom embed proxy system that supports lazy translation of embed content.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self, TypeAlias

import discord
from discord.app_commands import locale_str

__all__ = ["EmbedProxy"]

if TYPE_CHECKING:
    from .. import Translator

AnyStr: TypeAlias = str | locale_str


class EmbedProxy:
    """
    A proxy for discord.Embed that allows for lazy translation of strings.
    """

    __slots__ = (
        "color",
        "colour",
        "title",
        "url",
        "description",
        "timestamp",
        "footer_text",
        "footer_icon_url",
        "image_url",
        "thumbnail_url",
        "author_name",
        "author_url",
        "author_icon_url",
        "fields",
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
    ):
        """
        Initialize the EmbedProxy with optional parameters.
        All parameters are the same as discord.Embed(...).
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
        """
        Convert the EmbedProxy to a discord.Embed object.

        :param translator: The translator instance.
        :param locale: The locale to use for translation.
        :return: The translated discord.Embed object.
        """

        async def translate(string: AnyStr | None) -> str | None:
            """
            Translate a string using the translator.
            :param string: The string to translate.
            :return: The translated string or the original string if translation fails.
            """
            if string is None:
                return None
            if isinstance(string, locale_str):
                translated_string = await translator.translate(string, locale)
                if translated_string is not None:
                    return translated_string
                else:
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
        self.footer_text = text
        self.footer_icon_url = icon_url
        return self

    def remove_footer(self) -> Self:
        self.footer_text = None
        self.footer_icon_url = None
        return self

    def set_image(self, *, url: AnyStr | None) -> Self:
        self.image_url = url
        return self

    def set_thumbnail(self, *, url: AnyStr | None) -> Self:
        self.thumbnail_url = url
        return self

    def set_author(self, *, name: AnyStr, url: AnyStr | None = None, icon_url: AnyStr | None = None) -> Self:
        self.author_name = name
        self.author_url = url
        self.author_icon_url = icon_url
        return self

    def remove_author(self) -> Self:
        self.author_name = None
        self.author_url = None
        self.author_icon_url = None
        return self

    def add_field(self, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        self.fields.append((name, value, inline))
        return self

    def insert_field_at(self, index: int, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        self.fields.insert(index, (name, value, inline))
        return self

    def clear_fields(self) -> Self:
        self.fields.clear()
        return self

    def remove_field(self, index: int) -> Self:
        if 0 <= index < len(self.fields):
            self.fields.pop(index)
        return self

    def set_field_at(self, index: int, *, name: AnyStr, value: AnyStr, inline: bool = True) -> Self:
        if 0 <= index < len(self.fields):
            self.fields[index] = (name, value, inline)
        else:
            raise IndexError("field index out of range")
        return self
