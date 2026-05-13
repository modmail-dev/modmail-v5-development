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
from modmail.core import (
    BaseLayoutView,
    BaseModal,
    Context,
    ParamInfo,
    ProfileLookup,
    _,
    admin_only,
    bot_group,
    ephemeral_scope,
    locale_for,
)
from modmail.enum import AccessLevel, PermissionOverrideValue, ProfileType, RequiredAccessLevel
from modmail.errors import DatabaseOperationError

if TYPE_CHECKING:
    from .. import Utility

__all__ = ["profile_command"]

logger = logging.getLogger(__name__)


class ProfileCustomizeModal(BaseModal):
    """Modal for customizing a profile's appearance settings."""

    def __init__(
        self,
        *,
        editor_view: ProfileEditorView,
        timeout: float = 300.0,
    ) -> None:
        """Build the modal with the current customization fields.

        Args:
            editor_view: The parent [`ProfileEditorView`][] that owns the shared profile state.
            timeout: Seconds before the modal stops accepting input.
        """
        super().__init__(
            editor_view._bot,
            editor_view._author,
            title=_("ftl-modal-profile-customize-title"),
            interaction=editor_view._interaction,
            timeout=timeout,
        )
        self._editor_view = editor_view

        self.color: discord.ui.TextInput[ProfileCustomizeModal] = discord.ui.TextInput(
            label=self._t("ftl-modal-profile-customize-color"),
            placeholder=self._t("ftl-modal-profile-customize-color-placeholder"),
            default=utils.int_to_color_hex(self.profile.color) if self.profile.color is not None else None,
            required=False,
        )
        self.tag: discord.ui.TextInput[ProfileCustomizeModal] = discord.ui.TextInput(
            label=self._t("ftl-modal-profile-customize-tag"),
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

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate and persist the submitted customization values, then refresh the card.

        Args:
            interaction: The submission interaction from Discord.
        """
        if (
            self.color.value
            and re.match(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", self.color.value) is None
        ):
            await self.send_ephemeral(interaction, _("ftl-modal-profile-customize-color-invalid"))
            return

        to_update: dict[str, Any] = {}
        if self._editor_view.resync_profile():
            self._editor_view.render()

        color = utils.color_hex_to_int(self.color.value) if self.color.value else None
        if color != self.profile.color:
            to_update["color"] = color

        tag = self.tag.value or None
        if tag != self.profile.tag:
            to_update["tag"] = tag

        if to_update:
            self.defer(interaction)
            new_profile = self.profile.model_copy(update=to_update)
            try:
                await self._bot.database_client.update_profile(new_profile)
            except DatabaseOperationError as e:
                logger.error("Failed to update profile %d customization: %s", new_profile.profile_id, e)
                await self.send_ephemeral(interaction, _("ftl-view-profile-editor-update-failed"))
                return
            logger.debug("Updated profile %d customization: %s.", new_profile.profile_id, to_update)
            self._editor_view.profile = new_profile
            self._editor_view.render()

        await self.send_ephemeral(
            interaction, _("ftl-modal-profile-customize-success", profile=self.profile.mention)
        )


class ProfileAddOverrideModal(BaseModal):
    """Modal for adding an allow or deny permission override to a profile."""

    def __init__(
        self,
        *,
        editor_view: ProfileEditorView,
        override_value: PermissionOverrideValue,
        timeout: float = 300.0,
    ) -> None:
        """Build the modal with a command name text input.

        Args:
            editor_view: The parent [`ProfileEditorView`][] that owns the shared profile state.
            override_value: Whether to allow or deny the entered command.
            timeout: Seconds before the modal stops accepting input.
        """
        super().__init__(
            editor_view._bot,
            editor_view._author,
            title=_("ftl-modal-profile-add-override-allow-title")
            if override_value == PermissionOverrideValue.allow
            else _("ftl-modal-profile-add-override-deny-title"),
            interaction=editor_view._interaction,
            timeout=timeout,
        )
        self._editor_view = editor_view
        self._override_value = override_value

        self.command_name: discord.ui.TextInput[ProfileAddOverrideModal] = discord.ui.TextInput(
            label=self._t("ftl-modal-profile-add-override-command-label"),
            placeholder=self._t("ftl-modal-profile-add-override-command-placeholder"),
            required=True,
        )
        self.add_item(self.command_name)

    @property
    def profile(self) -> ProfileModel:
        """The current customized profile model."""
        return self._editor_view.profile

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate the command name and persist the override, then refresh the card.

        Args:
            interaction: The submission interaction from Discord.
        """
        # Since display labels are sent via ephemeral, can use the user's own locale here
        index = self._bot.permission_command_index(locale_for(interaction))

        canonical = index.resolve(self.command_name.value)
        if canonical is None:
            await self.send_ephemeral(
                interaction, _("ftl-cmd-profile-override-command-not-found", command=self.command_name.value)
            )
            return

        base = canonical.removesuffix("+")

        for cmd in self._bot.walk_commands():
            if self._bot.get_canonical_command_name(cmd) == base:
                if canonical != base and not isinstance(cmd, commands.Group):
                    canonical = base  # wildcards only apply to groups

                if CONFIG.bot.enable_jishaku and cmd.cog_name == "Jishaku":
                    await self.send_ephemeral(interaction, _("ftl-cmd-profile-override-jishaku-command"))
                    return

                if self._bot.get_command_access_level(cmd) == RequiredAccessLevel.owner:
                    # Only actual owner allowed to override owner-only commands
                    if not await self._bot.is_owner(self._author):
                        await self.send_ephemeral(
                            interaction,
                            _("ftl-cmd-profile-override-owner-command", command=self.command_name.value),
                        )
                        return
                break

        display = index.label(canonical)

        if self._editor_view.resync_profile():
            self._editor_view.render()

        if self.profile.permission_overrides.get(canonical) == self._override_value:
            await self.send_ephemeral(
                interaction,
                _("ftl-modal-profile-add-override-already-allow", command=display)
                if self._override_value == PermissionOverrideValue.allow
                else _("ftl-modal-profile-add-override-already-deny", command=display),
            )
            return

        self.defer(interaction)
        overrides = self.profile.permission_overrides.copy()
        overrides[canonical] = self._override_value
        new_profile = self.profile.model_copy(update={"permission_overrides": overrides})
        try:
            await self._bot.database_client.update_profile(new_profile)
        except DatabaseOperationError as e:
            logger.error("Failed to set override %r on profile %d: %s", canonical, new_profile.profile_id, e)
            await self.send_ephemeral(interaction, _("ftl-view-profile-editor-update-failed"))
            return

        logger.debug(
            "Set %s override for command %r on profile %d.",
            self._override_value.value,
            canonical,
            new_profile.profile_id,
        )
        self._editor_view.profile = new_profile
        self._editor_view.render()

        await self.send_ephemeral(
            interaction,
            _("ftl-view-profile-editor-override-allow-success", command=display)
            if self._override_value == PermissionOverrideValue.allow
            else _("ftl-view-profile-editor-override-deny-success", command=display),
        )


class ProfileRemoveOverrideModal(BaseModal):
    """Modal for removing a permission override by name (used when there are more than 25)."""

    def __init__(
        self,
        *,
        editor_view: ProfileEditorView,
        timeout: float = 300.0,
    ) -> None:
        """Build the modal with an override name text input.

        Args:
            editor_view: The parent [`ProfileEditorView`][] that owns the shared profile state.
            timeout: Seconds before the modal stops accepting input.
        """
        super().__init__(
            editor_view._bot,
            editor_view._author,
            title=_("ftl-modal-profile-remove-override-title"),
            interaction=editor_view._interaction,
            timeout=timeout,
        )
        self._editor_view = editor_view

        self.override_name: discord.ui.TextInput[ProfileRemoveOverrideModal] = discord.ui.TextInput(
            label=self._t("ftl-modal-profile-remove-override-name-label"),
            placeholder=self._t("ftl-modal-profile-remove-override-name-placeholder"),
            required=True,
        )
        self.add_item(self.override_name)

    @property
    def profile(self) -> ProfileModel:
        """The current customized profile model."""
        return self._editor_view.profile

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Remove the named override from the profile, then refresh the card.

        Args:
            interaction: The submission interaction from Discord.
        """
        # Since display labels are sent via ephemeral, can use the user's own locale here
        index = self._bot.permission_command_index(locale_for(interaction))

        sanitized = index.sanitize(self.override_name.value)
        resolved = index.resolve(self.override_name.value, allow_raw_key=True)

        if self._editor_view.resync_profile():
            self._editor_view.render()

        # Remove resolved if exists, otherwise remove sanitized input if it's an orphaned key
        key_to_remove = (
            resolved
            if resolved is not None and resolved in self.profile.permission_overrides
            else sanitized
            if sanitized in self.profile.permission_overrides
            else None
        )

        if key_to_remove is None:
            await self.send_ephemeral(
                interaction,
                _("ftl-modal-profile-remove-override-not-found", command=self.override_name.value),
            )
            return

        self.defer(interaction)
        if not await self._editor_view.remove_override(key_to_remove):
            await self.send_ephemeral(interaction, _("ftl-view-profile-editor-update-failed"))
            return

        self._editor_view.render()
        display = index.label(key_to_remove)
        await self.send_ephemeral(interaction, _("ftl-modal-profile-remove-override-success", command=display))


class ConfirmDeleteView(BaseLayoutView):
    """Ephemeral Component v2 confirm/cancel card shown before deleting a profile."""

    _interaction: discord.Interaction

    def __init__(
        self,
        *,
        editor_view: ProfileEditorView,
        interaction: discord.Interaction,
        timeout: float = 120.0,
    ) -> None:
        """Build the card with confirm text and confirm/cancel buttons.

        Args:
            editor_view: The [`ProfileEditorView`][] that owns the profile to delete.
            interaction: The interaction that opened this card (used to clean up on timeout).
            timeout: Seconds before the confirmation card expires.
        """
        super().__init__(editor_view._bot, editor_view._author, interaction=interaction, timeout=timeout)
        self._editor_view = editor_view
        self._interaction = interaction

        confirm_btn: discord.ui.Button[ConfirmDeleteView] = discord.ui.Button(
            label=self._t("ftl-view-profile-editor-delete-btn-confirm"),
            style=discord.ButtonStyle.danger,
        )
        confirm_btn.callback = self._on_confirm

        cancel_btn: discord.ui.Button[ConfirmDeleteView] = discord.ui.Button(
            label=self._t("ftl-view-prompt-cancel-label"),
            style=discord.ButtonStyle.secondary,
        )
        cancel_btn.callback = self._on_cancel

        action_row: discord.ui.ActionRow[ConfirmDeleteView] = discord.ui.ActionRow()
        action_row.add_item(confirm_btn)
        action_row.add_item(cancel_btn)

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(self._t("ftl-view-profile-editor-delete-confirm")),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                action_row,
            )
        )

    @property
    def profile(self) -> ProfileModel:
        """The current customized profile model."""
        return self._editor_view.profile

    async def delete_original_response(self) -> None:
        """Delete the original ephemeral confirmation message."""
        with contextlib.suppress(discord.HTTPException):
            await self._interaction.delete_original_response()

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        """Delete the profile, revoke channel access, and show a terminal card.

        Args:
            interaction: The button interaction from Discord.
        """
        self.defer(interaction)

        try:
            await self._bot.database_client.delete_profile(profile_id=self.profile.profile_id)
        except DatabaseOperationError as e:
            logger.error("Failed to delete profile %d: %s", self.profile.profile_id, e)
            await self.send_ephemeral(interaction, _("ftl-view-profile-editor-update-failed"))
            return

        logger.debug("Deleted profile %d.", self.profile.profile_id)
        self.stop()

        # Only staff+ levels have Discord channel access; everyone/None do not.
        access_sync_failed = False
        if self.profile.access_level is not None and self.profile.access_level != AccessLevel.everyone:
            try:
                await self._bot.staff_guild.revoke_access(self.profile.profile_id)
            except Exception as e:
                logger.error("Failed to revoke Discord access for profile %d: %s", self.profile.profile_id, e)
                access_sync_failed = True

        # Using _editor_view._t() since close_message will be rendered onto _editor_view
        close_message = self._editor_view._t(
            "ftl-view-profile-editor-deleted-content", profile=self.profile.mention
        )
        if access_sync_failed:
            close_message += "\n" + self._editor_view._t("ftl-view-profile-editor-access-sync-failed")

        self._editor_view.close_as_done(close_message, color=discord.Color.blurple())
        await self.delete_original_response()

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        """Dismiss the ephemeral confirm message without deleting.

        Args:
            interaction: The button interaction from Discord.
        """
        self.defer(interaction)
        self.stop()
        await self.delete_original_response()

    async def on_timeout(self) -> None:
        """Delete the ephemeral confirm card when it expires."""
        await self.delete_original_response()


class ProfileEditorView(BaseLayoutView):
    """In-place editor for a user or role profile.

    Renders the full profile state (access level, customization, overrides) inside
    a single updating card. Every interaction rebuilds the card in place via
    [`render`][].

    Warning:
        Set `message` after sending so the view can edit its card on timeout.

    Examples:
        ```python
        view = ProfileEditorView(ctx, profile=profile)
        view.build()
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
        super().__init__(ctx.bot, ctx.author, interaction=ctx.interaction, timeout=timeout)
        self.profile = profile
        """The profile being edited, updated in place as the user interacts."""
        self._done_card: discord.ui.Container[ProfileEditorView] | None = None
        """When set, this card is rendered instead of the interactive editor."""
        self._disabled: bool = False
        """When `True`, all interactive elements are rendered disabled (set on timeout)."""
        self._profile_sync_task: asyncio.Task[None] | None = None
        """Periodically re-renders the card when the profile is changed externally."""
        self._confirm_delete_view: ConfirmDeleteView | None = None
        """Active confirmation card, if any — only one may exist at a time."""

    async def remove_override(self, key: str) -> bool:
        """Remove an override by key and persist the change.

        Args:
            key: Override key to remove. Must be present in the current overrides.

        Returns:
            `True` on success. `False` if the key was not found in the current
            overrides or the database update failed — the caller is responsible
            for surfacing the error.
        """
        overrides = self.profile.permission_overrides.copy()
        if key not in overrides:
            return False

        del overrides[key]
        new_profile = self.profile.model_copy(update={"permission_overrides": overrides})

        try:
            await self._bot.database_client.update_profile(new_profile)
        except DatabaseOperationError as e:
            logger.error("Failed to remove override %r from profile %d: %s", key, new_profile.profile_id, e)
            return False

        self.profile = new_profile
        return True

    def close_as_done(self, content: str, *, color: discord.Color | None = None) -> None:
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
        self.render()

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
        current = self._bot.database_client.get_profile(self.profile.profile_id, self.profile.profile_type)
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
                self.render()

    def render(self, interaction: discord.Interaction | None = None, build: bool = True) -> None:
        """Rebuild the card and update the editor message.

        `interaction`, if provided, must originate from a component on this view's own message.
        This is verified by comparing [`message`][] to `interaction.message` — if they differ,
        the update falls back to editing [`message`][] directly via REST.

        Args:
            interaction: A component interaction from this view's message, used for the edit.
            build: Whether to call [`build`][] before rendering.
        """
        if build:
            self.build()

        if interaction is not None and (
            self.message is not None
            and interaction.message is not None
            and interaction.message.id != self.message.id
        ):
            logger.debug("The interaction message should be the editor's message, this is a bug.")
            interaction = None

        self._update_message(interaction)

    def build(self) -> None:
        """Clear and rebuild the container for the current profile state.

        Must be called before sending the initial message and after each state change.
        """
        self.clear_items()
        self.add_item(self._build_container())
        if self._profile_sync_task is None:
            self._profile_sync_task = asyncio.create_task(self._profile_sync_loop())

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

        header_text = self._t(
            "ftl-view-profile-editor-header",
            profile=self.profile.mention,
            type=_("ftl-view-profile-editor-type-user")
            if self.profile.profile_type == ProfileType.user
            else _("ftl-view-profile-editor-type-role"),
        )

        async def on_delete(interaction: discord.Interaction) -> None:
            profile = self._bot.database_client.get_profile(self.profile.profile_id, self.profile.profile_type)
            if profile is None:
                # The profile doesn't exist in the first place
                self.defer(interaction)
                self.close_as_done(
                    self._t("ftl-view-profile-editor-deleted-content", profile=self.profile.mention),
                    color=discord.Color.blurple(),
                )
                return

            if self._confirm_delete_view is not None and not self._confirm_delete_view.is_finished():
                self._confirm_delete_view.stop()
                with contextlib.suppress(discord.HTTPException):
                    await self._confirm_delete_view.delete_original_response()

            with ephemeral_scope(interaction):
                self._confirm_delete_view = ConfirmDeleteView(editor_view=self, interaction=interaction)
                await self.send(interaction, view=self._confirm_delete_view)

        # ── Summary: current level, tag, color ──

        summary_text = self._t(
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
                label=self._t("ftl-view-profile-editor-level-none"),
                value=self._LEVEL_NONE,
                default=self.profile.access_level is None,
            ),
            discord.SelectOption(
                label=self._t("ftl-access-level-everyone"),
                value=AccessLevel.everyone.name,
                default=self.profile.access_level == AccessLevel.everyone,
            ),
            discord.SelectOption(
                label=self._t("ftl-access-level-staff"),
                value=AccessLevel.staff.name,
                default=self.profile.access_level == AccessLevel.staff,
            ),
            discord.SelectOption(
                label=self._t("ftl-access-level-manager"),
                value=AccessLevel.manager.name,
                default=self.profile.access_level == AccessLevel.manager,
            ),
            discord.SelectOption(
                label=self._t("ftl-access-level-admin"),
                value=AccessLevel.admin.name,
                default=self.profile.access_level == AccessLevel.admin,
            ),
        ]
        level_select: discord.ui.Select[ProfileEditorView] = discord.ui.Select(
            placeholder=self._t("ftl-view-profile-editor-select-level-placeholder"),
            options=level_options,
            disabled=self._disabled,
        )

        async def on_level_select(interaction: discord.Interaction) -> None:
            selected_option = level_select.values[0]
            selected_level: AccessLevel | None = (
                None if selected_option == self._LEVEL_NONE else AccessLevel[selected_option]
            )

            if self.resync_profile():
                self.render(interaction)
            else:
                self.defer(interaction)

            if self.profile.access_level == selected_level:
                logger.debug(
                    "Access level didn't change for profile %d, skipping update.", self.profile.profile_id
                )
                return

            old_level = self.profile.access_level
            new_profile = self.profile.model_copy(update={"access_level": selected_level})
            try:
                await self._bot.database_client.update_profile(new_profile)
            except DatabaseOperationError as e:
                logger.error("Failed to update profile %d access level: %s", new_profile.profile_id, e)
                await self.send_ephemeral(interaction, _("ftl-view-profile-editor-update-failed"))
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
                    await self._bot.staff_guild.revoke_access(self.profile.profile_id)
                elif not previously_had_access and now_has_access:
                    await self._bot.staff_guild.grant_access(self.profile.profile_id, self.profile.profile_type)
            except Exception as e:
                logger.error("Failed to sync Discord access for profile %d: %s", self.profile.profile_id, e)
                access_sync_failed = True

            self.render(interaction)
            if access_sync_failed:
                await self.send_ephemeral(interaction, _("ftl-view-profile-editor-access-sync-failed"))

        level_select.callback = on_level_select

        # ── Appearance button ──

        async def on_customize(interaction: discord.Interaction) -> None:
            changed = self.resync_profile()
            await interaction.response.send_modal(ProfileCustomizeModal(editor_view=self))
            if changed:
                # Must render after sending the modal, so render doesn't use up the response
                self.render(interaction)

        components: list[discord.ui.Item[ProfileEditorView]] = [
            discord.ui.Section(
                discord.ui.TextDisplay(header_text),
                accessory=self._btn(
                    self._t("ftl-view-profile-editor-btn-delete"),
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
                    self._t("ftl-view-profile-editor-btn-customize"),
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
        # ── Header: override count ──

        overrides_header = self._t(
            "ftl-view-profile-editor-overrides-header", count=len(self.profile.permission_overrides)
        )
        result: list[discord.ui.Item[ProfileEditorView]] = [discord.ui.TextDisplay(overrides_header)]

        # ── Add buttons ──

        async def on_add_allow(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(
                ProfileAddOverrideModal(editor_view=self, override_value=PermissionOverrideValue.allow)
            )

        async def on_add_deny(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(
                ProfileAddOverrideModal(editor_view=self, override_value=PermissionOverrideValue.deny)
            )

        add_allow_btn = self._btn(
            self._t("ftl-view-profile-editor-btn-add-allow"),
            discord.ButtonStyle.success,
            on_add_allow,
            disabled=self._disabled,
        )
        add_deny_btn = self._btn(
            self._t("ftl-view-profile-editor-btn-add-deny"),
            discord.ButtonStyle.danger,
            on_add_deny,
            disabled=self._disabled,
        )

        # ── Override list and remove controls ──

        # Used for labeling, so only using the display locale
        index = self._bot.permission_command_index(self._locale)

        def _label(k: str) -> str:
            if k.removesuffix("+") not in index.keys:
                return "⚠️ " + k
            return index.label(k)

        def _override_sort_key(k: str) -> tuple[list[str], int]:
            is_wildcard = k.endswith("+")
            base = k[:-1] if is_wildcard else k
            return base.split(), 0 if is_wildcard else 1

        if overrides := sorted(
            self.profile.permission_overrides.items(), key=lambda item: _override_sort_key(item[0])
        ):
            lines = [
                self._t(
                    "ftl-view-profile-editor-override-line-allow"
                    if v == PermissionOverrideValue.allow
                    else "ftl-view-profile-editor-override-line-deny",
                    command=_label(k),
                )
                for k, v in overrides
            ]
            result.append(discord.ui.TextDisplay("\n".join(lines)))

            if len(overrides) <= self._SELECT_MAX:
                # ── Remove select ──

                remove_options = [
                    discord.SelectOption(
                        label=_label(k)[:100],
                        value=k,
                        description=self._t(
                            "ftl-view-profile-editor-override-value-allow"
                            if v == PermissionOverrideValue.allow
                            else "ftl-view-profile-editor-override-value-deny"
                        ),
                    )
                    for k, v in overrides
                ]
                remove_select: discord.ui.Select[ProfileEditorView] = discord.ui.Select(
                    placeholder=self._t("ftl-view-profile-editor-select-remove-placeholder"),
                    options=remove_options,
                    disabled=self._disabled,
                )

                async def on_remove_override(interaction: discord.Interaction) -> None:
                    key = remove_select.values[0]
                    if self.resync_profile():
                        self.render(interaction)
                    else:
                        self.defer(interaction)

                    if not await self.remove_override(key):
                        await self.send_ephemeral(interaction, _("ftl-view-profile-editor-update-failed"))
                    else:
                        self.render(interaction)

                remove_select.callback = on_remove_override
                result.extend([
                    discord.ui.ActionRow(remove_select),
                    discord.ui.ActionRow(add_allow_btn, add_deny_btn),
                ])
            else:

                async def on_remove_by_name(interaction: discord.Interaction) -> None:
                    await interaction.response.send_modal(ProfileRemoveOverrideModal(editor_view=self))

                result.append(
                    discord.ui.ActionRow(
                        add_allow_btn,
                        add_deny_btn,
                        self._btn(
                            self._t("ftl-view-profile-editor-btn-remove-override"),
                            discord.ButtonStyle.secondary,
                            on_remove_by_name,
                            disabled=self._disabled,
                        ),
                    )
                )
        else:
            result.append(discord.ui.ActionRow(add_allow_btn, add_deny_btn))

        return result

    async def on_timeout(self) -> None:
        """Disable all interactive elements in the card."""
        self._disabled = True
        self.render()


class ProfileListView(BaseLayoutView):
    """Read-only card listing all configured profiles."""

    def __init__(
        self,
        ctx: Context,
        *,
        profiles: list[ProfileModel],
    ) -> None:
        """Build the list card from the given profiles.

        Args:
            ctx: The command context used for translation.
            profiles: All profiles to display.
        """
        super().__init__(ctx.bot, ctx.author, interaction=ctx.interaction)

        lines = [
            self._t(
                "ftl-cmd-profile-list-row",
                mention=profile.mention,
                level=profile.access_level
                if profile.access_level is not None
                else _("ftl-cmd-profile-list-no-level"),
                overrides=_("ftl-cmd-profile-list-overrides", count=len(profile.permission_overrides)),
            )
            for profile in profiles
        ]

        title = self._t("ftl-cmd-profile-list-title", count=len(profiles))
        tip = self._t("ftl-cmd-profile-list-tip")
        content = f"{title}\n\n" + "\n".join(lines)

        children: list[discord.ui.Item[ProfileListView]] = [
            discord.ui.TextDisplay(content),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(tip),
        ]
        self.add_item(discord.ui.Container(*children, accent_color=discord.Color.blurple()))


@admin_only
@bot_group(
    name=_("ftl-cmd-profile-name"),
    fallback=_("ftl-cmd-profile-fallback-name"),
    description=_("ftl-cmd-profile-description"),
    help=_("ftl-cmd-profile-help"),
)
async def profile_command(cog: Utility, ctx: Context) -> None:
    """List every profile that has been created, sorted by access level.

    Args:
        cog: The [`Utility`][] cog instance.
        ctx: The command context.
    """
    profiles = cog.bot.database_client.profiles
    if not profiles:
        await ctx.reply(_("ftl-cmd-profile-list-empty"), ephemeral=True)
        return

    sorted_profiles = sorted(profiles, key=lambda p: (-int(p.access_level or 0), p.profile_type.value))
    await ctx.reply(view=ProfileListView(ctx, profiles=sorted_profiles))


@profile_command.command(
    name=_("ftl-cmd-profile-edit-name"),
    description=_("ftl-cmd-profile-edit-description"),
    help=_("ftl-cmd-profile-edit-help"),
    param_info={
        "target": ParamInfo(
            name=_("ftl-cmd-profile-edit-param-target-name"),
            description=_("ftl-cmd-profile-edit-param-target-description"),
        )
    },
)
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

    view = ProfileEditorView(ctx, profile=profile)
    view.build()
    message = await ctx.reply(view=view)
    view.message = message


@profile_command.command(
    name=_("ftl-cmd-profile-delete-name"),
    description=_("ftl-cmd-profile-delete-description"),
    help=_("ftl-cmd-profile-delete-help"),
    param_info={
        "target": ParamInfo(
            name=_("ftl-cmd-profile-delete-param-target-name"),
            description=_("ftl-cmd-profile-delete-param-target-description"),
        ),
        "id_": ParamInfo(
            name=_("ftl-cmd-profile-delete-param-id-name"),
            description=_("ftl-cmd-profile-delete-param-id-description"),
        ),
    },
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
        await ctx.reply(_("ftl-cmd-profile-delete-both"), ephemeral=True)
        return

    if target is not None:
        profile = target.profile
    elif id_ is not None:
        profile = next((p for p in cog.bot.database_client.profiles if p.profile_id == id_), None)
    else:
        await ctx.reply(_("ftl-cmd-profile-delete-none"), ephemeral=True)
        return

    if profile is None:
        await ctx.reply(_("ftl-cmd-profile-delete-not-found"), ephemeral=True)
        return

    try:
        await cog.bot.database_client.delete_profile(profile_id=profile.profile_id)
    except DatabaseOperationError as e:
        logger.error("Failed to delete profile %d: %s", profile.profile_id, e)
        await ctx.reply(_("ftl-cmd-profile-delete-failed"), ephemeral=True)
        return

    access_sync_failed = False
    if profile.access_level is not None and profile.access_level != AccessLevel.everyone:
        try:
            await cog.bot.staff_guild.revoke_access(profile.profile_id)
        except Exception as e:
            logger.error("Failed to revoke Discord access for profile %d: %s", profile.profile_id, e)
            access_sync_failed = True

    await ctx.reply(_("ftl-cmd-profile-delete-success", profile=profile.mention))
    if access_sync_failed:
        await ctx.reply(_("ftl-view-profile-editor-access-sync-failed"), ephemeral=True)
