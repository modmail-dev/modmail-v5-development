"""Ephemeral interaction scope helpers for Modmail.

Provides `using_ephemeral` and `ephemeral_scope` to manage whether an
interaction's responses should be ephemeral.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    import discord

__all__ = [
    "ephemeral_scope",
    "using_ephemeral",
]

_interaction_scope: ContextVar[dict[int, bool]] = ContextVar("modmail_interaction_scope")


def using_ephemeral(interaction: discord.Interaction | None) -> bool:
    """Return `True` if `interaction` was declared ephemeral.

    Args:
        interaction: The Discord interaction to check, or `None`.

    Returns:
        `True` if [`ephemeral_scope`][] is active for this interaction.
    """
    if interaction is None or interaction.is_expired():
        return False
    return _interaction_scope.get({}).get(interaction.id, False)


@contextmanager
def ephemeral_scope(interaction: discord.Interaction | None) -> Generator[None]:
    """Mark `interaction`'s responses as ephemeral for the block.

    Within the block [`using_ephemeral`][] returns `True`.
    """
    if interaction is None or interaction.is_expired():
        yield
        return

    current = _interaction_scope.get({})
    token = _interaction_scope.set({**current, interaction.id: True})
    try:
        yield
    finally:
        _interaction_scope.reset(token)
