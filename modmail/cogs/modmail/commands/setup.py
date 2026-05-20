"""Server setup command."""

from __future__ import annotations

import asyncio
import enum
import logging
from typing import TYPE_CHECKING, Any, Literal

import discord

from modmail.core import BaseLayoutView, Context, bot_command, owner_only
from modmail.errors import NoModmailCategoryError
from modmail.i18n import _

if TYPE_CHECKING:
    from .. import Modmail

__all__ = ["setup_command"]

logger = logging.getLogger(__name__)

setup_lock = asyncio.Lock()


class _WizardStep(enum.IntEnum):
    """Wizard navigation steps.

    Negative values are terminal states. [`STEP_0`][] through [`STEP_4`][] are the interactive
    steps shown to the user in sequence. [`WORKING`][] is a non-interactive terminal
    state shown while the setup API calls are in progress.
    """

    TIMEOUT = -2
    """Wizard stopped because the interaction timed out."""
    CANCELED = -1
    """User clicked Cancel at any step."""
    STEP_0 = 0
    """Already-configured warning (skipped on a fresh server)."""
    STEP_1 = 1
    """Channel type selection: category or forum."""
    STEP_2 = 2
    """Source selection: create new or use an existing channel."""
    STEP_3 = 3
    """Existing channel picker (only reached when use_existing is True)."""
    STEP_4 = 4
    """Confirmation screen summarizing what will be created."""
    WORKING = 5
    """Non-interactive card shown while setup API calls are in progress."""


