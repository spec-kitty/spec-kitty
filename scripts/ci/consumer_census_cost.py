"""CI-cost delta of the census-derived fan-out (#6173, WP04).

Measures, per changed-path set, the per-PR selected-shard count under the live
human-validated ``GROUP_MODULE_FANOUT`` vs the census-derived fan-out
(``derive_group_module_fanout``) — the cost full value-derivation WOULD add (the
follow-up decision input, FR-009). Shard counts come from the registry's measured
``shard_count`` (never a guess).

The library (``shard_count_for``, ``compare_fanouts``) is pure and unit-tested; the
CLI ``--recent N`` reads the last N merged-PR diffs off ``origin/main`` via git and
prints the comparison table recorded in the PR.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.ci.gate_selection import (  # noqa: E402 — needs the sys.path bootstrap above
    DEFAULT_REGISTRY_PATH,
    GROUP_MODULE_FANOUT,
    Router,
    _modules_for_test_paths,
    _registry_module_names,
    derive_group_module_fanout,
    load_router,
    select_gates,
)

__all__ = [
    "REPRESENTATIVE_EDITS",
    "compare_fanouts",
    "main",
    "modules_under_fanout",
    "shard_counts",
    "shard_count_for",
]

# The pack-edit types #6174 recorded: where the census-derived fan-out differs from
# the hand fan-out. Real recent PR diffs rarely touch these (so the measured delta
# over recent commits is ~0), so the per-edit-type table is the honest view of what
# full value-derivation would cost (FR-009).
REPRESENTATIVE_EDITS: tuple[tuple[str, list[str]], ...] = (
    ("mission-steps/*/prompt.md", ["packs/built-in/missions/mission-steps/software-dev/research/prompt.md"]),
    ("*/expected-artifacts.yaml", ["packs/built-in/missions/software-dev/expected-artifacts.yaml"]),
    ("mission_types/*.yaml", ["packs/built-in/missions/mission_types/plan.yaml"]),
    ("*/mission.yaml", ["packs/built-in/missions/software-dev/mission.yaml"]),
    ("cli/commands/lifecycle.py", ["src/specify_cli/cli/commands/lifecycle.py"]),
    ("pack README.md (control)", ["packs/built-in/missions/README.md"]),
)


def shard_counts(registry_path: Path | None = None) -> dict[str, int]:
    """Each registry module's measured ``shard_count`` (default 1)."""
    registry = yaml.safe_load((registry_path or DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    return {str(row["module"]): int(row.get("shard_count", 1)) for row in registry["modules"]}


def modules_under_fanout(
    changed_paths: list[str],
    fanout: dict[str, frozenset[str]],
    *,
    router: Router,
    registry_path: Path | None = None,
) -> frozenset[str]:
    """``select_modules`` with an arbitrary fan-out map (so the hand and derived
    fan-outs can be compared without mutating the module-global one)."""
    modules = _registry_module_names(registry_path)
    selection = select_gates(changed_paths, router=router)
    if selection.unmatched_src:
        return modules
    selected = selection.matched_groups & modules
    for group, targets in fanout.items():
        if group in selection.matched_groups:
            selected = selected | (targets & modules)
    test_selected = _modules_for_test_paths(changed_paths, router=router, registry_path=registry_path, modules=modules)
    return selected | test_selected


def shard_count_for(
    changed_paths: list[str],
    fanout: dict[str, frozenset[str]],
    *,
    router: Router,
    counts: dict[str, int],
    registry_path: Path | None = None,
) -> int:
    """Total per-PR shards a changed-path set selects under ``fanout``."""
    selected = modules_under_fanout(changed_paths, fanout, router=router, registry_path=registry_path)
    return sum(counts.get(module, 1) for module in selected)


def compare_fanouts(
    diffs: list[list[str]],
    *,
    router: Router | None = None,
    registry_path: Path | None = None,
) -> list[dict[str, object]]:
    """Per diff: the selected-shard count under the hand fan-out vs the derived one."""
    router = router or load_router()
    counts = shard_counts(registry_path)
    hand = GROUP_MODULE_FANOUT
    derived = derive_group_module_fanout(router=router, registry_path=registry_path)
    rows: list[dict[str, object]] = []
    for changed in diffs:
        hand_cost = shard_count_for(changed, hand, router=router, counts=counts, registry_path=registry_path)
        derived_cost = shard_count_for(changed, derived, router=router, counts=counts, registry_path=registry_path)
        rows.append(
            {
                "paths": changed,
                "hand_shards": hand_cost,
                "derived_shards": derived_cost,
                "delta": derived_cost - hand_cost,
            }
        )
    return rows


def _recent_merge_diffs(n: int) -> list[tuple[str, list[str]]]:
    """The changed files of the last ``n`` landed commits on ``origin/main``.

    ``spec-kitty`` lands PRs squash/rebase (linear first-parent history, no merge
    commits), so each first-parent non-merge commit is a landed change set."""
    out = subprocess.run(
        ["git", "log", "origin/main", "--no-merges", "--first-parent", f"-{n}", "--format=%H %s"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    diffs: list[tuple[str, list[str]]] = []
    for line in out:
        sha, _, subject = line.partition(" ")
        files = subprocess.run(
            ["git", "show", "--pretty=", "--name-only", sha],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if files:
            diffs.append((subject[:60], files))
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CI-cost delta of the census-derived fan-out (#6173).")
    parser.add_argument("--recent", type=int, default=20, help="How many recent merge commits to measure.")
    args = parser.parse_args(argv)

    # Per-edit-type delta (where the derivation differs): the honest cost of full
    # value-derivation, since real PR diffs rarely touch pack content.
    rep_rows = compare_fanouts([paths for _label, paths in REPRESENTATIVE_EDITS])
    print("Representative pack-edit types (hand vs census-derived fan-out):")
    print(f"  {'hand':>5} {'derived':>8} {'delta':>6}  edit type")
    for (label, _paths), row in zip(REPRESENTATIVE_EDITS, rep_rows, strict=True):
        print(f"  {row['hand_shards']:>5} {row['derived_shards']:>8} {row['delta']:>+6}  {label}")

    merges = _recent_merge_diffs(args.recent)
    if not merges:
        print("\nno landed commits found on origin/main", file=sys.stderr)
        return 0
    rows = compare_fanouts([files for _subject, files in merges])
    print(f"\nLast {len(rows)} landed commits on origin/main (real diffs):")
    print(f"  {'hand':>5} {'derived':>8} {'delta':>6}  change")
    total_hand = total_derived = 0
    for (subject, _files), row in zip(merges, rows, strict=True):
        total_hand += int(row["hand_shards"])  # type: ignore[call-overload]
        total_derived += int(row["derived_shards"])  # type: ignore[call-overload]
        print(f"  {row['hand_shards']:>5} {row['derived_shards']:>8} {row['delta']:>+6}  {subject}")
    print(f"  {total_hand:>5} {total_derived:>8} {total_derived - total_hand:>+6}  TOTAL over {len(rows)} commits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
