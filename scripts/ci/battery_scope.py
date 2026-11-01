"""Which gates one architectural battery leg runs for a diff (#6994).

``select`` prints ``key=value`` lines for ``$GITHUB_OUTPUT``:

* ``mode=full``: run the whole leg (a code diff, full mode, or any doubt);
* ``mode=scoped``: the diff matched only declared scan scopes; ``gates_file`` names a file that
  lists this leg's selected gates, one per line, which ``battery_partition_plugin`` reads from
  ``SK_BATTERY_GATES_FILE``;
* ``run=false``: scoped, and this leg holds none of the selected gates.

The selection itself is ``scripts.ci.gate_selection.select_battery_gates``; this module only
reads the diff, the leg's part and the ``--prose-only`` verdict the ``prose-scan`` job published.
It fails safe: no usable base, a git error or a selection error gives ``mode=full`` (and a
``::warning::``), never a narrower run.

``prose_only`` (#6999) narrows a PROVEN prose-only diff to the heavy gates whose declared scan
scope it touches -- the gates that read comment text, which the #4842 down-route used to drop
along with the whole battery (operator ruling 2026-11-01). It never widens: a prose answer is
still a scoped leg, and any doubt still answers the whole leg.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

__all__ = ["FULL", "SCOPED", "changed_paths", "decide", "main", "output_lines"]

FULL = "full"
SCOPED = "scoped"
_NULL_SHA = "0" * 40
_REPO_ROOT = Path(__file__).resolve().parents[2]


def changed_paths(base: str, head: str, *, repo: Path = _REPO_ROOT) -> list[str] | None:
    """The diff's paths, or ``None`` when no trustworthy diff can be computed."""
    if not base or base == _NULL_SHA or not head:
        return None
    # --no-renames: a move lists both its old and its new path, so a file moved out of src/ (or out of a
    # gate helper) still selects the whole battery instead of a scoped run of the destination's gates.
    result = subprocess.run(["git", "diff", "--name-only", "--no-renames", base, head], cwd=repo, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line]


def _part_files(part: str, repo: Path) -> frozenset[str]:
    from scripts.ci.battery_partition_plugin import compute_partition, load_spec_and_timings, parse_part

    spec, timings = load_spec_and_timings(repo)
    return frozenset(compute_partition(spec, repo, timings).parts[parse_part(part).key])


def decide(
    paths: Sequence[str] | None,
    *,
    part: str,
    mode: str = "pr",
    prose_only: bool = False,
    repo: Path = _REPO_ROOT,
) -> tuple[str, frozenset[str]]:
    """``(FULL, {})`` or ``(SCOPED, the gates of this leg the diff selects)``."""
    from scripts.ci.gate_selection import select_battery_gates

    if paths is None or mode == FULL:
        return FULL, frozenset()
    gates = select_battery_gates(paths, mode=mode, prose_only=prose_only)
    if gates is None:
        return FULL, frozenset()
    return SCOPED, gates & _part_files(part, repo)


def output_lines(mode: str, gates: frozenset[str], out: Path) -> list[str]:
    """The ``$GITHUB_OUTPUT`` lines; writes the gates file for a scoped answer."""
    if mode == FULL:
        return [f"mode={FULL}", "run=true", "gates_file="]
    out.write_text("".join(f"{gate}\n" for gate in sorted(gates)), encoding="utf-8")
    return [f"mode={SCOPED}", f"run={'true' if gates else 'false'}", f"gates_file={out}"]


def _flag(value: str) -> bool:
    """``true``/``false`` as the prose-scan output spells them; anything else is ``False``."""
    return value.strip().lower() == "true"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="battery_scope", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("select", help="decide which gates one battery leg runs for a diff")
    select.add_argument("--base", default="")
    select.add_argument("--head", default="")
    select.add_argument("--mode", default="pr")
    select.add_argument(
        "--prose-only",
        default="false",
        type=_flag,
        help="the prose-scan job's prose_only verdict (true|false); narrows a proven prose diff to its declared scan-scope gates",
    )
    select.add_argument("--battery-part", required=True)
    select.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        mode, gates = decide(changed_paths(args.base, args.head), part=args.battery_part, mode=args.mode, prose_only=args.prose_only)
    except Exception as error:  # fail safe: any doubt runs the whole leg, it never narrows the run
        print(f"::warning::battery scope selection failed ({error!r}); running the whole leg", file=sys.stderr)
        mode, gates = FULL, frozenset()
    lines = output_lines(mode, gates, args.out)
    if mode == SCOPED:
        print(f"battery scope: {len(gates)} gate(s) selected for part {args.battery_part}", file=sys.stderr)
        for gate in sorted(gates):
            print(f"  {gate}", file=sys.stderr)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
