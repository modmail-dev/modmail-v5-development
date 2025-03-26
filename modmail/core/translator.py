"""
modmail.core.translator
=======================
Provides translation services using FluentLocalization for Modmail interfaces.
Loads locale files from the modmail/locales directory based on configuration settings.
"""

from __future__ import annotations

import logging
import os
import warnings
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, TypeAlias

import discord
from discord import app_commands
from discord.app_commands import locale_str
from fluent.runtime import FluentLocalization, FluentResourceLoader

from .. import CONFIG

__all__ = ["Translator", "_"]

logger = logging.getLogger(__name__)

# Fluent supported types (see: fluent.runtime.utils.native_to_fluent)
FluentTypes: TypeAlias = str | int | float | Decimal | datetime | date | None


class HasLocaleStr(Protocol):
    def __locale_str__(self) -> locale_str: ...


# locales files are located in ../locales/{locale}/main.ftl
locale_loader = FluentResourceLoader(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales", "{locale}")
)

all_l10n: dict[str, FluentLocalization] = {}
for allowed_locale in CONFIG.allowed_locales:
    # Load the FluentLocalization for each locale, use en as fallback if the locale is missing translations
    if allowed_locale != "en":
        all_l10n[allowed_locale] = FluentLocalization([allowed_locale, "en"], ["main.ftl"], locale_loader)
    else:
        all_l10n[allowed_locale] = FluentLocalization([allowed_locale], ["main.ftl"], locale_loader)


class Translator(app_commands.Translator):
    async def translate(
        self,
        string: locale_str,
        locale: discord.Locale | str,
        context: app_commands.TranslationContextTypes | None = None,
    ) -> str | None:
        """
        Translate a message using FluentLocalization.

        :param string: The string to translate.
        :param locale: The locale to translate to, could be the name of the locale or provided by discord.py.
        :param context: [IGNORED] The context in which the translation is used.
        :return: The translated string or None if translation isn't available.
        """
        if "_string" not in string.extras:
            return None  # Not Modmail's string

        l10n = all_l10n[CONFIG.default_locale]

        locale_name = locale.value if isinstance(locale, discord.Locale) else locale
        if locale_name in all_l10n:
            l10n = all_l10n[locale_name]
        else:
            if "-" in locale_name:
                # If the locale is in the form of xx-YY (e.g., en-US), check if the base locale (xx) is supported
                locale_name = locale_name.split("-", maxsplit=1)[0]
                if locale_name in all_l10n:
                    l10n = all_l10n[locale_name]

        if l10n.locales == all_l10n[CONFIG.default_locale].locales:
            return string.message  # Already translated by _()

        # Real message stored in .extras['_string']
        message: str = string.extras["_string"]

        # Convert all extras items to supported types
        for key, value in string.extras.items():
            if key == "_string":
                continue
            if hasattr(value, "__locale_str__"):
                # If the value is a locale_str, translate it (recursive call)
                string.extras[key] = await self.translate(value.__locale_str__(), locale, context)
            elif isinstance(value, FluentTypes):
                string.extras[key] = value
            else:
                string.extras[key] = str(value)

        return l10n.format_value(message, string.extras)


def _(string: str, /, **kwargs: FluentTypes | HasLocaleStr) -> locale_str:
    """
    Translate string to default locale and move the original string into the extras dict.

    This is necessary because discord.py assumes the string to be the default string and validates it.
    """

    # extras for the default translation
    temp_kwargs: dict[str, FluentTypes] = {}

    for key, value in kwargs.items():
        if hasattr(value, "__locale_str__"):  # If the value is a locale_str, use the default message
            temp_kwargs[key] = value.__locale_str__().message  # type: ignore[reportUnknownMemberType]
        elif isinstance(value, FluentTypes):
            temp_kwargs[key] = value
        else:
            warnings.warn(f"Unsupported type for translation: {value} ({type(value)})", stacklevel=2)
            temp_kwargs[key] = str(value)  # Convert to string

    default_translated_string = all_l10n[CONFIG.default_locale].format_value(string, temp_kwargs)
    kwargs["_string"] = string
    return locale_str(default_translated_string, **kwargs)
