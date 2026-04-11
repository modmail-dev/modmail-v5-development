## Overview

Modmail is a Discord DM-based support ticket bot. It routes user DMs into staff channels/threads and supports interchangeable MongoDB and SQL backends. The codebase is async-first and structured as a Python package under `modmail/`.

## Structure

- Core runtime and Discord integration live in `modmail/core/` (bot, permissions, translator, internal helpers).
- Persistence is abstracted behind `modmail/backends/common/` (`DBBackend`, `DBClient`, shared models) with concrete implementations in `modmail/backends/mongodb/` and `modmail/backends/sql/`.
- Configuration models and loading logic live in `modmail/config/`.
- Discord-facing behavior is in `modmail/cogs/modmail/` (modmail flows) and `modmail/cogs/utility/` (utility commands).
- Localization resources are in `modmail/locales/<lang>/main.ftl`, wired via `modmail/core/translator.py`.
- Support modules: `modmail/logging.py`, `modmail/utils.py`, `modmail/errors.py`, `modmail/enum.py`, and `modmail/__main__.py` as entrypoint.

## Tickets and Data

- DMs are received by listeners in `modmail/cogs/modmail/listeners/`, which create or look up tickets via `StaffGuild` and the database client.
- Staff interact through commands in `modmail/cogs/modmail/commands/` (e.g. setup, reply, close).
- Ticket, message, user/profile, settings, activity, and instance-lock models are defined in `modmail/backends/common/models/` and mirrored in both backends. When changing persistence, update **both** Mongo and SQL implementations and keep `DBBackend` the single interface.

## Configuration and Environment

- Configuration is loaded from YAML via `modmail/config/loader.py` into Pydantic models under `modmail/config/models/`.
- Use configuration (not hardcoded values) for bot token, DB URIs, guild/channel IDs, and locale. Never commit real secrets; only example configs belong in VCS.

## Docs and Docstrings

Docs are built with **Zensical** + **mkdocstrings-python** (griffe). Config: `zensical.toml`. The `docs/` directory contains `:::` stubs — source docstrings are the API reference. Use **Google style**.

Attribute descriptions — write for the *user*, not the implementer:
- No trivial descriptions: `bot_id: The bot ID.` is bad; `bot_id: Discord application ID.` is the minimum.
- No implementation details (ORM internals, storage format, index notes, loading strategy) — these belong in the class docstring, not per-attribute.
- No semicolons; use parenthetical style e.g. `(``None`` if unset)`.
- Stay within the 115-char line limit.

Cross-references — use `[Name][]` (**not** RST `:class:`Name`` — griffe renders it as literal text):
- `` [`ClassName`][] ``, `` [`DBBackend`][modmail.backends.common.db_backend.DBBackend] ``, `` [`discord.Guild`][] ``

Unrecognized section names become admonition boxes: `Note:`, `Warning:`, `Tip:`, `Danger:`, etc.

## General Behaviour

- Be conservative with tokens and tool calls: read only what's needed, don't re-read files already in context, avoid unnecessary exploration.
- Use web search freely — it's cheap and preferred over guessing at external API behaviour.

## Workflows for Claude Code

When working in this repo:

1. Restate the goal and identify relevant modules using the structure above.
2. Consult the corresponding code/docstrings; for external packages or unfamiliar problems, search public API docs or the web before coding.
3. Propose a short plan listing affected files, then implement in small, reviewable changes.
4. Use the existing patterns:
   - Go through `DBClient` for persistence.
   - Use enums from `modmail/enum.py` and errors from `modmail/errors.py`.
   - Keep async I/O non-blocking and follow existing cog patterns.
   - Use Python **3.14+ syntax** in line with the existing code.
5. Run tools before considering work done:
   - `uv run ruff check --fix && uv run ruff format`
   - `uv run pyright`

## Quirks and Warnings

- Tests in this project are currently **obsolete**; do not use them as a source of truth.
- Treat migrations and instance-lock logic with care; avoid destructive schema or data changes without explicit human confirmation and a migration plan.
- No suppression comments: never add `# noqa`, `# type: ignore`, or `# pyright: ignore`; leave errors for a human to decide.
