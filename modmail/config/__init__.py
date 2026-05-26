"""Pydantic models, live ConfigStore, and the global config singleton.

All modmail code that needs the bot configuration should import `config`
from this package:

    from modmail.config import config
"""

from __future__ import annotations

from typing import Any, cast

from ._store import BatchOp, BatchOps, ConfigKeyEntry, ConfigStore, MutOp, SetOp, UnsetOp
from .models import Config

__all__ = [
    "BatchOp",
    "BatchOps",
    "Config",
    "ConfigKeyEntry",
    "ConfigProxy",
    "ConfigStore",
    "MutOp",
    "SetOp",
    "UnsetOp",
    "config",
    "get_store",
    "set_store",
]


class ConfigProxy:
    """Always-available proxy that forwards to `ConfigStore.model`.

    Behaves identically to a [`Config`][] instance for reading: attribute
    access, `repr` and `dir` all delegate. Writing is blocked
    -- use [`ConfigStore.update`][] to modify config.
    """

    def __init__(self) -> None:
        """Initialize the proxy with no store attached."""
        self._store: ConfigStore | None = None

    def set_store(self, store: ConfigStore) -> None:
        """Set the active ConfigStore for this proxy.

        Args:
            store: The ConfigStore instance to use for forwarding attribute access.
        """
        self._store = store

    def get_store(self) -> ConfigStore:
        """Return the active ConfigStore for this proxy.

        Raises:
            RuntimeError: If `set_store` has not been called yet.
        """
        if self._store is None:
            raise RuntimeError("config is not loaded, did you start the bot with modmail.run_bot()?")
        return self._store

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the underlying Config model.

        Returns:
            The attribute value from the live Config model.

        Raises:
            RuntimeError: If `set_store` has not been called yet.
        """
        if self._store is None:
            raise RuntimeError("config is not loaded, did you start the bot with modmail.run_bot()?")
        return getattr(self._store.model, name)

    def __repr__(self) -> str:
        """Return a string representation of the underlying Config."""
        if self._store is None:
            return f"<{self.__class__.__name__} (not loaded)>"
        return repr(self._store.model)

    def __dir__(self) -> list[str]:
        """Return the list of attributes from the underlying Config."""
        if self._store is None:
            return []
        return dir(self._store.model)


_proxy = ConfigProxy()
config: Config = cast("Config", cast("object", _proxy))


def set_store(store_instance: ConfigStore) -> None:
    """Register the active ConfigStore.

    Args:
        store_instance: The loaded ConfigStore to bind.
    """
    _proxy.set_store(store_instance)


def get_store() -> ConfigStore:
    """Return the active ConfigStore.

    Use this instead of importing `store` directly, which captures the
    value at import time (likely `None` before `set_store` is called).

    Returns:
        The active ConfigStore.

    Raises:
        RuntimeError: If `set_store` has not been called yet.
    """
    return _proxy.get_store()
