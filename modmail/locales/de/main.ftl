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

ftl-view-prompt-cancel-label = Abbrechen

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
ftl-cmd-status-param-status-name = status
ftl-cmd-status-param-status-description = Der zu setzende Status.

## Subcommand: Utility.status.clear

ftl-cmd-status-clear-name = löschen
ftl-cmd-status-clear-description = Löscht den Status des Modmail-Bots.

## Command: Utility.profile

ftl-cmd-profile-name = profil
ftl-cmd-profile-description = Zeigt eine Liste aller Profile an.
ftl-cmd-profile-fallback-name = anzeigen

ftl-cmd-profile-no-bot = Bots können keine Profile haben.

ftl-modal-profile-customize-title = Profil anpassen
ftl-modal-profile-customize-colour = Farbe
ftl-modal-profile-customize-colour-invalid = Ungültige Farbe. Bitte verwende einen Farb-Hex-Code (z. B. #FF0000 für Rot).
ftl-modal-profile-customize-tag = Tag
# :param $name: the name of the user or role
ftl-modal-profile-customize-success = Profil von { $name } erfolgreich angepasst.
ftl-view-profile-button-customize-label = Anpassen
ftl-view-profile-select-level-placeholder = Zugriffsebene ändern
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
ftl-cmd-profile-add-param-user-or-role-name = benutzer_oder_rolle
ftl-cmd-profile-add-param-user-or-role-description = Der Benutzer oder die Rolle, für den/die ein Profil erstellt werden soll.
# The following params can be used for the next 2 lines
# :param $name: the name of the user or role
ftl-cmd-profile-add-already-exists = { $name } hat bereits ein Profil.
ftl-cmd-profile-add-success = Profil für { $name } erfolgreich erstellt.

## Subcommand: Utility.profile.delete

ftl-cmd-profile-delete-name = löschen
ftl-cmd-profile-delete-description = Löscht ein Profil.
ftl-cmd-profile-delete-param-user-or-role-name = benutzer_oder_rolle
ftl-cmd-profile-delete-param-user-or-role-description = Der Benutzer oder die Rolle, dessen/deren Profil gelöscht werden soll.
ftl-cmd-profile-delete-both = Bitte gib nur einen Benutzer, eine Rolle oder eine ID ein.
ftl-cmd-profile-delete-none = Bitte gib einen Benutzer, eine Rolle oder eine ID an.
# :param $name: the name of the user or role or ID
ftl-cmd-profile-delete-success = Profil von { $name } gelöscht.

## Subcommand: Utility.profile.edit

ftl-cmd-profile-edit-name = bearbeiten
ftl-cmd-profile-edit-description = Passt das Profil an.
ftl-cmd-profile-edit-param-user-or-role-name = benutzer_oder_rolle
ftl-cmd-profile-edit-param-user-or-role-description = Der Benutzer oder die Rolle, dessen/deren Profil angepasst werden soll.
# :param $name: the name of the user or role
ftl-cmd-profile-edit-message = Profil von { $name } wird angepasst.

## Subcommand: Utility.profile.allow

ftl-cmd-profile-allow-name = erlauben
ftl-cmd-profile-allow-description = Erlaubt Benutzern dieses Profils, einen Befehl zu verwenden.
ftl-cmd-profile-allow-param-user-or-role-name = benutzer_oder_rolle
ftl-cmd-profile-allow-param-user-or-role-description = Der Benutzer oder die Rolle, dem/der Zugriff gewährt werden soll.
ftl-cmd-profile-allow-param-command-name-name = befehl-name
ftl-cmd-profile-allow-param-command-name-description = Der zu erlaubende Befehl. Kann Platzhalter mit "+" für Befehlsgruppen enthalten.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-allow-success = { $name } darf { $command } verwenden.
# The following params can be used for the next 2 lines
# :param $command: the name of the command
ftl-cmd-profile-override-owner-command = Nur Bot-Besitzer können diesen Befehl überschreiben.
ftl-cmd-profile-override-command-not-found = Befehl { $command } nicht gefunden.

## Subcommand: Utility.profile.deny

ftl-cmd-profile-deny-name = verweigern
ftl-cmd-profile-deny-description = Verweigert Benutzern dieses Profils die Verwendung eines Befehls.
ftl-cmd-profile-deny-param-user-or-role-name = benutzer_oder_rolle
ftl-cmd-profile-deny-param-user-or-role-description = Der Benutzer oder die Rolle, dem/der Zugriff verweigert werden soll.
ftl-cmd-profile-deny-param-command-name-name = befehl-name
ftl-cmd-profile-deny-param-command-name-description = Der zu verbietende Befehl. Kann Platzhalter mit "+" für Befehlsgruppen enthalten.
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-deny-success = { $name } darf { $command } nicht verwenden.

## Subcommand: Utility.profile.unset

ftl-cmd-profile-unset-name = zurücksetzen
ftl-cmd-profile-unset-description = Entfernt eine Erlaubnis-/Verweigerungsüberschreibung von diesem Profil für einen Befehl.
ftl-cmd-profile-unset-param-user-or-role-name = benutzer_oder_rolle
ftl-cmd-profile-unset-param-user-or-role-description = Der Benutzer oder die Rolle, für den/die die Überschreibung entfernt werden soll.
ftl-cmd-profile-unset-param-command-name-name = befehl-name
ftl-cmd-profile-unset-param-command-name-description = Der Befehl, von dem die Überschreibung entfernt werden soll. Leer lassen, um alle Überschreibungen zu entfernen.
# The following params can be used for the next 3 lines
# :param $name: the name of the user or role
# :param $command: the name of the command
ftl-cmd-profile-unset-success = Die Überschreibung für { $name } bei { $command } wurde zurückgesetzt.
ftl-cmd-profile-unset-profile-not-found = { $name } hat kein Profil.
ftl-cmd-profile-unset-override-not-found = Keine Überschreibung für { $command } bei { $name } vorhanden.

## Command: Modmail.setup

ftl-cmd-setup-name = setup
ftl-cmd-setup-description = Richtet den Modmail-Bot ein.
ftl-cmd-setup-not-enough-guild-permissions = Ich habe nicht genug Berechtigungen in diesem Server.
# :param $guild_name: the name of the staff guild
ftl-cmd-setup-wrong-guild = Du kannst den Modmail-Bot nur im Mitarbeiter-Server ({ $guild_name }) einrichten.
ftl-cmd-setup-already-running = Du kannst diesen Befehl gerade nicht verwenden. Bitte versuche es später erneut.
ftl-msg-setup-category-or-forum-name = Modmail
ftl-msg-setup-category-or-forum-create-reason = Kategorie/Forum für Modmail.
ftl-msg-setup-category-or-forum-permissions-reason = Kategorie-/Forum-Berechtigungen für Modmail.
ftl-msg-setup-forum-thread-unpin-reason = Bestehenden Thread im Modmail-Forum lösen.
ftl-msg-setup-log-channel-name = ticket-logs
ftl-msg-setup-log-channel-topic = Modmail-Protokolle
ftl-msg-setup-log-channel-create-reason = Protokollkanal für Modmail.
ftl-msg-setup-storage-channel-name = modmail-storage
ftl-msg-setup-storage-channel-topic = Modmail-Speicher (nur für Modmail reserviert)
ftl-msg-setup-storage-channel-create-reason = Speicherkanal für Modmail.

## Setup wizard

ftl-wizard-setup-reconfigure-content =
    ### Modmail ist bereits eingerichtet
    Durch Fortfahren wird die aktuelle Einrichtung ersetzt.
    Alle zuvor von Modmail erstellten Kanäle bleiben erhalten, werden aber nicht mehr verwendet.
ftl-wizard-setup-reconfigure-btn-continue = Fortfahren

ftl-wizard-setup-type-content =
    ### Schritt 1 von 3 — Layout auswählen
    Wähle aus, wie Modmail-Tickets organisiert werden sollen.
    - **Kategorie** — jedes Ticket erhält einen eigenen Textkanal innerhalb einer Kategorie.
    - **Forum** — jedes Ticket wird zu einem Beitrag in einem Forumkanal.
ftl-wizard-setup-type-btn-category = Kategorie
ftl-wizard-setup-type-btn-forum = Forum

ftl-wizard-setup-new-or-existing-content-category =
    ### Schritt 2 von 3 — Neu oder vorhanden?
    Soll ich eine neue **Modmail**-Kategorie erstellen oder eine bestehende in diesem Server verwenden?
ftl-wizard-setup-new-or-existing-content-forum =
    ### Schritt 2 von 3 — Neu oder vorhanden?
    Soll ich einen neuen **Modmail**-Forumkanal erstellen oder einen bestehenden in diesem Server verwenden?
ftl-wizard-setup-new-or-existing-btn-create = Neu erstellen
ftl-wizard-setup-new-or-existing-btn-existing-category = Bestehende Kategorie verwenden
ftl-wizard-setup-new-or-existing-btn-existing-forum = Bestehendes Forum verwenden

ftl-wizard-setup-select-existing-content-category =
    ### Schritt 3 von 3 — Kategorie auswählen
    Wähle über das Dropdown-Menü die Kategorie aus, die Modmail verwenden soll.
    Der Bot muss bereits Zugriff darauf haben.
ftl-wizard-setup-select-existing-content-forum =
    ### Schritt 3 von 3 — Forum auswählen
    Wähle über das Dropdown-Menü das Forum aus, das Modmail verwenden soll.
    Der Bot muss bereits Zugriff darauf haben.
ftl-wizard-setup-select-existing-placeholder-category = Kategorie auswählen…
ftl-wizard-setup-select-existing-placeholder-forum = Forum auswählen…
ftl-wizard-setup-select-existing-wrong-type-category = Bitte wähle eine Kategorie aus, kein Forum.
ftl-wizard-setup-select-existing-wrong-type-forum = Bitte wähle ein Forum aus, keine Kategorie.
ftl-wizard-setup-select-existing-no-perms = Ich habe nicht genug Berechtigungen im ausgewählten Kanal. Bitte wähle einen anderen aus.

ftl-wizard-setup-confirm-content-new-category =
    ### Einrichtung bestätigen
    Eine neue **Modmail**-Kategorie wird mit einem Protokollkanal und einem Speicherkanal darin erstellt.
    Berechtigungen werden automatisch konfiguriert.
ftl-wizard-setup-confirm-content-new-forum =
    ### Einrichtung bestätigen
    Ein neues **Modmail**-Forum wird für Tickets erstellt, mit einem Protokoll-Thread darin und einem separaten Speicherkanal.
    Berechtigungen werden automatisch konfiguriert.
# :param $name: the name of the existing category
ftl-wizard-setup-confirm-content-existing-category =
    ### Einrichtung bestätigen
    Die Kategorie **{ $name }** wird verwendet.
    Ein Protokollkanal und ein Speicherkanal werden darin hinzugefügt.
# :param $name: the name of the existing forum
ftl-wizard-setup-confirm-content-existing-forum =
    ### Einrichtung bestätigen
    Das Forum **{ $name }** wird für Tickets verwendet.
    Ein Protokoll-Thread wird darin hinzugefügt und ein separater Speicherkanal erstellt.
ftl-wizard-setup-confirm-btn = Bestätigen & Einrichten
ftl-wizard-setup-btn-back = Zurück

ftl-wizard-setup-working-content =
    ### Modmail wird eingerichtet…
    Das sollte nur einen Moment dauern. Bitte warten.
ftl-wizard-setup-canceled-content =
    ### Einrichtung abgebrochen
    Es wurden keine Änderungen vorgenommen. Führe den Befehl erneut aus, wenn du bereit bist.
ftl-wizard-setup-timeout-content =
    ### Einrichtung abgelaufen
    Der Assistent wurde wegen Inaktivität geschlossen. Es wurden keine Änderungen vorgenommen. Führe den Befehl erneut aus, um neu zu starten.
ftl-wizard-setup-error-channel-gone = Der ausgewählte Kanal existiert nicht mehr. Führe den Befehl erneut aus und wähle einen anderen.

# :param $category: the name of the Modmail category
# :param $log_channel: mention of the log channel
# :param $storage_channel: mention of the storage channel
ftl-wizard-setup-success-content-category =
    ## Einrichtung abgeschlossen
    Modmail ist jetzt konfiguriert und einsatzbereit.
    { "*" }*Kategorie:** { $category }
    { "*" }*Protokolle:** { $log_channel }
    { "*" }*Speicher:** { $storage_channel }
    Du kannst diese Kanäle umbenennen oder verschieben, aber bitte nicht löschen.
# :param $forum: the name of the Modmail forum
# :param $log_channel: mention of the log thread
# :param $storage_channel: mention of the storage channel
ftl-wizard-setup-success-content-forum =
    ## Einrichtung abgeschlossen
    Modmail ist jetzt konfiguriert und einsatzbereit.
    { "*" }*Forum:** { $forum }
    { "*" }*Protokolle:** { $log_channel }
    { "*" }*Speicher:** { $storage_channel }
    Du kannst diese Kanäle umbenennen oder verschieben, aber bitte nicht löschen.

## Command: Modmail.reply

ftl-cmd-reply-name = antworten
ftl-cmd-reply-description = Auf ein Modmail-Ticket antworten.
ftl-cmd-reply-param-attachment-name = anhang
ftl-cmd-reply-param-attachment-description = Der zu sendende Anhang. Kann eine Datei oder ein Bild sein.
ftl-cmd-reply-param-message-name = nachricht
ftl-cmd-reply-param-message-description = Die zu sendende Nachricht.
ftl-cmd-reply-message-empty = Bitte gib eine Nachricht zum Senden ein.
ftl-cmd-reply-message-sending = Nachricht wird gesendet...
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-cmd-reply-message-failed-recipients = Diese Nachricht konnte nicht an folgende Empfänger gesendet werden: { $recipients }.
                                          Sie haben möglicherweise DMs deaktiviert, mich blockiert oder teilen keinen Server mit mir.
ftl-cmd-reply-message-failed = Fehler beim Senden der Antwort. Bitte überprüfe die Protokolle für weitere Informationen.

## Command: Modmail.close

ftl-cmd-close-name = schließen
ftl-cmd-close-description = Ein Modmail-Ticket schließen.
ftl-cmd-close-param-attachment-name = anhang
ftl-cmd-close-param-attachment-description = Der zu sendende Anhang. Kann eine Datei oder ein Bild sein.
ftl-cmd-close-param-message-name = nachricht
ftl-cmd-close-param-message-description = Die zu sendende Nachricht.
ftl-cmd-close-message-sending = Ticket wird geschlossen...
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-cmd-close-message-failed-recipients = Die Schließnachricht konnte nicht an folgende Empfänger gesendet werden: { $recipients }.
                                          Sie haben möglicherweise DMs deaktiviert, mich blockiert oder teilen keinen Server mit mir.
ftl-cmd-close-message-failed = Fehler beim Senden der Schließnachricht. Bitte überprüfe die Protokolle für weitere Informationen.

## Command: Modmail.sclose

ftl-cmd-sclose-name = sschließen
ftl-cmd-sclose-description = Ein Modmail-Ticket lautlos schließen.
ftl-cmd-sclose-param-attachment-name = anhang
ftl-cmd-sclose-param-attachment-description = Der mit der Schließnachricht zu speichernde Anhang. Kann eine Datei oder ein Bild sein.
ftl-cmd-sclose-param-message-name = nachricht
ftl-cmd-sclose-param-message-description = Die als Schließnachricht zu speichernde Nachricht.
ftl-cmd-sclose-message-sending = Ticket wird geschlossen...

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

# :param $user_or_role: the name of the user or role
ftl-msg-grant-access-reason = Zugang für { $user_or_role } zur Modmail-Kategorie und den Kanälen gewähren.
ftl-msg-revoke-access-reason = Zugang von { $user_or_role } zur Modmail-Kategorie und den Kanälen entziehen.

ftl-msg-permission-denied = Du hast keine Berechtigung, diesen Befehl zu verwenden.
ftl-msg-command-invoke-error = Beim Verarbeiten deines Befehls ist ein unbekannter Fehler aufgetreten. Bitte versuche es später erneut.
                               Wenn das Problem weiterhin besteht, überprüfe deine Protokolle und melde den Fehler dem Modmail-Team.

ftl-msg-prompt-timeout = Zeitüberschreitung. Bitte führe den Befehl erneut aus.

ftl-msg-dm-received-not-configured = Modmail wurde noch nicht eingerichtet. Bitte wende dich an den Server-Inhaber, um Modmail für den Server einzurichten.
# :param $recipients: a comma-separated list of recipients who did not receive the message
ftl-msg-dm-received-failed-recipients = Folgende Empfänger haben diese Nachricht nicht erhalten: { $recipients }.
                                        Sie haben möglicherweise DMs deaktiviert, mich blockiert oder teilen keinen Server mit mir.

# :param $users: a comma-separated list of usernames
ftl-msg-new-ticket-reason = Neues Modmail-Ticket für: { $users }
# :param $users: a space-separated list of user mentions
ftl-msg-new-ticket-default-thread-opening-message = { $users } hat ein neues Modmail-Ticket erstellt.
# :param $created: the date the account was created
ftl-msg-new-ticket-initial-embed-description = Konto erstellt { $created }.
# :param $user_id: the user ID of the user (string)
ftl-msg-new-ticket-initial-embed-footer = Benutzer-ID: { $user_id }
# :param $joined: the date the user joined the server
# :param $roles: a comma-separated list of roles
# :param $has_role: whether the user has a role in the server (true) or not (false)
ftl-msg-new-ticket-initial-embed-guild-field-value = Beigetreten { $joined }.
                                                     Rollen: { $has_role ->
    *[true]  { $roles }
     [false] Keine
}
ftl-msg-new-ticket-initial-embed-guild-field-value-no-join-date = [Unbekannt]
ftl-msg-new-ticket-initial-embed-past-tickets-field-name = Frühere Tickets
# :param $count: the number of past tickets
ftl-msg-new-ticket-initial-embed-past-tickets-field-value = { $count ->
     [one] 1 früheres Ticket
    *[other] { $count } frühere Tickets
}
ftl-msg-create-ticket-failed = Beim Erstellen dieses Modmail-Tickets ist etwas schiefgelaufen. Bitte überprüfe die Protokolle für weitere Informationen.

# :param $user: the name of the closer
ftl-msg-ticket-closed-reason = Modmail-Ticket von { $user } geschlossen.
ftl-msg-ticket-closed-reason-unknown-closer = Modmail-Ticket von unbekanntem Benutzer geschlossen.

# :param $message_id: the message ID of the message (string)
ftl-msg-ticket-channel-embed-footer = Nachrichten-ID: { $message_id }

ftl-msg-log-embed-open-footer = Ticket offen
# :param $user: the username of the closer
ftl-msg-log-embed-closed-footer = Ticket geschlossen von @{ $user }
ftl-msg-log-embed-closed-footer-unknown-closer = Ticket geschlossen
ftl-msg-log-embed-no-content-description = *Kein Inhalt*

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
