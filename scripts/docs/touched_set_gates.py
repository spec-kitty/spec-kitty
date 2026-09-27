"""Touched-set docs gates (IC-03a / FR-017/018/023, NFR-002/005/006).

Presence and placement invariants for documentation pages must be checked over
the **touched set** — the pages a change actually adds or edits, computed from
``git diff --name-only <base>`` — never over the whole tree. A whole-tree
presence lint would red-line every untouched legacy page (C-012); the
denominator here is deliberately the diff, so an untouched page is never a
finding.

Three touched-set gates plus one closed-root gate:

* ``audience_presence`` (FR-018) — every touched in-scope page declares a
  resolvable ``audience:`` frontmatter reference (scalar or list) into the
  persona catalog under ``docs/context/audience/``.
* ``description_band`` (NFR-008) — every touched in-scope page carries a
  ``description:`` of 50-180 characters inclusive (the SEO band).
* ``audience_placement`` (SC-007) — a touched ``how_to``-typed page sits in the
  section its audience dictates: internal-audience how-tos in the internal home
  (``development/``), external-audience how-tos in the external home
  (``guides/``). The two homes are LOADED from the styleguide's
  ``structural_lint_config.concern_bucket_to_section`` (keys ``how_to_internal``
  / ``how_to_external``); when the styleguide has not yet been reconciled to the
  audience-split routing the placement gate reports nothing (it never guesses a
  home).
* ``root_allowlist`` (NFR-006/SC-002, T041) — a whole-repo-root gate the
  ``docs/``-rooted structural lint structurally cannot see: every
  documentation-bearing file at the repository root outside ``docs/`` must be in
  the closed ``structural_lint_config.root_allowlist``.

**Advisory** at this stage (IC-03a): the default exit code is ``0`` and findings
are reported; ``--strict`` flips the exit code to ``1`` on any finding. WP13
turns the structural gates blocking (OB-2). No policy literal is inlined — the
root allowlist and placement homes are read from the styleguide config block
(FR-011).

Non-vacuity (#3273): the report carries the examined counts, and the root
allowlist gate asserts a non-zero floor of root files examined via the shared
``assert_examined_floor`` guard, so a scope-narrowing regression goes red rather
than silently reporting "0 findings" over 0 examined.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from scripts.docs._guards import assert_examined_floor
from scripts.docs._inventory import parse_frontmatter

__all__ = [
    "DEFAULT_STYLEGUIDE",
    "GateReport",
    "Violation",
    "build_parser",
    "check_audience_placement",
    "check_audience_presence",
    "check_description_band",
    "check_root_allowlist",
    "compute_touched_set",
    "load_structural_config",
    "main",
    "run_gates",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"
DEFAULT_STYLEGUIDE: Final[str] = (
    "packs/internal/styleguides/spec-kitty-docs-lint-config.styleguide.yaml"
)
DEFAULT_CATALOG_ROOT: Final[str] = "docs/context/audience"
_CONFIG_KEY: Final[str] = "structural_lint_config"

#: SEO description band (inclusive), mirrors the styleguide principle.
_DESC_MIN: Final[int] = 50
_DESC_MAX: Final[int] = 180

#: Nav/landing basenames excluded from the touched in-scope page set — they are
#: scaffolding, not content pages carrying audience/description/placement.
_NAV_BASENAMES: Final[frozenset[str]] = frozenset({"index.md", "README.md"})

#: Root files considered "documentation-bearing" for the root-allowlist gate.
_DOC_ROOT_SUFFIXES: Final[tuple[str, ...]] = (".md", ".txt")
_DOC_ROOT_EXTRA: Final[frozenset[str]] = frozenset({".all-contributorsrc"})

_REFERENCE_SUFFIX: Final[str] = ".md"


@dataclass(slots=True, frozen=True)
class Violation:
    """One touched-set finding: ``{rule_id, path, message}``."""

    rule_id: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        """Serialize to the ``{rule_id, path, message}`` shape."""
        return {"rule_id": self.rule_id, "path": self.path, "message": self.message}


@dataclass(slots=True, frozen=True)
class GateReport:
    """Aggregate result of a touched-set gate run."""

    touched_pages_examined: int = 0
    root_files_examined: int = 0
    violations: list[Violation] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the report JSON shape."""
        return {
            "touched_pages_examined": self.touched_pages_examined,
            "root_files_examined": self.root_files_examined,
            "violations": [v.as_dict() for v in self.violations],
        }


