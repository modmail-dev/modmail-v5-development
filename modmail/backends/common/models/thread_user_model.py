"""Defines the ThreadUserModel class for representing a user in a thread.

This module contains the ThreadUserModel class, which represents a user
involved in a thread. This model is used to store information about
users, including their ID and name.
"""

from __future__ import annotations

import discord
from pydantic import BaseModel, ConfigDict

__all__ = ["ThreadUserModel"]


class ThreadUserModel(BaseModel):
    """Represents a user involved in a thread.

    This model contains information about the user, including their ID and name.

    Attributes:
        user_id: The unique identifier of the user.
        user_name: The name of the user.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    user_id: int
    user_name: str

    @classmethod
    def from_user(cls, user: discord.User | discord.Member | discord.ClientUser) -> ThreadUserModel:
        """Creates a ThreadUserModel from a discord user or member.

        Args:
            user: The discord user or member.

        Returns:
            A ThreadUserModel instance.
        """
        return cls(user_id=user.id, user_name=user.name)
