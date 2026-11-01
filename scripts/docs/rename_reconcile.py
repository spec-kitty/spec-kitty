"""Rename / deletion reconciliation gate (IC-03a / NFR-005, FR-023).

A docs move must not silently drop a published page. Two set-containment checks
enforce that against the standing moves ledger ``site/moves.yaml`` (#6927; no
Mission's ``occurrence_map.yaml`` is read, #2358):

* ``rename_reconcile`` (reverse direction) — every rename or deletion the git
  diff reports of a **published** ``docs/`` page (a page whose route is in
  ``site/url-baseline.txt``) MUST be a ledger ``from`` route. Non-page files and
  pages that were never published are out of scope: they have no URL to break.
* ``occurrence_subset_redirect`` (forward cross-check) — every ledger ``from``
  route MUST be a key of the committed ``redirect_map.yaml``, so a recorded move
  keeps a working redirect (a stale map is a finding).

**Path-configurable.** The ledger, baseline and redirect-map paths are
parameters (defaulting to their canonical repo-relative locations). When the
ledger is absent the gate is a no-op with an examined count of ``0`` (reported),
never a crash.

**Advisory**: report-only exit ``0`` unless ``--strict`` is passed, which flips
the exit code to ``1`` on any finding.
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

# ``python3 scripts/docs/rename_reconcile.py`` puts ``scripts/docs/`` on
# ``sys.path``, not the repository root; anchor it so the ledger module resolves.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs.moves_ledger import Move  # noqa: E402  (sys.path bootstrap above)
from scripts.docs.moves_ledger import load_baseline  # noqa: E402  (sys.path bootstrap above)
from scripts.docs.moves_ledger import load_moves as load_ledger_moves  # noqa: E402  (sys.path bootstrap above)
from scripts.docs.moves_ledger import source_to_route  # noqa: E402  (sys.path bootstrap above)

__all__ = [
    "DEFAULT_MOVES_LEDGER",
    "DEFAULT_REDIRECT_MAP",
    "DEFAULT_URL_BASELINE",
    "ReconcileReport",
    "Violation",
    "build_parser",
    "check_occurrence_subset_redirect",
    "check_renames_covered",
    "load_moves",
    "main",
    "renames_and_deletions",
    "run_reconcile",
]

DEFAULT_MOVES_LEDGER: Final[str] = "site/moves.yaml"
DEFAULT_URL_BASELINE: Final[str] = "site/url-baseline.txt"
DEFAULT_REDIRECT_MAP: Final[str] = "scripts/docs/redirect_map.yaml"


@dataclass(slots=True, frozen=True)
class Violation:
    """One reconciliation finding: ``{rule_id, path, message}``."""

    rule_id: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        """Serialize to the ``{rule_id, path, message}`` shape."""
        return {"rule_id": self.rule_id, "path": self.path, "message": self.message}


@dataclass(slots=True, frozen=True)
class ReconcileReport:
    """Aggregate result of a reconciliation run."""

    renames_examined: int = 0
    moves_examined: int = 0
    violations: list[Violation] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the report JSON shape."""
        return {
            "renames_examined": self.renames_examined,
            "moves_examined": self.moves_examined,
            "violations": [v.as_dict() for v in self.violations],
        }


# --- Spine loading ------------------------------------------------------------


def load_moves(moves_ledger_path: Path) -> list[Move]:
    """Load the moves ledger (``[]`` when the file is absent)."""
    if not moves_ledger_path.is_file():
        return []
    return load_ledger_moves(moves_ledger_path)


def _load_published_routes(baseline_path: Path) -> set[str]:
    """Routes of the URL baseline (``set()`` when absent)."""
    if not baseline_path.is_file():
        return set()
    return set(load_baseline(baseline_path))


def _load_redirect_keys(redirect_map_path: Path) -> set[str]:
    """Return the key set of a redirect map (``set()`` when absent)."""
    if not redirect_map_path.is_file():
        return set()
    yaml = YAML(typ="safe")
    try:
        with redirect_map_path.open("r", encoding="utf-8") as handle:
            raw: Any = yaml.load(handle)
    except (OSError, YAMLError) as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"cannot read redirect map {redirect_map_path}: {exc}"
        ) from exc
    return {str(key) for key in raw} if isinstance(raw, dict) else set()


# --- Git rename / deletion extraction ----------------------------------------


