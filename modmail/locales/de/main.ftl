# This file contains localization strings for the German (de) locale.
# Translations here will be used across the entire Modmail project.

### ========================
###         General
### ========================

ftl-access-level-everyone = Jeder
ftl-access-level-staff = Mitarbeiter
ftl-access-level-manager = Manager
ftl-access-level-admin = Admin
ftl-access-level-owner = Besitzer

### ========================
###         Commands
### ========================

## Command: Utility.about

ftl-cmd-about-name = über
ftl-cmd-about-fallback-name = info
ftl-cmd-about-description = Zeigt Informationen über den Modmail-Bot an.

## Subcommand: Utility.about.version

ftl-cmd-about-version-name = version
ftl-cmd-about-version-description = Zeigt die Version des Modmail-Bots an.
# :param $version: the version of the bot
ftl-cmd-about-version-message = Modmail v{ $version }

## Command: Utility.status

ftl-cmd-status-name = status
ftl-cmd-status-fallback-name = setzen
ftl-cmd-status-description = Setzt den Status des Modmail-Bots.
ftl-cmd-status-param-status-description = Der zu setzende Status.

## Subcommand: Utility.status.clear

ftl-cmd-status-clear-name = löschen
ftl-cmd-status-clear-description = Löscht den Status des Modmail-Bots.

## Command: Utility.profile

ftl-cmd-profile-name = profil
ftl-cmd-profile-description = Zeigt eine Liste aller Profile an.
ftl-cmd-profile-fallback-name = anzeigen

ftl-modal-profile-customize-title = Profil anpassen
ftl-modal-profile-customize-colour = Farbe
ftl-modal-profile-customize-colour-invalid = Ungültige Farbe. Bitte verwenden Sie einen Farb-Hex-Code (z.B. #FF0000 für Rot).
ftl-modal-profile-customize-tag = Tag
# :param $name: the name of the user or role
ftl-modal-profile-customize-success = Profil von { $name } erfolgreich angepasst.
ftl-view-profile-button-customize-label = Anpassen
ftl-view-profile-select-level-placeholder = Wählen Sie eine Zugriffsebene
ftl-view-profile-select-level-option-none = Keine
# :param $level: the name of the access level ('None' when unsetting)
# :param $name: the name of the user or role
ftl-view-profile-select-level-success = { $level ->
   *[default] Zugriffsebene von { $name } erfolgreich auf { $level } gesetzt.
    [None]    Zugriffsebene von { $name } erfolgreich entfernt.
}

## Subcommand: Utility.profile.add

ftl-cmd-profile-add-name = hinzufügen
ftl-cmd-profile-add-description = Erstellt ein Profil für einen Benutzer oder eine Rolle.
# The following params can be used for the next 2 lines
# :param $name: the name of the user or role
ftl-cmd-profile-add-already-exists = { $name } hat bereits ein Profil.
ftl-cmd-profile-add-success = Profil für { $name } erfolgreich erstellt.

## Subcommand: Utility.profile.delete

ftl-cmd-profile-delete-name = löschen
ftl-cmd-profile-delete-description = Löscht ein Profil.
ftl-cmd-profile-delete-both = Bitte geben Sie nur einen Benutzer, eine Rolle oder eine ID ein.
ftl-cmd-profile-delete-none = Bitte geben Sie einen Benutzer, eine Rolle oder eine ID an.
# :param $name: the name of the user or role or ID
ftl-cmd-profile-delete-success = Profil von { $name } gelöscht.

## Subcommand: Utility.profile.customize

ftl-cmd-profile-customize-name = anpassen
ftl-cmd-profile-customize-description = Passt das Profil an.
# :param $name: the name of the user or role
ftl-cmd-profile-customize-message = Profil von { $name } wird angepasst.

## Subcommand: Utility.profile.allow
ftl-cmd-profile-allow-name = erlauben
ftl-cmd-profile-allow-description = Erlaubt Benutzern dieses Profils, einen Befehl zu verwenden.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-allow-success = { $name } darf { $command } verwenden.

## Subcommand: Utility.profile.deny
ftl-cmd-profile-deny-name = verweigern
ftl-cmd-profile-deny-description = Verweigert Benutzern dieses Profils die Verwendung eines Befehls.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-deny-success = { $name } darf { $command } nicht verwenden.

## Subcommand: Utility.profile.unset
ftl-cmd-profile-unset-name = zurücksetzen
ftl-cmd-profile-unset-description = Entfernt eine Erlaubnis-/Verweigerungsüberschreibung von diesem Profil für einen Befehl.
# The following params can be used for the next 3 lines
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-unset-success = Die Überschreibung für { $name } bei { $command } wurde zurückgesetzt.
ftl-cmd-profile-unset-profile-not-found = { $name } hat kein Profil.
ftl-cmd-profile-unset-override-not-found = Keine Überschreibung für { $command } bei { $name } vorhanden.

### ========================
###         Messages
### ========================

## Status messages

# current-status and set-status has $status as the name of the current status (formatted in models section)
# current-activity and set-activity has $activity as the name of the current activity (formatted in models section)
ftl-msg-status-current-status = Aktueller Status: { $status }
ftl-msg-status-current-activity = Aktuelle Aktivität: { $activity }
ftl-msg-status-no-status = Es ist derzeit kein Status gesetzt.
ftl-msg-status-set-status = Status auf { $status } gesetzt.
ftl-msg-status-set-activity = Aktivität auf { $activity } gesetzt.
ftl-msg-status-clear-status = Status gelöscht.

### ========================
###          Models
### ========================

## Activity model

# Official Discord prefixes for each activity type, custom is blank so not defined here
# Currently does not support suffixes if the language has them
ftl-model-activity-playing-name = spielt
ftl-model-activity-streaming-name = streamt
ftl-model-activity-listening-name = hört
ftl-model-activity-watching-name = schaut
ftl-model-activity-competing-name = tritt an in

# $activity_type is the type of activity (playing, streaming, etc.)
# $activity_name is the name of the activity
# $activity_url is the url of the activity (only for streaming)
ftl-model-activity-text = { $activity_type ->
    [playing]   Spielt { $activity_name }
    [streaming] Streamt { $activity_name } (<{ $activity_url }>)
    [listening] Hört { $activity_name } zu
    [watching]  Schaut { $activity_name }
    [competing] Tritt an in { $activity_name }
   *[custom]    { $activity_name }
}

## Status model

# Official Discord names for each status type
ftl-model-status-online-name = online
ftl-model-status-idle-name = abwesend
ftl-model-status-dnd-name = bns
ftl-model-status-dnd-full-name = bitte nicht stören
ftl-model-status-offline-name = offline
ftl-model-status-invisible-name = unsichtbar

# $status is the status type (online, idle, dnd, offline)
ftl-model-status-text = { $status ->
   *[online]  Online
    [idle]    Abwesend
    [dnd]     Bitte nicht stören (bns)
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
