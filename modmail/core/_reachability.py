"""In-memory tracker for recipient DM reachability, with lazy expiry."""

from __future__ import annotations

from datetime import timedelta
from time import monotonic

__all__ = ["ReachabilityRegistry"]


class ReachabilityRegistry:
    """In-memory tracker for whether a recipient's DM channel is reachable.

    Stores a monotonic timestamp per user ID when a DM delivery fails.
    Entries auto-expire after the timeout; any [`is_reachable`][] call sweeps
    all stale entries in one dict rebuild for efficient cleanup.
    """

    _TIMEOUT = int(timedelta(minutes=30).total_seconds())

    def __init__(self) -> None:
        self._unreachable: dict[int, int] = {}

    def is_reachable(self, user_id: int) -> bool:
        """Whether the bot should attempt to DM this user.

        Sweeps all expired entries before checking, so any call doubles as
        garbage collection for the entire registry.

        Args:
            user_id: Discord snowflake ID of the user.

        Returns:
            bool: `True` if a DM delivery should be attempted.
        """
        self._sweep()
        return user_id not in self._unreachable

    def mark_unreachable(self, user_id: int) -> None:
        """Record that a DM delivery to this user has failed.

        Args:
            user_id: Discord snowflake ID of the user.
        """
        self._unreachable[user_id] = int(monotonic())

    def mark_reachable(self, user_id: int) -> None:
        """Clear any unreachable record for this user.

        Called when the user proves reachability by sending a DM.  Also
        serves as explicit garbage collection so an inactive user does not
        linger until the next sweep.

        Args:
            user_id: Discord snowflake ID of the user.
        """
        self._unreachable.pop(user_id, None)

    def _sweep(self) -> None:
        """Rebuild the internal dict, dropping entries older than the timeout."""
        now = int(monotonic())
        self._unreachable = {uid: ts for uid, ts in self._unreachable.items() if now - ts <= self._TIMEOUT}
