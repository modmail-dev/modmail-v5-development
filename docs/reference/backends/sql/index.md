# SQL Backend

SQLAlchemy 2 async + Alembic implementation of the Modmail database backend. See [`_SUPPORTED_DIALECTS`][modmail.backends.sql.backend._SUPPORTED_DIALECTS] for supported database dialects.

| Page                      | Contents                                                                                  |
|---------------------------|-------------------------------------------------------------------------------------------|
| [Backend](backend.md)     | [`SQLBackend`][modmail.backends.sql.backend.SQLBackend]{ data-preview } and domain mixins |
| [Migration](migration.md) | Alembic migration runner executed at startup                                              |
| [Models](models.md)       | SQLAlchemy ORM table models for settings, profiles, tickets, and more                     |
