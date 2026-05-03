"""Profile management commands."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from typing import TYPE_CHECKING, Any, Final

import discord
from discord.ext import commands

from modmail import CONFIG, utils
from modmail.backends.common import ProfileModel
from modmail.core import Context, ProfileLookup, _, lazy_hybrid_group, wrap
from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType, RequiredAccessLevel
from modmail.errors import DatabaseOperationError

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["profile_command"]

logger = logging.getLogger(__name__)


class ProfileCustomizeModal(discord.ui.Modal):
    """Modal for customizing a profile's appearance settings."""

    def __init__(
        self,
        ctx: Context,
        *,
        editor_view: ProfileEditorView,
        timeout: float = 300.0,
    ) -> None:
        """Build the modal with the current customization fields.

        Args:
            ctx: The command context used for translation and author checks.
            editor_view: The parent [`ProfileEditorView`][] that owns the shared profile state.
            timeout: Seconds before the modal stops accepting input.
        """
        super().__init__(title=ctx.t("ftl-modal-profile-customize-title"), timeout=timeout)
        self._ctx = ctx
        self._editor_view = editor_view

        self.color: discord.ui.TextInput[ProfileCustomizeModal] = discord.ui.TextInput(
            label=ctx.t("ftl-modal-profile-customize-color"),
            placeholder=ctx.t("ftl-modal-profile-customize-color-placeholder"),
            default=utils.int_to_color_hex(self.profile.color) if self.profile.color is not None else None,
            required=False,
        )
        self.tag: discord.ui.TextInput[ProfileCustomizeModal] = discord.ui.TextInput(
            label=ctx.t("ftl-modal-profile-customize-tag"),
            default=self.profile.tag if self.profile.tag is not None else None,
            required=False,
            max_length=128,
        )
        self.add_item(self.color)
        self.add_item(self.tag)

    @property
    def profile(self) -> ProfileModel:
        """The current customized profile model."""
        return self._editor_view.profile

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction originates from the command invoker."""
        return interaction.user == self._ctx.author

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate and persist the submitted customization values, then refresh the card.

        Args:
            interaction: The submission interaction from Discord.
        """
        if (
            self.color.value
            and re.match(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", self.color.value) is None
        ):
            await interaction.response.send_message(
                self._ctx.t("ftl-modal-profile-customize-color-invalid"),
                ephemeral=True,
            )
            return

        to_update: dict[str, Any] = {}
        changed = self._editor_view.resync_profile()

        color = utils.color_hex_to_int(self.color.value) if self.color.value else None
        if color != self.profile.color:
            to_update["color"] = color

        tag = self.tag.value or None
        if tag != self.profile.tag:
            to_update["tag"] = tag

        if to_update:
            new_profile = self.profile.model_copy(update=to_update)
            try:
                await self._ctx.bot.database_client.update_profile(new_profile)
            except DatabaseOperationError as e:
                logger.error("Failed to update profile %d customization: %s", new_profile.profile_id, e)
                if changed:
                    await self._editor_view.rebuild()
                await interaction.response.send_message(
                    self._ctx.t("ftl-view-profile-editor-update-failed"),
                    ephemeral=True,
                )
                return
            logger.debug("Updated profile %d customization: %s.", new_profile.profile_id, to_update)
            self._editor_view.profile = new_profile

        await self._editor_view.rebuild()
        await interaction.response.send_message(
            self._ctx.t("ftl-modal-profile-customize-success", profile=self.profile.mention),
            ephemeral=True,
        )


class ProfileAddOverrideModal(discord.ui.Modal):
    """Modal for adding an allow or deny permission override to a profile."""

    def __init__(
        self,
        ctx: Context,
        *,
        editor_view: ProfileEditorView,
        override_value: PermissionOverrideValue,
        timeout: float = 300.0,
    ) -> None:
        """Build the modal with a command name text input.

        Args:
            ctx: The command context used for translation and author checks.
            editor_view: The parent [`ProfileEditorView`][] that owns the shared profile state.
            override_value: Whether to allow or deny the entered command.
            timeout: Seconds before the modal stops accepting input.
        """
        super().__init__(
            title=ctx.t(
                "ftl-modal-profile-add-override-allow-title"
                if override_value == PermissionOverrideValue.allow
                else "ftl-modal-profile-add-override-deny-title"
            ),
            timeout=timeout,
        )
        self._ctx = ctx
        self._editor_view = editor_view
        self._override_value = override_value

        self.command_name: discord.ui.TextInput[ProfileAddOverrideModal] = discord.ui.TextInput(
            label=ctx.t("ftl-modal-profile-add-override-command-label"),
            placeholder=ctx.t("ftl-modal-profile-add-override-command-placeholder"),
            required=True,
        )
        self.add_item(self.command_name)

    @property
    def profile(self) -> ProfileModel:
        """The current customized profile model."""
        return self._editor_view.profile

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction originates from the command invoker."""
        return interaction.user == self._ctx.author

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate the command name and persist the override, then refresh the card.

        Args:
            interaction: The submission interaction from Discord.
        """
        locale = str(interaction.locale) if interaction.locale else CONFIG.default_locale
        index = self._ctx.bot.permission_command_index(locale)

        canonical = index.resolve(self.command_name.value)
        if canonical is None:
            await interaction.response.send_message(
                self._ctx.t("ftl-cmd-profile-override-command-not-found", command=self.command_name.value),
                ephemeral=True,
            )
            return

        base = canonical.removesuffix("+")

        for bot_command in self._ctx.bot.walk_commands():
            if self._ctx.bot.get_canonical_command_name(bot_command) == base:
                if canonical != base and not isinstance(bot_command, commands.Group):
                    canonical = base  # wildcards only apply to groups

                if self._ctx.bot.get_command_access_level(bot_command) == RequiredAccessLevel.owner:
                    # Only actual owner allowed to override owner-only commands
                    if not await self._ctx.bot.is_owner(self._ctx.author):
                        await interaction.response.send_message(
                            self._ctx.t("ftl-cmd-profile-override-owner-command", command=self.command_name.value),
                            ephemeral=True,
                        )
                        return
                break

        display = index.label(canonical)

        changed = self._editor_view.resync_profile()
        if self.profile.permission_overrides.get(canonical) == self._override_value:
            if changed:
                await self._editor_view.rebuild()
            await interaction.response.send_message(
                self._ctx.t(
                    "ftl-modal-profile-add-override-already-allow"
                    if self._override_value == PermissionOverrideValue.allow
                    else "ftl-modal-profile-add-override-already-deny",
                    command=display,
                ),
                ephemeral=True,
            )
            return

        overrides = self.profile.permission_overrides.copy()
        overrides[canonical] = self._override_value
        new_profile = self.profile.model_copy(update={"permission_overrides": overrides})
        try:
            await self._ctx.bot.database_client.update_profile(new_profile)
        except DatabaseOperationError as e:
            logger.error("Failed to set override %r on profile %d: %s", canonical, new_profile.profile_id, e)
            if changed:
                await self._editor_view.rebuild()
            await interaction.response.send_message(
                self._ctx.t("ftl-view-profile-editor-update-failed"),
                ephemeral=True,
            )
            return
        logger.debug(
            "Set %s override for command %r on profile %d.",
            self._override_value.value,
            canonical,
            new_profile.profile_id,
        )
        self._editor_view.profile = new_profile
        await self._editor_view.rebuild()

        await interaction.response.send_message(
            self._ctx.t(
                "ftl-view-profile-editor-override-allow-success"
                if self._override_value == PermissionOverrideValue.allow
                else "ftl-view-profile-editor-override-deny-success",
                command=display,
            ),
            ephemeral=True,
        )


class ProfileRemoveOverrideModal(discord.ui.Modal):
    """Modal for removing a permission override by name (used when there are more than 25)."""

    def __init__(self, ctx: Context, *, editor_view: ProfileEditorView, timeout: float = 300.0) -> None:
        """Build the modal with an override name text input.

        Args:
            ctx: The command context used for translation and author checks.
            editor_view: The parent [`ProfileEditorView`][] that owns the shared profile state.
            timeout: Seconds before the modal stops accepting input.
        """
        super().__init__(title=ctx.t("ftl-modal-profile-remove-override-title"), timeout=timeout)
        self._ctx = ctx
        self._editor_view = editor_view

        self.override_name: discord.ui.TextInput[ProfileRemoveOverrideModal] = discord.ui.TextInput(
            label=ctx.t("ftl-modal-profile-remove-override-name-label"),
            placeholder=ctx.t("ftl-modal-profile-remove-override-name-placeholder"),
            required=True,
        )
        self.add_item(self.override_name)

    @property
    def profile(self) -> ProfileModel:
        """The current customized profile model."""
        return self._editor_view.profile

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction originates from the command invoker."""
        return interaction.user == self._ctx.author

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Remove the named override from the profile, then refresh the card.

        Args:
            interaction: The submission interaction from Discord.
        """
        locale = str(interaction.locale) if interaction.locale else CONFIG.default_locale
        index = self._ctx.bot.permission_command_index(locale)
        sanitized = index.sanitize(self.override_name.value)

        resolved = index.resolve(self.override_name.value, allow_raw_key=True)

        changed = self._editor_view.resync_profile()

        # Remove resolved if exists, otherwise remove sanitized input if it's an orphaned key
        key_to_remove = (
            resolved
            if resolved is not None and resolved in self.profile.permission_overrides
            else sanitized
            if sanitized in self.profile.permission_overrides
            else None
        )

        if key_to_remove is None:
            if changed:
                await self._editor_view.rebuild()
            await interaction.response.send_message(
                self._ctx.t("ftl-modal-profile-remove-override-not-found", command=self.override_name.value),
                ephemeral=True,
            )
            return

        if not await self._editor_view.remove_override(key_to_remove, interaction):
            if changed:
                await self._editor_view.rebuild()
            return

        await self._editor_view.rebuild()
        display = index.label(key_to_remove)
        await interaction.response.send_message(
            self._ctx.t("ftl-modal-profile-remove-override-success", command=display),
            ephemeral=True,
        )


class ConfirmDeleteView(discord.ui.LayoutView):
    """Ephemeral Component v2 confirm/cancel card shown before deleting a profile."""

    def __init__(
        self,
        ctx: Context,
        *,
        editor_view: ProfileEditorView,
        interaction: discord.Interaction,
        timeout: float = 120.0,
    ) -> None:
        """Build the card with confirm text and confirm/cancel buttons.

        Args:
            ctx: The command context used for translation and author checks.
            editor_view: The [`ProfileEditorView`][] that owns the profile to delete.
            interaction: The interaction that opened this card (used to clean up on timeout).
            timeout: Seconds before the confirmation card expires.
        """
        super().__init__(timeout=timeout)
        self._ctx = ctx
        self._editor_view = editor_view
        self._interaction = interaction

        confirm_btn: discord.ui.Button[ConfirmDeleteView] = discord.ui.Button(
            label=ctx.t("ftl-view-profile-editor-delete-btn-confirm"),
            style=discord.ButtonStyle.danger,
        )
        confirm_btn.callback = self._on_confirm

        cancel_btn: discord.ui.Button[ConfirmDeleteView] = discord.ui.Button(
            label=ctx.t("ftl-view-prompt-cancel-label"),
            style=discord.ButtonStyle.secondary,
        )
        cancel_btn.callback = self._on_cancel

        action_row: discord.ui.ActionRow[ConfirmDeleteView] = discord.ui.ActionRow()
        action_row.add_item(confirm_btn)
        action_row.add_item(cancel_btn)

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(ctx.t("ftl-view-profile-editor-delete-confirm")),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                action_row,
            )
        )

    @property
    def profile(self) -> ProfileModel:
        """The current customized profile model."""
        return self._editor_view.profile

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction originates from the command invoker."""
        return interaction.user == self._ctx.author

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        """Delete the profile, revoke channel access, and show a terminal card.

        Args:
            interaction: The button interaction from Discord.
        """
        try:
            await self._ctx.bot.database_client.delete_profile(profile_id=self.profile.profile_id)
        except DatabaseOperationError as e:
            logger.error("Failed to delete profile %d: %s", self.profile.profile_id, e)
            await interaction.response.send_message(
                self._ctx.t("ftl-view-profile-editor-update-failed"),
                ephemeral=True,
            )
            return
        logger.debug("Deleted profile %d.", self.profile.profile_id)
        self.stop()

        # Only staff+ levels have Discord channel access; everyone/None do not.
        access_sync_failed = False
        if self.profile.access_level is not None and self.profile.access_level != AccessLevel.everyone:
            try:
                await self._ctx.bot.staff_guild.revoke_access(self.profile.profile_id)
            except Exception as e:
                logger.error("Failed to revoke Discord access for profile %d: %s", self.profile.profile_id, e)
                access_sync_failed = True

        close_message = self._ctx.t("ftl-view-profile-editor-deleted-content", profile=self.profile.mention)
        if access_sync_failed:
            close_message += "\n" + self._ctx.t("ftl-view-profile-editor-access-sync-failed")

        await self._editor_view.close(close_message, color=discord.Color.blurple())

        await interaction.response.defer()
        with contextlib.suppress(discord.HTTPException):
            await interaction.delete_original_response()

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        """Dismiss the ephemeral confirm message without deleting.

        Args:
            interaction: The button interaction from Discord.
        """
        await interaction.response.defer()
        with contextlib.suppress(discord.HTTPException):
            await interaction.delete_original_response()
        self.stop()

    async def on_timeout(self) -> None:
        """Delete the ephemeral confirm card when it expires."""
        with contextlib.suppress(discord.HTTPException):
            await self._interaction.delete_original_response()


class ProfileEditorView(discord.ui.LayoutView):
    """In-place editor for a user or role profile.

    Renders the full profile state (access level, customization, overrides) inside
    a single updating card. Every interaction rebuilds the card in place via
    [`_render`][].

    Warning:
        Set `message` after sending so the view can edit its card on timeout.

    Examples:
        ```python
        view = ProfileEditorView(ctx=ctx, profile=profile)
        await view.build()
        msg = await ctx.reply(view=view)
        view.message = msg
        ```
    """

    _LEVEL_NONE: Final[str] = "None"
    _SELECT_MAX: Final[int] = 25  # use a remove-select up to this many overrides

    def __init__(
        self,
        ctx: Context,
        *,
        profile: ProfileModel,
        timeout: float = 300.0,
    ) -> None:
        """Build the editor without rendering — call `build()` before sending.

        Args:
            ctx: The command context used for translation and author checks.
            profile: The [`ProfileModel`][] to edit — updated in place as the user interacts.
            timeout: Seconds of inactivity before the editor times out and becomes non-interactive.
        """
        super().__init__(timeout=timeout)
        self._ctx = ctx
        self.profile = profile
        """The profile being edited, updated in place as the user interacts."""
        self.message: discord.Message | None = None
        """The sent editor message (set by the caller after sending)."""
        self._done_card: discord.ui.Container[ProfileEditorView] | None = None
        """When set, this card is rendered instead of the interactive editor."""
        self._disabled: bool = False
        """When `True`, all interactive elements are rendered disabled (set on timeout)."""
        self._profile_sync_task: asyncio.Task[None] | None = None
        """Periodically re-renders the card when the profile is changed externally."""

    async def remove_override(self, key: str, interaction: discord.Interaction) -> bool:
        """Remove an override by name, then persist or auto-delete the profile.

        On a database error the ephemeral error message is sent via `interaction` and
        `False` is returned so the caller can early-return without rendering.

        Args:
            key: Override name to remove.
            interaction: Used to send an ephemeral error if the update fails.

        Returns:
            `True` on success, `False` on database error.
        """
        overrides = self.profile.permission_overrides.copy()
        if key not in overrides:
            return True

        del overrides[key]
        new_profile = self.profile.model_copy(update={"permission_overrides": overrides})

        try:
            await self._ctx.bot.database_client.update_profile(new_profile)
        except DatabaseOperationError as e:
            logger.error("Failed to remove override %r from profile %d: %s", key, new_profile.profile_id, e)
            await interaction.response.send_message(
                self._ctx.t("ftl-view-profile-editor-update-failed"),
                ephemeral=True,
            )
            return False
        self.profile = new_profile
        return True

    async def close(self, content: str, *, color: discord.Color | None = None) -> None:
        """Transition the editor to its final non-interactive state.

        Stops the view, rebuilds the card, and edits the message in place.

        Args:
            content: Text to display in the final card.
            color: Accent color for the final container (`None` defaults to red).
        """
        if color is None:
            color = discord.Color.red()

        self._done_card = discord.ui.Container(discord.ui.TextDisplay(content), accent_color=color)
        self.stop()
        await self.rebuild()

    def stop(self) -> None:
        """Stop the view and cancel the background sync task."""
        if self._profile_sync_task is not None:
            self._profile_sync_task.cancel()
        super().stop()

    def resync_profile(self) -> bool:
        """Sync [`profile`][] from the DB cache, falling back to a blank profile if not found.

        Returns:
            `True` if [`profile`][] changed, `False` if it was already up to date.
        """
        current = self._ctx.bot.database_client.get_profile(self.profile.profile_id, self.profile.profile_type)
        if current is None:
            current = ProfileModel(
                bot_id=self.profile.bot_id,
                profile_id=self.profile.profile_id,
                profile_type=self.profile.profile_type,
            )
        if changed := current != self.profile:
            logger.debug("Profile %d changed externally, resyncing editor view.", self.profile.profile_id)
            self.profile = current
        return changed

    async def _profile_sync_loop(self) -> None:
        """Periodically check the DB cache and re-render the card if the profile changed."""
        while not self.is_finished():
            await asyncio.sleep(30)
            if self.is_finished():
                break
            if self.resync_profile():
                await self.rebuild()

    async def build(self) -> None:
        """Clear and rebuild the container for the current profile state.

        Must be called before sending the initial message and after each state change.
        """
        self.clear_items()
        self.add_item(self._build_container())
        if self._profile_sync_task is None:
            self._profile_sync_task = asyncio.create_task(self._profile_sync_loop())

    async def rebuild(self) -> None:
        """Rebuild the card and silently push the update to the editor message."""
        await self.build()
        if self.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)

    async def _render(self, interaction: discord.Interaction) -> None:
        """Rebuild the card and edit the message in place via `interaction`.

        Args:
            interaction: The triggering interaction (used for the edit response).
        """
        await self.build()
        await interaction.response.edit_message(view=self)

    @staticmethod
    def _btn(
        label: str,
        style: discord.ButtonStyle,
        callback: Any,
        *,
        disabled: bool = False,
    ) -> discord.ui.Button[ProfileEditorView]:
        """Create a button bound to `callback`.

        Args:
            label: Button label text.
            style: Discord button style.
            callback: Async callable to invoke on click.
            disabled: Whether the button should be rendered as non-interactive.

        Returns:
            The configured button.
        """
        btn: discord.ui.Button[ProfileEditorView] = discord.ui.Button(label=label, style=style, disabled=disabled)
        btn.callback = callback
        return btn

    def _build_container(self) -> discord.ui.Container[ProfileEditorView]:
        """Build and return the container for the current editor state.

        Returns:
            The constructed [`discord.ui.Container`][] for the active state.
        """
        if self._done_card is not None:
            return self._done_card

        # ── Header: mention + type label + delete button ──

        header_text = self._ctx.t(
            "ftl-view-profile-editor-header",
            profile=self.profile.mention,
            type=_("ftl-view-profile-editor-type-user")
            if self.profile.profile_type == ProfileType.user
            else _("ftl-view-profile-editor-type-role"),
        )

        async def on_delete(interaction: discord.Interaction) -> None:
            if (
                self._ctx.bot.database_client.get_profile(self.profile.profile_id, self.profile.profile_type)
                is None
            ):
                # The profile doesn't exist in the first place
                await interaction.response.defer()
                await self.close(
                    self._ctx.t("ftl-view-profile-editor-deleted-content", profile=self.profile.mention),
                    color=discord.Color.blurple(),
                )
                return
            await interaction.response.send_message(
                ephemeral=True,
                view=ConfirmDeleteView(self._ctx, editor_view=self, interaction=interaction),
            )

        # ── Summary: current level, tag, color ──

        summary_text = self._ctx.t(
            "ftl-view-profile-editor-summary",
            level=self.profile.access_level
            if self.profile.access_level is not None
            else _("ftl-view-profile-editor-level-none"),
            tag=self.profile.tag if self.profile.tag is not None else _("ftl-view-profile-editor-not-set"),
            color=utils.int_to_color_hex(self.profile.color)
            if self.profile.color is not None
            else _("ftl-view-profile-editor-not-set"),
        )

        # ── Access level select ──

        level_options = [
            discord.SelectOption(
                label=self._ctx.t("ftl-view-profile-editor-level-none"),
                value=self._LEVEL_NONE,
                default=self.profile.access_level is None,
            ),
            discord.SelectOption(
                label=self._ctx.t("ftl-access-level-everyone"),
                value=AccessLevel.everyone.name,
                default=self.profile.access_level == AccessLevel.everyone,
            ),
            discord.SelectOption(
                label=self._ctx.t("ftl-access-level-staff"),
                value=AccessLevel.staff.name,
                default=self.profile.access_level == AccessLevel.staff,
            ),
            discord.SelectOption(
                label=self._ctx.t("ftl-access-level-manager"),
                value=AccessLevel.manager.name,
                default=self.profile.access_level == AccessLevel.manager,
            ),
            discord.SelectOption(
                label=self._ctx.t("ftl-access-level-admin"),
                value=AccessLevel.admin.name,
                default=self.profile.access_level == AccessLevel.admin,
            ),
        ]
        level_select: discord.ui.Select[ProfileEditorView] = discord.ui.Select(
            placeholder=self._ctx.t("ftl-view-profile-editor-select-level-placeholder"),
            options=level_options,
            disabled=self._disabled,
        )

        async def on_level_select(interaction: discord.Interaction) -> None:
            selected_option = level_select.values[0]
            selected_level: AccessLevel | None = (
                None if selected_option == self._LEVEL_NONE else AccessLevel[selected_option]
            )

            changed = self.resync_profile()
            if self.profile.access_level == selected_level:
                logger.debug(
                    "Access level didn't change for profile %d, skipping update.", self.profile.profile_id
                )
                if changed:
                    await self._render(interaction)
                else:
                    await interaction.response.defer()
                return

            old_level = self.profile.access_level
            new_profile = self.profile.model_copy(update={"access_level": selected_level})
            try:
                await self._ctx.bot.database_client.update_profile(new_profile)
            except DatabaseOperationError as e:
                logger.error("Failed to update profile %d access level: %s", new_profile.profile_id, e)
                if changed:
                    await self._render(interaction)
                    await interaction.followup.send(
                        self._ctx.t("ftl-view-profile-editor-update-failed"),
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        self._ctx.t("ftl-view-profile-editor-update-failed"),
                        ephemeral=True,
                    )
                return
            logger.debug("Updated profile %d access level to %s.", new_profile.profile_id, selected_level)
            self.profile = new_profile

            # "everyone" profiles don't get Discord channel access, so only sync when
            # crossing the everyone/staff boundary (not on changes within staff+).
            previously_had_access = old_level is not None and old_level != AccessLevel.everyone
            now_has_access = selected_level is not None and selected_level != AccessLevel.everyone

            access_sync_failed = False
            try:
                if previously_had_access and not now_has_access:
                    await self._ctx.bot.staff_guild.revoke_access(self.profile.profile_id)
                elif not previously_had_access and now_has_access:
                    await self._ctx.bot.staff_guild.grant_access(
                        self.profile.profile_id, self.profile.profile_type
                    )
            except Exception as e:
                logger.error("Failed to sync Discord access for profile %d: %s", self.profile.profile_id, e)
                access_sync_failed = True

            await self._render(interaction)
            if access_sync_failed:
                await interaction.followup.send(
                    self._ctx.t("ftl-view-profile-editor-access-sync-failed"),
                    ephemeral=True,
                )

        level_select.callback = on_level_select

        # ── Appearance button ──

        async def on_customize(interaction: discord.Interaction) -> None:
            if self.resync_profile():
                await self.rebuild()
            await interaction.response.send_modal(ProfileCustomizeModal(self._ctx, editor_view=self))

        components: list[discord.ui.Item[ProfileEditorView]] = [
            discord.ui.Section(
                discord.ui.TextDisplay(header_text),
                accessory=self._btn(
                    self._ctx.t("ftl-view-profile-editor-btn-delete"),
                    discord.ButtonStyle.danger,
                    on_delete,
                    disabled=self._disabled,
                ),
            ),
            discord.ui.Separator(visible=True),
            discord.ui.TextDisplay(summary_text),
            discord.ui.ActionRow(level_select),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(
                self._btn(
                    self._ctx.t("ftl-view-profile-editor-btn-customize"),
                    discord.ButtonStyle.primary,
                    on_customize,
                    disabled=self._disabled,
                )
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            *self._build_overrides_section(),
        ]

        return discord.ui.Container(*components, accent_color=discord.Color.blurple())

    def _build_overrides_section(self) -> list[discord.ui.Item[ProfileEditorView]]:
        """Build the overrides header, list, remove select, and add buttons.

        Returns:
            A list of Component v2 items for the overrides section of the editor card.
        """
        locale = str(self._ctx.interaction.locale) if self._ctx.interaction else CONFIG.default_locale
        index = self._ctx.bot.permission_command_index(locale)

        def _label(k: str) -> str:
            if k.removesuffix("+") not in index.keys:
                return "⚠️ " + k
            return index.label(k)

        # ── Header: override count ──

        overrides_header = self._ctx.t(
            "ftl-view-profile-editor-overrides-header", count=len(self.profile.permission_overrides)
        )
        result: list[discord.ui.Item[ProfileEditorView]] = [discord.ui.TextDisplay(overrides_header)]

        # ── Add buttons ──

        async def on_add_allow(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(
                ProfileAddOverrideModal(self._ctx, editor_view=self, override_value=PermissionOverrideValue.allow)
            )

        async def on_add_deny(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(
                ProfileAddOverrideModal(self._ctx, editor_view=self, override_value=PermissionOverrideValue.deny)
            )

        add_allow_btn = self._btn(
            self._ctx.t("ftl-view-profile-editor-btn-add-allow"),
            discord.ButtonStyle.success,
            on_add_allow,
            disabled=self._disabled,
        )
        add_deny_btn = self._btn(
            self._ctx.t("ftl-view-profile-editor-btn-add-deny"),
            discord.ButtonStyle.danger,
            on_add_deny,
            disabled=self._disabled,
        )

        # ── Override list and remove controls ──

        if self.profile.permission_overrides:
            lines = [
                self._ctx.t(
                    "ftl-view-profile-editor-override-line-allow"
                    if v == PermissionOverrideValue.allow
                    else "ftl-view-profile-editor-override-line-deny",
                    command=_label(k),
                )
                for k, v in self.profile.permission_overrides.items()
            ]
            result.append(discord.ui.TextDisplay("\n".join(lines)))

            if len(self.profile.permission_overrides) <= self._SELECT_MAX:
                # ── Remove select ──

                remove_options = [
                    discord.SelectOption(
                        label=_label(k)[:100],
                        value=k,
                        description=self._ctx.t(
                            "ftl-view-profile-editor-override-value-allow"
                            if v == PermissionOverrideValue.allow
                            else "ftl-view-profile-editor-override-value-deny"
                        ),
                    )
                    for k, v in self.profile.permission_overrides.items()
                ]
                remove_select: discord.ui.Select[ProfileEditorView] = discord.ui.Select(
                    placeholder=self._ctx.t("ftl-view-profile-editor-select-remove-placeholder"),
                    options=remove_options,
                    disabled=self._disabled,
                )

                async def on_remove_override(interaction: discord.Interaction) -> None:
                    key = remove_select.values[0]
                    self.resync_profile()
                    if not await self.remove_override(key, interaction):
                        await self.rebuild()
                        return
                    await self._render(interaction)

                remove_select.callback = on_remove_override
                result.extend([
                    discord.ui.ActionRow(remove_select),
                    discord.ui.ActionRow(add_allow_btn, add_deny_btn),
                ])
            else:

                async def on_remove_by_name(interaction: discord.Interaction) -> None:
                    await interaction.response.send_modal(ProfileRemoveOverrideModal(self._ctx, editor_view=self))

                result.append(
                    discord.ui.ActionRow(
                        add_allow_btn,
                        add_deny_btn,
                        self._btn(
                            self._ctx.t("ftl-view-profile-editor-btn-remove-override"),
                            discord.ButtonStyle.secondary,
                            on_remove_by_name,
                            disabled=self._disabled,
                        ),
                    )
                )
        else:
            result.append(discord.ui.ActionRow(add_allow_btn, add_deny_btn))

        return result

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Return `True` only when the interaction originates from the command invoker."""
        return interaction.user == self._ctx.author

    async def on_timeout(self) -> None:
        """Disable all interactive elements in the card."""
        self._disabled = True
        self.stop()
        await self.rebuild()


