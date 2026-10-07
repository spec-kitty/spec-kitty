"""The independent oracles of the Mission Status health, drift and Ops reads (plan D-P14, D-P6; spec FR-025).

An oracle answers the same question as a reference reader by a different route, so that a reader that is consistently wrong is
caught by the comparison. This module therefore imports no reader module of ``tests/contract`` (an AST test of the reality
module asserts it); it shares only the resolver memo (a helper that holds raw resolver outcomes and decides nothing) and public
product readers: the status classifier, the reducer snapshot, the lifecycle test and the lane branch naming.

What is read here is read in a different way from the readers: ``meta.json``, ``lanes.json`` and every Op line are parsed as raw
JSON; the branches are tested with one ``git rev-parse --verify --quiet`` per expected name, never from the readers' single
listing; the evidence of a closure is classified by a regex over the stored string, never by the readers' redaction pipeline.
Nothing here reads a wall clock: an instant is an argument.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel.clock import datetime
from specify_cli.audit.classifiers.status_json import classify_status_json
from specify_cli.lanes.branch_naming import PLANNING_LANE_ID, code_lane_branch_name
from specify_cli.status.lifecycle import derive_mission_lifecycle, is_mission_completed
from specify_cli.status.reducer import materialize_snapshot
from tests.contract._mission_status_memo import ResolverMemo, memo_resolve

FALLBACK_REASON = "coordination_branch_deleted"
KIND_DISAGREES = "snapshot_disagrees_with_event_log"
KIND_MISSING = "snapshot_or_event_log_missing"
KIND_BRANCH = "lane_branch_missing"
SNAPSHOT_NAME = "status.json"
LOG_NAME = "status.events.jsonl"
LANES_NAME = "lanes.json"
OPS_DIRECTORY = "kitty-ops"
SPINE_NAME = "op-closures.jsonl"
# The four codes of kind 1: the classifier also emits legacy-key and unknown-key codes, which belong to no kind of the contract.
KIND1_CODES = frozenset({"SNAPSHOT_DRIFT", "SNAPSHOT_DRIFT_PROVENANCE", "SNAPSHOT_DRIFT_TERMINAL", "CORRUPT_JSON"})
CORRUPT_JSON = "CORRUPT_JSON"
UNREADABLE_PREFIX = "could not read file"
ACTIVE_STATUS_LANES = frozenset({"claimed", "in_progress", "for_review", "in_review", "approved"})
COMPLETED_STATES = frozenset({"recently_completed", "archived"})
PROBE_TIMEOUT = 5.0

# Why an Op is skipped, as the oracle names it (coarser than the reader's reasons: the named list is the legacy completion alone).
SKIP_LEGACY_COMPLETION = "legacy_completion"
SKIP_UNREADABLE = "unreadable_or_malformed"
CATEGORY_NONE = "none"
CATEGORY_ABSOLUTE = "absolute_path"
CATEGORY_URL = "url"
CATEGORY_FREE_TEXT = "free_text"
CATEGORY_RELATIVE = "relative_reference"

_OP_FILE = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}\.jsonl", re.ASCII)
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:[Zz]|[+-]\d{2}:\d{2})", re.ASCII)
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+://", re.ASCII)
_FILE_SCHEME = re.compile(r"file://", re.IGNORECASE)
_DRIVE = re.compile(r"[A-Za-z]:")
_WHITESPACE = re.compile(r"\s")
_BRANCH_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")

# The key a legacy-shape lanes.json carries, assembled so that this module holds no literal of the retired term.
LEGACY_SLUG_KEY = "fea" + "ture" + "_slug"


def run_git(repo_root: Path, *arguments: str, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    """One git call with prompting disabled; the caller judges the exit code."""
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="surrogateescape",
        timeout=timeout,
        env=environment,
    )


# ---------------------------------------------------------------------------
# The network probe: outside the reader, decides online or offline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RemoteState:
    """The configured remotes and those that did not answer ``git ls-remote --heads``."""

    remotes: tuple[str, ...]
    unreachable: tuple[str, ...]

    @property
    def online(self) -> bool:
        """True when every configured remote answers (no remote at all is online: nothing can be unreachable)."""
        return not self.unreachable


def probe_remotes(repo_root: Path, *, timeout: float = PROBE_TIMEOUT) -> RemoteState:
    """Ask every configured remote for its heads; one that errors or times out is unreachable."""
    listing = run_git(repo_root, "remote", timeout=timeout)
    if listing.returncode != 0:
        raise RuntimeError("git could not list the remotes, so the network state is unknown")
    remotes = tuple(sorted(listing.stdout.split()))
    unreachable = []
    for remote in remotes:
        try:
            answered = run_git(repo_root, "ls-remote", "--heads", remote, timeout=timeout).returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            answered = False
        if not answered:
            unreachable.append(remote)
    return RemoteState(remotes, tuple(unreachable))


# ---------------------------------------------------------------------------
# Missions, raw metadata and branches
# ---------------------------------------------------------------------------


def mission_names(repo_root: Path) -> list[str]:
    """The Mission directories of ``kitty-specs/`` that hold a ``meta.json``, sorted: the discovered set."""
    base = repo_root / "kitty-specs"
    if not base.is_dir():
        return []
    return sorted(entry.name for entry in base.iterdir() if (entry / "meta.json").is_file())


def raw_json_object(path: Path) -> dict[str, Any] | None:
    """The JSON object a file holds, or None when it is absent, undecodable, not JSON or not an object."""
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def raw_meta(repo_root: Path, name: str) -> dict[str, Any]:
    """``meta.json`` of a Mission as raw JSON; an unreadable one is an error of the corpus the oracle cannot answer for."""
    meta = raw_json_object(repo_root / "kitty-specs" / name / "meta.json")
    if meta is None:
        raise ValueError(f"{name}: meta.json is not a readable JSON object")
    return meta


def mission_id_of(meta: Mapping[str, Any]) -> str | None:
    value = meta.get("mission_id")
    return value if isinstance(value, str) else None


def local_heads(repo_root: Path) -> frozenset[str]:
    """The local branch names: one ``git for-each-ref refs/heads`` listing."""
    result = run_git(repo_root, "for-each-ref", "--format=%(refname)", "refs/heads")
    if result.returncode != 0:
        raise RuntimeError("the branch listing failed")
    return frozenset(line.removeprefix("refs/heads/") for line in result.stdout.splitlines() if line)


def worktree_branches(repo_root: Path) -> frozenset[str]:
    """The branches checked out in a worktree: ``git worktree list --porcelain``."""
    result = run_git(repo_root, "worktree", "list", "--porcelain")
    if result.returncode != 0:
        raise RuntimeError("the worktree listing failed")
    return frozenset(line.split(" ", 1)[1].removeprefix("refs/heads/") for line in result.stdout.splitlines() if line.startswith("branch "))


def remote_tracking_names(repo_root: Path) -> frozenset[str]:
    """The branch names held as remote-tracking refs (the arm of the resolver the derivation does not mirror)."""
    result = run_git(repo_root, "for-each-ref", "--format=%(refname)", "refs/remotes")
    if result.returncode != 0:
        raise RuntimeError("the remote-tracking listing failed")
    return frozenset(line.removeprefix("refs/remotes/").partition("/")[2] for line in result.stdout.splitlines() if line)


def current_branch(repo_root: Path) -> str | None:
    """The branch ``HEAD`` points at (with or without a commit), asked of git; None for a detached ``HEAD`` or a name this contract cannot carry."""
    result = run_git(repo_root, "symbolic-ref", "--short", "-q", "HEAD")
    name = result.stdout.strip()
    return name if result.returncode == 0 and _BRANCH_NAME.fullmatch(name) else None


def branch_exists(repo_root: Path, branch: str) -> bool:
    """Whether ``refs/heads/<branch>`` resolves: one ``git rev-parse --verify --quiet`` per name (a different read than a listing)."""
    return run_git(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def derive_fallbacks(repo_root: Path, names: list[str], heads: frozenset[str], worktrees: frozenset[str]) -> dict[str, str]:
    """The Missions the resolver is expected to answer ``CoordinationBranchDeleted`` for (FRESH3-002): an agreement check, not a mirror.

    ``meta.json`` names a ``coordination_branch``, holds no ``merged_at``, and the branch is in neither the local heads nor a worktree.
    It does not reproduce the resolver's reopen-aware merged test, its stored-topology gate or its remote arms.
    """
    found: dict[str, str] = {}
    for name in names:
        meta = raw_meta(repo_root, name)
        branch = meta.get("coordination_branch")
        if not isinstance(branch, str) or not branch or meta.get("merged_at"):
            continue
        if branch not in heads and branch not in worktrees:
            found[name] = FALLBACK_REASON
    return found


def derived_but_remote_present(repo_root: Path, fallbacks: Mapping[str, str], remote_names: frozenset[str]) -> list[str]:
    """The derived fallback Missions whose branch exists as a remote-tracking ref: the resolver judges those present (FRESH4-004)."""
    return sorted(name for name in fallbacks if raw_meta(repo_root, name)["coordination_branch"] in remote_names)


# ---------------------------------------------------------------------------
# Kinds 1 and 2
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OracleFinding:
    """One finding as the oracle states it: the Mission identity, the kind, the path and the audit code."""

    mission_id: str
    kind: str
    artifact_path: str
    source_code: str | None


@dataclass(frozen=True)
class ReadDirs:
    """The directory each Mission is read from, and the resolver outcomes that are neither a directory nor the named fallback."""

    dirs: dict[str, Path]
    resolver_errors: dict[str, str]


def read_directories(repo_root: Path, names: list[str], fallbacks: Mapping[str, str], memo: ResolverMemo) -> ReadDirs:
    """Each Mission's read directory: the memo's resolver outcome, or the own directory for a Mission on the derived fallback list.

    An exception that is not the named fallback is recorded by class name, never absorbed (that list is expected empty); the own
    directory is then used so the other comparisons still run.
    """
    dirs: dict[str, Path] = {}
    errors: dict[str, str] = {}
    for name in names:
        own = repo_root / "kitty-specs" / name
        if name in fallbacks:
            dirs[name] = own
            continue
        outcome = memo_resolve(memo, repo_root, name).outcome
        if isinstance(outcome, Exception):
            errors[name] = type(outcome).__name__
            dirs[name] = own
        else:
            dirs[name] = Path(outcome)
    return ReadDirs(dirs, errors)


def snapshot_codes(read_dir: Path) -> list[str]:
    """The kind-1 codes of ``classify_status_json`` over one directory: the classifier filtered to the four codes (FR-025).

    An undecodable snapshot raises ``UnicodeDecodeError`` out of the classifier; it is ``CORRUPT_JSON``, as in the reader. The
    ``CORRUPT_JSON`` the classifier emits for a file it could not read at all is dropped: the reader answers 500 there.
    """
    try:
        findings = classify_status_json(read_dir)
    except UnicodeDecodeError:
        return [CORRUPT_JSON]
    return [
        finding.code for finding in findings if finding.code in KIND1_CODES and not (finding.code == CORRUPT_JSON and finding.detail.startswith(UNREADABLE_PREFIX))
    ]


def kinds_one_and_two(repo_root: Path, names: list[str], read_dirs: Mapping[str, Path]) -> list[OracleFinding]:
    """Kinds 1 and 2: file presence in the read directory, and the filtered classifier for a directory that holds both files."""
    found: list[OracleFinding] = []
    for name in names:
        read_dir = read_dirs[name]
        has_snapshot, has_log = (read_dir / SNAPSHOT_NAME).exists(), (read_dir / LOG_NAME).exists()
        mission_id = mission_id_of(raw_meta(repo_root, name)) or ""
        if has_snapshot and has_log:
            found.extend(OracleFinding(mission_id, KIND_DISAGREES, SNAPSHOT_NAME, code) for code in snapshot_codes(read_dir))
        elif has_snapshot != has_log:
            found.append(OracleFinding(mission_id, KIND_MISSING, LOG_NAME if has_snapshot else SNAPSHOT_NAME, None))
    return found


# ---------------------------------------------------------------------------
# Kind 3 (D-P6)
# ---------------------------------------------------------------------------


def is_completed(repo_root: Path, name: str, read_dir: Path, now: datetime) -> bool:
    """Completion as the product tests it: ``is_mission_completed`` on the own directory, else the two arms read directly (COMPLETE-012)."""
    own = repo_root / "kitty-specs" / name
    if read_dir.resolve() == own.resolve():
        return is_mission_completed(own, now=now)
    if raw_meta(repo_root, name).get("merged_at"):
        return True
    return derive_mission_lifecycle(read_dir, now=now).state in COMPLETED_STATES


def expected_branches(manifest: Mapping[str, Any], meta: Mapping[str, Any], read_dir: Path) -> list[str]:
    """The branches the product created for the lanes that hold a work package in an active status lane, and the one Mission-level branch."""
    lane_of = {wp_id: str(state.get("lane")) for wp_id, state in materialize_snapshot(read_dir).work_packages.items()}
    lanes = [lane for lane in manifest["lanes"] if lane["lane_id"] != PLANNING_LANE_ID and any(lane_of.get(wp) in ACTIVE_STATUS_LANES for wp in lane["wp_ids"])]
    if not lanes:
        return []
    coordination = meta.get("coordination_branch")
    mission_level = coordination if isinstance(coordination, str) and coordination else manifest["mission_branch"]
    return [*(code_lane_branch_name(manifest["mission_slug"], lane["lane_id"]) for lane in lanes), mission_level]


@dataclass(frozen=True)
class Kind3Oracle:
    """Kind 3 over the corpus: the findings, the legacy-shaped manifests (named, not evaluated) and the population they come from."""

    findings: dict[str, OracleFinding]
    legacy: tuple[str, ...]
    population: int
    completed: int


def kind_three(repo_root: Path, names: list[str], read_dirs: Mapping[str, Path], now: datetime) -> Kind3Oracle:
    """One finding per Mission that is not completed, holds a current-shaped manifest and has an expected branch with no local ref."""
    findings: dict[str, OracleFinding] = {}
    legacy: list[str] = []
    population = completed = 0
    for name in names:
        read_dir = read_dirs[name]
        if is_completed(repo_root, name, read_dir, now):
            completed += 1
            continue
        path = repo_root / "kitty-specs" / name / LANES_NAME
        if not path.exists():
            continue
        manifest = raw_json_object(path)
        if manifest is None:
            raise ValueError(f"{name}: lanes.json is not a readable JSON object")
        population += 1
        if LEGACY_SLUG_KEY in manifest and "mission_slug" not in manifest:
            legacy.append(name)
            continue
        meta = raw_meta(repo_root, name)
        if any(not branch_exists(repo_root, branch) for branch in expected_branches(manifest, meta, read_dir)):
            findings[name] = OracleFinding(mission_id_of(meta) or "", KIND_BRANCH, LANES_NAME, None)
    return Kind3Oracle(findings, tuple(sorted(legacy)), population, completed)


def completion_pairs(repo_root: Path, names: list[str], now: datetime) -> dict[str, bool]:
    """``is_mission_completed`` of the own directory of every Mission that declares no coordination branch (AC-DRIFT row 19)."""
    pairs: dict[str, bool] = {}
    for name in names:
        branch = raw_meta(repo_root, name).get("coordination_branch")
        if isinstance(branch, str) and branch:
            continue
        pairs[name] = is_mission_completed(repo_root / "kitty-specs" / name, now=now)
    return pairs


@dataclass(frozen=True)
class DriftOracle:
    """Everything the drift oracles say about one repository."""

    names: list[str]
    fallbacks: dict[str, str]
    remote_present: list[str]
    resolver_errors: dict[str, str]
    findings: list[OracleFinding]
    kind3: Kind3Oracle


def drift_oracle(repo_root: Path, memo: ResolverMemo, now: datetime) -> DriftOracle:
    """The independent expectation of the project-wide drift read: fallbacks, kinds 1 to 3, and the named lists."""
    names = mission_names(repo_root)
    fallbacks = derive_fallbacks(repo_root, names, local_heads(repo_root), worktree_branches(repo_root))
    dirs = read_directories(repo_root, names, fallbacks, memo)
    kind3 = kind_three(repo_root, names, dirs.dirs, now)
    remote_present = derived_but_remote_present(repo_root, fallbacks, remote_tracking_names(repo_root))
    return DriftOracle(names, fallbacks, remote_present, dirs.resolver_errors, kinds_one_and_two(repo_root, names, dirs.dirs), kind3)


# ---------------------------------------------------------------------------
# Ops: a direct scan of every Op file and of the spine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OracleOp:
    """One served Op as the direct scan states it."""

    invocation_id: str
    status: str
    outcome: str | None
    closed_by: str | None
    completed_at: str | None
    evidence_category: str | None
    own_file_completion: bool
    spine_closed: bool


@dataclass
class OpsScan:
    """The Ops of a repository: the served ones, and the skipped ones with the oracle's coarse reason."""

    served: dict[str, OracleOp] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)

    def legacy_completions(self) -> list[str]:
        return sorted(op for op, reason in self.skipped.items() if reason == SKIP_LEGACY_COMPLETION)


