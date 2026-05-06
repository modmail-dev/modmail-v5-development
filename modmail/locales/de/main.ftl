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
ftl-cmd-profile-description = Berechtigungsprofile für Benutzer und Rollen anzeigen und verwalten.
ftl-cmd-profile-fallback-name = liste

## Modals: profile appearance and override

ftl-modal-profile-customize-title = Aussehen anpassen
ftl-modal-profile-customize-color = Farbe
ftl-modal-profile-customize-color-placeholder = #000000
ftl-modal-profile-customize-color-invalid = Ungültige Farbe. Bitte verwende einen Farb-Hex-Code (z. B. #FF0000 für Rot).
ftl-modal-profile-customize-tag = Tag
# :param $profile: the mention of the user or role
ftl-modal-profile-customize-success = Aussehen von { $profile } aktualisiert.

ftl-modal-profile-remove-override-title = Überschreibung entfernen
ftl-modal-profile-remove-override-name-label = Name der Überschreibung
ftl-modal-profile-remove-override-name-placeholder = z. B. antworten, profil+
# :param $command: the override name entered
ftl-modal-profile-remove-override-not-found = Keine Überschreibung namens `{ $command }` auf diesem Profil vorhanden.
# :param $command: the override name removed
ftl-modal-profile-remove-override-success = Überschreibung für `{ $command }` entfernt.

ftl-modal-profile-add-override-allow-title = Befehl erlauben
ftl-modal-profile-add-override-deny-title = Befehl verweigern
ftl-modal-profile-add-override-command-label = Befehlsname
ftl-modal-profile-add-override-command-placeholder = z. B. antworten, profil+
# :param $command: the command name
ftl-modal-profile-add-override-already-allow = `{ $command }` ist auf diesem Profil bereits erlaubt.
# :param $command: the command name
ftl-modal-profile-add-override-already-deny = `{ $command }` ist auf diesem Profil bereits verweigert.

## Profile editor card (ProfileEditorView)

# :param $profile: the mention of the user or role
# :param $type: "Benutzer" or "Rolle"
ftl-view-profile-editor-header = ### Profil: { $profile }
    **Typ**: { $type }
ftl-view-profile-editor-type-user = Benutzer
ftl-view-profile-editor-type-role = Rolle
# :param $level: the access level label or "Keine"
# :param $tag: the tag value or "Nicht gesetzt"
# :param $color: the hex color string or "Nicht gesetzt"
ftl-view-profile-editor-summary = **Zugriffsebene**: { $level }  •  **Tag**: { $tag }  •  **Farbe**: { $color }
ftl-view-profile-editor-level-none = Keine
ftl-view-profile-editor-not-set = Nicht gesetzt
ftl-view-profile-editor-select-level-placeholder = Zugriffsebene ändern…
ftl-view-profile-editor-btn-delete = Löschen
ftl-view-profile-editor-btn-customize = Anpassen
ftl-view-profile-editor-btn-add-allow = + Erlauben
ftl-view-profile-editor-btn-add-deny = + Verweigern
# :param $count: number of overrides
ftl-view-profile-editor-overrides-header = { $count ->
    [0]    **Berechtigungsüberschreibungen** — Keine
   *[other] **Berechtigungsüberschreibungen** ({ $count })
}
ftl-view-profile-editor-select-remove-placeholder = Überschreibung entfernen…
ftl-view-profile-editor-btn-remove-override = Überschreibung entfernen
ftl-view-profile-editor-override-value-allow = Erlauben
ftl-view-profile-editor-override-value-deny = Verweigern
# :param $command: the command name
ftl-view-profile-editor-override-line-allow = ✅ `{ $command }`
# :param $command: the command name
ftl-view-profile-editor-override-line-deny = ❌ `{ $command }`
# :param $command: the command name
ftl-view-profile-editor-override-allow-success = ✅ `{ $command }` für dieses Profil erlaubt.
# :param $command: the command name
ftl-view-profile-editor-override-deny-success = ❌ `{ $command }` für dieses Profil verweigert.
ftl-view-profile-editor-delete-confirm = Bist du sicher, dass du dieses Profil löschen möchtest? Dies kann nicht rückgängig gemacht werden.
ftl-view-profile-editor-delete-btn-confirm = Profil löschen
# :param $profile: the mention of the user or role
ftl-view-profile-editor-deleted-content =
    ### Profil gelöscht
    Das Profil von { $profile } wurde entfernt.
ftl-view-profile-editor-update-failed = Etwas ist schiefgelaufen. Bitte versuche es erneut.
ftl-view-profile-editor-access-sync-failed = Profil aktualisiert, aber die Discord-Kanalberechtigungen konnten nicht synchronisiert werden.

## Subcommand: Utility.profile.list (fallback)

# :param $count: the number of profiles
ftl-cmd-profile-list-title = ### Profile ({ $count })
ftl-cmd-profile-list-empty = Es wurden noch keine Profile konfiguriert.
ftl-cmd-profile-list-no-level = Keine Zugriffsebene
# :param $count: number of overrides
ftl-cmd-profile-list-overrides = { $count ->
    [0]     keine Überschreibungen
    [one]   { $count } Überschreibung
   *[other] { $count } Überschreibungen
}
# :param $mention: the profile mention
# :param $level: the access level label
# :param $overrides: the formatted override count string
ftl-cmd-profile-list-row = - **{ $mention }** — { $level } · { $overrides }
ftl-cmd-profile-list-tip = -# Verwende `/{ ftl-cmd-profile-name } { ftl-cmd-profile-edit-name }`, um ein Profil hinzuzufügen oder zu bearbeiten.

## Subcommand: Utility.profile.edit

ftl-cmd-profile-edit-name = bearbeiten
ftl-cmd-profile-edit-description = Zugriffsebene, Aussehen und Befehlsüberschreibungen eines Profils bearbeiten.
ftl-cmd-profile-edit-param-target-name = benutzer_oder_rolle
ftl-cmd-profile-edit-param-target-description = Der Benutzer oder die Rolle, dessen/deren Profil bearbeitet werden soll.

## Subcommand: Utility.profile.delete

ftl-cmd-profile-delete-name = löschen
ftl-cmd-profile-delete-description = Profil löschen und alle Zugriffseinstellungen sowie Befehlsüberschreibungen entfernen.
ftl-cmd-profile-delete-param-target-name = benutzer_oder_rolle
ftl-cmd-profile-delete-param-target-description = Der Benutzer oder die Rolle, dessen/deren Profil gelöscht werden soll.
ftl-cmd-profile-delete-param-id-name = id
ftl-cmd-profile-delete-param-id-description = Discord-ID verwenden, wenn der Benutzer oder die Rolle nicht mehr im Server existiert.
ftl-cmd-profile-delete-both = Entweder einen Benutzer oder eine Rolle, oder eine ID angeben – nicht beides.
ftl-cmd-profile-delete-none = Bitte einen Benutzer, eine Rolle oder eine ID angeben.
ftl-cmd-profile-delete-not-found = Kein Profil für diesen Benutzer, diese Rolle oder diese ID gefunden.
# :param $profile: the mention of the user or role or ID
ftl-cmd-profile-delete-success = Profil von { $profile } gelöscht.
ftl-cmd-profile-delete-failed = Profil konnte nicht gelöscht werden. Bitte versuche es erneut.

## Shared override error messages

# :param $command: the name of the command
ftl-cmd-profile-override-owner-command = Nur Bot-Besitzer können diesen Befehl überschreiben.
ftl-cmd-profile-override-command-not-found = Befehl `{ $command }` nicht gefunden.

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
ftl-cmd-close-failed = Fehler beim Schließen des Tickets. Bitte überprüfe die Protokolle für weitere Informationen.

## Command: Modmail.sclose

ftl-cmd-sclose-name = sschließen
ftl-cmd-sclose-description = Ein Modmail-Ticket lautlos schließen.
ftl-cmd-sclose-param-attachment-name = anhang
ftl-cmd-sclose-param-attachment-description = Der mit der Schließnachricht zu speichernde Anhang. Kann eine Datei oder ein Bild sein.
ftl-cmd-sclose-param-message-name = nachricht
ftl-cmd-sclose-param-message-description = Die als Schließnachricht zu speichernde Nachricht.
ftl-cmd-sclose-message-sending = Ticket wird geschlossen...
ftl-cmd-sclose-failed = Fehler beim Schließen des Tickets. Bitte überprüfe die Protokolle für weitere Informationen.

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
ftl-msg-bad-permissions = Mir fehlen hier die folgenden Berechtigungen: { $permissions }.
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
###    Converter errors
### ========================

## Profile converter errors

# :param $argument: the raw argument string supplied by the user
ftl-error-converter-profile-not-found = Es konnte kein Nutzer oder keine Rolle für „{ $argument }" gefunden werden.
ftl-error-converter-profile-is-bot = Bots können keine Profile haben.

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
