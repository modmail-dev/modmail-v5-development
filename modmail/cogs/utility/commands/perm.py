from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple, Type, cast

import discord
from discord.ext import commands

from modmail import CONFIG
from modmail.backends import PermissionGroup
from modmail.core import Bot, _, lazy_hybrid_group

__all__ = ["perm_command"]

from modmail.enum import PermissionGroupType, PermissionLevel

if TYPE_CHECKING:
    from .. import Utility

    class PermCustomizeView(discord.ui.View):
        _original_message: discord.Message | None

        def set_original_message(self, message: discord.Message) -> None: ...


logger = logging.getLogger(__name__)


async def make_perm_customize_view(
    cog: Utility, ctx: commands.Context[Bot], group: PermissionGroup
) -> Type[PermCustomizeView]:
    """
    Create a view for customizing permissions.
    This view contains a "Customize" button and a select menu for choosing a permission level.

    :param cog: The Utility cog instance.
    :param ctx: The context of the command.
    :param group: The permission group to customize.
    :return: A Discord.py UI view for customizing permissions.
    """
    ui_button_label = await cog.translate(ctx, _("ftl-view-perm-button-customize-label"))
    ui_select_level_placeholder = await cog.translate(ctx, _("ftl-view-perm-select-level-placeholder"))
    ui_select_level_options = [
        # Default to remove the permission level for this user/role
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-view-perm-select-level-option-none")), value="None"
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-perm-level-everyone")), value=PermissionLevel.everyone.name
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-perm-level-staff")), value=PermissionLevel.staff.name
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-perm-level-manager")), value=PermissionLevel.manager.name
        ),
        discord.SelectOption(
            label=await cog.translate(ctx, _("ftl-perm-level-admin")), value=PermissionLevel.admin.name
        ),
    ]

    ui_title = await cog.translate(ctx, _("ftl-modal-perm-customize-title"))
    ui_colour_label = await cog.translate(ctx, _("ftl-model-perm-customize-colour"))
    ui_tag_label = await cog.translate(ctx, _("ftl-model-perm-customize-tag"))

    class PermCustomizeModal(discord.ui.Modal, title=ui_title):
        # TODO: Use default from group
        colour: discord.ui.TextInput[PermCustomizeModal] = discord.ui.TextInput(
            label=ui_colour_label, default="#000000", required=False
        )
        tag: discord.ui.TextInput[PermCustomizeModal] = discord.ui.TextInput(
            label=ui_tag_label, default="", required=False
        )

        def __init__(self, view: PermCustomizeView):
            super().__init__()
            self._view = view

        async def on_submit(self, interaction: discord.Interaction) -> None:
            print(self.colour, self.tag)
            # Disable the modal customize button
            button = cast(discord.ui.Button[PermCustomizeView], self._view.children[1])
            button.disabled = True
            # noinspection PyProtectedMember
            if self._view._original_message is not None:  # type: ignore[reportPrivateUsage]
                # noinspection PyProtectedMember
                await self._view._original_message.edit(view=self._view)  # type: ignore[reportPrivateUsage]

    # noinspection PyShadowingNames
    class PermCustomizeView(discord.ui.View):
        """
        A view for customizing permissions.
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
            Remove this view when timed out.
            """
            if self._original_message is not None:
                await self._original_message.edit(view=None)

        @discord.ui.select(placeholder=ui_select_level_placeholder, options=ui_select_level_options)
        async def level_select(
            self, interaction: discord.Interaction, select: discord.ui.Select[PermCustomizeView]
        ) -> None:
            nonlocal group

            selected_option = select.values[0]
            if selected_option == "None":
                selected_level: PermissionLevel | None = None
            else:
                # noinspection PyTypeChecker
                selected_level = PermissionLevel[selected_option]

            if group.level != selected_level:
                new_group = group.model_copy(deep=True, update={"level": selected_level})
                await ctx.bot.database_client.update_permission_group(new_group)
                logger.debug("Updated permission group level for %d to %s.", new_group.group_id, selected_level)
                group = new_group
            await interaction.response.send_message(
                await cog.translate(ctx, _("ftl-view-perm-select-level-success", level=selected_level)),
                ephemeral=True,
            )

            # Disable the select
            select = cast(discord.ui.Select[PermCustomizeView], self.children[0])
            select.disabled = True
            if self._original_message is not None:
                await self._original_message.edit(view=self)

        @discord.ui.button(label=ui_button_label, style=discord.ButtonStyle.primary)
        async def customize_button(
            self, interaction: discord.Interaction, button: discord.ui.Button[PermCustomizeView]
        ) -> None:
            await interaction.response.send_modal(PermCustomizeModal(self))

    return PermCustomizeView


class GroupDetail(NamedTuple):
    mention: str
    id_: int
    type_: PermissionGroupType | None


