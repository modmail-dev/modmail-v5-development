"""Fluent-based translation services for Modmail.

Ephemeral responses use the user's locale; public responses use `CONFIG.default_locale`.
Use [`ephemeral_scope`][] to declare an interaction as ephemeral — [`ctx.t`][] and
[`Bot.send_message`][] resolve locale automatically from there.
"""

from __future__ import annotations

import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import discord
from discord import app_commands
from discord.app_commands import locale_str
from fluent.runtime import FluentLocalization, FluentResourceLoader

from .. import CONFIG

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = ["Translator", "_", "ephemeral_scope", "locale_for", "supported_locales", "using_ephemeral"]

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


_interaction_scope: ContextVar[dict[int, bool]] = ContextVar("modmail_interaction_scope")
"""Task-local scope dict mapping interaction IDs to their ephemeral flag.

Populated by [`ephemeral_scope`][]. Isolated per asyncio task via copy-on-write semantics.
"""


def locale_for(interaction: discord.Interaction[Any] | None) -> str:
    """Return the locale for `interaction`, or `CONFIG.default_locale` when unavailable.

    Args:
        interaction: The Discord interaction, or `None`.

    Returns:
        BCP-47 locale string.
    """
    if interaction is None or interaction.is_expired():
        return CONFIG.default_locale
    return str(interaction.locale)


def using_ephemeral(interaction: discord.Interaction[Any] | None) -> bool:
    """Return `True` if `interaction` was declared ephemeral via [`ephemeral_scope`][].

    Args:
        interaction: The Discord interaction to check, or `None`.

    Returns:
        `True` if [`ephemeral_scope`][] is active for this interaction.
    """
    if interaction is None or interaction.is_expired():
        return False
    return _interaction_scope.get({}).get(interaction.id, False)


@contextmanager
def ephemeral_scope(interaction: discord.Interaction[Any] | None) -> Generator[None]:
    """Mark `interaction`'s responses as ephemeral for the duration of the block.

    Within the block, [`using_ephemeral`][] returns `True` for this interaction, [`ctx.t`][]
    resolves to the user's locale, and sends default to ephemeral. Has no effect when
    `interaction` is `None` or expired.

    Note:
        Pass `interaction=interaction` to any view constructors inside this block so they
        capture the user's locale.

    Args:
        interaction: The interaction that will receive the ephemeral responses.

    Yields:
        Nothing.
    """
    if interaction is None or interaction.is_expired():
        yield
        return

    current = _interaction_scope.get({})
    token = _interaction_scope.set({**current, interaction.id: True})
    try:
        yield
    finally:
        _interaction_scope.reset(token)


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

        should_escape = bool(string.extras.get("_escape", True))

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
            if key in {"_string", "_escape"}:
                continue

            if hasattr(value, "__locale_str__"):
                value = value.__locale_str__()

            if isinstance(value, locale_str):
                string.extras[key] = self._translate(value, locale, context)
            elif isinstance(value, FluentTypes):
                if isinstance(value, str) and should_escape:
                    string.extras[key] = discord.utils.escape_markdown(value)
                else:
                    string.extras[key] = value
            else:
                converted = str(value)
                string.extras[key] = discord.utils.escape_markdown(converted) if should_escape else converted

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


def _(string: str, /, *, escape: bool = True, **kwargs: FluentTypes | HasLocaleStr | locale_str) -> locale_str:
    """Mark `string` for translation and pre-render it in the default locale.

    Returns a [`locale_str`][] whose `.message` holds the default-locale rendering.
    The raw FTL key and all kwargs are stored in `.extras` for later re-rendering
    into other locales by [`Translator`][].

    Args:
        string: FTL message ID.
        escape: When `True` (default), applies [`discord.utils.escape_markdown`][] to plain
            `str` kwargs before substitution. Pass `False` for intentional markdown in kwargs.
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
        if hasattr(value, "__locale_str__"):
            value = cast("locale_str", value.__locale_str__())  # pyright: ignore [reportUnknownMemberType, reportOptionalMemberAccess, reportAttributeAccessIssue]

        if isinstance(value, locale_str):
            temp_kwargs[key] = value.message
        elif isinstance(value, FluentTypes):
            if isinstance(value, str) and escape:
                temp_kwargs[key] = discord.utils.escape_markdown(value)
            else:
                temp_kwargs[key] = value
        else:
            warnings.warn(f"Unsupported type for translation: {value} ({type(value)})", stacklevel=2)
            converted = str(value)
            temp_kwargs[key] = discord.utils.escape_markdown(converted) if escape else converted

    default_translated_string = _all_l10n[CONFIG.default_locale].format_value(string, temp_kwargs)
    kwargs["_string"] = string
    kwargs["_escape"] = escape
    return locale_str(default_translated_string, **kwargs)
