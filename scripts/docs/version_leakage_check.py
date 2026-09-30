"""Version leakage check (FR-005 / NFR-002).

Read-only tool that compares a docs page inventory (``PageInventoryEntry``
rows) against the on-disk markdown tree and emits structured findings when
version-tier discipline is violated.

Four rule IDs:

- ``LEAK-CURRENT-LINKS-ARCHIVAL`` – a ``current`` page links to an
  ``archival`` path without a migration banner.
- ``LEAK-MISSING-BANNER`` – an ``archival`` or ``migration`` page is
  missing its required banner.
- ``LEAK-MISSING-INVENTORY`` – a markdown file under ``docs/`` is not in
  the manifest.
- ``LEAK-MISSING-FILE`` – an inventory row points at a non-existent file.

The former ``LEAK-FRONTMATTER-MISMATCH`` rule (frontmatter ``version_tag``
disagreeing with the inventory row) was **retired** in Mission B: under the
in-file-frontmatter SSOT (ADR ``2026-06-27-1`` D1) the datum lives in exactly
one place, and the now-blocking ``INVENTORY-LOCKFILE-DRIFT`` gate in
``check_docs_freshness.py`` subsumes frontmatter/inventory drift enforcement.

Exit codes (per contract):

- ``0`` – clean (no error-severity findings).
- ``1`` – one or more error-severity findings.
- ``2`` – input error (missing inventory, malformed YAML, bad row).
- ``3`` – environmental setup error (e.g. ``docs-root`` unresolvable).

The script never writes to ``docs/`` or to the inventory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from kernel.clock import now_utc_iso
from pathlib import Path
from typing import Final

from rich.console import Console

from scripts.docs._inventory import (
    LoadError,
    PageInventoryEntry,
    VersionTag,
    load_inventory,
)
from scripts.docs._render import (
    FreshnessFinding,
    render_table_plain,
    render_table_rich,
)

__all__ = [
    "DEFAULT_BANNER_REGEX",
    "DEFAULT_DOCS_ROOT",
    "DEFAULT_INVENTORY_PATH",
    "build_parser",
    "main",
    "run_checks",
]


DEFAULT_INVENTORY_PATH: Final[str] = "docs/development/page-inventory.yaml"
DEFAULT_DOCS_ROOT: Final[str] = "docs/"
DEFAULT_BANNER_REGEX: Final[str] = r"^>\s*(?:Archive notice|Migration note)\b"

_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"\[([^\]]+)\]\(([^)]+)\)"
)

# Banner-tier tags whose pages must carry an archive/migration banner.
_BANNER_REQUIRED: Final[frozenset[VersionTag]] = frozenset(
    {VersionTag.ARCHIVAL, VersionTag.MIGRATION}
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the leakage check."""
    parser = argparse.ArgumentParser(
        prog="version_leakage_check",
        description=(
            "Detect version-tier docs leakage and frontmatter/inventory "
            "drift (FR-005 / NFR-002). Read-only."
        ),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(DEFAULT_INVENTORY_PATH),
        help=f"Path to the page inventory YAML (default: {DEFAULT_INVENTORY_PATH}).",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Root directory to scan for markdown files (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--banner-regex",
        type=str,
        default=DEFAULT_BANNER_REGEX,
        help=(
            "Regex matched against the first 20 non-empty lines of "
            "archival/migration pages."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write a JSON FreshnessReport slice.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Suppress rich output; emit plain-text lines for CI annotations.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        banner_regex = re.compile(args.banner_regex, re.MULTILINE)
    except re.error as exc:
        _stderr(f"Invalid --banner-regex: {exc}")
        return 2

    docs_root: Path = args.docs_root
    if not docs_root.exists():
        _stderr(f"docs-root does not exist: {docs_root}")
        return 3
    if not docs_root.is_dir():
        _stderr(f"docs-root is not a directory: {docs_root}")
        return 3

    try:
        inventory = load_inventory(args.inventory)
    except LoadError as exc:
        _stderr(str(exc))
        return 2

    findings = run_checks(
        inventory=inventory,
        docs_root=docs_root,
        banner_regex=banner_regex,
    )

    # Deterministic ordering: by rule_id, then location.
    findings_sorted = sorted(
        findings, key=lambda f: (f.rule_id, f.location, f.message)
    )

    exit_code: int = 1 if any(f.severity == "error" for f in findings_sorted) else 0

    if args.report is not None:
        _write_report(
            report_path=args.report,
            findings=findings_sorted,
            inventory=inventory,
            exit_code=exit_code,
        )

    _emit_output(findings_sorted, ci=args.ci)
    return exit_code


def run_checks(
    inventory: list[PageInventoryEntry],
    docs_root: Path,
    banner_regex: re.Pattern[str],
) -> list[FreshnessFinding]:
    """Execute all leakage checks. Pure function for ease of testing."""
    findings: list[FreshnessFinding] = []
    inventory_by_path: dict[str, PageInventoryEntry] = {
        entry.path: entry for entry in inventory
    }

    for entry in inventory:
        file_path = Path(entry.path)
        if not file_path.exists() or not file_path.is_file():
            findings.append(
                FreshnessFinding(
                    rule_id="LEAK-MISSING-FILE",
                    severity="error",
                    location=entry.path,
                    message=(
                        "inventory row references a file that does not "
                        "exist on disk"
                    ),
                    suggested_action=(
                        "create the page or remove the row from the inventory"
                    ),
                )
            )
            continue

        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                FreshnessFinding(
                    rule_id="LEAK-MISSING-FILE",
                    severity="error",
                    location=entry.path,
                    message=f"could not read file: {exc}",
                    suggested_action="check filesystem permissions",
                )
            )
            continue

        if entry.tag in _BANNER_REQUIRED and not _has_banner(text, banner_regex):
            findings.append(
                FreshnessFinding(
                    rule_id="LEAK-MISSING-BANNER",
                    severity="error",
                    location=entry.path,
                    message=(
                        f"{entry.tag.value} page missing banner matching "
                        f"/{banner_regex.pattern}/"
                    ),
                    suggested_action=(
                        "prepend an archive or migration banner to the page"
                    ),
                )
            )

        if entry.tag is VersionTag.CURRENT:
            for link_target in _iter_link_targets(text):
                resolved = _resolve_link_target(link_target, file_path)
                if resolved is None:
                    continue
                target_entry = inventory_by_path.get(resolved)
                if (
                    target_entry is not None
                    and target_entry.tag is VersionTag.ARCHIVAL
                ):
                    findings.append(
                        FreshnessFinding(
                            rule_id="LEAK-CURRENT-LINKS-ARCHIVAL",
                            severity="error",
                            location=entry.path,
                            message=(
                                f"links to {resolved} (archival) without a "
                                "migration banner"
                            ),
                            suggested_action=(
                                "add a migration callout or retarget the link "
                                "to a current/migration page"
                            ),
                        )
                    )

    # Filesystem walk: any markdown file under docs_root not in the inventory.
    for md_path in _iter_markdown_files(docs_root):
        rel = _to_repo_relative(md_path)
        if rel in inventory_by_path:
            continue
        findings.append(
            FreshnessFinding(
                rule_id="LEAK-MISSING-INVENTORY",
                severity="error",
                location=rel,
                message="markdown file under docs/ is not in the inventory",
                suggested_action=(
                    "add a PageInventoryEntry row for this page or move it "
                    "outside docs/"
                ),
            )
        )

    return findings


# --- helpers ---------------------------------------------------------------


def _stderr(message: str) -> None:
    """Print ``message`` to stderr."""
    print(message, file=sys.stderr)


def _emit_output(findings: list[FreshnessFinding], *, ci: bool) -> None:
    """Print findings to stdout in the configured style."""
    if ci or not sys.stdout.isatty():
        sys.stdout.write(render_table_plain(findings))
        return
    console = Console()
    console.print(render_table_rich(findings))


def _write_report(
    report_path: Path,
    findings: list[FreshnessFinding],
    inventory: list[PageInventoryEntry],
    exit_code: int,
) -> None:
    """Serialize a FreshnessReport slice to ``report_path`` as JSON."""
    payload = {
        "started_at": now_utc_iso(),
        "inventory_rows_count": len(inventory),
        "findings": [asdict(f) for f in findings],
        "exit_code": exit_code,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _has_banner(text: str, banner_regex: re.Pattern[str]) -> bool:
    """Return True if any of the first 20 non-empty lines match ``banner_regex``."""
    seen = 0
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        seen += 1
        if seen > 20:
            break
        if banner_regex.search(line):
            return True
    return False


def _iter_link_targets(text: str) -> Iterable[str]:
    """Yield raw target strings from ``[text](target)`` markdown links."""
    for match in _MARKDOWN_LINK_RE.finditer(text):
        yield match.group(2)


def _resolve_link_target(link_target: str, source_file: Path) -> str | None:
    """Resolve a link target to a repo-relative path, or ``None``.

    External links (http/https/mailto/anchors) are filtered out. Relative
    paths are resolved against the source file's directory; the result is
    returned as a forward-slash-separated repo-relative string.
    """
    if not link_target:
        return None
    target = link_target.split("#", 1)[0]
    if not target:
        return None
    lowered = target.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:", "ftp://")):
        return None
    if target.startswith("/"):
        # Absolute repo paths are normalized by stripping the leading slash.
        return target.lstrip("/")

    candidate = (source_file.parent / target).resolve()
    try:
        rel = candidate.relative_to(Path.cwd().resolve())
    except ValueError:
        return None
    return rel.as_posix()


def _iter_markdown_files(docs_root: Path) -> Iterable[Path]:
    """Yield every ``.md`` file under ``docs_root`` (sorted for determinism)."""
    yield from sorted(docs_root.rglob("*.md"))


def _to_repo_relative(path: Path) -> str:
    """Render ``path`` as a forward-slash-separated repo-relative string."""
    cwd = Path.cwd().resolve()
    try:
        rel = path.resolve().relative_to(cwd)
    except ValueError:
        return path.as_posix()
    return rel.as_posix()


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
