# Backends

The database abstraction layer consists of two collaborating abstractions:

- [`DBClient`][modmail.backends.common.db_client.DBClient]{ data-preview } — owns all in-memory caches and the public API consumed by the rest of the bot. Delegates persistence work to a [`DBBackend`][modmail.backends.common.db_backend.DBBackend]{ data-preview }.
- [`DBBackend`][modmail.backends.common.db_backend.DBBackend]{ data-preview } — abstract base class for backend implementations, composed from four domain mixins (lock, settings, profiles, tickets).

The active backend is selected at startup from `config.yaml` and is never swapped at runtime.

## Implementations

| Backend                     | Module                     | Storage                                                   |
|-----------------------------|----------------------------|-----------------------------------------------------------|
| [Common](common/index.md)   | `modmail.backends.common`  | Shared interfaces and models used by both implementations |
| [MongoDB](mongodb/index.md) | `modmail.backends.mongodb` | Beanie ODM on top of Motor / MongoDB                      |
| [SQL](sql/index.md)         | `modmail.backends.sql`     | SQLAlchemy 2 async + Alembic                              |

!!! note "Instance lock"
    All backends implement a distributed instance lock (`_lock` mixin + [`InstanceLockModel`][modmail.backends.common.models.instance_lock_model.InstanceLockModel]{ data-preview }) to prevent two processes from running against the same database simultaneously.
