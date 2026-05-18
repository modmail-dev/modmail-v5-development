# This file contains localization strings for the English (en) locale.
# Translations here will be used across the entire Modmail project.

### ========================
###         General
### ========================

ftl-access-level-everyone = Everyone
ftl-access-level-staff = Staff
ftl-access-level-manager = Manager
ftl-access-level-admin = Admin
ftl-access-level-owner = Owner

ftl-view-prompt-cancel-label = Cancel

### ========================
###         Commands
### ========================

## Command: Utility.help

ftl-cmd-help-name = help
ftl-cmd-help-description = Browse all available bot commands interactively.
ftl-cmd-help-param-command-name = command
ftl-cmd-help-param-command-description = Command or subcommand to get help for directly.

## Help view — overview

ftl-view-help-title = ### Modmail Help
ftl-view-help-subtitle = Select a category below, or use the help command with a command name for details.
ftl-view-help-select-category-placeholder = Choose a category…

## Category names and descriptions (referenced from cog setup)

ftl-view-help-category-modmail-name = Modmail
ftl-view-help-category-modmail-description = Ticket management and replies
ftl-view-help-category-utility-name = Utility
ftl-view-help-category-utility-description = Bot configuration and profiles
ftl-view-help-category-jishaku-name = Jishaku
ftl-view-help-category-jishaku-description = External developer & debug tools.
ftl-view-help-category-other-name = Other

# :param $categories: number of categories, :param $commands: number of commands
ftl-view-help-overview-stats = { $categories } { $categories ->
    [one]   category
   *[other] categories
} · { $commands } { $commands ->
    [one]   command
   *[other] commands
} available

## Help view — category page

# :param $page: current page number, :param $total: total number of pages
ftl-view-help-page-indicator = Page { $page } of { $total }
ftl-view-help-select-command-placeholder = Choose a command for details…
ftl-view-help-btn-back = ← Back
ftl-view-help-btn-prev = ‹ Prev
ftl-view-help-btn-next = Next ›
ftl-view-help-prefix-only = prefix only
ftl-view-help-category-empty-title = ### { $category }
ftl-view-help-category-empty-body =
    There are no commands in this category yet.
    Try another category or check back later.
ftl-view-help-no-access = -# You don't have access to any commands.

## Help view — command detail page

# :param $level: access level label (e.g. Staff, Admin)
ftl-view-help-detail-access = **Access:** { $level }
ftl-view-help-detail-param-header = **Parameters:**
ftl-view-help-detail-param-optional-label = optional
ftl-view-help-detail-prefix-note = This command is only available via the bot prefix.
# :param $command: the command name the user searched for
ftl-view-help-not-found = Command `{ $command }` was not found.

## Command: Utility.about

ftl-cmd-about-name = about
ftl-cmd-about-fallback-name = info
ftl-cmd-about-description = Shows information about the Modmail bot.

## Subcommand: Utility.about.version

ftl-cmd-about-version-name = version
ftl-cmd-about-version-description = Shows the version of the Modmail bot.
# :param $version: the version of the bot
ftl-cmd-about-version-message = Modmail v{ $version }

## Command: Utility.status

ftl-cmd-status-name = status
ftl-cmd-status-fallback-name = set
ftl-cmd-status-description = Set the status of the Modmail bot.
ftl-cmd-status-help =
    Set the bot status or activity, or show the current values when no status is provided.
    Status values: online, idle, dnd, offline.
    Activity formats: playing <name>, watching <name>, listening to <name>, competing in <name>.
    Streaming format: streaming <name> <twitch-url>.
    Any other text becomes a custom activity. Use the clear subcommand to reset.
ftl-cmd-status-param-status-name = status
ftl-cmd-status-param-status-description = The status to set.

## Subcommand: Utility.status.clear

ftl-cmd-status-clear-name = clear
ftl-cmd-status-clear-description = Clear the status of the Modmail bot.
ftl-cmd-status-clear-help =
    Clear the current status and activity so the bot shows no presence text.

## Command: Utility.profile

ftl-cmd-profile-name = profile
ftl-cmd-profile-description = View and manage permission profiles for users and roles.
ftl-cmd-profile-help =
    List all configured permission profiles, ordered by access level.
    Use edit to create or update a profile, or delete to remove one.
