"""Every commit SHA a Mission dossier's tool-written files record is classified (#7322).

Mission dossiers under ``kitty-specs/<mission>/`` record git commit SHAs as
evidence. Pull requests land on ``main`` by rebase merge, which rewrites every
commit, so most recorded SHAs name commits on the branch the Mission was built
on and are not ancestors of ``main`` afterwards. The archive freeze
(``test_archive_root_byte_identical.py``) then keeps those values byte-for-byte.

ADR ``docs/adr/4.x/2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance.md``
decides what such a value means: each SHA-valued field is classified once, in
:data:`DOSSIER_SHA_FIELDS` below, and a ``BRANCH_RELATIVE`` value is provenance of
the branch the work was built on. It is never repointed at "the rebased
equivalent" after landing and never needs a freeze exception. A ``LANDED`` value
names the commit on the target branch; its writer verifies it is an ancestor of
the target before it records it.

This gate keeps the classification complete. It walks every tool-written
dossier file on disk and fails when a SHA-valued key path is not classified, so a
writer that starts recording a new SHA field must classify it (and the ADR must
say what it means) in the same change. Hand-authored evidence files (research
notes, review evidence, ``issue-matrix.json`` ``evidence_ref`` prose) are outside
the registry: the ADR defines every SHA they cite as branch-relative by rule.

The registry lives here, beside the freeze's own exception sets, because its
only reader is this gate (``test_no_dead_symbols.py`` does not count test
callers, so a ``src/`` constant read only here would be dead).
"""

from __future__ import annotations

import enum
import json
import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]
KITTY_SPECS = REPO_ROOT / "kitty-specs"

#: A full-length git object id. Abbreviated SHAs are not matched: short hex runs
#: collide with ordinary values, and every tool writer records the full id.
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

#: Path segments that hold a work package id; normalised so one registry entry
#: covers every work package.
_WP_SEGMENT = re.compile(r"^WP\d+")


class ShaProvenance(enum.Enum):
    """What a recorded commit SHA is guaranteed to resolve to after landing."""

    #: Names a commit on the branch the Mission was built on (local ``HEAD``, a
    #: lane tip, a consolidation result, the target tip before consolidation).
    #: After a rebase merge it resolves only through the PR's head ref, if at
    #: all. Never repointed after landing.
    BRANCH_RELATIVE = "branch_relative"
    #: Names the commit on the target branch that landed the Mission. Its writer
    #: verifies it is an ancestor of the target before recording it.
    LANDED = "landed"


#: The tool-written dossier files the registry covers, as patterns over the path
#: relative to the Mission directory (``tasks/WP*/`` after normalisation).
TOOL_WRITTEN_FILES: frozenset[str] = frozenset(
    {
        "meta.json",
        "lanes.json",
        "status.json",
        "status.events.jsonl",
        "tasks/WP*/baseline-tests.json",
        "acceptance-matrix.json",
    }
)

#: Subtrees of a tool-written file that hold hand-authored evidence: no writer in
#: ``src/`` produces them, so the ADR defines every SHA inside as branch-relative
#: by rule and the walk does not descend into them.
HAND_AUTHORED_SUBTREES: frozenset[tuple[str, str]] = frozenset(
    {
        # Hand-added provenance notes in older acceptance matrices.
        ("acceptance-matrix.json", "evidence_provenance"),
    }
)

_BR = ShaProvenance.BRANCH_RELATIVE