def _get_group_detail(
    *, user: discord.User | None = None, role: discord.Role | None = None, id_: int | None = None
) -> GroupDetail | None:
    """
    Get a sanitized GroupDetail from the raw user/role/id_ command inputs.

    :param user: The group user if type is user.
    :param role: The group role if type is role.
    :param id_: The group_id if type is unknown.
    :return: A GroupDetail of the user/role/id_, None if no input was provided.
    """
    group_mention: str
    group_id: int
    group_type: PermissionGroupType | None

    if role is not None:
        if role.is_default():
            group_mention = "@everyone"
        else:
            group_mention = role.mention
        group_id = role.id
        group_type = PermissionGroupType.role
    elif user is not None:
        group_mention = user.mention
        group_id = user.id
        group_type = PermissionGroupType.user
    elif id_ is not None:
        group_mention = f"`{id_}`"
        group_id = id_
        group_type = None
    else:
        return None
    return GroupDetail(group_mention, group_id, group_type)


@lazy_hybrid_group(
    name=_("ftl-cmd-perm-name"),
    fallback=_("ftl-cmd-perm-fallback-name"),
    description=_("ftl-cmd-perm-description"),
)
async def perm_command(self: Utility, ctx: commands.Context[Bot]) -> None:
    """
    View the currently set perm.
    """
    ...


@perm_command.command(name=_("ftl-cmd-perm-add-name"), description=_("ftl-cmd-perm-add-description"))
async def perm_add_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user: discord.User | None = None,
    role: discord.Role | None = None,
) -> None:
    """
    Add a user/role to the staff list.
    """
    if role is not None and user is not None:
        await self.reply(ctx, _("ftl-cmd-perm-add-both"))
        return

    group_detail = _get_group_detail(user=user, role=role)

    if group_detail is None:
        await self.reply(ctx, _("ftl-cmd-perm-add-none"))
        return
    assert group_detail.type_ is not None, "Group type cannot be None"

    # Check if the user/role is already in the staff list
    existing_group = self.bot.database_client.get_permission_group(group_detail.id_, group_detail.type_)
    if existing_group is not None:
        await self.reply(ctx, _("ftl-cmd-perm-add-already-exists", group=group_detail.mention))
        return

    new_group = PermissionGroup(bot_id=CONFIG.bot.bot_id, group_id=group_detail.id_, group_type=group_detail.type_)
    await self.bot.database_client.update_permission_group(new_group)

    view = (await make_perm_customize_view(self, ctx, new_group))()
    message = await self.reply(ctx, _("ftl-cmd-perm-add-success", group=group_detail.mention), view=view)
    view.set_original_message(message)


@perm_command.command(name=_("ftl-cmd-perm-remove-name"), description=_("ftl-cmd-perm-remove-description"))
async def perm_remove_command(
    self: Utility,
    ctx: commands.Context[Bot],
    role: discord.Role | None = None,
    user: discord.User | None = None,
    id_: int | None = None,  # in case role/user was deleted
) -> None:
    """
    Remove a user/role from the staff list.
    """
    if role is not None and user is not None:
        await self.reply(ctx, _("ftl-cmd-perm-remove-both"))
        return

    group_detail = _get_group_detail(user=user, role=role, id_=id_)
    if group_detail is None:
        await self.reply(ctx, _("ftl-cmd-perm-remove-none"))
        return

    await self.bot.database_client.delete_permission_group(
        group_id=group_detail.id_, group_type=group_detail.type_
    )
    await self.reply(ctx, _("ftl-cmd-perm-remove-success", group=group_detail.mention))


@perm_command.command(name=_("ftl-cmd-perm-customize-name"), description=_("ftl-cmd-perm-customize-description"))
async def perm_customize_command(
    self: Utility,
    ctx: commands.Context[Bot],
    user: discord.User | None = None,
    role: discord.Role | None = None,
) -> None:
    """
    Customize a user/role's attributes.
    """
    if role is not None and user is not None:
        await self.reply(ctx, _("ftl-cmd-perm-customize-both"))
        return

    group_detail = _get_group_detail(user=user, role=role)
    if group_detail is None:
        await self.reply(ctx, _("ftl-cmd-perm-customize-none"))
        return
    assert group_detail.type_ is not None, "Group type cannot be None"

    # Check if the user/role is not in the staff list
    group = self.bot.database_client.get_permission_group(group_detail.id_, group_detail.type_)
    if group is None:
        await self.reply(ctx, _("ftl-cmd-perm-customize-not-found", group=group_detail.mention))
        return

    view = (await make_perm_customize_view(self, ctx, group))()
    message = await self.reply(ctx, _("ftl-cmd-perm-customize-message", group=group_detail.mention), view=view)
    view.set_original_message(message)
