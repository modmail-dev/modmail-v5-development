"""Babel-based internationalization for Modmail.

Bundles are loaded by the config validator — see `Config._parse_allowed_locales`.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import babel.dates as _babel_dates
import babel.numbers as _babel_numbers
import discord
from babel import Locale as _BabelLocale
from babel.core import negotiate_locale
from babel.support import NullTranslations as _NullTranslations, Translations as _BabelTranslations
from discord import app_commands
from discord.app_commands import locale_str

from .config import config

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
LOCALES_ROOT = Path(__file__).resolve().parent / "locales"


class HasLocaleStr(Protocol):
    """Protocol for objects that expose a `__locale_str__()` method."""

    def __locale_str__(self) -> locale_str:
        """Return the locale string for this object."""
        ...


class Translator(app_commands.Translator):
    """Translation engine wrapping babel `.mo` files.

    All locale identifiers are BCP-47 strings (e.g. `"en-US"`, `"de-DE"`).
    [`load_bundles`][] must be called once before any translation is requested
    (driven by the config validator).

    Loaded bundles are cached at class level so every instance shares
    the same in-memory translation data.
    """

    _RESERVED = frozenset({"_string", "_escape", "_string_plural", "_count", "_context"})
    _PLACEHOLDER_RE = re.compile(r"\{\s*([a-zA-Z0-9_-]+)\s*\}")
    _DOMAIN = "messages"

    _bundles: dict[str, _NullTranslations] = {}
    _custom_bundle: _NullTranslations | None = None
    _custom_locale: str | None = None
    _fallback_locale: str = "en-US"
    _fallback_bundle: _NullTranslations | None = None

    async def translate(
        self,
        string: locale_str,
        locale: discord.Locale | str,
        context: app_commands.TranslationContextTypes | None = None,
    ) -> str | None:
        """discord.py `app_commands.Translator` entry point.

        Args:
            string: The `locale_str` to translate.
            locale: Target locale as a `discord.Locale` or BCP-47 string.
            context: Translation context type from discord.py.

        Returns:
            Translated string, or `None`.
        """
        return self.translate_sync(string, locale)

    @classmethod
    def load_bundles(cls, locales: tuple[str, ...]) -> None:
        """Load `.mo` files for the given *locales* from the locale directory.

        `"en-US"` is always loaded as the ultimate fallback. Call this
        once during configuration validation.

        Args:
            locales: BCP-47 locale strings to load.
        """
        from .locales import ensure_compiled

        ensure_compiled()

        if cls._fallback_bundle is None:
            cls._fallback_bundle = _BabelTranslations.load(
                LOCALES_ROOT, locales=[cls._fallback_locale], domain=cls._DOMAIN
            )
            cls._bundles[cls._fallback_locale] = cls._fallback_bundle

        for bcp47_locale in sorted(locales):
            if bcp47_locale == cls._fallback_locale:
                continue
            t = _BabelTranslations.load(LOCALES_ROOT, locales=[bcp47_locale], domain=cls._DOMAIN)
            t.add_fallback(cls._fallback_bundle)
            cls._bundles[bcp47_locale] = t

        cls.load_custom_bundle()
        logger.info("Loaded translation bundles for locales: %s", ", ".join(cls._bundles))

    @classmethod
    def load_custom_bundle(cls) -> None:
        """Load the custom translation bundle from a `*-custom` directory."""
        cls._custom_bundle = cls._custom_locale = None
        for child in LOCALES_ROOT.iterdir():
            if child.is_dir() and child.name.endswith("-custom"):
                mo = child / "LC_MESSAGES" / f"{cls._DOMAIN}.mo"
                if mo.is_file():
                    with mo.open("rb") as f:
                        cls._custom_bundle = _BabelTranslations(fp=f, domain=cls._DOMAIN)
                    cls._custom_locale = child.name.replace("-custom", "@custom")
                    logger.info("Loaded custom translations from %s", child.name)
                return

    @classmethod
    def _get_bundle(cls, locale: str) -> _NullTranslations:
        """Return the translation bundle most appropriate for *locale*.

        Uses `babel.core.negotiate_locale` to find the best match from
        the available `_bundles`, falling back to `config.default_locale`
        """
        available = list(cls._bundles)
        match = negotiate_locale([locale], available, sep="-")
        if match is not None:
            return cls._bundles[match]
        return cls._bundles[config.default_locale]

    @classmethod
    def format_template(cls, template: str, bcp47_locale: str, **kwargs: Any) -> str:
        """Substitute `{name}` placeholders using *kwargs*.

        * `{{` and `}}` escape literal braces.
        * `{ name }` is replaced by the value of *name*, where *name* is
          `[a-zA-Z0-9_-]+` (whitespace inside braces is ignored).
        * Missing keys produce the empty string.
        * Date, time, and number types are formatted locale-aware.
        * Unmatched or malformed `{...}` tokens are left as-is.

        Args:
            template: The template string with `{name}` placeholders.
            bcp47_locale: The target locale as a BCP-47 string.
            **kwargs: Values to substitute into the template.

        Returns:
            The rendered string.
        """
        locale = _BabelLocale.parse(bcp47_locale, sep="-")

        def _format_value(value: Any) -> str:
            """Format a substitution value for display.

            Args:
                value: The substitution value to format.

            Returns:
                The formatted string.
            """
            if value is None:
                return ""
            if isinstance(value, datetime):
                return _babel_dates.format_datetime(value, locale=locale)
            if isinstance(value, date):
                return _babel_dates.format_date(value, locale=locale)
            if isinstance(value, time):
                return _babel_dates.format_time(value, locale=locale)
            if isinstance(value, timedelta):
                return _babel_dates.format_timedelta(value, locale=locale)
            if isinstance(value, Decimal):
                return _babel_numbers.format_decimal(value, locale=locale)
            if isinstance(value, int | float) and not isinstance(value, bool):
                return _babel_numbers.format_decimal(value, locale=locale)
            return str(value)

        text = template.replace("{{", "\x00").replace("}}", "\x01")
        text = cls._PLACEHOLDER_RE.sub(lambda m: _format_value(kwargs.get(m.group(1))), text)
        return text.replace("\x00", "{").replace("\x01", "}")

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
        msgid: str | None = string.extras.get("_string")
        if msgid is None:
            return None

        if msgid.startswith("internal."):
            match msgid:
                case "internal.blank":
                    return ""
                case "internal.error":
                    return "!Error!"
                case _:
                    logger.warning("Unknown internal msgid %r", msgid)
                    return None

        ctx: str | None = string.extras.get("_context")
        plural_msgid: str | None = string.extras.get("_string_plural")
        count: int | None = string.extras.get("_count")
        escape = escape if escape is not None else bool(string.extras.get("_escape", True))
        bcp47_locale = locale.value if isinstance(locale, discord.Locale) else locale

        if count is not None and "count" not in override_kwargs:
            override_kwargs["count"] = count
        kwargs: dict[str, Any] = {k: v for k, v in string.extras.items() if k not in cls._RESERVED}
        kwargs |= override_kwargs

        for key, value in list(kwargs.items()):
            if hasattr(value, "__locale_str__"):
                value = value.__locale_str__()
            if isinstance(value, locale_str):
                if (new_v := cls.translate_sync(value, locale)) is not None:
                    value = new_v
                else:
                    logger.warning(
                        "Failed to translate nested locale_str for key %r (msgid %r, locale %r); "
                        "using pre-rendered message",
                        key,
                        value,
                        locale,
                    )
                    value = value.message
            if not isinstance(value, TranslationTypes):
                logger.warning("Formatting key %r has non-primitive value %r; coercing to string", key, value)
                value = str(value)
            if isinstance(value, str) and escape:
                value = discord.utils.escape_markdown(value)
            kwargs[key] = value

        def _lookup(bundle: _NullTranslations) -> str:
            """Look up a translation from a bundle using context/plural rules.

            Args:
                bundle: The translation bundle to query.

            Returns:
                The translated (but unformatted) string, or None.
            """
            if ctx and plural_msgid and count is not None:
                return bundle.unpgettext(ctx, msgid, plural_msgid, count)
            if ctx:
                return bundle.upgettext(ctx, msgid)
            if plural_msgid and count is not None:
                return bundle.ngettext(msgid, plural_msgid, count)
            return bundle.gettext(msgid)

        if cls._custom_bundle and cls._custom_locale:
            translated = _lookup(cls._custom_bundle)
            if translated != msgid and (not plural_msgid or translated != plural_msgid):
                return cls.format_template(translated, bcp47_locale=cls._custom_locale, **kwargs)

        translated = _lookup(cls._get_bundle(bcp47_locale))
        return cls.format_template(translated, bcp47_locale=bcp47_locale, **kwargs)

    @classmethod
    def gettext(cls, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
        """Mark *msgid* for translation and pre-render in the default locale.

        Args:
            msgid: The message ID to translate.
            escape: When True, escape Discord markdown in the result.
            **kwargs: Formatting values for `{placeholders}`.

        Returns:
            A `locale_str` whose `.message` holds the rendered string and
            `.extras` carries the msgid plus all kwargs for re-rendering.
        """
        if msgid.startswith("internal.") or cls._fallback_bundle is None:
            default_message = msgid
        else:
            default_message = cls._fallback_bundle.gettext(msgid)

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

        Args:
            msgid: The message ID to translate.
            n: The number for plural selection.
            escape: When True, escape Discord markdown in the result.
            **kwargs: Formatting values for `{placeholders}`.

        Returns:
            A `locale_str` with the pre-rendered plural form.
        """
        plural_msgid = msgid + ".plural"
        if msgid.startswith("internal.") or cls._fallback_bundle is None:
            default_message = msgid
        else:
            default_message = cls._fallback_bundle.ngettext(msgid, plural_msgid, n)

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

        Args:
            context: Translation context.
            msgid: The message ID to translate.
            escape: When True, escape Discord markdown in the result.
            **kwargs: Formatting values for `{placeholders}`.

        Returns:
            A `locale_str` with the pre-rendered contextual form.
        """
        if msgid.startswith("internal.") or cls._fallback_bundle is None:
            default_message = msgid
        else:
            default_message = cls._fallback_bundle.upgettext(context, msgid)

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

        Args:
            context: Translation context.
            msgid: The message ID to translate.
            n: The number for plural selection.
            escape: When True, escape Discord markdown in the result.
            **kwargs: Formatting values for `{placeholders}`.

        Returns:
            A `locale_str` with the pre-rendered contextual plural form.
        """
        plural_msgid = msgid + ".plural"
        if msgid.startswith("internal."):
            default_message = msgid
        else:
            default_message = cls._bundles[cls._fallback_locale].unpgettext(context, msgid, plural_msgid, n)

        kwargs["_context"] = context
        kwargs["_string"] = msgid
        kwargs["_string_plural"] = plural_msgid
        kwargs["_count"] = n
        kwargs["_escape"] = escape
        return locale_str(default_message, **kwargs)


