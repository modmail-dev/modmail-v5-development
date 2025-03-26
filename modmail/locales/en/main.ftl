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
ftl-cmd-status-param-status-description = The status to set.

## Subcommand: Utility.status.clear

ftl-cmd-status-clear-name = clear
ftl-cmd-status-clear-description = Clear the status of the Modmail bot.

## Command: Utility.profile

ftl-cmd-profile-name = profile
ftl-cmd-profile-description = View a list of all profiles.
ftl-cmd-profile-fallback-name = view

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
# The following params can be used for the next 2 lines
# :param $name: the name of the user or role
ftl-cmd-profile-add-already-exists = { $name } already has a profile.
ftl-cmd-profile-add-success = Successfully created a profile for { $name }.

## Subcommand: Utility.profile.delete

ftl-cmd-profile-delete-name = delete
ftl-cmd-profile-delete-description = Delete a profile.
ftl-cmd-profile-delete-both = Please only enter a user, role, or ID.
ftl-cmd-profile-delete-none = Please provide a user, role, or ID.
# :param $name: the name of the user or role or ID
ftl-cmd-profile-delete-success = Deleted the profile of { $name }.

## Subcommand: Utility.profile.customize

ftl-cmd-profile-customize-name = customize
ftl-cmd-profile-customize-description = Customize the profile.
# :param $name: the name of the user or role
ftl-cmd-profile-customize-message = Customizing the profile of { $name }.

## Subcommand: Utility.profile.allow
ftl-cmd-profile-allow-name = allow
ftl-cmd-profile-allow-description = Allow users of this profile to use a command.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-allow-success = Allowed { $name } to use { $command }.

## Subcommand: Utility.profile.deny
ftl-cmd-profile-deny-name = deny
ftl-cmd-profile-deny-description = Deny users of this profile from using a command.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-deny-success = Denied { $name } from using { $command }.

## Subcommand: Utility.profile.unset
ftl-cmd-profile-unset-name = unset
ftl-cmd-profile-unset-description = Remove an allow/deny override from this profile on a command.
# The following params can be used for the next 3 lines
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-unset-success = The override for { $name } on { $command } has been unset.
ftl-cmd-profile-unset-profile-not-found = { $name } does not have a profile.
ftl-cmd-profile-unset-override-not-found = No override exists on { $command } for { $name }.

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