def renames_and_deletions(base: str, repo_root: Path) -> list[str]:
    """Return source paths of every rename/deletion vs ``base`` (rename-aware).

    Uses ``git diff --find-renames --name-status`` so a moved page surfaces as
    its ORIGINAL path (the thing the spine must account for), and a plain delete
    surfaces as its path. Additions and in-place edits are ignored.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--find-renames", "--name-status", base],
        capture_output=True,
        text=True,
        check=True,
    )
    sources: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            sources.append(parts[1])  # original path of a rename
        elif status.startswith("D") and len(parts) >= 2:
            sources.append(parts[1])  # deleted path
    return sorted(sources)


# --- Gate 1: rename/deletion reconciliation (reverse) ------------------------


def check_renames_covered(
    sources: list[str], moves: list[Move], published: set[str]
) -> list[Violation]:
    """Flag a renamed/deleted published page whose route is not a ledger ``from``."""
    recorded = {move.from_route for move in moves}
    violations: list[Violation] = []
    for source in sources:
        route = source_to_route(source)
        if route is None or route not in published or route in recorded:
            continue
        violations.append(
            Violation(
                rule_id="rename_reconcile",
                path=source,
                message=(
                    f"{source} was renamed/deleted but its published route {route} "
                    "has no site/moves.yaml entry (append one)"
                ),
            )
        )
    return violations


# --- Gate 2: ledger subset of redirect-map (forward) -------------------------


def check_occurrence_subset_redirect(
    moves: list[Move], redirect_keys: set[str]
) -> list[Violation]:
    """Flag a ledger move whose ``from`` route is not a redirect-map key."""
    violations: list[Violation] = []
    for move in moves:
        key = move.from_route.lstrip("/")
        if key not in redirect_keys:
            violations.append(
                Violation(
                    rule_id="occurrence_subset_redirect",
                    path=move.from_route,
                    message=(
                        f"{move.from_route} moves to {move.to_route} but '{key}' is "
                        "absent from the redirect map (run regenerate-map)"
                    ),
                )
            )
    return violations


# --- Aggregation + CLI --------------------------------------------------------


def run_reconcile(
    *,
    base: str,
    repo_root: Path,
    moves_ledger_path: Path | None = None,
    url_baseline_path: Path | None = None,
    redirect_map_path: Path | None = None,
    cross_check: bool = True,
) -> ReconcileReport:
    """Run the rename-reconcile gate and (optionally) the redirect cross-check."""
    moves = load_moves(moves_ledger_path or repo_root / DEFAULT_MOVES_LEDGER)
    published = _load_published_routes(url_baseline_path or repo_root / DEFAULT_URL_BASELINE)
    red_path = redirect_map_path or repo_root / DEFAULT_REDIRECT_MAP
    sources = renames_and_deletions(base, repo_root)

    violations = check_renames_covered(sources, moves, published)
    if cross_check:
        redirect_keys = _load_redirect_keys(red_path)
        violations.extend(check_occurrence_subset_redirect(moves, redirect_keys))
    violations.sort(key=lambda v: (v.rule_id, v.path))
    return ReconcileReport(
        renames_examined=len(sources),
        moves_examined=len(moves),
        violations=violations,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the rename-reconcile CLI parser."""
    parser = argparse.ArgumentParser(
        prog="rename_reconcile",
        description=(
            "Assert every rename/deletion of a published docs page is recorded "
            "in site/moves.yaml, and every recorded move has a redirect. "
            "Report-only (exit 0) unless --strict is passed."
        ),
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Git ref the diff is computed against (e.g. origin/main).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: cwd).",
    )
    parser.add_argument(
        "--moves",
        type=Path,
        default=None,
        help=f"Moves ledger path (default: <repo-root>/{DEFAULT_MOVES_LEDGER}).",
    )
    parser.add_argument(
        "--url-baseline",
        type=Path,
        default=None,
        help=f"URL baseline path (default: <repo-root>/{DEFAULT_URL_BASELINE}).",
    )
    parser.add_argument(
        "--redirect-map",
        type=Path,
        default=None,
        help=f"Redirect map path (default: <repo-root>/{DEFAULT_REDIRECT_MAP}).",
    )
    parser.add_argument(
        "--no-cross-check",
        action="store_true",
        help="Skip the ledger ⊆ redirect-map cross-check.",
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
    report = run_reconcile(
        base=args.base,
        repo_root=args.repo_root,
        moves_ledger_path=args.moves,
        url_baseline_path=args.url_baseline,
        redirect_map_path=args.redirect_map,
        cross_check=not args.no_cross_check,
    )
    _emit(report, as_json=args.json)
    if args.strict and report.violations:
        return 1
    return 0


def _emit(report: ReconcileReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return
    sys.stdout.write(
        f"rename_reconcile: examined {report.renames_examined} rename/deletion(s) "
        f"against {report.moves_examined} move(s); "
        f"{len(report.violations)} finding(s).\n"
    )
    for violation in report.violations:
        sys.stdout.write(
            f"  [{violation.rule_id}] {violation.path}: {violation.message}\n"
        )


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