ftl-cmd-profile-fallback-name = list

## Modals: profile appearance and override

ftl-modal-profile-customize-title = Customize Appearance
ftl-modal-profile-customize-color = Color
ftl-modal-profile-customize-color-placeholder = #000000
ftl-modal-profile-customize-color-invalid = Invalid color. Please use a color hex code (e.g. #FF0000 for red).
ftl-modal-profile-customize-tag = Tag
# :param $profile: the mention of the user or role
ftl-modal-profile-customize-success = Updated the appearance of { $profile }.

ftl-modal-profile-remove-override-title = Remove Override
ftl-modal-profile-remove-override-name-label = Override Name
ftl-modal-profile-remove-override-name-placeholder = e.g. reply, profile+
# :param $command: the override name entered
ftl-modal-profile-remove-override-not-found = No override named `{ $command }` exists on this profile.
# :param $command: the override name removed
ftl-modal-profile-remove-override-success = Removed the override for `{ $command }`.

ftl-modal-profile-add-override-allow-title = Allow Command
ftl-modal-profile-add-override-deny-title = Deny Command
ftl-modal-profile-add-override-command-label = Command Name
ftl-modal-profile-add-override-command-placeholder = e.g. reply, profile+
# :param $command: the command name
ftl-modal-profile-add-override-already-allow = `{ $command }` is already allowed on this profile.
# :param $command: the command name
ftl-modal-profile-add-override-already-deny = `{ $command }` is already denied on this profile.

## Profile editor card (ProfileEditorView)

# :param $profile: the mention of the user or role
# :param $type: "User" or "Role"
ftl-view-profile-editor-header =
    ### Profile: { $profile }
    { "**" }Type{ "**" }: { $type }
ftl-view-profile-editor-type-user = User
ftl-view-profile-editor-type-role = Role
# :param $level: the access level label or "None"
# :param $tag: the tag value or "Not set"
# :param $color: the hex color string or "Not set"
ftl-view-profile-editor-summary = **Access Level**: { $level }  •  **Tag**: { $tag }  •  **Color**: { $color }
ftl-view-profile-editor-level-none = None
ftl-view-profile-editor-not-set = Not set
ftl-view-profile-editor-select-level-placeholder = Change access level…
ftl-view-profile-editor-btn-delete = Delete
ftl-view-profile-editor-btn-customize = Customize
ftl-view-profile-editor-btn-add-allow = + Allow
ftl-view-profile-editor-btn-add-deny = + Deny
# :param $count: number of overrides
ftl-view-profile-editor-overrides-header = { $count ->
    [0]    **Permission Overrides** — None
   *[other] **Permission Overrides** ({ $count })
}
ftl-view-profile-editor-select-remove-placeholder = Remove override…
ftl-view-profile-editor-btn-remove-override = Remove Override
ftl-view-profile-editor-override-value-allow = Allow
ftl-view-profile-editor-override-value-deny = Deny
# :param $command: the command name
ftl-view-profile-editor-override-line-allow = ✅ `{ $command }`
# :param $command: the command name
ftl-view-profile-editor-override-line-deny = ❌ `{ $command }`
# :param $command: the command name
ftl-view-profile-editor-override-allow-success = ✅ Allowed `{ $command }` on this profile.
# :param $command: the command name
ftl-view-profile-editor-override-deny-success = ❌ Denied `{ $command }` on this profile.
ftl-view-profile-editor-delete-confirm = Are you sure you want to delete this profile? This cannot be undone.
ftl-view-profile-editor-delete-btn-confirm = Delete Profile
# :param $profile: the mention of the user or role
ftl-view-profile-editor-deleted-content =
    ### Profile deleted
    The profile of { $profile } has been removed.
ftl-view-profile-editor-update-failed = Something went wrong. Please try again.
ftl-view-profile-editor-access-sync-failed = Profile updated, but Discord channel permissions could not be synced.

## Subcommand: Utility.profile.list (fallback)

# :param $count: the number of profiles
ftl-cmd-profile-list-title = ### Profiles ({ $count })
ftl-cmd-profile-list-empty = No profiles have been configured yet.
ftl-cmd-profile-list-no-level = No access level
# :param $count: number of overrides
ftl-cmd-profile-list-overrides = { $count ->
    [0]     no overrides
    [one]   { $count } override
   *[other] { $count } overrides
}
# :param $mention: the profile mention
# :param $level: the access level label
# :param $overrides: the formatted override count string
ftl-cmd-profile-list-row = - **{ $mention }** — { $level } · { $overrides }
ftl-cmd-profile-list-tip = -# Use `/{ ftl-cmd-profile-name } { ftl-cmd-profile-edit-name }` to add or update a profile.

## Subcommand: Utility.profile.edit

ftl-cmd-profile-edit-name = edit
ftl-cmd-profile-edit-description = Edit a profile's access level, appearance, and command overrides.
ftl-cmd-profile-edit-help =
    Open a friendly editor for a user or role profile.
    Set the access level, tag, color, and command overrides from the card.
ftl-cmd-profile-edit-param-target-name = user_or_role
ftl-cmd-profile-edit-param-target-description = The user or role whose profile to edit.

## Subcommand: Utility.profile.delete

ftl-cmd-profile-delete-name = delete
ftl-cmd-profile-delete-description = Delete a profile, removing all access settings and command overrides.
ftl-cmd-profile-delete-help =
    Delete a profile and remove its access settings and command overrides.
    Provide a user or role, or use a raw ID if the entry no longer exists.
ftl-cmd-profile-delete-param-target-name = user_or_role
ftl-cmd-profile-delete-param-target-description = The user or role whose profile should be deleted.
ftl-cmd-profile-delete-param-id-name = id
ftl-cmd-profile-delete-param-id-description = Raw Discord ID to use when the user or role no longer exists in the server.
ftl-cmd-profile-delete-both = Provide either a user or role, or an ID — not both.
ftl-cmd-profile-delete-none = Provide a user, role, or ID.
ftl-cmd-profile-delete-not-found = No profile found for that user, role, or ID.
# :param $profile: the mention of the user or role or ID
ftl-cmd-profile-delete-success = Deleted the profile of { $profile }.
ftl-cmd-profile-delete-failed = Failed to delete the profile. Please try again.

## Shared override error messages

# :param $command: the name of the command
ftl-cmd-profile-override-owner-command = Only bot owners can override this command.
ftl-cmd-profile-override-command-not-found = Command `{ $command }` not found.
ftl-cmd-profile-override-jishaku-command = Jishaku manages its own permissions and does not support Modmail permission overrides.

## Command: Modmail.setup

ftl-cmd-setup-name = setup
ftl-cmd-setup-description = Set up the Modmail bot.
ftl-cmd-setup-help =
    Start the guided setup in the staff server.
    Pick a category or forum layout and let the bot create or configure channels.
    Only one setup can run at a time.
ftl-cmd-setup-not-enough-guild-permissions = I don't have enough permissions in this server.
# :param $guild_name: the name of the staff guild
ftl-cmd-setup-wrong-guild = You can only setup the Modmail bot in the staff server ({ $guild_name }).
ftl-cmd-setup-already-running = You can't use this command right now. Please try again later.
ftl-msg-setup-category-or-forum-name = Modmail
ftl-msg-setup-category-or-forum-create-reason = Category/Forum for Modmail.
ftl-msg-setup-category-or-forum-permissions-reason = Category/Forum permissions for Modmail.
ftl-msg-setup-forum-thread-unpin-reason = Unpin existing thread in Modmail forum.
ftl-msg-setup-log-channel-name = ticket-logs
ftl-msg-setup-log-channel-topic = Modmail logs
ftl-msg-setup-log-channel-create-reason = Log channel for Modmail.
ftl-msg-setup-storage-channel-name = modmail-storage
ftl-msg-setup-storage-channel-topic = Modmail storage (reserved for Modmail use only)
ftl-msg-setup-storage-channel-create-reason = Storage channel for Modmail.

## Setup wizard

ftl-wizard-setup-reconfigure-content =
    ### Modmail is already configured
    Continuing will replace the current setup.
    Any channels Modmail previously created will remain, but won't be used.
ftl-wizard-setup-reconfigure-btn-continue = Continue

ftl-wizard-setup-type-content =
    ### Step 1 of 3 — Choose a layout
    Choose how Modmail tickets will be organized.
    - **Category** — each ticket gets a dedicated text channel inside a category.
    - **Forum** — each ticket becomes a post inside a forum channel.
ftl-wizard-setup-type-btn-category = Category
ftl-wizard-setup-type-btn-forum = Forum

ftl-wizard-setup-new-or-existing-content-category =
    ### Step 2 of 3 — New or existing?
    Should I create a new **Modmail** category, or adopt one that already exists in this server?
ftl-wizard-setup-new-or-existing-content-forum =
    ### Step 2 of 3 — New or existing?
    Should I create a new **Modmail** forum channel, or adopt one that already exists in this server?
ftl-wizard-setup-new-or-existing-btn-create = Create new
ftl-wizard-setup-new-or-existing-btn-existing-category = Use existing category
ftl-wizard-setup-new-or-existing-btn-existing-forum = Use existing forum

ftl-wizard-setup-select-existing-content-category =
    ### Step 3 of 3 — Select a category
    Use the dropdown to pick the category Modmail should use.
    The bot must already have access to it.
ftl-wizard-setup-select-existing-content-forum =
    ### Step 3 of 3 — Select a forum
    Use the dropdown to pick the forum Modmail should use.
    The bot must already have access to it.
ftl-wizard-setup-select-existing-placeholder-category = Select a category…
ftl-wizard-setup-select-existing-placeholder-forum = Select a forum…
ftl-wizard-setup-select-existing-wrong-type-category = Please select a category, not a forum.
ftl-wizard-setup-select-existing-wrong-type-forum = Please select a forum, not a category.
ftl-wizard-setup-select-existing-no-perms = I don't have enough permissions in the selected channel. Please select a different one.

ftl-wizard-setup-confirm-content-new-category =
    ### Confirm setup
    A new **Modmail** category will be created with a log channel and a storage channel inside it.
    Permissions will be configured automatically.
ftl-wizard-setup-confirm-content-new-forum =
    ### Confirm setup
    A new **Modmail** forum will be created for tickets, with a log thread inside it and a separate storage channel.
    Permissions will be configured automatically.
# :param $name: the name of the existing category
ftl-wizard-setup-confirm-content-existing-category =
    ### Confirm setup
    The **{ $name }** category will be used.
    A log channel and a storage channel will be added inside it.
# :param $name: the name of the existing forum
ftl-wizard-setup-confirm-content-existing-forum =
    ### Confirm setup
    The **{ $name }** forum will be used for tickets.
    A log thread will be added inside it and a separate storage channel will be created.
ftl-wizard-setup-confirm-btn = Confirm & Set Up
ftl-wizard-setup-btn-back = Back

ftl-wizard-setup-working-content =
    ### Setting up Modmail…
    This should only take a moment. Please wait.
ftl-wizard-setup-canceled-content =
    ### Setup canceled
    No changes were made. Run the command again whenever you're ready.
ftl-wizard-setup-timeout-content =
    ### Setup timed out
    The wizard closed due to inactivity. No changes were made. Run the command again to restart.
ftl-wizard-setup-error-channel-gone = The selected channel no longer exists. Run the command again and choose a different one.

# :param $category: the name of the Modmail category
# :param $log_channel: mention of the log channel
# :param $storage_channel: mention of the storage channel
ftl-wizard-setup-success-content-category =
    ## Setup complete
    Modmail is now configured and ready to use.
    { "*" }*Category:** { $category }
    { "*" }*Logs:** { $log_channel }
    { "*" }*Storage:** { $storage_channel }
    Feel free to rename or move these channels, but please don't delete them.
# :param $forum: the name of the Modmail forum
# :param $log_channel: mention of the log thread
# :param $storage_channel: mention of the storage channel
ftl-wizard-setup-success-content-forum =
    ## Setup complete
    Modmail is now configured and ready to use.
    { "*" }*Forum:** { $forum }
    { "*" }*Logs:** { $log_channel }
    { "*" }*Storage:** { $storage_channel }
    Feel free to rename or move these channels, but please don't delete them.

## Command: Modmail.reply

ftl-cmd-reply-name = reply
ftl-cmd-reply-description = Reply to a Modmail ticket.
ftl-cmd-reply-help =
    Reply to the user from within a Modmail ticket channel or thread.
    Provide a message, an attachment, or both. At least one is required.
ftl-cmd-reply-param-attachment-name = attachment
ftl-cmd-reply-param-attachment-description = The attachment to send. Can be a file or an image.
ftl-cmd-reply-param-message-name = message
ftl-cmd-reply-param-message-description = The message to send.
ftl-cmd-reply-message-empty = Please enter a message to send.
ftl-cmd-reply-message-sending = Sending the message...
ftl-cmd-reply-message-failed = Failed to send the reply, please check my logs for more information.

## Command: Modmail.close

ftl-cmd-close-name = close
ftl-cmd-close-description = Close a Modmail ticket.
ftl-cmd-close-help =
    Close the current ticket and send a closing message to the user.
    Provide a message, an attachment, or both. If you provide nothing, a default message is used.
ftl-cmd-close-param-attachment-name = attachment
ftl-cmd-close-param-attachment-description = The attachment to send. Can be a file or an image.
ftl-cmd-close-param-message-name = message
ftl-cmd-close-param-message-description = The message to send.
ftl-cmd-close-message-sending = Closing the ticket...
ftl-cmd-close-message-failed = Failed to send the close message, please check my logs for more information.
ftl-cmd-close-failed = Failed to close the ticket, please check my logs for more information.
# :param $closer: staff member ID
ftl-cmd-close-default-message = Thank you for reaching out. Your ticket has been closed by <@{ $closer }>. If you have any further questions, feel free to send us a message at any time.

## Command: Modmail.sclose

ftl-cmd-sclose-name = sclose
ftl-cmd-sclose-description = Silently close a Modmail ticket.
ftl-cmd-sclose-help =
    Close the current ticket without sending a DM to the user.
    You may include a message or attachment to save in the ticket log.
ftl-cmd-sclose-param-attachment-name = attachment
ftl-cmd-sclose-param-attachment-description = The attachment to store with the close message. Can be a file or an image.
ftl-cmd-sclose-param-message-name = message
ftl-cmd-sclose-param-message-description = The message to store as the close message.
ftl-cmd-sclose-message-sending = Closing the ticket...
ftl-cmd-sclose-failed = Failed to close the ticket, please check my logs for more information.
# :param $closer: staff member ID
ftl-cmd-sclose-default-message = Ticket closed by <@{ $closer }>.

### ========================
###         Messages
### ========================

## Status messages

# The following params can be used for the next 2 lines
# :param $status: the status name (formatted in models section)
ftl-msg-status-current-status = Current status: { $status }
ftl-msg-status-set-status = Set status to { $status }.
# The following params can be used for the next 2 lines
# :param $activity: the activity name (formatted in models section)
ftl-msg-status-current-activity = Current activity: { $activity }
ftl-msg-status-set-activity = Set activity to { $activity }.
ftl-msg-status-no-status = No status is currently set.
ftl-msg-status-clear-status = Cleared status.

# :param $user_or_role: the name of the user or role
ftl-msg-grant-access-reason = Granting access to { $user_or_role } to Modmail category and channels.
ftl-msg-revoke-access-reason = Revoking access to { $user_or_role } to Modmail category and channels.

ftl-msg-permission-denied = You do not have permission to use this command.
ftl-msg-bad-permissions = I'm missing the following permissions here: { $permissions }.
ftl-msg-command-invoke-error = An unknown error occurred while processing your command, try again later.
                               If the problem persists, please check your logs and report the error to the Modmail team.

ftl-msg-prompt-timeout = Timed out. Please rerun the command to try again.

ftl-msg-dm-received-not-configured = Modmail has not been configured. Please contact the server owner to configure Modmail for the server.

# :param $users: a comma-separated list of usernames
ftl-msg-new-ticket-reason = New Modmail ticket for: { $users }
# :param $users: a space-separated list of user mentions
ftl-msg-new-ticket-default-thread-opening-message = { $users } started a new Modmail ticket.
ftl-msg-create-ticket-failed = Something went wrong while creating this Modmail ticket. Please check my logs for more information.

# :param $user: the name of the closer
ftl-msg-ticket-closed-reason = Modmail ticket closed by { $user }.
ftl-msg-ticket-closed-reason-unknown-closer = Modmail ticket closed by unknown user.

## Ticket view — log channel

# Shared params for `ftl-msg-ticket-log-{title,body,footer}`:
# :param $users: recipient mentions string
# :param $key: 12-char ticket key
# :param $log_url: log viewer URL
# :param $created_ts: ticket-open unix timestamp (string), :param $created_by: creator ID
# :param $closed_ts: ticket-close unix timestamp (string, "0" if open)
# :param $closed_by: closer ID
# :param $status: lifecycle marker
ftl-msg-ticket-log-title = ### **{ $users }**
ftl-msg-ticket-log-body =
    { $status ->
        [open] Ticket opened <t:{ $created_ts }:R> in <#{ $channel_id }>
       *[other] Ticket opened <t:{ $created_ts }:R>
    }
    by <@{ $created_by }> with key **`{ $key }`**

    Click [here]({ $log_url }) for the full log
ftl-msg-ticket-log-footer =
    { $status ->
        [open] 📧 This ticket is currently open
        [closed_by] 🔒 Closed by <@{ $closed_by }> on <t:{ $closed_ts }:f>
       *[closed] 🔒 Closed on <t:{ $closed_ts }:f>
    }

## Ticket view — staff channel

# Shared params for `ftl-msg-ticket-staff-{title,footer,body}-*`:
# :param $author_id: author's Discord ID (string)
# :param $author_name: author's display name (markdown-escaped)
# :param $message_id: Discord message ID (string)
# :param $created_ts: message creation unix timestamp (string)
# :param $key: 12-char ticket key (string)
# :param $log_url: log viewer URL (string)

ftl-msg-ticket-staff-title-dm = <@{ $author_id }>
ftl-msg-ticket-staff-title-reply = <@{ $author_id }>
ftl-msg-ticket-staff-title-internal =
    <@{ $author_id }>
    -# Internal note
ftl-msg-ticket-staff-title-close = ### This ticket is now closed
ftl-msg-ticket-staff-title-sclose = ### This ticket is now closed

ftl-msg-ticket-staff-footer-dm = -# 📨 DM  ·  ID: `{ $message_id }`  ·  <t:{ $created_ts }:f>
ftl-msg-ticket-staff-footer-reply = -# 💬 Reply  ·  ID: `{ $message_id }`  ·  <t:{ $created_ts }:f>
ftl-msg-ticket-staff-footer-internal = -# 🔒 Staff only  ·  ID: `{ $message_id }`  ·  <t:{ $created_ts }:f>
ftl-msg-ticket-staff-footer-close = -# 🚫 Closed by <@{ $author_id }>  ·  <t:{ $created_ts }:R>  ·  [`{ $key }`]({ $log_url })
ftl-msg-ticket-staff-footer-sclose = -# 🚫 Closed silently by <@{ $author_id }>  ·  <t:{ $created_ts }:R>  ·  [`{ $key }`]({ $log_url })

# :param $count: number of unreachable recipients (integer), :param $recipients: comma-separated user mentions
ftl-msg-ticket-staff-unreachable = -# ⚠️ { $recipients } didn't receive this message. They may have disabled DMs or blocked the bot.

## Ticket view — user DM

# Shared params for `ftl-msg-ticket-user-{title,footer}-*`:
# :param $author_id: author's Discord ID (string)
# :param $author_name: author's display name (markdown-escaped)
# :param $message_id: Discord message ID (string)
# :param $created_ts: message creation unix timestamp (string)
# :param $key: 12-char ticket key (string)
# :param $log_url: log viewer URL (string)

ftl-msg-ticket-user-title-dm = **{ $author_name }**
ftl-msg-ticket-user-title-reply = **{ $author_name }**
ftl-msg-ticket-user-title-close = **Your ticket has been closed**

ftl-msg-ticket-user-footer-dm = -# This message is from another user  ·  <t:{ $created_ts }:f>
ftl-msg-ticket-user-footer-reply = -# Support Staff  ·  <t:{ $created_ts }:f>
ftl-msg-ticket-user-footer-close = -# You can DM us again to open a new ticket.
# :param $user_id: recipient Discord ID (string), :param $user_name: recipient display name (markdown-escaped)
ftl-msg-dm-welcome-title = ### We've received your message
ftl-msg-dm-welcome-body = A support ticket has been opened and our team will assist you as soon as possible. A `✅` on your message means it has been forwarded successfully.
ftl-msg-dm-welcome-footer = -# You may reply to this message at any time.

## Ticket view — recipient info card

# Shared params for `ftl-msg-ticket-info-{title,body,footer}`:
# :param $user_name: recipient display name (markdown-escaped)
# :param $user_id: recipient Discord ID (string)
# :param $account_created_ts: account creation unix timestamp (string)
# :param $log_url: log viewer URL, :param $key: ticket / logviewer key
# :param $created_ts: ticket-open unix timestamp (string)
# :param $past_ticket_count: number of past closed tickets (integer)
ftl-msg-ticket-info-title = <@{ $user_id }>
ftl-msg-ticket-info-body =
    -# Account created <t:{ $account_created_ts }:R> · User ID `{ $user_id }`
ftl-msg-ticket-info-footer =
    -# Ticket [`{ $key }`]({ $log_url }) opened <t:{ $created_ts }:R>
    -# { $past_ticket_count ->
        [0] No past tickets
        [one] 1 past ticket
       *[other] { $past_ticket_count } past tickets
    }

