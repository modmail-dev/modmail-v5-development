"""Profile management commands for the Modmail bot.

This module implements commands for managing user and role profiles including:
- Adding and removing profiles.
- Customizing profile appearance (color, tag).
- Managing permission overrides for commands.
- Setting access levels for users and roles.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import discord
from discord.ext import commands

from modmail import CONFIG, utils
from modmail.backends.common import ProfileModel
from modmail.core import Bot, Str, _, lazy_hybrid_group, wrap
from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType, RequiredAccessLevel

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["profile_command"]

logger = logging.getLogger(__name__)


class _ProfileCustomizeView(discord.ui.View, ABC):
    """Abstract base class for profile customization views.

    The real implementation is created dynamically in make_profile_customize_view().
    """

    @abstractmethod
    def set_original_message(self, message: discord.Message) -> None:
        """Set the message that sent this view.

        This should be called after sending the message so the view can reference and edit it.

        Args:
            message: The Discord.py message from the original .send().
        """


# TODO: move ProfileDetail and _get_profile_detail into a converter/transformer in converters.py


class ProfileDetail(NamedTuple):
    """Container for profile information.

    Attributes:
        mention: String representation/mention of the profile entity.
        profile_id: Unique identifier for the profile.
        profile_type: Type of profile (user or role).
    """

    mention: str
    profile_id: int
    profile_type: ProfileType | None


def _get_profile_detail(
    *, user_or_role: discord.Member | discord.User | discord.Role | None = None, id_: int | None = None
) -> ProfileDetail | None:
    """Get sanitized profile details from raw user/role/id inputs.

    Args:
        user_or_role: The Discord User or Role when the type is known.
        id_: The profile's ID if type is unknown.

    Returns:
        A ProfileDetail of the user/role/id_, or None if no valid input was provided.
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


def _check_is_bot(user_or_role: discord.Member | discord.User | discord.Role) -> bool:
    """Check if the user or role is a bot or bot's role.

    Args:
        user_or_role: The user or role to check.

    Returns:
        True if the user or role is a bot, False otherwise.
    """
    if isinstance(user_or_role, discord.Member | discord.User):
        return user_or_role.bot
    return bool(user_or_role.tags is not None and user_or_role.tags.is_bot_managed())


