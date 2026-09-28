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
import logging
import os
import re
import stat
import subprocess
import sys
import warnings
from collections.abc import Callable
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
#
# - kitty-specs/coord-read-fail-closed-01M38VVH/status.json
#   kitty-specs/silent-write-hardening-residuals-01M37QN4/status.json
#   (2026-09-25, operator decision during the #4972 upgrade-stamping landing pass):
#   both landed with a SNAPSHOT_DRIFT teamspace blocker — the committed status.json
#   never caught up to the authoritative status.events.jsonl (coord: snapshot stale
#   at 19 events vs 24 in the log; silent-write: the empty bootstrap snapshot vs 18
#   events). Same surfacing path as the acceptance-matrix entry above: the upgrade
#   module shard's corpus scan (test_public_witnesses.py :: ...no_teamspace_blockers)
#   is path-filtered on main, and #4972 touches upgrade paths, un-skipping it. The
#   correction regenerates each status.json from its event log via the reducer
#   (materialize) — events are the sole authority and the materialized timestamps
#   derive from them, so the result is deterministic and reduce(events)==persisted.
#   Follow-up: once in main's baseline, these entries are dead weight and should be
#   removed to restore the byte-freeze on the corrected files.
#
# - kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md
#   (2026-09-27, operator decision during the #4957 landing pass): the archived
#   file carried UNRESOLVED git conflict markers (`<<<<<<< HEAD` … `=======` …
#   `>>>>>>>`) at lines 758/773, surfaced by mission #4957 (this mission) —
#   the same defect class the #4880/#4936 precedent and #4972 landings above
#   addressed. The correction resolves the markers to the `HEAD` side (the
#   lineage confirmed an ancestor of `main` via `git merge-base --is-ancestor
#   df2dac046 main`); the losing `5eda48f7` side (confirmed NOT an ancestor of
#   `main`) was deleted along with the markers.
#   Follow-up: once this correction is in main's baseline, this entry is dead
#   weight and should be removed to restore the byte-freeze on the corrected
#   file (#4956).
_OPERATOR_SANCTIONED_CORRECTIONS: frozenset[str] = frozenset(
    {
        "kitty-specs/acceptance-matrix-merge-fail-closed-01M34HG8/status.json",
        "kitty-specs/coord-read-fail-closed-01M38VVH/status.json",
        "kitty-specs/silent-write-hardening-residuals-01M37QN4/status.json",
        "kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md",
    }
)


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "SPEC_KITTY_ENABLE_SAAS_SYNC": "0"},
    )


# PR-FRESH2-002: the three git-subprocess env overrides below (disable
# replace-refs so a candidate can't be silently substituted; disable
# optional locks for a read-only walk; force the SaaS sync client off) were
# duplicated verbatim at three call sites (`_git_bytes` here, plus
# `_read_file_at_rev` and `_run_ls_files` below) -- hoisted to one constant,
# per this repo's own >=3-repetition hoisting convention (Sonar S1192).
# `_run_git` above intentionally keeps its own, narrower two-var env (no
# `GIT_OPTIONAL_LOCKS`) -- a pre-existing, distinct helper this finding does
# not touch.
_GIT_SUBPROCESS_ENV_OVERRIDES: dict[str, str] = {
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "SPEC_KITTY_ENABLE_SAAS_SYNC": "0",
}


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        check=False,
        env={**os.environ, **_GIT_SUBPROCESS_ENV_OVERRIDES},
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


_EMPTY_BLOB_OID = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def _is_new_rename_destination(status: str, paths: tuple[str, ...], path: str, baseline: dict[str, Blob], index: dict[str, Blob]) -> bool:
    """True when *path* is a brand-new empty file that git paired as an R/C destination.

    Git's default rename detection pairs identical blobs, so a PR that deletes an
    empty ``__init__.py`` elsewhere and adds an empty ``.gitkeep`` under an archive
    root reports ``R100 <old> <new>``. That pairing is spurious only for the empty
    blob: a real move of content into an archive root stays a violation, and the
    source endpoint is still checked on its own iteration.
    """
    if not (status.startswith(("R", "C")) and len(paths) == 2 and path == paths[1] and path not in baseline):
        return False
    staged = index.get(path)
    return staged is not None and staged.oid == _EMPTY_BLOB_OID


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
            if _is_new_rename_destination(status, paths, path, baseline, index):
                continue
            violations.append(f"{status}\t{path}: ordinary archive history changed")
    assert not violations, "Historical preservation violation under the four archive roots:\n  " + "\n  ".join(sorted(set(violations)))


def test_new_rename_destination_is_an_addition_but_the_source_stays_checked() -> None:
    """An R/C row's new empty destination is an addition; nothing else is.

    Git pairs identical blobs, so deleting an empty ``tests/pkg/__init__.py``
    while adding an empty mission ``tasks/.gitkeep`` reports ``R100``. Only that
    empty destination is exempt, and only when it is absent from the baseline; a
    rename that carries real content into an archive root stays a violation.
    """
    archived = "kitty-specs/m/tasks/.gitkeep"
    moved_in = "kitty-specs/m/incoming.md"
    moved_out = "kitty-specs/old/spec.md"
    baseline = {moved_out: Blob("100644", "0" * 40)}
    index = {archived: Blob("100644", _EMPTY_BLOB_OID), moved_in: Blob("100644", "1" * 40)}
    assert _is_new_rename_destination("R100", ("tests/pkg/__init__.py", archived), archived, {}, index)
    assert not _is_new_rename_destination("R100", ("outside.md", moved_in), moved_in, {}, index)
    assert not _is_new_rename_destination("R100", (moved_out, "elsewhere/spec.md"), moved_out, baseline, index)
    assert not _is_new_rename_destination("R100", ("a", moved_out), moved_out, baseline, index)
    assert not _is_new_rename_destination("M", (archived,), archived, {}, index)


