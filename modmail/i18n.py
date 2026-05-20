"""Babel-based internationalization for Modmail.

Bundles are loaded by the config validator — see `Config._parse_allowed_locales`.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

import babel.dates as _babel_dates
import babel.numbers as _babel_numbers
import discord
from babel import Locale as _BabelLocale
from babel.core import negotiate_locale
from babel.support import NullTranslations as _NullTranslations, Translations as _BabelTranslations
from discord import app_commands
from discord.app_commands import locale_str

if TYPE_CHECKING:
    from typing import Any

__all__ = [
    "Translator",
    "_",
    "_c",
    "_cn",
    "_n",
    "cgettext",
    "gettext",
    "ngettext",
    "unpgettext",
    "upgettext",
]

logger = logging.getLogger(__name__)

TranslationTypes = str | int | float | Decimal | datetime | date | time | timedelta | None


class HasLocaleStr(Protocol):
    """Protocol for objects that expose a `__locale_str__()` method."""

    def __locale_str__(self) -> locale_str:
        """Return the locale string for this object."""
        ...


class Translator(app_commands.Translator):
    """Translation engine wrapping babel `.mo` files.

    All locale identifiers are BCP-47 strings (e.g. ``"en-US"``, ``"de-DE"``).
    [`load_bundles`][] must be called once before any translation is requested
    (driven by the config validator).

    Loaded bundles are cached at class level so every instance shares
    the same in-memory translation data.
    """

    _RESERVED = frozenset({"_string", "_escape", "_string_plural", "_count", "_context"})
    _PLACEHOLDER_RE = re.compile(r"\{\s*([a-zA-Z0-9_-]+)\s*\}")

    _bundles: dict[str, _NullTranslations] = {}
    _fallback_locale: str = "en-US"

    async def translate(
        self,
        string: locale_str,
        locale: discord.Locale | str,
        context: app_commands.TranslationContextTypes | None = None,
    ) -> str | None:
        """discord.py `app_commands.Translator` entry point.

        Returns:
            Translated string, or `None`.
        """
        return self.translate_sync(string, locale)

    @classmethod
    def load_bundles(cls, dir_path: str, locales: list[str], domain: str) -> None:
        """Load `.mo` files from *dir_path* for every locale in *locales*.

        ``"en-US"`` is always loaded as the ultimate fallback.  Call this
        once during configuration validation.

        Args:
            dir_path: Absolute path to the ``locales/`` directory.
            locales: BCP-47 locale strings to load.
            domain: The `.po` / `.mo` domain name (e.g. ``"messages"``).
        """
        en_bundle = _BabelTranslations.load(dir_path, locales=[cls._fallback_locale], domain=domain)

        for bcp47_locale in sorted(locales):
            if bcp47_locale == cls._fallback_locale:
                cls._bundles[cls._fallback_locale] = en_bundle
                continue
            t = _BabelTranslations.load(dir_path, locales=[bcp47_locale], domain=domain)
            t.add_fallback(en_bundle)
            cls._bundles[bcp47_locale] = t

    @classmethod
    def _get_bundle(cls, locale: str) -> _NullTranslations:
        """Return the translation bundle most appropriate for *locale*.

        Uses `babel.core.negotiate_locale` to find the best match from
        the available ``_bundles``, falling back to ``cls._fallback_locale``
        (``"en-US"``) when none matches.
        """
        available = list(cls._bundles)
        match = negotiate_locale([locale], available, sep="-")
        if match is not None:
            return cls._bundles[match]

        from . import CONFIG

        return cls._bundles[CONFIG.default_locale]

    @staticmethod
    def _format_value(value: object, locale: str) -> str:
        """Format a single substitution value for the target locale.

        Returns:
            The formatted string.
        """
        loc = _BabelLocale.parse(locale, sep="-")
        if value is None:
            return ""
        if isinstance(value, datetime):
            return _babel_dates.format_datetime(value, locale=loc)
        if isinstance(value, date):
            return _babel_dates.format_date(value, locale=loc)
        if isinstance(value, time):
            return _babel_dates.format_time(value, locale=loc)
        if isinstance(value, timedelta):
            return _babel_dates.format_timedelta(value, locale=loc)
        if isinstance(value, Decimal):
            return _babel_numbers.format_decimal(value, locale=loc)
        if isinstance(value, int) and not isinstance(value, bool):
            return _babel_numbers.format_number(value, locale=loc)
        if isinstance(value, float):
            return _babel_numbers.format_decimal(value, locale=loc)
        return str(value)

    @classmethod
    def format_template(cls, template: str, locale: str, **kwargs: object) -> str:
        """Substitute `{name}` placeholders using *kwargs*.

        * `{{` and `}}` escape literal braces.
        * ``{ name }`` is replaced by the value of *name*, where *name* is
          ``[a-zA-Z0-9_-]+`` (whitespace inside braces is ignored).
        * Missing keys produce the empty string.
        * Date, time, and number types are formatted locale-aware.
        * Unmatched or malformed ``{...}`` tokens are left as-is.

        Returns:
            The rendered string.
        """
        text = template.replace("{{", "\x00").replace("}}", "\x01")
        text = cls._PLACEHOLDER_RE.sub(lambda m: cls._format_value(kwargs.get(m.group(1)), locale), text)
        return text.replace("\x00", "{").replace("\x01", "}")

    @classmethod
    def _resolve_kwargs(
        cls, kwargs: dict[str, object], locale: str, escape: bool, *, recursive: bool = False
    ) -> dict[str, object]:
        """Resolve kwargs for formatting.

        Calls `__locale_str__()` on enums, recursively translates nested
        `locale_str` values (when *recursive*), and escapes markdown.

        Returns:
            Resolved kwargs ready for `format_template`.
        """
        resolved: dict[str, object] = {}
        for key, value in kwargs.items():
            if key in cls._RESERVED:
                continue
            v: Any = value

            if hasattr(v, "__locale_str__"):
                v = v.__locale_str__()

            if isinstance(v, locale_str):
                new_v = cls.translate_sync(v, locale) if recursive else v.message
                if new_v is None:
                    logger.warning(
                        "Failed to translate nested locale_str for key %r"
                        "(msgid %r, locale %r); using pre-rendered message",
                        key,
                        v,
                        locale,
                    )
                    v = v.message
                else:
                    v = new_v

            if isinstance(v, str) and escape:
                v = discord.utils.escape_markdown(v)

            if isinstance(v, TranslationTypes):
                resolved[key] = v
            else:
                logger.warning("Formatting key %r has non-primitive value %r; coercing to string", key, v)
                v = str(v)
                if escape:
                    v = discord.utils.escape_markdown(v)
                resolved[key] = v
        return resolved

    @classmethod
    def translate_sync(
        cls,
        string: locale_str,
        locale: discord.Locale | str,
        *,
        escape: bool | None = None,
        **override_kwargs: object,
    ) -> str | None:
        """Translate a `locale_str` to *locale*.

        Args:
            string: The `locale_str` to translate.
            locale: Target locale — `discord.Locale` or BCP-47 string.
            escape: Override the construction-time escape flag.
            **override_kwargs: Format kwargs merged on top of construction kwargs.

        Returns:
            Translated string, or `None` when not a Modmail key.
        """
        if "_string" not in string.extras:
            return None

        if isinstance(locale, discord.Locale):
            bcp47_locale = locale.value
        else:
            bcp47_locale = locale

        bundle = cls._get_bundle(bcp47_locale)
        should_escape = escape if escape is not None else bool(string.extras.get("_escape", True))

        if "_count" in string.extras and "count" not in override_kwargs and "count" not in string.extras:
            override_kwargs["count"] = string.extras["_count"]

        msgid: str = string.extras["_string"]

        if msgid.startswith("internal."):
            if msgid == "internal.blank":
                return ""
            if msgid == "internal.error":
                return "!Error!"
            logger.warning("Unknown internal msgid %r", msgid)
            return None

        if "_context" in string.extras and "_string_plural" in string.extras and "_count" in string.extras:
            translated = bundle.unpgettext(
                string.extras["_context"],
                msgid,
                string.extras["_string_plural"],
                string.extras["_count"],
            )
        elif "_context" in string.extras:
            translated = bundle.upgettext(string.extras["_context"], msgid)
        elif "_string_plural" in string.extras and "_count" in string.extras:
            translated = bundle.ngettext(msgid, string.extras["_string_plural"], string.extras["_count"])
        else:
            translated = bundle.gettext(msgid)

        extras_kwargs = {k: v for k, v in string.extras.items() if k not in cls._RESERVED}
        kwargs = {**extras_kwargs, **override_kwargs}

        resolved = cls._resolve_kwargs(kwargs, bcp47_locale, should_escape, recursive=True)
        return cls.format_template(str(translated), locale=bcp47_locale, **resolved)

    @classmethod
    def gettext(cls, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
        """Mark *msgid* for translation and pre-render in the default locale.

        Returns:
            A `locale_str` whose `.message` holds the rendered string and
            `.extras` carries the msgid plus all kwargs for re-rendering.
        """
        if msgid.startswith("internal."):
            if msgid == "internal.blank":
                return locale_str("", _string=msgid, _escape=escape)
            if msgid == "internal.error":
                return locale_str("!Error!", _string=msgid, _escape=escape)
            logger.warning("Unknown internal msgid %r", msgid)
            return locale_str(msgid, _string=msgid, _escape=escape)

        default_message = cls._bundles[cls._fallback_locale].gettext(msgid)

        kwargs["_string"] = msgid
        kwargs["_escape"] = escape
        return locale_str(default_message, **kwargs)

    @classmethod
    def ngettext(cls, msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
        """Plural-aware translation.

        Selects the correct plural form for *n* via the locale's
        `Plural-Forms` rule.  The plural msgid is `{msgid}.plural` by
        convention.  A `count` kwarg is auto-injected as *n* unless
        already present.

        Returns:
            A `locale_str` with the pre-rendered plural form.
        """
        plural_msgid = msgid + ".plural"
        default_message = cls._bundles[cls._fallback_locale].ngettext(msgid, plural_msgid, n)

        kwargs["_string"] = msgid
        kwargs["_string_plural"] = plural_msgid
        kwargs["_count"] = n
        kwargs["_escape"] = escape
        return locale_str(default_message, **kwargs)

    @classmethod
    def upgettext(cls, context: str, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
        """Context-aware translation (gender, disambiguation).

        Uses `upgettext` / `msgctxt` to distinguish strings that share
        a msgid but differ by *context*.

        Returns:
            A `locale_str` with the pre-rendered contextual form.
        """
        default_message = cls._bundles[cls._fallback_locale].upgettext(context, msgid)

        kwargs["_context"] = context
        kwargs["_string"] = msgid
        kwargs["_escape"] = escape
        return locale_str(default_message, **kwargs)

    @classmethod
    def unpgettext(
        cls, context: str, msgid: str, n: int, /, *, escape: bool = True, **kwargs: object
    ) -> locale_str:
        """Context-aware plural translation.

        Combines `upgettext` (context) with `ngettext` (plural).  Uses
        `unpgettext` / `msgctxt` + plural forms.

        Returns:
            A `locale_str` with the pre-rendered contextual plural form.
        """
        plural_msgid = msgid + ".plural"
        default_message = cls._bundles[cls._fallback_locale].unpgettext(context, msgid, plural_msgid, n)

        kwargs["_context"] = context
        kwargs["_string"] = msgid
        kwargs["_string_plural"] = plural_msgid
        kwargs["_count"] = n
        kwargs["_escape"] = escape
        return locale_str(default_message, **kwargs)


def _(msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.gettext`.

    Returns:
        A `locale_str` pre-rendered in the default locale.
    """
    return Translator.gettext(msgid, escape=escape, **kwargs)


