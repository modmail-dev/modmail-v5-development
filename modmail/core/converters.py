"""Argument converters for both prefix and slash commands.

Exports [`Str`][] (whitespace-stripping), [`ProfileLookup`][] (mentionable → profile),
and [`ProfileResult`][] for use in hybrid commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

import discord
from discord.ext import commands

from .. import utils
from ..enum import ProfileType
from ..errors import LocalizedBadArgumentError
from ..i18n import _

if TYPE_CHECKING:
    from discord import Interaction

    from modmail.backends.common import ProfileModel


__all__ = ["ProfileLookup", "ProfileResult", "Str"]


type Str = Annotated[str, StrStripConverter]
type ProfileLookup = Annotated[ProfileResult, _ProfileResultTransformer]


class StrStripConverter(discord.app_commands.Transformer, commands.Converter[str]):
    """Strips leading and trailing whitespace from a string argument.

    Used as the annotation target for [`Str`][], transparent to both prefix and slash commands.
    """

    async def convert(self, ctx: commands.Context[Any], argument: str) -> str:
        """Return the argument with surrounding whitespace stripped (prefix path).

        Args:
            ctx: The command context.
            argument: Raw argument string supplied by the user.

        Returns:
            Trimmed argument string.
        """
        return argument.strip()

    async def transform(self, interaction: Interaction, value: str) -> str:
        """Return the value with surrounding whitespace stripped (slash path).

        Args:
            interaction: The Discord interaction.
            value: String option value supplied by the user.

        Returns:
            Trimmed value string.
        """
        return value.strip()


@dataclass
class ProfileResult:
    """Resolved Discord mentionable paired with its database profile.

    Returned by [`ProfileLookup`][]. Commands receive both objects without an extra database call.
    """

    entity: discord.Member | discord.User | discord.Role
    """The resolved Discord member, user, or role."""
    profile: ProfileModel | None
    """Database profile (`None` when no profile exists yet)."""

    @property
    def profile_type(self) -> ProfileType:
        """[`ProfileType.role`][] for roles, [`ProfileType.user`][] otherwise."""
        return ProfileType.role if isinstance(self.entity, discord.Role) else ProfileType.user


class _ProfileResultTransformer(discord.app_commands.Transformer, commands.Converter[ProfileResult]):
    """Resolves a Discord mentionable to a [`ProfileResult`][].

    Rejects bot users and bot-managed roles with [`LocalizedBadArgumentError`][].
    """

    @property
    def type(self) -> discord.AppCommandOptionType:
        """Slash command option type — `mentionable`."""
        return discord.AppCommandOptionType.mentionable

    async def convert(self, ctx: commands.Context[Any], argument: str) -> ProfileResult:
        """Resolve a string argument to a [`ProfileResult`][] (prefix path).

        Tries [`RoleConverter`][discord.ext.commands.RoleConverter], then
        [`MemberConverter`][discord.ext.commands.MemberConverter], then
        [`UserConverter`][discord.ext.commands.UserConverter] in order.

        Args:
            ctx: The command context.
            argument: Raw argument string (a mention, name, or ID).

        Returns:
            A [`ProfileResult`][] for the resolved mentionable.

        Raises:
            LocalizedBadArgumentError: When the argument cannot be resolved, or targets a bot.
        """
        entity: discord.Member | discord.User | discord.Role | None = None
        for converter_cls in (commands.RoleConverter, commands.MemberConverter, commands.UserConverter):
            try:
                entity = await converter_cls().convert(ctx, argument)
                break
            except commands.BadArgument:
                continue

        if entity is None:
            # @param argument: The search term provided by the user
            raise LocalizedBadArgumentError(_("error.profile.not_found", argument=argument))

        if utils.is_bot(entity):
            raise LocalizedBadArgumentError(_("error.profile.is_bot"))

        profile_type = ProfileType.role if isinstance(entity, discord.Role) else ProfileType.user
        profile = ctx.bot.database_client.get_profile(entity.id, profile_type)
        return ProfileResult(entity=entity, profile=profile)

    async def transform(
        self, interaction: Interaction[Any], value: discord.Member | discord.User | discord.Role
    ) -> ProfileResult:
        """Wrap the already-resolved mentionable with its profile (slash path).

        Args:
            interaction: The Discord interaction.
            value: The mentionable already resolved by Discord.

        Returns:
            A [`ProfileResult`][] for the resolved mentionable.

        Raises:
            LocalizedBadArgumentError: When the target is a bot or bot-managed role.
        """
        if utils.is_bot(value):
            raise LocalizedBadArgumentError(_("error.profile.is_bot"))

        profile_type = ProfileType.role if isinstance(value, discord.Role) else ProfileType.user
        profile = interaction.client.database_client.get_profile(value.id, profile_type)
        return ProfileResult(entity=value, profile=profile)