#: The single classification of every SHA-valued key path in a tool-written
#: dossier file. Key paths join object keys with ``.``; ``[]`` marks a list
#: element and ``*`` a work package id. Moving a field to ``LANDED`` needs a
#: writer that verifies ancestry; adding a field needs an ADR line saying what
#: it means.
DOSSIER_SHA_FIELDS: Mapping[tuple[str, str], ShaProvenance] = {
    # consolidation/baseline.py: local HEAD after consolidation, and the target
    # tip before it, both written before the pull request exists. On the pull
    # request route baseline_merge_commit is the landing commit's first parent
    # (PrMergeEvidence), which is on the target; the field is mixed provenance,
    # so it stays branch-relative, the class that promises nothing.
    ("meta.json", "merged_commit"): _BR,
    ("meta.json", "baseline_merge_commit"): _BR,
    # consolidation/baseline.py (accept --mode pr --merge-commit,
    # migrate backfill-merge-commit): verify_pr_merge_evidence checks the
    # commit is on the target branch before it is stamped.
    ("meta.json", "pr_merge_commit"): ShaProvenance.LANDED,
    # mission_metadata.record_acceptance: the commit accept ran on and the one
    # it wrote.
    ("meta.json", "accept_commit"): _BR,
    ("meta.json", "accepted_from_commit"): _BR,
    ("meta.json", "acceptance_history[].accept_commit"): _BR,
    ("meta.json", "acceptance_history[].accepted_from_commit"): _BR,
    # mission_metadata.record_mission_base_sha (#7560): the commit the Mission
    # branch was cut from, written once at create; no ancestry check, so it
    # promises nothing about the target after landing.
    ("meta.json", "mission_base_sha"): _BR,
    # Hand-recorded keys in older dossiers; no writer in src/ today.
    ("meta.json", "move_task_extension_source_base"): _BR,
    ("meta.json", "pr_prep_base"): _BR,
    # lanes/compute_and_persist.py: the planning commit lanes were cut from.
    ("lanes.json", "planning_commit_sha"): _BR,
    # status/lane_head.py: the lane branch tip at each transition (append-only
    # log; consumed at consolidate time, before landing).
    ("status.events.jsonl", "policy_metadata.lane_head"): _BR,
    # status/transition_pipeline.py: the window-open SHA on a work package's
    # opening transition (wp_window, Mission consolidation-window-provenance-01M6Y84D);
    # provenance of the lane branch, valid for one consolidation attempt.
    ("status.events.jsonl", "policy_metadata.wp_window.open_sha"): _BR,
    # cli/commands/agent/tasks_move_task_gates.py via lanes/lane_invocation.py
    # (capture_evidence_tree, Mission lane-code-verification-01M76AC0, #7547):
    # the HEAD of the lane or write checkout the pre-review gate's verdict was
    # produced in; provenance of that branch at review time.
    ("status.events.jsonl", "policy_metadata.pre_review_gate.evidence_tree.head"): _BR,
    # Review references that happen to be commit ids.
    ("status.events.jsonl", "review_ref"): _BR,
    ("status.events.jsonl", "review_result.reference"): _BR,
    ("status.events.jsonl", "evidence.review.reference"): _BR,
    ("status.json", "work_packages.*.review_result.reference"): _BR,
    # review/baseline.py: the commit the baseline tests ran on (base_branch is
    # a raw SHA when the baseline was captured at a commit), plus hand-added
    # provenance keys in older captures.
    ("tasks/WP*/baseline-tests.json", "base_commit"): _BR,
    ("tasks/WP*/baseline-tests.json", "base_branch"): _BR,
    ("tasks/WP*/baseline-tests.json", "previous_capture.base_commit"): _BR,
    ("tasks/WP*/baseline-tests.json", "evidence_commits[]"): _BR,
    ("tasks/WP*/baseline-tests.json", "runtime_commits[]"): _BR,
    ("tasks/WP*/baseline-tests.json", "immutable_baseline.source_commit"): _BR,
    ("tasks/WP*/baseline-tests.json", "immutable_baseline.source_tree"): _BR,
    # acceptance/matrix.py _stamp_provenance and acceptance/post_consolidation.py:
    # the commit a negative invariant was verified at (a branch commit, or the
    # consolidation result).
    ("acceptance-matrix.json", "negative_invariants[].verified_ref"): _BR,
}

#: Non-vacuity floors for the real tree: the scan must see at least this many
#: distinct classified key paths and SHA values, or it is not reading dossiers.
_MIN_DISTINCT_KEY_PATHS = 8
_MIN_SHA_VALUES = 1000


def _normalise_file(relative: Path) -> str:
    return "/".join("WP*" if _WP_SEGMENT.match(part) else part for part in relative.parts)


def _sha_key_paths(node: object, prefix: str = "", skip: frozenset[str] = frozenset()) -> Iterator[str]:
    """Yield the key path of every full-SHA string inside a decoded JSON value.

    A key path in ``skip`` (a hand-authored subtree) is not descended into.
    """
    if prefix in skip:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            segment = "*" if _WP_SEGMENT.match(str(key)) else str(key)
            yield from _sha_key_paths(value, f"{prefix}.{segment}" if prefix else segment, skip)
    elif isinstance(node, list):
        for item in node:
            yield from _sha_key_paths(item, f"{prefix}[]", skip)
    elif isinstance(node, str) and _FULL_SHA.match(node):
        yield prefix


def _decoded_records(path: Path) -> Iterator[object]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        lines: Iterable[str] = (line for line in text.splitlines() if line.strip())
    else:
        lines = (text,)
    for line in lines:
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            # A corrupt record is the status / meta validators' finding, not
            # this gate's: it carries no key path to classify.
            continue


def scan_sha_fields(specs_root: Path) -> list[tuple[str, str, str]]:
    """Return ``(normalised file, key path, dossier-relative path)`` for every SHA value."""
    found: list[tuple[str, str, str]] = []
    if not specs_root.is_dir():
        return found
    for mission_dir in sorted(p for p in specs_root.iterdir() if p.is_dir()):
        for path in sorted(mission_dir.rglob("*")):
            if not path.is_file():
                continue
            normalised = _normalise_file(path.relative_to(mission_dir))
            if normalised not in TOOL_WRITTEN_FILES:
                continue
            where = path.relative_to(specs_root).as_posix()
            skip = frozenset(subtree for file, subtree in HAND_AUTHORED_SUBTREES if file == normalised)
            for record in _decoded_records(path):
                found.extend((normalised, key_path, where) for key_path in _sha_key_paths(record, skip=skip))
    return found


def unclassified(found: Iterable[tuple[str, str, str]], registry: Mapping[tuple[str, str], ShaProvenance]) -> dict[tuple[str, str], str]:
    """Map each unclassified ``(file, key path)`` to one dossier file that records it."""
    missing: dict[tuple[str, str], str] = {}
    for normalised, key_path, where in found:
        if (normalised, key_path) not in registry:
            missing.setdefault((normalised, key_path), where)
    return missing


