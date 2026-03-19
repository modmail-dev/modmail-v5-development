# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Modmail v5 is a complete rewrite of the Modmail Discord bot (alpha/WIP). It manages support tickets between users and Discord server staff via DM-based modmail. Requires Python 3.14+, uses `uv` as the package manager.

## Commands

### Setup
```bash
# Install with SQLite backend
uv sync --locked --compile-bytecode --no-default-groups --extra speed --extra sqlite

# Install with MongoDB backend
uv sync --locked --compile-bytecode --no-default-groups --extra speed --extra mongodb
```

### Run
```bash
uv run python start.py
# or
python -m modmail
```

### Lint & Format
```bash
uv run pre-commit run --all-files   # Run all pre-commit hooks
uv run ruff check --fix modmail tests
uv run ruff format modmail tests
uv run isort modmail tests
```

### Type Check
```bash
uv run pyright
```

### Tests (Not Yet Implemented)
```bash
uv run pytest
uv run pytest tests/test_utils.py   # Run a single test file
uv run pytest -k "test_name"        # Run a specific test
uv run pytest --cov=modmail --cov-report html
uv run tox                          # Run all tox environments (lint, type, py3.14)
```

## Architecture

### Module Structure
```
modmail/
├── backends/          # Database abstraction layer
│   ├── common/        # Abstract base class & shared models
│   ├── mongodb/       # Beanie ODM implementation
│   └── sql/           # SQLAlchemy + aiosqlite implementation
├── config/            # Pydantic config models + YAML loader
├── core/              # Bot class, translator, permissions
│   └── internals/     # Cog base, command types, UI views, embeds
├── cogs/
│   ├── modmail/       # Core ticket logic (commands + listeners)
│   └── utility/       # about, status, profile commands
└── locales/           # Fluent FTL translation files (en, de)
```

### Key Design Patterns

**Database Abstraction**: `DBClientBase` in `backends/common/client_base.py` defines the interface. Both SQL and MongoDB clients implement this. The active backend is selected via `config.yaml`.

**Ticket Flow**:
1. User DMs bot → `cogs/modmail/listeners/dm_receive.py` intercepts
2. `core/internals/staff_guild.py` creates a channel or forum thread in the staff server
3. Database stores ticket state via the active backend client
4. Staff reply via commands in `cogs/modmail/commands/`

**Localization**: Fluent FTL format (`locales/en/main.ftl`). All user-facing strings go through `core/translator.py`. Commands use `LazyHybridCommand` (`core/internals/command.py`) supporting both prefix and slash commands.

**Cog Base**: Custom `Cog` class in `core/internals/cog.py` with enhanced send/reply helpers and access to the translator.

### Config
Copy `config.yaml.example` → `config.yaml`. Required fields: `bot.token`, `bot.staff_server_id`, `log_url`. Database backend is configured under the `database` key.

### Testing Notes
Tests are currently undergoing a rewrite. Pyright runs in strict mode but excludes the `tests/` directory. Pre-commit hooks enforce isort + ruff formatting on every commit.