def _n(msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Underscore shorthand for `ngettext`.

    Returns:
        A `locale_str` with the pre-rendered plural form.
    """
    return Translator.ngettext(msgid, n, escape=escape, **kwargs)


def _c(context: str, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Underscore shorthand for `upgettext` / `cgettext`.

    Returns:
        A `locale_str` with the pre-rendered contextual form.
    """
    return Translator.upgettext(context, msgid, escape=escape, **kwargs)


def _cn(context: str, msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Underscore shorthand for `unpgettext`.

    Returns:
        A `locale_str` with the pre-rendered contextual plural form.
    """
    return Translator.unpgettext(context, msgid, n, escape=escape, **kwargs)


def gettext(msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Long-form alias for `_()` / `Translator.gettext`.

    Returns:
        A `locale_str` pre-rendered in the default locale.
    """
    return Translator.gettext(msgid, escape=escape, **kwargs)


def ngettext(msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.ngettext`.

    Returns:
        A `locale_str` with the pre-rendered plural form.
    """
    return Translator.ngettext(msgid, n, escape=escape, **kwargs)


def upgettext(context: str, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.upgettext`.

    Returns:
        A `locale_str` with the pre-rendered contextual form.
    """
    return Translator.upgettext(context, msgid, escape=escape, **kwargs)


def cgettext(context: str, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Long-form alias for `upgettext` / `_c` / `Translator.upgettext`.

    Returns:
        A `locale_str` with the pre-rendered contextual form.
    """
    return Translator.upgettext(context, msgid, escape=escape, **kwargs)


def unpgettext(context: str, msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.unpgettext`.

    Returns:
        A `locale_str` with the pre-rendered contextual plural form.
    """
    return Translator.unpgettext(context, msgid, n, escape=escape, **kwargs)