def test_archive_baseline_is_non_empty() -> None:
    """Anti-vacuity floor: the archive roots are non-empty at the base, so the
    byte-identity assertion above is scanning real content, not nothing."""
    assert _files_under_roots_at(_require_port_base_rev()), (
        "no tracked files found under the archive roots at the EXP port base — the byte-identity gate would pass vacuously"
    )


# ---------------------------------------------------------------------------
# Conflict-marker guard (M1 FR-002-009, mission #4957): a non-vacuous,
# always-on gate against committed git conflict markers, plus a shrink-only
# ratchet over its one legitimate exemption. See spec.md/plan.md Section B
# for the Standing Order #5 non-vacuity rationale (concrete floor,
# self-mutation test, shrink-only allowlist, and that allowlist's own
# positive control -- four distinct legs, none folded into another).
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

_CONFLICT_MARKER_PATTERN = re.compile(r"^(<<<<<<<|>>>>>>>) ")

# The one legitimate exemption: `test_conflict_marker_parsing`
# (tests/git_ops/test_git.py:452-457) commits a literal conflict-marker
# fixture on purpose, to exercise GitVCS's own marker parsing -- not real
# corruption.
#
# PR-FRESH-003 (accept-with-reason, not narrowed to that fixture's own line
# range): this is a whole-file exemption, not a line-scoped one, so a
# hypothetical future real corruption landing elsewhere in this same file
# would also be invisible to the guard. This mirrors the pre-existing
# `_APPEND_ONLY_SPINE_EXCEPTIONS` shape a few lines below (also a whole-path
# carve-out), so it is a consistent, documented precedent rather than an
# oversight, and the risk is bounded to one contributor-owned test file.
# Narrowing to the fixture's own line range would require locating it
# programmatically (e.g. an `ast` walk for the `conflict_content` literal) to
# avoid a second, drift-prone hardcoded-line-number surface -- disproportionate
# cost for marginal risk reduction on a file whose only content is
# git-behavior test fixtures. Left as a known, accepted residual risk.
_CONFLICT_MARKER_SCAN_EXEMPTIONS: frozenset[str] = frozenset({"tests/git_ops/test_git.py"})

# PR-CONTRACT-001: the shrink-only ratchet's baseline is NOT a second literal
# co-located in this same file -- that was the mission's original design, and
# it was trivially co-editable with the live set above in one diff hunk: a
# contributor growing the exemption set could "re-baseline" it in the same
# PR, indistinguishable from a legitimate operator re-baseline. Instead, the
# baseline is read from the BASE ref's own copy of this file --
# `git show <base>:tests/architectural/test_archive_root_byte_identical.py`,
# parsed structurally via `ast` (not a regex) for the
# `_CONFLICT_MARKER_SCAN_EXEMPTIONS` assignment -- reusing the exact base-ref
# resolution the byte-identical freeze test above already uses
# (`_require_port_base_rev` / `_port_base_candidate_refs`, line ~708). A PR's
# own working-tree diff cannot move that anchor: the anchor is fixed at
# `merge-base(HEAD, main)`, a commit the PR's own diff is, by definition, not
# part of -- see `test_conflict_marker_exemption_baseline_anchors_to_base_ref_not_working_tree`
# for the same-PR-co-edit-is-now-caught proof.
#
# spec.md Clarification (k) is cited ONLY for the separate decision not to
# register this exemption set in `_baselines.yaml` (a three-file-edit problem
# under C-002's two-file blast radius) -- it says nothing about, and is not
# the basis for, this anti-co-edit anchoring design (PR-VERIFY-001).
#
# `_resolve_exemption_baseline` below resolves one of THREE outcomes, not two
# (PR-FRESH2-001 hardened the mission's original two-outcome design, which
# treated "the base ref's own copy has no assignment" as always meaning "this
# mission's own PR is the first landing" -- true for THIS PR, but also true,
# indefinitely, for any stale/un-rebased branch forked before the mechanism
# existed; a sweeper reproduced exactly that bypass against the real,
# imported functions):
#
# 1. `base_rev`'s own copy already has the constant -- use it verbatim (the
#    anti-co-edit anchor above; unchanged).
# 2. `base_rev` predates the constant, but it has already landed on the
#    canonical branch -- checked at each `landed_candidate_refs()` ref's OWN
#    TIP (never a merge-base with HEAD, which is what made `base_rev` stale
#    in the first place) -- use THAT real, landed value instead of the live
#    set. `test_conflict_marker_exemption_baseline_checks_landed_ref_when_base_predates_constant`
#    is the sweeper's reproduction: red before this fix, green after.
# 3. Neither `base_rev` nor any candidate ref has ever landed the constant --
#    genuinely nothing to shrink from yet (this mechanism's own introducing
#    PR, or any equally-early fork). The live set becomes its own baseline.
#    `test_conflict_marker_exemption_baseline_defaults_to_live_on_first_landing`
#    covers this, with `landed_candidate_refs` pinned to `[]` so the test is
#    a hermetic, deterministic proof rather than depending on this
#    checkout's own transient upstream state.
#
# An UNREACHABLE base ref (git unavailable, no candidate remote resolves) is
# a different, unaffected case and fails closed:
# `_require_conflict_marker_exemption_baseline` reuses
# `_require_port_base_rev`'s existing contract (raise in CI, skip locally)
# rather than defaulting to an empty/vacuous baseline.
#
# Residual, deliberately accepted: outcome 2's landed-ref lookup still names
# the constant's Python identifier as a string
# (`_CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME`) for the `ast` walk, exactly as
# outcome 1/3 always did. A future rename of the live identifier that forgets
# to update that string would make the lookup find nothing at every
# revision, reading as outcome 3 forever --
# `test_conflict_marker_exemption_constant_name_matches_live_identifier`
# closes that specific drift LOUDLY (asserting the string still names a
# live module global), independent of git history.
_CONFLICT_MARKER_GUARD_RELATIVE_PATH = "tests/architectural/test_archive_root_byte_identical.py"
_CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME = "_CONFLICT_MARKER_SCAN_EXEMPTIONS"


