"""Locale management for Modmail.

Provides the `python -m modmail.locales` CLI and callable entry points
for use in other code.
"""

from __future__ import annotations

import ast
import logging
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from babel.core import Locale as _BabelLocale
from babel.messages import Catalog, Message, mofile, pofile

__all__ = [
    "LocaleError",
    "add_locale",
    "check_locales",
    "compile_locales",
    "create_custom_locale",
    "ensure_compiled",
    "extract_locales",
]

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_ROOT = PROJECT_ROOT / "modmail"
LOCALES_DIR = SOURCE_ROOT / "locales"
DOMAIN = "messages"

_CONTEXT_FUNCS = frozenset({"_c", "cgettext", "upgettext", "_cn", "unpgettext"})
_PLURAL_FUNCS = frozenset({"_n", "ngettext", "_cn", "unpgettext"})
_ALL_FUNCS = _CONTEXT_FUNCS | _PLURAL_FUNCS | frozenset({"_", "gettext"})

_FORMAT_RE = re.compile(r"\{\s*([a-zA-Z0-9_-]+)\s*\}")

_INTERNAL_MSGIDS = frozenset({"internal.blank", "internal.error"})

type _Extracted = dict[str | tuple[str, str], dict[str, Any]]
type _Directives = dict[str, list[str]]
type _SeeSources = dict[str, list[tuple[str, str, int]]]


class LocaleError(Exception):
    """Raised when a locale operation cannot complete."""


def _to_babel_locale(locale: str) -> str:
    """Convert BCP-47 `en-US` to babel underscore form `en_US`.

    A trailing `-custom` suffix becomes `@custom` so
    `en-US-custom` produces `en_US@custom` and
    `en-custom` produces `en@custom`.

    Returns:
        Babel locale string with underscore and optional `@modifier`.
    """
    suffix = "@custom" if locale.endswith("-custom") else ""
    return locale.removesuffix("-custom").replace("-", "_") + suffix


