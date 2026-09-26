"""Census re-key tooling and equivalence proof (WP04 T020 / T025, FR-006).

Mission artefact, NOT a committed test: a test would have to hold the 80 old
``rel:lineno:op`` line keys, which the widened positional-anchor ban forbids.

Run from the repository root with the project venv (stdlib + repo imports only):

    .venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py \\
        --head-root <lane-worktree-abs-path> [--base 3717c7ea] MODE

Modes
-----
``--emit-map``
    Write ``census-rekey-map.csv`` (next to this directory's parent): one row per
    base allowlist entry, ``gate, old_key, rel, qualname, token_line, op,
    op_ordinal, rationale_sha256``.
``--emit-literals <gate>``
    Print the base ``_ALLOWLIST`` block of *gate* with every string key rewritten
    to its ``CensusKey(...)`` literal. Comments, grouping, order and rationale
    text are preserved byte-for-byte (only the key tokens are replaced).
(default) equivalence check
    (a) old site set ``{(gate, rel, lineno, op)}`` from the base allowlists;
    (b) every ``CensusKey`` of the head gates resolved through ``census_keys``
    over live source to ``(rel, lineno)``; (c) the two site sets are equal, the
    old->new mapping is a bijection and ``rationale_sha256`` matches per site;
    (d) per-gate counts are printed. Exits non-zero on any mismatch.
``--self-test``
    Runs the equivalence check on three in-memory corruptions of the new keys
    (flip one ``op_ordinal``; drop one key; swap two rationales) and exits
    non-zero unless EACH corruption is detected.

``--head-root`` is required: it is inserted at the front of ``sys.path`` before
the gate modules are imported, so the migrated gates of the lane are imported,
never the gates of the checkout the script runs from. The script also proves
that every censused source file under ``--head-root`` is byte-identical to
``--base`` (C-005), which is what makes ``(rel, lineno)`` a valid cross-SHA
site identity.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib
import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

GATES: dict[str, tuple[str, str]] = {
    # gate -> (gate module path, finder function name)
    "destructive": ("tests/architectural/test_destructive_op_routing.py", "_find_destructive_literals"),
    "mutation": ("tests/architectural/test_mutation_ownership_routing.py", "_find_destructive_ops"),
    "overwrite": ("tests/architectural/test_overwrite_ownership_routing.py", "_find_overwrite_ops"),
}
EXPECTED_COUNTS = {"destructive": 22, "mutation": 56, "overwrite": 2}
MISSION_DIR = Path(__file__).resolve().parents[1]
MAP_PATH = MISSION_DIR / "census-rekey-map.csv"

Site = tuple[str, str, int, str]  # (gate, rel, lineno, op)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_show(base: str, rel: str) -> str:
    return subprocess.run(["git", "show", f"{base}:{rel}"], check=True, capture_output=True, text=True).stdout


# ---------------------------------------------------------------------------
# Base (old) allowlists
# ---------------------------------------------------------------------------


def _allowlist_node(tree: ast.Module) -> ast.Dict:
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else (node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "_ALLOWLIST" and isinstance(node.value, ast.Dict):  # type: ignore[union-attr]
            return node.value  # type: ignore[union-attr]
    raise SystemExit("no module-level _ALLOWLIST dict found")


def old_allowlist(base: str, gate: str) -> tuple[str, ast.Dict, dict[str, str]]:
    source = git_show(base, GATES[gate][0])
    node = _allowlist_node(ast.parse(source))
    allowlist = ast.literal_eval(node)
    if not all(isinstance(k, str) for k in allowlist):
        raise SystemExit(f"{gate}: base _ALLOWLIST is not string-keyed at {base}")
    return source, node, allowlist


def split_old_key(key: str) -> tuple[str, int, str]:
    rel, lineno, op = key.rsplit(":", 2)
    return rel, int(lineno), op


# ---------------------------------------------------------------------------
# Head (new) gates
# ---------------------------------------------------------------------------


def import_head(head_root: Path) -> tuple[ModuleType, dict[str, ModuleType]]:
    sys.path[:0] = [str(head_root), str(head_root / "src")]
    census = importlib.import_module("tests.architectural._destructive_op_census")
    if not str(Path(census.__file__).resolve()).startswith(str(head_root.resolve())):
        raise SystemExit(f"imported census helper from {census.__file__}, not from --head-root {head_root}")
    gates = {gate: importlib.import_module(path[:-3].replace("/", ".")) for gate, (path, _finder) in GATES.items()}
    return census, gates


@dataclass
class Head:
    root: Path
    census: ModuleType
    gates: dict[str, ModuleType]

    def live_keys(self, gate: str, rel: str) -> dict[Any, int]:
        finder: Callable[[Path], list[tuple[int, str]]] = getattr(self.gates[gate], GATES[gate][1])
        path = self.root / rel
        return dict(self.census.census_keys(rel, path.read_text(encoding="utf-8"), finder(path)))


def assert_sources_unchanged(base: str, head_root: Path, rels: set[str]) -> None:
    changed = sorted(rel for rel in rels if (head_root / rel).read_text(encoding="utf-8") != git_show(base, rel))
    if changed:
        raise SystemExit(f"C-005 violated: censused source differs from {base}: {changed}")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def map_rows(base: str, head: Head) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gate in GATES:
        _src, _node, allowlist = old_allowlist(base, gate)
        for old_key, rationale in allowlist.items():
            rel, lineno, op = split_old_key(old_key)
            matches = [key for key, line in head.live_keys(gate, rel).items() if line == lineno and key.op == op]
            if len(matches) != 1:
                raise SystemExit(f"{gate}: {old_key} maps to {len(matches)} live key(s)")
            key = matches[0]
            rows.append(
                {
                    "gate": gate,
                    "old_key": old_key,
                    "rel": key.rel,
                    "qualname": key.qualname,
                    "token_line": key.token_line,
                    "op": key.op,
                    "op_ordinal": key.op_ordinal,
                    "rationale_sha256": sha256(rationale),
                }
            )
    return rows


def emit_map(base: str, head: Head) -> int:
    rows = map_rows(base, head)
    with MAP_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {MAP_PATH}")
    return 0


def _literal(key: Any) -> str:
    q = json.dumps
    return f"CensusKey(rel={q(key.rel)}, qualname={q(key.qualname)}, token_line={q(key.token_line)}, op={q(key.op)}, op_ordinal={key.op_ordinal})"


def emit_literals(base: str, head: Head, gate: str) -> int:
    source, node, _allowlist = old_allowlist(base, gate)
    by_old = {row["old_key"]: row for row in map_rows(base, head) if row["gate"] == gate}
    lines = source.splitlines(keepends=True)
    for key_node in sorted((k for k in node.keys if k is not None), key=lambda k: (k.lineno, k.col_offset), reverse=True):
        assert isinstance(key_node, ast.Constant) and key_node.lineno == key_node.end_lineno
        row = by_old[key_node.value]
        new = head.census.CensusKey(row["rel"], row["qualname"], row["token_line"], row["op"], row["op_ordinal"])
        line = lines[key_node.lineno - 1]
        lines[key_node.lineno - 1] = line[: key_node.col_offset] + _literal(new) + line[key_node.end_col_offset :]
    assert node.end_lineno is not None
    print("".join(lines[node.lineno - 1 : node.end_lineno]), end="")
    return 0


def old_sites(base: str) -> dict[Site, str]:
    sites: dict[Site, str] = {}
    for gate in GATES:
        for old_key, rationale in old_allowlist(base, gate)[2].items():
            rel, lineno, op = split_old_key(old_key)
            sites[(gate, rel, lineno, op)] = sha256(rationale)
    return sites


def check(base: str, head: Head, new_allowlists: Mapping[str, Mapping[Any, str]]) -> list[str]:
    """Return every equivalence violation (empty list = proof holds)."""
    problems: list[str] = []
    old = old_sites(base)
    new: dict[Site, str] = {}
    for gate, allowlist in new_allowlists.items():
        live: dict[str, dict[Any, int]] = {}
        for key, rationale in allowlist.items():
            if key.rel not in live:
                live[key.rel] = head.live_keys(gate, key.rel)
            lineno = live[key.rel].get(key)
            if lineno is None:
                problems.append(f"{gate}: {key} resolves to no live site")
                continue
            site = (gate, key.rel, lineno, key.op)
            if site in new:
                problems.append(f"{gate}: not a bijection -- two keys resolve to {site}")
            new[site] = sha256(rationale)
        count = len(allowlist)
        if count != EXPECTED_COUNTS[gate]:
            problems.append(f"{gate}: {count} keys, expected {EXPECTED_COUNTS[gate]}")
    problems += [f"exempted on base, not blessed at head: {site}" for site in sorted(set(old) - set(new))]
    problems += [f"blessed at head, not exempted on base: {site}" for site in sorted(set(new) - set(old))]
    problems += [f"rationale hash differs at {site}" for site in sorted(set(old) & set(new)) if old[site] != new[site]]
    return problems


def head_allowlists(head: Head) -> dict[str, dict[Any, str]]:
    return {gate: dict(module._ALLOWLIST) for gate, module in head.gates.items()}


def run_check(base: str, head: Head) -> int:
    allowlists = head_allowlists(head)
    assert_sources_unchanged(base, head.root, {key.rel for allowlist in allowlists.values() for key in allowlist})
    problems = check(base, head, allowlists)
    for gate, allowlist in allowlists.items():
        print(f"{gate}: {len(allowlist)} keys")
    total = sum(len(a) for a in allowlists.values())
    ordinal_1 = sum(1 for a in allowlists.values() for key in a if key.op_ordinal > 0)
    print(f"total: {total} keys; op_ordinal>0: {ordinal_1}; base sites: {len(old_sites(base))}")
    if problems:
        print("EQUIVALENCE FAILED:")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    print(f"EQUIVALENCE OK: {total}/{len(old_sites(base))} sites, bijection, rationale hashes equal (base {base})")
    return 0


def self_test(base: str, head: Head) -> int:
    pristine = head_allowlists(head)
    corruptions: dict[str, dict[str, dict[Any, str]]] = {}

    flipped = {g: dict(a) for g, a in pristine.items()}
    victim = next(k for k in flipped["mutation"] if k.op_ordinal == 0)
    flipped["mutation"][victim._replace(op_ordinal=1)] = flipped["mutation"].pop(victim)
    corruptions["flip one op_ordinal"] = flipped

    dropped = {g: dict(a) for g, a in pristine.items()}
    dropped["destructive"].pop(next(iter(dropped["destructive"])))
    corruptions["drop one key"] = dropped

    swapped = {g: dict(a) for g, a in pristine.items()}
    first, second = list(swapped["destructive"])[:2]
    swapped["destructive"][first], swapped["destructive"][second] = swapped["destructive"][second], swapped["destructive"][first]
    corruptions["swap one rationale"] = swapped

    failures = 0
    for label, allowlists in corruptions.items():
        problems = check(base, head, allowlists)
        verdict = "DETECTED" if problems else "MISSED"
        print(f"self-test [{label}]: {verdict} ({len(problems)} problem(s)){': ' + problems[0] if problems else ''}")
        failures += 0 if problems else 1
    if check(base, head, pristine):
        print("self-test: pristine allowlists do not pass the check")
        failures += 1
    print("SELF-TEST OK: all corruptions detected" if not failures else "SELF-TEST FAILED")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="3717c7ea")
    parser.add_argument("--head-root", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--emit-map", action="store_true")
    mode.add_argument("--emit-literals", choices=sorted(GATES))
    mode.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    head_root = args.head_root.resolve()
    census, gates = import_head(head_root)
    head = Head(head_root, census, gates)
    if args.emit_map:
        return emit_map(args.base, head)
    if args.emit_literals:
        return emit_literals(args.base, head, args.emit_literals)
    if args.self_test:
        return self_test(args.base, head)
    return run_check(args.base, head)


if __name__ == "__main__":
    raise SystemExit(main())