def _read_file_at_rev(root: Path, rev: str, rel_path: str) -> str | None:
    """Return ``rel_path``'s text content at ``rev``, or ``None`` if it does
    not exist there (a plain ``git show`` miss, not a git failure)."""
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{rev}:{rel_path}"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **_GIT_SUBPROCESS_ENV_OVERRIDES},
    )
    return result.stdout if result.returncode == 0 else None


def _parse_frozenset_of_str_constant(source: str, constant_name: str) -> frozenset[str] | None:
    """Structurally parse a module-level ``frozenset[str]`` literal assignment
    named ``constant_name`` out of ``source`` -- an ``ast`` walk, not a
    regex, so it is robust to reformatting/comments and to the annotated
    (``name: frozenset[str] = ...``) shape this file actually uses. Returns
    ``None`` when no such assignment exists at module level, so the caller
    can distinguish "this constant doesn't exist yet at this revision" from
    a parse failure."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == constant_name for target in targets):
            continue
        value = node.value
        assert value is not None
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "frozenset":
            literal: object = ast.literal_eval(value.args[0]) if value.args else frozenset()
        else:
            literal = ast.literal_eval(value)
        if not isinstance(literal, (set, frozenset, list, tuple)) or not all(isinstance(item, str) for item in literal):
            raise TypeError(f"{constant_name} is not a literal collection of paths: {literal!r}")
        return frozenset(literal)
    return None


def _parse_exemption_constant_at_rev(root: Path, rev: str) -> frozenset[str] | None:
    """Read and structurally parse ``_CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME``
    out of ``root``'s copy of this file at ``rev``. Returns ``None`` both when
    the file does not exist at ``rev`` and when it exists without that
    assignment -- the caller cannot yet tell "not landed here" from "landed
    under a different name" from this return value alone; see
    ``test_conflict_marker_exemption_constant_name_matches_live_identifier``
    for the independent, loud guard against a silent rename."""
    source = _read_file_at_rev(root, rev, _CONFLICT_MARKER_GUARD_RELATIVE_PATH)
    if source is None:
        return None
    return _parse_frozenset_of_str_constant(source, _CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME)


def _resolve_landed_exemption_baseline(root: Path, candidate_refs: list[str]) -> frozenset[str] | None:
    """Search each candidate ref's OWN TIP (never a merge-base) for a landed
    exemption baseline -- the real value the mechanism has already recorded
    upstream, for a branch whose own merge-base predates the constant's
    introduction (PR-FRESH2-001). Returns ``None`` only when no candidate ref
    has ever landed the constant either -- genesis, not staleness."""
    for ref in candidate_refs:
        parsed = _parse_exemption_constant_at_rev(root, ref)
        if parsed is not None:
            return parsed
    return None


def _resolve_exemption_baseline(
    root: Path,
    base_rev: str,
    live: frozenset[str],
    *,
    landed_candidate_refs: Callable[[], list[str]] = _port_base_candidate_refs,
) -> frozenset[str]:
    """Resolve the shrink-only ratchet's baseline -- three outcomes, per the
    module comment above ``_CONFLICT_MARKER_GUARD_RELATIVE_PATH`` (PR-FRESH2-001):
    ``base_rev``'s own copy, else the first candidate ref that has landed the
    constant at its own current tip, else ``live`` (genuinely never landed
    anywhere). ``landed_candidate_refs`` defaults to the real
    ``_port_base_candidate_refs`` (production callers never override it); test
    fixtures inject a ref list scoped to their own throwaway repo instead."""
    parsed = _parse_exemption_constant_at_rev(root, base_rev)
    if parsed is not None:
        return parsed
    landed = _resolve_landed_exemption_baseline(root, landed_candidate_refs())
    return live if landed is None else landed


def _require_conflict_marker_exemption_baseline() -> frozenset[str]:
    """Fail-closed wrapper real callers use: reuses ``_require_port_base_rev``
    so an unreachable base fails exactly like the byte-identical freeze test
    already does, never silently defaulting to an empty baseline."""
    base_rev = _require_port_base_rev()
    return _resolve_exemption_baseline(REPO_ROOT, base_rev, _CONFLICT_MARKER_SCAN_EXEMPTIONS)


def _run_ls_files(root: Path) -> subprocess.CompletedProcess[str]:
    """Enumerate tracked files under ``root`` via ``git ls-files -z``.

    ``-z`` yields NUL-separated, *verbatim* paths -- this disables git's
    default ``core.quotePath`` C-quoting, which would otherwise wrap a
    non-ASCII path like ``café.txt`` as ``"caf\\303\\251.txt"`` (a literal
    string that does not exist on disk) and silently drop that path out of
    the content scan via a mislabeled binary/unreadable skip (PR-TESTS-001).
    Mirrors ``tests/architectural/test_no_invalid_windows_filenames.py``'s
    ``_tracked_paths()`` precedent for the identical defect class.

    A genuinely new call site -- applies the same ``_GIT_SUBPROCESS_ENV_OVERRIDES``
    (``GIT_NO_REPLACE_OBJECTS``, ``GIT_OPTIONAL_LOCKS``,
    ``SPEC_KITTY_ENABLE_SAAS_SYNC``) ``_git_bytes`` and ``_read_file_at_rev``
    apply, unconditionally, on every call (PR-FRESH2-002). Does not change
    ``_run_git``'s own, narrower two-var env.
    """
    return subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **_GIT_SUBPROCESS_ENV_OVERRIDES},
    )


def _enumerate_tracked_files(root: Path = REPO_ROOT) -> list[str]:
    """Return tracked relative paths under ``root``, raising on enumeration failure.

    Splits on ``"\\0"`` (NUL), matching ``-z``'s verbatim output -- never
    ``str.splitlines()``, which would only be correct for the C-quoted,
    newline-delimited default output this guard deliberately does not use.
    """
    result = _run_ls_files(root)
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files under {root} failed (exit {result.returncode}): {result.stderr!r}")
    return [path for path in result.stdout.split("\0") if path]


_BINARY_SKIP_REASON = "binary (NUL byte present)"


def _warn_skipped_file(rel_path: str, reason: str) -> None:
    """Surface one unreadable-file (``OSError``) content-scan skip on two
    independent channels, immediately and per-file -- this is the
    actually-actionable skip case, unlike the expected/permanent binary case
    (see ``_warn_binary_skip_summary``, PR-FRESH-002).

    PR-CONTRACT-002: a ``logger.warning`` alone is invisible in CI's actual
    ``pytest tests/architectural/test_archive_root_byte_identical.py -q``
    invocation (no ``--log-cli-level``/``--log-cli-format``, and neither
    ``pytest.ini`` nor ``pyproject.toml`` sets ``log_cli``/``log_level``), so
    it never prints for a *passing* run. ``warnings.warn`` does not have that
    problem: pytest's default warnings-summary footer prints for every run,
    passing or not, with no special flag -- so a skip is never silently
    hidden behind an unread log stream (spec.md Edge Cases).
    """
    message = f"conflict-marker scan: skipping tracked file not content-scanned: {rel_path} ({reason})"
    logger.warning(message)
    warnings.warn(message, stacklevel=2)


def _warn_binary_skip_summary(paths: list[str]) -> None:
    """Aggregate every binary (NUL-byte) content-scan skip from one
    invocation into ONE warning naming the count and every skipped path
    (PR-FRESH-002).

    Before this, each of the ~30 known-binary tracked files (images, logos)
    produced its own ``UserWarning``, printed unconditionally on every green
    run of the always-on archive-freeze job -- permanent, unactionable
    noise for content that never changes. The per-file ``OSError`` skip (see
    ``_warn_skipped_file``) is untouched and stays loud, since that case is
    the actually-actionable one. Every skipped path is still named here,
    just inside one message instead of N -- spec.md Edge Cases still holds:
    a skip can never silently shrink the floor or hide which files were not
    scanned.
    """
    message = f"conflict-marker scan: skipping {len(paths)} tracked file(s) not content-scanned (binary, NUL byte present): {', '.join(sorted(paths))}"
    logger.warning(message)
    warnings.warn(message, stacklevel=2)


def _decode_tracked_file_for_scan(root: Path, rel_path: str) -> tuple[str | None, str | None]:
    """Read and decode one tracked file's content for the marker scan.

    Returns ``(content, skip_reason)``. ``content`` is ``None`` when the file
    is skipped -- the caller still counts it toward FR-004's scanned-file
    floor. Two distinct skip reasons, surfaced differently by the caller
    (PR-FRESH-002):

    * unreadable (``OSError`` -- permission denied, dangling symlink, or any
      other read failure) -- the actually-actionable case, warned loudly and
      immediately per file;
    * a genuine binary blob, detected by a NUL-byte heuristic on the raw
      bytes *before* any decode attempt -- expected/permanent, aggregated by
      the caller into one summary warning instead of N per-file ones.

    A genuine text file with an isolated non-UTF-8 byte (no NUL byte) is
    NOT skipped: it is decoded with ``errors="replace"`` rather than the
    strict default, so its ASCII conflict-marker lines still match the
    anchored regex even though the byte around them decodes lossily. This
    closes PR-CONTRACT-002's false-negative gap, where a strict decode raised
    ``UnicodeDecodeError`` for *any* encoding wrinkle -- not just "legitimate
    binary blobs" as spec.md's Edge Cases rationale intends -- and silently
    dropped that file's real marker out of the content scan.
    """
    try:
        raw = (root / rel_path).read_bytes()
    except OSError as error:
        return None, f"unreadable: {error}"
    if b"\x00" in raw:
        return None, _BINARY_SKIP_REASON
    return raw.decode("utf-8", errors="replace"), None


def _scan_tracked_files_for_conflict_markers(
    root: Path,
    exemptions: frozenset[str],
) -> tuple[list[tuple[str, int]], int, list[str]]:
    """Enumerate tracked files under ``root`` and scan each non-exempted file
    for a committed conflict-marker line.

    Fails closed (NFR-002/FR-007): raises if enumeration itself raises, or if
    it unexpectedly reports zero tracked files -- a git repository with at
    least one commit is never legitimately empty for this gate's callers
    (REPO_ROOT, or a fixture repo that just committed a file), so a zero
    count signals a broken enumeration, not "nothing to scan."

    Returns ``(violations, scanned_count, skipped)`` where ``violations`` is
    a list of ``(relative_path, line_number)`` pairs, ``scanned_count`` is
    the exact number of tracked files enumerated (FR-004's ground-truth
    tie), and ``skipped`` is the list of relative paths that were not
    content-scanned (still counted toward ``scanned_count``) -- returned
    rather than only logged, so a caller can assert on it directly instead
    of depending on log capture. Every binary skip in this call is folded
    into one summary warning at the end (PR-FRESH-002); every unreadable
    (``OSError``) skip warns immediately, per file.
    """
    tracked = _enumerate_tracked_files(root)
    if not tracked:
        raise RuntimeError(f"git ls-files under {root} enumerated zero tracked files; refusing to report a vacuous pass")
    violations: list[tuple[str, int]] = []
    skipped: list[str] = []
    binary_skips: list[str] = []
    for rel_path in tracked:
        if rel_path in exemptions:
            continue
        content, skip_reason = _decode_tracked_file_for_scan(root, rel_path)
        if content is None:
            assert skip_reason is not None
            skipped.append(rel_path)
            if skip_reason == _BINARY_SKIP_REASON:
                binary_skips.append(rel_path)
            else:
                _warn_skipped_file(rel_path, skip_reason)
            continue
        for line_no, line in enumerate(content.splitlines(), start=1):
            if _CONFLICT_MARKER_PATTERN.match(line):
                violations.append((rel_path, line_no))
    if binary_skips:
        _warn_binary_skip_summary(binary_skips)
    return violations, len(tracked), skipped


def _assert_exemption_set_is_shrink_only(candidate: frozenset[str], baseline: frozenset[str]) -> None:
    """Assert ``candidate`` is a subset of ``baseline`` (shrink-only ratchet).

    Shared by the ratchet test and its own positive control so neither
    duplicates the comparison logic (FR-005/FR-008).
    """
    unexpected = candidate - baseline
    assert not unexpected, f"Exemption allowlist grew beyond baseline; unexpected entries: {sorted(unexpected)}"


def _git_init_fixture_repo(path: Path) -> None:
    """Initialize a throwaway git repo for a conflict-marker guard fixture."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)


