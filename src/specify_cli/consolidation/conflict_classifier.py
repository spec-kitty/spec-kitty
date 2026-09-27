"""Conflict classifier for stale-lane auto-rebase.

Encodes the rule set defined in
``docs/adr/3.x/2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md``
as pure functions returning :class:`ConflictClassification`.

Rules (in evaluation order):

1. **R-PYPROJECT-DEPS-UNION** — additive ``[project.dependencies]`` /
   ``[project.optional-dependencies.*]`` / ``[dependency-groups.*]`` array merges.
2. **R-INIT-IMPORTS-UNION** — additive ``__init__.py`` import-block merges.
3. **R-URLS-LIST-UNION** — additive merges of list constants in ``urls.py`` and
   ``_URLS`` / ``URL_PATTERNS`` shaped constants.
4. **R-UVLOCK-REGENERATE** — special sentinel for ``uv.lock`` (orchestrator
   regenerates rather than merges).
5. **R-DEFAULT-MANUAL** — fail-safe default (NFR-005).

Every rule body is wrapped in ``try/except`` so any unexpected failure
defaults to :class:`Manual` (NFR-005, invariant 2).

This module is pure: no I/O, no subprocess, no globals. The orchestrator in
:mod:`specify_cli.lanes.auto_rebase` is responsible for writing merged text
to disk and for invoking external tools like ``ruff`` and ``uv lock``.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Auto",
    "ClassifierRule",
    "ConflictClassification",
    "Manual",
    "RULES",
    "Resolution",
    "RULE_ID_UVLOCK",
    "classify",
    "r_default_manual",
    "r_init_imports_union",
    "r_pyproject_deps_union",
    "r_urls_list_union",
    "r_uvlock_regenerate",
]


# ---------------------------------------------------------------------------
# Data classes — match kitty-specs/.../data-model.md §3
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Auto:
    """Auto-resolve: return the merged text. The classifier emits this."""

    merged_text: str
    rule_id: str  # which classifier rule produced this; for audit log


@dataclass(frozen=True)
class Manual:
    """Halt and surface to operator. Default for any unmatched pattern."""

    reason: str


Resolution = Auto | Manual


@dataclass(frozen=True)
class ConflictClassification:
    """Output of the file-pattern classifier for a single conflict region."""

    file_path: Path
    hunk_text: str
    resolution: Resolution


# Rule identifiers (string constants — also stamped into Auto.rule_id /
# Manual.reason for audit-log searchability).
RULE_ID_PYPROJECT_DEPS = "R-PYPROJECT-DEPS-UNION"
RULE_ID_INIT_IMPORTS = "R-INIT-IMPORTS-UNION"
RULE_ID_URLS_LIST = "R-URLS-LIST-UNION"
RULE_ID_UVLOCK = "R-UVLOCK-REGENERATE"
RULE_ID_DEFAULT_MANUAL = "R-DEFAULT-MANUAL"


# Type alias for a rule body.
ClassifierRule = Callable[[Path, str], "ConflictClassification | None"]


# ---------------------------------------------------------------------------
# Conflict-marker parsing helpers
# ---------------------------------------------------------------------------


_RE_OURS_HEADER = re.compile(r"^<{7}[^\n]*\n", re.MULTILINE)
_RE_BASE_HEADER = re.compile(r"^\|{7}[^\n]*\n", re.MULTILINE)
_RE_SEP = re.compile(r"^={7}\s*\n", re.MULTILINE)
_RE_THEIRS_HEADER = re.compile(r"^>{7}[^\n]*\n", re.MULTILINE)


def _split_conflict_region(hunk_text: str) -> tuple[str, str] | None:
    """Return ``(ours_text, theirs_text)`` from a hunk containing one
    conflict region, else ``None``.

    Supports both 2-way (``<<<<< / ===== / >>>>>``) and 3-way diff3
    (``<<<<< / |||||| / ===== / >>>>>``) styles. The base (diff3) side, when
    present, is dropped — rules consume only the two endpoint sides.
    """
    ours_m = _RE_OURS_HEADER.search(hunk_text)
    if ours_m is None:
        return None
    sep_m = _RE_SEP.search(hunk_text, ours_m.end())
    theirs_m = _RE_THEIRS_HEADER.search(hunk_text, sep_m.end() if sep_m else 0)
    if sep_m is None or theirs_m is None:
        return None

    # The diff3 base header (||||||) may appear between ours and ===.
    base_m = _RE_BASE_HEADER.search(hunk_text, ours_m.end())
    ours = (
        hunk_text[ours_m.end() : base_m.start()]
        if base_m is not None and base_m.start() < sep_m.start()
        else hunk_text[ours_m.end() : sep_m.start()]
    )
    theirs = hunk_text[sep_m.end() : theirs_m.start()]
    return ours, theirs


def _strip_trailing_newline(text: str) -> str:
    return text[:-1] if text.endswith("\n") else text


# ---------------------------------------------------------------------------
# Rule 1: R-PYPROJECT-DEPS-UNION
# ---------------------------------------------------------------------------


_RE_DEP_PKG = re.compile(r'^\s*"([^"<>=!~\s]+)')


def _parse_dep_lines(block: str) -> list[tuple[str, str]] | None:
    """Parse a block of dependency lines into ``[(package_name, raw_line), ...]``.

    Returns ``None`` if any line is not a recognizable dependency entry. Comment
    lines and blank lines are skipped (preserved on output positionally is not
    a requirement — the rule emits a normalized union).
    """
    parsed: list[tuple[str, str]] = []
    for raw in block.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            # Allow blank lines and comments; do not record them.
            continue
        if not stripped.startswith('"') and not stripped.startswith("'"):
            return None
        m = _RE_DEP_PKG.match(raw)
        if m is None:
            return None
        # Normalize trailing comma so deduplication is stable.
        line = raw.rstrip()
        if not line.endswith(","):
            line = line + ","
        parsed.append((m.group(1).lower(), line))
    return parsed


def _is_sorted_alpha(entries: list[tuple[str, str]]) -> bool:
    names = [name for name, _ in entries]
    return names == sorted(names)


def r_pyproject_deps_union(
    file_path: Path, hunk_text: str
) -> ConflictClassification | None:
    """Match additive merges on ``pyproject.toml`` dependency-array regions.

    Returns ``None`` if the rule does not apply (caller should try the next
    rule). Returns :class:`ConflictClassification` with :class:`Auto` on a
    successful additive merge and :class:`Manual` on a same-package version
    drift.
    """
    try:
        if file_path.name != "pyproject.toml":
            return None
        split = _split_conflict_region(hunk_text)
        if split is None:
            return None
        ours, theirs = split

        ours_entries = _parse_dep_lines(ours)
        theirs_entries = _parse_dep_lines(theirs)
        if ours_entries is None or theirs_entries is None:
            return None  # not a recognizable dep block — let later rules try

        # Detect same-package version drift: same package name appears on
        # both sides but the raw line differs.
        ours_by_name = dict(ours_entries)
        theirs_by_name = dict(theirs_entries)
        for name in ours_by_name.keys() & theirs_by_name.keys():
            if ours_by_name[name].strip() != theirs_by_name[name].strip():
                return ConflictClassification(
                    file_path=file_path,
                    hunk_text=hunk_text,
                    resolution=Manual(
                        reason=(
                            f"{RULE_ID_PYPROJECT_DEPS}: same-package version "
                            f"drift on '{name}' — semantic conflict"
                        )
                    ),
                )

        # Union: dedup by lowercase package name.
        merged: dict[str, str] = {}
        for name, line in ours_entries:
            merged.setdefault(name, line)
        for name, line in theirs_entries:
            merged.setdefault(name, line)

        # Choose sort convention: if the ours side is alphabetically sorted,
        # sort the union; otherwise insertion order (ours then theirs-new).
        ordered = (
            sorted(merged.items(), key=lambda kv: kv[0])
            if _is_sorted_alpha(ours_entries)
            else list(merged.items())
        )

        # Preserve leading indentation of the first non-empty ours line.
        leading_indent = ""
        for raw in ours.splitlines():
            if raw.strip():
                leading_indent = raw[: len(raw) - len(raw.lstrip())]
                break

        merged_lines: list[str] = []
        for _, line in ordered:
            stripped = line.lstrip()
            merged_lines.append(leading_indent + stripped)
        merged_text = "\n".join(merged_lines) + "\n"

        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Auto(merged_text=merged_text, rule_id=RULE_ID_PYPROJECT_DEPS),
        )
    except Exception as exc:  # NFR-005: any rule exception → Manual
        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Manual(
                reason=f"{RULE_ID_PYPROJECT_DEPS}: rule raised: {exc!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Rule 2: R-INIT-IMPORTS-UNION
# ---------------------------------------------------------------------------


# Common identifier-list pattern (target after ``import`` or ``from x import``).
# Allows dots for dotted module imports; the trailing ``\s*$`` anchors the line.
_IDENT_LIST = r"[A-Za-z_][\w.,\s]*"

_RE_IMPORT_TARGET = re.compile(
    rf"""
    ^\s*
    (?:
        from\s+\S+\s+import\s+(?P<from_target>{_IDENT_LIST})
        |
        import\s+(?P<imp_target>{_IDENT_LIST})
    )
    \s*$
    """,
    re.VERBOSE,
)


def _parse_import_lines(block: str) -> list[tuple[str, str]] | None:
    """Parse import lines. Returns ``[(canonical_key, raw_line), ...]`` or
    ``None`` if any non-blank, non-comment line is not an import statement.

    ``canonical_key`` is a lowercase target identifier used for dedup and
    rename detection.
    """
    parsed: list[tuple[str, str]] = []
    for raw in block.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _RE_IMPORT_TARGET.match(raw)
        if m is None:
            return None
        # Normalize key: lowercased module/symbol so renames are detected.
        parsed.append((stripped.lower(), raw.rstrip()))
    return parsed


def _extract_module(raw: str) -> str | None:
    """Return the ``X`` from ``from X import Y`` (or ``X`` from ``import X``)."""
    m = re.match(r"\s*from\s+(\S+)\s+import", raw)
    if m:
        return m.group(1)
    m = re.match(r"\s*import\s+(\S+)", raw)
    if m:
        return m.group(1).split(",")[0].strip()
    return None


def _detect_import_rename(
    ours_entries: list[tuple[str, str]],
    theirs_entries: list[tuple[str, str]],
) -> str | None:
    """Return the module name modified on both sides, or None."""
    ours_by_mod: dict[str, str] = {}
    for _key, raw in ours_entries:
        mod = _extract_module(raw)
        if mod is not None:
            ours_by_mod.setdefault(mod, raw.strip())
    for _key, raw in theirs_entries:
        mod = _extract_module(raw)
        if mod is None:
            continue
        other = ours_by_mod.get(mod)
        if other is not None and other != raw.strip():
            return mod
    return None


def r_init_imports_union(
    file_path: Path, hunk_text: str
) -> ConflictClassification | None:
    """Match additive merges on ``__init__.py`` import blocks."""
    try:
        if file_path.name != "__init__.py":
            return None
        split = _split_conflict_region(hunk_text)
        if split is None:
            return None
        ours, theirs = split

        ours_entries = _parse_import_lines(ours)
        theirs_entries = _parse_import_lines(theirs)
        if ours_entries is None or theirs_entries is None:
            return None

        renamed_mod = _detect_import_rename(ours_entries, theirs_entries)
        if renamed_mod is not None:
            return ConflictClassification(
                file_path=file_path,
                hunk_text=hunk_text,
                resolution=Manual(
                    reason=(
                        f"{RULE_ID_INIT_IMPORTS}: import statement modified "
                        f"for module '{renamed_mod}' — semantic conflict"
                    )
                ),
            )

        merged: dict[str, str] = {}
        for key, raw in ours_entries:
            merged.setdefault(key, raw)
        for key, raw in theirs_entries:
            merged.setdefault(key, raw)
        ordered = sorted(merged.items(), key=lambda kv: kv[0])
        merged_text = "\n".join(raw for _, raw in ordered) + "\n"

        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Auto(merged_text=merged_text, rule_id=RULE_ID_INIT_IMPORTS),
        )
    except Exception as exc:
        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Manual(
                reason=f"{RULE_ID_INIT_IMPORTS}: rule raised: {exc!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Rule 3: R-URLS-LIST-UNION
# ---------------------------------------------------------------------------


_RE_URL_LIST_ENTRY = re.compile(r'^\s*("[^"\n]*"|\'[^\']*\')')


def _parse_url_entries(block: str) -> list[tuple[str, str]] | None:
    """Parse a block of list-of-strings entries. Returns ``[(key, raw_line), ...]``."""
    parsed: list[tuple[str, str]] = []
    for raw in block.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _RE_URL_LIST_ENTRY.match(raw)
        if m is None:
            return None
        # key is the quoted body (lowercased) so duplicate-detection
        # ignores trailing comma drift.
        key = m.group(1).strip("'\"").lower()
        line = raw.rstrip()
        if not line.endswith(","):
            line = line + ","
        parsed.append((key, line))
    return parsed


def _is_urls_list_eligible(file_path: Path, hunk_text: str) -> bool:
    """Eligibility predicate for the URL-list-union rule."""
    if file_path.name == "urls.py":
        return True
    return any(_looks_like_urls_assignment(line) for line in hunk_text.splitlines())


def _looks_like_urls_assignment(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False

    name, sep, value = stripped.partition("=")
    if sep:
        name = name.split(":", 1)[0]
    else:
        name, sep, value = stripped.partition(":")
    if not sep:
        return False

    candidate = name.strip()
    for prefix in ("URL_PATTERNS", "_URLS", "URLS", "_URL", "URL"):
        if candidate != prefix:
            continue
        value = value.lstrip()
        return bool(value) and (value[0].isalpha() or value[0] == "[")
    return False


def _find_url_entry_conflict(
    ours_entries: list[tuple[str, str]],
    theirs_entries: list[tuple[str, str]],
) -> str | None:
    """Return a key modified on both sides, or None."""
    ours_by_key = {key: line.strip() for key, line in ours_entries}
    theirs_by_key = {key: line.strip() for key, line in theirs_entries}
    for key in ours_by_key.keys() & theirs_by_key.keys():
        if ours_by_key[key] != theirs_by_key[key]:
            return key
    return None


def _leading_indent_of(block: str) -> str:
    for raw in block.splitlines():
        if raw.strip():
            return raw[: len(raw) - len(raw.lstrip())]
    return ""


def r_urls_list_union(
    file_path: Path, hunk_text: str
) -> ConflictClassification | None:
    """Match additive merges on URL-list constants."""
    try:
        if not _is_urls_list_eligible(file_path, hunk_text):
            return None

        split = _split_conflict_region(hunk_text)
        if split is None:
            return None
        ours, theirs = split

        ours_entries = _parse_url_entries(ours)
        theirs_entries = _parse_url_entries(theirs)
        if ours_entries is None or theirs_entries is None:
            return None

        conflict_key = _find_url_entry_conflict(ours_entries, theirs_entries)
        if conflict_key is not None:
            return ConflictClassification(
                file_path=file_path,
                hunk_text=hunk_text,
                resolution=Manual(
                    reason=(
                        f"{RULE_ID_URLS_LIST}: same entry '{conflict_key}' modified "
                        f"on both sides — semantic conflict"
                    )
                ),
            )

        merged: dict[str, str] = {}
        for key, line in ours_entries:
            merged.setdefault(key, line)
        for key, line in theirs_entries:
            merged.setdefault(key, line)

        ordered = (
            sorted(merged.items(), key=lambda kv: kv[0])
            if _is_sorted_alpha(ours_entries)
            else list(merged.items())
        )

        leading_indent = _leading_indent_of(ours)
        merged_lines = [leading_indent + line.lstrip() for _, line in ordered]
        merged_text = "\n".join(merged_lines) + "\n"

        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Auto(merged_text=merged_text, rule_id=RULE_ID_URLS_LIST),
        )
    except Exception as exc:
        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Manual(
                reason=f"{RULE_ID_URLS_LIST}: rule raised: {exc!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Rule 4: R-UVLOCK-REGENERATE
# ---------------------------------------------------------------------------


# Sentinel rule_id stamped into the Auto.merged_text=""; the orchestrator
# interprets the special rule_id and runs ``uv lock --no-upgrade`` instead
# of writing merged_text.
def r_uvlock_regenerate(
    file_path: Path, hunk_text: str
) -> ConflictClassification | None:
    """Match ``uv.lock`` conflicts; emit a special sentinel for the orchestrator."""
    try:
        if file_path.name != "uv.lock":
            return None
        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Auto(merged_text="", rule_id=RULE_ID_UVLOCK),
        )
    except Exception as exc:
        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Manual(reason=f"{RULE_ID_UVLOCK}: rule raised: {exc!r}"),
        )


# ---------------------------------------------------------------------------
# Rule 5: R-DEFAULT-MANUAL (always last)
# ---------------------------------------------------------------------------


def r_default_manual(
    file_path: Path, hunk_text: str
) -> ConflictClassification | None:
    """Fail-safe default. Always returns a Manual classification."""
    try:
        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Manual(
                reason=f"no classifier rule matched {file_path}"
            ),
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ConflictClassification(
            file_path=file_path,
            hunk_text=hunk_text,
            resolution=Manual(reason=f"{RULE_ID_DEFAULT_MANUAL}: rule raised: {exc!r}"),
        )


RULES: tuple[ClassifierRule, ...] = (
    r_pyproject_deps_union,
    r_init_imports_union,
    r_urls_list_union,
    r_uvlock_regenerate,
    r_default_manual,
)


# ---------------------------------------------------------------------------
# Post-resolution validation
# ---------------------------------------------------------------------------


def validate_resolution(
    classification: ConflictClassification, full_file_text: str
) -> ConflictClassification:
    """Verify an Auto resolution produces syntactically valid output.

    ``full_file_text`` is the would-be file body if ``classification.resolution.merged_text``
    were spliced in. Returns the original classification on success; returns a
    new classification with ``Manual`` on validation failure (NFR-005 invariant 3).
    The ``uv.lock`` sentinel is exempt — the orchestrator regenerates it.
    """
    res = classification.resolution
    if not isinstance(res, Auto):
        return classification
    if res.rule_id == RULE_ID_UVLOCK:
        return classification  # not a textual merge — skip validation

    try:
        if classification.file_path.suffix == ".toml":
            tomllib.loads(full_file_text)
        elif classification.file_path.suffix == ".py":
            ast.parse(full_file_text)
        # Other file types are not validated here (callers may add their own).
    except Exception as exc:
        return ConflictClassification(
            file_path=classification.file_path,
            hunk_text=classification.hunk_text,
            resolution=Manual(
                reason=(
                    f"post-merge validation failed for "
                    f"{classification.file_path}: {exc!r}"
                )
            ),
        )
    return classification


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def classify(file_path: Path, hunk_text: str) -> ConflictClassification:
    """Run the rule list in declared order; return the first non-None result.

    ``R-DEFAULT-MANUAL`` is always last, so the return is never ``None``.
    """
    for rule in RULES:
        try:
            result = rule(file_path, hunk_text)
        except Exception as exc:  # NFR-005 belt-and-braces
            return ConflictClassification(
                file_path=file_path,
                hunk_text=hunk_text,
                resolution=Manual(
                    reason=f"classifier dispatcher caught {rule.__name__}: {exc!r}"
                ),
            )
        if result is not None:
            return result
    # Unreachable — R-DEFAULT-MANUAL always returns a value — but keep a
    # belt-and-braces fallback for type-checkers.
    return ConflictClassification(  # pragma: no cover
        file_path=file_path,
        hunk_text=hunk_text,
        resolution=Manual(reason="classifier exhausted with no match"),
    )