def _(msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.gettext`.

    Args:
        msgid: The message ID to translate.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` pre-rendered in the default locale.
    """
    return Translator.gettext(msgid, escape=escape, **kwargs)


def _n(msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Underscore shorthand for `ngettext`.

    Args:
        msgid: The message ID to translate.
        n: The number for plural selection.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` with the pre-rendered plural form.
    """
    return Translator.ngettext(msgid, n, escape=escape, **kwargs)


def _c(context: str, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Underscore shorthand for `upgettext` / `cgettext`.

    Args:
        context: Translation context.
        msgid: The message ID to translate.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` with the pre-rendered contextual form.
    """
    return Translator.upgettext(context, msgid, escape=escape, **kwargs)


def _cn(context: str, msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Underscore shorthand for `unpgettext`.

    Args:
        context: Translation context.
        msgid: The message ID to translate.
        n: The number for plural selection.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` with the pre-rendered contextual plural form.
    """
    return Translator.unpgettext(context, msgid, n, escape=escape, **kwargs)


def gettext(msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Long-form alias for `_()` / `Translator.gettext`.

    Args:
        msgid: The message ID to translate.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` pre-rendered in the default locale.
    """
    return Translator.gettext(msgid, escape=escape, **kwargs)


def ngettext(msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.ngettext`.

    Args:
        msgid: The message ID to translate.
        n: The number for plural selection.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` with the pre-rendered plural form.
    """
    return Translator.ngettext(msgid, n, escape=escape, **kwargs)


def upgettext(context: str, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.upgettext`.

    Args:
        context: Translation context.
        msgid: The message ID to translate.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` with the pre-rendered contextual form.
    """
    return Translator.upgettext(context, msgid, escape=escape, **kwargs)


def cgettext(context: str, msgid: str, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Long-form alias for `upgettext` / `_c` / `Translator.upgettext`.

    Args:
        context: Translation context.
        msgid: The message ID to translate.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` with the pre-rendered contextual form.
    """
    return Translator.upgettext(context, msgid, escape=escape, **kwargs)


def unpgettext(context: str, msgid: str, n: int, /, *, escape: bool = True, **kwargs: object) -> locale_str:
    """Shorthand for `Translator.unpgettext`.

    Args:
        context: Translation context.
        msgid: The message ID to translate.
        n: The number for plural selection.
        escape: When True, escape Discord markdown in the result.
        **kwargs: Formatting values for `{placeholders}`.

    Returns:
        A `locale_str` with the pre-rendered contextual plural form.
    """
    return Translator.unpgettext(context, msgid, n, escape=escape, **kwargs)