def _git_commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=path, check=True, capture_output=True)


def _run_git_rev_parse(path: Path, ref: str) -> str:
    """Resolve ``ref`` to a full SHA inside a throwaway fixture repo."""
    result = subprocess.run(["git", "-C", str(path), "rev-parse", ref], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def test_no_conflict_markers_in_tracked_files(tmp_path: Path) -> None:
    """Real-tree negative control (FR-003/FR-004), plus the folded spec.md User
    Story 2 Acceptance Scenario 5: a ground-truth-tied floor over an
    independently-counted N-file fixture subtree, including one binary file."""
    violations, scanned_count, _skipped = _scan_tracked_files_for_conflict_markers(REPO_ROOT, _CONFLICT_MARKER_SCAN_EXEMPTIONS)
    assert not violations, "Conflict markers found in tracked files:\n  " + "\n  ".join(f"{path}:{line_no}" for path, line_no in violations)
    assert scanned_count > 0
    assert scanned_count == len(_enumerate_tracked_files(REPO_ROOT))

    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    (fixture_repo / "a.txt").write_text("alpha\n")
    (fixture_repo / "b.txt").write_text("bravo\n")
    (fixture_repo / "binary.bin").write_bytes(bytes([0xFF, 0xFE, 0x00, 0x01, 0x02]))
    _git_commit_all(fixture_repo, "fixture subtree")

    fixture_violations, fixture_scanned_count, fixture_skipped = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert fixture_scanned_count == 3, "binary file must be counted toward the floor, not silently dropped"
    assert not fixture_violations
    assert fixture_skipped == ["binary.bin"]


def test_conflict_marker_guard_aggregates_binary_skips_into_one_warning(tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
    """PR-FRESH-002: N binary (NUL-byte) skips from one invocation must
    produce exactly one aggregate ``UserWarning`` naming the count and every
    skipped path -- not N separate warnings, which was permanent,
    unactionable noise on every green run of the always-on archive-freeze
    job (measured: ~30 such warnings on the real tree before this fix). The
    per-file ``OSError`` skip path is untouched and stays loud (see
    ``test_conflict_marker_guard_logs_skipped_undecodable_files``)."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    (fixture_repo / "clean.txt").write_text("nothing suspicious here\n")
    binary_names = ("one.bin", "two.bin", "three.bin")
    for name in binary_names:
        (fixture_repo / name).write_bytes(bytes([0xFF, 0x00, 0x01]))
    _git_commit_all(fixture_repo, "fixture with three binary tracked files")

    violations, scanned_count, skipped = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())

    assert not violations
    assert scanned_count == 4
    assert sorted(skipped) == sorted(binary_names)
    binary_warnings = [w for w in recwarn.list if issubclass(w.category, UserWarning) and "binary" in str(w.message)]
    assert len(binary_warnings) == 1, f"expected exactly one aggregate warning for {len(binary_names)} binary skips; got {len(binary_warnings)}"
    message = str(binary_warnings[0].message)
    assert str(len(binary_names)) in message
    for name in binary_names:
        assert name in message


def test_conflict_marker_guard_scans_non_ascii_tracked_filenames(tmp_path: Path) -> None:
    """PR-TESTS-001: a non-ASCII tracked filename must not be C-quoted out of
    the content scan. Without ``-z``, git's default ``core.quotePath`` emits
    such a path as a literal octal-escaped string that does not exist on
    disk; ``(root / rel_path).read_text(...)`` (or ``.read_bytes()``) then
    raises ``FileNotFoundError`` (an ``OSError``), mislabeling a real,
    content-scannable file as a binary/unreadable skip -- exactly the defect
    class ``tests/architectural/test_no_invalid_windows_filenames.py``'s
    ``_tracked_paths()`` already fixed with ``-z``. Red before the ``-z``
    fix (the marker would be silently skipped, not caught), green after."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    target = fixture_repo / "café.txt"
    target.write_text("clean line\n<<<<<<< HEAD\nplanted\n")
    _git_commit_all(fixture_repo, "non-ascii tracked filename with a real marker")

    violations, scanned_count, skipped = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert violations == [("café.txt", 2)], "a non-ASCII tracked filename must be content-scanned via the verbatim -z enumeration, not C-quoted and skipped"
    assert scanned_count == 1
    assert skipped == []


def test_conflict_marker_guard_scans_text_file_with_stray_non_utf8_byte(tmp_path: Path) -> None:
    """PR-CONTRACT-002: a genuine text file with one stray non-UTF-8 byte
    elsewhere in the file must still be content-scanned -- its ASCII marker
    line survives ``errors="replace"`` decoding of the surrounding bytes.
    Red before this fix (a strict ``utf-8`` decode raised
    ``UnicodeDecodeError``, silently binary-skipping the file and its real
    marker); green after."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    target = fixture_repo / "corrupted.txt"
    target.write_bytes(b"clean start\n\xff\n<<<<<<< HEAD\nplanted\n")
    _git_commit_all(fixture_repo, "text file with a stray non-utf-8 byte and a real marker")

    violations, scanned_count, skipped = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert violations == [("corrupted.txt", 3)], "a text file with an isolated non-UTF-8 byte must still be content-scanned, not silently binary-skipped"
    assert scanned_count == 1
    assert skipped == []


def test_conflict_marker_guard_self_mutation_catches_synthetic_marker(tmp_path: Path) -> None:
    """The marker-scan guard's own positive control (FR-006): proves the
    real-tree pass above is a real negative, not a probe that cannot see
    anything -- catches a planted marker, clears once it is removed."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    target = fixture_repo / "clean.txt"
    target.write_text("nothing suspicious here\n")
    _git_commit_all(fixture_repo, "clean baseline")

    violations, _, _ = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert not violations

    target.write_text("nothing suspicious here\n<<<<<<< HEAD\nplanted\n")
    _git_commit_all(fixture_repo, "plant synthetic marker")
    violations, _, _ = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert violations == [("clean.txt", 2)]

    target.write_text("nothing suspicious here\n")
    _git_commit_all(fixture_repo, "remove synthetic marker")
    violations, _, _ = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert not violations


def test_conflict_marker_guard_self_mutation_catches_synthetic_closing_marker(tmp_path: Path) -> None:
    """PR-FRESH-001: the ``>>>>>>> `` alternation arm has its own,
    independent self-mutation proof -- every other fixture in this file
    plants only the opening ``<<<<<<< HEAD`` marker, so dropping the closing
    arm from ``_CONFLICT_MARKER_PATTERN`` left every test in this file
    passing (verified by mutation in a throwaway worktree). Mirrors
    ``test_conflict_marker_guard_self_mutation_catches_synthetic_marker``
    exactly, but for a bare closing marker with no accompanying opening
    marker -- catches it, clears once removed."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    target = fixture_repo / "clean.txt"
    target.write_text("nothing suspicious here\n")
    _git_commit_all(fixture_repo, "clean baseline")

    violations, _, _ = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert not violations

    target.write_text("nothing suspicious here\n>>>>>>> some-branch\n")
    _git_commit_all(fixture_repo, "plant synthetic closing marker with no opening marker")
    violations, _, _ = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert violations == [("clean.txt", 2)]

    target.write_text("nothing suspicious here\n")
    _git_commit_all(fixture_repo, "remove synthetic closing marker")
    violations, _, _ = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())
    assert not violations


def test_conflict_marker_exemption_allowlist_is_shrink_only() -> None:
    """Shrink-only ratchet (FR-005/NFR-003): the live exemption set must
    never grow beyond the base ref's own historical copy of this same
    exemption set (PR-CONTRACT-001) -- an anchor a same-PR diff cannot move,
    unlike the mission's original co-located-literal design (see
    ``_require_conflict_marker_exemption_baseline`` and the module comment
    above it).

    Subset-only, per FR-005's own text ("the exemption set can shrink over
    time but never silently grow") and NFR-003's cited Burn-down Policy
    analogy ("growth ... FAILS CI, shrinkage WARNS"): an exact-equality
    assertion here would false-red a legitimate future shrink -- e.g.
    removing ``tests/git_ops/test_git.py`` once its fixture no longer needs
    the exemption. See ``test_conflict_marker_exemption_allowlist_permits_a_shrink``
    below for the shrink direction's own positive control (PR-TESTS-003)."""
    baseline = _require_conflict_marker_exemption_baseline()
    _assert_exemption_set_is_shrink_only(_CONFLICT_MARKER_SCAN_EXEMPTIONS, baseline)


def test_conflict_marker_exemption_shrink_only_ratchet_has_positive_control() -> None:
    """The shrink-only ratchet's own positive control (FR-008), distinct from
    the marker-scan guard's positive control above: proves the comparator
    detects growth, so the ratchet test's pass is a real negative. Exercises
    the pure comparator directly (not the git-anchored baseline resolution,
    which has its own dedicated tests below)."""
    augmented = _CONFLICT_MARKER_SCAN_EXEMPTIONS | frozenset({"some/spurious/extra/path.py"})
    with pytest.raises(AssertionError, match="some/spurious/extra/path.py"):
        _assert_exemption_set_is_shrink_only(augmented, _CONFLICT_MARKER_SCAN_EXEMPTIONS)


def test_conflict_marker_exemption_allowlist_permits_a_shrink() -> None:
    """Shrink-direction positive control (PR-TESTS-003): a strict,
    non-empty-diff subset of the baseline -- and the empty set -- must NOT
    raise, proving the ratchet's namesake "shrink" permission is genuinely
    exercised rather than merely untested-and-coincidentally-working
    alongside the growth-detection test above. A mutation that tightens
    ``_assert_exemption_set_is_shrink_only`` back to a strict-equality check
    (the exact defect PR-CONTRACT-001 found) makes this test fail."""
    shrunk = _CONFLICT_MARKER_SCAN_EXEMPTIONS - {"tests/git_ops/test_git.py"}
    assert shrunk != _CONFLICT_MARKER_SCAN_EXEMPTIONS, "fixture must be a genuine strict subset, not the baseline itself"
    _assert_exemption_set_is_shrink_only(shrunk, _CONFLICT_MARKER_SCAN_EXEMPTIONS)
    _assert_exemption_set_is_shrink_only(frozenset(), _CONFLICT_MARKER_SCAN_EXEMPTIONS)


def test_conflict_marker_exemption_baseline_defaults_to_live_on_first_landing(tmp_path: Path) -> None:
    """PR-CONTRACT-001 genesis case, hardened by PR-FRESH2-001: outcome 3 of
    ``_resolve_exemption_baseline``'s three-outcome design -- the constant has
    NEVER landed anywhere, not merely "the base ref's own copy lacks it"
    (that alone is now insufficient to reach this outcome; see
    ``test_conflict_marker_exemption_baseline_checks_landed_ref_when_base_predates_constant``
    for the case where it HAS landed elsewhere and must NOT default to live).
    ``landed_candidate_refs`` is pinned to an empty list so this test is a
    hermetic, deterministic proof of genesis, independent of this real
    checkout's own transient upstream state -- it no longer relies on
    ``_port_base_candidate_refs``'s live remote resolution against
    ``REPO_ROOT`` the way the mission's original version of this test did."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    fixture_file = fixture_repo / _CONFLICT_MARKER_GUARD_RELATIVE_PATH
    fixture_file.parent.mkdir(parents=True, exist_ok=True)
    fixture_file.write_text("# no exemption constant defined at this revision\n")
    _git_commit_all(fixture_repo, "base commit predates the exemption constant")
    base_rev = _run_git_rev_parse(fixture_repo, "HEAD")

    live = frozenset({"tests/git_ops/test_git.py"})
    baseline = _resolve_exemption_baseline(fixture_repo, base_rev, live, landed_candidate_refs=lambda: [])
    assert baseline == live


def test_conflict_marker_exemption_baseline_checks_landed_ref_when_base_predates_constant(tmp_path: Path) -> None:
    """PR-FRESH2-001: reproduces the sweeper's stale/un-rebased-branch bypass
    against the real, imported ``_resolve_exemption_baseline``.

    A "main" lineage lands the guard's exemption constant with baseline
    ``{"a.txt"}``. A separate "contributor" commit forks from BEFORE that
    landing -- its own copy of this file has no
    ``_CONFLICT_MARKER_SCAN_EXEMPTIONS`` assignment at all, exactly like this
    mission's own introducing PR looks to the base-ref check alone -- and
    grows a LIVE set that hides a malicious entry. Before this fix,
    ``_resolve_exemption_baseline`` could not distinguish "genuinely never
    landed anywhere" from "predates landing, but IS landed on main," and
    silently fell back to the (already-grown) live set, so the shrink-only
    ratchet compared the malicious live set against itself and passed
    vacuously -- RED reproduces exactly that with the pre-fix two-outcome
    behaviour (parsed is ``None`` at ``base_rev`` -> return ``live``
    unconditionally). After this fix (GREEN), the base ref's own copy still
    has no constant, but the landed-ref lookup finds ``main``'s real, current
    ``{"a.txt"}`` baseline and checks the malicious growth against THAT --
    failing exactly as FR-005/NFR-003 require."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    fixture_file = fixture_repo / _CONFLICT_MARKER_GUARD_RELATIVE_PATH
    fixture_file.parent.mkdir(parents=True, exist_ok=True)

    fixture_file.write_text("# pre-guard revision: no exemption constant defined yet\n")
    _git_commit_all(fixture_repo, "pre-guard commit (contributor's stale merge-base)")
    pre_guard_rev = _run_git_rev_parse(fixture_repo, "HEAD")

    fixture_file.write_text('_CONFLICT_MARKER_SCAN_EXEMPTIONS: frozenset[str] = frozenset({"a.txt"})\n')
    _git_commit_all(fixture_repo, "guard lands on main: baseline is {a.txt}")
    landed_main_rev = _run_git_rev_parse(fixture_repo, "HEAD")

    grown_live = frozenset({"a.txt", "malicious/hides_a_marker.py"})
    baseline = _resolve_exemption_baseline(
        fixture_repo,
        pre_guard_rev,
        grown_live,
        landed_candidate_refs=lambda: [landed_main_rev],
    )
    assert baseline == frozenset({"a.txt"}), "a stale merge-base must anchor to main's real landed baseline, not its own (possibly grown) live set"
    with pytest.raises(AssertionError, match="malicious/hides_a_marker.py"):
        _assert_exemption_set_is_shrink_only(grown_live, baseline)


def test_conflict_marker_exemption_constant_name_matches_live_identifier() -> None:
    """PR-FRESH2-001 (related, lower-probability variant): the ast-lookup
    name ``_CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME`` must name a REAL,
    currently-live module-level frozenset. If a future rename changes
    ``_CONFLICT_MARKER_SCAN_EXEMPTIONS``'s Python identifier without updating
    this string, ``_parse_exemption_constant_at_rev`` would silently find no
    matching assignment at every revision (including the current one), and
    ``_resolve_exemption_baseline`` would treat that drift as "never landed,
    use live" forever. This test fails LOUDLY the moment the string and the
    real identifier diverge, instead of that silent, indefinite fallback."""
    module_globals = sys.modules[__name__].__dict__
    assert _CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME in module_globals, (
        f"the ast-lookup name {_CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME!r} no longer names a live module-level "
        "symbol -- the constant was renamed without updating _CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME"
    )
    live_value = module_globals[_CONFLICT_MARKER_EXEMPTION_CONSTANT_NAME]
    assert isinstance(live_value, frozenset)
    assert live_value is _CONFLICT_MARKER_SCAN_EXEMPTIONS


def test_conflict_marker_exemption_baseline_anchors_to_base_ref_not_working_tree(tmp_path: Path) -> None:
    """PR-CONTRACT-001: proves a same-PR co-edit is now caught. The base
    commit's copy of this file records a small exemption set; a later
    commit (simulating this PR's own diff) grows it in the SAME file at the
    SAME path. The resolved baseline still reflects the base commit's set,
    not the file's current committed content -- because it is read via
    ``git show <base_rev>:...``, an anchor the PR's own diff cannot move.
    This is exactly the defect the mission's original co-located-literal
    design could not catch (both constants moved together in one diff hunk);
    here, growing the live set alone still fails the shrink-only ratchet."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    fixture_file = fixture_repo / _CONFLICT_MARKER_GUARD_RELATIVE_PATH
    fixture_file.parent.mkdir(parents=True, exist_ok=True)
    fixture_file.write_text('_CONFLICT_MARKER_SCAN_EXEMPTIONS: frozenset[str] = frozenset({"a.txt"})\n')
    _git_commit_all(fixture_repo, "base: exemption set is {a.txt}")
    base_rev = _run_git_rev_parse(fixture_repo, "HEAD")

    fixture_file.write_text('_CONFLICT_MARKER_SCAN_EXEMPTIONS: frozenset[str] = frozenset({"a.txt", "b.txt"})\n')
    _git_commit_all(fixture_repo, "PR diff: grows the exemption set in the same file")
    grown_live = frozenset({"a.txt", "b.txt"})

    baseline = _resolve_exemption_baseline(fixture_repo, base_rev, grown_live)
    assert baseline == frozenset({"a.txt"}), "baseline must anchor to the base commit, not the PR's own working-tree content"
    with pytest.raises(AssertionError, match="b.txt"):
        _assert_exemption_set_is_shrink_only(grown_live, baseline)


def test_conflict_marker_exemption_baseline_fails_closed_when_base_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR-CONTRACT-001: an unreachable base must never silently default to an
    empty/vacuous baseline -- it must fail exactly like the byte-identical
    freeze test's own base-ref resolution already does. Proven by wiring:
    ``_require_conflict_marker_exemption_baseline`` calls straight through
    ``_require_port_base_rev``, so whatever that raises propagates
    unmodified rather than being swallowed into a default."""
    sentinel_message = "simulated: base ref unreachable"

    def _raising_require_port_base_rev() -> str:
        raise RuntimeError(sentinel_message)

    monkeypatch.setattr(sys.modules[__name__], "_require_port_base_rev", _raising_require_port_base_rev)
    with pytest.raises(RuntimeError, match=sentinel_message):
        _require_conflict_marker_exemption_baseline()


def test_conflict_marker_guard_fails_closed_on_enumeration_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed leg (FR-007/NFR-002): enumeration failure -- or an
    unexpectedly empty enumeration -- must raise, never silently report zero
    conflict markers as a pass. Scoped to enumeration failure only; a
    per-file binary/decode failure during content scan is a different,
    non-fatal path already covered above."""
    this_module = sys.modules[__name__]

    def _raising_ls_files(root: Path) -> subprocess.CompletedProcess[str]:
        raise OSError("git executable unavailable (simulated)")

    monkeypatch.setattr(this_module, "_run_ls_files", _raising_ls_files)
    with pytest.raises(OSError, match="git executable unavailable"):
        _scan_tracked_files_for_conflict_markers(REPO_ROOT, _CONFLICT_MARKER_SCAN_EXEMPTIONS)
    monkeypatch.undo()

    monkeypatch.setattr(this_module, "_enumerate_tracked_files", lambda root=REPO_ROOT: [])
    with pytest.raises(RuntimeError, match="zero tracked files"):
        _scan_tracked_files_for_conflict_markers(REPO_ROOT, _CONFLICT_MARKER_SCAN_EXEMPTIONS)


def test_conflict_marker_guard_logs_skipped_undecodable_files(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Review fix (WP02-R-002), hardened by PR-CONTRACT-002: a genuine binary
    skip (NUL-byte heuristic) must never be silent (spec.md Edge Cases), and
    its visibility must not depend on ``--log-cli-level`` -- assert both the
    ``logger.warning`` record AND a ``warnings.warn`` (which pytest's default
    warnings summary prints even under CI's exact ``pytest ... -q``
    invocation) name the skipped path."""
    fixture_repo = tmp_path / "fixture-repo"
    fixture_repo.mkdir()
    _git_init_fixture_repo(fixture_repo)
    (fixture_repo / "clean.txt").write_text("nothing suspicious here\n")
    undecodable = fixture_repo / "undecodable.bin"
    undecodable.write_bytes(bytes([0xFF, 0xFE, 0x00, 0x01, 0x02]))
    _git_commit_all(fixture_repo, "fixture with one undecodable tracked file")

    with caplog.at_level(logging.WARNING), pytest.warns(UserWarning, match="undecodable.bin"):
        violations, scanned_count, skipped = _scan_tracked_files_for_conflict_markers(fixture_repo, frozenset())

    assert not violations
    assert scanned_count == 2, "the undecodable file must still count toward the enumerated-file floor"
    assert skipped == ["undecodable.bin"]
    skip_warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert any("undecodable.bin" in message for message in skip_warnings), f"expected a warning naming the skipped undecodable file; got: {skip_warnings!r}"


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
