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
ftl-cmd-status-param-status-name = status
ftl-cmd-status-param-status-description = The status to set.

## Subcommand: Utility.status.clear

ftl-cmd-status-clear-name = clear
ftl-cmd-status-clear-description = Clear the status of the Modmail bot.

## Command: Utility.profile

ftl-cmd-profile-name = profile
ftl-cmd-profile-description = View a list of all profiles.
ftl-cmd-profile-fallback-name = view

ftl-cmd-profile-no-bot = Bots cannot have profiles.

ftl-modal-profile-customize-title = Customize Profile
ftl-modal-profile-customize-colour = Colour
ftl-modal-profile-customize-colour-invalid = Invalid colour. Please use a colour hex code (e.g. #FF0000 for red).
ftl-modal-profile-customize-tag = Tag
# :param $name: the name of the user or role
ftl-modal-profile-customize-success = Successfully customized the profile of { $name }.
ftl-view-profile-button-customize-label = Customize
ftl-view-profile-select-level-placeholder = Change access level
ftl-view-profile-select-level-option-none = None
# :param $level: the name of the access level ('None' when unsetting)
# :param $name: the name of the user or role
ftl-view-profile-select-level-success = { $level ->
   *[default] Successfully set the permission access level of { $name } to { $level }.
    [None]    Successfully removed the permission access level of { $name }.
}

## Subcommand: Utility.profile.add

ftl-cmd-profile-add-name = add
ftl-cmd-profile-add-description = Create a profile for a user or role.
ftl-cmd-profile-add-param-user-or-role-name = user_or_role
ftl-cmd-profile-add-param-user-or-role-description = The user or role whose profile should be created.
# The following params can be used for the next 2 lines
# :param $name: the name of the user or role
ftl-cmd-profile-add-already-exists = { $name } already has a profile.
ftl-cmd-profile-add-success = Successfully created a profile for { $name }.

## Subcommand: Utility.profile.delete

ftl-cmd-profile-delete-name = delete
ftl-cmd-profile-delete-description = Delete a profile.
ftl-cmd-profile-delete-param-user-or-role-name = user_or_role
ftl-cmd-profile-delete-param-user-or-role-description = The user or role whose profile should be deleted.
ftl-cmd-profile-delete-both = Please only enter a user, role, or ID.
ftl-cmd-profile-delete-none = Please provide a user, role, or ID.
# :param $name: the name of the user or role or ID
ftl-cmd-profile-delete-success = Deleted the profile of { $name }.

## Subcommand: Utility.profile.edit

ftl-cmd-profile-edit-name = edit
ftl-cmd-profile-edit-description = Customize the profile.
ftl-cmd-profile-edit-param-user-or-role-name = user_or_role
ftl-cmd-profile-edit-param-user-or-role-description = The user or role whose profile should be customized.
# :param $name: the name of the user or role
ftl-cmd-profile-edit-message = Customizing the profile of { $name }.

## Subcommand: Utility.profile.allow

ftl-cmd-profile-allow-name = allow
ftl-cmd-profile-allow-description = Allow users of this profile to use a command.
ftl-cmd-profile-allow-param-user-or-role-name = user_or_role
ftl-cmd-profile-allow-param-user-or-role-description = The user or role to allow.
ftl-cmd-profile-allow-param-command-name-name = command-name
ftl-cmd-profile-allow-param-command-name-description = The command to allow. Can include wildcards using "+" for command groups.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-allow-success = Allowed { $name } to use { $command }.
# The following params can be used for the next 2 lines
# :param $command: the name of the command
ftl-cmd-profile-override-owner-command = Only bot owners can override this command.
ftl-cmd-profile-override-command-not-found = Command { $command } not found.

## Subcommand: Utility.profile.deny

ftl-cmd-profile-deny-name = deny
ftl-cmd-profile-deny-description = Deny users of this profile from using a command.
ftl-cmd-profile-deny-param-user-or-role-name = user_or_role
ftl-cmd-profile-deny-param-user-or-role-description = The user or role to deny.
ftl-cmd-profile-deny-param-command-name-name = command-name
ftl-cmd-profile-deny-param-command-name-description = The command to deny. Can include wildcards using "+" for command groups.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-deny-success = Denied { $name } from using { $command }.

## Subcommand: Utility.profile.unset

ftl-cmd-profile-unset-name = unset
ftl-cmd-profile-unset-description = Remove an allow/deny override from this profile on a command.
ftl-cmd-profile-unset-param-user-or-role-name = user_or_role
ftl-cmd-profile-unset-param-user-or-role-description = The user or role to remove the override from.
ftl-cmd-profile-unset-param-command-name-name = command-name
ftl-cmd-profile-unset-param-command-name-description = The command to remove the override from. Leave blank to remove all overrides.
# The following params can be used for the next 3 lines
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-unset-success = The override for { $name } on { $command } has been unset.
ftl-cmd-profile-unset-profile-not-found = { $name } does not have a profile.
ftl-cmd-profile-unset-override-not-found = No override exists on { $command } for { $name }.

## Command: Modmail.setup

ftl-cmd-setup-name = setup
ftl-cmd-setup-description = Setup the Modmail bot.
ftl-cmd-setup-not-enough-guild-permissions = I don't have enough permissions in this server.
# :param $guild_name: the name of the staff guild
ftl-cmd-setup-wrong-guild = You can only setup the Modmail bot in the staff server ({ $guild_name }).
ftl-cmd-setup-already-running = You can't use this command right now. Please try again later.
ftl-cmd-setup-guild-already-configured-prompt = This server is already configured. Do you want to reconfigure it?
ftl-cmd-setup-guild-already-configured-prompt-continue-anyway = Yes
ftl-cmd-setup-use-category-or-forum-prompt = Do you want to use a category or a forum for Modmail? (Category is recommended)
ftl-cmd-setup-use-category-or-forum-prompt-category = Category
ftl-cmd-setup-use-category-or-forum-prompt-forum = Forum
ftl-cmd-setup-use-new-category-prompt = Do you want me to create a new category for Modmail?
ftl-cmd-setup-use-new-category-prompt-new = Create
ftl-cmd-setup-use-new-category-prompt-existing = Use an existing category
ftl-cmd-setup-use-new-category-prompt-existing-category = Please enter the name or ID of the category you want to use for Modmail:
ftl-cmd-setup-use-new-category-prompt-existing-category-not-found = Category not found.
ftl-cmd-setup-use-new-category-prompt-existing-category-no-permissions = I don't have enough permissions in this category.
ftl-cmd-setup-use-new-forum-prompt = Do you want me to create a new forum for Modmail?
ftl-cmd-setup-use-new-forum-prompt-new = Create
ftl-cmd-setup-use-new-forum-prompt-existing = Use an existing forum
ftl-cmd-setup-use-new-forum-prompt-existing-forum = Please enter the name or ID of the forum you want to use for Modmail:
ftl-cmd-setup-use-new-forum-prompt-existing-forum-not-found = Forum not found.
ftl-cmd-setup-use-new-forum-prompt-existing-forum-no-permissions = I don't have enough permissions in this forum.
ftl-cmd-setup-category-or-forum-name = Modmail
ftl-cmd-setup-category-or-forum-create-reason = Category/Forum for Modmail.
ftl-cmd-setup-category-or-forum-permissions-reason = Category/Forum permissions for Modmail.
ftl-cmd-setup-forum-thread-unpin-reason = Unpin existing thread in Modmail forum.
ftl-cmd-setup-log-channel-name = ticket-logs
ftl-cmd-setup-log-channel-topic = Modmail logs
ftl-cmd-setup-log-channel-create-reason = Log channel for Modmail.
ftl-cmd-setup-storage-channel-name = modmail-storage
ftl-cmd-setup-storage-channel-topic = Modmail storage (reserved for Modmail use only)
ftl-cmd-setup-storage-channel-create-reason = Storage channel for Modmail.
# TODO: Add more information (e.g. quick tutorial) + better format setup complete
# :param $category: the name of the Modmail category
# :param $log_channel: the name of the Modmail log channel
# :param $storage_channel: the name of the Modmail storage channel
ftl-cmd-setup-category-complete = Successfully setup Modmail. Your Modmail category is { $category }. I have also created two channels: { $log_channel } for Modmail logs and { $storage_channel } for storing some of my internal data. Feel free to rename and move these channels, but please do not delete them! Please check the permissions of the category and channels to make sure they are correct.
# :param forum: the name of the Modmail forum
# :param $log_channel: the name of the Modmail log thread
# :param $storage_channel: the name of the Modmail storage thread
ftl-cmd-setup-forum-complete = Successfully setup Modmail. Your Modmail forum is { $forum }. I have also created two threads: { $log_channel } for Modmail logs and { $storage_channel } for storing some of my internal data. Feel free to rename these threads, but please do not delete them! Please check the permissions of the forum to make sure they are correct.

## Command: Modmail.reply

ftl-cmd-reply-name = reply
ftl-cmd-reply-description = Reply to a Modmail ticket.
ftl-cmd-reply-param-attachment-name = attachment
ftl-cmd-reply-param-attachment-description = The attachment to send. Can be a file or an image.
ftl-cmd-reply-param-message-name = message
ftl-cmd-reply-param-message-description = The message to send.
ftl-cmd-reply-message-empty = Please enter a message to send.
ftl-cmd-reply-message-sending = Sending the message...
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-cmd-reply-message-failed-recipients = Failed to send this message to the following recipients: { $recipients }.
                                          They may have disabled DMs, blocked me, or does not share any servers with me.
ftl-cmd-reply-message-failed = Failed to send the reply, please check my logs for more information.

## Command: Modmail.close

ftl-cmd-close-name = close
ftl-cmd-close-description = Close a Modmail ticket.
ftl-cmd-close-param-attachment-name = attachment
ftl-cmd-close-param-attachment-description = The attachment to send. Can be a file or an image.
ftl-cmd-close-param-message-name = message
ftl-cmd-close-param-message-description = The message to send.
ftl-cmd-close-message-sending = Closing the ticket...
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-cmd-close-message-failed-recipients = Failed to send the close message to the following recipients: { $recipients }.
                                          They may have disabled DMs, blocked me, or does not share any servers with me.
ftl-cmd-close-message-failed = Failed to send the close message, please check my logs for more information.

## Command: Modmail.sclose

ftl-cmd-sclose-name = sclose
ftl-cmd-sclose-description = Silently close a Modmail ticket.
ftl-cmd-sclose-param-attachment-name = attachment
ftl-cmd-sclose-param-attachment-description = The attachment to store with the close message. Can be a file or an image.
ftl-cmd-sclose-param-message-name = message
ftl-cmd-sclose-param-message-description = The message to store as the close message.
ftl-cmd-sclose-message-sending = Closing the ticket...

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
ftl-msg-command-invoke-error = An unknown error occurred while processing your command, try again later.
                               If the problem persists, please check your logs and report the error to the Modmail team.

ftl-msg-prompt-timeout = Timed out. Please rerun the command to try again.

ftl-msg-dm-received-not-configured = Modmail has not been configured. Please contact the server owner to configure Modmail for the server.
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-msg-dm-received-failed-recipients = The following recipients did not receive this message: { $recipients }.
                                        They may have disabled DMs, blocked me, or does not share any servers with me.

# :param $users: a comma-separated list of usernames
ftl-msg-new-ticket-reason = New Modmail ticket for: { $users }
# :param $users: a space-separated list of user mentions
ftl-msg-new-ticket-default-thread-opening-message = { $users } started a new Modmail ticket.
# :param $created: the date the account was created
ftl-msg-new-ticket-initial-embed-description = Account created { $created }.
# :param $user_id: the user ID of the user (string)
ftl-msg-new-ticket-initial-embed-footer = User ID: { $user_id }
# :param $joined: the date the user joined the server
# :param $roles: a comma-separated list of roles
# :param $has_role: whether the user has a role in the server (true) or not (false)
ftl-msg-new-ticket-initial-embed-guild-field-value = Joined { $joined }.
                                                     Roles: { $has_role ->
    *[true]  { $roles }
     [false] None
}
ftl-msg-new-ticket-initial-embed-guild-field-value-no-join-date = [Unknown]
ftl-msg-new-ticket-initial-embed-past-tickets-field-name = Past Tickets
# :param $count: the number of past tickets
ftl-msg-new-ticket-initial-embed-past-tickets-field-value = { $count ->
     [one] 1 past ticket
    *[other] { $count } past tickets
}
ftl-msg-create-ticket-failed = Something went wrong while creating this Modmail ticket. Please check my logs for more information.

# :param $user: the name of the closer
ftl-msg-ticket-closed-reason = Modmail ticket closed by { $user }.
ftl-msg-ticket-closed-reason-unknown-closer = Modmail ticket closed by unknown user.

# :param $message_id: the message ID of the message (string)
ftl-msg-ticket-channel-embed-footer = Message ID: { $message_id }

ftl-msg-log-embed-open-footer = Ticket Open
# :param $user: the username of the closer
ftl-msg-log-embed-closed-footer = Ticket Closed by @{ $user }
ftl-msg-log-embed-closed-footer-unknown-closer = Ticket Closed
ftl-msg-log-embed-no-content-description = *No content*

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