class SetupWizardView(BaseLayoutView):
    """Multi-step in-place setup wizard rendered as a single updating card.

    Renders all interaction steps inside one Discord message that edits in
    place on every button or select interaction. Each step is a fresh
    [`discord.ui.Container`][] produced by a builder method. State advances by
    modifying `_step` and calling [`_render`][].

    Warning:
        Call `wizard.build()` before sending the initial message, and set
        `message` after sending, before `await wizard.wait()`. Without `message`,
        timeout and error cards cannot be pushed.

    Examples:
        ```python
        wizard = SetupWizardView(ctx, show_reconfigure_warning=False, timeout=300.0)
        wizard.build()
        msg = await ctx.reply(view=wizard)
        wizard.message = msg
        timed_out = await wizard.wait()
        ```
    """

    def __init__(
        self,
        ctx: Context,
        *,
        show_reconfigure_warning: bool,
        timeout: float = 300.0,
    ) -> None:
        """Build the wizard state without rendering the initial step.

        Args:
            ctx: Command context used for locale resolution and guild access.
            show_reconfigure_warning: Whether to show the already-configured warning before step 1.
            timeout: Seconds before the wizard stops accepting interactions.
        """
        super().__init__(ctx.bot, ctx.author, interaction=ctx.interaction, timeout=timeout)
        self._step: _WizardStep = _WizardStep.STEP_0 if show_reconfigure_warning else _WizardStep.STEP_1
        self._completed: bool = False
        self._setup_type: Literal["category", "forum"] | None = None
        self._channel_id: int | None = None
        self._channel_name: str | None = None

    @property
    def completed(self) -> bool:
        """`True` once the user clicked Confirm and the working card is shown."""
        return self._completed

    @property
    def canceled(self) -> bool:
        """`True` if the user clicked Cancel at any step."""
        return self._step == _WizardStep.CANCELED

    @property
    def setup_type(self) -> Literal["category", "forum"]:
        """Whether tickets use a category or forum layout.

        Only valid after the wizard completes.

        Raises:
            RuntimeError: If accessed before the wizard has completed.
        """
        if not self._completed or self._setup_type is None:
            raise RuntimeError("setup_type accessed before wizard completed")
        return self._setup_type

    @property
    def use_existing(self) -> bool:
        """Whether the user chose an existing channel rather than creating a new one.

        Only valid after the wizard completes.

        Raises:
            RuntimeError: If accessed before the wizard has completed.
        """
        if not self._completed:
            raise RuntimeError("use_existing accessed before wizard completed")
        return self._channel_id is not None

    @property
    def channel_id(self) -> int | None:
        """Discord ID of the selected existing channel, or `None` if creating a new one.

        Only valid after the wizard completes.

        Raises:
            RuntimeError: If accessed before the wizard has completed.
        """
        if not self._completed:
            raise RuntimeError("channel_id accessed before wizard completed")
        return self._channel_id

    def build(self) -> None:
        """Clear the view's items and add the container for the current step.

        Must be called before sending the initial message.
        """
        self.clear_items()
        self.add_item(self._build_container())

    def _render(self, interaction: discord.Interaction) -> None:
        """Re-render the current step and edit the triggering message in-place.

        Raises:
            RuntimeError: If called after the wizard has already completed.
        """
        if self._completed:
            raise RuntimeError("_render called after wizard completed")
        self.build()
        self._update_message(interaction)

    @staticmethod
    def _btn(label: str, style: discord.ButtonStyle, callback: Any) -> discord.ui.Button[SetupWizardView]:
        """Create a button and bind its callback.

        Args:
            label: Button label text.
            style: Discord button style.
            callback: Async callable to invoke on click.

        Returns:
            The configured button.
        """
        btn: discord.ui.Button[SetupWizardView] = discord.ui.Button(label=label, style=style)
        btn.callback = callback
        return btn

    def _cancel_btn(self) -> discord.ui.Button[SetupWizardView]:
        """Create the shared danger-styled cancel button.

        Returns:
            The configured cancel button.
        """

        async def callback(interaction: discord.Interaction) -> None:  # noqa: RUF029
            self._step = _WizardStep.CANCELED
            self.stop()
            self._render(interaction)

        return self._btn(self._t(_("view.prompt.cancel")), discord.ButtonStyle.danger, callback)

    def _build_container(self) -> discord.ui.Container[SetupWizardView]:
        """Build and return the container for the current step.

        Returns:
            The constructed [`discord.ui.Container`][] for the active step.
        """
        match self._step:
            case _WizardStep.CANCELED | _WizardStep.TIMEOUT:
                return discord.ui.Container(
                    discord.ui.TextDisplay(
                        self._t(
                            _("view.setup.wizard.canceled")
                            if self._step == _WizardStep.CANCELED
                            else _("view.setup.wizard.timeout")
                        )
                    ),
                    accent_color=discord.Color.red(),
                )

            case _WizardStep.STEP_0:

                async def on_continue(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._step = _WizardStep.STEP_1
                    self._render(interaction)

                return discord.ui.Container(
                    discord.ui.TextDisplay(self._t(_("view.setup.wizard.reconfigure.content"))),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        self._btn(
                            self._t(_("view.setup.wizard.reconfigure.btn_continue")),
                            discord.ButtonStyle.primary,
                            on_continue,
                        ),
                        self._cancel_btn(),
                    ),
                    accent_color=discord.Color.yellow(),
                )

            case _WizardStep.STEP_1:

                async def on_category(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._setup_type = "category"
                    self._step = _WizardStep.STEP_2
                    self._render(interaction)

                async def on_forum(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._setup_type = "forum"
                    self._step = _WizardStep.STEP_2
                    self._render(interaction)

                category_label = self._t(_("view.setup.wizard.type.category"))
                forum_label = self._t(_("view.setup.wizard.type.forum"))
                return discord.ui.Container(
                    discord.ui.TextDisplay(self._t(_("view.setup.wizard.type.content"))),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        self._btn(category_label, discord.ButtonStyle.primary, on_category),
                        self._btn(forum_label, discord.ButtonStyle.primary, on_forum),
                        self._cancel_btn(),
                    ),
                    accent_color=discord.Color.blurple(),
                )

            case _WizardStep.STEP_2:
                is_category = self._setup_type == "category"

                async def on_create_new(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._channel_id = None
                    self._channel_name = None
                    self._step = _WizardStep.STEP_4
                    self._render(interaction)

                async def on_use_existing(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._step = _WizardStep.STEP_3
                    self._render(interaction)

                async def on_back_step_2(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._setup_type = None
                    self._channel_id = None
                    self._channel_name = None
                    self._step = _WizardStep.STEP_1
                    self._render(interaction)

                create_label = self._t(_("view.setup.wizard.new_existing.btn.create"))
                existing_label = self._t(
                    _("view.setup.wizard.new_existing.btn.existing_category")
                    if is_category
                    else _("view.setup.wizard.new_existing.btn.existing_forum")
                )
                back_label = self._t(_("view.setup.wizard.btn.back"))
                return discord.ui.Container(
                    discord.ui.TextDisplay(
                        self._t(
                            _("view.setup.wizard.new_existing.content.category")
                            if is_category
                            else _("view.setup.wizard.new_existing.content.forum")
                        )
                    ),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        self._btn(create_label, discord.ButtonStyle.primary, on_create_new),
                        self._btn(existing_label, discord.ButtonStyle.secondary, on_use_existing),
                        self._btn(back_label, discord.ButtonStyle.secondary, on_back_step_2),
                        self._cancel_btn(),
                    ),
                    accent_color=discord.Color.blurple(),
                )

            case _WizardStep.STEP_3:
                is_category = self._setup_type == "category"

                select: discord.ui.ChannelSelect[SetupWizardView] = discord.ui.ChannelSelect(
                    channel_types=[discord.ChannelType.category if is_category else discord.ChannelType.forum],
                    placeholder=self._t(
                        _("view.setup.wizard.select_existing.placeholder.category")
                        if is_category
                        else _("view.setup.wizard.select_existing.placeholder.forum")
                    ),
                    min_values=1,
                    max_values=1,
                )

                async def on_channel_select(interaction: discord.Interaction) -> None:
                    if not isinstance(interaction.guild, discord.Guild):
                        return  # Shouldn't happen

                    picked = select.values[0]
                    real_channel = interaction.guild.get_channel(picked.id)

                    expected_type = discord.CategoryChannel if is_category else discord.ForumChannel
                    if not isinstance(real_channel, expected_type):
                        await self.send_ephemeral(
                            interaction,
                            _("view.setup.wizard.select_existing.wrong_type.category")
                            if is_category
                            else _("view.setup.wizard.select_existing.wrong_type.forum"),
                        )
                        return

                    min_perms = self._bot.staff_guild.MIN_PERMISSIONS
                    if (~real_channel.permissions_for(interaction.guild.me) & min_perms).value:
                        await self.send_ephemeral(interaction, _("view.setup.wizard.select_existing.no_perms"))
                        return

                    self._channel_id = real_channel.id
                    self._channel_name = real_channel.name
                    self._step = _WizardStep.STEP_4
                    self._render(interaction)

                select.callback = on_channel_select

                async def on_back_step_3(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._channel_id = None
                    self._channel_name = None
                    self._step = _WizardStep.STEP_2
                    self._render(interaction)

                back_label = self._t(_("view.setup.wizard.btn.back"))
                return discord.ui.Container(
                    discord.ui.TextDisplay(
                        self._t(
                            _("view.setup.wizard.select_existing.content.category")
                            if is_category
                            else _("view.setup.wizard.select_existing.content.forum")
                        )
                    ),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(select),
                    discord.ui.ActionRow(
                        self._btn(back_label, discord.ButtonStyle.secondary, on_back_step_3),
                        self._cancel_btn(),
                    ),
                    accent_color=discord.Color.blurple(),
                )

            case _WizardStep.STEP_4:
                is_category = self._setup_type == "category"
                use_existing = self._channel_id is not None

                async def on_confirm(interaction: discord.Interaction) -> None:
                    self._step = _WizardStep.WORKING
                    self._completed = True
                    self.build()
                    await self._update_message(interaction)  # Ensure WORKING card is shown before proceeding
                    self.stop()  # Stops the .wait(), proceed the setup in do_setup() below

                async def on_back_step_4(interaction: discord.Interaction) -> None:  # noqa: RUF029
                    self._step = _WizardStep.STEP_3 if self._channel_id is not None else _WizardStep.STEP_2
                    self._render(interaction)

                if use_existing:
                    content = self._t(
                        _("view.setup.wizard.confirm.existing_category")
                        if is_category
                        else _("view.setup.wizard.confirm.existing_forum"),
                        name=self._channel_name or "",
                    )
                else:
                    content = self._t(
                        _("view.setup.wizard.confirm.new_category")
                        if is_category
                        else _("view.setup.wizard.confirm.new_forum")
                    )

                confirm_label = self._t(_("view.setup.wizard.confirm.btn"))
                back_label = self._t(_("view.setup.wizard.btn.back"))
                return discord.ui.Container(
                    discord.ui.TextDisplay(content),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        self._btn(confirm_label, discord.ButtonStyle.success, on_confirm),
                        self._btn(back_label, discord.ButtonStyle.secondary, on_back_step_4),
                        self._cancel_btn(),
                    ),
                    accent_color=discord.Color.green(),
                )

            case _:  # WORKING
                return discord.ui.Container(
                    discord.ui.TextDisplay(self._t(_("view.setup.wizard.working"))),
                    accent_color=discord.Color.orange(),
                )

    def show_success(
        self,
        category_or_forum: discord.CategoryChannel | discord.ForumChannel,
        log_channel: discord.TextChannel | discord.Thread,
        storage_channel: discord.TextChannel,
    ) -> None:
        """Edit the message to the success card after setup completes.

        Args:
            category_or_forum: The category or forum that was set up.
            log_channel: The created log channel or thread.
            storage_channel: The created storage channel.
        """
        if self._setup_type == "category":
            content = self._t(
                _(
                    "view.setup.wizard.success.category",
                    category=category_or_forum.name,
                    log_channel=log_channel.mention,
                    storage_channel=storage_channel.mention,
                )
            )
        else:
            content = self._t(
                _(
                    "view.setup.wizard.success.forum",
                    forum=category_or_forum.mention,
                    log_channel=log_channel.mention,
                    storage_channel=storage_channel.mention,
                )
            )

        self.clear_items()
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(content),
                accent_color=discord.Color.green(),
            )
        )
        self._update_message()

    def show_error(self, text: str) -> None:
        """Edit the message to a generic error card.

        Args:
            text: Error message to display inside the card.
        """
        self.clear_items()
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(text),
                accent_color=discord.Color.red(),
            )
        )
        self._update_message()

    async def on_timeout(self) -> None:
        """Render the timeout card and edit the message."""
        self._step = _WizardStep.TIMEOUT
        self.build()
        self._update_message()


