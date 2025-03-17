# Modmail v5 - WIP, UNSTABLE BUILD

1. Fill in the configs from `config.yaml.example` and rename it to `config.yaml`
2. Install Python 3.13 and pdm, then run `pdm install --prod --no-editable --no-lock -G:speed` to install the dependencies
3. Install database drivers with `pdm install -G DBTYPE` - replace `DBTYPE` with `mongodb` or `sqlite`, only these two are supported at the moment
4. Start the bot with `pdm run python start.py`

Please note that the database structure may change at any time, and database migrations between development versions are not available.
You will need to drop the database when the structure changes.

## Acknowledgements

The current release of Modmail (v5) is a complete rewrite of the original Modmail bot.
Special thanks to the original Modmail team (kyb3r, fourjr, Taaku18) for their work,
and to the contributors of the original Modmail bot for their help in making this project possible.