def evidence_category(stored: str | None) -> str:
    """The class of a stored evidence reference by regex alone: none, absolute path, address, free text or relative reference."""
    if stored is None:
        return CATEGORY_NONE
    if _FILE_SCHEME.match(stored):
        return CATEGORY_ABSOLUTE
    if _SCHEME.match(stored):
        return CATEGORY_URL
    if stored.startswith(("/", "~/", chr(92) * 2)) or _DRIVE.match(stored):
        return CATEGORY_ABSOLUTE
    if not stored or _WHITESPACE.search(stored):
        return CATEGORY_FREE_TEXT
    return CATEGORY_RELATIVE


def _object_of(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _is_instant(value: Any) -> bool:
    return isinstance(value, str) and _INSTANT.fullmatch(value) is not None


def _is_closing(record: Mapping[str, Any], invocation_id: str) -> bool:
    """A completion line of the current shape for this Op: ``closed_by`` present, a stated outcome, and an instant."""
    return record.get("event") == "completed" and record.get("invocation_id") == invocation_id and isinstance(record.get("closed_by"), str)


def spine_closures(repo_root: Path) -> dict[str, dict[str, Any]]:
    """The first closing record per invocation id of ``op-closures.jsonl``; none when the spine is absent."""
    path = repo_root / OPS_DIRECTORY / SPINE_NAME
    if not path.exists():
        return {}
    closures: dict[str, dict[str, Any]] = {}
    for line in path.read_bytes().decode("utf-8").split("\n"):
        record = _object_of(line)
        if record is not None and isinstance(record.get("invocation_id"), str) and _is_closing(record, record["invocation_id"]):
            closures.setdefault(record["invocation_id"], record)
    return closures


def _started_is_readable(first: Mapping[str, Any] | None, invocation_id: str) -> bool:
    if first is None or first.get("event") != "started" or first.get("invocation_id") != invocation_id:
        return False
    # ``mode_of_work`` is present in every record of the current shape; its absence marks the legacy shape.
    return "mode_of_work" in first and all(isinstance(first.get(key), str) for key in ("profile_id", "action", "actor")) and _is_instant(first.get("started_at"))


def _op_of(invocation_id: str, closure: Mapping[str, Any] | None, *, own: bool) -> OracleOp:
    if closure is None:
        return OracleOp(invocation_id, "open", None, None, None, None, False, False)
    stored = closure.get("evidence_ref")
    return OracleOp(
        invocation_id,
        "closed",
        closure.get("outcome"),
        closure.get("closed_by"),
        closure.get("completed_at"),
        evidence_category(stored if isinstance(stored, str) else None),
        own,
        not own,
    )


def scan_ops(repo_root: Path) -> OpsScan:
    """Read every Op file of ``kitty-ops/`` and the spine directly. An Op closes by its own completion line, else by the spine."""
    scan = OpsScan()
    directory = repo_root / OPS_DIRECTORY
    if not directory.is_dir():
        return scan
    spine = spine_closures(repo_root)
    for name in sorted(os.listdir(directory)):
        if _OP_FILE.fullmatch(name) is None:
            continue
        invocation_id = name.removesuffix(".jsonl")
        try:
            lines = (directory / name).read_bytes().decode("utf-8").split("\n")
        except UnicodeDecodeError:
            scan.skipped[invocation_id] = SKIP_UNREADABLE
            continue
        if not _started_is_readable(_object_of(lines[0]), invocation_id):
            scan.skipped[invocation_id] = SKIP_UNREADABLE
            continue
        records = [record for record in (_object_of(line) for line in lines[1:]) if record is not None]
        completions = [record for record in records if record.get("event") == "completed" and record.get("invocation_id") == invocation_id]
        own = completions[0] if completions else None
        legacy = own is not None and not _is_closing(own, invocation_id)
        closing = own if own is not None and not legacy else spine.get(invocation_id)
        if closing is None and legacy:
            scan.skipped[invocation_id] = SKIP_LEGACY_COMPLETION
        elif closing is not None and not _is_instant(closing.get("completed_at")):
            scan.skipped[invocation_id] = SKIP_UNREADABLE
        else:
            scan.served[invocation_id] = _op_of(invocation_id, closing, own=closing is own)
    return scan
