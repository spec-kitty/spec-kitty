"""Historical preservation gate (M1 NFR-002, WP12 FR-007-011).

The four fixed exclusion roots (``DM-01M0P6C8C7Q6SPBT412V39RPN0``) are immutable
historical-record surfaces:

* ``kitty-specs/`` — archived mission dossiers,
* ``.kittify/mission-state-audit/quarantine/`` — quarantined migration state,
* ``kitty-ops/`` — repo-ops history,
* ``.kittify/missions/`` — mission-state history.

M1's editorial freeze endures; its operator decision also permits runtime
appends. Only the exact lifecycle log may extend a preserved byte prefix.
Unsigned suffix validation establishes format, not cryptographic authenticity.
WP11's independently reviewed recovery has exact Git provenance, output pins
AND current read-only canonical replay. It is not a general snapshot exception.
The separate dead-port recovery below binds one additional output to public-main
inputs and independently reviewed blob/receipt pins; it does not repin WP11.
Both index and working tree are checked against merge-base(HEAD, main), where
``main`` is resolved against THIS repository's own remote (by URL), never
blindly against whatever ref the local clone happens to call ``origin/main``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from specify_cli.invocation.errors import LegacyRecordError
from specify_cli.invocation.lifecycle import LIFECYCLE_LOG_RELATIVE_PATH
from specify_cli.invocation.record import OpCompletedEvent, ProfileInvocationRecord, parse_op_event
from specify_cli.invocation.writer import OP_CLOSURES_RELATIVE_PATH
from specify_cli.missions._archive import ARCHIVE_REGISTRY_RELPATH
from specify_cli.status.reducer import materialize_snapshot, materialize_to_json

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

# The convergence-port base ref. The upstream mission base is not an ancestor of
# this repository's main, so comparing it directly would blame pre-existing fork
# deletions on M1. The merge-base with main is the exact pre-port EXP tree.
#
# WHICH clone's "main" is load-bearing (#4365): the base must be the merge-base
# against THIS repository's own main, resolved by remote URL — never blindly
# ``origin/main``. In a fork-based contributor clone ``origin`` is the fork
# (e.g. Priivacy-ai/spec-kitty) and this repository is ``upstream``; a detached
# worktree at upstream/main then diffs against a merge-base that predates
# already-merged archive history, and merged-but-post-base rewrites of archived
# dossiers render as fresh ``ordinary archive history changed`` violations —
# the false positive that filed #4365 (the gate was green in this repository's
# own CI at every sha that issue named). Candidate order: the remote(s) whose
# configured URL names this repository, ``origin`` first among them; the legacy
# ``origin/main`` stays last so a fork-only clone with no canonical remote
# keeps its previous behaviour.
_CANONICAL_REPO_SLUG = "spec-kitty/spec-kitty"
_LEGACY_PORT_BASE_REF = "origin/main"
# Recorded in-place rewrites of already-archived dossiers in main history —
# #4365's "what mutates archived artifacts". The one genuine event is
# 583f3bb888 ("docs: use canonical Team Kitty host and redact retired
# references", #4260, merged 2026-09-13): a deliberate, merged redaction sweep
# that rewrote archived mission dossiers across (at least)
# per-project-sync-consent-ledgers-01KZKMQZ,
# setup-plan-auth-diagnostics-nonfatal-01M0QEAD,
# home-pin-census-owner-adoption-01M05C50 and
# operator-config-ergonomics-01M04YK8. It merged without this gate ever
# running — the heavy architectural battery is code-scoped, so a docs-only PR
# pays for neither it nor a code shard — which is why the always-on
# ``archive-freeze`` CI job (`.github/workflows/ci-router.yml`) now runs this
# file on every PR shape. The event is recorded here, not re-litigated and not
# re-baselined: an edit that has merged is inside the baseline by
# construction, and this gate protects the review frontier (unmerged branch
# edits), which is the only thing a diff-against-main gate can protect.

# The four fixed exclusion / immutable-archive roots.
# #4928: the mission-state repair quarantine moved from the gitignored
# ``.kittify/migrations/mission-state/quarantine/`` to the git-TRACKED
# ``.kittify/mission-state-audit/quarantine/``. It stays an immutable-archive
# root here (repointed, not removed): the quarantine holds VERBATIM evicted
# event rows — historical snapshots that must not be byte-mutated. The repair
# MANIFEST (``.kittify/mission-state-audit/*.json``) is deliberately NOT frozen
# — it is ordinary operator-committed, reviewable content.
_ARCHIVE_ROOTS: tuple[str, ...] = (
    "kitty-specs/",
    ".kittify/mission-state-audit/quarantine/",
    "kitty-ops/",
    ".kittify/missions/",
)

# Append-only exceptions carved out of the immutable-archive freeze
# (2026-08-28, mission charter-authority-flip-01M14RB3 landing pass, #3664):
# the canonical rename-reconcile spine (``scripts/docs/rename_reconcile.py``'s
# ``DEFAULT_OCCURRENCE_MAP``) lives under ``kitty-specs/`` but is a *living*
# cross-mission registry, NOT a frozen proof artifact — every doc-rename
# mission is REQUIRED to append its move here or the ``build`` job's
# rename-reconcile gate reds (see main's own ``docs(landing): declare docs/plans
# curation moves on the reconcile spine`` and ``docs(plans): register the
# domains/ plan moves on the canonical rename-reconcile spine``). Appending a
# new move line is this file's designed use, not the "editing an archived
# artifact to fix a stale line" that NFR-002 forbids, so it is exempt from the
# byte-freeze while every other pre-existing archived file stays frozen.
# NOTE: the exemption is a whole-path carve-out (any mutation of this one file
# passes, not strictly an append) -- its content integrity is independently
# policed by the build job's rename-reconcile gate, so a destructive rewrite
# here would red there, not slip through silently.
_APPEND_ONLY_SPINE_EXCEPTIONS: frozenset[str] = frozenset({"kitty-specs/common-docs-convergence-01KZMTR9/occurrence_map.yaml"})

# Operator-sanctioned one-off CORRECTIONS of an archived file (distinct from the
# living-spine carve-out above — these are not appends and not living registries).
# The freeze protects the review frontier (unmerged edits) against diff-vs-main;
# a genuine correction of an archived file that is itself CORRUPT can only land
# through an explicit operator decision recorded here, because the always-on
# archive-freeze job (ci-router.yml) now blocks the merge that would otherwise
# make the correction baseline-by-construction.
#
# - kitty-specs/acceptance-matrix-merge-fail-closed-01M34HG8/status.json
#   (2026-09-23, operator decision during the #4936 / epic #4915 landing pass):
#   #4880's mission artifacts committed this status.json to main with UNRESOLVED
#   git conflict markers (`<<<<<<< HEAD` … `=======` … `>>>>>>>`) — a CORRUPT_JSON
#   teamspace blocker. It went unnoticed because the upgrade module shard (whose
#   corpus scan flags it) is path-filtered and #4880 touched no upgrade paths;
#   #4936's #4888 change un-skips that shard, surfacing the pre-existing
#   corruption on this innocent PR. The correction resolves the markers to the
#   populated side (event_count 24, real slug) — the HEAD side was a blank reset.
#   Follow-up: once this correction is in main's baseline, this entry is dead
#   weight and should be removed to restore the byte-freeze on the corrected file.
_OPERATOR_SANCTIONED_CORRECTIONS: frozenset[str] = frozenset({"kitty-specs/acceptance-matrix-merge-fail-closed-01M34HG8/status.json"})


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "SPEC_KITTY_ENABLE_SAAS_SYNC": "0"},
    )


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        check=False,
        env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0", "SPEC_KITTY_ENABLE_SAAS_SYNC": "0"},
    )
    assert result.returncode == 0, f"Git preservation read failed {args!r}: {result.stderr!r}"
    return result.stdout


@dataclass(frozen=True)
class Blob:
    mode: str
    oid: str
    kind: str = "blob"

    def read(self) -> bytes:
        assert self.kind == "blob", f"{self.oid}: non-blob protected input"
        return _git_bytes("cat-file", "blob", self.oid)


def _tree(rev: str, *paths: str) -> dict[str, Blob]:
    result: dict[str, Blob] = {}
    for row in _git_bytes("ls-tree", "-rz", rev, "--", *paths).split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            mode, kind, oid = header.decode("ascii").split()
            name = os.fsdecode(path)
            if name.startswith(_ARCHIVE_ROOTS) or name in {root.rstrip("/") for root in _ARCHIVE_ROOTS}:
                assert kind == "blob", f"{name}: non-blob historical entry"
            # Keep unrelated Gitlinks visible without imposing archive policy.
            result[name] = Blob(mode, oid, kind)
    return result


def _index() -> dict[str, Blob]:
    result: dict[str, Blob] = {}
    for row in _git_bytes("ls-files", "--stage", "-z").split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            mode, oid, stage = header.decode("ascii").split()
            assert stage == "0", f"{os.fsdecode(path)}: unmerged index"
            result[os.fsdecode(path)] = Blob(mode, oid, "commit" if mode == "160000" else "blob")
    return result


def _confined(path: str) -> Path:
    relative = Path(path)
    assert not relative.is_absolute() and ".." not in relative.parts, f"{path}: unsafe path"
    current = REPO_ROOT
    for part in relative.parts[:-1]:
        current = current / part
        assert current.is_dir() and not current.is_symlink(), f"{path}: unsafe parent {current}"
    return current / relative.name


def _disk(path: str, mode: str) -> bytes:
    candidate = _confined(path)
    assert candidate.exists() or candidate.is_symlink(), f"{path}: missing file"
    observed = candidate.lstat()
    assert stat.S_ISREG(observed.st_mode), f"{path}: regular-file kind required"
    actual_mode = "100755" if observed.st_mode & stat.S_IXUSR else "100644"
    assert mode in {"100644", "100755"} and actual_mode == mode, f"{path}: mode changed"
    return candidate.read_bytes()


def _changes(base: str, *, cached: bool = False) -> list[tuple[str, tuple[str, ...]]]:
    """Unscoped NUL view: retain both endpoints, regardless of rename detection."""
    args = ["diff", "--name-status", "-z", "--no-ext-diff"]
    if cached:
        args.append("--cached")
    rows = iter(_git_bytes(*args, base, "--").split(b"\0"))
    changes = []
    for row in rows:
        if row:
            status = row.decode("ascii")
            count = 2 if status.startswith(("R", "C")) else 1
            paths = tuple(os.fsdecode(next(rows)) for _ in range(count))
            changes.append((status, paths))
    return changes


def _lifecycle_prefix(path: str, before: bytes, after: bytes) -> None:
    if after == before:
        return
    assert after.startswith(before), f"{path}: historical byte prefix changed"
    assert not before or before.endswith(b"\n"), f"{path}: unterminated historical boundary"
    suffix = after[len(before) :]
    assert suffix.endswith(b"\n"), f"{path}: incomplete suffix record"
    for number, row in enumerate(suffix[:-1].split(b"\n"), 1):
        try:
            data = json.loads(row.decode("utf-8"))
            assert isinstance(data, dict), "record must be an object"
            ProfileInvocationRecord.from_dict(data)
        except (UnicodeError, ValueError, KeyError, TypeError, AssertionError) as error:
            raise AssertionError(f"{path}: invalid suffix row {number}: {error}") from error


def _check_lifecycle(baseline: dict[str, Blob], index: dict[str, Blob]) -> None:
    path = LIFECYCLE_LOG_RELATIVE_PATH.as_posix()
    if path not in baseline:
        return
    old = baseline[path]
    assert path in index, f"{path}: deleted or renamed in index"
    assert index[path].mode == old.mode, f"{path}: index mode changed"
    before = old.read()
    _lifecycle_prefix(path, before, index[path].read())
    _lifecycle_prefix(path, before, _disk(path, old.mode))


def _op_closure_suffix(path: str, before: bytes, after: bytes) -> None:
    """Validate appended rows on the Op-closure spine as v2 completed events.

    The spine (``kitty-ops/op-closures.jsonl``, #4397) is the one sanctioned
    mutable surface for doctor-sweep Op closures: per-record ``kitty-ops/``
    files stay byte-frozen, so the sweep records each closure as a new
    append-only line here. The historical byte prefix must be preserved and
    every suffix row must be a valid v2 ``OpCompletedEvent`` — a rewrite or a
    legacy/malformed row fails exactly like a tampered lifecycle log.
    """
    if after == before:
        return
    assert after.startswith(before), f"{path}: historical byte prefix changed"
    assert not before or before.endswith(b"\n"), f"{path}: unterminated historical boundary"
    suffix = after[len(before) :]
    assert suffix.endswith(b"\n"), f"{path}: incomplete suffix record"
    for number, row in enumerate(suffix[:-1].split(b"\n"), 1):
        try:
            data = json.loads(row.decode("utf-8"))
            assert isinstance(data, dict), "record must be an object"
            event = parse_op_event(data)
            assert isinstance(event, OpCompletedEvent), "closure row must be a completed event"
        except (UnicodeError, ValueError, KeyError, TypeError, AssertionError, LegacyRecordError) as error:
            raise AssertionError(f"{path}: invalid suffix row {number}: {error}") from error


def _check_op_closures(baseline: dict[str, Blob], index: dict[str, Blob]) -> None:
    path = OP_CLOSURES_RELATIVE_PATH.as_posix()
    if path not in baseline:
        return
    old = baseline[path]
    assert path in index, f"{path}: deleted or renamed in index"
    assert index[path].mode == old.mode, f"{path}: index mode changed"
    before = old.read()
    _op_closure_suffix(path, before, index[path].read())
    _op_closure_suffix(path, before, _disk(path, old.mode))


def _json_object(raw: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _status_event_prefix(path: str, before: bytes, after: bytes) -> None:
    assert after.startswith(before), f"{path}: historical byte prefix changed"
    assert before.endswith(b"\n") and after.endswith(b"\n"), f"{path}: incomplete event boundary"
    suffix = after[len(before) :]
    assert suffix, f"{path}: terminal transition added no events"
    for line in suffix.splitlines():
        _json_object(line)


def _terminal_lifecycle_paths(  # noqa: C901 - fail-closed evidence validation is linear
    baseline: dict[str, Blob], index: dict[str, Blob]
) -> set[str]:
    """Admit one canonical active-to-terminal transition, never proof edits."""
    admitted: set[str] = set()
    mission_dirs = {path.rsplit("/", 1)[0] for path in baseline if path.startswith("kitty-specs/") and path.endswith("/meta.json")}
    for directory in mission_dirs:
        names = {name: f"{directory}/{name}" for name in ("meta.json", "status.events.jsonl", "status.json")}
        if not all(path in baseline and path in index for path in names.values()):
            continue
        try:
            old_meta = _json_object(baseline[names["meta.json"]].read())
            new_meta = _json_object(index[names["meta.json"]].read())
            old_status = _json_object(baseline[names["status.json"]].read())
            mission_id = old_meta.get("mission_id")
            if not isinstance(mission_id, str) or not mission_id:
                continue
            if old_meta.get("mission_number") is not None:
                continue
            old_packages = old_status.get("work_packages")
            if not isinstance(old_packages, dict) or not old_packages:
                continue
            if all(isinstance(row, dict) and row.get("lane") == "done" for row in old_packages.values()):
                continue
            registry = baseline.get(ARCHIVE_REGISTRY_RELPATH.as_posix())
            if registry is not None and any(_json_object(line).get("mission_id") == mission_id for line in registry.read().splitlines() if line):
                continue

            changed_meta = {key for key in old_meta.keys() | new_meta.keys() if old_meta.get(key) != new_meta.get(key)}
            if not changed_meta or not changed_meta <= {"baseline_merge_commit", "mission_number"}:
                continue
            if not isinstance(new_meta.get("mission_number"), int) or new_meta["mission_number"] <= 0:
                continue
            merge_commit = new_meta.get("baseline_merge_commit")
            if not isinstance(merge_commit, str) or len(merge_commit) != 40:
                continue

            events_path = names["status.events.jsonl"]
            before = baseline[events_path].read()
            after = index[events_path].read()
            _status_event_prefix(events_path, before, after)
            current_dir = REPO_ROOT / directory
            canonical = materialize_to_json(materialize_snapshot(current_dir)).encode("utf-8")
            status_path = names["status.json"]
            if canonical != index[status_path].read():
                continue
            new_status = _json_object(canonical)
            packages = new_status.get("work_packages")
            if not isinstance(packages, dict) or not packages or not all(isinstance(row, dict) and row.get("lane") == "done" for row in packages.values()):
                continue
            if str(new_meta["mission_number"]) != new_status.get("mission_number"):
                continue
            if any(index[path].read() != _disk(path, index[path].mode) for path in names.values()):
                continue
        except (AssertionError, KeyError, OSError, TypeError, ValueError):
            continue
        admitted.update(names.values())
    return admitted


# WP11 independent review, persisted by parent event 01M1VMFHA7K9XJAK0Y2MJR6NRV.
# These commits and this digest are trust inputs, never taken from the candidate.
ORIGINAL = "c0054153b9bce0778cf41a85d11ecd4e9650031d"
SOURCE = "3442ca1afc20b1b83b27a7bc64fd7014050b12a1"
CONVERGENCE = "2554bd13adc289d3457681308645fe52619bca0e"
RED_RECEIPT = "13e75ffd06434e02b0ddd578b7047f22506bc917"
RESTORED = "3cb4af0ccce9a3b8db73e03fb37149d62bf3ef53"
RECOVERED = "8e2d40bc0cbf607eea3af97ae9a80e82f18ee8f4"
RECEIPT = "docs/archive/program-evidence/upgrade-preview-mission-health-01M1V6E1/recovery-receipt.json"
RECEIPT_SHA256 = "f320ada834fbabcddd7186147d606551dcecf066dad4c4eef182eafcf0a7f4b8"
CYCLIC = "kitty-specs/reject-cyclic-lane-graphs-01M0QCK4"
CYCLIC_FILES = frozenset(
    {
        ".kittify/dossiers/reject-cyclic-lane-graphs-01M0QCK4/snapshot-latest.json",
        "acceptance-matrix.json",
        "adversarial-review.md",
        "analysis-report.md",
        "checklists/requirements.md",
        "contracts/lane-dependency-cycle.schema.json",
        "data-model.md",
        "decisions/DM-01M0QCNTD5CM0SE0HKQ79C9NF6.md",
        "decisions/DM-01M0QDJWKXD5JHSVHV0NWSJDWM.md",
        "decisions/DM-01M0QEAKZVM8QAVZPF9AE6D1N8.md",
        "decisions/index.json",
        "issue-matrix.json",
        "lanes.json",
        "meta.json",
        "mission-review.md",
        "plan.md",
        "pr-summary.md",
        "quickstart.md",
        "research.md",
        "retrospective.yaml",
        "spec.md",
        "status.events.jsonl",
        "status.json",
        "tasks.md",
        "tasks/.gitkeep",
        "tasks/README.md",
        "tasks/WP01-authoritative-domain-cycle-gate.md",
        "tasks/WP01-authoritative-domain-cycle-gate/review-cycle-1.md",
        "tasks/WP01-authoritative-domain-cycle-gate/review-cycle-2.md",
        "tasks/WP01-authoritative-domain-cycle-gate/review-feedback-1.md",
        "tasks/WP02-finalization-diagnostics-and-persistence.md",
        "tasks/WP03-determinism-performance-and-regression.md",
    }
)
OLD_BUNDLE = "kitty-specs/R2-T1-local-legacy-removal"
NEW_BUNDLE = "docs/archive/program-evidence/R2-T1-local-legacy-removal"
SPINE = "kitty-specs/common-docs-convergence-01KZMTR9/occurrence_map.yaml"
SNAPSHOTS = (
    "kitty-specs/doctrine-drg-silent-drop-boundary-01M0PE7E/status.json",
    "kitty-specs/symbolkey-source-module-01M0B0SF/status.json",
    CYCLIC + "/status.json",
)
MOVES = tuple(
    (f"{OLD_BUNDLE}/{name}", f"{NEW_BUNDLE}/{name}")
    for name in (
        "deletion-manifest.md",
        "commit-history-notes.md",
    )
)


def _reviewed_receipt() -> dict[str, Any]:
    raw = _git_bytes("show", f"{RECOVERED}:{RECEIPT}")
    assert _sha256(raw) == RECEIPT_SHA256, f"{RECEIPT}: reviewed receipt pin"
    result: dict[str, Any] = json.loads(raw)
    return result


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()  # noqa: TID251 - exact file-integrity digest, not charter semantic hashing


def _exact_candidate(path: str, expected: Blob, index: dict[str, Blob]) -> bytes:
    assert index.get(path) == expected, f"{path}: tracked index blob/mode differs from reviewed proof"
    raw = _disk(path, expected.mode)
    assert raw == expected.read(), f"{path}: reviewed bytes changed"
    return raw


def _recovery_present(baseline: dict[str, Blob], index: dict[str, Blob]) -> bool:
    if RECEIPT in baseline or RECEIPT in index or (REPO_ROOT / RECEIPT).is_symlink():
        return True
    # Deleting all outputs together must not erase the admission's obligations.
    return _run_git(["merge-base", "--is-ancestor", RECOVERED, "HEAD"]).returncode == 0


def _historical_restoration(receipt: dict[str, Any]) -> dict[str, Blob]:
    source = _tree(SOURCE, CYCLIC)
    assert source.keys() == {f"{CYCLIC}/{name}" for name in CYCLIC_FILES}, f"{CYCLIC}: historical path membership"
    assert source == _tree(CONVERGENCE + "^1", CYCLIC), f"{CYCLIC}: convergence source history"
    schema = CYCLIC + "/contracts/lane-dependency-cycle.schema.json"
    assert _tree(CONVERGENCE, CYCLIC) == {schema: source[schema]}, f"{CYCLIC}: convergence deletion proof"
    assert _tree(ORIGINAL, CYCLIC) == {schema: source[schema]}, f"{CYCLIC}: retained schema proof"
    assert source[schema].oid == "26cb3b8bafde72894f0d1ec0a9c1701cd511f497"
    assert source == _tree(RESTORED, CYCLIC), f"{CYCLIC}: restoration before replay differs"
    entries = receipt["restores"]
    assert sorted(entry["path"] for entry in entries) == sorted(source.keys() - {schema})
    for entry in [*entries, receipt["retained_schema"]]:
        old = source[entry["path"]]
        assert (old.oid, old.mode, _sha256(old.read())) == (
            entry["blob"],
            entry["mode"],
            entry["sha256"],
        ), f"{entry['path']}: historical receipt provenance"
    assert _tree(RED_RECEIPT, CYCLIC) == {schema: source[schema]}, f"{CYCLIC}: RED chronology"
    return source


def _check_snapshot(path: str, index: dict[str, Blob], receipt: dict[str, Any]) -> None:
    source = SOURCE if path == SNAPSHOTS[2] else ORIGINAL
    directory = path.rsplit("/", 1)[0]
    before = _tree(source, directory)
    reviewed = _tree(RECOVERED, directory)
    # Every historical input, including annotations and metadata, stays exact.
    assert before.keys() == reviewed.keys(), f"{path}: reviewed input membership"
    for name, old in before.items():
        if name != path:
            assert reviewed[name] == old, f"{name}: reviewed history changed"
            _exact_candidate(name, old, index)
    candidate = _exact_candidate(path, reviewed[path], index)
    entry = receipt["restored_mission_replay"] if source == SOURCE else next(entry for entry in receipt["replays"] if entry["path"] == path)
    assert before[path].oid == entry["before_blob"], f"{path}: original snapshot OID"
    assert _sha256(candidate) == entry["after_sha256"], f"{path}: reviewed output hash"
    # Read-only owner composition; never materialize/save/repair the candidate.
    canonical = materialize_to_json(materialize_snapshot(REPO_ROOT / directory)).encode("utf-8")
    assert canonical == candidate, f"{path}: canonical replay differs from reviewed output"
    old_snapshot = json.loads(before[path].read())
    snapshot = json.loads(candidate)
    assert snapshot["work_packages"].keys() == old_snapshot["work_packages"].keys()
    for wp, old_state in old_snapshot["work_packages"].items():
        state = snapshot["work_packages"][wp]
        for key in ("review_result", "lane", "force_count", "last_event_id", "last_transition_at", "actor", "agent"):
            assert state.get(key) == old_state.get(key), f"{path}: {wp} historical {key} changed"
        assert state["lane"] == "done" and state["review_result"]["verdict"] == "approved"


def _check_relocations(index: dict[str, Blob], receipt: dict[str, Any]) -> None:
    assert sorted((entry["from"], entry["to"]) for entry in receipt["relocations"]) == sorted(MOVES)
    for old, new in MOVES:
        source = _tree(ORIGINAL, old)[old]
        entry = next(entry for entry in receipt["relocations"] if entry["from"] == old)
        assert entry["to"] == new and source.oid == entry["blob"], f"{old}: relocation provenance"
        assert _tree(entry["introduction_commit"], old)[old] == source, f"{old}: introduction proof"
        assert old not in index, f"{old}: relocation source still tracked"
        assert not (REPO_ROOT / old).exists(), f"{old}: relocation source still present"
        _exact_candidate(new, source, index)
    assert not (REPO_ROOT / OLD_BUNDLE).exists() and not (REPO_ROOT / OLD_BUNDLE).is_symlink(), f"{OLD_BUNDLE}: residual source directory or alias"


def _check_recovery(index: dict[str, Blob]) -> set[str]:
    receipt = _reviewed_receipt()
    trusted = _tree(RECOVERED, RECEIPT, NEW_BUNDLE, SPINE, CYCLIC, *SNAPSHOTS)
    _exact_candidate(RECEIPT, trusted[RECEIPT], index)
    source = _historical_restoration(receipt)
    assert {p for p in index if p.startswith(CYCLIC + "/")} == source.keys(), f"{CYCLIC}: index inventory differs"
    disk_paths = {str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / CYCLIC).rglob("*") if not p.is_dir()}
    assert disk_paths == source.keys(), f"{CYCLIC}: disk inventory differs: {sorted(disk_paths ^ source.keys())}"
    for path, old in source.items():
        expected = trusted[path] if path == SNAPSHOTS[2] else old
        _exact_candidate(path, expected, index)
    for path in SNAPSHOTS:
        _check_snapshot(path, index, receipt)
    _check_relocations(index, receipt)
    _exact_candidate(NEW_BUNDLE + "/README.md", trusted[NEW_BUNDLE + "/README.md"], index)
    # Preserve the reviewed prefix/rows while retaining the separate spine policy
    # for subsequent additions. No candidate-controlled receipt can change it.
    prefix = trusted[SPINE].read()
    assert prefix == _git_bytes("show", f"{ORIGINAL}:{SPINE}") + receipt["occurrence_map"]["append_only_delta"].encode()
    assert SPINE in index and index[SPINE].mode == trusted[SPINE].mode, f"{SPINE}: tracked mode changed"
    assert index[SPINE].read().startswith(prefix), f"{SPINE}: reviewed navigation prefix changed in index"
    assert _disk(SPINE, trusted[SPINE].mode).startswith(prefix), f"{SPINE}: reviewed navigation prefix changed"
    return {*SNAPSHOTS, *(old for old, _ in MOVES)}


# PR4082's independently reviewed one-snapshot recovery. The source is public
# main, and output/receipt are content pins: no topic commit must survive squash.
_DEAD_PORT_SOURCE = "f2be03af4889c89184fdb3a4aeb90fc3f90b3a87"
_DEAD_PORT_DIR = "kitty-specs/dead-port-disposition-01M1VRA2"
_DEAD_PORT_STATUS = _DEAD_PORT_DIR + "/status.json"
_DEAD_PORT_BEFORE = "341d7cf81db9232425ee315de9b72752ae8a4498"
_DEAD_PORT_AFTER = Blob("100644", "5c39a554f0958c22bfc8ffc3f2fcfd38023c0287")
_DEAD_PORT_SHA256 = "9c904f5b83cf02140b57e205e63e496c2bef7c556969acd50ed7399f62575e26"
_DEAD_PORT_RECEIPT = "docs/archive/program-evidence/upgrade-preview-mission-health-01M1V6E1/dead-port-snapshot-recovery.json"
_DEAD_PORT_RECEIPT_BLOB = Blob("100644", "654362863ebe86c9ecf604abc1a2bca1a2491c5a")
_DEAD_PORT_RECEIPT_SHA256 = "d8c6e48518b99d2f77834c1f2ec1296106af8cb25db48dbe4f9aad003f7c1c68"


def _dead_port_recovery_present(baseline: dict[str, Blob], index: dict[str, Blob]) -> bool:
    receipt = REPO_ROOT / _DEAD_PORT_RECEIPT
    if _DEAD_PORT_RECEIPT in baseline or _DEAD_PORT_RECEIPT in index or receipt.exists() or receipt.is_symlink():
        return True
    # Baseline activation survives deleting both outputs after landing. The
    # untouched historical snapshots remain subject only to ordinary byte freeze.
    return any(_DEAD_PORT_STATUS in tree and tree[_DEAD_PORT_STATUS].oid == _DEAD_PORT_AFTER.oid for tree in (baseline, index))


def _check_dead_port_recovery(index: dict[str, Blob]) -> set[str]:
    receipt = _exact_candidate(_DEAD_PORT_RECEIPT, _DEAD_PORT_RECEIPT_BLOB, index)
    assert _sha256(receipt) == _DEAD_PORT_RECEIPT_SHA256, "dead-port reviewed receipt digest"
    source = _tree(_DEAD_PORT_SOURCE, _DEAD_PORT_DIR)
    assert source[_DEAD_PORT_STATUS].oid == _DEAD_PORT_BEFORE, "dead-port original snapshot provenance"
    indexed = {path for path in index if path.startswith(_DEAD_PORT_DIR + "/")}
    disk = {path.relative_to(REPO_ROOT).as_posix() for path in (REPO_ROOT / _DEAD_PORT_DIR).rglob("*") if not path.is_dir() or path.is_symlink()}
    assert indexed == source.keys(), "dead-port index input inventory changed"
    assert disk == source.keys(), "dead-port disk input inventory changed"
    for path, expected in source.items():
        if path != _DEAD_PORT_STATUS:
            _exact_candidate(path, expected, index)
    candidate = _exact_candidate(_DEAD_PORT_STATUS, _DEAD_PORT_AFTER, index)
    assert _sha256(candidate) == _DEAD_PORT_SHA256, "dead-port reviewed output digest"
    canonical = materialize_to_json(materialize_snapshot(REPO_ROOT / _DEAD_PORT_DIR)).encode("utf-8")
    assert candidate == canonical, "dead-port canonical replay differs from reviewed output"
    before, after = _json_object(source[_DEAD_PORT_STATUS].read()), _json_object(candidate)
    for key in ("event_count", "last_event_id", "materialized_at", "mission_slug", "summary"):
        assert before[key] == after[key], f"dead-port historical {key} changed"
    assert before["work_packages"].keys() == after["work_packages"].keys(), "dead-port WP membership changed"
    for wp, state in before["work_packages"].items():
        for key in ("review_result", "lane", "force_count", "last_event_id", "last_transition_at", "actor", "agent"):
            assert state.get(key) == after["work_packages"][wp].get(key), f"dead-port {wp} historical {key} changed"
    return {_DEAD_PORT_STATUS}


def _files_under_roots_at(rev: str) -> set[str]:
    """Every tracked file under an archive root at ``rev``."""
    return {path for path in _tree(rev) if any(path.startswith(root) for root in _ARCHIVE_ROOTS)}


def _remote_repo_slug(url: str) -> str:
    """The ``owner/repo`` slug a remote URL names, across checkout shapes.

    Accepts the https, ssh and scp-style spellings a checkout of this
    repository can carry — ``https://github.com/spec-kitty/spec-kitty.git``,
    the exe fleet's ``github.int.exe.xyz`` proxy form,
    ``git@github.com:spec-kitty/spec-kitty.git`` — and reduces any of them to
    the trailing ``owner/repo`` path segments, so host, port, credentials and
    a ``.git`` suffix never change the answer. Returns ``""`` for a URL too
    short to name an owner/repo pair.
    """
    text = url.strip().rstrip("/")
    if text.endswith(".git"):
        text = text[: -len(".git")]
    if "://" in text:
        text = text.split("://", 1)[1]
    elif ":" in text:
        # scp-style git@host:owner/repo — no scheme to strip, one separator.
        text = text.replace(":", "/", 1)
    segments = [segment for segment in text.split("/") if segment]
    if len(segments) < 2:
        return ""
    return "/".join(segments[-2:])


def _live_remote_urls() -> dict[str, str]:
    """Configured remote URLs, by remote name.

    Read through ``git config --get`` rather than ``git remote get-url``: the
    configured URL is the clone's own declaration of where it came from, and a
    machine-local ``url.<base>.insteadOf`` transport rewrite must never re-home
    which repository a clone names (the same rule
    ``specify_cli.zeitgeist_client.repo_identity`` applies to origin identity).
    """
    urls: dict[str, str] = {}
    for name in _run_git(["remote"]).stdout.split():
        url = _run_git(["config", "--get", f"remote.{name}.url"]).stdout.strip()
        if url:
            urls[name] = url
    return urls


def _select_port_base_refs(remotes: dict[str, str]) -> list[str]:
    """Port-base candidates: canonical remote(s) first, legacy ref last.

    ``origin`` leads the canonical remotes when it is one, so the fleet's
    proxy-URL clone and a GitHub Actions checkout keep using ``origin/main``
    exactly as before. Only a clone whose ``origin`` is a fork re-homes to the
    remote that actually names this repository.
    """
    canonical = [name for name, url in remotes.items() if _remote_repo_slug(url) == _CANONICAL_REPO_SLUG]
    ordered = sorted(canonical, key=lambda name: (name != "origin", name))
    candidates = [f"{name}/main" for name in ordered]
    if _LEGACY_PORT_BASE_REF not in candidates:
        candidates.append(_LEGACY_PORT_BASE_REF)
    return candidates


def _port_base_candidate_refs() -> list[str]:
    return _select_port_base_refs(_live_remote_urls())


def _port_base_rev() -> str | None:
    for ref in _port_base_candidate_refs():
        result = _run_git(["merge-base", "HEAD", ref])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


def _require_port_base_rev() -> str:
    """Return the EXP port base, failing closed under CI when it is absent."""
    port_base_rev = _port_base_rev()
    if port_base_rev is not None:
        return port_base_rev
    message = f"EXP port base (merge-base HEAD {' or '.join(_port_base_candidate_refs())!r}) is not reachable; archive freeze cannot run"
    if os.environ.get("CI") == "true":
        pytest.fail(message)
    pytest.skip(message)


def test_no_preexisting_archived_file_was_modified() -> None:
    """Default freeze plus evidence-bound lifecycle and recovery operations."""
    port_base_rev = _require_port_base_rev()
    baseline = _tree(port_base_rev)
    assert any(path.startswith(_ARCHIVE_ROOTS) for path in baseline), "empty archive baseline"
    index = _index()
    _check_lifecycle(baseline, index)
    _check_op_closures(baseline, index)
    admitted = _check_recovery(index) if _recovery_present(baseline, index) else set()
    if _dead_port_recovery_present(baseline, index):
        admitted |= _check_dead_port_recovery(index)
    admitted |= _terminal_lifecycle_paths(baseline, index)
    violations: list[str] = []
    for status, paths in [*_changes(port_base_rev), *_changes(port_base_rev, cached=True)]:
        for path in paths:
            if not path.startswith(_ARCHIVE_ROOTS) or path in _APPEND_ONLY_SPINE_EXCEPTIONS or path in _OPERATOR_SANCTIONED_CORRECTIONS:
                continue
            if path == LIFECYCLE_LOG_RELATIVE_PATH.as_posix() and status == "M":
                continue
            # #4397: the Op-closure spine is the append-only surface for
            # doctor-sweep closures; a prefix-preserving append is validated
            # structurally by ``_check_op_closures`` above.
            if path == OP_CLOSURES_RELATIVE_PATH.as_posix() and status == "M":
                continue
            if path in admitted:
                continue
            if status == "A" and path not in baseline:
                continue
            violations.append(f"{status}\t{path}: ordinary archive history changed")
    assert not violations, "Historical preservation violation under the four archive roots:\n  " + "\n  ".join(sorted(set(violations)))


def test_archive_baseline_is_non_empty() -> None:
    """Anti-vacuity floor: the archive roots are non-empty at the base, so the
    byte-identity assertion above is scanning real content, not nothing."""
    assert _files_under_roots_at(_require_port_base_rev()), (
        "no tracked files found under the archive roots at the EXP port base — the byte-identity gate would pass vacuously"
    )


def test_remote_repo_slug_matches_every_checkout_shape() -> None:
    """The slug matcher is checkout-shape independent (#4365).

    Host (github.com or the exe fleet proxy), scheme, port, credentials and a
    ``.git`` suffix must never change which repository a URL names — and a
    fork of this repository must never match the canonical slug.
    """
    for url in (
        "https://github.com/spec-kitty/spec-kitty.git",
        "https://github.com/spec-kitty/spec-kitty",
        "https://github.int.exe.xyz/spec-kitty/spec-kitty.git",
        "https://user:token@github.com/spec-kitty/spec-kitty.git",
        "ssh://git@github.com:22/spec-kitty/spec-kitty.git",
        "git@github.com:spec-kitty/spec-kitty.git",
    ):
        assert _remote_repo_slug(url) == _CANONICAL_REPO_SLUG, url
    assert _remote_repo_slug("git@github.com:Priivacy-ai/spec-kitty.git") == "Priivacy-ai/spec-kitty"
    assert _remote_repo_slug("https://github.com/spec-kitty/spec-kitty-saas.git") == "spec-kitty/spec-kitty-saas"
    assert _remote_repo_slug("") == ""
    assert _remote_repo_slug("https://github.com") == ""


def test_port_base_candidates_prefer_this_repository_over_a_fork_origin() -> None:
    """#4365's filing shape: ``origin`` is a fork, ``upstream`` is this repo.

    A detached worktree at this repository's main must diff against THIS
    repository's main, so the canonical remote's ref leads the candidate list
    and the fork's ``origin/main`` is demoted to the legacy fallback behind it.
    """
    remotes = {
        "origin": "git@github.com:Priivacy-ai/spec-kitty.git",
        "upstream": "https://github.com/spec-kitty/spec-kitty.git",
    }
    assert _select_port_base_refs(remotes) == ["upstream/main", "origin/main"]


def test_port_base_candidates_put_origin_first_when_origin_is_canonical() -> None:
    """A checkout whose ``origin`` already names this repository is unchanged."""
    remotes = {
        "fork": "git@github.com:Priivacy-ai/spec-kitty.git",
        "origin": "https://github.int.exe.xyz/spec-kitty/spec-kitty.git",
        "upstream": "https://github.com/spec-kitty/spec-kitty.git",
    }
    assert _select_port_base_refs(remotes) == ["origin/main", "upstream/main"]


def test_port_base_candidates_keep_the_legacy_ref_in_a_fork_only_clone() -> None:
    """No configured remote names this repository: the fork's main stands."""
    assert _select_port_base_refs({"origin": "git@github.com:someone/spec-kitty.git"}) == ["origin/main"]
    assert _select_port_base_refs({}) == ["origin/main"]


def test_live_port_base_resolves_when_a_canonical_remote_is_configured() -> None:
    """In a checkout that names this repository, the port base is reachable."""
    canonical = [name for name, url in _live_remote_urls().items() if _remote_repo_slug(url) == _CANONICAL_REPO_SLUG]
    if not canonical:
        pytest.skip("no configured remote points at this repository (fork-only clone)")
    assert _port_base_rev() is not None


def test_archive_freeze_gate_uses_the_exp_port_base_without_import_time_skip() -> None:
    """NFR-002 must execute in an EXP checkout instead of silently skipping.

    This is deliberately structural: decorators are evaluated while this module
    imports, before a test body could exercise the guard's runtime fallback.
    """
    module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    assigned_names = {target.id for node in module.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}
    guarded = {"test_no_preexisting_archived_file_was_modified", "test_archive_baseline_is_non_empty"}
    guarded_nodes = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in guarded}

    assert "_MISSION" + "_BASE_REV" not in assigned_names
    assert guarded_nodes.keys() == guarded, "protected gate function missing"
    assert all(
        not any(
            isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "skipif" for decorator in node.decorator_list
        )
        for node in guarded_nodes.values()
    )
