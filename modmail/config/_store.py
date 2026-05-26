"""Manages the live Config model and persistence."""

from __future__ import annotations

import asyncio
import copy
import enum
import logging
import os
import tomllib
from dataclasses import dataclass
from types import NoneType, UnionType
from typing import TYPE_CHECKING, Annotated, Any, Literal, Union, get_args, get_origin

import pydantic
import tomli_w
from pydantic import BaseModel, SecretStr

from ..errors import ConfigUpdateError
from .models import Config

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "BatchOp",
    "BatchOps",
    "ConfigKeyEntry",
    "ConfigStore",
    "MutOp",
    "SetOp",
    "UnsetOp",
]


@dataclass
class ConfigKeyEntry:
    """A discovered config key with its static metadata."""

    path: str
    """Full dotted config key path (e.g. `bot.prefix`)."""
    type_repr: str
    """Human-readable type representation (e.g. `str`, `SecretStr`)."""
    description: str
    """Field description from the Pydantic model."""
    settable: bool = True
    """Whether this key can be changed via a config command."""


class MutOp(enum.Enum):
    """Discriminator for collection mutation operations."""

    ADD = enum.auto()
    """Add an element to a set."""
    REMOVE = enum.auto()
    """Remove an element from a set."""
    ADD_DICT = enum.auto()
    """Set a key-value pair in a dict."""
    REMOVE_DICT = enum.auto()
    """Delete a key from a dict."""


type BatchOps = list[
    tuple[Literal[MutOp.ADD], str]
    | tuple[Literal[MutOp.REMOVE], str]
    | tuple[Literal[MutOp.ADD_DICT], str, str]
    | tuple[Literal[MutOp.REMOVE_DICT], str]
]


@dataclass
class SetOp:
    """Replace a config key with a single parsed value."""

    value: object = None


@dataclass
class UnsetOp:
    """Restore a config key to its Pydantic default."""


@dataclass
class BatchOp:
    """A sequence of collection mutations applied atomically."""

    items: BatchOps


def _values_match(stored: object, raw: str) -> bool:
    """Case-insensitive matching for removal comparisons.

    Compares *stored* (a typed value from the config) against *raw* (a
    user-provided string). Handles special types that `str()` renders
    poorly: `bytes` is decoded.

    Returns:
        `True` when the values match (same key/value).
    """
    norm = raw.casefold()
    if isinstance(stored, SecretStr):
        return stored.get_secret_value().casefold() == norm
    if isinstance(stored, bytes):
        return stored.decode("utf-8", errors="replace").casefold() == norm
    return str(stored).casefold() == norm


class _ConfigStoreMeta(type):
    """Metaclass that enforces a single [`ConfigStore`][] instance."""

    def __call__(cls, file_path: Path) -> ConfigStore:
        if ConfigStore.instance is not None:
            if ConfigStore.instance.path != file_path:
                raise RuntimeError("ConfigStore instance already exists with a different path.")
            return ConfigStore.instance
        instance = super().__call__(file_path)
        ConfigStore.instance = instance
        return instance