def _read_pyproject() -> dict[str, str]:
    """Return `{name, version, author, email, license}` from pyproject.toml.

    Returns:
        Dict with project metadata.

    Raises:
        FileNotFoundError: If pyproject.toml is missing.
        KeyError: If a required key is missing from the `[project]` table.
        IndexError: If `[project].authors` is empty.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    project: dict[str, Any] = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())["project"]
    return {
        "name": str(project["name"]),
        "version": str(project["version"]),
        "author": str(project["authors"][0]["name"]),
        "email": str(project["authors"][0]["email"]),
        "license": str(lic if isinstance(lic := project["license"], str) else lic["text"]),
    }


def _resolve_constant(node: ast.expr) -> object | None:
    """Resolve an AST expression to a compile-time constant.

    Handles plain / raw / unicode / bytes (decoded UTF-8) literals and
    all-constant f-strings / t-strings.

    Returns:
        The resolved value, or `None` when unresolvable.
    """
    match node:
        case ast.Constant(value=bytes(v)):
            return v.decode()
        case ast.Constant(value=v):
            return v
        case ast.JoinedStr() | ast.TemplateStr():
            parts: list[str] = []
            for val in node.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    parts.append(val.value)
                else:
                    return None
            return "".join(parts)
        case _:
            return None


def _extract_comments(source: str, call_lineno: int) -> list[str]:
    """Scan comments above *call_lineno* for `@param` / `@info` / `@see` directives.

    AST line numbers are 1-based. `splitlines()` is 0-based, so the line
    immediately before the call is at index `call_lineno - 2`.

    Returns:
        Directive strings in source order.
    """
    lines = source.splitlines()
    comments: list[str] = []
    for i in range(call_lineno - 2, -1, -1):
        stripped = lines[i].strip()
        if not stripped or not stripped.startswith("#"):
            break
        body = stripped[1:].strip()
        if body.startswith(("@param", "@info", "@see")):
            comments.append(body)
    comments.reverse()
    return comments


def _discover_locales() -> list[str]:
    """Locale directories under `LOCALES_DIR`, or `['en-US']`.

    Returns:
        List of locale directory names.
    """
    if not LOCALES_DIR.is_dir():
        return ["en-US"]
    found = sorted(d.name for d in LOCALES_DIR.iterdir() if d.is_dir() and (d / "LC_MESSAGES").is_dir())
    return found or ["en-US"]


def _iter_locales(locale: str | None = None) -> list[str]:
    """Return locale identifiers to process -- explicit *locale* or auto-discovered.

    Returns:
        List of locale identifiers.
    """
    return [locale] if locale else _discover_locales()


def _create_locale(locale: str) -> str:
    """Validate *locale* as BCP-47 and create its directory tree.

    Returns:
        The canonical locale tag.

    Raises:
        LocaleError: On invalid input or existing directory.
    """
    try:
        parsed = _BabelLocale.parse(locale, sep="-")
    except ValueError, TypeError, AttributeError:
        raise LocaleError(f"Invalid BCP-47 locale: {locale!r}") from None

    canonical = f"{parsed.language}-{parsed.territory}" if parsed.territory else parsed.language
    locale_dir = LOCALES_DIR / canonical
    if locale_dir.exists():
        raise LocaleError(f"Locale directory already exists: {locale_dir}")

    (locale_dir / "LC_MESSAGES").mkdir(parents=True, exist_ok=True)
    logger.info("Created locale directory: %s", locale_dir.relative_to(LOCALES_DIR))
    return canonical


def create_custom_locale(base: str = "en-US") -> str:
    """Create a custom locale override based on *base*.

    Only one `*-custom` directory may exist.  The custom locale is
    loaded at startup by [`Translator.load_bundles`][] and checked before
    every translation lookup.

    Args:
        base: BCP-47 locale to inherit plural rules and formatting from.

    Returns:
        The custom directory name (e.g. `"en-US-custom"`).

    Raises:
        LocaleError: If *base* is invalid or a custom locale already exists.
    """
    try:
        _BabelLocale.parse(base, sep="-")
    except ValueError, TypeError, AttributeError:
        raise LocaleError(f"Invalid base locale for custom: {base!r}") from None

    for d in LOCALES_DIR.iterdir():
        if d.is_dir() and d.name.endswith("-custom"):
            raise LocaleError(f"A custom locale already exists: {d.name}")

    dirname = f"{base}-custom"
    locale_dir = LOCALES_DIR / dirname
    (locale_dir / "LC_MESSAGES").mkdir(parents=True, exist_ok=True)
    logger.info("Created custom locale directory: %s", locale_dir.relative_to(LOCALES_DIR))

    meta = _read_pyproject()
    extracted = _SourceScanner().scan()
    logger.info("Scanned sources — %d unique msgids found.", len(extracted))
    eng = _CatalogEngine(dirname, meta)
    catalog = eng.build(extracted)
    eng.write_po(catalog)
    eng.write_mo(catalog)
    s = _catalog_stats(catalog)
    logger.info(
        "[%s] Generated PO and MO  (%d total · %d translated · %d untranslated · %d fuzzy · %d obsolete)",
        dirname,
        s["total"],
        s["translated"],
        s["untranslated"],
        s["fuzzy"],
        s["obsolete"],
    )
    return dirname


def _catalog_stats(catalog: Catalog) -> dict[str, int]:
    """Return translation stats for a catalog.

    Returns:
        A dict with *total*, *translated*, *untranslated*, *fuzzy*,
        and *obsolete* counts.
    """
    translated = untranslated = fuzzy = 0
    for m in catalog:
        if m.string and not (isinstance(m.string, (list, tuple)) and all(not s for s in m.string)):
            translated += 1
        else:
            untranslated += 1
        fuzzy += m.fuzzy
    return {
        "total": translated + untranslated,
        "translated": translated,
        "untranslated": untranslated,
        "fuzzy": fuzzy,
        "obsolete": len(catalog.obsolete),
    }


def _log_undocumented_params(params: _Directives, catalog: Catalog) -> bool:
    """Log warnings for msgstr entries whose `{name}` placeholders lack `@param` directives.

    Returns:
        `True` when all placeholders are documented, `False` otherwise.
    """
    clean = True
    for m in catalog:
        if not m.string:
            continue
        raw_str = m.string
        if isinstance(raw_str, str):
            combined = raw_str
        else:
            combined = " ".join(s for s in raw_str if s)
        if not combined:
            continue
        placeholders = set(_FORMAT_RE.findall(combined))
        if not placeholders:
            continue
        raw_id = m.id
        if isinstance(raw_id, str):
            mid = raw_id
        elif isinstance(raw_id, tuple):
            mid = raw_id[0]
        else:
            continue
        param_lines = [c for c in params.get(mid, []) if c.startswith("@param")]
        param_names = {c.removeprefix("@param").strip().split(":", 1)[0].strip() for c in param_lines}
        for ph in sorted(placeholders):
            if ph not in param_names:
                logger.warning(
                    "msgstr for %r has format placeholder {%s} without @param directive",
                    mid,
                    ph,
                )
                clean = False
    return clean


def ensure_compiled() -> None:
    """Compile every locale's `.mo` from its `.po` when missing or outdated.

    Called during bot startup so that cloning the repo and running
    directly works without a manual compile step.
    """
    for loc in _discover_locales():
        po_path = LOCALES_DIR / loc / "LC_MESSAGES" / f"{DOMAIN}.po"
        mo_path = LOCALES_DIR / loc / "LC_MESSAGES" / f"{DOMAIN}.mo"
        if not po_path.is_file():
            continue
        if mo_path.is_file() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
            continue
        with po_path.open("rb") as f:
            catalog = pofile.read_po(f, locale=_to_babel_locale(loc))
        mo_path.parent.mkdir(parents=True, exist_ok=True)
        with mo_path.open("wb") as f:
            mofile.write_mo(f, catalog)
        s = _catalog_stats(catalog)
        logger.info(
            "%s → %s  (%d total · %d translated · %d untranslated · %d fuzzy · %d obsolete)",
            po_path.relative_to(LOCALES_DIR),
            mo_path.relative_to(LOCALES_DIR),
            s["total"],
            s["translated"],
            s["untranslated"],
            s["fuzzy"],
            s["obsolete"],
        )


class _SeeResolver:
    """Resolve `@see target.key` by copying `@param` lines from the target.

    Local params override. Errors are logged with the `file:line` of the
    offending directive.
    """

    def __init__(
        self,
        all_params: _Directives,
        see_sources: _SeeSources,
    ) -> None:
        self._params = all_params
        self._see_sources = see_sources

    def resolve(self) -> None:
        for requester, see_list in self._see_sources.items():
            for target, file, line in see_list:
                resolved = self._resolve_one(requester, target, f"{file}:{line}", set())
                if resolved:
                    bucket = self._params.setdefault(requester, [])
                    for entry in resolved:
                        if entry not in bucket:
                            bucket.append(entry)

    def _resolve_one(self, requester: str, target: str, origin: str, visited: set[str]) -> list[str]:
        if target in visited:
            logger.warning("%s: circular @see — %r already in chain (requester %r)", origin, target, requester)
            return []
        if target == requester:
            logger.warning("%s: @see references itself (target %r)", origin, target)
            return []
        if target not in self._params:
            logger.warning("%s: @see references unknown msgid %r (from %r)", origin, target, requester)
            return []

        visited.add(target)
        own = {
            c.split(":")[0].removeprefix("@param ").strip()
            for c in self._params.get(requester, [])
            if c.startswith("@param")
        }
        result: list[str] = []
        for c in self._params.get(target, []):
            if c.startswith("@see "):
                nested = c[5:].strip()
                result.extend(self._resolve_one(requester, nested, f"{origin} → @see {nested}", visited))
            elif c.startswith("@param"):
                name = c.split(":")[0].removeprefix("@param ").strip()
                if name not in own:
                    result.append(c)
        return result


class _SourceScanner:
    """Walk `.py` files and collect every translation call site."""

    def scan(self) -> _Extracted:
        """Walk source files and extract translation entries.

        Returns:
            Dict of extracted translation entries keyed by msgid.
        """
        extracted: _Extracted = {}
        for path in sorted(SOURCE_ROOT.rglob("*.py")):
            if LOCALES_DIR in path.parents or "locales.bak" in str(path):
                continue
            try:
                source = path.read_text(encoding="utf-8")
                relpath = str(path.relative_to(PROJECT_ROOT))
            except OSError:
                continue
            try:
                tree = ast.parse(source, filename=relpath)
            except SyntaxError:
                logger.warning("Skip unparseable file: %s", relpath)
                continue
            for entry in self._visit_file(source, relpath, tree):
                self._merge(extracted, entry)
        return extracted

    @staticmethod
    def _visit_file(source: str, relpath: str, tree: ast.AST) -> list[dict[str, Any]]:
        """Parse a file and collect translation entries.

        Returns:
            List of extracted entry dicts.
        """
        vis = _SourceScanner._Visitor(source, relpath)
        vis.visit(tree)
        return vis.entries

    @staticmethod
    def _merge(extracted: _Extracted, entry: dict[str, Any]) -> None:
        """Merge an entry into the extracted dict, deduplicating."""
        msgid: str = entry["msgid"]
        if msgid.startswith("internal."):
            if msgid not in _INTERNAL_MSGIDS:
                logger.warning(
                    "%s:%d: unknown internal msgid %r",
                    entry["file"],
                    entry["line"],
                    msgid,
                )
            return
        ctx = entry.get("context")
        key: str | tuple[str, str] = (msgid, ctx) if ctx else msgid
        ex = extracted.setdefault(
            key,
            {"func": entry["func"], "files": {}, "msgid": msgid, "context": ctx, "comments": []},
        )
        ex["files"].setdefault(entry["file"], []).append(entry["line"])
        if entry["func"] != ex["func"]:
            logger.warning("Key %r used as both %s and %s", msgid, ex["func"], entry["func"])
        if entry.get("context") and not ex.get("context"):
            ex["context"] = entry["context"]
        for c in entry["comments"]:
            if c not in ex["comments"]:
                ex["comments"].append(c)

    class _Visitor(ast.NodeVisitor):
        def __init__(self, source: str, relpath: str) -> None:
            super().__init__()
            self._source = source
            self._relpath = relpath
            self.entries: list[dict[str, Any]] = []

        def visit_Call(self, node: ast.Call) -> None:
            """Record translation call metadata from an AST node."""
            fid = node.func.id if isinstance(node.func, ast.Name) else None
            if fid not in _ALL_FUNCS:
                self.generic_visit(node)
                return

            has_ctx = fid in _CONTEXT_FUNCS
            min_args = 2 if has_ctx else 1
            if len(node.args) < min_args:
                logger.warning(
                    "%s:%d: %s() needs %d positional arg(s), got %d",
                    self._relpath,
                    node.lineno,
                    fid,
                    min_args,
                    len(node.args),
                )
                self.generic_visit(node)
                return

            ctx: str | None = None
            if has_ctx:
                cv = _resolve_constant(node.args[0])
                if not isinstance(cv, str):
                    logger.warning("%s:%d: %s() context not a string literal", self._relpath, node.lineno, fid)
                    self.generic_visit(node)
                    return
                ctx = cv
                msgid_val = _resolve_constant(node.args[1])
            else:
                msgid_val = _resolve_constant(node.args[0])

            if not isinstance(msgid_val, str):
                logger.warning("%s:%d: %s() msgid not a string literal", self._relpath, node.lineno, fid)
                self.generic_visit(node)
                return

            self.entries.append({
                "func": "ngettext" if fid in _PLURAL_FUNCS else fid,
                "msgid": msgid_val,
                "file": self._relpath,
                "line": node.lineno,
                "context": ctx,
                "comments": _extract_comments(self._source, node.lineno),
            })
            self.generic_visit(node)


def _collect_params(extracted: _Extracted) -> tuple[_Directives, _Directives, _SeeSources]:
    """Collect `@param`, `@info`, and `@see` directives from extracted entries.

    Returns:
        Tuple of `(params, infos, see_sources)`.
    """
    params: _Directives = {}
    infos: _Directives = {}
    sees: _SeeSources = {}

    for entry in extracted.values():
        mid: str = entry["msgid"]
        for c in entry["comments"]:
            if c.startswith("@param"):
                bucket = params.setdefault(mid, [])
                if c not in bucket:
                    bucket.append(c)
            elif c.startswith("@info"):
                bucket = infos.setdefault(mid, [])
                if c not in bucket:
                    bucket.append(c)
            elif c.startswith("@see "):
                target = c[5:].strip()
                if not target:
                    logger.warning("%s: empty @see for %r", next(iter(entry["files"])), mid)
                    continue
                bucket = params.setdefault(mid, [])
                if c not in bucket:
                    bucket.append(c)
                for fp, lines in entry["files"].items():
                    sees.setdefault(mid, []).append((target, fp, lines[0] if lines else 0))

        if entry["func"] == "ngettext" and not any(c.startswith("@param count") for c in params.get(mid, [])):
            params.setdefault(mid, []).append("@param count: The number used to select the plural form.")

    return params, infos, sees


class _CatalogEngine:
    """Build, load, merge, and write babel `Catalog` objects for one locale."""

    def __init__(self, locale: str, meta: dict[str, str]) -> None:
        self.locale = locale
        self._meta = meta
        self._babel_locale = _to_babel_locale(locale)

    @property
    def _po_dir(self) -> Path:
        return LOCALES_DIR / self.locale / "LC_MESSAGES"

    @property
    def po_path(self) -> Path:
        return self._po_dir / f"{DOMAIN}.po"

    @property
    def mo_path(self) -> Path:
        return self._po_dir / f"{DOMAIN}.mo"

    def build(self, extracted: _Extracted) -> Catalog:
        """Build a babel Catalog from extracted entries.

        Returns:
            A populated `Catalog` with header metadata and locations.
        """
        header = (
            f"# {self._meta['name']} localization\n"
            f"# Copyright (C) {datetime.now(UTC).year} {self._meta['author']}\n"
            f"# {self._meta['license']}"
        )
        catalog = Catalog(
            locale=self._babel_locale,
            header_comment=header,
            project=self._meta["name"],
            version=self._meta["version"],
            copyright_holder=self._meta["author"],
            msgid_bugs_address=self._meta["email"],
            last_translator="",
        )
        catalog.revision_date = datetime.now(UTC)

        all_params, all_infos, see_sources = _collect_params(extracted)
        _SeeResolver(all_params, see_sources).resolve()

        for entry in extracted.values():
            msgid = entry["msgid"]
            locs = [(fp, ln) for fp, lines in sorted(entry["files"].items()) for ln in sorted(lines)]
            auto = self._build_comments(msgid, all_params, all_infos)
            ctx = entry.get("context")
            plural = entry["func"] == "ngettext"

            msg = Message(
                id=(msgid, msgid + ".plural") if plural else msgid,
                string=[""] * catalog.num_plurals if plural else "",
                locations=locs,
                auto_comments=auto,
                context=ctx,
            )
            if _FORMAT_RE.search(msgid):
                msg.flags.add("python-brace-format")
            catalog[msg.id] = msg

        return catalog

    def load(self) -> Catalog | None:
        """Load an existing PO file.

        Returns:
            The loaded `Catalog`, or `None` if the file does not exist.
        """
        if not self.po_path.is_file():
            return None
        with self.po_path.open("rb") as f:
            return pofile.read_po(f, locale=self._babel_locale)

    @staticmethod
    def merge(existing: Catalog | None, template: Catalog) -> Catalog:
        """Merge an existing catalog into a template catalog.

        Returns:
            The merged `Catalog`.
        """
        if existing is None:
            return template
        existing.update(template)
        return existing

    def write_po(self, catalog: Catalog) -> Path:
        """Write the catalog to a PO file.

        Returns:
            The path to the written PO file.
        """
        self._po_dir.mkdir(parents=True, exist_ok=True)
        with self.po_path.open("wb") as f:
            pofile.write_po(f, catalog, sort_output=True, include_previous=True)
        self._normalize_locations()
        if self.locale == "en-US":
            self._inject_crowdin_header()
        return self.po_path

    def _inject_crowdin_header(self) -> None:
        """Inject `X-Crowdin-SourceKey: msgstr` into the en-US PO header."""
        content = self.po_path.read_text(encoding="utf-8")
        if "X-Crowdin-SourceKey" in content:
            return

        # babel does not provide a way to inject custom header fields, so we do it manually.
        # Find the header stanza and inject the custom field below a known marker.
        header_start = content.find('\nmsgid ""\nmsgstr ""\n')
        if header_start == -1:
            logger.warning(
                "[%s] Could not inject X-Crowdin-SourceKey — header stanza not found.",
                self.locale,
            )
            return
        header_body = header_start + len('\nmsgid ""\nmsgstr ""\n')
        next_msgid = content.find('\nmsgid "', header_body)
        if next_msgid == -1:
            next_msgid = len(content)

        marker = '"Content-Transfer-Encoding: 8bit\\n"\n'
        if marker not in content[header_body:next_msgid]:
            logger.warning(
                "[%s] Could not inject X-Crowdin-SourceKey — header marker not found.",
                self.locale,
            )
            return

        injection = '"X-Crowdin-SourceKey: msgstr\\n"\n'
        start = content.index(marker, header_body, next_msgid)
        content = content[:start] + marker + injection + content[start + len(marker) :]
        self.po_path.write_text(content, encoding="utf-8")

    def _normalize_locations(self) -> None:
        """Combine consecutive `#:` lines into one per entry."""
        content = self.po_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        result: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#:"):
                refs = [line[2:].strip()]
                j = i + 1
                while j < len(lines) and lines[j].startswith("#:"):
                    refs.append(lines[j][2:].strip())
                    j += 1
                result.append("#: " + " ".join(refs) + "\n")
                i = j
            else:
                result.append(line)
                i += 1
        text = "".join(result).rstrip("\n") + "\n"
        self.po_path.write_text(text, encoding="utf-8")

    def write_mo(self, catalog: Catalog) -> Path:
        """Write the catalog to a MO file.

        Returns:
            The path to the written MO file.
        """
        self._po_dir.mkdir(parents=True, exist_ok=True)
        with self.mo_path.open("wb") as f:
            mofile.write_mo(f, catalog)
        return self.mo_path

    @staticmethod
    def _build_comments(msgid: str, params: _Directives, infos: _Directives) -> list[str]:
        """Build auto_comments from @info and @param directives.

        Returns:
            List of auto-comment strings.
        """
        result: list[str] = []
        for info in infos.get(msgid, []):
            text = info.removeprefix("@info").strip().lstrip(":").strip()
            if text:
                result.append(f"Info: {text}")

        param_lines = [c for c in params.get(msgid, []) if c.startswith("@param")]
        if param_lines:
            seen: set[str] = set()
            deduped: list[str] = []
            for pc in param_lines:
                name = pc.removeprefix("@param").strip().split(":", 1)[0].strip()
                if name in seen:
                    continue
                seen.add(name)
                deduped.append(pc)

            names: list[str] = []
            details: list[str] = []
            for pc in deduped:
                parts = pc.removeprefix("@param").strip().split(":", 1)
                n = parts[0].strip()
                d = parts[1].strip() if len(parts) > 1 else ""
                names.append(n)
                details.append(f"  {n}: {d}" if d else f"  {n}")
            result.insert(0, f"Parameters: {', '.join(names)}")
            result.extend(details)
        return result


def _check_locale(extracted: _Extracted, engine: _CatalogEngine) -> bool:
    """Return `True` when the locale's PO covers every extracted key."""
    existing = engine.load()
    if existing is None:
        logger.info("[%s] No PO file — %d keys missing.", engine.locale, len(extracted))
        return False

    s = _catalog_stats(existing)
    logger.info(
        "[%s] %s  (%d · +%d · -%d · !%d · x%d)",
        engine.locale,
        engine.po_path.relative_to(LOCALES_DIR),
        s["total"],
        s["translated"],
        s["untranslated"],
        s["fuzzy"],
        s["obsolete"],
    )

    clean = True
    for entry in extracted.values():
        msgid: str = entry["msgid"]
        ctx = entry.get("context")
        lookup: str | tuple[str, str] = (msgid, msgid + ".plural") if entry["func"] == "ngettext" else msgid
        found = any(getattr(m, "context", None) == ctx and m.id == lookup for m in existing)
        if not found:
            ctx_suffix = f" (context: {ctx})" if ctx else ""
            logger.info("[%s] Missing: %s%s", engine.locale, msgid, ctx_suffix)
            clean = False

    all_params, _all_infos, see_sources = _collect_params(extracted)
    _SeeResolver(all_params, see_sources).resolve()
    if not _log_undocumented_params(all_params, existing):
        clean = False
    return clean


