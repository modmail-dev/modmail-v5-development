# Modmail

A Discord DM-based support ticket bot, built for reliability and flexibility.

Modmail v5 routes user DMs into dedicated staff channels or forum threads, keeping support organized and auditable. It ships two interchangeable database backends and a full Fluent i18n system.

## Key features

- **Dual-mode tickets** — forum-thread or channel-per-ticket layout
- **Swappable backends** — MongoDB (Beanie ODM) or SQL (SQLAlchemy + Alembic), selected at runtime
- **Hybrid commands** — prefix and slash commands from the same definition via `LazyHybridCommand`
- **Fluent i18n** — all user-facing strings in FTL translation files, zero hardcoded text
- **Strict config** — Pydantic models validated at startup, clear errors on misconfiguration
- **Instance locking** — distributed lock prevents split-brain when multiple bot processes start

## API reference

| Section                                 | Description                                                                         |
|-----------------------------------------|-------------------------------------------------------------------------------------|
| [Backends](reference/backends/index.md) | DB abstraction layer — `DBClient`, `DBBackend`, and the MongoDB/SQL implementations |
| [Cogs](reference/cogs/index.md)         | Ticket commands, reply/close workflow, and event listeners                          |
| [Config](reference/config.md)           | Pydantic settings models and YAML loader                                            |
| [Core](reference/core.md)               | Bot class, translator, permission system, and shared internals                      |
| [Misc](reference/misc.md)               | Enums, errors, logging, and utilities                                               |

!!! tip "Setup & configuration"
    See the [repository](https://github.com/modmail-dev/modmail) for installation instructions, `config.yaml` reference, and deployment guides.
