"""
modmail.cogs.utility.commands.profile
=====================================
This file implements profile management commands for the modmail bot. It defines
several commands for adding, removing, customizing profiles and interface for overriding permission access levels.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple, Type, cast

import discord
from discord.ext import commands

from modmail import CONFIG
from modmail.backends import Profile
from modmail.core import Bot, _, lazy_hybrid_group

__all__ = ["profile_command"]

from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType

if TYPE_CHECKING:
    from .. import Utility

    # A "stub" for type hinting
    class ProfileCustomizeView(discord.ui.View):
        _original_message: discord.Message | None

        def set_original_message(self, message: discord.Message) -> None: ...


logger = logging.getLogger(__name__)


class ProfileDetail(NamedTuple):
    mention: str
    profile_id: int
    profile_type: ProfileType | None


def _get_profile_detail(
    *, user_or_role: discord.User | discord.Role | None = None, id_: int | None = None
) -> ProfileDetail | None:
    """
    Get a sanitized ProfileDetail from the raw user/role/id_ command inputs.

    :param user_or_role: The discord User or Role when the type is known.
    :param id_: The profile's ID if type is unknown.
    :return: A ProfileDetail of the user/role/id_, None if no input was provided.
    """
    profile_mention: str
    profile_id: int
    profile_type: ProfileType | None

    if user_or_role is not None:
        profile_id = user_or_role.id
        if isinstance(user_or_role, discord.Role):
            if user_or_role.is_default():
                profile_mention = "@everyone"
            else:
                profile_mention = user_or_role.mention
            profile_type = ProfileType.role
        else:
            profile_mention = user_or_role.mention
            profile_type = ProfileType.user
    elif id_ is not None:
        profile_mention = f"`{id_}`"
        profile_id = id_
        profile_type = None
    else:
        return None
    return ProfileDetail(profile_mention, profile_id, profile_type)


async def make_profile_customize_view(
    cog: Utility, ctx: commands.Context[Bot], profile_detail: ProfileDetail, profile: Profile
) -> Type[ProfileCustomizeView]:
    """
    Create a view for customizing profiles.
    This view contains a "Customize" button and a select menu for choosing a permission access level.

    :param cog: The Utility cog instance.
    :param ctx: The context of the command.
    :param profile_detail: The profile detail of the profile.
    :param profile: The profile to customize.
    :return: A Discord.py UI view for customizing the profile.
    """
    ui_button_label = await cog.translate(ctx, _("ftl-view-profile-button-customize-label"))
    ui_select_level_placeholder = await cog.translate(ctx, _("ftl-view-profile-select-level-placeholder"))
    _LEVEL_NONE = "None"
    ui_select_level_options = [
        # An option to remove the access level for this profile
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-view-profile-select-level-option-none")), value=_LEVEL_NONE
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-access-level-everyone")), value=AccessLevel.everyone.name
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-access-level-staff")), value=AccessLevel.staff.name
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-access-level-manager")), value=AccessLevel.manager.name
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-access-level-admin")), value=AccessLevel.admin.name
        ),
    ]

    ui_title = await cog.translate(ctx, _("ftl-modal-profile-customize-title"))
    ui_colour_label = await cog.translate(ctx, _("ftl-modal-profile-customize-colour"))
    ui_tag_label = await cog.translate(ctx, _("ftl-modal-profile-customize-tag"))

    class ProfileCustomizeModal(discord.ui.Modal, title=ui_title):
        # TODO: Use default from current profile
        colour: discord.ui.TextInput[ProfileCustomizeModal] = discord.ui.TextInput(
            label=ui_colour_label, default="#000000", required=False
        )
        tag: discord.ui.TextInput[ProfileCustomizeModal] = discord.ui.TextInput(
            label=ui_tag_label, default="", required=False
        )

        def __init__(self, view: ProfileCustomizeView):
            super().__init__()
            self._view = view

        async def on_submit(self, interaction: discord.Interaction) -> None:
            print(self.colour, self.tag)
            # Disable the modal customize button
            button = cast(discord.ui.Button[ProfileCustomizeView], self._view.children[1])
            button.disabled = True
            # noinspection PyProtectedMember
            if self._view._original_message is not None:  # type: ignore[reportPrivateUsage]
                # noinspection PyProtectedMember
                await self._view._original_message.edit(view=self._view)  # type: ignore[reportPrivateUsage]

    # noinspection PyShadowingNames
    class ProfileCustomizeView(discord.ui.View):
        """
        A view for customizing the profile.
        """

        def __init__(self):
            super().__init__()
            self._original_message: discord.Message | None = None

        def set_original_message(self, message: discord.Message) -> None:
            """
            Set the original message that sent this view.

            :param message: The Discord.py message from the original .send().
            """
            self._original_message = message

        async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
            """
            Check if the interaction is from the user who invoked the command.
            """
            return interaction.user == ctx.author

        async def on_timeout(self) -> None:
            """
            Disable all components of this view when timed out.
            """
            for children in self.children:
                if hasattr(children, "disabled"):
                    children.disabled = True  # type: ignore[reportAttributeAccessIssue]

            if self._original_message is not None:
                await self._original_message.edit(view=self)

        @discord.ui.select(placeholder=ui_select_level_placeholder, options=ui_select_level_options)
        async def level_select(
            self, interaction: discord.Interaction, select: discord.ui.Select[ProfileCustomizeView]
        ) -> None:
            nonlocal profile

            selected_option = select.values[0]
            if selected_option == _LEVEL_NONE:
                selected_level: AccessLevel | None = None
            else:
                # noinspection PyTypeChecker
                selected_level = AccessLevel[selected_option]

            if profile.access_level != selected_level:
                new_profile = profile.model_copy(deep=True, update={"access_level": selected_level})
                await ctx.bot.database_client.update_profile(new_profile)
                logger.debug("Updated profile access level for %d to %s.", new_profile.profile_id, selected_level)
                profile = new_profile
            await interaction.response.send_message(
                await cog.translate(
                    ctx,
                    _("ftl-view-profile-select-level-success", name=profile_detail.mention, level=selected_level),
                ),
                ephemeral=True,
            )

            # Disable the select
            select = cast(discord.ui.Select[ProfileCustomizeView], self.children[0])
            select.disabled = True
            select.placeholder = next(option.label for option in select.options if option.value == selected_option)
            if self._original_message is not None:
                await self._original_message.edit(view=self)

        @discord.ui.button(label=ui_button_label, style=discord.ButtonStyle.primary)
        async def customize_button(
            self, interaction: discord.Interaction, button: discord.ui.Button[ProfileCustomizeView]
        ) -> None:
            await interaction.response.send_modal(ProfileCustomizeModal(self))

    return ProfileCustomizeView


@lazy_hybrid_group(
    name=_("ftl-cmd-profile-name"),
    fallback=_("ftl-cmd-profile-fallback-name"),
    description=_("ftl-cmd-profile-description"),
)
async def profile_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    View every profile.
    """
    ...


