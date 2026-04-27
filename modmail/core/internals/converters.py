"""Custom converters and transformers for command arguments.

Provides [`Str`][] (whitespace-stripping string converter) and
[`ProfileLookup`][] (a converter that resolves a Discord mentionable to a
[`ProfileResult`][] carrying both the Discord object and its database profile)
for use in hybrid commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

import discord
from discord.ext import commands

from modmail import utils
from modmail.enum import ProfileType
from modmail.errors import LocalizedBadArgumentError

from ..translator import _

if TYPE_CHECKING:
    from discord import Interaction

    from modmail.backends.common import ProfileModel


__all__ = ["ProfileLookup", "ProfileResult", "Str"]


type Str = Annotated[str, StrStripConverter]
type ProfileLookup = Annotated[ProfileResult, _ProfileResultTransformer]


class StrStripConverter(discord.app_commands.Transformer, commands.Converter[str]):
    """Converter that strips leading and trailing whitespace from a string argument.

    Used as the annotation target for [`Str`][], so both prefix and slash
    commands receive a trimmed value without any extra handling in the command body.
    """

    async def convert(self, ctx: commands.Context[Any], argument: str) -> str:
        """Prefix-command path: strip whitespace from a raw argument string.

        Args:
            ctx: The command context.
            argument: The raw argument string supplied by the user.

        Returns:
            The argument with leading and trailing whitespace removed.
        """
        return argument.strip()

    async def transform(self, interaction: Interaction, value: str) -> str:
        """Slash-command path: strip whitespace from a resolved string option.

        Args:
            interaction: The Discord interaction.
            value: The string option value supplied by the user.

        Returns:
            The value with leading and trailing whitespace removed.
        """
        return value.strip()


@dataclass
class ProfileResult:
    """A resolved Discord mentionable together with its database profile.

    Returned by the [`ProfileLookup`][] converter. Bundles the Discord object
    and the profile in a single value so commands do not need to perform a
    second database lookup.
    """

    entity: discord.Member | discord.User | discord.Role
    """The resolved Discord member, user, or role."""

    profile: ProfileModel | None
    """The profile fetched from the database (`None` when no profile exists yet)."""

    @property
    def profile_type(self) -> ProfileType:
        """Whether the target is a user or role profile.

        Returns:
            [`ProfileType.role`][modmail.enum.ProfileType.role] for roles,
            [`ProfileType.user`][modmail.enum.ProfileType.user] otherwise.
        """
        return ProfileType.role if isinstance(self.entity, discord.Role) else ProfileType.user


class _ProfileResultTransformer(discord.app_commands.Transformer, commands.Converter[ProfileResult]):
    """Converter that resolves a Discord mentionable to a [`ProfileResult`][].

    Both the prefix and slash paths reject bot users and bot-managed roles by
    raising [`discord.ext.commands.BadArgument`][].
    """

    @property
    def type(self) -> discord.AppCommandOptionType:
        """Discord option type used for slash commands — `mentionable`."""
        return discord.AppCommandOptionType.mentionable

    async def convert(self, ctx: commands.Context[Any], argument: str) -> ProfileResult:
        """Prefix-command path: parse a string into a mentionable and look up its profile.

        Tries [`commands.RoleConverter`][discord.ext.commands.RoleConverter],
        [`commands.MemberConverter`][discord.ext.commands.MemberConverter],
        then [`commands.UserConverter`][discord.ext.commands.UserConverter] in order.

        Args:
            ctx: The command context.
            argument: The raw argument string (a mention, name, or ID).

        Returns:
            A [`ProfileResult`][] for the resolved mentionable.

        Raises:
            LocalizedBadArgumentError: When the string cannot be resolved to a known
                member, user, or role, or when the target is a bot or bot-managed role.
        """
        entity: discord.Member | discord.User | discord.Role | None = None
        for converter_cls in (commands.RoleConverter, commands.MemberConverter, commands.UserConverter):
            try:
                entity = await converter_cls().convert(ctx, argument)
                break
            except commands.BadArgument:
                continue

        if entity is None:
            raise LocalizedBadArgumentError(_("ftl-error-converter-profile-not-found", argument=argument))

        if utils.is_bot(entity):
            raise LocalizedBadArgumentError(_("ftl-error-converter-profile-is-bot"))

        profile_type = ProfileType.role if isinstance(entity, discord.Role) else ProfileType.user
        profile = ctx.bot.database_client.get_profile(entity.id, profile_type)
        return ProfileResult(entity=entity, profile=profile)

    async def transform(
        self, interaction: Interaction[Any], value: discord.Member | discord.User | discord.Role
    ) -> ProfileResult:
        """Slash-command path: wrap the resolved mentionable with its profile.

        Args:
            interaction: The Discord interaction.
            value: The mentionable resolved by Discord.

        Returns:
            A [`ProfileResult`][] for the resolved mentionable.

        Raises:
            LocalizedBadArgumentError: When the target is a bot or bot-managed role.
        """
        if utils.is_bot(value):
            raise LocalizedBadArgumentError(_("ftl-error-converter-profile-is-bot"))

        profile_type = ProfileType.role if isinstance(value, discord.Role) else ProfileType.user
        profile = interaction.client.database_client.get_profile(value.id, profile_type)
        return ProfileResult(entity=value, profile=profile)
