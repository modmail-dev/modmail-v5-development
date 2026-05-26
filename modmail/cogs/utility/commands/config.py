"""Config management commands for the Modmail bot.

Provides the `/config` command group (owner-only) for viewing and editing bot
configuration at runtime. Changes are written to disk immediately and take
effect after a restart.
"""

from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass
from types import NoneType
from typing import TYPE_CHECKING, Any, Protocol, cast, get_origin

import discord
import pydantic
from lark import Lark, Token as LarkToken, Tree, UnexpectedInput
from pydantic import BaseModel, SecretStr

from modmail.config import (
    BatchOp,
    BatchOps,
    Config,
    ConfigKeyEntry,
    ConfigStore,
    MutOp,
    SetOp,
    UnsetOp,
    get_store,
)
from modmail.core import Context, PaginatedLayoutView, ParamInfo, bot_group, ephemeral_scope, owner_only, wrap
from modmail.errors import ConfigUpdateError
from modmail.i18n import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .. import Utility

logger = logging.getLogger(__name__)

__all__ = ["config_command"]


_LARK_GRAMMAR = r"""
    %ignore /\s+/
    start: token+
    token: sign (dict_entry | body)
    dict_entry: body "=" body
    sign: "+" | "-"
    body: QUOTED_STRING | UNQUOTED
    QUOTED_STRING: /"([^"\\]|\\.)*"/
    UNQUOTED: /[^\s"=](\\.|[^\s"=])*/
"""


class _Parser(Protocol):
    """Protocol to work around lark's incomplete type stubs."""

    def parse(
        self,
        text: str,
        start: str | None = None,
        on_error: Callable[[UnexpectedInput], bool] | None = None,
    ) -> Tree[LarkToken]: ...


# Type hint in lark is broken, needs to be cast to a Protocol to be usable
_TOKENIZER: _Parser = Lark(_LARK_GRAMMAR, parser="lalr", keep_all_tokens=True)


@dataclass
class _Token:
    """A single syntactically parsed token from a batch expression.

    The parser is purely syntax-driven: `key=value` always produces a
    dict-style token; bare `value` (no `=`) always produces a simple
    token. Field-type validation happens downstream.

    Attributes:
        sign: `+` (add) or `-` (remove).
        body: The full token body (includes `=val` for dict entries).
        dict_key: For dict-style tokens (syntax `key=val`), the key
            part; `None` for simple tokens.
        dict_value: For dict-style tokens (syntax `key=val`), the
            value part; `None` for simple tokens.
    """

    sign: str
    body: str
    dict_key: str | None = None
    dict_value: str | None = None


