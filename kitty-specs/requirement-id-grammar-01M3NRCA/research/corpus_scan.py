#!/usr/bin/env python3
"""NFR-001 compatibility-evidence corpus scan (WP08 / T035).

A standalone, deterministic, read-only scan comparing the requirement-ID
grammar's classification of the ``kitty-specs/*/spec.md`` and
``kitty-specs/*/tasks/WP*.md`` corpus between the mission's merge-base with
``upstream/main`` ("base") and the mission's branch head ("head").

Two modes:

* **Driver** (default): builds one shared, sorted file list from the head
  tree, spawns one worker subprocess per side (each with ``PYTHONPATH`` set
  to that side's ``src``), and writes ``corpus-scan.json`` (deterministic --
  no timestamps, no absolute temp paths) plus a markdown summary to
  ``--out-dir``.
* **Worker** (``--worker --side base|head --file-list <json> --corpus-root
  <head-tree> --expected-src <side-src>``): reads file CONTENT from the head
  tree and classifies it through the side's own
  ``specify_cli.requirement_mapping`` API (never a locally-defined
  requirement-ID regex), printing one JSON object to stdout.

Every classification goes through the tree under test's own API
(``find_bare_prose_requirement_ids``, ``lint_spec_requirement_ids``,
``parse_requirement_ids_from_spec_md``, ``read_all_wp_raw_requirement_refs``,
``grammar.classify``, ``compute_coverage``, and -- base side only --
``normalize_requirement_refs_value``) so the evidence measures the product,
not this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_WP_FILE_RE = re.compile(r"WP\d+")
_SPEC_GLOB = "kitty-specs/*/spec.md"
_WP_GLOB = "kitty-specs/*/tasks/WP*.md"

# The packages a worker may transitively import; recorded (relative to the
# side's src root, never as an absolute path) so a reviewer can see
# isolation held without the JSON output carrying a volatile /tmp prefix.
_TRACKED_PACKAGES = ("specify_cli", "runtime", "charter", "kernel")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, help="Head tree root (file CONTENT source for both sides).")
    parser.add_argument("--base-src", type=Path, help="Driver only: the merge-base worktree's src/ directory.")
    parser.add_argument("--head-src", type=Path, help="Driver only: the head tree's src/ directory.")
    parser.add_argument("--out-dir", type=Path, help="Driver only: scratch output directory.")
    parser.add_argument("--worker", action="store_true", help="Run in worker mode.")
    parser.add_argument("--side", choices=("base", "head"), help="Worker only: which side this worker measures.")
    parser.add_argument("--file-list", type=Path, help="Worker only: path to the shared JSON file list.")
    parser.add_argument("--expected-src", type=Path, help="Worker only: the src/ root this worker must resolve under.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.worker:
        return _run_worker(args)
    return _run_driver(args)


# --------------------------------------------------------------------------- #
# Driver: file-list construction
# --------------------------------------------------------------------------- #


def _discover_file_list(corpus_root: Path) -> list[str]:
    """Every ``kitty-specs/*/spec.md`` and ``kitty-specs/*/tasks/WP*.md``
    under *corpus_root*, as sorted, repo-relative POSIX paths."""
    specs = {p.relative_to(corpus_root).as_posix() for p in corpus_root.glob(_SPEC_GLOB)}
    wps = {p.relative_to(corpus_root).as_posix() for p in corpus_root.glob(_WP_GLOB)}
    return sorted(specs | wps)


def _hash_file_list(paths: list[str]) -> str:
    payload = json.dumps(paths, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()  # noqa: TID251 -- file-list integrity check, not a charter hash


# --------------------------------------------------------------------------- #
# Driver: subprocess orchestration
# --------------------------------------------------------------------------- #


def _spawn_worker(
    *,
    side: str,
    file_list_path: Path,
    corpus_root: Path,
    src_root: Path,
    tmp_dir: Path,
) -> dict[str, Any]:
    home = tmp_dir / f"home-{side}"
    home.mkdir(parents=True, exist_ok=True)
    cwd = tmp_dir / f"cwd-{side}"
    cwd.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(src_root),
        "HOME": str(home),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell, trusted interpreter
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--side",
            side,
            "--file-list",
            str(file_list_path),
            "--corpus-root",
            str(corpus_root),
            "--expected-src",
            str(src_root),
        ],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{side} worker failed (exit {completed.returncode}):\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")
    try:
        result: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{side} worker did not print valid JSON:\n{completed.stdout}") from exc
    return result


# --------------------------------------------------------------------------- #
# Driver: comparisons (a)-(d)
# --------------------------------------------------------------------------- #


def _compare_bare_prose(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """(a): the blocking bare-prose check, base vs. head."""
    base_flagged: dict[str, list[str]] = base["bare_prose"]
    head_flagged: dict[str, list[str]] = head["bare_prose"]
    return {
        "base_count": len(base_flagged),
        "head_count": len(head_flagged),
        "verdict": "PASS" if len(head_flagged) <= len(base_flagged) else "FAIL",
        "base_flagged": base_flagged,
        "head_flagged": head_flagged,
        "newly_flagged": {path: ids for path, ids in head_flagged.items() if path not in base_flagged},
        "no_longer_flagged": {path: ids for path, ids in base_flagged.items() if path not in head_flagged},
    }


def _compare_lint_refusals(head: dict[str, Any]) -> dict[str, Any]:
    """(b): planning hand-off refusals -- head only (base predates the lint)."""
    lint = head["lint"]
    refused = {path: entry["errors"] for path, entry in lint.items() if entry["errors"]}
    return {"refused_count": len(refused), "refused": refused}


def _compare_declared_growth(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """(c): declared-ID set growth (and shrinkage) per spec."""
    base_declared: dict[str, list[str]] = base["declared"]
    head_declared: dict[str, list[str]] = head["declared"]
    growth: dict[str, list[str]] = {}
    shrink: dict[str, list[str]] = {}
    for path in sorted(set(base_declared) | set(head_declared)):
        before = set(base_declared.get(path, []))
        after = set(head_declared.get(path, []))
        added = sorted(after - before)
        removed = sorted(before - after)
        if added:
            growth[path] = added
        if removed:
            shrink[path] = removed
    return {"growth": growth, "shrink": shrink}


def _pair_wp_tokens(base_tokens: list[str], head_tokens: list[str]) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """Positionally pair *base_tokens* with *head_tokens* (both sides tokenise
    the same raw frontmatter value). Returns (pairs, orphan_base, orphan_head)."""
    pair_count = min(len(base_tokens), len(head_tokens))
    pairs = list(zip(base_tokens[:pair_count], head_tokens[:pair_count], strict=True))
    return pairs, base_tokens[pair_count:], head_tokens[pair_count:]


def _wp_transition_entries(base_wps: dict[str, Any], head_wps: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for mission_dir in sorted(set(base_wps) | set(head_wps)):
        base_mission = base_wps.get(mission_dir, {"wps": {}})
        head_mission = head_wps.get(mission_dir, {"wps": {}})
        base_mission_wps: dict[str, list[dict[str, Any]]] = base_mission["wps"]
        head_mission_wps: dict[str, list[dict[str, Any]]] = head_mission["wps"]
        for wp_id in sorted(set(base_mission_wps) | set(head_mission_wps)):
            base_records = base_mission_wps.get(wp_id, [])
            head_records = head_mission_wps.get(wp_id, [])
            base_tokens = [r["token"] for r in base_records]
            head_tokens = [r["token"] for r in head_records]
            pairs, orphan_base, orphan_head = _pair_wp_tokens(base_tokens, head_tokens)
            for index, (base_token, head_token) in enumerate(pairs):
                # Load-bearing, not defensive: both sides tokenise the SAME raw
                # frontmatter value (base via the legacy split regex, head via
                # grammar.tokenize_refs), so positional pairing is only valid
                # when the tokens actually agree. A mismatch here would mean
                # the two readers disagree about tokenisation itself, which
                # would silently corrupt every downstream transition -- fail
                # loudly instead (review cycle 1, reviewer-renata).
                assert base_token == head_token, (  # noqa: S101 -- evidence-integrity guard, not a test
                    f"{mission_dir} {wp_id}: base/head token mismatch at pairing index {index}: "
                    f"base={base_token!r} head={head_token!r} -- the two sides tokenised differently"
                )
                entries.append(
                    {
                        "mission": mission_dir,
                        "wp_id": wp_id,
                        "token": base_token,
                        "before": base_records[index]["verdict"],
                        "respelled_to": base_records[index].get("respelled_to"),
                        "after": head_records[index]["verdict"],
                    }
                )
            if orphan_base or orphan_head:
                entries.append(
                    {
                        "mission": mission_dir,
                        "wp_id": wp_id,
                        "token": None,
                        "before": f"orphan_base_tokens:{orphan_base}",
                        "after": f"orphan_head_tokens:{orphan_head}",
                    }
                )
    return entries


#: The one transition that is not a change at all: a ref already valid under
#: the old (known-ref) gate stays valid under the new (accepted) one. Review
#: Guidance / T036 section 5 names this the "unchanged case" and excludes it
#: from the full item list -- the label differs (before/after use different
#: vocabularies) but nothing about the ref's admissibility moved.
_UNCHANGED_TRANSITION_KEY = "kept/known -> accepted"


def _compare_wp_transitions(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """(d): before -> after transition matrix over every raw WP ref token."""
    entries = _wp_transition_entries(base["wp_refs"], head["wp_refs"])
    matrix: dict[str, int] = {}
    changed: list[dict[str, Any]] = []
    for entry in entries:
        key = f"{entry['before']} -> {entry['after']}"
        matrix[key] = matrix.get(key, 0) + 1
        if key != _UNCHANGED_TRANSITION_KEY:
            changed.append(entry)
    return {"matrix": matrix, "changed": changed, "total_tokens_compared": len(entries)}


def _mission_coverage_classification(base_unmapped: set[str], head_unmapped: set[str]) -> tuple[str, list[str], list[str]]:
    """One mission's (e) classification from its base/head unmapped-FR sets.

    Returns ``(classification, newly_unmapped_ids, newly_mapped_ids)``.
    ``newly_unmapped_ids`` = ``head_unmapped - base_unmapped`` (a functional
    ID the finalize-tasks coverage gate did not flag at base but does at
    head -- the class this section exists to surface, per the pre-PR squad
    finding: (c) only diffs the *declared*-ID set, never checks whether a
    newly-declared functional ID actually has a WP mapped to it).
    ``newly_mapped_ids`` = ``base_unmapped - head_unmapped`` (the reverse:
    an ID the gate used to flag that head now covers).
    """
    newly_unmapped = sorted(head_unmapped - base_unmapped)
    newly_mapped = sorted(base_unmapped - head_unmapped)
    if not newly_unmapped and not newly_mapped:
        return "unchanged", newly_unmapped, newly_mapped
    if newly_unmapped and newly_mapped:
        return "mixed", newly_unmapped, newly_mapped
    if newly_unmapped:
        return "newly_unmapped", newly_unmapped, newly_mapped
    return "newly_mapped", newly_unmapped, newly_mapped


def _compare_coverage_verdict(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """(e): the finalize-tasks coverage verdict per mission, base vs. head.

    (c) only diffs the *declared*-functional-ID set per spec; it never asks
    whether a newly-declared functional ID actually has a WP ref mapped to
    it. This section closes that gap by running each side's OWN
    ``compute_coverage`` (imported from that side's
    ``specify_cli.requirement_mapping``; never re-implemented here, C-008)
    over that side's own raw WP ``requirement_refs`` mapping and that side's
    own declared-functional-ID set -- both already computed once per mission
    by the worker's ``_scan_mission_wp_refs`` and carried in ``wp_refs``, so
    this driver-side comparison is pure set arithmetic over the two sides'
    ``unmapped_functional`` lists.
    """
    base_wps: dict[str, Any] = base["wp_refs"]
    head_wps: dict[str, Any] = head["wp_refs"]
    changed: dict[str, Any] = {}
    counts = {"unchanged": 0, "newly_unmapped": 0, "newly_mapped": 0, "mixed": 0}
    for mission_dir in sorted(set(base_wps) | set(head_wps)):
        base_unmapped = set(base_wps.get(mission_dir, {}).get("coverage", {}).get("unmapped_functional", []))
        head_unmapped = set(head_wps.get(mission_dir, {}).get("coverage", {}).get("unmapped_functional", []))
        classification, newly_unmapped_ids, newly_mapped_ids = _mission_coverage_classification(base_unmapped, head_unmapped)
        counts[classification] += 1
        if classification != "unchanged":
            changed[mission_dir] = {
                "classification": classification,
                "base_unmapped": sorted(base_unmapped),
                "head_unmapped": sorted(head_unmapped),
                "newly_unmapped_ids": newly_unmapped_ids,
                "newly_mapped_ids": newly_mapped_ids,
            }
    return {
        "unchanged_count": counts["unchanged"],
        "newly_unmapped_count": counts["newly_unmapped"],
        "newly_mapped_count": counts["newly_mapped"],
        "mixed_count": counts["mixed"],
        "changed": changed,
    }


# --------------------------------------------------------------------------- #
# Driver: assembly + output
# --------------------------------------------------------------------------- #


def _isolation_summary(side_result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": side_result["isolation_ok"], "resolved": side_result["resolved_relative"]}


def _build_report(
    *,
    base: dict[str, Any],
    head: dict[str, Any],
    file_list: list[str],
    file_list_hash: str,
    base_sha: str,
    head_sha: str,
) -> dict[str, Any]:
    spec_count = sum(1 for p in file_list if p.endswith("/spec.md"))
    wp_count = sum(1 for p in file_list if _WP_FILE_RE.search(Path(p).name))
    return {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "file_list_count": len(file_list),
        "spec_count": spec_count,
        "wp_count": wp_count,
        "file_list_hash": file_list_hash,
        "isolation": {"base": _isolation_summary(base), "head": _isolation_summary(head)},
        "bare_prose": _compare_bare_prose(base, head),
        "lint_refusals": _compare_lint_refusals(head),
        "declared_growth": _compare_declared_growth(base, head),
        "wp_ref_transitions": _compare_wp_transitions(base, head),
        "coverage_verdict": _compare_coverage_verdict(base, head),
    }


def _summary_markdown(report: dict[str, Any]) -> str:
    bp = report["bare_prose"]
    lint = report["lint_refusals"]
    growth = report["declared_growth"]
    trans = report["wp_ref_transitions"]
    coverage = report["coverage_verdict"]
    lines = [
        "# corpus-scan summary",
        "",
        f"- base SHA: `{report['base_sha']}`",
        f"- head SHA: `{report['head_sha']}`",
        f"- file list: {report['file_list_count']} files ({report['spec_count']} specs, {report['wp_count']} WP files), hash `{report['file_list_hash']}`",
        "",
        "## (a) bare prose",
        f"- base={bp['base_count']} head={bp['head_count']} verdict={bp['verdict']}",
        "",
        "## (b) lint refusals (head only)",
        f"- refused_count={lint['refused_count']}",
        "",
        "## (c) declared-ID growth",
        f"- specs with growth: {len(growth['growth'])}",
        f"- specs with shrink: {len(growth['shrink'])}",
        "",
        "## (d) WP ref transitions",
        f"- total tokens compared: {trans['total_tokens_compared']}",
        f"- changed: {len(trans['changed'])}",
        f"- matrix: {json.dumps(trans['matrix'], sort_keys=True)}",
        "",
        "## (e) coverage verdict (compute_coverage, base vs. head)",
        f"- unchanged={coverage['unchanged_count']} newly_unmapped={coverage['newly_unmapped_count']} "
        f"newly_mapped={coverage['newly_mapped_count']} mixed={coverage['mixed_count']}",
        f"- changed missions: {sorted(coverage['changed'])}",
        "",
    ]
    return "\n".join(lines)


_EGRESS_SPEC_PATH = "kitty-specs/egress-refusal-consolidation-3110-01KYW895/spec.md"
_EGRESS_EXPECTED_IDS = {"C-1", "C-3"}

#: Pre-PR squad finding (MEDIUM): a `finalize-tasks --validate-only` run
#: against this mission was independently confirmed to exit 1 with
#: `unmapped_functional_requirements: ["FR-004a"]` at head. (e) must
#: reproduce that exact result through `compute_coverage`, never a
#: locally-defined check.
_COVERAGE_POSITIVE_CONTROL_MISSION = "kitty-specs/operator-config-ergonomics-01M04YK8"
_COVERAGE_POSITIVE_CONTROL_ID = "FR-004a"


def _assert_floors(report: dict[str, Any]) -> None:
    """Test Strategy: a collapsed/broken detector must not silently report
    a clean corpus. Raises loudly instead of emitting a partial report."""
    bp = report["bare_prose"]
    egress_base = set(bp["base_flagged"].get(_EGRESS_SPEC_PATH, []))
    egress_head = set(bp["head_flagged"].get(_EGRESS_SPEC_PATH, []))
    if not _EGRESS_EXPECTED_IDS.issubset(egress_base):
        raise RuntimeError(
            f"(a) floor failed: base side does not flag {_EGRESS_SPEC_PATH} with {_EGRESS_EXPECTED_IDS} (got {egress_base}) -- scan is broken, not a clean corpus"
        )
    if not _EGRESS_EXPECTED_IDS.issubset(egress_head):
        raise RuntimeError(f"(a) SC-005 positive control failed: head side does not flag {_EGRESS_SPEC_PATH} with {_EGRESS_EXPECTED_IDS} (got {egress_head})")

    lint = report["lint_refusals"]
    if lint["refused_count"] < 1:
        raise RuntimeError("(b) floor failed: zero refusals at head -- the lint was not really invoked")

    matrix = report["wp_ref_transitions"]["matrix"]
    dropped_to_accepted = matrix.get("dropped -> accepted", 0)
    if dropped_to_accepted < 1:
        raise RuntimeError("(d) floor failed: zero 'dropped -> accepted' transitions -- the head classification did not run")

    coverage = report["coverage_verdict"]
    operator_config = coverage["changed"].get(_COVERAGE_POSITIVE_CONTROL_MISSION)
    if operator_config is None or _COVERAGE_POSITIVE_CONTROL_ID not in operator_config["newly_unmapped_ids"]:
        raise RuntimeError(
            f"(e) floor failed: {_COVERAGE_POSITIVE_CONTROL_MISSION} does not newly-unmap "
            f"{_COVERAGE_POSITIVE_CONTROL_ID} (CLI-confirmed positive control) -- got {operator_config}"
        )


def _run_driver(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root).resolve()
    base_src = Path(args.base_src).resolve()
    head_src = Path(args.head_src).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if base_src == head_src:
        raise RuntimeError(f"--base-src and --head-src resolve to the same tree ({base_src}) -- isolation would be unproven, not merely unexercised")

    file_list = _discover_file_list(corpus_root)
    file_list_hash = _hash_file_list(file_list)
    file_list_path = out_dir / "file-list.json"
    file_list_path.write_text(json.dumps(file_list, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    base_sha = _git_head_sha(base_src.parent)
    head_sha = _git_head_sha(corpus_root)

    base_result = _spawn_worker(side="base", file_list_path=file_list_path, corpus_root=corpus_root, src_root=base_src, tmp_dir=out_dir / "tmp")
    head_result = _spawn_worker(side="head", file_list_path=file_list_path, corpus_root=corpus_root, src_root=head_src, tmp_dir=out_dir / "tmp")

    report = _build_report(
        base=base_result,
        head=head_result,
        file_list=file_list,
        file_list_hash=file_list_hash,
        base_sha=base_sha,
        head_sha=head_sha,
    )
    _assert_floors(report)

    (out_dir / "corpus-scan.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (out_dir / "corpus-scan.summary.md").write_text(_summary_markdown(report) + "\n", encoding="utf-8")
    print(_summary_markdown(report))
    return 0


def _git_head_sha(worktree_root: Path) -> str:
    completed = subprocess.run(  # noqa: S603, S607 -- fixed argv, no shell
        ["git", "rev-parse", "HEAD"], cwd=str(worktree_root), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


# --------------------------------------------------------------------------- #
# Worker: import isolation
# --------------------------------------------------------------------------- #


def _resolved_relative(module_file: str, expected_src: Path) -> str:
    resolved = Path(module_file).resolve()
    try:
        return resolved.relative_to(expected_src).as_posix()
    except ValueError:
        return f"OUTSIDE_EXPECTED_SRC:{resolved.name}"


def _check_import_isolation(expected_src: Path) -> tuple[bool, dict[str, str | None]]:
    import specify_cli

    resolved: dict[str, str | None] = {}
    ok = True
    for package_name in _TRACKED_PACKAGES:
        try:
            module = specify_cli if package_name == "specify_cli" else __import__(package_name)
        except ImportError:
            resolved[package_name] = None
            continue
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            resolved[package_name] = None
            continue
        rel = _resolved_relative(module_file, expected_src)
        resolved[package_name] = rel
        if rel.startswith("OUTSIDE_EXPECTED_SRC:"):
            ok = False
    return ok, resolved


# --------------------------------------------------------------------------- #
# Worker: per-spec scan (a)/(b)/(c)
# --------------------------------------------------------------------------- #


def _scan_spec(content: str, side: str) -> dict[str, Any]:
    from specify_cli.requirement_mapping import find_bare_prose_requirement_ids, parse_requirement_ids_from_spec_md

    candidates = find_bare_prose_requirement_ids(content)
    flagged_ids: list[str] = []
    for candidate in candidates:
        for requirement_id in candidate.ids:
            if requirement_id not in flagged_ids:
                flagged_ids.append(requirement_id)

    declared = parse_requirement_ids_from_spec_md(content)["all"]

    lint_entry: dict[str, Any]
    if side == "head":
        from specify_cli.requirement_mapping.lint import lint_spec_requirement_ids

        result = lint_spec_requirement_ids(content)
        lint_entry = {
            "errors": [e.as_dict() for e in result.errors],
            "warnings_count": len(result.warnings),
        }
    else:
        lint_entry = {"errors": [], "warnings_count": 0, "not_available": True}

    return {"flagged_ids": flagged_ids, "declared": declared, "lint": lint_entry}


# --------------------------------------------------------------------------- #
# Worker: per-mission WP ref classification (d)
# --------------------------------------------------------------------------- #


def _classify_wp_token_base(token: str, declared: set[str]) -> dict[str, Any]:
    """The 'before' (base) classification (FR-019 precursor).

    ``verdict`` is a stable bucket label (never fragmented by the specific
    respelled value, so the transition matrix stays small); the actual
    respelled string, when there is one, rides separately in ``respelled_to``.

    ``normalize_requirement_refs_value`` exists only on the merge-base tree
    (WP01 deleted it at head once every product caller moved to the raw
    reader); this worker only runs this function in ``--side base`` mode, so
    a dynamic ``importlib`` lookup is used instead of a static ``from``
    import -- a static import would make ``mypy --strict`` (run against the
    head tree's ``specify_cli.requirement_mapping``, which no longer exports
    this name) fail even though the code is only ever exercised on the base
    side.
    """
    import importlib

    module = importlib.import_module("specify_cli.requirement_mapping")
    normalize_requirement_refs_value = module.normalize_requirement_refs_value
    normalized: list[str] = normalize_requirement_refs_value([token])
    respelled_to: str | None = None
    if not normalized:
        bucket = "dropped"
    elif normalized == [token]:
        bucket = "kept"
    else:
        bucket = "kept_respelled"
        respelled_to = normalized[0]
    known = "known" if (normalized and normalized[0] in declared) else "unknown"
    verdict = bucket if bucket == "dropped" else f"{bucket}/{known}"
    return {"token": token, "verdict": verdict, "respelled_to": respelled_to}


def _classify_wp_token_head(token: str, declared: set[str]) -> dict[str, Any]:
    from specify_cli.requirement_mapping import grammar

    verdict_obj = grammar.classify(token, declared)
    verdict = "accepted" if isinstance(verdict_obj, grammar.Accepted) else f"rejected:{verdict_obj.reason}"
    return {"token": token, "verdict": verdict}


def _scan_mission_wp_refs(mission_dir: str, corpus_root: Path, side: str) -> dict[str, Any]:
    from specify_cli.requirement_mapping import (
        compute_coverage,
        parse_requirement_ids_from_spec_md,
        read_all_wp_raw_requirement_refs,
    )

    tasks_dir = corpus_root / mission_dir / "tasks"
    spec_path = corpus_root / mission_dir / "spec.md"
    spec_missing = not spec_path.is_file()
    declared: set[str] = set()
    functional_ids: set[str] = set()
    if not spec_missing:
        parsed_spec_ids = parse_requirement_ids_from_spec_md(spec_path.read_text(encoding="utf-8"))
        declared = set(parsed_spec_ids["all"])
        functional_ids = set(parsed_spec_ids["functional"])

    raw_refs = read_all_wp_raw_requirement_refs(tasks_dir)
    classifier = _classify_wp_token_base if side == "base" else _classify_wp_token_head
    wps: dict[str, list[dict[str, Any]]] = {}
    for wp_id, tokens in raw_refs.items():
        wps[wp_id] = [classifier(token, declared) for token in tokens]

    # (e): this side's own `compute_coverage` over this side's own raw
    # `requirement_refs` mapping and this side's own declared-functional-ID
    # set -- the same inputs `map-requirements`/`finalize-tasks` feed it,
    # just read from the corpus rather than a live run.
    coverage = compute_coverage(raw_refs, functional_ids)

    return {
        "spec_missing": spec_missing,
        "declared": sorted(declared),
        "wps": wps,
        "coverage": {
            "functional_ids": sorted(functional_ids),
            "unmapped_functional": coverage["unmapped_functional"],
        },
    }


def _group_wp_paths_by_mission(wp_paths: list[str]) -> dict[str, list[str]]:
    by_mission: dict[str, list[str]] = {}
    for path in wp_paths:
        # kitty-specs/<mission>/tasks/WP##-*.md -> mission dir is parts[1].
        parts = Path(path).parts
        mission_dir = "/".join(parts[:2])
        by_mission.setdefault(mission_dir, []).append(path)
    return by_mission


# --------------------------------------------------------------------------- #
# Worker: entrypoint
# --------------------------------------------------------------------------- #


def _run_worker(args: argparse.Namespace) -> int:
    expected_src = Path(args.expected_src).resolve()
    isolation_ok, resolved_relative = _check_import_isolation(expected_src)
    if not isolation_ok:
        print(json.dumps({"error": "import isolation violated", "resolved": resolved_relative}), file=sys.stderr)
        return 1

    corpus_root = Path(args.corpus_root).resolve()
    file_list: list[str] = json.loads(Path(args.file_list).read_text(encoding="utf-8"))
    spec_paths = [p for p in file_list if p.endswith("/spec.md")]
    wp_paths = [p for p in file_list if p != "" and p not in spec_paths]

    bare_prose: dict[str, list[str]] = {}
    declared: dict[str, list[str]] = {}
    lint: dict[str, dict[str, Any]] = {}
    for rel_path in spec_paths:
        content = (corpus_root / rel_path).read_text(encoding="utf-8")
        scanned = _scan_spec(content, args.side)
        if scanned["flagged_ids"]:
            bare_prose[rel_path] = scanned["flagged_ids"]
        declared[rel_path] = scanned["declared"]
        lint[rel_path] = scanned["lint"]

    wp_refs: dict[str, Any] = {}
    for mission_dir in sorted(_group_wp_paths_by_mission(wp_paths)):
        wp_refs[mission_dir] = _scan_mission_wp_refs(mission_dir, corpus_root, args.side)

    output = {
        "side": args.side,
        "isolation_ok": isolation_ok,
        "resolved_relative": resolved_relative,
        "bare_prose": bare_prose,
        "declared": declared,
        "lint": lint if args.side == "head" else "not_available",
        "wp_refs": wp_refs,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
