# AGENTS.md

## Setup & verification

```bash
uv sync --locked --compile-bytecode --no-default-groups --extra speed --extra <DBTYPE>
# DBTYPE: mongodb | sqlite | postgresql | mysql | mariadb
cp config.yaml.example config.yaml  # edit token, staff_server_id, etc.
uv run python start.py
```

Run before marking work done:

```bash
uv run ruff check --fix && uv run ruff format
uv run pyright
```

- **Python 3.14 only** (`requires-python = "==3.14.*"`).
- Line length: 115 (docstrings: 105). Ruff `preview = true`.
- Tests are **obsolete/disabled** — do not run/create them, do not use as reference.

## Hard conventions

- **Every `.py` file starts with** `from __future__ import annotations` (enforced via ruff isort `required-imports`).
- **Never add suppression comments** (`# noqa`, `# type: ignore`, `# pyright: ignore`).
- Docstrings: **Google style**. Cross-refs: `[Name][]`. Use single backtick for inline code. Unrecognized section headers become admonition boxes (`Note:`, `Warning:`, etc.).
- Attribute descriptions: for the user, no implementation details, no semicolons.
- Use US spelling (`color`, not `colour`).

## Startup order

1. `modmail.__main__` → `modmail.init()` → `modmail.run_bot()`
2. `init()` calls `config.load_config()` (YAML → Pydantic `Config`), stores in module `_state["config"]`.
3. `run_bot()` creates `Bot()`, which calls `create_db_client(CONFIG)` to wire the backend.
4. `Bot.run_bot()` → `database_client.connect()` → loads two extensions (`modmail.cogs.utility`, `modmail.cogs.modmail`) → `bot.start()`. On shutdown, calls `database_client.disconnect()`.
5. `modmail.CONFIG` is a lazy `__getattr__` — raises `RuntimeError` if accessed before `init()`.

## Command system (`modmail/core/commands.py`)

Cogs are **not** written as classes. Commands are plain `async` functions decorated with `@bot_command()` or `@bot_group()`, which wrap them in `CommandBuilder` / `GroupBuilder`. These *defer* command creation — they store the callback + kwargs without calling `commands.hybrid_command()`.

At cog load time, `create_cog()` dynamically builds a `Cog` subclass via `type(name, (Cog,), methods)`.

`CommandBuilder.get_commands(cog_name)` injects `cog_name` into the callback's `__qualname__` (discord.py builds the command tree from qualnames), auto-applies `app_commands.rename` / `app_commands.describe` from `param_info`, applies deferred wrappers from `@wrap()`, then calls `commands.hybrid_command(...)(func)`. `GroupBuilder` extends this to recursively build subgroups.

Use `@wrap()` to attach standard discord.py checks:

```python
@wrap(commands.has_permissions, manage_messages=True)
@bot_command(name=...)
async def my_command(cog, ctx): ...
```

`@in_modmail_ticket()` (built on `wrap`) checks the channel is an open ticket in the staff guild.

## Permissions (`modmail/core/permission.py` + `bot.py`)

Two checks run on every command: `_bot_can_run_check` (no-op) and `_user_access_check` (calls `Bot.check_user_access()`).

`check_user_access()` resolves `RequiredAccessLevel` via: (1) `CONFIG.permission.overrides`, (2) `__permission__` attribute from `@staff_only` etc., (3) defaults to `everyone`. Then evaluates profiles (user + role profiles, `@everyone` upward): profile deny overrides, profile allow overrides (exact or wildcard `name+`), owner-only guard, Discord admin bypass, level match (`access_level >= required_level`), everyone default.

Profiles live in `DBClient.profiles` (in-memory cache). Modifying a profile triggers `StaffGuild.grant_access()` / `revoke_access()` to update Discord channel permission overwrites.

## Tickets (`modmail/core/staff_guild.py` + `_ticket_view.py`)

**DM listener** (`dm_receive.py`): ignores bots/non-DM, checks guild setup, skips valid prefix commands, calls `staff_guild.get_ticket()` or `staff_guild.create_ticket()`.

**`StaffGuild`** owns channel setup and access. **`TicketView`** is the runtime handle for an open ticket — message relay, DM delivery, layout building.

`create_ticket()`: creates a channel/thread → builds `TicketModel` (12-char random `key`) → persists → creates `TicketView` → `view.open()` posts log entry, staff info layout (account age, shared servers, past count), and "opened" DM layout.

**Message relay**: `process_dm_message()` (DM → staff) and `process_reply_message()` (staff → DM) both build Component v2 layouts (`discord.ui.LayoutView`/`Container`). Failed deliveries mark recipients `unreachable` (retried after 30 min). Accent colors encode message type (green=reply, red=close, blurple=DM, yellow=internal).

**Closure**: `TicketView.close()` marks in DB, spawns `_delete_channel()` (delete or archive/lock thread) and `_update_log()` (edits log entry). Channel/thread deletion listeners also trigger `closed_by_deletion`.

## Backends (`modmail/backends/`)

`create_db_client(config)` maps `database_type` → `DBClient(SQLBackend(config))` or `DBClient(MongoDBBackend(config))`. `DBClient` wraps a `DBBackend`, provides in-memory caches (`profiles`, `settings`) and an instance lock. All persistence goes through `DBClient` methods.

Shared Pydantic models in `common/models/`: `TicketModel`, `TicketMessageModel`, `TicketDMMessageModel`, `TicketUserModel`, `ProfileModel`, `SettingsModel`, `ActivityModel`, `InstanceLockModel`. Both backends persist the same models — **update both when changing persistence**.

## Config loading

`config/loader.py` reads YAML → `Config(**data)`. `Config` extends `pydantic_settings.BaseSettings` — env vars override file values (prefix `modmail__`, delimiter `__`). SQL driver suffix is auto-injected (`postgresql://...` → `postgresql+asyncpg://...`).

## Localization

Fluent (FTL) in `modmail/locales/<lang>/main.ftl` (`en`, `de`). `modmail/core/translator.py` — `Translator` (implements `discord.app_commands.Translator`), `_()` helper, `locale_for()`. Translator is set on `bot.tree` in `setup_hook()`.

## Other gotchas

- SQL migrations: `uv run alembic revision --autogenerate -m "description"`. Post-write hooks auto-format via ruff.
- `Bot.run()` raises `NotImplementedError` — always use `Bot.run_bot()`.
- Callback function names should end with `_command` — `Bot.add_command()` logs a debug warning if not.