def _tokenize_batch_ops(text: str) -> list[_Token]:
    r"""Split a batch expression (`+key=val -other`) into structured tokens.

    Uses lark for multi-token parsing. `%ignore /\s+/` strips whitespace
    at the lexer level. `find_data("token")` finds all token sub-nodes.

    Falls back to single-token mode when multi-token parsing fails
    (e.g. unquoted multi-word values like `+some text`).

    Returns:
        A list of `_Token` instances.

    Raises:
        ConfigUpdateError: Content before the first `+`/`-`, stray
            characters, or unterminated quotes.
    """
    text = text.strip()
    if not text:
        raise ConfigUpdateError("parse", "Batch expression is empty")
    if text[0] not in "+-":
        raise ConfigUpdateError("parse", f"Batch expression must start with '+' or '-', got {text[0]!r}")

    def _sanitize(raw: str) -> str:
        """Strip outer quotes and resolve backslash escapes.

        If `raw` is a quoted string (`"..."`), remove the quotes and replace
        escape sequences with their literal values. Otherwise, return the
        string unchanged.

        Returns:
            The unquoted / unescaped string.
        """
        quotes_limit = 2
        if len(raw) >= quotes_limit and raw.startswith('"') and raw.endswith('"'):
            inner = raw[1:-1]
            out: list[str] = []
            i = 0
            while i < len(inner):
                if inner[i] == "\\" and i + 1 < len(inner):
                    out.append(inner[i + 1])
                    i += 2
                else:
                    out.append(inner[i])
                    i += 1
            return "".join(out)
        return raw

    tokens: list[_Token] = []

    try:
        tree = _TOKENIZER.parse(text)
        # find_data recurses depth-first and yields every node.
        for node in tree.find_data("token"):
            # sign is always a direct child of token: Tree("sign", [Token("+")])
            sign_node = next(node.find_data("sign"), None)
            if sign_node is None:
                raise ConfigUpdateError("internal", "Internal parser error: token node missing sign")

            sign = next((str(c) for c in sign_node.children if isinstance(c, LarkToken)), "")
            if not sign:
                raise ConfigUpdateError("internal", "Internal parser error: sign node has no token child")

            # dict_entry is present for key=value syntax, absent for simple +val.
            dict_entry_node = next(node.find_data("dict_entry"), None)
            if dict_entry_node is not None:
                # dict_entry holds exactly two body subtrees (key and value).
                bodies = tuple(dict_entry_node.find_data("body"))
                body_length = 2
                if len(bodies) != body_length:
                    raise ConfigUpdateError(
                        "internal",
                        "Internal parser error: dict_entry node does not have exactly two body children",
                    )
                key = _sanitize(next((str(c) for c in bodies[0].children if isinstance(c, LarkToken)), ""))
                val = _sanitize(next((str(c) for c in bodies[1].children if isinstance(c, LarkToken)), ""))
                tokens.append(_Token(sign=sign, body=f"{key}={val}", dict_key=key, dict_value=val))
                continue

            # No dict_entry -- either a simple body token (+val) or bare sign (+).
            body_node = next(node.find_data("body"), None)
            if body_node is not None:
                body = _sanitize(next((str(c) for c in body_node.children if isinstance(c, LarkToken)), ""))
                tokens.append(_Token(sign=sign, body=body))
                continue
            raise ConfigUpdateError("internal", "Internal parser error: token node missing body")

        if tokens:
            return tokens

    except UnexpectedInput:
        pass

    body = text[1:].lstrip()

    if re.search(r"\s[+-]", body):
        raise ConfigUpdateError(
            "parse", f'Invalid batch expression: {text!r}. Use quotes for multi-word values: +"{body}"'
        )

    if (eq_count := len(re.findall(r"(?<!\\)=", body))) > 1:
        raise ConfigUpdateError(
            "parse", f"Invalid batch expression: {text!r}. Multiple '=' not allowed in a single value."
        )

    if eq_count == 1:
        match = cast("re.Match[str]", re.search(r"(?<!\\)=", body))
        key = _sanitize(body[: match.start()])
        val = _sanitize(body[match.end() :])
        if not key:
            raise ConfigUpdateError("parse", f"Invalid batch expression: {text!r}. Dict key is empty.")
        if not val:
            raise ConfigUpdateError("parse", f"Invalid batch expression: {text!r}. Dict value is empty.")
        return [_Token(sign=text[0], body=f"{key}={val}", dict_key=key, dict_value=val)]

    return [_Token(sign=text[0], body=_sanitize(body))]


def _parse_batch(value_str: str, typ: object) -> BatchOp:
    """Parse a batch expression into add/remove operations.

    `key=value` produces dict entries (`ADD_DICT` / `REMOVE_DICT`); bare
    `value` produces simple add/remove.  Type mismatches between tokens and
    the field (e.g. `+key=value` on a list) raise `ConfigUpdateError`.

    Args:
        value_str: The raw batch expression (e.g. `'+a -b +"c d"'`).
        typ: The field's type annotation.

    Returns:
        A `BatchOp` ready for `ConfigStore.update()`.

    Raises:
        ConfigUpdateError: On malformed tokens, type mismatches, or
            invalid syntax.
    """
    # Origin[Args] is used for generics like list[int], dict[str, int]
    origin = get_origin(typ)
    tokens = _tokenize_batch_ops(value_str)

    ops: BatchOps = []
    for t in tokens:
        if t.dict_key is not None and t.dict_value is not None:
            if origin is not dict:
                raise ConfigUpdateError(
                    "parse",
                    f'Cannot use key=value syntax on a {typ!r} field; use quoting for literal =: +"{t.body}"',
                )
            if t.sign == "+":
                ops.append((MutOp.ADD_DICT, t.dict_key, t.dict_value))
            else:
                ops.append((MutOp.REMOVE_DICT, t.dict_key))

        elif origin is dict:
            if t.sign == "+":
                raise ConfigUpdateError(
                    "parse",
                    f"Cannot use non-key=value syntax on a {typ!r} field; "
                    "use '+' with '=' separator to set a key-value pair",
                )
            ops.append((MutOp.REMOVE_DICT, t.body))
        elif t.sign == "+":
            ops.append((MutOp.ADD, t.body))
        else:
            ops.append((MutOp.REMOVE, t.body))
    return BatchOp(items=ops)


