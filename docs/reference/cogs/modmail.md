# Modmail Cog

Commands and event listeners that implement the core ticket workflow.

::: cogs.modmail
    options:
        heading: "Modmail"
        toc_label: "Modmail"

::: cogs.modmail.commands
    options:
        heading: "Commands"
        toc_label: "Commands"
        show_submodules: true
        filters:
            - "!^_[^_]"
            - "!^__all__$"
            - "!^logger$"
            - "!^all_commands$"

::: cogs.modmail.listeners
    options:
        heading: "Event listeners"
        toc_label: "Event listeners"
        show_submodules: true
        filters:
            - "!^_[^_]"
            - "!^__all__$"
            - "!^logger$"
            - "!^all_listeners$"