@profile_command.command(name=_("ftl-cmd-profile-add-name"), description=_("ftl-cmd-profile-add-description"))
async def profile_add_command(
    self: Utility, ctx: commands.Context[Bot], user_or_role: discord.User | discord.Role
) -> None:
    """
    Create a new profile for a user/role.
    """

    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the user/role already have a profile
    existing_profile = self.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if existing_profile is not None:
        await self.reply(ctx, _("ftl-cmd-profile-add-already-exists", name=profile_detail.mention))
        return

    new_profile = Profile(
        bot_id=CONFIG.bot.bot_id, profile_id=profile_detail.profile_id, profile_type=profile_detail.profile_type
    )
    await self.bot.database_client.update_profile(new_profile)

    view = (await make_profile_customize_view(self, ctx, profile_detail, new_profile))()
    message = await self.reply(ctx, _("ftl-cmd-profile-add-success", name=profile_detail.mention), view=view)
    view.set_original_message(message)


@profile_command.command(
    name=_("ftl-cmd-profile-delete-name"), description=_("ftl-cmd-profile-delete-description")
)
async def profile_delete_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.User | discord.Role,
    id_: int | None,  # in case role/user was deleted TODO: auto delete on bot start so this isn't necessary
) -> None:
    """
    Delete a profile associated with a user/role.
    """
    if user_or_role is not None and id_ is not None:
        await self.reply(ctx, _("ftl-cmd-profile-delete-both"))
        return

    profile_detail = _get_profile_detail(user_or_role=user_or_role, id_=id_)
    if profile_detail is None:
        await self.reply(ctx, _("ftl-cmd-profile-delete-none"))
        return

    await self.bot.database_client.delete_profile(profile_id=profile_detail.profile_id)
    await self.reply(ctx, _("ftl-cmd-profile-delete-success", name=profile_detail.mention))