async def make_profile_customize_view(
    cog: Utility, ctx: commands.Context[Bot], profile_detail: ProfileDetail, profile: ProfileModel
) -> type[_ProfileCustomizeView]:
    """Create a UI view for customizing profiles.

    Args:
        cog: The Utility cog instance.
        ctx: The context of the command.
        profile_detail: The profile detail containing ID, mention and type.
        profile: The profile to customize.

    Returns:
        A Discord.py UI view class for customizing the profile with buttons and selects
        for managing appearance and access level.
    """
    # Stores the previous interaction so we can delete the response later
    previous_interaction: discord.Interaction | None = None

    ui_button_label = await cog.translate(ctx, _("ftl-view-profile-button-customize-label"))

    if profile.access_level is not None:
        # If the profile has an access level, set the placeholder to the current access level
        ui_select_level_placeholder = await cog.translate(ctx, profile.access_level.__locale_str__())
    else:
        ui_select_level_placeholder = await cog.translate(ctx, _("ftl-view-profile-select-level-placeholder"))

    # noinspection PyPep8Naming
    LEVEL_NONE: Final[str] = "None"  # noqa: N806
    ui_select_level_options = [
        # An option to remove the access level for this profile
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-view-profile-select-level-option-none")), value=LEVEL_NONE
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
        """Modal for customizing profile appearance."""

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
            """Check if the interaction is from the user who invoked the command.

            Returns:
                True if the interaction is from the user who invoked the command, False otherwise.
            """
            return interaction.user == ctx.author

        async def on_submit(self, interaction: discord.Interaction) -> None:
            """Handle submission of the modal."""
            nonlocal profile, previous_interaction

            if previous_interaction is not None:
                # Delete the previous interaction response if it exists
                await previous_interaction.delete_original_response()
            previous_interaction = interaction

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

            tag = self.tag.value or None
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

    class ProfileCustomizeView(_ProfileCustomizeView):
        """A view for customizing the profile."""

        def __init__(self) -> None:
            super().__init__()
            self._original_message: discord.Message | None = None

        def set_original_message(self, message: discord.Message) -> None:
            """Set the original message that sent this view.

            Args:
                message: The Discord.py message from the original .send().
            """
            self._original_message = message

        async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
            """Check if the interaction is from the user who invoked the command.

            Returns:
                True if the interaction is from the user who invoked the command, False otherwise.
            """
            return interaction.user == ctx.author

        async def on_timeout(self) -> None:
            """Disable all components of this view when timed out."""
            self.stop()

            for children in self.children:
                if hasattr(children, "disabled"):
                    children.disabled = True  # pyright: ignore [reportAttributeAccessIssue]

            if self._original_message is not None:
                await self._original_message.edit(view=self)

        @discord.ui.select(placeholder=ui_select_level_placeholder, options=ui_select_level_options)
        async def level_select(
            self, interaction: discord.Interaction, select: discord.ui.Select[ProfileCustomizeView]
        ) -> None:
            """Handle selection of access level."""
            nonlocal profile, previous_interaction

            if previous_interaction is not None:
                # Delete the previous interaction response if it exists
                await previous_interaction.delete_original_response()
            previous_interaction = interaction

            selected_option = select.values[0]
            if selected_option == LEVEL_NONE:
                selected_level: AccessLevel | None = None
            else:
                selected_level = AccessLevel[selected_option]

            if profile.access_level != selected_level:
                new_profile = profile.model_copy(deep=True, update={"access_level": selected_level})
                await ctx.bot.database_client.update_profile(new_profile)
                logger.debug("Updated profile access level for %d to %s.", new_profile.profile_id, selected_level)
                profile = new_profile

                if selected_level is None or selected_level == AccessLevel.everyone:
                    # Remove the profile's access from the Modmail category
                    await ctx.bot.staff_guild.revoke_access(profile.profile_id, profile.profile_type)
                else:
                    # Add the profile's access to the Modmail category
                    await ctx.bot.staff_guild.grant_access(profile.profile_id, profile.profile_type)

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

        @discord.ui.button(label=ui_button_label, style=discord.ButtonStyle.primary)
        async def customize_button(
            self, interaction: discord.Interaction, button: discord.ui.Button[ProfileCustomizeView]
        ) -> None:
            """Open the modal for profile customization."""
            await interaction.response.send_modal(ProfileCustomizeModal())

    return ProfileCustomizeView


@lazy_hybrid_group(
    name=_("ftl-cmd-profile-name"),
    fallback=_("ftl-cmd-profile-fallback-name"),
    description=_("ftl-cmd-profile-description"),
)
async def profile_command(cog: Utility, ctx: commands.Context[Bot]) -> None:
    """View and manage profile settings.

    This group command provides access to all profile management functionality
    including creating, editing, and deleting profiles, as well as managing
    permission overrides.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
    """


@wrap(discord.app_commands.rename, user_or_role=_("ftl-cmd-profile-add-param-user-or-role-name"))
@wrap(discord.app_commands.describe, user_or_role=_("ftl-cmd-profile-add-param-user-or-role-description"))
@profile_command.command(name=_("ftl-cmd-profile-add-name"), description=_("ftl-cmd-profile-add-description"))
async def profile_add_command(
    cog: Utility, ctx: commands.Context[Bot], user_or_role: discord.Member | discord.User | discord.Role
) -> None:
    """Create a new profile for a user or role.

    Creates a profile in the database and immediately provides customization options
    through an interactive view.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        user_or_role: The user or role whose profile should be created.
    """
    if _check_is_bot(user_or_role):
        await cog.reply(ctx, _("ftl-cmd-profile-no-bot"))
        return

    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the user/role already have a profile
    existing_profile = cog.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if existing_profile is not None:
        await cog.reply(ctx, _("ftl-cmd-profile-add-already-exists", name=profile_detail.mention))
        return

    new_profile = ProfileModel(
        bot_id=CONFIG.bot.bot_id,
        profile_id=profile_detail.profile_id,
        profile_type=profile_detail.profile_type,
    )
    await cog.bot.database_client.update_profile(new_profile)

    view = (await make_profile_customize_view(cog, ctx, profile_detail, new_profile))()
    message = await cog.reply(ctx, _("ftl-cmd-profile-add-success", name=profile_detail.mention), view=view)
    view.set_original_message(message)


@wrap(discord.app_commands.rename, user_or_role=_("ftl-cmd-profile-delete-param-user-or-role-name"))
@wrap(discord.app_commands.describe, user_or_role=_("ftl-cmd-profile-delete-param-user-or-role-description"))
@profile_command.command(
    name=_("ftl-cmd-profile-delete-name"), description=_("ftl-cmd-profile-delete-description")
)
async def profile_delete_command(
    cog: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role | None,
    id_: int | None,  # in case role/user was deleted TODO: auto delete on bot start so this isn't necessary
) -> None:
    """Delete a profile associated with a user or role.

    Removes the profile and all associated customizations and permission overrides
    from the database.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        user_or_role: The user or role whose profile should be deleted.
        id_: The profile ID to delete if the user/role is no longer accessible.
    """
    if user_or_role is not None and id_ is not None:
        await cog.reply(ctx, _("ftl-cmd-profile-delete-both"))
        return

    profile_detail = _get_profile_detail(user_or_role=user_or_role, id_=id_)
    if profile_detail is None:
        await cog.reply(ctx, _("ftl-cmd-profile-delete-none"))
        return

    await cog.bot.database_client.delete_profile(profile_id=profile_detail.profile_id)
    if profile_detail.profile_type is not None and user_or_role is not None and not _check_is_bot(user_or_role):
        # Remove access from the Modmail category if not a bot
        await cog.bot.staff_guild.revoke_access(profile_detail.profile_id, profile_detail.profile_type)

    await cog.reply(ctx, _("ftl-cmd-profile-delete-success", name=profile_detail.mention))


@wrap(discord.app_commands.rename, user_or_role=_("ftl-cmd-profile-edit-param-user-or-role-name"))
@wrap(discord.app_commands.describe, user_or_role=_("ftl-cmd-profile-edit-param-user-or-role-description"))
@profile_command.command(name=_("ftl-cmd-profile-edit-name"), description=_("ftl-cmd-profile-edit-description"))
async def profile_edit_command(
    cog: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
) -> None:
    """Customize a user or role's profile.

    Opens an interactive view for editing a profile's appearance settings and
    access level. Creates a new profile if one doesn't exist.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        user_or_role: The user or role whose profile should be edited.
    """
    if _check_is_bot(user_or_role):
        await cog.reply(ctx, _("ftl-cmd-profile-no-bot"))
        return

    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the user/role has an existing profile
    profile = cog.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if profile is None:
        # Create a new profile if it doesn't exist
        profile = ProfileModel(
            bot_id=CONFIG.bot.bot_id,
            profile_id=profile_detail.profile_id,
            profile_type=profile_detail.profile_type,
        )
        await cog.bot.database_client.update_profile(profile)

    view = (await make_profile_customize_view(cog, ctx, profile_detail, profile))()
    message = await cog.reply(ctx, _("ftl-cmd-profile-edit-message", name=profile_detail.mention), view=view)
    view.set_original_message(message)


async def _update_permission_override(
    cog: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    command_name: Str,
    override_value: PermissionOverrideValue,
) -> None:
    """Update the permission override for a user or role.

    Helper function for the allow and deny commands that modifies command access
    permissions for specific users or roles.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        user_or_role: The user or role to update permissions for.
        command_name: The command name to override permissions for.
        override_value: The permission value to set (allow or deny).
    """
    if _check_is_bot(user_or_role):
        await cog.reply(ctx, _("ftl-cmd-profile-no-bot"))
        return

    # Sanitize the command name
    command_name = utils.sanitize_user_command_name(command_name)
    command_name_no_wildcard = command_name.split("+")[0].strip()

    # Check if the command name is valid
    for bot_command in cog.bot.walk_commands():
        bot_command_name = utils.get_command_name(bot_command)

        if bot_command_name == command_name_no_wildcard:
            if "+" in command_name and not isinstance(bot_command, commands.Group):
                command_name = command_name_no_wildcard  # Remove the wildcard

            if cog.bot.get_command_access_level(bot_command) == RequiredAccessLevel.owner:
                # Trying to override an owner-only command
                if not await cog.bot.is_owner(ctx.author):
                    await cog.reply(ctx, _("ftl-cmd-profile-override-owner-command", command=command_name))
                    return
            break  # Command found, exit the loop
    else:
        # Command not found
        await cog.reply(ctx, _("ftl-cmd-profile-override-command-not-found", command=command_name))
        return

    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the profile exists in the database
    profile = cog.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if profile is None:
        # Create a new profile if it doesn't exist
        profile = ProfileModel(
            bot_id=CONFIG.bot.bot_id,
            profile_id=profile_detail.profile_id,
            profile_type=profile_detail.profile_type,
        )

    # Update the overrides
    overrides = profile.permission_overrides.copy()
    overrides[command_name] = override_value
    new_profile = profile.model_copy(deep=True, update={"permission_overrides": overrides})

    await cog.bot.database_client.update_profile(new_profile)
    if override_value == PermissionOverrideValue.allow:
        await cog.reply(ctx, _("ftl-cmd-profile-allow-success", name=profile_detail.mention, command=command_name))
    else:
        await cog.reply(ctx, _("ftl-cmd-profile-deny-success", name=profile_detail.mention, command=command_name))


@wrap(
    discord.app_commands.rename,
    user_or_role=_("ftl-cmd-profile-allow-param-user-or-role-name"),
    command_name=_("ftl-cmd-profile-allow-param-command-name-name"),
)
@wrap(
    discord.app_commands.describe,
    user_or_role=_("ftl-cmd-profile-allow-param-user-or-role-description"),
    command_name=_("ftl-cmd-profile-allow-param-command-name-description"),
)
@profile_command.command(name=_("ftl-cmd-profile-allow-name"), description=_("ftl-cmd-profile-allow-description"))
async def profile_allow_command(
    cog: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    *,
    command_name: Str,
) -> None:
    """Allow a user or role to use a specific command.

    Grants permission to use a command without having the normally required
    access level. Particularly useful for allowing lower-level users to access
    specific higher-level commands.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        user_or_role: The user or role to grant permission to.
        command_name: The command to allow access to. Can include wildcards using "+" for command groups.
    """
    await _update_permission_override(cog, ctx, user_or_role, command_name, PermissionOverrideValue.allow)


@wrap(
    discord.app_commands.rename,
    user_or_role=_("ftl-cmd-profile-deny-param-user-or-role-name"),
    command_name=_("ftl-cmd-profile-deny-param-command-name-name"),
)
@wrap(
    discord.app_commands.describe,
    user_or_role=_("ftl-cmd-profile-deny-param-user-or-role-description"),
    command_name=_("ftl-cmd-profile-deny-param-command-name-description"),
)
@profile_command.command(name=_("ftl-cmd-profile-deny-name"), description=_("ftl-cmd-profile-deny-description"))
async def profile_deny_command(
    cog: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    *,
    command_name: Str,
) -> None:
    """Deny a user or role from using a specific command.

    Prevents the use of a command even if the user or role would normally have
    the required access level to use it.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        user_or_role: The user or role to deny permission to.
        command_name: The command to deny access to. Can include wildcards using "+" for command groups.
    """
    await _update_permission_override(cog, ctx, user_or_role, command_name, PermissionOverrideValue.deny)


@wrap(
    discord.app_commands.rename,
    user_or_role=_("ftl-cmd-profile-unset-param-user-or-role-name"),
    command_name=_("ftl-cmd-profile-unset-param-command-name-name"),
)
@wrap(
    discord.app_commands.describe,
    user_or_role=_("ftl-cmd-profile-unset-param-user-or-role-description"),
    command_name=_("ftl-cmd-profile-unset-param-command-name-description"),
)
@profile_command.command(name=_("ftl-cmd-profile-unset-name"), description=_("ftl-cmd-profile-unset-description"))
async def profile_unset_command(
    cog: Utility,
    ctx: commands.Context[Bot],
    user_or_role: discord.Member | discord.User | discord.Role,
    *,
    command_name: Str | None,
) -> None:
    """Remove command permission overrides for a user or role.

    Removes specific or all command permission overrides, returning the commands
    to their default access level requirements for the specified user or role.

    Args:
        cog: The Utility cog instance.
        ctx: The command context.
        user_or_role: The user or role to remove overrides for.
        command_name: The specific command override to remove, or None to remove all overrides.
    """
    if _check_is_bot(user_or_role):
        await cog.reply(ctx, _("ftl-cmd-profile-no-bot"))
        return

    profile_detail = _get_profile_detail(user_or_role=user_or_role)

    # These can't be None, assert for type checker
    assert profile_detail is not None
    assert profile_detail.profile_type is not None

    # Check if the profile exists in the database
    profile = cog.bot.database_client.get_profile(profile_detail.profile_id, profile_detail.profile_type)
    if profile is None:
        await cog.reply(ctx, _("ftl-cmd-profile-unset-profile-not-found", name=profile_detail.mention))
        return

    if command_name is not None:
        # Sanitize the command name
        command_name = utils.sanitize_user_command_name(command_name)

        # Check if the command override exists
        if command_name not in profile.permission_overrides:
            await cog.reply(
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

    await cog.bot.database_client.update_profile(new_profile)
    await cog.reply(ctx, _("ftl-cmd-profile-unset-success", name=profile_detail.mention, command=command_name))