class ProfileListView(discord.ui.LayoutView):
    """Read-only card listing all configured profiles."""

    def __init__(self, ctx: Context, *, profiles: list[ProfileModel]) -> None:
        """Build the list card from the given profiles.

        Args:
            ctx: The command context used for translation.
            profiles: All profiles to display.
        """
        super().__init__(timeout=1.0)  # non-interactive

        lines = [
            ctx.t(
                "ftl-cmd-profile-list-row",
                mention=profile.mention,
                level=profile.access_level
                if profile.access_level is not None
                else _("ftl-cmd-profile-list-no-level"),
                overrides=_("ftl-cmd-profile-list-overrides", count=len(profile.permission_overrides)),
            )
            for profile in profiles
        ]

        title = ctx.t("ftl-cmd-profile-list-title", count=len(profiles))
        tip = ctx.t("ftl-cmd-profile-list-tip")
        content = f"{title}\n\n" + "\n".join(lines)

        children: list[discord.ui.Item[ProfileListView]] = [
            discord.ui.TextDisplay(content),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(tip),
        ]
        self.add_item(discord.ui.Container(*children, accent_color=discord.Color.blurple()))


@lazy_hybrid_group(
    name=_("ftl-cmd-profile-name"),
    fallback=_("ftl-cmd-profile-fallback-name"),
    description=_("ftl-cmd-profile-description"),
)
async def profile_command(cog: Utility, ctx: Context) -> None:
    """List every profile that has been created, sorted by access level.

    Args:
        cog: The [`Utility`][] cog instance.
        ctx: The command context.
    """
    profiles = ctx.bot.database_client.profiles
    if not profiles:
        await ctx.reply(_("ftl-cmd-profile-list-empty"))
        return

    sorted_profiles = sorted(profiles, key=lambda p: (-int(p.access_level or 0), p.profile_type.value))
    await ctx.reply(view=ProfileListView(ctx, profiles=sorted_profiles))


