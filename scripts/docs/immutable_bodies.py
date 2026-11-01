"""Body-hash baseline for the immutable documentation corpus (ADR 2026-10-31-1 D-7).

D-7's immutable-corpus rule: "ADRs, plans, reports and changelog entries keep their
**body** byte for byte. A frontmatter-only change made by a recorded, mechanical
migration is allowed. The migration step carries a test that hashes every immutable
file's body before and after and fails on any difference."

This module is the record that test compares against:

* :func:`collect` hashes the body (:func:`scripts.docs.frontmatter_contract.body_of`)
  of every Markdown file under :data:`IMMUTABLE_PREFIXES`;
* ``python -m scripts.docs.immutable_bodies --write`` records the baseline;
* ``python -m scripts.docs.immutable_bodies --check`` reports a difference and exits
  ``1`` — the same shape a gate takes, so CI wiring is a one-liner if it is ever
  wanted there.

What the baseline deliberately does **not** do:

* it does not forbid a *new* ADR, plan, report or changelog entry (a new artifact is
  not a changed body); re-running ``--write`` records it;
* it does not hash frontmatter. The whole point of D-7 is that the frontmatter of
  these files *may* change mechanically while the prose does not.

The test that consumes it (:mod:`tests.docs.test_frontmatter_body_immutability`)
also asserts the stronger property directly on the migration function — that the
transformation cannot alter a body for any input — so the guarantee survives the
baseline going stale, and the baseline catches the one thing a property test cannot:
a body that a human or another tool rewrote outside the migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from scripts.docs.frontmatter_contract import body_of

__all__ = [
    "BASELINE_PATH",
    "IMMUTABLE_PREFIXES",
    "BaselineDrift",
    "collect",
    "load_baseline",
    "main",
    "render_baseline",
]

#: The trees D-7 calls immutable. ``reports/`` is not published today (D-8 excludes
#: it), which is exactly why its bodies must still be pinned: unpublished is not the
#: same as disposable.
IMMUTABLE_PREFIXES: Final[tuple[str, ...]] = (
    "docs/adr/",
    "docs/plans/",
    "docs/reports/",
    "docs/changelog/",
)

#: Where the recorded baseline lives. Under ``docs/_meta/`` because it describes the
#: docs tree, and it is data rather than a page (no frontmatter, not published).
BASELINE_PATH: Final[str] = "docs/_meta/immutable-body-hashes.json"

#: What the hashes mean, recorded in the file so a reader does not have to guess.
BASELINE_DEFINITION: Final[str] = (
    "sha256 of each immutable page's body: the text from the closing frontmatter "
    "fence onward (scripts.docs.frontmatter_contract.body_of). Frontmatter is not "
    "hashed: ADR 2026-10-31-1 D-7 permits frontmatter-only mechanical changes."
)


@dataclass(slots=True, frozen=True)
class BaselineDrift:
    """One difference between the recorded baseline and the tree."""

    path: str
    kind: str  # "changed" | "missing"
    recorded: str
    observed: str | None

    def as_dict(self) -> dict[str, object]:
        """Serialize to the CLI's JSON shape."""
        return {
            "path": self.path,
            "kind": self.kind,
            "recorded": self.recorded,
            "observed": self.observed,
        }


def _iter_markdown(repo_root: Path, prefixes: Iterable[str]) -> list[Path]:
    """Every Markdown file under ``prefixes``, sorted for determinism."""
    found: list[Path] = []
    for prefix in prefixes:
        root = repo_root / prefix
        if root.is_dir():
            found.extend(path for path in root.rglob("*.md") if path.is_file())
    return sorted(set(found))


def body_hash(text: str) -> str:
    """SHA-256 of a page's body, as recorded in the baseline."""
    digest = hashlib.sha256()  # noqa: TID251 - artifact-integrity hash, not a security primitive
    digest.update(body_of(text).encode("utf-8"))
    return digest.hexdigest()


def collect(repo_root: Path, prefixes: Iterable[str] = IMMUTABLE_PREFIXES) -> dict[str, str]:
    """Hash every immutable page's body, keyed by repo-relative path."""
    hashes: dict[str, str] = {}
    for path in _iter_markdown(repo_root, prefixes):
        rel = path.relative_to(repo_root).as_posix()
        hashes[rel] = body_hash(path.read_text(encoding="utf-8"))
    return dict(sorted(hashes.items()))


def load_baseline(path: Path) -> dict[str, str]:
    """Read the recorded hashes from ``path``."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, Mapping):
        raise ValueError(f"{path}: baseline has no 'files' mapping")
    return {str(key): str(value) for key, value in files.items()}


def render_baseline(repo_root: Path, *, prefixes: Iterable[str] = IMMUTABLE_PREFIXES) -> str:
    """Render the baseline JSON deterministically."""
    payload = {
        "definition": BASELINE_DEFINITION,
        "immutable_prefixes": list(prefixes),
        "files": collect(repo_root, prefixes=prefixes),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def diff_baseline(recorded: Mapping[str, str], observed: Mapping[str, str]) -> list[BaselineDrift]:
    """Compare recorded hashes to the tree: changed and missing bodies only.

    A path present in the tree but absent from the baseline is a **new** artifact,
    not drift — the rule is about bodies that move, not about files that appear.
    """
    drift: list[BaselineDrift] = []
    for path, digest in sorted(recorded.items()):
        seen = observed.get(path)
        if seen is None:
            drift.append(BaselineDrift(path=path, kind="missing", recorded=digest, observed=None))
        elif seen != digest:
            drift.append(BaselineDrift(path=path, kind="changed", recorded=digest, observed=seen))
    return drift


def build_parser() -> argparse.ArgumentParser:
    """Build the baseline CLI parser."""
    parser = argparse.ArgumentParser(
        prog="immutable_bodies",
        description=(
            "Record or check the body hashes of the immutable documentation corpus "
            "(ADRs, plans, reports, changelog) that ADR 2026-10-31-1 D-7 freezes."
        ),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root (default: cwd).")
    parser.add_argument("--baseline", type=Path, default=None, help=f"Baseline path (default: {BASELINE_PATH}).")
    parser.add_argument("--write", action="store_true", help="Record the current bodies as the baseline.")
    parser.add_argument("--json", action="store_true", help="Emit the drift report as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    baseline_path = args.baseline if args.baseline is not None else args.repo_root / BASELINE_PATH
    if args.write:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(render_baseline(args.repo_root), encoding="utf-8")
        count = len(collect(args.repo_root))
        sys.stdout.write(f"immutable_bodies: recorded {count} body hash(es) in {baseline_path}.\n")
        return 0
    if not baseline_path.is_file():
        sys.stderr.write(
            f"immutable_bodies: no baseline at {baseline_path}; run --write to record one.\n"
        )
        return 2
    drift = diff_baseline(load_baseline(baseline_path), collect(args.repo_root))
    if args.json:
        sys.stdout.write(json.dumps([d.as_dict() for d in drift], indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"immutable_bodies: {len(drift)} body difference(s).\n")
        for entry in drift:
            sys.stdout.write(f"  {entry.kind.upper()} {entry.path}\n")
    return 1 if drift else 0


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
