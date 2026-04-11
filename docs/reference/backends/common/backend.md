# DBBackend

::: modmail.backends.common.db_backend
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
        - "^_connect$"
        - "^_disconnect$"
