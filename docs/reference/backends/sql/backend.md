# Backend

[`SQLBackend`][modmail.backends.sql.backend.SQLBackend]{ data-preview } composes four domain mixins
that each handle one area of persistence (lock, settings, profiles, tickets).

::: modmail.backends.sql.backend
    options:
      filters:
        - "!^_[^_]"
        - "!^__all__$"
        - "!^logger$"
        - "^_connect$"
        - "^_disconnect$"
        - "^_SUPPORTED_DIALECTS$"


## Domain Mixins

::: modmail.backends.sql._lock
    options:
      filters:
        - "!^_[^_]"
        - "!^__all__$"
        - "!^logger$"
        - "^_try_insert_lock$"
        - "^_read_lock$"
        - "^_try_takeover_lock$"
        - "^_delete_lock$"
        - "^_update_heartbeat$"
        - "^_acquire_instance_lock$"

::: modmail.backends.sql._settings

::: modmail.backends.sql._profiles

::: modmail.backends.sql._tickets

::: modmail.backends.sql._base
    options:
      filters:
        - "!^_[^_]"
        - "!^__all__$"
        - "!^logger$"
        - "^_sql_config$"