def test_every_sha_field_in_tool_written_dossier_files_is_classified() -> None:
    found = scan_sha_fields(KITTY_SPECS)
    distinct = {(normalised, key_path) for normalised, key_path, _ in found}
    assert len(found) >= _MIN_SHA_VALUES and len(distinct) >= _MIN_DISTINCT_KEY_PATHS, (
        f"the scan saw {len(found)} SHA values over {len(distinct)} key paths under {KITTY_SPECS}; it is not reading the Mission dossiers"
    )
    missing = unclassified(found, DOSSIER_SHA_FIELDS)
    assert not missing, (
        "These tool-written dossier fields record a commit SHA but are not classified in "
        "DOSSIER_SHA_FIELDS. Classify each one and say what it means in ADR "
        "2026-11-07-1 (dossier commit SHAs are branch-relative provenance):\n"
        + "\n".join(f"  {file}: {key}  (e.g. kitty-specs/{where})" for (file, key), where in sorted(missing.items()))
    )


def test_registry_entries_name_tool_written_files() -> None:
    stray = sorted(file for file, _ in DOSSIER_SHA_FIELDS if file not in TOOL_WRITTEN_FILES)
    assert not stray, f"DOSSIER_SHA_FIELDS names files the scan never reads: {stray}"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_gate_reports_an_unclassified_sha_field(tmp_path: Path) -> None:
    """Self-mutation control: an unregistered SHA key in each file kind is reported."""
    sha = "a" * 40
    mission = tmp_path / "some-mission-01ABCDEF"
    _write(mission / "meta.json", json.dumps({"merged_commit": sha, "landed_somewhere": sha}))
    _write(mission / "status.events.jsonl", json.dumps({"policy_metadata": {"lane_head": sha, "new_head": sha}}) + "\nnot json\n")
    _write(mission / "tasks" / "WP03-thing" / "baseline-tests.json", json.dumps({"base_commit": sha, "extra": [sha]}))
    _write(mission / "status.json", json.dumps({"work_packages": {"WP02": {"review_result": {"reference": sha, "other": sha}}}}))
    _write(
        mission / "acceptance-matrix.json",
        json.dumps({"negative_invariants": [{"verified_ref": sha, "checked_at": sha}], "evidence_provenance": {"E-1": {"verified_ref": sha}}}),
    )
    # Hand-authored evidence is outside the registry and never reported.
    _write(mission / "research" / "notes.json", json.dumps({"base_sha": sha}))
    _write(mission / "issue-matrix.json", json.dumps({"rows": [{"evidence_ref": sha}]}))
    # Abbreviated and non-hex values are not SHAs.
    _write(mission / "lanes.json", json.dumps({"planning_commit_sha": sha, "short": "abc1234", "id": "01M6VJQ8EVKJ30JNE22MN46S92"}))

    missing = unclassified(scan_sha_fields(tmp_path), DOSSIER_SHA_FIELDS)

    assert set(missing) == {
        ("meta.json", "landed_somewhere"),
        ("status.events.jsonl", "policy_metadata.new_head"),
        ("tasks/WP*/baseline-tests.json", "extra[]"),
        ("status.json", "work_packages.*.review_result.other"),
        ("acceptance-matrix.json", "negative_invariants[].checked_at"),
    }


def test_removing_a_registry_entry_turns_the_real_tree_red() -> None:
    """Self-mutation control on the real tree: drop the busiest entry and the gate fires."""
    weakened = {key: value for key, value in DOSSIER_SHA_FIELDS.items() if key != ("status.events.jsonl", "policy_metadata.lane_head")}
    missing = unclassified(scan_sha_fields(KITTY_SPECS), weakened)
    assert ("status.events.jsonl", "policy_metadata.lane_head") in missing


def test_wp_window_open_sha_is_classified_branch_relative(tmp_path: Path) -> None:
    """FR-005: the window-open SHA a status row records is branch-relative provenance.

    The scan walks nested objects, so ``policy_metadata.wp_window.open_sha`` is
    reported by key path; a row that carries a gap records no SHA at all.
    """
    sha = "b" * 40
    rows = [
        {"policy_metadata": {"lane_head": sha, "wp_window": {"schema_version": 1, "open_sha": sha}}},
        {"policy_metadata": {"wp_window": {"schema_version": 1, "gap": {"reason": "lane_branch_missing", "detail": "x"}}}},
    ]
    _write(tmp_path / "some-mission-01ABCDEF" / "status.events.jsonl", "\n".join(json.dumps(row) for row in rows) + "\n")

    found = scan_sha_fields(tmp_path)

    assert ("status.events.jsonl", "policy_metadata.wp_window.open_sha") in {(file, key) for file, key, _ in found}
    assert unclassified(found, DOSSIER_SHA_FIELDS) == {}
    assert DOSSIER_SHA_FIELDS[("status.events.jsonl", "policy_metadata.wp_window.open_sha")] is ShaProvenance.BRANCH_RELATIVE
