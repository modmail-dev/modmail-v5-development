"""Listeners for the modmail-related events.

This module contains all listeners for the modmail bot. Listeners are functions that
respond to specific events in the Discord API. Each listener is responsible for
handling a specific type of event, such as receiving a direct message or a reaction
to a message.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .dm_receive import dm_receive
from .thread_channel_delete import thread_channel_delete

all_listeners: list[Callable[..., Any]] = [
    dm_receive,
    thread_channel_delete,
]
