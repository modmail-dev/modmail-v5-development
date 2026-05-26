"""CLI entry point for locale management.

Usage:
    python -m modmail.locales extract  [-l LANG]   Update PO files from source
    python -m modmail.locales check    [-l LANG]   Report issues (no writes)
    python -m modmail.locales compile  [-l LANG]   Compile PO to MO
    python -m modmail.locales add      LANG         Create a new locale
    python -m modmail.locales custom   [BASE]       Create a custom locale override
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING, Any

from modmail.locales import (
    LocaleError,
    add_locale,
    check_locales,
    compile_locales,
    create_custom_locale,
    extract_locales,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def _add_subparser(
    sub: Any,
    name: str,
    help_text: str,
    func: Callable[[argparse.Namespace], None],
) -> None:
    """Register a subcommand with optional --locale flag."""
    p = sub.add_parser(name, help=help_text)
    p.add_argument("-l", "--locale", help="Single locale (default: all configured)")
    p.set_defaults(func=func)


def _wrap_extract(args: argparse.Namespace) -> None:
    """Run extract_locales with parsed args."""
    extract_locales(args.locale)


def _wrap_check(args: argparse.Namespace) -> None:
    """Run check_locales and exit with status 1 on failure."""
    if not check_locales(args.locale):
        sys.exit(1)


def _wrap_compile(args: argparse.Namespace) -> None:
    """Run compile_locales with parsed args."""
    compile_locales(args.locale)


def _wrap_add(args: argparse.Namespace) -> None:
    """Run add_locale with parsed args."""
    add_locale(args.locale)


def _wrap_custom(args: argparse.Namespace) -> None:
    """Run create_custom_locale with parsed args."""
    create_custom_locale(args.base)


def main(argv: list[str] | None = None) -> None:
    """Entry point for `python -m modmail.locales`.

    Args:
        argv: Command-line arguments (defaults to `sys.argv`).
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

    parser = argparse.ArgumentParser(
        prog="python -m modmail.locales", description="Modmail locale management tool."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    _add_subparser(sub, "extract", "Scan sources -> update PO + compile MO", _wrap_extract)
    _add_subparser(sub, "check", "Scan sources -> report missing keys", _wrap_check)
    _add_subparser(sub, "compile", "Recompile existing PO -> MO", _wrap_compile)

    p = sub.add_parser("add", help="Create a new locale from source scan")
    p.add_argument("locale", help="BCP-47 locale tag (e.g. de, de-DE)")
    p.set_defaults(func=_wrap_add)

    p = sub.add_parser("custom", help="Create a custom locale override")
    p.add_argument("base", nargs="?", default="en-US", help="Base BCP-47 locale (default: en-US)")
    p.set_defaults(func=_wrap_custom)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (LocaleError, FileNotFoundError, KeyError, IndexError, ValueError) as exc:
        logger.error("%s: %s", type(exc).__name__, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
