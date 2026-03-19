"""Listeners for the modmail-related events.

This module contains all listeners for the modmail bot. Listeners are functions that
respond to specific events in the Discord API. Each listener is responsible for
handling a specific type of event, such as receiving a direct message or a reaction
to a message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .dm_receive import dm_receive
from .ticket_channel_delete import ticket_channel_delete
from .ticket_thread_delete import ticket_thread_delete

if TYPE_CHECKING:
    from collections.abc import Callable

all_listeners: list[Callable[..., Any]] = [
    dm_receive,
    ticket_channel_delete,
    ticket_thread_delete,
]
