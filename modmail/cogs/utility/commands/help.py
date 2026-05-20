"""Interactive help command with Component v2 navigation."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import discord
from discord.app_commands import locale_str
from discord.ext import commands as _commands

from modmail import CONFIG
from modmail.core import (
    BaseLayoutView,
    Cog,
    Context,
    ParamInfo,
    Str,
    bot_command,
    ephemeral_scope,
    locale_for,
    using_ephemeral,
)
from modmail.enum import RequiredAccessLevel
from modmail.i18n import _, ngettext

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["help_command"]

logger = logging.getLogger(__name__)

_SELECT_PAGE_SIZE: int = 10
_MAX_SELECT_LABEL_LEN: int = 100
_MAX_SELECT_DESC_LEN: int = 100
_MAX_LIST_DESC_LEN: int = 80

_ACCESS_COLORS: dict[RequiredAccessLevel, discord.Color] = {
    RequiredAccessLevel.everyone: discord.Color.light_grey(),
    RequiredAccessLevel.staff: discord.Color.blue(),
    RequiredAccessLevel.manager: discord.Color.orange(),
    RequiredAccessLevel.admin: discord.Color.red(),
    RequiredAccessLevel.owner: discord.Color.gold(),
}

_JISHAKU_COG_NAME = "Jishaku"
_JISHAKU_COLOR = discord.Color.dark_grey()
_OTHER_COG_KEY = "__other__"


@dataclass
class _ParamEntry:
    """Resolved info for a single command parameter."""

    name: str
    """Display name for the parameter."""
    description: str
    """User-facing summary of what the parameter does."""
    required: bool
    """Whether the parameter is required for the command."""


@dataclass
class _CommandEntry:
    """Resolved command info for one command entry in the help menu."""

    canonical_key: str
    """Canonical command key used by the permission index."""
    category_key: str
    """Cog key (the name in code) used to group the command in the UI."""
    display_name: str
    """Label shown for the command in help views."""
    fallback_name: str
    """Translated fallback subcommand name for hybrid groups with a slash fallback (empty if absent)."""
    description: str
    """Short description shown in list views."""
    help_text: str
    """Long-form help text (can be blank)."""
    access_level: RequiredAccessLevel
    """Minimum access level required to run the command."""
    params: list[_ParamEntry]
    """Ordered parameter details for the command."""
    parent_keys: list[str]
    """Canonical keys for parent commands (can be empty)."""
    is_prefix_only: bool
    """Whether the command is available only as a prefix command."""
    is_jishaku: bool
    """Whether the command belongs to the Jishaku cog."""


@dataclass
class _CategoryInfo:
    """Metadata and command list for a single cog category."""

    category_key: str
    """Cog key (the name in code) used to group the command in the UI."""
    display_name: str
    """Label shown for the category in help views."""
    description: str
    """Category description shown in the overview (can be blank)."""
    color: discord.Color
    """Accent color used for category UI containers."""
    commands: list[_CommandEntry]
    """Commands visible within this category."""


def _build_command(
    ctx: Context,
    cmd: _commands.Command[Any, Any, Any],
    display_name: str,
    *,
    cog_key: str,
) -> _CommandEntry:
    """Construct a [`_CommandEntry`][] from a single command.

    Args:
        ctx: The invoking context, used for translation.
        cmd: The command to resolve.
        display_name: Pre-translated display name from the permission index.
        cog_key: Internal cog name (dict key in categories).

    Returns:
        A fully populated [`_CommandEntry`][].
    """
    if isinstance(cmd, _commands.HybridCommand | _commands.HybridGroup):
        is_prefix_only = cmd.app_command is None or cmd.app_command is discord.utils.MISSING
        description = ctx.t(cmd._locale_description) if cmd._locale_description else cmd.description  # pyright: ignore [reportPrivateUsage]
    else:
        is_prefix_only = True
        description = cmd.description

    if not description:
        description = cmd.short_doc  # first line of the docstring

    fallback_name: str = ""
    if isinstance(cmd, _commands.HybridGroup):
        if cmd.fallback_locale is not None:
            fallback_name = ctx.t(cmd.fallback_locale)
        elif cmd.fallback is not None:
            fallback_name = cmd.fallback

    # Help text stored by CommandBuilder.get_commands
    help_text_raw: locale_str | str = getattr(cmd.callback, "_bot_help", "")
    help_text: str = ctx.t(help_text_raw) if isinstance(help_text_raw, locale_str) else help_text_raw

    # Param info stored by CommandBuilder.get_commands — keyed by Python param name
    bot_param_info: dict[str, ParamInfo] = getattr(cmd.callback, "_bot_param_info", {})

    params: list[_ParamEntry] = []
    for p_name, param in cmd.clean_params.items():
        if (info := bot_param_info.get(p_name)) is not None:
            param_name = ctx.t(info.name) if isinstance(info.name, locale_str) else info.name
            param_desc = ctx.t(info.description) if isinstance(info.description, locale_str) else info.description
        else:
            if bot_param_info:
                logger.debug(
                    "Parameter '%s' on command '%s' is missing ParamInfo; falling back to defaults",
                    p_name,
                    cmd.qualified_name,
                )
            param_name = param.displayed_name or param.name
            param_desc = param.description or ""

        params.append(_ParamEntry(name=param_name, description=param_desc, required=param.required))

    return _CommandEntry(
        canonical_key=ctx.bot.get_canonical_command_name(cmd),
        category_key=cog_key,
        display_name=display_name,
        fallback_name=fallback_name,
        description=description,
        help_text=help_text,
        access_level=ctx.bot.get_command_access_level(cmd),
        params=params,
        parent_keys=[ctx.bot.get_canonical_command_name(p) for p in getattr(cmd, "parents", [])],
        is_prefix_only=is_prefix_only,
        is_jishaku=CONFIG.bot.enable_jishaku and cmd.cog_name == _JISHAKU_COG_NAME,
    )


def _build_cat_info(ctx: Context, cog_key: str, commands: list[_CommandEntry]) -> _CategoryInfo:
    """Build a [`_CategoryInfo`][] from a cog key and its resolved command entries.

    Returns:
        A [`_CategoryInfo`][] with display name, commands, accent color, and description.
    """
    if cog_key == _OTHER_COG_KEY:
        return _CategoryInfo(
            category_key=cog_key,
            display_name=ctx.t(_("view.help.category.other.name")),
            description="",
            color=discord.Color.greyple(),
            commands=commands,
        )

    if CONFIG.bot.enable_jishaku and cog_key == _JISHAKU_COG_NAME:
        return _CategoryInfo(
            category_key=cog_key,
            display_name=ctx.t(_("view.help.category.jishaku.name")),
            description=ctx.t(_("view.help.category.jishaku.description")),
            color=_JISHAKU_COLOR,
            commands=commands,
        )

    cog = ctx.bot.cogs.get(cog_key)
    if cog is None:
        return _CategoryInfo(
            category_key=cog_key,
            display_name=cog_key,
            description="",
            color=discord.Color.greyple(),
            commands=commands,
        )

    if not isinstance(cog, Cog):
        return _CategoryInfo(
            category_key=cog_key,
            display_name=cog.qualified_name,
            description=cog.description,
            color=discord.Color.greyple(),
            commands=commands,
        )

    return _CategoryInfo(
        category_key=cog_key,
        display_name=ctx.t(cog.help_name)
        if isinstance(cog.help_name, locale_str)
        else cog.help_name or cog.qualified_name,
        description=ctx.t(cog.help_description)
        if isinstance(cog.help_description, locale_str)
        else cog.help_description or "",
        color=cog.help_color if cog.help_color is not None else discord.Color.greyple(),
        commands=commands,
    )


async def _build_categories(ctx: Context) -> dict[str, _CategoryInfo]:
    """Build an ordered category map from the bot's live command tree.

    Applies access filtering based on [`CONFIG.bot`][] settings:
    - Owner-only commands hidden when [`BotConfig.hide_owner_commands`][] is `True`
      and the invoking user is not an owner.
    - All inaccessible commands hidden when [`BotConfig.hide_inaccessible`][] is `True`.
      Jishaku commands bypass this check.
    - Cogs with no visible commands are omitted entirely.

    Args:
        ctx: The invoking command context.

    Returns:
        Ordered mapping of cog key to [`_CategoryInfo`][] with filtered, sorted commands.
    """
    if using_ephemeral(ctx.interaction):
        locale = locale_for(ctx.interaction)
    else:
        locale = locale_for(None)
    index = ctx.bot.permission_command_index(locale)

    is_owner = await ctx.bot.is_owner(ctx.author)
    profiles = ctx.bot.get_all_user_profiles(ctx.author)
    seen_commands: set[str] = set()
    cog_commands_mapping: defaultdict[str, list[_CommandEntry]] = defaultdict(list)

    for cmd in ctx.bot.walk_commands():
        if cmd.hidden:
            continue

        canonical_key = ctx.bot.get_canonical_command_name(cmd)
        if canonical_key in seen_commands:
            continue
        seen_commands.add(canonical_key)

        cog_key = cmd.cog_name or _OTHER_COG_KEY
        display_name = index.label(canonical_key)
        command = _build_command(ctx, cmd, display_name, cog_key=cog_key)

        if CONFIG.bot.hide_owner_commands:
            if command.access_level == RequiredAccessLevel.owner and not is_owner:
                continue

        if CONFIG.bot.hide_inaccessible:
            user_access = await ctx.bot.check_user_access(
                author=ctx.author,
                command_key=command.canonical_key,
                parent_keys=command.parent_keys,
                command_access_level=command.access_level,
                profiles=profiles,
                is_owner=is_owner,
                is_jishaku=command.is_jishaku,
            )

            if not user_access.allowed:
                continue

        cog_commands_mapping[cog_key].append(command)

    # Build category infos
    all_cats: dict[str, _CategoryInfo] = {}
    for cog_key, commands in cog_commands_mapping.items():
        commands.sort(key=lambda e: e.display_name.lower())
        all_cats[cog_key] = _build_cat_info(ctx, cog_key, commands)

    # Sort: normal cogs alphabetically → Jishaku → Other
    jishaku_info = all_cats.pop(_JISHAKU_COG_NAME, None)
    other_info = all_cats.pop(_OTHER_COG_KEY, None)

    ordered: dict[str, _CategoryInfo] = dict(sorted(all_cats.items(), key=lambda kv: kv[1].display_name.lower()))
    if jishaku_info is not None:
        ordered[_JISHAKU_COG_NAME] = jishaku_info
    if other_info is not None:
        ordered[_OTHER_COG_KEY] = other_info

    return ordered


class HelpView(BaseLayoutView):
    """Interactive Component v2 help browser.

    Presents three navigable pages: an overview with category selection, a category page
    listing commands with optional pagination, and a detail page for a single command.
    When all commands are filtered out, the overview shows a "no access" message.
    """

    def __init__(
        self,
        ctx: Context,
        categories: dict[str, _CategoryInfo],
        *,
        initial_entry: _CommandEntry | _CategoryInfo | None = None,
        timeout: float = 300.0,
    ) -> None:
        """Build the help browser, starting on the overview or a direct entry page.

        Args:
            ctx: The invoking command context.
            categories: Pre-built data from [`_build_categories`][].
            initial_entry: Opens directly on this command or category instead of the overview.
            timeout: Seconds before the view stops accepting interactions.
        """
        super().__init__(ctx.bot, ctx.author, interaction=ctx.interaction, timeout=timeout)
        self._categories = categories
        self._current_interactive: list[discord.ui.Select[HelpView] | discord.ui.Button[HelpView]] = []
        if isinstance(initial_entry, _CommandEntry):
            self._show_command(initial_entry)
        elif isinstance(initial_entry, _CategoryInfo):
            self._show_category(initial_entry.category_key)
        else:
            self._show_overview()

    def _make_cmd_select_option(self, command: _CommandEntry) -> discord.SelectOption:
        """Build a select option for a single command entry.

        Returns:
            A [`discord.SelectOption`][] with label, description, and value set.
        """
        name = command.display_name
        if command.fallback_name:
            name = f"{name} [{command.fallback_name}]"
        label = name[:_MAX_SELECT_LABEL_LEN]

        access = self._t(command.access_level.__locale_str__())
        if command.description:
            prefix = f"{access} · "
            remaining = _MAX_SELECT_DESC_LEN - len(prefix)
            desc_text = command.description
            if len(desc_text) > remaining:
                desc_text = desc_text[: remaining - 1] + "…"
            description: str | None = f"{prefix}{desc_text}"
        else:
            description = access

        return discord.SelectOption(label=label, description=description, value=command.canonical_key)

    def _format_list_line(self, command: _CommandEntry) -> str:
        """Format a single command as a markdown list line.

        Returns:
            A Discord markdown string for use in a [`discord.ui.TextDisplay`][].
        """
        access = self._t(command.access_level.__locale_str__())
        desc = command.description
        short_desc = desc[: _MAX_LIST_DESC_LEN - 1] + "…" if len(desc) > _MAX_LIST_DESC_LEN else desc
        desc_part = f" — {short_desc}" if short_desc else ""

        if command.fallback_name:
            annotation = f" *({command.fallback_name})*"
        elif command.is_prefix_only:
            annotation = f" *({self._t(_('view.help.prefix_only'))})*"
        else:
            annotation = ""

        return f"- **{command.display_name}**{annotation}{desc_part}  `{access}`"

    def _build_nav_row(self, cog_key: str, page: int, total_pages: int) -> discord.ui.ActionRow[HelpView]:
        """Build the navigation row: back (leftmost, primary), prev, next.

        Returns:
            An [`discord.ui.ActionRow`][] containing the applicable navigation buttons.
        """
        nav_row: discord.ui.ActionRow[HelpView] = discord.ui.ActionRow()

        # Back always comes first (primary style to distinguish from nav buttons)
        back_btn: discord.ui.Button[HelpView] = discord.ui.Button(
            label=self._t(_("view.help.btn.back")),
            style=discord.ButtonStyle.primary,
        )

        async def on_back(interaction: discord.Interaction) -> None:  # noqa: RUF029
            self._show_overview()
            self._update_message(interaction)

        back_btn.callback = on_back
        self._current_interactive.append(back_btn)
        nav_row.add_item(back_btn)

        if total_pages > 1:
            prev_btn: discord.ui.Button[HelpView] = discord.ui.Button(
                label=self._t(_("view.help.btn.prev")),
                style=discord.ButtonStyle.secondary,
                disabled=page == 0,
            )

            async def on_prev(interaction: discord.Interaction) -> None:  # noqa: RUF029
                self._show_category(cog_key, page - 1)
                self._update_message(interaction)

            prev_btn.callback = on_prev
            self._current_interactive.append(prev_btn)
            nav_row.add_item(prev_btn)

            next_btn: discord.ui.Button[HelpView] = discord.ui.Button(
                label=self._t(_("view.help.btn.next")),
                style=discord.ButtonStyle.secondary,
                disabled=page >= total_pages - 1,
            )

            async def on_next(interaction: discord.Interaction) -> None:  # noqa: RUF029
                self._show_category(cog_key, page + 1)
                self._update_message(interaction)

            next_btn.callback = on_next
            self._current_interactive.append(next_btn)
            nav_row.add_item(next_btn)

        return nav_row

    def _show_overview(self) -> None:
        """Rebuild the view to show the category-selection overview page."""
        self._current_interactive.clear()
        self.clear_items()

        if not self._categories:
            no_access_items: list[discord.ui.Item[HelpView]] = [
                discord.ui.TextDisplay(self._t(_("view.help.title"))),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(self._t(_("view.help.no_access"))),
            ]
            self.add_item(discord.ui.Container(*no_access_items, accent_color=discord.Color.blurple()))
            return

        total_cmds = sum(len(c.commands) for c in self._categories.values())
        total_cats = len(self._categories)
        cat_word = self._t(ngettext("view.help.stats.category", total_cats))
        cmd_word = self._t(ngettext("view.help.stats.command", total_cmds))
        stats = self._t(_("view.help.stats.template", categories_word=cat_word, commands_word=cmd_word))

        cat_lines = "\n".join(
            f"**{info.display_name}** — {info.description}" if info.description else f"**{info.display_name}**"
            for info in self._categories.values()
        )

        # TODO: handle/paginate if # cogs > 25 / select max
        options = [
            discord.SelectOption(
                label=cat_info.display_name,
                description=cat_info.description[:_MAX_SELECT_DESC_LEN] or None,
                value=cog_key,
            )
            for cog_key, cat_info in self._categories.items()
        ]

        cat_select: discord.ui.Select[HelpView] = discord.ui.Select(
            placeholder=self._t(_("view.help.category.placeholder")),
            options=options,
        )

        async def on_cat_select(interaction: discord.Interaction) -> None:  # noqa: RUF029
            self._show_category(cat_select.values[0])
            self._update_message(interaction)

        cat_select.callback = on_cat_select
        self._current_interactive.append(cat_select)

        action_row: discord.ui.ActionRow[HelpView] = discord.ui.ActionRow()
        action_row.add_item(cat_select)

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(self._t(_("view.help.title"))),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(stats),
                discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(cat_lines),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(self._t(_("view.help.subtitle"))),
                discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
                action_row,
                accent_color=discord.Color.blurple(),
            )
        )

    def _show_category(self, cog_key: str, page: int = 0) -> None:
        """Rebuild the view to show the commands for `cog_key`, with pagination.

        Args:
            cog_key: The internal cog key used in [`_categories`][].
            page: Zero-based page index into the paginated command list.
        """
        self._current_interactive.clear()
        self.clear_items()

        cat_info = self._categories.get(cog_key)
        if cat_info is None:
            logger.warning("Category key '%s' not found in categories map; how did we get here?", cog_key)
            self._show_overview()
            return

        if not cat_info.commands:
            self._show_category_empty(cog_key=cog_key, cat_info=cat_info)
            return

        total_pages = max(1, math.ceil(len(cat_info.commands) / _SELECT_PAGE_SIZE))
        page = max(0, min(page, total_pages - 1))
        start = page * _SELECT_PAGE_SIZE
        page_commands = cat_info.commands[start : start + _SELECT_PAGE_SIZE]

        list_text = "\n".join(self._format_list_line(e) for e in page_commands)

        header = f"### {cat_info.display_name}"
        if total_pages > 1:
            # @param page: Current page number (1-indexed)
            # @param total: Total number of pages
            indicator = self._t(_("view.help.page_indicator", page=page + 1, total=total_pages))
            header = f"{header}  ·  *{indicator}*"

        cmd_select: discord.ui.Select[HelpView] = discord.ui.Select(
            placeholder=self._t(_("view.help.command.placeholder")),
            options=[self._make_cmd_select_option(e) for e in page_commands],
        )

        async def on_cmd_select(interaction: discord.Interaction) -> None:  # noqa: RUF029
            key = cmd_select.values[0]
            found = next((e for e in page_commands if e.canonical_key == key), None)
            if found is None:
                logger.warning("Selected command not found, value was '%s'; how did we get here?", key)
                self.defer(interaction)
            else:
                self._show_command(found)
                self._update_message(interaction)

        cmd_select.callback = on_cmd_select
        self._current_interactive.append(cmd_select)

        select_row: discord.ui.ActionRow[HelpView] = discord.ui.ActionRow()
        select_row.add_item(cmd_select)
        nav_row = self._build_nav_row(cog_key, page, total_pages)

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(header),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(list_text),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                select_row,
                nav_row,
                accent_color=cat_info.color,
            )
        )

    def _show_category_empty(self, *, cog_key: str, cat_info: _CategoryInfo) -> None:
        # @param category: Category display name
        empty_title = self._t(_("view.help.category.empty_title", category=cat_info.display_name))
        empty_body = self._t(_("view.help.category.empty_body"))
        nav_row = self._build_nav_row(cog_key, 0, 1)

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(empty_title),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(empty_body),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                nav_row,
                accent_color=cat_info.color,
            )
        )

    def _show_command(self, command: _CommandEntry) -> None:
        """Rebuild the view to show full details for a single command.

        Args:
            command: The command entry to display.
        """
        self._current_interactive.clear()
        self.clear_items()

        cat_info = self._categories.get(command.category_key)
        if not cat_info:
            logger.warning(
                "No category found for command '%s' with category key '%s'",
                command.display_name,
                command.category_key,
            )
            back_label = command.category_key
        else:
            back_label = cat_info.display_name

        title = (
            f"{command.display_name} [{command.fallback_name}]" if command.fallback_name else command.display_name
        )
        detail_parts: list[str] = [f"### {title}"]

        if command.description:
            detail_parts.append(command.description)

        if command.help_text:
            detail_parts.extend(["", command.help_text])

        detail_parts.extend([
            "",
            # @param level: Localized access level name
            self._t(_("view.help.detail.access", level=command.access_level.__locale_str__())),
        ])

        if command.params:
            detail_parts.extend(["", self._t(_("view.help.detail.param_header"))])
            optional_label = self._t(_("view.help.detail.param_optional"))
            for param in command.params:
                line = f"- `{param.name}`"
                if param.description:
                    line = f"{line} — {param.description}"
                if not param.required:
                    line = f"{line} *({optional_label})*"
                detail_parts.append(line)

        if command.is_prefix_only:
            detail_parts.extend(["", f"-# {self._t(_('view.help.detail.prefix_note'))}"])

        back_btn: discord.ui.Button[HelpView] = discord.ui.Button(
            label=f"← {back_label}",
            style=discord.ButtonStyle.primary,
        )

        async def on_back(interaction: discord.Interaction) -> None:
            self._show_category(command.category_key)
            await self._update_message(interaction)

        back_btn.callback = on_back
        self._current_interactive.append(back_btn)

        back_row: discord.ui.ActionRow[HelpView] = discord.ui.ActionRow()
        back_row.add_item(back_btn)

        color = _ACCESS_COLORS.get(command.access_level, discord.Color.light_grey())
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("\n".join(detail_parts)),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                back_row,
                accent_color=color,
            )
        )

    async def on_timeout(self) -> None:
        """Disable all interactive elements on the current page when the view expires."""
        for item in self._current_interactive:
            item.disabled = True
        self._update_message()


@bot_command(
    name=_("cmd.help.name"),
    description=_("cmd.help.description"),
    param_info={
        "command": ParamInfo(
            name=_("cmd.help.param.command.name"),
            description=_("cmd.help.param.command.description"),
        )
    },
)
async def help_command(cog: Utility, ctx: Context, *, command: Str | None = None) -> None:
    """Display an interactive browser for all available commands.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        command: Optional command name to jump directly to its detail page.
    """
    with ephemeral_scope(ctx.interaction):
        categories = await _build_categories(ctx)
        user_locale = locale_for(ctx.interaction)

        if command is not None:
            # Check if the command matches any canonical command keys in the permission index
            canonical = cog.bot.permission_command_index(user_locale).resolve(command)
            if canonical:
                for cat_info in categories.values():
                    found = next((e for e in cat_info.commands if e.canonical_key == canonical), None)
                    if found is not None:
                        view = HelpView(ctx, categories, initial_entry=found)
                        msg = await ctx.reply(view=view)
                        view.message = msg
                        return

            # Check if the command matches a cog name
            normalized = command.casefold().replace("_", " ")
            for match_locale in {user_locale, CONFIG.default_locale}:
                for cat_info in categories.values():
                    if cat_info.category_key == _OTHER_COG_KEY:
                        display_name = cog.bot.translate(_("view.help.category.other.name"), locale=match_locale)
                    elif CONFIG.bot.enable_jishaku and cat_info.category_key == _JISHAKU_COG_NAME:
                        display_name = cog.bot.translate(_("view.help.category.jishaku.name"), locale=match_locale)
                    else:
                        category_cog = cog.bot.cogs.get(cat_info.category_key)
                        if category_cog is None:
                            display_name = cat_info.category_key
                        elif not isinstance(category_cog, Cog):
                            display_name = category_cog.qualified_name
                        else:
                            display_name = (
                                cog.bot.translate(category_cog.help_name, locale=match_locale)
                                if isinstance(category_cog.help_name, locale_str)
                                else category_cog.help_name or category_cog.qualified_name
                            )

                    if display_name.casefold().replace("_", " ").strip() == normalized:
                        view = HelpView(ctx, categories, initial_entry=cat_info)
                        msg = await ctx.reply(view=view)
                        view.message = msg
                        return

            # @param command: The user-typed command name
            await ctx.reply(_("view.help.not_found", command=command))
            return

        view = HelpView(ctx, categories)
        message = await ctx.reply(view=view)
        view.message = message