def extract_locales(locale: str | None = None) -> None:
    """Scan sources, update PO files, and compile MO files.

    Args:
        locale: Single BCP-47 locale to process, or `None` for all configured.
    """
    meta = _read_pyproject()
    extracted = _SourceScanner().scan()
    logger.info("Scanned sources — %d unique msgids found.", len(extracted))
    for loc in _iter_locales(locale):
        eng = _CatalogEngine(loc, meta)
        result = _CatalogEngine.merge(eng.load(), eng.build(extracted))
        po = eng.write_po(result)
        mo = eng.write_mo(result)
        s = _catalog_stats(result)
        logger.info(
            "[%s] %s  %s  (%d total · %d translated · %d untranslated · %d fuzzy · %d obsolete)",
            loc,
            po.relative_to(LOCALES_DIR),
            mo.relative_to(LOCALES_DIR),
            s["total"],
            s["translated"],
            s["untranslated"],
            s["fuzzy"],
            s["obsolete"],
        )


def check_locales(locale: str | None = None) -> bool:
    """Scan sources and report missing translation keys.

    Args:
        locale: Single BCP-47 locale to check, or `None` for all configured.

    Returns:
        `True` when all locales are clean, `False` otherwise.
    """
    meta = _read_pyproject()
    extracted = _SourceScanner().scan()
    logger.info("Scanned sources — %d unique msgids found.", len(extracted))
    locales = _iter_locales(locale)
    failures = 0
    for loc in locales:
        if not _check_locale(extracted, _CatalogEngine(loc, meta)):
            failures += 1

    if failures:
        logger.info("%d of %d locale(s) have missing keys.", failures, len(locales))
        return False
    logger.info("All %d locale(s) are complete.", len(locales))
    return True