@profile_command.command(
    name=_("ftl-cmd-profile-customize-name"), description=_("ftl-cmd-profile-customize-description")
)
async def profile_customize_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.User | discord.Role,
) -> None:
    """
    Customize a user/role's profile.
    """
    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the user/role has an existing profile
    profile = self.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if profile is None:
        # Create a new profile if it doesn't exist
        profile = Profile(
            bot_id=CONFIG.bot.bot_id,
            profile_id=profile_detail.profile_id,
            profile_type=profile_detail.profile_type,
        )
        await self.bot.database_client.update_profile(profile)

    view = (await make_profile_customize_view(self, ctx, profile_detail, profile))()
    message = await self.reply(ctx, _("ftl-cmd-profile-customize-message", name=profile_detail.mention), view=view)
    view.set_original_message(message)


@profile_command.command(name=_("ftl-cmd-profile-allow-name"), description=_("ftl-cmd-profile-allow-description"))
async def profile_allow_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.User | discord.Role,
    command_name: str,
) -> None:
    """
    Allow a user/role to use a specific command without having the required access level.
    """
    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the profile exists in the database
    profile = self.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if profile is None:
        # Create a new profile if it doesn't exist
        profile = Profile(
            bot_id=CONFIG.bot.bot_id,
            profile_id=profile_detail.profile_id,
            profile_type=profile_detail.profile_type,
        )

    # Update the overrides
    overrides = profile.permission_overrides.copy()
    overrides[command_name] = PermissionOverrideValue.allow
    new_profile = profile.model_copy(deep=True, update={"permission_overrides": overrides})

    await self.bot.database_client.update_profile(new_profile)
    await self.reply(ctx, _("ftl-cmd-profile-allow-success", name=profile_detail.mention, command=command_name))


@profile_command.command(name=_("ftl-cmd-profile-deny-name"), description=_("ftl-cmd-profile-deny-description"))
async def profile_deny_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.User | discord.Role,
    command_name: str,
) -> None:
    """
    Deny a user/role from using a specific command even if they have the required access level.
    """
    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the profile exists in the database
    profile = self.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if profile is None:
        # Create a new profile if it doesn't exist
        profile = Profile(
            bot_id=CONFIG.bot.bot_id,
            profile_id=profile_detail.profile_id,
            profile_type=profile_detail.profile_type,
        )

    # Update the overrides
    overrides = profile.permission_overrides.copy()
    overrides[command_name] = PermissionOverrideValue.deny
    new_profile = profile.model_copy(deep=True, update={"permission_overrides": overrides})

    await self.bot.database_client.update_profile(new_profile)
    await self.reply(ctx, _("ftl-cmd-profile-deny-success", name=profile_detail.mention, command=command_name))


@profile_command.command(name=_("ftl-cmd-profile-unset-name"), description=_("ftl-cmd-profile-unset-description"))
async def profile_unset_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.User | discord.Role,
    command_name: str | None,
) -> None:
    """
    Remove a command override for a user/role.
    If no command is specified, remove all overrides.
    """
    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the profile exists in the database
    profile = self.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if profile is None:
        await self.reply(ctx, _("ftl-cmd-profile-unset-profile-not-found", name=profile_detail.mention))
        return

    if command_name is not None:
        # Check if the command override exists
        if command_name not in profile.permission_overrides:
            await self.reply(
                ctx,
                _("ftl-cmd-profile-unset-override-not-found", name=profile_detail.mention, command=command_name),
            )
            return

        overrides = profile.permission_overrides.copy()
        # Remove the override
        del overrides[command_name]
    else:
        # Remove all overrides
        overrides = {}
    new_profile = profile.model_copy(deep=True, update={"permission_overrides": overrides})

    await self.bot.database_client.update_profile(new_profile)
    await self.reply(ctx, _("ftl-cmd-profile-unset-success", name=profile_detail.mention, command=command_name))
