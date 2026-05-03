"""Fluent-based translation services for Modmail.

[`Translator`][] wraps `FluentLocalization` and resolves [`locale_str`][] objects at
render time. The module-level [`_`][] function marks a string for translation and
pre-renders it in the default locale.
"""

from __future__ import annotations

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

__all__ = ["Translator", "_", "supported_locales"]

# Fluent supported types (see: fluent.runtime.utils.native_to_fluent)
FluentTypes = str | int | float | Decimal | datetime | date | None


class HasLocaleStr(Protocol):  # pragma: no cover
    """Protocol for objects that expose a `__locale_str__()` method."""

    def __locale_str__(self) -> locale_str:
        """Return the locale string for this object."""
        ...


def _build_l10n() -> dict[str, FluentLocalization]:
    """Build a [`FluentLocalization`][] instance for each allowed locale, with English as fallback.

    Returns:
        Mapping of locale name to its [`FluentLocalization`][].
    """
    # locales files are located in ../locales/{locale}/main.ftl
    locale_loader = FluentResourceLoader(str(Path(__file__).absolute().parent.parent / "locales" / "{locale}"))
    result: dict[str, FluentLocalization] = {}
    for locale in CONFIG.allowed_locales:
        fallbacks = [locale, "en"] if locale != "en" else [locale]
        result[locale] = FluentLocalization(fallbacks, ["main.ftl"], locale_loader)
    return result


_all_l10n: dict[str, FluentLocalization] = _build_l10n()


def supported_locales() -> frozenset[str]:
    """Return the set of locale codes currently loaded (mirrors CONFIG.allowed_locales).

    Returns:
        Frozenset of BCP-47 locale strings for which FTL bundles are available.
    """
    return frozenset(_all_l10n)


class Translator(app_commands.Translator):
    """Implements [`app_commands.Translator`][] using `FluentLocalization`."""

    def _translate(
        self,
        string: locale_str,
        locale: discord.Locale | str,
        context: app_commands.TranslationContextTypes | None = None,
    ) -> str | None:
        """Translate `string` to `locale` synchronously.

        When `locale` matches the default locale, returns the pre-rendered `string.message`
        immediately. For other locales the appropriate FTL bundle is selected and all kwargs
        are recursively resolved before calling `format_value`.

        Args:
            string: The locale string to translate (must have `"_string"` in `extras`).
            locale: Target locale — a [`discord.Locale`][] or BCP-47 string.
            context: Translation context (unused).

        Returns:
            Translated string, or `None` when `string` is not a Modmail FTL key.
        """
        if "_string" not in string.extras:
            return None  # Not Modmail's string

        l10n = _all_l10n[CONFIG.default_locale]

        locale_name = locale.value if isinstance(locale, discord.Locale) else locale
        if locale_name in _all_l10n:
            l10n = _all_l10n[locale_name]
        else:
            if "-" in locale_name:
                # If the locale is in the form of xx-YY (e.g., en-US),
                # check if the base locale (xx) is supported
                locale_name = locale_name.partition("-")[0]
                if locale_name in _all_l10n:
                    l10n = _all_l10n[locale_name]

        if l10n.locales == _all_l10n[CONFIG.default_locale].locales:
            return string.message  # Already translated by _()

        # Real message stored in .extras['_string']
        message: str = string.extras["_string"]

        # Convert all extras items to supported types
        for key, value in string.extras.items():
            if key == "_string":
                continue
            if hasattr(value, "__locale_str__"):
                string.extras[key] = self._translate(value.__locale_str__(), locale, context)
            elif isinstance(value, locale_str):
                string.extras[key] = self._translate(value, locale, context)
            elif isinstance(value, FluentTypes):
                string.extras[key] = value
            else:
                string.extras[key] = str(value)

        return l10n.format_value(message, string.extras)

    def translate_sync(
        self,
        string: locale_str,
        locale: discord.Locale | str,
        context: app_commands.TranslationContextTypes | None = None,
    ) -> str | None:
        """Translate `string` to `locale` synchronously.

        Public wrapper around [`_translate`][]. Use this from other modules; prefer
        [`Context.t`][] in command handlers.

        Args:
            string: The locale string to translate.
            locale: Target locale.
            context: Translation context (unused).

        Returns:
            Translated string, or `None` when not found.
        """
        return self._translate(string, locale, context)

    async def translate(
        self,
        string: locale_str,
        locale: discord.Locale | str,
        context: app_commands.TranslationContextTypes | None = None,
    ) -> str | None:
        """Translate a message using FluentLocalization.

        Required by the [`app_commands.Translator`][] abstract interface.

        Args:
            string: The locale string to translate.
            locale: Target locale.
            context: Translation context (unused).

        Returns:
            Translated string, or `None` when not found.
        """
        return self._translate(string, locale, context)


def _(string: str, /, **kwargs: FluentTypes | HasLocaleStr | locale_str) -> locale_str:
    """Mark `string` for translation and pre-render it in the default locale.

    Returns a [`locale_str`][] whose `.message` holds the default-locale rendering.
    The raw FTL key and all kwargs are stored in `.extras` for later re-rendering
    into other locales by [`Translator`][].

    Args:
        string: FTL message ID.
        **kwargs: FTL variables. Accepts [`FluentTypes`][], objects implementing
            `__locale_str__()`, or nested [`locale_str`][] instances.

    Returns:
        A [`locale_str`][] ready for use in embeds, messages, or slash command labels.

    Warns:
        UserWarning: If a kwarg value is not a supported Fluent type.
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

    default_translated_string = _all_l10n[CONFIG.default_locale].format_value(string, temp_kwargs)
    kwargs["_string"] = string
    return locale_str(default_translated_string, **kwargs)
