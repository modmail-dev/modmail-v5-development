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

ftl-msg-permission-denied = You do not have permission to use this command.
ftl-msg-command-invoke-error = An unknown error occurred while processing your command, try again later.
                               If the problem persists, please check your logs and report the error to the Modmail team.

ftl-view-prompt-cancel-label = Cancel
ftl-msg-prompt-timeout = Timed out. Please rerun the command to try again.

ftl-dm-received-not-configured = Modmail has not been configured. Please contact the server owner to configure Modmail for the server.
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-dm-received-failed-recipients = The following recipients did not receive this message: { $recipients }.
                                    They may have disabled DMs, blocked me, or does not share any servers with me.

# :param $users: a comma-separated list of usernames
ftl-msg-new-thread-reason = New Modmail thread for: { $users }
# :param $created: the date the account was created
ftl-msg-new-thread-initial-embed-description = Account created { $created }.
# :param $user_id: the user ID of the user (string)
ftl-msg-new-thread-initial-embed-footer = User ID: { $user_id }
# :param $joined: the date the user joined the server
# :param $roles: a comma-separated list of roles
# :param $has_role: whether the user has a role in the server (true) or not (false)
ftl-msg-new-thread-initial-embed-guild-field-value = Joined { $joined }.
                                                     Roles: { $has_role ->
    *[true]  { $roles }
     [false] None
}
ftl-msg-new-thread-initial-embed-past-threads-field-name = Past Threads
# :param $count: the number of past threads
ftl-msg-new-thread-initial-embed-past-threads-field-value = { $count ->
     [one] 1 past thread
    *[other] { $count } past threads
}
ftl-msg-create-thread-failed = Something went wrong while creating this Modmail thread. Please check my logs for more information.

# :param $message_id: the message ID of the message (string)
ftl-msg-thread-channel-embed-footer = Message ID: { $message_id }

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
# :param $guild_name: the name of the staff guild
ftl-cmd-setup-wrong-guild = You can only setup the Modmail bot in the staff server ({ $guild_name }).
ftl-cmd-setup-already-running = You can't use this command right now. Please try again later.
ftl-cmd-setup-not-enough-guild-permissions = I don't have enough permissions to create the Modmail category and channels.
ftl-cmd-setup-guild-already-configured-prompt = This server is already configured. Do you want to reconfigure it?
ftl-cmd-setup-guild-already-configured-prompt-continue-anyway = Yes
ftl-cmd-setup-use-new-category-prompt = Do you want me to create a new category for Modmail?
ftl-cmd-setup-use-new-category-prompt-new = Yes
ftl-cmd-setup-use-new-category-prompt-existing = Use an existing category
ftl-cmd-setup-use-new-category-prompt-existing-category = Please enter the ID or name of the category you want to use for Modmail:
ftl-cmd-setup-use-new-category-prompt-existing-category-not-found = Category not found.
ftl-cmd-setup-use-new-category-prompt-existing-category-no-permissions = I don't have enough permissions in this category.
ftl-cmd-setup-category-name = Modmail
ftl-cmd-setup-category-create-reason = Category for Modmail.
ftl-cmd-setup-category-permissions-reason = Category permissions for Modmail.
ftl-cmd-setup-log-channel-name = thread-logs
ftl-cmd-setup-log-channel-topic = Modmail logs
ftl-cmd-setup-log-channel-create-reason = Log channel for Modmail.
ftl-cmd-setup-storage-channel-name = modmail-storage
ftl-cmd-setup-storage-channel-topic = Modmail storage (reserved for Modmail use only)
ftl-cmd-setup-storage-channel-create-reason = Storage channel for Modmail.
# TODO: Add more information (e.g. quick tutorial) + better format setup complete
# :param $category: the name of the Modmail category
# :param $log_channel: the name of the Modmail log channel
# :param $storage_channel: the name of the Modmail storage channel
ftl-cmd-setup-complete = Successfully setup Modmail. Your Modmail category is { $category }. I have also created a channel called { $log_channel } for Modmail logs and { $storage_channel } for storing some of my internal data. Feel free to rename and move these channels, but please do not delete them! Please check the permissions of the category and channels to make sure they are correct.


## Command: Modmail.reply

ftl-cmd-reply-name = reply
ftl-cmd-reply-description = Reply to a Modmail thread.
ftl-cmd-reply-param-attachment-name = attachment
ftl-cmd-reply-param-attachment-description = The attachment to send. Can be a file or an image.
ftl-cmd-reply-param-message-name = message
ftl-cmd-reply-param-message-description = The message to send.
ftl-cmd-reply-message-empty = Please enter a message to send.
flt-cmd-reply-message-sending = Sending the message...
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-cmd-reply-message-failed-recipients = Failed to send this message to the following recipients: { $recipients }.
                                          They may have disabled DMs, blocked me, or does not share any servers with me.
ftl-cmd-reply-message-failed = Failed to send the reply, please check my logs for more information.

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
