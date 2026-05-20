"""Locale resolution helpers for Modmail.

Provides `locale_for` to resolve a Discord interaction's locale against
the configured allowed locales.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from babel.core import negotiate_locale

from .. import CONFIG

if TYPE_CHECKING:
    import discord

__all__ = [
    "locale_for",
]


def locale_for(interaction: discord.Interaction | None) -> str:
    """Return the locale for `interaction`, or `CONFIG.default_locale`.

    The locale is validated against `CONFIG.allowed_locales` via
    `negotiate_locale`; unmatched locales fall back to
    `CONFIG.default_locale`.

    Args:
        interaction: The Discord interaction, or `None`.

    Returns:
        BCP-47 locale string.
    """
    if interaction is None or interaction.is_expired():
        return CONFIG.default_locale
    match = negotiate_locale([interaction.locale.value.replace("_", "-")], list(CONFIG.allowed_locales), sep="-")
    return match if match is not None else CONFIG.default_locale
