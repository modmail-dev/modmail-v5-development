"""Access-level decorators and the [`PermissionCommandIndex`][] for command permission overrides."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, cast

from discord.app_commands import locale_str
from discord.ext import commands

from .. import CONFIG
from ..enum import RequiredAccessLevel
from .cog import LazyHybridCommand
from .translator import all_l10n

if TYPE_CHECKING:
    from .bot import Bot

type AnyCo = commands.Command[Any, Any, Any] | LazyHybridCommand[Any] | Callable[..., Coroutine[Any, Any, Any]]

__all__ = [
    "PermissionCommandIndex",
    "PermissionCommandView",
    "admin_only",
    "manager_only",
    "owner_only",
    "staff_only",
]

logger = logging.getLogger(__name__)


def _locale_candidates(locale: str) -> list[str]:
    """Return locale lookup candidates: full tag, language-only, then `CONFIG.default_locale`."""
    return list(dict.fromkeys([locale, locale.partition("-")[0], CONFIG.default_locale]))


def _set_access_level[T: AnyCo](func: T, access_level: RequiredAccessLevel) -> T:
    """Inject `__permission__` onto the command callback (or plain callable).

    Args:
        func: A hybrid command, lazy command, or plain callable.
        access_level: The access level to set.

    Returns:
        `func` unchanged (for decorator chaining).
    """
    # Lots of type ignore here because we are using function injection to set the access level.
    if isinstance(func, commands.Command | LazyHybridCommand):  # Inject into the command callback
        func.callback.__permission__ = access_level  # pyright: ignore [reportUnknownMemberType, reportFunctionMemberAccess]
    else:  # Inject into the function itself
        func.__permission__ = access_level  # pyright: ignore [reportFunctionMemberAccess]
    return func  # pyright: ignore [reportUnknownVariableType, reportReturnType]


def staff_only[T: AnyCo](func: T) -> T:
    """Require [`RequiredAccessLevel.staff`][] or above to invoke the command.

    Returns:
        `func` unchanged, for decorator chaining.
    """
    return _set_access_level(func, RequiredAccessLevel.staff)


def manager_only[T: AnyCo](func: T) -> T:
    """Require [`RequiredAccessLevel.manager`][] or above to invoke the command.

    Returns:
        `func` unchanged, for decorator chaining.
    """
    return _set_access_level(func, RequiredAccessLevel.manager)


def admin_only[T: AnyCo](func: T) -> T:
    """Require [`RequiredAccessLevel.admin`][] or above to invoke the command.

    Returns:
        `func` unchanged, for decorator chaining.
    """
    return _set_access_level(func, RequiredAccessLevel.admin)


def owner_only[T: AnyCo](func: T) -> T:
    """Restrict the command to bot owners only.

    Returns:
        `func` unchanged, for decorator chaining.
    """
    return _set_access_level(func, RequiredAccessLevel.owner)


class PermissionCommandView:
    """A locale-bound view over a [`PermissionCommandIndex`][].

    Obtained by calling the index with a locale: `index(locale)`. All methods
    on this view operate in that locale without needing it passed again.
    """

    def __init__(self, index: PermissionCommandIndex, locale: str) -> None:
        """Bind `index` to `locale`. Prefer calling the index directly: `index(locale)`."""
        self._index = index
        self._locale = locale

    @property
    def keys(self) -> frozenset[str]:
        """All canonical command keys currently known to the index."""
        return self._index.keys

    @staticmethod
    def sanitize(name: str) -> str:
        """Normalize raw user input into the form accepted by [`resolve`][] and [`label`][].

        Args:
            name: Raw user input.

        Returns:
            Lowercased, whitespace-stripped name with underscores replaced by spaces,
            asterisks replaced by `"+"`, and at most one trailing `"+"` wildcard.
        """
        return PermissionCommandIndex.sanitize(name)

    def label(self, canonical_key: str) -> str:
        """Return the display name for `canonical_key` in `locale`.

        Args:
            canonical_key: Canonical command key.

        Returns:
            Translated display name, or `canonical_key` when the command is not found.
        """
        return self._index.label(canonical_key, self._locale)

    def resolve(self, raw: str, *, allow_raw_key: bool = False) -> str | None:
        """Resolve a user-typed command name to its canonical key.

        Args:
            raw: Raw user input (sanitized internally).
            allow_raw_key: When `True`, also accept a bare canonical key as input,
                useful for deleting orphaned overrides.

        Returns:
            The canonical key (with `"+"` restored if present), or `None` when not found.
        """
        return self._index.resolve(raw, self._locale, allow_raw_key=allow_raw_key)


class PermissionCommandIndex:
    """Bidirectional index between canonical command keys and their locale-specific display names.

    Built once at startup via [`from_bot`][]. Call the index with a locale string to
    get a [`PermissionCommandView`][] that omits the locale from every subsequent call:

    ```python
    view = ctx.bot.permission_command_index(locale)
    view.label("profile edit")  # translated display name
    view.resolve("profil ändern")  # → "profile_edit"
    ```

    Note:
        Wildcard suffixes (`"reply+"`) are never stored in the index; both `label`
        and `resolve` strip and re-apply `"+"` transparently.
    """

    def __init__(self, display: dict[str, dict[str, str]], input_map: dict[tuple[str, str], str]) -> None:
        """Initialize the index with pre-built lookup tables.

        Args:
            display: Mapping from canonical key to per-locale display names.
            input_map: Mapping from `(locale, casefolded_name)` to canonical key.
        """
        self._display = display
        self._input_map = input_map
        self.keys = frozenset(display.keys())
        """All canonical command keys currently known to the index (base names, no wildcard suffix)."""

    @staticmethod
    def sanitize(name: str) -> str:
        """Normalize raw user input into the form accepted by [`resolve`][] and [`label`][].

        Args:
            name: Raw user input.

        Returns:
            Lowercased, whitespace-stripped name with underscores replaced by spaces,
            asterisks replaced by `"+"`, and at most one trailing `"+"` wildcard.
        """
        name = name.casefold().strip().replace("_", " ").replace("*", "+")
        base, sep, _ = name.partition("+")
        return base.strip() + sep

    def __call__(self, locale: str) -> PermissionCommandView:
        """Return a locale-bound [`PermissionCommandView`][] for this index.

        Args:
            locale: BCP-47 locale code of the user.

        Returns:
            A view whose `label` and `resolve` methods operate in `locale`.
        """
        return PermissionCommandView(self, locale)

    @classmethod
    def from_bot(cls, bot: Bot) -> PermissionCommandIndex:
        """Build the index from the bot's currently loaded commands.

        Args:
            bot: The running bot instance.

        Returns:
            A fully populated [`PermissionCommandIndex`][].
        """

        def _qualified_name(cmd: commands.Command[Any, Any, Any], locale: str) -> str:
            ancestors: list[commands.Command[Any, Any, Any] | commands.Group[Any, Any, Any]] = []
            node: commands.Command[Any, Any, Any] | commands.Group[Any, Any, Any] | None = cmd
            while node is not None:
                ancestors.insert(0, node)
                node = cast("commands.Group[Any, Any, Any] | None", node.parent)
            return " ".join(
                bot.translate(name, ctx_or_locale=locale)
                if isinstance(name := getattr(a, "_locale_name", a.name), locale_str) and "_string" in name.extras
                else str(a.name)
                for a in ancestors
            )

        display: dict[str, dict[str, str]] = {}
        input_map: dict[tuple[str, str], str] = {}

        for cmd in bot.walk_commands():
            canonical = bot.get_canonical_command_name(cmd)
            locale_map: dict[str, str] = {}
            for loc in all_l10n:
                localized = _qualified_name(cmd, loc)
                locale_map[loc] = localized
                # setdefault so the first registered command wins on name collisions
                input_map.setdefault((loc, localized.casefold()), canonical)
            display[canonical] = locale_map

        return cls(display, input_map)

    def label(self, canonical_key: str, locale: str) -> str:
        """Return the display name for `canonical_key` in `locale`.

        Args:
            canonical_key: Canonical command key.
            locale: BCP-47 locale code of the user. Falls back to `CONFIG.default_locale`
                if no translation is found.

        Returns:
            Translated display name, or `canonical_key` when the command is not found.
        """
        suffix = "+" if canonical_key.endswith("+") else ""
        base = canonical_key.removesuffix("+")

        locale_map = self._display.get(base)
        if locale_map is None:
            return canonical_key
        for loc in _locale_candidates(locale):
            if name := locale_map.get(loc):
                return name + suffix
        return canonical_key

    def resolve(self, raw: str, locale: str, *, allow_raw_key: bool = False) -> str | None:
        """Resolve a user-typed command name to its canonical key.

        Args:
            raw: Raw user input (sanitized internally).
            locale: BCP-47 locale code of the submitting user. Falls back to
                `CONFIG.default_locale` if no match is found.
            allow_raw_key: When `True`, also accept a bare canonical key as input,
                useful for deleting orphaned overrides.

        Returns:
            The canonical key (with `"+"` restored if present), or `None` when not found.
        """
        raw = PermissionCommandIndex.sanitize(raw)
        suffix = "+" if raw.endswith("+") else ""
        base = raw.removesuffix("+")

        key = base.casefold()
        for loc in _locale_candidates(locale):
            if result := self._input_map.get((loc, key)):
                return result + suffix
        if allow_raw_key and base in self.keys:
            return base + suffix
        return None
