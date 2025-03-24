#!/usr/bin/env python3
"""
Script to find missing FTL strings in locale files.
Displays file locations for each missing string.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


class FTLStringFinder(ast.NodeVisitor):
    """AST visitor that finds all string literals starting with 'ftl-'."""

    def __init__(self):
        self.ftl_strings: dict[str, list[tuple[int, int]]] = {}  # string -> [(line, col)]

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls to catch _("ftl-...") and _(f"ftl-...") patterns."""
        if isinstance(node.func, ast.Name) and node.func.id == "_" and len(node.args) > 0:
            # Handle regular string constant: _("ftl-...")
            if (
                isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.startswith("ftl-")
            ):
                value = node.args[0].value
                locations = self.ftl_strings.get(value, [])
                locations.append((node.args[0].lineno, node.args[0].col_offset))
                self.ftl_strings[value] = locations

            # Handle f-string argument: _(f"ftl-...")
            elif (
                isinstance(node.args[0], ast.JoinedStr)
                and len(node.args[0].values) > 0
                and isinstance(node.args[0].values[0], ast.Constant)
                and isinstance(node.args[0].values[0].value, str)
                and node.args[0].values[0].value.startswith("ftl-")
            ):
                value = node.args[0].values[0].value
                locations = self.ftl_strings.get(value, [])
                locations.append((node.args[0].lineno, node.args[0].col_offset))
                self.ftl_strings[value] = locations

        self.generic_visit(node)


def find_ftl_strings_in_file(file_path: Path) -> dict[str, list[tuple[int, int]]]:
    """Find all ftl strings in a single Python file with their locations."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(file_path))
        finder = FTLStringFinder()
        finder.visit(tree)
        return finder.ftl_strings
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return {}


def scan_directory(directory: Path) -> dict[str, dict[Path, list[tuple[int, int]]]]:
    """
    Recursively scan directory for Python files and find all ftl strings.

    Returns:
        Dict mapping ftl-strings to their locations (file path -> list of (line, col))
    """
    result: dict[str, dict[Path, list[tuple[int, int]]]] = {}

    for path in directory.rglob("*.py"):
        if path.is_file() and path.name != Path(__file__).name:
            strings_in_file = find_ftl_strings_in_file(path)

            for ftl_string, locations in strings_in_file.items():
                if ftl_string not in result:
                    result[ftl_string] = {}
                result[ftl_string][path] = locations

    return result


def extract_locale_strings(locale_file: Path) -> set[str]:
    """Extract all ftl- keys from a locale file."""
    locale_strings: set[str] = set()
    pattern = re.compile(r"^(ftl-[a-zA-Z0-9-]+)\s*=")

    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            for line in f:
                match = pattern.match(line.strip())
                if match:
                    locale_strings.add(match.group(1))
    except Exception as e:
        print(f"Error reading locale file {locale_file}: {e}")

    return locale_strings


def main():
    # Use the script's location to determine the project root
    script_path = Path(__file__).absolute()
    project_root = script_path.parent.parent

    print(f"Scanning Python files in {project_root} for FTL strings...")
    code_strings_with_locations = scan_directory(project_root)
    code_strings = set(code_strings_with_locations.keys())
    print(f"Found {len(code_strings)} unique FTL strings in code.")

    # Find locale files
    locales_dir = project_root / "locales"
    if not locales_dir.exists():
        print(f"Error: Locales directory not found at {locales_dir}")
        return

    # Process each locale
    for locale_dir in locales_dir.iterdir():
        if not locale_dir.is_dir():
            continue

        locale_name = locale_dir.name
        main_ftl = locale_dir / "main.ftl"

        if not main_ftl.exists():
            print(f"Warning: No main.ftl found for locale {locale_name}")
            continue

        print(f"\nAnalyzing locale: {locale_name}")
        locale_strings = extract_locale_strings(main_ftl)

        # Find missing strings
        missing_strings = code_strings - locale_strings
        # Find unused strings
        unused_strings = locale_strings - code_strings

        if missing_strings:
            print(f"\nMissing FTL strings in {locale_name}/main.ftl ({len(missing_strings)}):")
            for string in sorted(missing_strings):
                print(f"\n  {string}")
                print(f"    Found in:")
                for file_path, locations in code_strings_with_locations[string].items():
                    rel_path = file_path.relative_to(project_root)
                    for line, col in locations:
                        print(f"      {rel_path}:{line}:{col}")
        else:
            print(f"No missing FTL strings in {locale_name}/main.ftl")

        if unused_strings:
            print(f"\nUnused FTL strings in {locale_name}/main.ftl ({len(unused_strings)}):")
            for string in sorted(unused_strings):
                print(f"  {string}")
        else:
            print(f"No unused FTL strings in {locale_name}/main.ftl")


if __name__ == "__main__":
    main()
