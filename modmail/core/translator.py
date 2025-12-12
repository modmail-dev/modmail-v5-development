"""Provides translation services using FluentLocalization for Modmail interfaces.

Loads locale files from the modmail/locales directory based on configuration settings.
"""

from __future__ import annotations

import logging
import warnings
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import discord
from discord import app_commands
from discord.app_commands import locale_str
from fluent.runtime import FluentLocalization, FluentResourceLoader

from .. import CONFIG

__all__ = ["Translator", "_"]

logger = logging.getLogger(__name__)

# Fluent supported types (see: fluent.runtime.utils.native_to_fluent)
FluentTypes = str | int | float | Decimal | datetime | date | None


class HasLocaleStr(Protocol):  # pragma: no cover
    def __locale_str__(self) -> locale_str:
        """Protocol for objects that can be converted to locale_str.

        Returns:
            A locale_str representation of the object.
        """
        ...


# locales files are located in ../locales/{locale}/main.ftl
locale_loader = FluentResourceLoader(str(Path(__file__).absolute().parent.parent / "locales" / "{locale}"))

all_l10n: dict[str, FluentLocalization] = {}
for allowed_locale in CONFIG.allowed_locales:
    # Load the FluentLocalization for each locale, use en as fallback if the locale is missing translations
    if allowed_locale != "en":
        all_l10n[allowed_locale] = FluentLocalization([allowed_locale, "en"], ["main.ftl"], locale_loader)
    else:
        all_l10n[allowed_locale] = FluentLocalization([allowed_locale], ["main.ftl"], locale_loader)


class Translator(app_commands.Translator):
    """Custom translator for Modmail using FluentLocalization."""

    async def translate(
        self,
        string: locale_str,
        locale: discord.Locale | str,
        context: app_commands.TranslationContextTypes | None = None,
    ) -> str | None:
        """Translate a message using FluentLocalization.

        Args:
            string: The string to translate.
            locale: The locale to translate to, could be a discord.Locale object or a locale string.
            context: The context in which the translation is used (ignored in this implementation).

        Returns:
            The translated string or None if translation isn't available.
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
            elif isinstance(value, locale_str):
                # TODO: check if this works
                string.extras[key] = await self.translate(value, locale, context)
            elif isinstance(value, FluentTypes):
                string.extras[key] = value
            else:
                string.extras[key] = str(value)

        return l10n.format_value(message, string.extras)


def _(string: str, /, **kwargs: FluentTypes | HasLocaleStr | locale_str) -> locale_str:
    """Translate string to default locale and prepare for multi-locale support.

    This function handles the initial translation to the default locale and stores
    the original string in extras for later translation to other locales.

    Args:
        string: The raw message key/string to be translated.
        **kwargs: Optional parameters for string formatting. Can be basic types or objects
            that implement __locale_str__.

    Returns:
        A locale_str object containing the translated string for default locale and
        metadata for other locales.

    Warnings:
        Warning: If an unsupported type is provided for translation.
    """
    # extras for the default translation
    temp_kwargs: dict[str, FluentTypes] = {}

    for key, value in kwargs.items():
        # If the value can be converted to a locale_str, use the default message
        if hasattr(value, "__locale_str__"):
            temp_kwargs[key] = value.__locale_str__().message  # pyright: ignore [reportUnknownMemberType, reportOptionalMemberAccess, reportAttributeAccessIssue]
        elif isinstance(value, locale_str):
            temp_kwargs[key] = value.message
        elif isinstance(value, FluentTypes):
            temp_kwargs[key] = value
        else:
            warnings.warn(f"Unsupported type for translation: {value} ({type(value)})", stacklevel=2)
            temp_kwargs[key] = str(value)  # Convert to string

    default_translated_string = all_l10n[CONFIG.default_locale].format_value(string, temp_kwargs)
    kwargs["_string"] = string
    return locale_str(default_translated_string, **kwargs)
