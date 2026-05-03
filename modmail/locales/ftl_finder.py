#!/usr/bin/env python3
"""FTL string finder utility.

Scans Python source files for every string literal whose value starts with `ftl-`
and compares them against locale FTL files to report missing or unused translations.
Any `ftl-` string in the codebase is matched regardless of calling context —
`ctx.t("ftl-key")`, `_("ftl-key")`, or bare literal assignments all count.

Supported string forms (Python 3.14+):

- Plain and raw strings: `"ftl-key"`, `r"ftl-key"` (same AST node)
- F-strings: `f"ftl-key"` (all-constant) or nested inside `f"... {ctx.t('ftl-key')}"`
- T-strings: `t"ftl-key"` (Python 3.14 template strings, [`ast.TemplateStr`][])
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path


class FTLStringFinder(ast.NodeVisitor):
    """[`ast.NodeVisitor`][] that collects every string literal starting with `ftl-`.

    Handles plain/raw strings, f-strings, and Python 3.14 t-strings. String
    fragments in the *delimiter* parts of interpolated strings are suppressed so
    that partial prefixes like `"ftl-"` inside `f"ftl-{key}"` are not mistaken
    for complete FTL keys. Expressions *inside* interpolations are still recursed
    into, so `f"... {ctx.t('ftl-some-key')}"` is found correctly.
    """

    def __init__(self) -> None:
        """Initialize an empty finder with a zeroed interpolation-depth counter."""
        self.ftl_strings: dict[str, list[tuple[int, int]]] = {}
        """Mapping from FTL message ID to the `(line, col)` positions where it appears."""
        self._in_interp = 0

    def _record(self, key: str, line: int, col: int) -> None:
        self.ftl_strings.setdefault(key, []).append((line, col))

    def visit_Constant(self, node: ast.Constant) -> None:
        """Record plain and raw string constants starting with `ftl-`.

        Skipped when the visitor is currently inside the literal-part of an
        interpolated string (f-string or t-string delimiter), to avoid recording
        partial prefixes such as `"ftl-"` from `f"ftl-{key}"`.

        Args:
            node: The [`ast.Constant`][] node being visited.
        """
        if self._in_interp == 0 and isinstance(node.value, str) and node.value.startswith("ftl-"):
            self._record(node.value, node.lineno, node.col_offset)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Record f-strings that are wholly a static `ftl-` key, or recurse into their expressions.

        If the f-string has no actual interpolations (all parts are [`ast.Constant`][]
        nodes), the concatenated literal value is recorded as a single key. For
        f-strings that do contain expressions, only the expression subtrees are
        visited — the string delimiter fragments are suppressed.

        Args:
            node: The [`ast.JoinedStr`][] node being visited.
        """
        if all(isinstance(v, ast.Constant) for v in node.values):
            full = "".join(
                v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
            if full.startswith("ftl-"):
                self._record(full, node.lineno, node.col_offset)
            return

        # Suppress Constant visits inside string-literal parts; recurse only
        # into FormattedValue (the expression + format_spec parts).
        self._in_interp += 1
        for child in node.values:
            if isinstance(child, ast.FormattedValue):
                self._in_interp -= 1
                self.visit(child)
                self._in_interp += 1
        self._in_interp -= 1

    def visit_TemplateStr(self, node: ast.AST) -> None:
        """Record Python 3.14 t-strings whose literal value starts with `ftl-`.

        Mirrors the logic of [`visit_JoinedStr`][] for `t"..."` template strings.
        On Python versions that do not emit [`ast.TemplateStr`][] nodes this method
        is never invoked, so it degrades safely.

        Args:
            node: The [`ast.TemplateStr`][] node being visited.
        """
        values: list[ast.AST] = getattr(node, "values", [])
        const_parts = [v for v in values if isinstance(v, ast.Constant)]
        interp_parts = [v for v in values if not isinstance(v, ast.Constant)]

        if not interp_parts:
            full = "".join(v.value for v in const_parts if isinstance(v.value, str))
            if full.startswith("ftl-"):
                self._record(full, getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
            return

        self._in_interp += 1
        for child in interp_parts:
            self._in_interp -= 1
            self.visit(child)
            self._in_interp += 1
        self._in_interp -= 1


_FTL_IGNORE = re.compile(r"#\s*ftl\s*:\s*ignore", re.IGNORECASE)


def _ignored_lines(source: str) -> set[int]:
    """Return the set of line numbers carrying an `# ftl: ignore` comment.

    Uses the tokenizer so that comment-like text inside string literals is
    never mistaken for a real directive.

    Args:
        source: Full source text of a Python file.

    Returns:
        Set of 1-based line numbers where an `# ftl: ignore` comment appears.
    """
    lines: set[int] = set()
    try:
        for tok_type, tok_string, tok_start, _, _ in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok_type == tokenize.COMMENT and _FTL_IGNORE.search(tok_string):
                lines.add(tok_start[0])
    except tokenize.TokenError:
        pass
    return lines


def find_ftl_strings_in_file(file_path: Path) -> dict[str, list[tuple[int, int]]]:
    """Return every `ftl-` string literal in `file_path` with its source locations.

    Entries on lines carrying an `# ftl: ignore` comment are excluded.

    Args:
        file_path: Python source file to analyze.

    Returns:
        Mapping from FTL message ID to a list of `(line, col)` tuples where it appears.
        Returns an empty dict if the file cannot be parsed.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        finder = FTLStringFinder()
        finder.visit(tree)
        ignored = _ignored_lines(source)
        return {
            key: [(line, col) for line, col in locs if line not in ignored]
            for key, locs in finder.ftl_strings.items()
            if any(line not in ignored for line, _ in locs)
        }
    except Exception as exc:
        print(f"Error processing {file_path}: {exc}")
        return {}


def scan_directory(directory: Path) -> dict[str, dict[Path, list[tuple[int, int]]]]:
    """Recursively scan `directory` for Python files and collect all `ftl-` strings.

    Args:
        directory: Root directory to walk recursively.

    Returns:
        Mapping from FTL message ID to a per-file dict of `(line, col)` locations.
    """
    result: dict[str, dict[Path, list[tuple[int, int]]]] = {}

    for path in sorted(directory.rglob("*.py")):
        if not path.is_file() or path.resolve() == Path(__file__).resolve():
            continue
        for key, locs in find_ftl_strings_in_file(path).items():
            result.setdefault(key, {})[path] = locs

    return result


def extract_locale_strings(locale_file: Path) -> set[str]:
    """Return the set of `ftl-` message IDs defined in `locale_file`.

    Args:
        locale_file: Path to a Fluent `.ftl` file.

    Returns:
        Set of message IDs (keys) defined at the top level of the file.
        Returns an empty set if the file cannot be read.
    """
    keys: set[str] = set()
    pattern = re.compile(r"^(ftl-[a-zA-Z0-9-]+)\s*=")

    try:
        for line in locale_file.read_text(encoding="utf-8").splitlines():
            m = pattern.match(line.strip())
            if m:
                keys.add(m.group(1))
    except Exception as exc:
        print(f"Error reading locale file {locale_file}: {exc}")

    return keys


def main() -> None:
    """Scan the project for `ftl-` strings and report missing or unused translations.

    Derives the project root from this script's location, scans all Python files,
    then cross-references against every `locales/<lang>/main.ftl` file found.
    """
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    print(f"Scanning Python files in {project_root} for FTL strings...")
    code_strings_with_locations = scan_directory(project_root)
    code_strings = set(code_strings_with_locations)
    print(f"Found {len(code_strings)} unique FTL strings in code.")

    locales_dir = project_root / "locales"
    if not locales_dir.exists():
        print(f"Error: locales directory not found at {locales_dir}")
        return

    for locale_dir in sorted(locales_dir.iterdir()):
        if not locale_dir.is_dir() or locale_dir.name.startswith((".", "_")):
            continue

        locale_name = locale_dir.name
        main_ftl = locale_dir / "main.ftl"

        if not main_ftl.exists():
            print(f"Warning: no main.ftl found for locale {locale_name!r}")
            continue

        print(f"\nAnalyzing locale: {locale_name}")
        locale_strings = extract_locale_strings(main_ftl)

        missing = code_strings - locale_strings
        unused = locale_strings - code_strings

        if missing:
            print(f"\n  Missing in {locale_name}/main.ftl ({len(missing)}):")
            for key in sorted(missing):
                print(f"\n    {key}")
                for file_path, locs in code_strings_with_locations[key].items():
                    rel = file_path.relative_to(project_root)
                    for line, col in locs:
                        print(f"      {rel}:{line}:{col}")
        else:
            print(f"  No missing strings in {locale_name}/main.ftl")

        if unused:
            print(f"\n  Unused in {locale_name}/main.ftl ({len(unused)}):")
            for key in sorted(unused):
                print(f"    {key}")
        else:
            print(f"  No unused strings in {locale_name}/main.ftl")


if __name__ == "__main__":
    main()
