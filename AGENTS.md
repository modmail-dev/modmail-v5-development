# Modmail v5

> **Before editing any file, re-read this file first.** Every rule below
> is mandatory — assume nothing, verify everything.

## Docstring quick-ref

| Rule | Wrong | Right |
|---|---|---|
| Single backticks only | ``discord`` | `discord` |
| No implementation details in attr desc | "Per-logger floor for..." | "Logging level for the `discord` package." |
| Line length 105 (docstrings) | lines > 105 chars | split to ≤ 105 |
| No semicolons | `for the user;` | `for the user.` |

The full rules are in the Conventions section below.

## Git safety

- **Never run destructive git operations**: no `git checkout`, `git reset --hard`, `git revert`, `git clean`, `git push --force`, or any command that discards or overwrites uncommitted changes. If you need to restore a file, ask first.
- **Never run `rm` on tracked files** — warn the user before doing so.

## Commands

```bash
# Setup
uv sync --locked --compile-bytecode --no-default-groups --extra speed --extra <DBTYPE>
cp config.toml.example config.toml  # edit token, staff_server_id, etc.

# Required before marking any work done
uv run ruff check --fix && uv run ruff format
uv run pyright
```

## Conventions

- **Line length**: 115 (docstrings: 105). Ruff `preview = true`.
- **Docstrings**: Google style. Cross-refs: `[Name][]`.
- **Attribute descriptions**: inline `"""` under each field, for the user, no implementation details, no semicolons.
- **US spelling** (`color`, not `colour`).
- **Never add suppression comments** (`# noqa`, `# type: ignore`, `# pyright: ignore`). If ruff or pyright complains, fix the code, don't silence it.
- **Tests are obsolete/disabled** — do not create, run, or reference them.
- **No Cog classes**: commands are `async` functions decorated with `@bot_command()` or `@bot_group()`. Function names must end with `_command`.
- **Single backticks only** in docstrings (`code`, never ``code``).
- **No section divider comments** (no `# ----` banners, separator blocks, or partitioning markers).
- **Config is a proxy**: `from modmail.config import config`. Do not construct `Config(...)` directly — access before init raises `RuntimeError`. Mutate at runtime via `get_store().update(...)`.
- **Don't call `Bot.run()`** — it raises `NotImplementedError`. Always use `Bot.run_bot()`.

## Non-obvious patterns

- **SQL driver injection**: the async driver suffix is added automatically (`postgresql://` → `postgresql+asyncpg://`). Don't append it manually.
- **Backend detection**: the database backend is detected from the URI scheme, not a config key.
- **Ticket channel check**: use `@in_modmail_ticket()` to guard commands that require an open ticket.
- **Runtime config editing**: `get_store().update("bot.prefix", SetOp("!"))`.
- **No member cache**: the bot disables discord.py's default member caching. Use `guild.fetch_member()` — `guild.get_member()` returns `None`.
- **Allowed mentions default off**: `allowed_mentions` is set to `discord.AllowedMentions.none()`. Mentions do not resolve unless explicitly opted into per-message.
- **Ticket flow**: DMs to the bot → `staff_guild.create_ticket()` creates a channel/thread in the staff guild → `TicketView` bridges DM ↔ staff messages until close (channel deleted/archived, ticket marked in DB).
- **Permission evaluation**: `check_user_access()` evaluates in order: profile deny overrides → profile allow overrides (exact + wildcard `name+`) → owner check → Discord admin bypass → `access_level >= required_level` → everyone default.
- **Both backends persist the same models**: SQL and MongoDB share Pydantic models in `backends/common/models/`. Update both `SQL*Mixin` and `MongoDB*Mixin` when changing persistence schema.
- **`spawn_task()` for fire-and-forget**: use `bot.spawn_task(coro)` instead of `asyncio.create_task()`. Tasks are tracked in `_pending_tasks` (prevent GC) and canceled on bot shutdown.
- **Cog `TYPE_CHECKING` trick**: cogs are dynamically built via `create_cog()`. Each `cogs/*/__init__.py` uses `if TYPE_CHECKING: class Name(Cog): ... else: Name = create_cog(...)` to keep type checkers happy.
- **Localization**: Gettext `.po`/`.mo` via Babel with dotted-path msgids (`cmd.reply.name`). `_()`/`_n()`/`_c()`/`_cn()` return `locale_str` (not `str`); Discord resolves per-user locale at send time. Use `ctx.t(_("key"))` inside commands for a rendered `str` in the user's locale. Placeholders: `{name}`. Context via `upgettext("ctx", "key")`.
  - PO files auto-compiled to MO on startup via config validator → `ensure_compiled()`.
  - CLI: `python -m modmail.locales {extract,check,compile,add,custom}`.
  - Custom locale: `python -m modmail.locales custom [BASE]` creates `locales/<BASE>-custom/`; babel sees `xx_YY@custom`. Only one `*-custom` dir allowed. Custom `.mo` checked before every lookup — translated `msgstr` overrides the default.
  - `internal.*` msgids are rejected by the extractor (known set: `internal.blank`, `internal.error`); unknown ones emit a warning.
  - **Construction-time vs translation-time kwargs**: `_("key", name=val)` stores `name=val` in the `locale_str`. `ctx.t(_("key"), name=val2)` merges on top, both works.
  - **Translator comments**: Comments above `_()` calls with `@info`, `@param`, or `@see` become auto-comments in `.po` files.
    - `@info: text` — explains what the string is used for when the msgid isn't self-explanatory.
    - `@param param-name: Description` — required for every `{placeholder}` in the msgid. One `@param` line per parameter, format `@param name: description`.
    - `@see other.msgid.key` — copies the `@param` lines from `other.msgid.key` to this entry (useful when two msgids share the same parameters).
- **`EmbedProxy` for lazy translation**: stores `locale_str` values unresolved. `to_embed(translator, locale)` resolves all strings at send time, so one proxy renders into any locale.