def _parse_scalar(value_str: str) -> SetOp:
    """Parse a raw value string as TOML, falling back to plain string.

    TOML inline syntax gives properly typed values (`true` -> `True`,
    `42` -> `42`, `[1, 2, 3]` -> `[1, 2, 3]`). If TOML rejects the string
    (bare words like `hello`, special chars like `!`) the raw string is
    stored as-is and Pydantic validates later via `Config(**new_raw)`.

    Args:
        value_str: Stripped user string.

    Returns:
        A `SetOp` with the parsed value.
    """
    if not value_str:
        return SetOp(value="")
    try:
        parsed = tomllib.loads(f"_ = {value_str}")
        return SetOp(value=parsed["_"])
    except tomllib.TOMLDecodeError:
        logger.debug("TOML parse failed -- fallback to raw string for %r", value_str)
    except KeyError:
        logger.warning("TOML parsed but key '_' missing for %r", value_str)
    return SetOp(value=value_str)


def _parse(path: str, v: str) -> SetOp | BatchOp:
    """Parse a config value string into a `SetOp` or `BatchOp`.

    Routing logic:

    1. Strip the value. Empty string -> `SetOp(value="")`.
    2. If the value starts with `+`/`-`, it is treated as a batch
       expression. The field must be a supported collection
       (set/list/frozenset/dict). Invalid syntax raises
       `ConfigUpdateError`.
    3. Otherwise, treat the value as a scalar: try TOML, fall back to
       raw string (`_try_parse_scalar`).

    `_apply_and_commit` always finishes with `Config(**new_raw)`, so
    Pydantic validates and coerces the final value regardless of which path
    was taken.

    Args:
        path: Dotted config key path (`"bot.prefix"`).
        v: Raw string from the user.

    Returns:
        A `SetOp` or `BatchOp` for `ConfigStore.update()`.

    Raises:
        ConfigUpdateError: If the value starts with `+`/`-` but the
            field does not support batch operations, or the batch syntax
            is invalid.
    """
    v = v.strip()
    if not v:
        return SetOp(value="")

    def _resolve_type() -> object:
        """Walk a dotted config path through the Config model tree.

        Each key before the last must name a `BaseModel` field so we can keep
        descending. The last key's annotation is returned.

        Returns `str` as a safe fallback on any failure: missing key,
        non-BaseModel mid-path, or empty path.

        Returns:
            The type annotation for the field, or `str`.
        """
        if not path:
            return str
        keys = path.split(".")
        model_cls: object = Config
        for i, k in enumerate(keys):
            if not isinstance(model_cls, type) or not issubclass(model_cls, BaseModel):
                logger.debug("Type resolution failed at %r -- not a BaseModel", k)
                return str
            field_info = model_cls.model_fields.get(k)
            if field_info is None:
                logger.debug("Field %r not found in %s", k, model_cls.__name__)
                return str
            if i == len(keys) - 1:
                return field_info.annotation
            model_cls = field_info.annotation
        return str

    typ = _resolve_type()

    if v.startswith(("+", "-")):
        if get_origin(typ) not in {set, list, tuple, frozenset, dict}:
            raise ConfigUpdateError("parse", "Batch operations (+/-) are not supported for this field type")
        return _parse_batch(v, typ)
    return _parse_scalar(v)


def _get_nested(obj: object, key: str) -> object:
    """Walk `key` into a nested model by attribute access.

    Args:
        obj: The starting model or dict.
        key: Attribute name to traverse.

    Returns:
        The value at the nested path.

    Raises:
        AttributeError: If any key is invalid or doesn't exist in `obj`.
    """
    for k in key.split("."):
        obj = getattr(obj, k)
    return obj