@wrap(discord.app_commands.rename, target=_("ftl-cmd-profile-edit-param-target-name"))
@wrap(discord.app_commands.describe, target=_("ftl-cmd-profile-edit-param-target-description"))
@profile_command.command(name=_("ftl-cmd-profile-edit-name"), description=_("ftl-cmd-profile-edit-description"))
async def profile_edit_command(cog: Utility, ctx: Context, target: ProfileLookup) -> None:
    """Open an editor for a user or role's profile.

    Creates a temporary profile first if none exists. The editor allows changing the
    access level, tag, color, and per-command permission overrides all from one card.

    Args:
        cog: The [`Utility`][modmail.cogs.utility.Utility] cog instance.
        ctx: The command context.
        target: The resolved [`ProfileResult`][] for the target user or role.
    """
    profile = target.profile
    if profile is None:
        profile = ProfileModel(
            bot_id=CONFIG.bot.bot_id,
            profile_id=target.entity.id,
            profile_type=target.profile_type,
        )

    view = ProfileEditorView(ctx=ctx, profile=profile)
    await view.build()
    message = await ctx.reply(view=view)
    view.message = message


@wrap(
    discord.app_commands.rename,
    target=_("ftl-cmd-profile-delete-param-target-name"),
    id_=_("ftl-cmd-profile-delete-param-id-name"),
)
@wrap(
    discord.app_commands.describe,
    target=_("ftl-cmd-profile-delete-param-target-description"),
    id_=_("ftl-cmd-profile-delete-param-id-description"),
)
@profile_command.command(
    name=_("ftl-cmd-profile-delete-name"), description=_("ftl-cmd-profile-delete-description")
)
async def profile_delete_command(
    cog: Utility,
    ctx: Context,
    target: ProfileLookup | None,
    id_: int | None,
) -> None:
    """Delete a profile, removing all overrides and access level settings.

    Exactly one of `target` or `id_` must be provided. The `id_` parameter
    exists for cases where the Discord user or role has already been deleted and
    can no longer be resolved by mention or name.

    Also revokes Modmail category access for the deleted profile if it had
    staff-or-above access.

    Args:
        cog: The [`Utility`][modmail.cogs.utility.Utility] cog instance.
        ctx: The command context.
        target: The resolved [`ProfileResult`][] for the target user or role
            (`None` when using `id_` instead).
        id_: Raw snowflake ID of the profile to delete, used when the Discord entity
            no longer exists (`None` when using `target` instead).
    """
    if target is not None and id_ is not None:
        await ctx.reply(_("ftl-cmd-profile-delete-both"))
        return

    if target is not None:
        profile = target.profile
    elif id_ is not None:
        profile = next((p for p in ctx.bot.database_client.profiles if p.profile_id == id_), None)
    else:
        await ctx.reply(_("ftl-cmd-profile-delete-none"))
        return

    if profile is None:
        await ctx.reply(_("ftl-cmd-profile-delete-not-found"))
        return

    try:
        await ctx.bot.database_client.delete_profile(profile_id=profile.profile_id)
    except DatabaseOperationError as e:
        logger.error("Failed to delete profile %d: %s", profile.profile_id, e)
        await ctx.reply(_("ftl-cmd-profile-delete-failed"))
        return

    access_sync_failed = False
    if profile.access_level is not None and profile.access_level != AccessLevel.everyone:
        try:
            await ctx.bot.staff_guild.revoke_access(profile.profile_id)
        except Exception as e:
            logger.error("Failed to revoke Discord access for profile %d: %s", profile.profile_id, e)
            access_sync_failed = True

    await ctx.reply(_("ftl-cmd-profile-delete-success", profile=profile.mention))
    if access_sync_failed:
        await ctx.reply(_("ftl-view-profile-editor-access-sync-failed"), ephemeral=True)
