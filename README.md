# Modmail v5 - WIP, UNSTABLE BUILD

1. Fill in the configs from `config.yaml.example` and rename it to `config.yaml`
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run `uv sync --locked --compile-bytecode --no-default-groups --extra speed --extra DBTYPE` to install the dependencies
   - Replace `DBTYPE` with `mongodb` or `sqlite`, only these two are supported at the moment
3. Start the bot with `uv run python start.py`

Please note that the database structure may change at any time, and database migrations between development versions are not available.
You will need to drop the database when the structure changes.

## Acknowledgements

The current release of Modmail (v5) is a complete rewrite of the original Modmail bot.
Special thanks to the original Modmail dev team (kyb3r, fourjr, Taaku18) for their work,
and to the contributors of the original Modmail bot for their help in making this project possible.
