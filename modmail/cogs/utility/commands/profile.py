"""
modmail.cogs.utility.commands.profile
=====================================
This file implements profile management commands for the modmail bot. It defines
several commands for adding, removing, customizing profiles and interface for overriding permission access levels.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, NamedTuple, Type

import discord
from discord.ext import commands

# noinspection PyProtectedMember
from modmail import CONFIG, utils
from modmail.backends import Profile

# noinspection PyProtectedMember
from modmail.core import Bot, _, lazy_hybrid_group
from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType, RequiredAccessLevel

__all__ = ["profile_command"]

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
    *, user_or_role: discord.Member | discord.User | discord.Role | None = None, id_: int | None = None
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
    # Stores the previous interaction so we can delete the response later
    _previous_interaction: discord.Interaction | None = None

    ui_button_label = await cog.translate(ctx, _("ftl-view-profile-button-customize-label"))

    if profile.access_level is not None:
        # If the profile has an access level, set the placeholder to the current access level
        ui_select_level_placeholder = await cog.translate(ctx, profile.access_level.__locale_str__())
    else:
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
            label=ui_colour_label,
            placeholder="#000000",
            default=utils.int_to_colour_hex(profile.colour) if profile.colour is not None else None,
            required=False,
        )
        tag: discord.ui.TextInput[ProfileCustomizeModal] = discord.ui.TextInput(
            label=ui_tag_label,
            default=profile.tag if profile.tag is not None else None,
            required=False,
            max_length=128,
        )

        async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
            """
            Check if the interaction is from the user who invoked the command.
            """
            return interaction.user == ctx.author

        async def on_submit(self, interaction: discord.Interaction) -> None:
            nonlocal profile, _previous_interaction

            if _previous_interaction is not None:
                # Delete the previous interaction response if it exists
                await _previous_interaction.delete_original_response()
            _previous_interaction = interaction

            to_update: dict[str, Any] = {}

            # Check if colour hex is invalid
            if self.colour.value and re.match(r"^#?[0-9a-fA-F]{6}$", self.colour.value) is None:
                await interaction.response.send_message(
                    await cog.translate(ctx, _("ftl-modal-profile-customize-colour-invalid")),
                    ephemeral=True,
                )
                return

            colour = utils.colour_hex_to_int(self.colour.value) if self.colour.value else None
            if colour != profile.colour:
                to_update["colour"] = colour
                # Update the default value of the modal
                ProfileCustomizeModal.colour.default = (
                    utils.int_to_colour_hex(colour) if colour is not None else None
                )

            tag = self.tag.value if self.tag.value else None
            if tag != profile.tag:
                to_update["tag"] = tag
                # Update the default value of the modal
                ProfileCustomizeModal.tag.default = tag

            if to_update:
                new_profile = profile.model_copy(deep=True, update=to_update)
                await ctx.bot.database_client.update_profile(new_profile)
                logger.debug("Updated profile %d with %s.", new_profile.profile_id, to_update)
                profile = new_profile

            await interaction.response.send_message(
                await cog.translate(ctx, _("ftl-modal-profile-customize-success", name=profile_detail.mention)),
                ephemeral=True,
            )

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
                    children.disabled = True  # pyright: ignore [reportAttributeAccessIssue]

            if self._original_message is not None:
                await self._original_message.edit(view=self)

        @discord.ui.select(placeholder=ui_select_level_placeholder, options=ui_select_level_options)
        async def level_select(
            self, interaction: discord.Interaction, select: discord.ui.Select[ProfileCustomizeView]
        ) -> None:
            nonlocal profile, _previous_interaction

            if _previous_interaction is not None:
                # Delete the previous interaction response if it exists
                await _previous_interaction.delete_original_response()
            _previous_interaction = interaction

            selected_option = select.values[0]
            if selected_option == _LEVEL_NONE:
                selected_level: AccessLevel | None = None
            else:
                selected_level = AccessLevel[selected_option]

            if profile.access_level != selected_level:
                new_profile = profile.model_copy(deep=True, update={"access_level": selected_level})
                await ctx.bot.database_client.update_profile(new_profile)
                logger.debug("Updated profile access level for %d to %s.", new_profile.profile_id, selected_level)
                profile = new_profile
            await interaction.response.send_message(
                await cog.translate(
                    ctx,
                    _(
                        "ftl-view-profile-select-level-success",
                        name=profile_detail.mention,
                        level=selected_level if selected_level is not None else "None",
                    ),
                ),
                ephemeral=True,
            )

        # noinspection PyUnusedLocal
        @discord.ui.button(label=ui_button_label, style=discord.ButtonStyle.primary)
        async def customize_button(
            self, interaction: discord.Interaction, button: discord.ui.Button[ProfileCustomizeView]
        ) -> None:
            await interaction.response.send_modal(ProfileCustomizeModal())

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
    self: Utility, ctx: commands.Context[Bot], user_or_role: discord.Member | discord.User | discord.Role
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
    user_or_role: discord.Member | discord.User | discord.Role | None,
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


@profile_command.command(name=_("ftl-cmd-profile-edit-name"), description=_("ftl-cmd-profile-edit-description"))
async def profile_edit_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
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
    message = await self.reply(ctx, _("ftl-cmd-profile-edit-message", name=profile_detail.mention), view=view)
    view.set_original_message(message)


async def _update_permission_override(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    command_name: str,
    override_value: PermissionOverrideValue,
) -> None:
    """
    Update the permission override for a user/role.
    This is a helper function for the allow and deny commands.
    """
    # Sanitize the command name
    command_name = utils.sanitize_user_command_name(command_name)
    command_name_no_wildcard = command_name.split("+")[0].strip()

    # Check if the command name is valid
    for bot_command in self.bot.walk_commands():
        bot_command_name = utils.get_command_name(bot_command)

        if bot_command_name == command_name_no_wildcard:
            if "+" in command_name and not isinstance(bot_command, commands.Group):
                command_name = command_name_no_wildcard  # Remove the wildcard

            if self.bot.get_command_access_level(bot_command) == RequiredAccessLevel.owner:
                # Trying to override an owner-only command
                if not await self.bot.is_owner(ctx.author):
                    await self.reply(ctx, _("ftl-cmd-profile-override-owner-command", command=command_name))
                    return
            break  # Command found, exit the loop
    else:
        # Command not found
        await self.reply(ctx, _("ftl-cmd-profile-override-command-not-found", command=command_name))
        return

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
    overrides[command_name] = override_value
    new_profile = profile.model_copy(deep=True, update={"permission_overrides": overrides})

    await self.bot.database_client.update_profile(new_profile)
    if override_value == PermissionOverrideValue.allow:
        await self.reply(
            ctx, _("ftl-cmd-profile-allow-success", name=profile_detail.mention, command=command_name)
        )
    else:
        await self.reply(ctx, _("ftl-cmd-profile-deny-success", name=profile_detail.mention, command=command_name))


@profile_command.command(name=_("ftl-cmd-profile-allow-name"), description=_("ftl-cmd-profile-allow-description"))
async def profile_allow_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    *,
    command_name: str,
) -> None:
    """
    Allow a user/role to use a specific command without having the required access level.
    """
    await _update_permission_override(self, ctx, user_or_role, command_name, PermissionOverrideValue.allow)


@profile_command.command(name=_("ftl-cmd-profile-deny-name"), description=_("ftl-cmd-profile-deny-description"))
async def profile_deny_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    *,
    command_name: str,
) -> None:
    """
    Deny a user/role from using a specific command even if they have the required access level.
    """
    await _update_permission_override(self, ctx, user_or_role, command_name, PermissionOverrideValue.deny)


@profile_command.command(name=_("ftl-cmd-profile-unset-name"), description=_("ftl-cmd-profile-unset-description"))
async def profile_unset_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    *,
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
        # Sanitize the command name
        command_name = utils.sanitize_user_command_name(command_name)

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