@owner_only
@bot_command(
    name=_("cmd.setup.name"),
    description=_("cmd.setup.description"),
    help=_("cmd.setup.help"),
)
async def setup_command(cog: Modmail, ctx: Context) -> None:
    """Configure the server for Modmail.

    Initiates the setup wizard in the staff guild. Only one setup can run at a
    time — concurrent invocations are rejected immediately.

    Args:
        cog: The Modmail cog instance.
        ctx: The command context containing information about the invocation.
    """
    if ctx.guild is None or ctx.guild.id != cog.bot.staff_guild.guild_id:
        # @param guild_name: Staff guild name
        await ctx.reply(_("msg.setup.wrong_guild", guild_name=cog.bot.staff_guild.guild.name), ephemeral=True)
        return

    if setup_lock.locked():
        await ctx.reply(_("msg.setup.already_running"), ephemeral=True)
        return

    async with setup_lock:
        await do_setup(ctx)


async def do_setup(ctx: Context) -> None:
    """Run the interactive setup wizard and execute the resulting configuration.

    Sends a single wizard card that updates in place at each step, then — once
    the user confirms — performs all required Discord API calls to create or
    configure the Modmail channel structure.

    Args:
        ctx: The command context containing information about the invocation.

    Raises:
        discord.HTTPException: If an unexpected error occurred during API calls.
        RuntimeError: If the context is missing the expected guild.
    """
    if ctx.guild is None:
        raise RuntimeError("Expected guild context for setup")

    if (~ctx.guild.me.guild_permissions & ctx.bot.staff_guild.MIN_PERMISSIONS).value:
        logger.debug("Bot does not have enough permissions to run setup in %s", ctx.guild)
        await ctx.reply(_("msg.setup.not_enough_permissions"), ephemeral=True)
        return

    wizard = SetupWizardView(ctx, show_reconfigure_warning=ctx.bot.staff_guild.is_setup())
    wizard.build()

    wizard.message = await ctx.reply(view=wizard)
    timed_out = await wizard.wait()

    if timed_out or wizard.canceled or not wizard.completed:
        return  # wizard already rendered its terminal card

    logger.info("%s is setting up Modmail in %s using %s", ctx.author, ctx.guild.name, wizard.setup_type)

    try:
        category_or_forum, log_channel, storage_channel = await ctx.bot.staff_guild.setup(
            wizard.setup_type, existing_channel_id=wizard.channel_id
        )
    except NoModmailCategoryError:
        logger.error("Selected channel %s no longer exists in %s", wizard.channel_id, ctx.guild)
        # Using wizard's _t() since it should be localized to wizard's locale
        wizard.show_error(wizard._t(_("view.setup.wizard.error_channel_gone")))  # pyright: ignore [reportPrivateUsage]
        return
    # TODO: Add another generic error handle for unknown errors

    wizard.show_success(category_or_forum, log_channel, storage_channel)