# Per-guild membership entry.
# :param $guild_name: guild display name (markdown-escaped), :param $guild_id: guild ID (string)
# :param $joined_ts: member-join unix timestamp (string)
# :param $roles: comma-separated role mentions ("none" if member has no non-default roles)
ftl-msg-ticket-info-guild-name = { "**" }{ $guild_name }{ "**" }
ftl-msg-ticket-info-guild-entry =
    { $joined_ts ->
        [0] -# Joined: unknown
       *[other] -# Joined <t:{ $joined_ts }:f>
    }
    { $roles ->
        [none] -# No roles
       *[other] -# Roles: { $roles }
    }
ftl-msg-ticket-info-no-shared-servers = No shared servers found

### ========================
###    Converter errors
### ========================

## Profile converter errors

# :param $argument: the raw argument string supplied by the user
ftl-error-converter-profile-not-found = Could not find a user or role matching "{ $argument }".
ftl-error-converter-profile-is-bot = Bots cannot have profiles.

### ========================
###          Models
### ========================

## Activity model

# Official Discord prefixes for each activity type, custom is blank so not defined here
# Currently does not support suffixes if the language has them
ftl-model-activity-playing-name = playing
ftl-model-activity-streaming-name = streaming
ftl-model-activity-listening-name = listening to
ftl-model-activity-watching-name = watching
ftl-model-activity-competing-name = competing in

# $activity_type is the type of activity (playing, streaming, etc.)
# $activity_name is the name of the activity
# $activity_url is the url of the activity (only for streaming)
ftl-model-activity-text = { $activity_type ->
    [playing]   Playing { $activity_name }
    [streaming] Streaming { $activity_name } (<{ $activity_url }>)
    [listening] Listening to { $activity_name }
    [watching]  Watching { $activity_name }
    [competing] Competing in { $activity_name }
   *[custom]    { $activity_name }
}

## Status model

# Official Discord names for each status type
ftl-model-status-online-name = online
ftl-model-status-idle-name = idle
ftl-model-status-dnd-name = dnd
ftl-model-status-dnd-full-name = do not disturb
ftl-model-status-offline-name = offline
ftl-model-status-invisible-name = invisible

# $status is the status type (online, idle, dnd, offline)
ftl-model-status-text = { $status ->
   *[online]  Online
    [idle]    Idle
    [dnd]     Do not disturb (dnd)
    [offline] Offline
}

### ========================
###        Internal
###   (Do Not Translate)
### ========================

# Placeholder for when an option shouldn't be used, but still got used regardless
ftl-error = !Error!

# Placeholder for an empty string
ftl-blank = { "" }
