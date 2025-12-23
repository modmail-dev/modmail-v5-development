# Modmail v5 - WIP, UNSTABLE BUILD

> [!CAUTION]
> This build of Modmail is currently a work in progress and is considered highly unstable and lacks essential features.
> It is not recommended for general usage at this time. Please use the stable v4 release for production environments at https://github.com/modmail-dev/modmail.
>
> No migration effort will be made between pushes, bugs and vulnerabilities are expected, and data loss may occur if used.
> We are also not accepting contributions through issues and pull requests for this branch at this time.

1. Copy `config.yaml.example` and rename it to `config.yaml`, then edit it with your settings
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run `uv sync --locked --compile-bytecode --no-default-groups --extra speed --extra DBTYPE` to install the dependencies
   - Replace `DBTYPE` with `mongodb` or `sqlite`, only these two are supported at the moment
3. Start the bot with `uv run python start.py`

Please note that the database structure may change at any time, and database migrations between v5 alpha development versions are not available.
You will need to drop the database when the structure changes.

### Short-Term TODOs

- [x] Forum implementation, alternative to category/channel structure
- [x] Implement log channel message
- [ ] Convert certain embeds to use component v2
- [ ] "Custom locale" to allow overriding specific locale strings without editing language files
- [ ] Proper pytest unit tests (see how other projects do it)
- [ ] pyinstaller or nuitka compiled build, also with an installer
- [ ] Message attachment support (linked attachment to storage channel)

## Acknowledgements

The current release of Modmail (v5) is a complete relicensed rewrite of the original Modmail bot.
Special thanks to the original Modmail dev team (kyb3r, fourjr, Taaku18) for their work,
and to the contributors of the original Modmail bot for their help in making this project possible.
