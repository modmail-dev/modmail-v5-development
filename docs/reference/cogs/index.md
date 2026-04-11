# Cogs

Discord.py cogs that implement the bot's command surface and event handling.

| Cog | Description |
|---|---|
| [Modmail](modmail.md) | Ticket commands (`reply`, `close`, `setup`, `sclose`) and DM/channel listeners |
| [Utility](utility.md) | Informational commands (`about`, `status`) and profile management |

All cogs extend the custom [`Cog`][modmail.core.internals.cog.Cog] base class, which wires up the translator and shared bot context automatically.
