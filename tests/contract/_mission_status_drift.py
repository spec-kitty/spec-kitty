"""The reference drift reader of the ``mission-status`` contract (plan D-P1, D-P3, D-P6, D-P7; spec FR-008 to FR-015).

``scan_drift`` is the production entry point of the reference reader for ``GET /drift``. It returns a ``DriftOutcome`` (an
HTTP status and a body), and a refusal is an outcome, never an exception. It reads and never repairs: it never calls the
writing ``materialize``, opens only the files the spec lists, and starts at most one process of its own (the local branch
listing). The coordination resolver is reached only through the memo (``_mission_status_memo``), so its git queries are
counted and never repeated.

Three kinds are reported. Kind 1 compares ``status.json`` with the reducer replay at the snapshot's own generation, kind 2
reports exactly one of ``status.json`` and the event log missing, and kind 3 reports an expected lane branch or Mission
branch with no local branch, for a Mission that is not completed and whose lane manifest has the current shape.

Failure semantics (FR-015, FR-024): a broken derived file is a finding, a broken authority is a 500, and an older valid shape
is "not evaluated" and counted. The module has one place for each rule, and the mutation catalogue of the test module
replaces exactly one of those places by its defective twin.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel.clock import UTC, UTC_SECOND_TIMESTAMP_FORMAT, Clock, datetime, format_stamp, parse_iso
from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.lanes.branch_naming import PLANNING_LANE_ID, code_lane_branch_name
from specify_cli.lanes.models import LanesManifest
from specify_cli.mission_metadata import load_meta, resolve_mission_identity
from specify_cli.status.lifecycle import derive_mission_lifecycle
from specify_cli.status.reducer import materialize_snapshot, materialize_to_json
from tests.contract import _mission_status_memo as memo_module
from tests.contract._mission_status_payloads import STATUS_LANES, enumerate_missions, is_wp_id

KIND_DISAGREES = "snapshot_disagrees_with_event_log"
KIND_MISSING = "snapshot_or_event_log_missing"
KIND_BRANCH = "lane_branch_missing"
CODE_DRIFT = "SNAPSHOT_DRIFT"
CODE_PROVENANCE = "SNAPSHOT_DRIFT_PROVENANCE"
CODE_TERMINAL = "SNAPSHOT_DRIFT_TERMINAL"
CODE_CORRUPT = "CORRUPT_JSON"
REMEDY_MATERIALIZE = "materialize_status"
FALLBACK_REASON = "coordination_branch_deleted"
SNAPSHOT_FILE = "status.json"
EVENT_LOG_FILE = "status.events.jsonl"
LANES_FILE = "lanes.json"
REFUSAL_UNREADABLE = "drift_scan_unreadable"
REFUSAL_NOT_FOUND = "mission_not_found"
OK = 200
BAD_REQUEST = 400
NOT_FOUND = 404
UNREADABLE = 500
CAP = 1000
ACTIVE_LANES = frozenset({"claimed", "in_progress", "for_review", "in_review", "approved"})
COMPLETED_STATES = frozenset({"recently_completed", "archived"})
PROVENANCE_FIELDS = frozenset({"actor", "last_event_id", "last_transition_at"})
WORK_PACKAGES = "work_packages"
LANE = "lane"
_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

# The closed table of (kind, sourceCode) pairs and the fixed sentence of each (FR-014): no source text is ever forwarded.
SUMMARIES: dict[tuple[str, str | None], str] = {
    (KIND_DISAGREES, CODE_DRIFT): "The status snapshot disagrees with the event log.",
    (KIND_DISAGREES, CODE_PROVENANCE): "The status snapshot differs from the event log only in provenance fields.",
    (KIND_DISAGREES, CODE_TERMINAL): "The status snapshot differs from the event log and every work package is done.",
    (KIND_DISAGREES, CODE_CORRUPT): "The status snapshot is not a valid JSON object.",
    (KIND_MISSING, None): "One of the status snapshot and the event log is missing.",
    (KIND_BRANCH, None): "An expected lane or Mission branch has no local branch.",
}
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
_SEVERITIES = {CODE_DRIFT: SEVERITY_ERROR, CODE_CORRUPT: SEVERITY_ERROR}
REFUSALS: dict[str, tuple[int, str, str]] = {
    REFUSAL_NOT_FOUND: (NOT_FOUND, "The Mission was not found", "No Mission has this identity."),
    REFUSAL_UNREADABLE: (
        UNREADABLE,
        "The drift scan could not read a Mission",
        "A Mission the scan had to read could not be read, so no report is returned.",
    ),
}
INVALID_IDENTITY = (BAD_REQUEST, "The missionId is not a Mission identity", "The missionId must be the 26-character ULID of a Mission.")


class ScanUnreadable(Exception):
    """A read the scan cannot do its job without: the whole scan is refused 500, never partly answered (AD-10)."""


class ReadDirOutsideRoot(ScanUnreadable):
    """The resolver returned a read directory outside the repository root: a 500 here, a fallback in the v1 helper."""


# ---------------------------------------------------------------------------
# The file-system seam and the outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileSystem:
    """The two calls the reader makes on the files it owns. A test replaces one with a fault or a counter."""

    exists: Callable[[Path], bool]
    read_bytes: Callable[[Path], bytes]


REAL_FS = FileSystem(exists=Path.exists, read_bytes=Path.read_bytes)


@dataclass(frozen=True)
class DriftOutcome:
    """What the operation answers, and what the reader's result carries beside it (FR-015, FR-025).

    ``fallbacks`` names the Missions read from their own directory because their declared coordination branch is gone, with the
    reason; ``legacy_manifests`` lists the Missions whose lane manifest predates ``mission_slug`` (not evaluated for kind 3).
    """

    status: int
    body: dict[str, Any]
    fallbacks: dict[str, str] = field(default_factory=dict)
    legacy_manifests: tuple[str, ...] = ()


def refusal(code: str) -> DriftOutcome:
    """The problem details outcome of ``code`` (status, title and detail are fixed by the code)."""
    status, title, detail = REFUSALS[code]
    return DriftOutcome(status, {"type": "about:blank", "title": title, "status": status, "code": code, "detail": detail})


def invalid_identity() -> DriftOutcome:
    """The 400 of a ``missionId`` that is not a ULID (the shared ``Problem`` of ``default``)."""
    status, title, detail = INVALID_IDENTITY
    return DriftOutcome(status, {"type": "about:blank", "title": title, "status": status, "detail": detail})


def list_local_branches(repo_root: Path) -> frozenset[str]:
    """The names of the local branches of ``repo_root``: one ``git for-each-ref refs/heads`` listing (FR-012 step 4).

    A missing git binary, a non-zero exit and a directory that is not itself a repository are all ``ScanUnreadable``, never "every
    branch is absent". Git is not allowed to look above the repository root, so a directory that merely sits inside another
    checkout is not read as that checkout.
    """
    environment = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo_root.resolve().parent)}
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "for-each-ref", "--format=%(refname)", "refs/heads"],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            env=environment,
        )
    except OSError as error:
        raise ScanUnreadable("git could not be started") from error
    if result.returncode != 0:
        raise ScanUnreadable("the branch listing failed")
    return frozenset(line.removeprefix("refs/heads/") for line in result.stdout.splitlines())


@dataclass
class ScanContext:
    """The explicit input of one scan: the root, the memo, the instant, the seam and the one branch listing."""

    repo_root: Path
    memo: memo_module.ResolverMemo
    now: datetime
    fs: FileSystem
    listing: Callable[[Path], frozenset[str]]
    listed: frozenset[str] | None = None

    def branches(self) -> frozenset[str]:
        """The local branches, listed at most once for the whole scan."""
        if self.listed is None:
            self.listed = self.listing(self.repo_root)
        return self.listed


# ---------------------------------------------------------------------------
# The read directory: the strict sibling (D-P3)
# ---------------------------------------------------------------------------


def resolve_scan_dir(repo_root: Path, name: str, entry: memo_module.MemoEntry) -> tuple[Path, str | None]:
    """The directory a Mission is read from and the reason it fell back to its own directory, on the memo's raw outcome.

    Only ``CoordinationBranchDeleted`` falls back; every other resolver exception is raised again, and a read directory outside
    the repository root raises ``ReadDirOutsideRoot``. The v1 helper falls back for three more outcomes, and is not reused.
    """
    own = repo_root / "kitty-specs" / name
    outcome = entry.outcome
    if isinstance(outcome, Exception):
        if isinstance(outcome, CoordinationBranchDeleted):
            return own, FALLBACK_REASON
        raise outcome
    if outcome.resolve() == own.resolve():
        return own, None
    try:
        outcome.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise ReadDirOutsideRoot(name) from error
    return outcome, None


def _resolve_dir(ctx: ScanContext, name: str) -> tuple[Path, str | None]:
    entry = memo_module.memo_resolve(ctx.memo, ctx.repo_root, name)
    try:
        return resolve_scan_dir(ctx.repo_root, name, entry)
    except Exception as error:  # every resolver outcome but the named fallback ends the scan: the exception class is not the reader's to list
        raise ScanUnreadable(type(error).__name__) from error


# ---------------------------------------------------------------------------
# Own-directory reads: meta.json, completion, identity
# ---------------------------------------------------------------------------


def read_meta(own: Path) -> Mapping[str, Any] | None:
    """``meta.json`` of the Mission's own directory, fail-closed: None when absent, ``ScanUnreadable`` when it cannot be read."""
    try:
        return load_meta_fail_closed(own)
    except (MissionMetaReadError, OSError) as error:
        raise ScanUnreadable("meta.json") from error