def compile_locales(locale: str | None = None) -> None:
    """Compile existing PO files to MO for one or all locales.

    Args:
        locale: Single BCP-47 locale to compile, or `None` for all configured.
    """
    meta = _read_pyproject()
    for loc in _iter_locales(locale):
        eng = _CatalogEngine(loc, meta)
        if (existing := eng.load()) is None:
            logger.info("[%s] No PO file — skipping.", loc)
            continue
        s = _catalog_stats(existing)
        mo = eng.write_mo(existing)
        logger.info(
            "[%s] %s  (%d total · %d translated · %d untranslated · %d fuzzy · %d obsolete)",
            loc,
            mo.relative_to(LOCALES_DIR),
            s["total"],
            s["translated"],
            s["untranslated"],
            s["fuzzy"],
            s["obsolete"],
        )


def add_locale(locale: str) -> str:
    """Create a new locale directory, scan sources, and generate PO+MO.

    Args:
        locale: BCP-47 locale tag (e.g. `"de"`, `"de-DE"`).

    Returns:
        The canonical locale tag that was created.
    """
    canonical = _create_locale(locale)
    meta = _read_pyproject()
    extracted = _SourceScanner().scan()
    logger.info("Scanned sources — %d unique msgids found.", len(extracted))
    eng = _CatalogEngine(canonical, meta)
    catalog = eng.build(extracted)
    po = eng.write_po(catalog)
    mo = eng.write_mo(catalog)
    s = _catalog_stats(catalog)
    logger.info(
        "[%s] %s  %s  (%d total · %d translated · %d untranslated · %d fuzzy · %d obsolete)",
        canonical,
        po.relative_to(LOCALES_DIR),
        mo.relative_to(LOCALES_DIR),
        s["total"],
        s["translated"],
        s["untranslated"],
        s["fuzzy"],
        s["obsolete"],
    )
    return canonical
