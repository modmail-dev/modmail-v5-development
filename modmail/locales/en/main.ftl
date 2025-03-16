# This file contains localization strings for the English (en) locale.
# Translations here will be used across the entire Modmail project.

### ========================
###         Commands
### ========================

## Command: Utility.about

cmd-about-name = about
cmd-about-fallback-name = info
cmd-about-description = Shows information about the Modmail bot.

## Subcommand: Utility.about.version

cmd-about-version-name = version
cmd-about-version-description = Shows the version of the Modmail bot.
# Has $version as the version of the bot
cmd-about-version-message = Modmail v{ $version }

## Command: Utility.status

cmd-status-name = status
cmd-status-fallback-name = set
cmd-status-description = Set the status of the Modmail bot.
cmd-status-param-status-description = The status to set.

## Subcommand: Utility.status.clear

cmd-status-clear-name = clear
cmd-status-clear-description = Clear the status of the Modmail bot.

### ========================
###         Messages
### ========================

## Status messages

# current-status and set-status has $status as the name of the current status (formatted in models section)
# current-activity and set-activity has $activity as the name of the current activity (formatted in models section)
msg-status-current-status = Current status: { $status }
msg-status-current-activity = Current activity: { $activity }
msg-status-no-status = No status is currently set.
msg-status-set-status = Set status to { $status }.
msg-status-set-activity = Set activity to { $activity }.
msg-status-clear-status = Cleared status.


### ========================
###          Models
### ========================

## Activity model

# Official Discord prefixes for each activity type, custom is blank so not defined here
# Currently does not support suffixes if the language has them
model-activity-playing-name = playing
model-activity-streaming-name = streaming
model-activity-listening-name = listening to
model-activity-watching-name = watching
model-activity-competing-name = competing in

# $activity_type is the type of activity (playing, streaming, etc.)
# $activity_name is the name of the activity
# $activity_url is the url of the activity (only for streaming)
model-activity-text = { $activity_type ->
    [playing]   Playing { $activity_name }
    [streaming] Streaming { $activity_name } (<{ $activity_url }>)
    [listening] Listening to { $activity_name }
    [watching]  Watching { $activity_name }
    [competing] Competing in { $activity_name }
   *[custom]    { $activity_name }
}

## Status model

# Official Discord names for each status type
model-status-online-name = online
model-status-idle-name = idle
model-status-dnd-name = dnd
model-status-dnd-full-name = do not disturb
model-status-offline-name = offline
model-status-invisible-name = invisible

# $status is the status type (online, idle, dnd, offline)
model-status-text = { $status ->
   *[online]  Online
    [idle]    Idle
    [dnd]     Do not disturb (dnd)
    [offline] Offline
}

### ========================
### Internal (Don't Change)
### ========================

# Placeholder for when an option shouldn't be used, but still got used regardless
flt-error = !Error!

# Placeholder for an empty string
flt-blank = { "" }