def merged_at_of(meta: Mapping[str, Any] | None) -> datetime | None:
    """The merge instant ``meta.json`` holds, read as the completion test of the product reads it; None when there is none."""
    raw = meta.get("merged_at") if meta else None
    if not isinstance(raw, str):
        return None
    try:
        return parse_iso(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def completion_of(ctx: ScanContext, read_dir: Path, meta: Mapping[str, Any] | None) -> bool:
    """The two arms of ``is_mission_completed``, applied by the reader (FR-012): the merge marker of the OWN ``meta.json``, else the lifecycle.

    The merge marker is never read from the read directory, which for an unmerged coordination Mission is the coordination
    surface's copy. The lifecycle arm reads the event log of the read directory.
    """
    if merged_at_of(meta) is not None:
        return True
    try:
        state = derive_mission_lifecycle(read_dir, now=ctx.now).state
    except Exception as error:  # the lifecycle reads the event log through the reducer, which raises several classes
        raise ScanUnreadable("the event log") from error
    return state in COMPLETED_STATES


def mission_id_of(own: Path) -> str:
    """The Mission identity of a finding: the v1 identity read; a Mission with no readable ULID cannot carry a finding."""
    try:
        identity = resolve_mission_identity(own)
    except (MissionMetaReadError, OSError, ValueError) as error:
        raise ScanUnreadable("the Mission identity") from error
    value = identity.mission_id
    if not isinstance(value, str) or _ULID.fullmatch(value) is None:
        raise ScanUnreadable("the Mission has no identity a finding can carry")
    return value


def find_mission(repo_root: Path, names: list[str], mission_id: str) -> str | None:
    """The Mission directory name of ``mission_id`` by the v1 identity read, or None.

    A directory whose identity cannot be read matches no identity and does not fail the lookup of another Mission (AD-10).
    """
    for name in names:
        own = repo_root / "kitty-specs" / name
        try:
            load_meta(own, on_malformed="raise")
            identity = resolve_mission_identity(own)
        except (MissionMetaReadError, OSError, ValueError):
            continue
        if identity.mission_id == mission_id:
            return name
    return None


# ---------------------------------------------------------------------------
# Kinds 1 and 2
# ---------------------------------------------------------------------------


def read_file(ctx: ScanContext, path: Path) -> bytes:
    """The bytes of one file the reader owns; an ``OSError`` is ``ScanUnreadable`` (a broken authority is a 500)."""
    try:
        return ctx.fs.read_bytes(path)
    except OSError as error:
        raise ScanUnreadable(path.name) from error


def has_file(ctx: ScanContext, path: Path) -> bool:
    try:
        return ctx.fs.exists(path)
    except OSError as error:
        raise ScanUnreadable(path.name) from error


def parse_snapshot(raw: bytes) -> dict[str, Any] | None:
    """The persisted snapshot as an object, or None when it is not valid UTF-8, not JSON or not an object (``CORRUPT_JSON``, OQ-4)."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        return None
    return value if isinstance(value, dict) else None


def replay(read_dir: Path) -> str:
    """The reducer replay at the snapshot's own generation, serialised as ``classify_status_json`` serialises it (never ``materialize``)."""
    try:
        return str(materialize_to_json(materialize_snapshot(read_dir)))
    except Exception as error:  # the reducer is the authority: any failure of it is a 500, not a finding
        raise ScanUnreadable("the reducer") from error


def normalised(persisted: dict[str, Any]) -> str:
    """The persisted snapshot parsed and serialised with the replay's options, so a byte compare is a content compare."""
    return json.dumps(persisted, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def is_provenance_only(computed: dict[str, Any], persisted: dict[str, Any]) -> bool:
    """True when the two differ only in ``actor``, ``last_event_id`` and ``last_transition_at`` of work packages present on both sides."""
    if {key: value for key, value in computed.items() if key != WORK_PACKAGES} != {key: value for key, value in persisted.items() if key != WORK_PACKAGES}:
        return False
    computed_wps, persisted_wps = computed.get(WORK_PACKAGES, {}), persisted.get(WORK_PACKAGES, {})
    if not isinstance(computed_wps, dict) or not isinstance(persisted_wps, dict) or set(computed_wps) != set(persisted_wps):
        return False
    saw_difference = False
    for wp_id, computed_wp in computed_wps.items():
        persisted_wp = persisted_wps[wp_id]
        if not isinstance(computed_wp, dict) or not isinstance(persisted_wp, dict):
            return False
        differing = {key for key in set(computed_wp) | set(persisted_wp) if computed_wp.get(key) != persisted_wp.get(key)}
        if differing and not differing <= PROVENANCE_FIELDS:
            return False
        saw_difference = saw_difference or bool(differing)
    return saw_difference


def is_terminal(computed: dict[str, Any]) -> bool:
    """True when every work package of the reducer output is ``done``; a Mission with no work package is not terminal."""
    work_packages = computed.get(WORK_PACKAGES, {})
    return isinstance(work_packages, dict) and bool(work_packages) and all(isinstance(wp, dict) and wp.get(LANE) == "done" for wp in work_packages.values())


def classify_variant(computed: dict[str, Any], persisted: dict[str, Any]) -> str:
    """The audit code of a difference, tested in the order of OR-4: provenance only, then all done, then the error."""
    if is_provenance_only(computed, persisted):
        return CODE_PROVENANCE
    if is_terminal(computed):
        return CODE_TERMINAL
    return CODE_DRIFT


def _lane_of(entry: Any) -> Any:
    return entry.get(LANE) if isinstance(entry, dict) else None


def _display(lane: Any) -> str | None:
    return lane if isinstance(lane, str) and lane in STATUS_LANES else None


def lane_comparison(persisted: dict[str, Any], computed: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per work package of the union whose ``lane`` differs, by id in byte order; a lane that is not a display lane reads null (OR-3)."""
    left, right = persisted.get(WORK_PACKAGES), computed.get(WORK_PACKAGES)
    left, right = (left if isinstance(left, dict) else {}), (right if isinstance(right, dict) else {})
    rows = []
    for wp_id in sorted((key for key in set(left) | set(right) if is_wp_id(key)), key=lambda key: key.encode("utf-8")):
        if _lane_of(left.get(wp_id)) != _lane_of(right.get(wp_id)):
            rows.append({"wpId": wp_id, "persistedStatusLane": _display(_lane_of(left.get(wp_id))), "derivedStatusLane": _display(_lane_of(right.get(wp_id)))})
    return rows


def kind1(ctx: ScanContext, read_dir: Path, merged: bool) -> dict[str, Any] | None:
    """Kind 1 for a read directory that holds both files: one finding, or None when the snapshot agrees with the replay."""
    persisted = parse_snapshot(read_file(ctx, read_dir / SNAPSHOT_FILE))
    if persisted is None:
        return raw_finding(KIND_DISAGREES, SNAPSHOT_FILE, CODE_CORRUPT, [], None if merged else REMEDY_MATERIALIZE)
    computed_json = replay(read_dir)
    if computed_json == normalised(persisted):
        return None
    computed = json.loads(computed_json)
    code = classify_variant(computed, persisted)
    remedy = REMEDY_MATERIALIZE if code == CODE_DRIFT and not merged else None
    return raw_finding(KIND_DISAGREES, SNAPSHOT_FILE, code, lane_comparison(persisted, computed), remedy)


def kind2(has_log: bool) -> dict[str, Any]:
    """Kind 2 for a read directory that holds exactly one of the two files; the path is the MISSING file (FR-011, AD-4)."""
    return raw_finding(KIND_MISSING, SNAPSHOT_FILE if has_log else EVENT_LOG_FILE, None, [], REMEDY_MATERIALIZE if has_log else None)


# ---------------------------------------------------------------------------
# Kind 3
# ---------------------------------------------------------------------------


def is_legacy_manifest(data: dict[str, Any]) -> bool:
    """True for a manifest that predates ``mission_slug``: the one place the retired term appears (D-P7, AC-VERSION bullet 5)."""
    return "feature_slug" in data and "mission_slug" not in data


def classify_manifest(raw: bytes) -> LanesManifest | None:
    """The three-way classification of ``lanes.json`` (D-P7): a manifest (current shape), None (legacy shape), or ``ScanUnreadable``."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError) as error:
        raise ScanUnreadable(LANES_FILE) from error
    if not isinstance(data, dict):
        raise ScanUnreadable(LANES_FILE)
    if is_legacy_manifest(data):
        return None
    if "mission_slug" not in data:
        raise ScanUnreadable(LANES_FILE)
    try:
        manifest = LanesManifest.from_dict(data)
    except (KeyError, TypeError, AttributeError) as error:
        raise ScanUnreadable(LANES_FILE) from error
    shaped = isinstance(manifest.mission_slug, str) and isinstance(manifest.mission_branch, str)
    if not shaped or not all(isinstance(lane.lane_id, str) and all(isinstance(wp, str) for wp in lane.wp_ids) for lane in manifest.lanes):
        raise ScanUnreadable(LANES_FILE)
    return manifest


def manifest_of(ctx: ScanContext, own: Path, completed: bool) -> tuple[bool, LanesManifest | None]:
    """The manifest of a Mission that is not completed, as (present, current-shaped manifest); a completed Mission's file is never read."""
    path = own / LANES_FILE
    if completed or not has_file(ctx, path):
        return False, None
    return True, classify_manifest(read_file(ctx, path))


def expected_lane_ids(manifest: LanesManifest, lanes_by_wp: Mapping[str, str]) -> list[str]:
    """The code lanes that hold a work package in an active status lane: an all-planned lane has no branch yet (FR-012 rule 2)."""
    return [lane.lane_id for lane in manifest.lanes if lane.lane_id != PLANNING_LANE_ID and any(lanes_by_wp.get(wp_id) in ACTIVE_LANES for wp_id in lane.wp_ids)]


def expected_branch_names(manifest: LanesManifest, coordination_branch: str | None, lane_ids: list[str]) -> list[str]:
    """The branches the product created for the expected lanes, and the ONE Mission-level branch of the topology (ARCH-001)."""
    if not lane_ids:
        return []
    names = [code_lane_branch_name(manifest.mission_slug, lane_id) for lane_id in lane_ids]
    return [*names, coordination_branch or manifest.mission_branch]


def listing_needed(names: list[str]) -> bool:
    """The listing is made only when a Mission has an expected branch (zero listings otherwise, COMPLETE-001)."""
    return bool(names)


def any_branch_missing(ctx: ScanContext, names: list[str]) -> bool:
    """True when one of ``names`` is not in the single local listing (local branches only, OQ-3)."""
    present = ctx.branches()
    return any(name not in present for name in names)


def coordination_branch_of(meta: Mapping[str, Any] | None) -> str | None:
    """The coordination branch ``meta.json`` names, else None; an absent ``meta.json`` names none."""
    raw = meta.get("coordination_branch") if meta else None
    return raw if isinstance(raw, str) else None


def lanes_by_wp(lanes_json: str) -> dict[str, str]:
    """The status lane of each work package in the reducer output."""
    work_packages = json.loads(lanes_json).get(WORK_PACKAGES, {})
    return {wp_id: str(_lane_of(state)) for wp_id, state in work_packages.items()}


def kind3(ctx: ScanContext, manifest: LanesManifest, meta: Mapping[str, Any] | None, replayed: str) -> dict[str, Any] | None:
    """Kind 3 for a current-shaped manifest: one finding when an expected branch has no local branch, none otherwise."""
    names = expected_branch_names(manifest, coordination_branch_of(meta), expected_lane_ids(manifest, lanes_by_wp(replayed)))
    if not listing_needed(names) or not any_branch_missing(ctx, names):
        return None
    return raw_finding(KIND_BRANCH, LANES_FILE, None, [], None)


# ---------------------------------------------------------------------------
# Findings, order and cap
# ---------------------------------------------------------------------------


def fixed_summary(kind: str, source_code: str | None) -> str:
    """The fixed sentence of a (kind, sourceCode) pair; a pair outside the closed table is a failure of the reader."""
    try:
        return SUMMARIES[(kind, source_code)]
    except KeyError as error:
        raise ValueError(f"the pair ({kind}, {source_code}) is outside the closed table") from error


def raw_finding(kind: str, artifact_path: str, source_code: str | None, comparison: list[dict[str, Any]], remedy: str | None) -> dict[str, Any]:
    """A finding without its Mission identity (added once the scan of the Mission is done)."""
    return {
        "kind": kind,
        "severity": _SEVERITIES.get(source_code or "", SEVERITY_WARNING),
        "missionId": None,
        "artifactPath": artifact_path,
        "summary": fixed_summary(kind, source_code),
        "authority": "git" if kind == KIND_BRANCH else "event_log",
        "derivedSide": "lanes_json" if kind == KIND_BRANCH else "status_json",
        "laneComparison": comparison,
        "remedy": remedy,
        "sourceCode": source_code,
    }


def sort_key(finding: Mapping[str, Any]) -> tuple[bytes, bytes, bytes]:
    """The order of FR-009: ``(missionId, kind, artifactPath)`` in the byte order of the UTF-8 encoding."""
    return (str(finding["missionId"]).encode("utf-8"), str(finding["kind"]).encode("utf-8"), str(finding["artifactPath"]).encode("utf-8"))


def sort_and_cap(findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """The first ``CAP`` findings in order, and whether more existed (exactly ``CAP`` is not truncated)."""
    ordered = sorted(findings, key=sort_key)
    return ordered[:CAP], len(ordered) > CAP


# ---------------------------------------------------------------------------
# One Mission, and the scan
# ---------------------------------------------------------------------------


def scan_mission(ctx: ScanContext, name: str, fallbacks: dict[str, str], legacy: list[str]) -> list[dict[str, Any]]:
    """Every finding of one Mission; the Mission is added to ``fallbacks`` or ``legacy`` when it is one of those."""
    own = ctx.repo_root / "kitty-specs" / name
    read_dir, reason = _resolve_dir(ctx, name)
    if reason is not None:
        fallbacks[name] = reason
    meta = read_meta(own)
    has_snapshot, has_log = has_file(ctx, read_dir / SNAPSHOT_FILE), has_file(ctx, read_dir / EVENT_LOG_FILE)
    found: list[dict[str, Any]] = []
    if has_snapshot and has_log:
        finding = kind1(ctx, read_dir, merged_at_of(meta) is not None)
        found += [finding] if finding is not None else []
    elif has_snapshot != has_log:
        found.append(kind2(has_log))
    present, manifest = manifest_of(ctx, own, completion_of(ctx, read_dir, meta))
    if present and manifest is None:
        legacy.append(name)
    elif manifest is not None:
        finding = kind3(ctx, manifest, meta, replay(read_dir))
        found += [finding] if finding is not None else []
    if found:
        mission_id = mission_id_of(own)
        for finding in found:
            finding["missionId"] = mission_id
    return found


def scan_drift(
    repo_root: Path,
    memo: memo_module.ResolverMemo,
    *,
    clock: Clock,
    mission_id: str | None = None,
    fs: FileSystem = REAL_FS,
    listing: Callable[[Path], frozenset[str]] | None = None,
) -> DriftOutcome:
    """``getDriftReport``: 400 for a ``missionId`` that is not a ULID, 404 for an unknown one, 500 when a read fails, else the report.

    ``clock`` is the service clock (an injected ``Clock``), read once when the scan starts. The scan is project-wide, or the one Mission ``mission_id`` names.
    """
    now = clock.now().astimezone(UTC)
    names = enumerate_missions(repo_root)
    if mission_id is not None:
        if _ULID.fullmatch(mission_id) is None:
            return invalid_identity()
        found = find_mission(repo_root, names, mission_id)
        if found is None:
            return refusal(REFUSAL_NOT_FOUND)
        names = [found]
    ctx = ScanContext(repo_root, memo, now, fs, listing if listing is not None else list_local_branches)
    findings: list[dict[str, Any]] = []
    fallbacks: dict[str, str] = {}
    legacy: list[str] = []
    try:
        for name in names:
            findings += scan_mission(ctx, name, fallbacks, legacy)
    except ScanUnreadable:
        return refusal(REFUSAL_UNREADABLE)
    kept, truncated = sort_and_cap(findings)
    body = {"scannedAt": format_stamp(now, UTC_SECOND_TIMESTAMP_FORMAT), "findings": kept, "truncated": truncated}
    return DriftOutcome(OK, body, fallbacks, tuple(sorted(legacy)))