# --- Config load (FR-011 SSOT) -----------------------------------------------


def load_structural_config(styleguide_path: Path) -> dict[str, Any]:
    """Return the ``structural_lint_config:`` block from the styleguide.

    Reads the same policy block the ``docs_structural_lint`` asset consumes, so
    the root allowlist and placement homes are never inlined here (FR-011).
    """
    yaml = YAML(typ="safe")
    try:
        with styleguide_path.open("r", encoding="utf-8") as handle:
            raw: Any = yaml.load(handle)
    except (OSError, YAMLError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"cannot read styleguide {styleguide_path}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get(_CONFIG_KEY), dict):
        raise ValueError(
            f"{styleguide_path} has no '{_CONFIG_KEY}:' mapping block (FR-011)."
        )
    return dict(raw[_CONFIG_KEY])


# --- Touched-set computation --------------------------------------------------


def compute_touched_set(base: str, repo_root: Path) -> list[Path]:
    """Return in-scope touched ``docs/**/*.md`` pages (absolute paths).

    Runs ``git diff --name-only <base>`` in ``repo_root`` and keeps only
    ``docs/``-rooted ``.md`` content pages (nav/landing basenames excluded). The
    denominator for every touched-set gate is exactly this set (C-012).
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", base],
        capture_output=True,
        text=True,
        check=True,
    )
    pages: list[Path] = []
    for line in result.stdout.splitlines():
        rel = line.strip()
        if not rel or not rel.endswith(".md"):
            continue
        parts = rel.split("/")
        if parts[0] != DEFAULT_DOCS_ROOT or parts[-1] in _NAV_BASENAMES:
            continue
        pages.append((repo_root / rel).resolve())
    return sorted(pages)


# --- Shared helpers -----------------------------------------------------------


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _frontmatter(md_path: Path) -> dict[str, Any]:
    try:
        return parse_frontmatter(md_path.read_text(encoding="utf-8"))
    except OSError:  # pragma: no cover - defensive
        return {}


def _audience_values(frontmatter: dict[str, Any]) -> list[str]:
    raw = frontmatter.get("audience")
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [str(item) for item in raw if isinstance(item, str) and item.strip()]
    return []


# --- Gate 1: audience presence + resolvability (FR-018) ----------------------


def check_audience_presence(
    pages: list[Path], repo_root: Path, catalog_root: Path
) -> list[Violation]:
    """Flag touched pages lacking a resolvable ``audience:`` reference."""
    catalog = catalog_root.resolve()
    violations: list[Violation] = []
    for page in pages:
        page_rel = _repo_relative(page, repo_root)
        values = _audience_values(_frontmatter(page))
        if not values:
            violations.append(
                Violation(
                    rule_id="audience_presence",
                    path=page_rel,
                    message=f"{page_rel} declares no audience: reference",
                )
            )
            continue
        for value in values:
            if not value.strip().endswith(_REFERENCE_SUFFIX):
                violations.append(
                    Violation(
                        rule_id="audience_presence",
                        path=page_rel,
                        message=(
                            f"{page_rel} audience '{value}' is not a persona "
                            "reference (.md path)"
                        ),
                    )
                )
                continue
            # The audience: value is a page-relative .md path into the persona
            # catalog (per the styleguide good_example, e.g.
            # ``../context/audience/internal/maintainer.md``), resolved against
            # the page's own directory like a markdown link.
            target = (page.parent / value.strip()).resolve()
            if not (target.is_file() and target.is_relative_to(catalog)):
                violations.append(
                    Violation(
                        rule_id="audience_presence",
                        path=page_rel,
                        message=(
                            f"{page_rel} audience '{value}' does not resolve to a "
                            f"persona under {_repo_relative(catalog, repo_root)}/"
                        ),
                    )
                )
    return violations


# --- Gate 2: description band (NFR-008) ---------------------------------------


def check_description_band(pages: list[Path], repo_root: Path) -> list[Violation]:
    """Flag touched pages whose ``description:`` is missing or out of band."""
    violations: list[Violation] = []
    for page in pages:
        page_rel = _repo_relative(page, repo_root)
        description = _frontmatter(page).get("description")
        if not isinstance(description, str) or not description.strip():
            violations.append(
                Violation(
                    rule_id="description_band",
                    path=page_rel,
                    message=f"{page_rel} has no description:",
                )
            )
            continue
        length = len(description)
        if not (_DESC_MIN <= length <= _DESC_MAX):
            violations.append(
                Violation(
                    rule_id="description_band",
                    path=page_rel,
                    message=(
                        f"{page_rel} description is {length} chars; must be "
                        f"{_DESC_MIN}-{_DESC_MAX} inclusive"
                    ),
                )
            )
    return violations


# --- Gate 3: audience placement (SC-007) -------------------------------------


def _placement_homes(config: dict[str, Any]) -> dict[str, str] | None:
    """Resolve the internal/external how-to section homes from config.

    Returns ``None`` (placement not enforceable) when the styleguide has not yet
    been reconciled to the audience-split routing — the gate never guesses a
    home from an inlined literal.
    """
    routing = config.get("concern_bucket_to_section")
    if not isinstance(routing, dict):
        return None
    internal = routing.get("how_to_internal")
    external = routing.get("how_to_external")
    if not isinstance(internal, str) or not isinstance(external, str):
        return None
    return {"internal": internal.strip("/"), "external": external.strip("/")}


def _audience_orientation(frontmatter: dict[str, Any]) -> str | None:
    """Classify a page's audience as ``internal``/``external`` from its refs."""
    for value in _audience_values(frontmatter):
        segments = value.strip("./").split("/")
        if "internal" in segments:
            return "internal"
        if "external" in segments:
            return "external"
    return None


def _is_how_to(frontmatter: dict[str, Any]) -> bool:
    return any(
        str(frontmatter.get(key, "")).strip().lower() == "how_to"
        for key in ("type", "divio_type", "doc_type")
    )


def check_audience_placement(
    pages: list[Path], repo_root: Path, docs_root: Path, config: dict[str, Any]
) -> list[Violation]:
    """Flag touched how-to pages sitting outside their audience's section."""
    homes = _placement_homes(config)
    if homes is None:
        return []
    violations: list[Violation] = []
    for page in pages:
        frontmatter = _frontmatter(page)
        if not _is_how_to(frontmatter):
            continue
        orientation = _audience_orientation(frontmatter)
        if orientation is None:
            continue
        expected = homes[orientation]
        section = _repo_relative(page, docs_root).split("/", 1)[0]
        if section == expected:
            continue
        page_rel = _repo_relative(page, repo_root)
        violations.append(
            Violation(
                rule_id="audience_placement",
                path=page_rel,
                message=(
                    f"{page_rel} is an {orientation}-audience how_to but lives in "
                    f"'{section}/'; its home is '{expected}/'"
                ),
            )
        )
    return violations


# --- Gate 4: root allowlist (NFR-006/SC-002, T041) ---------------------------


def _doc_bearing_root_files(repo_root: Path) -> list[Path]:
    """Documentation-bearing regular files at the repo root (outside docs/)."""
    found: list[Path] = []
    for entry in sorted(repo_root.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix in _DOC_ROOT_SUFFIXES or entry.name in _DOC_ROOT_EXTRA:
            found.append(entry)
    return found


def check_root_allowlist(
    repo_root: Path, config: dict[str, Any], *, min_files: int = 1
) -> tuple[list[Violation], int]:
    """Flag doc-bearing root files not in the closed ``root_allowlist``.

    Returns the violations and the number of root files examined. Raises via
    ``assert_examined_floor`` when fewer than ``min_files`` were examined — a
    scope-narrowing regression must go red, not silently pass over 0 files.
    """
    raw_allow = config.get("root_allowlist")
    if not isinstance(raw_allow, list):
        raise ValueError(f"'{_CONFIG_KEY}.root_allowlist' must be a list (FR-011).")
    allowlist = {str(item) for item in raw_allow}
    root_files = _doc_bearing_root_files(repo_root)
    assert_examined_floor(
        len(root_files),
        min_files,
        gate="check_root_allowlist",
        noun="documentation-bearing root file(s) examined",
        fr_id="NFR-006",
    )
    violations: list[Violation] = []
    for entry in root_files:
        if entry.name in allowlist:
            continue
        violations.append(
            Violation(
                rule_id="root_allowlist",
                path=entry.name,
                message=(
                    f"{entry.name} is a documentation-bearing root file not in "
                    "the sanctioned root_allowlist"
                ),
            )
        )
    return violations, len(root_files)


# --- Aggregation + CLI --------------------------------------------------------


def run_gates(
    *,
    base: str,
    repo_root: Path,
    styleguide_path: Path,
    docs_root: Path | None = None,
    catalog_root: Path | None = None,
    min_root_files: int = 1,
) -> GateReport:
    """Run every touched-set gate plus the root-allowlist gate."""
    docs = docs_root or repo_root / DEFAULT_DOCS_ROOT
    catalog = catalog_root or repo_root / DEFAULT_CATALOG_ROOT
    config = load_structural_config(styleguide_path)

    pages = compute_touched_set(base, repo_root)
    violations: list[Violation] = []
    violations.extend(check_audience_presence(pages, repo_root, catalog))
    violations.extend(check_description_band(pages, repo_root))
    violations.extend(check_audience_placement(pages, repo_root, docs, config))
    root_violations, root_examined = check_root_allowlist(
        repo_root, config, min_files=min_root_files
    )
    violations.extend(root_violations)
    violations.sort(key=lambda v: (v.rule_id, v.path))
    return GateReport(
        touched_pages_examined=len(pages),
        root_files_examined=root_examined,
        violations=violations,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the touched-set gates CLI parser."""
    parser = argparse.ArgumentParser(
        prog="touched_set_gates",
        description=(
            "Touched-set docs gates (audience presence, description band, "
            "audience placement) + root-allowlist gate. Report-only (exit 0) "
            "unless --strict is passed."
        ),
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Git ref the touched set is diffed against (e.g. origin/main).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: cwd).",
    )
    parser.add_argument(
        "--styleguide",
        type=Path,
        default=Path(DEFAULT_STYLEGUIDE),
        help=(
            "Path to the common-docs styleguide carrying the "
            f"'{_CONFIG_KEY}:' block (default: {DEFAULT_STYLEGUIDE})."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any finding exists (blocking). Advisory off.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    report = run_gates(
        base=args.base,
        repo_root=args.repo_root,
        styleguide_path=args.styleguide,
    )
    _emit(report, as_json=args.json)
    if args.strict and report.violations:
        return 1
    return 0


def _emit(report: GateReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return
    sys.stdout.write(
        f"touched_set_gates: examined {report.touched_pages_examined} touched "
        f"page(s) + {report.root_files_examined} root file(s); "
        f"{len(report.violations)} finding(s).\n"
    )
    for violation in report.violations:
        sys.stdout.write(
            f"  [{violation.rule_id}] {violation.path}: {violation.message}\n"
        )


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
