# This file contains localization strings for the English (en) locale.
# Translations here will be used across the entire Modmail project.

### ========================
###         General
### ========================

ftl-perm-level-everyone = Everyone
ftl-perm-level-staff = Staff
ftl-perm-level-manager = Manager
ftl-perm-level-admin = Admin
ftl-perm-level-owner = Owner

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
# Has $version as the version of the bot
ftl-cmd-about-version-message = Modmail v{ $version }

## Command: Utility.status

ftl-cmd-status-name = status
ftl-cmd-status-fallback-name = set
ftl-cmd-status-description = Set the status of the Modmail bot.
ftl-cmd-status-param-status-description = The status to set.

## Subcommand: Utility.status.clear

ftl-cmd-status-clear-name = clear
ftl-cmd-status-clear-description = Clear the status of the Modmail bot.

## Command: Utility.perm

ftl-cmd-perm-name = perm
ftl-cmd-perm-description = Manage the permissions of the Modmail bot.
ftl-cmd-perm-fallback-name = view

ftl-modal-perm-customize-title = Customize Permissions
ftl-model-perm-customize-colour = Colour
ftl-model-perm-customize-tag = Tag
ftl-view-perm-button-customize-label = Customize
ftl-view-perm-select-level-placeholder = Select a permission level
ftl-view-perm-select-level-option-none = None
ftl-view-perm-select-level-success = Successfully set the permission level to { $level }.

## Subcommand: Utility.perm.add

ftl-cmd-perm-add-name = add
ftl-cmd-perm-add-description = Add a user or role to the ACL list.
ftl-cmd-perm-add-both = User and role cannot be used at the same time.
ftl-cmd-perm-add-none = Please provide either a user or role.
ftl-cmd-perm-add-already-exists = The user or role already exists in the ACL list.
ftl-cmd-perm-add-success = Added { $group } to the ACL list.

## Subcommand: Utility.perm.remove

ftl-cmd-perm-remove-name = remove
ftl-cmd-perm-remove-description = Remove a user or role from the ACL list.
ftl-cmd-perm-remove-both = { -ftl-cmd-perm-add-both }
ftl-cmd-perm-remove-none = { -ftl-cmd-perm-add-none }
ftl-cmd-perm-remove-success = Removed { $group } from the ACL list.

### ========================
###         Messages
### ========================

## Status messages

# current-status and set-status has $status as the name of the current status (formatted in models section)
# current-activity and set-activity has $activity as the name of the current activity (formatted in models section)
ftl-msg-status-current-status = Current status: { $status }
ftl-msg-status-current-activity = Current activity: { $activity }
ftl-msg-status-no-status = No status is currently set.
ftl-msg-status-set-status = Set status to { $status }.
ftl-msg-status-set-activity = Set activity to { $activity }.
ftl-msg-status-clear-status = Cleared status.


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