class ConfigShowView(PaginatedLayoutView[ConfigKeyEntry, dict[Any, Any]]):
    """Paginated config browser with list and single-key detail views.

    Two display modes:
    - List view: paginated key list with select dropdown and prev/next
      navigation.
    - Detail view: single key with type, description, value, and set hint.
    """

    def __init__(
        self,
        ctx: Context,
        entries: list[ConfigKeyEntry],
        model: Config,
        *,
        initial_key: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        """Build the view, starting on the list or a specific key detail.

        Args:
            ctx: The invoking command context.
            entries: Key entries to browse.
            model: The live config model used to resolve values.
            initial_key: Jump directly to this key's detail view.
            timeout: Seconds before the view stops accepting interactions.
        """
        super().__init__(ctx.bot, ctx.author, interaction=ctx.interaction, timeout=timeout)
        self._items = entries
        self._model = model
        if initial_key:
            self._show_key(initial_key)
        else:
            self._show_list()

    def _make_context(self) -> dict[Any, Any]:
        return {}

    def _entry_value(self, entry: ConfigKeyEntry) -> object | None:
        """Resolve the live value for a config key entry.

        Returns:
            The raw config value at the entry's dotted path.
        """
        try:
            return _get_nested(self._model, entry.path)
        except AttributeError:
            logger.debug("Failed to resolve value for entry %r", entry.path)
            return None

    def _is_set(self, entry: ConfigKeyEntry) -> bool:
        """Return whether the entry has a non-empty value."""
        value = self._entry_value(entry)
        return not (value is None or value in ("", [], {}, set(), frozenset()))

    def _show_list(self) -> None:
        """Render the paginated key list with select dropdown and nav buttons."""
        self._render_page(title=self._t(_("view.config.title")))

    def _render_body(self, items: Sequence[ConfigKeyEntry]) -> list[discord.ui.Item[Any]]:
        """Return content children: key lines, sep, [select row].

        Args:
            items: Key entries visible on the current page.
        """
        if not items:
            return [
                discord.ui.TextDisplay(self._t(_("view.config.empty"))),
            ]

        has_unsettable = any(not e.settable for e in items)
        list_lines: list[str] = []
        for e in items:
            path_text = discord.utils.escape_markdown(e.path)
            prefix = "\\*" if not e.settable else ""
            if not self._is_set(e):
                # @info: Shown in the list view when a config value is empty
                list_lines.append(f"**{prefix}{path_text}** = {self._t(_('view.config.not_set'))}")
            else:
                list_lines.append(f"**{prefix}{path_text}** = `{_clean_display(self._entry_value(e))}`")
        if has_unsettable:
            list_lines.extend(["", self._t(_("view.config.list_settable_note"))])
        list_text = "\n".join(list_lines)

        key_select = discord.ui.Select[Any](
            placeholder=self._t(_("view.config.select_placeholder")),
            options=[discord.SelectOption(label=e.path, value=e.path) for e in items],
        )

        async def on_select(interaction: discord.Interaction) -> None:
            self._show_key(key_select.values[0])
            await self._update_message(interaction)

        key_select.callback = on_select
        return [
            discord.ui.TextDisplay(list_text),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(key_select),
        ]

    def _show_key(self, path: str) -> None:
        """Show a single config key with its value.

        Args:
            path: The full dotted config key path to display.
        """
        entry = next((e for e in self._items if e.path == path), None)
        if entry is None:
            logger.debug("Key %r not found in entries", path)
            self._show_list()
            return

        parts = [f"### `{path}`"]
        if entry.description:
            parts.append(entry.description)
        parts.extend([
            "",
            self._t(_("view.config.type_label")),
            f"`{entry.type_repr}`",
            "",
            self._t(_("view.config.value_label")),
        ])
        if not self._is_set(entry):
            # @info: Shown in the key detail view when a config value is empty
            parts.append(self._t(_("view.config.not_set")))
        else:
            # TODO: Some formats (dicts/lists/etc.) should be pretty-printed (in json/toml?)
            parts.append(f"`{_clean_display(self._entry_value(entry), max_length=1000, strip_newlines=False)}`")
        content = "\n".join(parts)

        async def on_back(interaction: discord.Interaction) -> None:
            self._show_list()
            await self._update_message(interaction)

        if entry.settable:
            # @param key: Config key path
            footer = self._t(_("view.config.footer", key=path, escape=False))
        else:
            footer = self._t(_("view.config.footer_readonly", key=path, escape=False))

        self._render_custom_page(
            discord.ui.Container(
                discord.ui.TextDisplay(content),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(footer),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(self._back_btn(callback=on_back)),
                accent_color=discord.Color.blurple(),
            )
        )


def _clean_display(value: Any, max_length: int = 100, strip_newlines: bool = True) -> str:
    r"""Format and sanitize a config value for safe inline display.

    Args:
        value: The raw config value.
        max_length: Maximum length of the output string before truncation.
        strip_newlines: When `True`, replace newlines with literal `\\n`.

    Returns:
        A display-safe plain string.
    """
    if isinstance(value, SecretStr):
        raw = "**********"
    elif isinstance(value, bool | NoneType):
        raw = str(value).lower()
    else:
        raw = str(value)
    if strip_newlines:
        sanitized = raw.replace("\\", "\\\\").replace("\n", "\\n").replace("`", "'")
    else:
        sanitized = raw.replace("\\", "\\\\").replace("`", "'")
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "\u2026"
    return sanitized


async def _config_key_autocomplete(  # noqa: RUF029
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    """Return matching config keys for slash-command autocomplete."""
    try:
        st = get_store()
        keys = st.keys()
    except RuntimeError:
        logger.debug("Autocomplete failed: config store not loaded")
        return []
    current_lower = current.casefold()
    matches = [k.path for k in keys if current_lower in k.path.casefold()]
    return [discord.app_commands.Choice(name=p, value=p) for p in matches[:25]]


@owner_only
@bot_group(
    name=_("cmd.config.name"),
    description=_("cmd.config.description"),
    help=_("cmd.config.help"),
    hidden=True,
)
async def config_command(cog: Utility, ctx: Context) -> None:
    """Manage bot configuration at runtime.

    Changes are written to `config.toml` immediately and take effect after a
    restart. Supports TOML inline values and `+`/`-` batch operations for
    collections.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """
    await ctx.reply(_("msg.config.help"))


@wrap(discord.app_commands.autocomplete, key=_config_key_autocomplete)
@config_command.command(
    name=_("cmd.config.show.name"),
    description=_("cmd.config.show.description"),
    help=_("cmd.config.show.help"),
    param_info={
        "key": ParamInfo(
            name=_("cmd.config.param.key.name"),
            description=_("cmd.config.param.key.description"),
        )
    },
)
async def config_show_command(cog: Utility, ctx: Context, *, key: str | None = None) -> None:
    """Show the current value of a config key.

    Omit `key` to browse all writable keys and their values. Provide a dotted
    path to inspect a single key in detail. Secret fields display as
    `**********`.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        key: Dot-separated config key path. Omit to browse all keys.
    """
    with ephemeral_scope(ctx.interaction):
        try:
            store = get_store()
        except RuntimeError:
            logger.warning("Config show attempted before store was loaded")
            await ctx.reply(_("msg.config.no_keys"))
            return

        entries = store.keys()
        if not entries:
            logger.debug("No config entries resolved for display")
            await ctx.reply(_("msg.config.no_keys"))
            return

        if key is not None and not any(e.path == key for e in entries):
            # TODO: give fuzzy suggestions based on the input key
            logger.debug("Requested key %r not found in entries", key)
            # @param key: The config key that was requested.
            await ctx.reply(_("msg.config.invalid_key", key=key, escape=False))
            return

        logger.debug("Showing config browser with %d entries (initial_key=%r)", len(entries), key)
        view = ConfigShowView(ctx, entries, store.model, initial_key=key)
        msg = await ctx.reply(view=view)
        view.message = msg


@wrap(discord.app_commands.autocomplete, key=_config_key_autocomplete)
@config_command.command(
    name=_("cmd.config.set.name"),
    description=_("cmd.config.set.description"),
    help=_("cmd.config.set.help"),
    param_info={
        "key": ParamInfo(
            name=_("cmd.config.param.key.name"),
            description=_("cmd.config.param.key.description"),
        ),
        "value": ParamInfo(
            name=_("cmd.config.param.value.name"),
            description=_("cmd.config.param.value.description"),
        ),
    },
)
async def config_set_command(cog: Utility, ctx: Context, key: str, *, value: str) -> None:
    """Set a config value with smart parsing.

    Supports TOML inline values (`true`, `123`, `"hello"`, `[1,2,3]`),
    raw strings, and `+`/`-` batch operations for collections:

    - `+123` adds an element to a set.
    - `-123` removes an element from a set.
    - `+cmd=staff` adds/updates a dict entry.
    - `-cmd` removes a dict entry.

    Multiple operations can be space-separated: `+a -b +c=d`.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        key: Dot-separated config key path.
        value: The new value.
    """
    with ephemeral_scope(ctx.interaction):
        try:
            st = get_store()
        except RuntimeError:
            logger.warning("Config set attempted before store was loaded")
            await ctx.reply(_("msg.config.not_loaded"))
            return

        all_keys = st.keys()
        entry = next((k for k in all_keys if k.path == key), None)
        if entry is not None and not entry.settable:
            await ctx.reply(_("msg.config.error.readonly"))
            return

        try:
            parsed = _parse(key, value)
            logger.debug("Setting %s to %s (parsed=%r)", key, value, parsed)
            new_config = await st.update(key, parsed)
        except ConfigUpdateError as e:
            logger.warning("Config set failed for %s (reason=%s, detail=%s)", key, e.reason, e.detail)
            match e.reason:
                case "parse":
                    await ctx.reply(_("msg.config.error.parse"))
                case "validation":
                    await ctx.reply(_("msg.config.error.validation"))
                case "readonly":
                    await ctx.reply(_("msg.config.error.readonly"))
                case _:
                    await ctx.reply(_("msg.config.error.internal"))
            return

        try:
            val = _get_nested(new_config, key)
        except AttributeError:
            logger.error("Config set succeeded but key %r not found on validated model", key)
            await ctx.reply(_("msg.config.set.not_found", key=key, escape=False))
            return
        display = _clean_display(val)
        logger.info("Config set succeeded for %s (val=%s)", key, val)
        # @param key: The config key that was set.
        # @param value: The new value of the config key.
        await ctx.reply(_("msg.config.set.ok", key=key, value=display, escape=False))


@wrap(discord.app_commands.autocomplete, key=_config_key_autocomplete)
@config_command.command(
    name=_("cmd.config.unset.name"),
    description=_("cmd.config.unset.description"),
    help=_("cmd.config.unset.help"),
    param_info={
        "key": ParamInfo(
            name=_("cmd.config.param.key.name"),
            description=_("cmd.config.param.key.description"),
        )
    },
)
async def config_unset_command(cog: Utility, ctx: Context, *, key: str) -> None:
    """Restore a config key to its Pydantic default value.

    Removes the key from the config data and re-validates. Pydantic fills in
    the field default automatically. Fails if the field has no default.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        key: Dot-separated config key path to unset.
    """
    try:
        st: ConfigStore = get_store()
    except RuntimeError:
        logger.warning("Config unset attempted before store was loaded")
        await ctx.reply(_("msg.config.not_loaded"), ephemeral=True)
        return

    all_keys = st.keys()
    entry = next((k for k in all_keys if k.path == key), None)
    if entry is not None and not entry.settable:
        await ctx.reply(_("msg.config.error.readonly"), ephemeral=True)
        return

    try:
        logger.debug("Unsetting %s", key)
        new_config = await st.update(key, UnsetOp())
    except ConfigUpdateError as e:
        logger.warning("Config unset failed for %s (reason=%s, detail=%s)", key, e.reason, e.detail)
        match e.reason:
            case "parse":
                await ctx.reply(_("msg.config.error.parse"), ephemeral=True)
            case "validation":
                await ctx.reply(_("msg.config.error.validation"), ephemeral=True)
            case "readonly":
                await ctx.reply(_("msg.config.error.readonly"), ephemeral=True)
            case _:
                await ctx.reply(_("msg.config.error.internal"), ephemeral=True)
        return

    try:
        val = _get_nested(new_config, key)
    except AttributeError:
        logger.error("Config unset succeeded but key %r not found on validated model", key)
        await ctx.reply(_("msg.config.unset.not_found", key=key, escape=False))
        return
    display = _clean_display(val)
    logger.info("Config unset succeeded for %s (default=%s)", key, display)
    # @param key: The config key that was unset.
    # @param value: The default value of the config key.
    await ctx.reply(_("msg.config.unset.ok", key=key, value=display, escape=False))


@config_command.command(
    name=_("cmd.config.reload.name"),
    description=_("cmd.config.reload.description"),
    help=_("cmd.config.reload.help"),
)
async def config_reload_command(cog: Utility, ctx: Context) -> None:
    """Reload the config file from disk and re-validate.

    Useful after manual edits to `config.toml`.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """
    try:
        st: ConfigStore = get_store()
    except RuntimeError:
        logger.warning("Config reload attempted before store was loaded")
        await ctx.reply(_("msg.config.not_loaded"), ephemeral=True)
        return

    logger.debug("Reloading config from disk")
    try:
        await st.reload()
    except (pydantic.ValidationError, OSError) as e:
        logger.warning("Config reload failed: %s", e)
        await ctx.reply(_("msg.config.reload.failed"))
        return

    logger.debug("Config reloaded successfully")
    await ctx.reply(_("msg.config.reload.ok"))
