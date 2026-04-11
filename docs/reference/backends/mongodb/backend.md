# Backend

[`MongoDBBackend`][modmail.backends.mongodb.backend.MongoDBBackend]{ data-preview } composes four domain mixins
that each handle one area of persistence (lock, settings, profiles, tickets).

::: modmail.backends.mongodb.backend
    options:
      filters:
        - "!^_[^_]"
        - "!^__all__$"
        - "!^logger$"
        - "^_connect$"
        - "^_disconnect$"


## Domain Mixins

::: modmail.backends.mongodb._lock
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

::: modmail.backends.mongodb._settings

::: modmail.backends.mongodb._profiles

::: modmail.backends.mongodb._tickets

::: modmail.backends.mongodb._base
    options:
      filters:
        - "!^_[^_]"
        - "!^__all__$"
        - "!^logger$"
        - "^_mongodb_config$"