class ConfigStore(metaclass=_ConfigStoreMeta):
    """Manages the live [`Config`][] model -- loading, updating, persisting.

    The metaclass enforces a singleton so `ConfigStore(path)` always
    returns the same instance.
    """

    instance: ConfigStore | None = None
    _keys: list[ConfigKeyEntry] | None = None

    def __init__(self, file_path: Path) -> None:
        self.path = file_path
        self._lock: asyncio.Lock = asyncio.Lock()
        self._raw = self._load_toml()
        self.model = Config(**self._raw)

    @property
    def model(self) -> Config:
        return self._model

    @model.setter
    def model(self, value: Config) -> None:
        self._model = value
        from ..logging import setup_logging

        setup_logging(value.logging)

    @classmethod
    def keys(cls) -> list[ConfigKeyEntry]:
        """List all discoverable config keys with their static metadata.

        Returns:
            All writable config keys as [`ConfigKeyEntry`][] instances.
        """
        if cls._keys is None:
            cls._keys = sorted(cls._walk_fields(Config, ""), key=lambda e: e.path)
        return cls._keys

    @staticmethod
    def _is_settable(key: str) -> bool:
        # TODO: Allow setting logging, need to reload logging on update
        return not any(
            key == f or key.startswith(f + ".") for f in ("version", "bot.token", "database", "logging")
        )

    def _load_toml(self) -> dict[str, Any]:
        """Read and parse a TOML config file.

        Returns:
            The parsed config data as a dict.

        Raises:
            OSError: If the file cannot be opened or read.
        """
        with self.path.open("rb") as f:
            return tomllib.load(f)

    def _save_toml(self, data: dict[str, Any]) -> None:
        """Serialize to TOML and atomically write to *file_path*.

        Writes to a temporary file first, then renames. This prevents
        corruption if the process crashes mid-write.

        Args:
            data: Config data dict to serialize.
        """
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("wb") as f:
            tomli_w.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)
        try:
            dir_fd = os.open(self.path.parent, os.O_DIRECTORY)
        except AttributeError, NotImplementedError, OSError:
            pass
        else:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        self._raw = data

    async def _apply_and_commit(self, key: str, op: SetOp | UnsetOp | BatchOp) -> Config:
        """Apply *op* to a copy of `_raw`, validate, persist, and update state.

        Returns:
            The freshly validated [`Config`][].

        Raises:
            ConfigUpdateError: If Pydantic validation fails or given an invalid operation.
        """
        keys = key.split(".")

        last_key_dict = new_raw = copy.deepcopy(self._raw)
        for k in keys[:-1]:
            last_key_dict.setdefault(k, {})
            last_key_dict = last_key_dict[k]
        last = keys[-1]

        if isinstance(op, SetOp):
            last_key_dict[last] = op.value
        elif isinstance(op, UnsetOp):
            last_key_dict.pop(last, None)
        elif op.items:
            kind = op.items[0][0]
            if kind is MutOp.ADD or kind is MutOp.REMOVE:
                if last not in last_key_dict:
                    last_key_dict[last] = []
                elif not isinstance(last_key_dict[last], list):
                    raise ConfigUpdateError(
                        "parse",
                        f"Expected a list at {'.'.join(keys)}, but found {type(last_key_dict[last]).__name__}",
                    )
            else:
                if last not in last_key_dict:
                    last_key_dict[last] = {}
                elif not isinstance(last_key_dict[last], dict):
                    raise ConfigUpdateError(
                        "parse",
                        f"Expected a dict at {'.'.join(keys)}, but found {type(last_key_dict[last]).__name__}",
                    )

            for child in op.items:
                match child:
                    case (MutOp.ADD, value):
                        last_key_dict[last].append(value)
                    case (MutOp.REMOVE, value):
                        last_key_dict[last] = [v for v in last_key_dict[last] if not _values_match(v, value)]
                    case (MutOp.ADD_DICT, key, value):
                        last_key_dict[last][key] = value
                    case (MutOp.REMOVE_DICT, key):
                        folded = key.casefold()
                        found = next((k for k in last_key_dict[last] if k.casefold() == folded), None)
                        if found is not None:
                            del last_key_dict[last][found]

        try:
            new_config = Config(**new_raw)
        except pydantic.ValidationError as e:
            logger.debug("Config validation error", exc_info=e)
            err = e.errors()[0]
            loc = ".".join(str(p) for p in err["loc"])
            raise ConfigUpdateError("validation", f"{loc}: {err['msg']} (got {err.get('input', '?')!r})") from e
        except Exception as e:
            logger.exception("Config validation raised unexpected error")
            raise ConfigUpdateError("validation", f"Unexpected error in config validation: {e}") from e

        self.model = new_config
        self._raw = new_raw
        self._save_toml(new_raw)
        return new_config

    async def update(self, key: str, operation: SetOp | UnsetOp | BatchOp) -> Config:
        """Apply a pre-parsed operation to a config key and persist.

        Args:
            key: Dot-separated config key path (e.g. `"bot.prefix"`).
            operation: A [`SetOp`][], [`UnsetOp`][], or [`BatchOp`][].

        Returns:
            The updated Config instance.

        Raises:
            ConfigUpdateError: If the key is read-only, the resulting
                config is invalid, or the operation cannot be applied.
        """
        if not key or not self._is_settable(key):
            raise ConfigUpdateError("readonly", f"Key {key!r} is read-only or invalid")

        async with self._lock:
            return await self._apply_and_commit(key, operation)

    async def reload(self) -> Config:
        """Re-read the config file from disk and re-validate.

        Returns:
            The new Config instance.
        """
        async with self._lock:
            data = self._load_toml()
            new_config = Config(**data)
            self._raw = data
            self.model = new_config
            return new_config

    @classmethod
    def _walk_fields(cls, model_cls: type[BaseModel], prefix: str) -> list[ConfigKeyEntry]:
        """Recursively collect field dot-paths, types, and descriptions.

        Args:
            model_cls: A [`pydantic.BaseModel`][] subclass.
            prefix: Dot-separated parent path (empty string for root).

        Returns:
            A list of [`ConfigKeyEntry`][] instances.
        """
        out: list[ConfigKeyEntry] = []
        for field_name, field_info in model_cls.model_fields.items():
            full = f"{prefix}.{field_name}" if prefix else field_name
            annotation = field_info.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                out.extend(cls._walk_fields(annotation, full))
            else:
                description = field_info.description or ""
                out.append(
                    ConfigKeyEntry(
                        path=full,
                        type_repr=cls._type_repr(annotation),
                        description=description,
                        settable=cls._is_settable(full),
                    )
                )
        return out

    @classmethod
    def _type_repr(cls, annotation: object) -> str:
        """Return a human-readable representation of *annotation*.

        Handles plain types (`int`), generic aliases (`set[int]`),
        `Annotated` wrappers, `Union` / `| None`, and dict types
        (`dict[str, RequiredAccessLevel]`).
        """
        origin = get_origin(annotation)
        if origin is Annotated:
            return cls._type_repr(get_args(annotation)[0])
        if origin in {Union, UnionType}:
            args = get_args(annotation)
            names = [cls._type_repr(a) for a in args if a is not NoneType]
            return " | ".join(names) if args else str(annotation)
        if origin in {set, list, frozenset}:
            inner_args = get_args(annotation)
            inner = cls._type_repr(inner_args[0]) if inner_args else "Any"
            return f"{origin.__name__}[{inner}]"
        if origin is dict:
            dict_args = get_args(annotation)
            k = cls._type_repr(dict_args[0]) if dict_args else "Any"
            v = cls._type_repr(dict_args[1]) if len(dict_args) > 1 else "Any"
            return f"dict[{k}, {v}]"
        if isinstance(annotation, type):
            return annotation.__name__
        return repr(annotation)
