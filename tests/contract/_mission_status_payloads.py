"""Test-side builders for the ``mission-status`` contract payloads (FR-003 to FR-007, FR-009, FR-012).

Nothing here is a test and nothing here writes. The module builds the overview, detail and work package
payloads and the event projection from this repository's own Missions, composing only the public,
read-only status readers (``materialize_snapshot``, ``load_meta``, ``resolve_mission_identity``,
``compute_weighted_progress``, ``reconstruct_wp_view``, ``dependency_readiness_for_wp``, the tail reader and
``read_authored_wp_frontmatter``). The writing ``materialize`` is never imported: a reader that wrote to
``kitty-specs/`` would be a severity-5 defect, and the reality check proves it did not (see
``tree_fingerprint``).

Derivations that have no public reader (lifecycle status, phases, ``readyToStart``, ``missionCount``,
``nextAction``) are the executable form of the rules written in the contract's schema descriptions, which are
the single authority. The unit tests cover every branch and the pinned expected-output fixture keeps the copy
from testing only itself.

String fields fall into the classes of spec D-14: strict fields (identifiers, handles, branch names,
dependencies, owned files, requirement refs, subtask ids, tracker refs) become null where nullable and are a
projection error otherwise; human text fields pass through when clean and have only the matching substring
replaced by ``[path]`` or ``[email]`` when not. Every redaction is recorded with its Mission and field.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from kernel.clock import parse_iso
from mission_runtime.identity import resolve_mid8
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.core.dependency_graph import dependency_readiness_for_wp
from specify_cli.mission_metadata import load_meta, resolve_mission_identity
from specify_cli.status.aggregate import CoordAuthorityUnavailable, MissionMetadataUnavailable, MissionStatus
from specify_cli.status.lifecycle_events import LIFECYCLE_EVENT_TYPES
from specify_cli.status.progress import compute_weighted_progress
from specify_cli.status.reducer import materialize_snapshot
from specify_cli.status.tail_reader import EMPTY_DIGEST, TailCursor, poll_once
from specify_cli.status.wp_metadata import WPMetadata, read_authored_wp_frontmatter
from specify_cli.status.wp_view import reconstruct_wp_view
from tests.contract._loader import load_tool

# ---------------------------------------------------------------------------
# Vocabularies and constants
# ---------------------------------------------------------------------------

STATUS_LANES: tuple[str, ...] = (
    "planned",
    "claimed",
    "in_progress",
    "for_review",
    "in_review",
    "approved",
    "done",
    "blocked",
    "canceled",
)
NON_DISPLAY_LANES = frozenset({"genesis", "uninitialized"})
TOPOLOGIES: tuple[str, ...] = ("lanes", "single_branch", "coord", "lanes_with_coord")
UNKNOWN_TOPOLOGY = "unknown"
LIFECYCLE_STATUSES: tuple[str, ...] = ("active", "planned", "done", "draft", "discarded")
PHASE_NAMES: tuple[str, ...] = ("specify", "plan", "tasks", "implement", "review")

# The seven lifecycle types the contract forwards: a set owned by this contract (spec FR-007), deliberately
# smaller than the runtime's LIFECYCLE_EVENT_TYPES.
LIFECYCLE_ALLOW_LIST: frozenset[str] = frozenset(
    {
        "MissionCreated",
        "SpecifyStarted",
        "SpecifyCompleted",
        "PlanStarted",
        "PlanCompleted",
        "TasksStarted",
        "TasksCompleted",
    }
)
PHASE_ARTIFACTS = {"specify": "spec.md", "plan": "plan.md", "tasks": "tasks.md"}
PHASE_MARKERS = {
    "specify": ("SpecifyStarted", "SpecifyCompleted"),
    "plan": ("PlanStarted", "PlanCompleted"),
    "tasks": ("TasksStarted", "TasksCompleted"),
}

_ACTIVE_LANES = ("claimed", "in_progress", "for_review", "in_review", "approved")
_REVIEWED_OR_LATER = ("for_review", "in_review", "approved", "done", "canceled")
_REVIEW_STARTED = ("for_review", "in_review", "approved", "done")
_HANDLE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_RELATIVE_REFERENCE = re.compile(r"^(?![A-Za-z]:)[^/\\~].{0,255}$")
_WP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MISSION_ID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_SENTINELS = frozenset({"__resolved_model_absent__", "__resolved_profile_absent__", "__resolved_profile_version_absent__", "__resolved_provider_absent__"})
_PATH_TOKEN = "[path]"
_EMAIL_TOKEN = "[email]"
_REVIEW_THEN_ACCEPT = "Run /spec-kitty.review in your coding agent, then: spec-kitty accept --mission {slug}"
_CONSOLIDATE = "Run: spec-kitty consolidate --mission {slug}"
DRAIN_BY_FLOOR = "2026-10-02"

_ISSUE_REFERENCE = re.compile(r"^#?[0-9]+$")
_OWNER_HANDLE = re.compile(r"^@[A-Za-z0-9][A-Za-z0-9-]*(/[A-Za-z0-9._-]+)?$")
_ISO_DATE = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")

SCHEMA_OVERVIEW = "MissionOverview"
SCHEMA_DETAIL = "MissionDetail"
SCHEMA_WORK_PACKAGE = "WorkPackage"
SCHEMA_PROJECT = "Project"
SCHEMA_TRANSITION_EVENT = "StatusTransitionEvent"
SCHEMA_LIFECYCLE_EVENT = "MissionLifecycleEvent"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProjectionError(Exception):
    """A real value cannot be projected into the contract (a strict field that is not nullable, or an unknown lane)."""

    def __init__(self, mission: str, field_name: str, detail: str) -> None:
        super().__init__(f"{mission}: {field_name}: {detail}")
        self.mission = mission
        self.field_name = field_name
        self.detail = detail


class EmptyCaseListError(RuntimeError):
    """The per-Mission case list is empty: a collection error, never a silent skip."""


class EmptyFingerprintError(RuntimeError):
    """The read-only proof hashed zero files, so it would prove nothing."""


# ---------------------------------------------------------------------------
# Discovery, floors and the read-only proof
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Floors:
    """Pinned floors, set below the measured corpus (research R-8: 541 Missions, 3156 files, 2967 snapshot work packages)."""

    missions: int = 500
    work_package_payloads: int = 3000
    snapshot_work_packages: int = 2800


FLOORS = Floors()


def enumerate_missions(repo_root: Path) -> list[str]:
    """The Mission directory names under ``kitty-specs/`` that hold a ``meta.json``, sorted."""
    base = repo_root / "kitty-specs"
    if not base.is_dir():
        return []
    return sorted(entry.name for entry in base.iterdir() if (entry / "meta.json").is_file())


def require_cases(cases: Sequence[str]) -> list[str]:
    """Refuse an empty case list: pytest would otherwise skip an empty parameter set silently."""
    if not cases:
        raise EmptyCaseListError("the Mission enumeration is empty, so the reality check would run no case")
    return list(cases)


@dataclass(frozen=True)
class Fingerprint:
    """Bytes of every tracked file under one path, plus ``git status`` for it (catches created files)."""

    files: int
    digest: str
    porcelain: tuple[str, ...]


def _git() -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for the read-only proof")
    return git


def tree_fingerprint(repo_root: Path, subpath: str) -> Fingerprint:
    """Fingerprint every tracked file under ``subpath`` (``git ls-files``) and the porcelain status of it."""
    git = _git()
    listing = subprocess.run([git, "-C", str(repo_root), "ls-files", "-z", "--", subpath], capture_output=True, check=True).stdout
    names = sorted(name for name in listing.split(b"\0") if name)
    if not names:
        raise EmptyFingerprintError(f"git lists no file under {subpath}, so nothing could be hashed")
    digest = hashlib.blake2b()
    for name in names:
        path = repo_root / name.decode("utf-8")
        content = path.read_bytes() if path.is_file() else b"<missing>"
        digest.update(name + b"\0" + hashlib.blake2b(content).digest())
    status = subprocess.run([git, "-C", str(repo_root), "status", "--porcelain", "--", subpath], capture_output=True, check=True, text=True).stdout
    return Fingerprint(files=len(names), digest=digest.hexdigest(), porcelain=tuple(sorted(status.splitlines())))


# ---------------------------------------------------------------------------
# Pure derivations (the executable form of the contract's x-derived rules)
# ---------------------------------------------------------------------------


def _count(lane_counts: Mapping[str, int], lanes: Iterable[str]) -> int:
    return sum(lane_counts.get(lane, 0) for lane in lanes)


def derive_lifecycle_status(lane_counts: Mapping[str, int], wp_total: int, discarded_at: str | None, accepted_at: str | None) -> str:
    """D-5, evaluated in order: discarded, draft, active, planned, then active until accepted and done after."""
    if discarded_at:
        return "discarded"
    if wp_total == 0:
        return "draft"
    if _count(lane_counts, _ACTIVE_LANES):
        return "active"
    if _count(lane_counts, ("planned", "blocked")):
        return "planned"
    return "done" if accepted_at else "active"


def derive_phase_status(name: str, lane_counts: Mapping[str, int], wp_total: int, artifacts: frozenset[str], lifecycle_types: frozenset[str]) -> dict[str, str]:
    """One entry of ``MissionDetail.phases``: specify, plan and tasks by artifact then lifecycle event; the rest by lanes."""
    if name in PHASE_ARTIFACTS:
        started, completed = PHASE_MARKERS[name]
        if PHASE_ARTIFACTS[name] in artifacts:
            return {"name": name, "status": "complete", "basis": "artifact"}
        if completed in lifecycle_types:
            return {"name": name, "status": "complete", "basis": "lifecycle_event"}
        if started in lifecycle_types:
            return {"name": name, "status": "in_progress", "basis": "lifecycle_event"}
        return {"name": name, "status": "pending", "basis": "artifact"}
    basis = "derived_from_status_lanes"
    if name == "implement":
        if wp_total > 0 and _count(lane_counts, _REVIEWED_OR_LATER) == wp_total:
            return {"name": name, "status": "complete", "basis": basis}
        if _count(lane_counts, ("planned", "blocked")) == wp_total:
            return {"name": name, "status": "pending", "basis": basis}
        return {"name": name, "status": "in_progress", "basis": basis}
    if name == "review":
        if wp_total > 0 and _count(lane_counts, ("done", "canceled")) == wp_total:
            return {"name": name, "status": "complete", "basis": basis}
        if not _count(lane_counts, _REVIEW_STARTED):
            return {"name": name, "status": "pending", "basis": basis}
        return {"name": name, "status": "in_progress", "basis": basis}
    raise ValueError(f"unknown Mission phase {name!r}")


def derive_phases(lane_counts: Mapping[str, int], wp_total: int, artifacts: frozenset[str], lifecycle_types: frozenset[str]) -> list[dict[str, str]]:
    """The five phases in workflow order."""
    return [derive_phase_status(name, lane_counts, wp_total, artifacts, lifecycle_types) for name in PHASE_NAMES]


def derive_next_action(slug: str, accepted_at: str | None, has_baseline: bool, lane_counts: Mapping[str, int]) -> str | None:
    """Null once accepted; the review-then-accept sentence with a merge baseline; the consolidate sentence when finished."""
    if accepted_at:
        return None
    if has_baseline:
        return _REVIEW_THEN_ACCEPT.format(slug=slug)
    total = sum(lane_counts.values())
    if total and _count(lane_counts, ("done", "canceled")) == total and lane_counts.get("done", 0) > 0:
        return _CONSOLIDATE.format(slug=slug)
    return None


def derive_ready_to_start(status_lane: str | None, readiness_satisfied: bool) -> bool:
    """True only for a planned work package whose dependencies are satisfied (a null lane is never ready)."""
    return status_lane == "planned" and readiness_satisfied


def derive_project(name: str, overviews: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """``missionCount`` is the number of overview records."""
    return {"name": name, "missionCount": len(overviews)}


def overview_order_key(overview: Mapping[str, Any]) -> tuple[Any, str]:
    """Sort key for ``createdAt`` descending (as an instant), then ``missionId`` ascending."""
    created = parse_iso(str(overview["createdAt"]))
    return (-created.timestamp(), str(overview["missionId"]))


def order_overviews(overviews: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(overviews, key=overview_order_key)


def ordering_problems(overviews: Sequence[Mapping[str, Any]]) -> list[str]:
    """Strict ordering of a built list: any inversion or tie, and a duplicate ``missionId``, is a problem."""
    problems: list[str] = []
    keys = [overview_order_key(item) for item in overviews]
    for index in range(1, len(keys)):
        if keys[index - 1] == keys[index]:
            problems.append(f"tie at {index}: {overviews[index]['missionId']}")
        elif keys[index - 1] > keys[index]:
            problems.append(f"inversion at {index}: {overviews[index]['missionId']}")
    ids = Counter(str(item["missionId"]) for item in overviews)
    problems.extend(f"duplicate missionId {mission_id}" for mission_id, count in sorted(ids.items()) if count > 1)
    return problems


# ---------------------------------------------------------------------------
# The ratchet: header format and shrink-only ceiling
# ---------------------------------------------------------------------------


def ratchet_header_problems(header: Mapping[str, Any]) -> list[str]:
    """Problems with the ratchet keys of the pinned fixture header (issue, owner, drain_by, ceiling)."""
    problems: list[str] = []
    issue, owner, drain_by = header.get("issue"), header.get("owner"), header.get("drain_by")
    if not isinstance(issue, str) or not _ISSUE_REFERENCE.match(issue):
        problems.append(f"issue must be a numeric issue reference, not {issue!r}")
    if not isinstance(owner, str) or not _OWNER_HANDLE.match(owner):
        problems.append(f"owner must be an @-prefixed handle, not {owner!r}")
    if not isinstance(drain_by, str) or not _ISO_DATE.match(drain_by):
        problems.append(f"drain_by must be an ISO date, not {drain_by!r}")
    elif drain_by < DRAIN_BY_FLOOR:
        problems.append(f"drain_by {drain_by} is before the pinned floor {DRAIN_BY_FLOOR}")
    ceiling = header.get("ceiling")
    if not isinstance(ceiling, int) or isinstance(ceiling, bool) or ceiling < 0:
        problems.append(f"ceiling must be a non-negative integer, not {ceiling!r}")
    return problems


def ceiling_problem(measured: int, ceiling: int) -> str | None:
    """Above the ceiling the list grew; below it the ceiling is stale and must be lowered (shrink-only)."""
    if measured > ceiling:
        return (
            f"the disagreement list grew: {measured} Missions, ceiling {ceiling}. A new Mission must commit its status snapshot "
            "together with its work package files, or fix the snapshot or files of the Mission listed below. header.ceiling in "
            "tests/contract/fixtures/mission_status_expected.json may only be lowered, never raise it; the tracker and owner "
            "named in that header own the drain"
        )
    if measured < ceiling:
        return f"stale ceiling: lower header.ceiling in tests/contract/fixtures/mission_status_expected.json to {measured}"
    return None


# ---------------------------------------------------------------------------
# Redaction and projection of single values
# ---------------------------------------------------------------------------


@dataclass
class Projector:
    """Projects real values into contract values for one Mission and records every redaction."""

    leak: ModuleType
    mission: str
    redactions: list[tuple[str, str, str]] = field(default_factory=list)

    def handle(self, value: Any) -> str | None:
        """An actor-handle value: null unless it is a string that fits the handle shape (sentinels read as null)."""
        if isinstance(value, str) and value not in _SENTINELS and _HANDLE.match(value):
            return value
        return None

    def actor(self, stored: Any) -> dict[str, str | None]:
        """D-10: a structured actor field by field, a plain handle string as ``tool``, anything else all-null."""
        if isinstance(stored, Mapping):
            return {key: self.handle(stored.get(key)) for key in ("tool", "role", "profile")}
        return {"tool": self.handle(stored), "role": None, "profile": None}

    def strict(self, value: Any, field_name: str, *, nullable: bool, pattern: re.Pattern[str] | None = None) -> str | None:
        """A strict field: a clean string, or null when nullable, or a projection error."""
        if value is None:
            if nullable:
                return None
            raise ProjectionError(self.mission, field_name, "a required strict field is missing")
        clean = isinstance(value, str) and value != "" and not self.leak.leak_codes(value, self.leak.STRICT) and (pattern is None or bool(pattern.match(value)))
        if clean:
            return str(value)
        if nullable:
            self.redactions.append((self.mission, field_name, "nulled"))
            return None
        raise ProjectionError(self.mission, field_name, "a strict field holds a value that is not representable")

    def strict_list(self, values: Any, field_name: str, pattern: re.Pattern[str] | None = None) -> list[str]:
        if values is None:
            return []
        if not isinstance(values, (list, tuple)):
            raise ProjectionError(self.mission, field_name, "expected a list")
        return [str(self.strict(item, field_name, nullable=False, pattern=pattern)) for item in values]

    def human(self, value: Any, field_name: str) -> str | None:
        """A human text field: clean text passes through; only the matching substring is replaced otherwise."""
        if value is None:
            return None
        text = str(value)
        for pattern in self.leak.HUMAN_HOST_PATH_PATTERNS:
            widened = re.compile(pattern.pattern + r"\S*", pattern.flags)
            text, replaced = widened.subn(_PATH_TOKEN, text)
            if replaced:
                self.redactions.append((self.mission, field_name, "path"))
        text, replaced = self.leak.EMAIL_PATTERN.subn(_EMAIL_TOKEN, text)
        if replaced:
            self.redactions.append((self.mission, field_name, "email"))
        if self.leak.leak_codes(text, self.leak.HUMAN):
            raise ProjectionError(self.mission, field_name, "redaction left a leak in a human text field")
        return text

    def lane(self, value: Any, field_name: str) -> str | None:
        """A display lane, or null for the non-display lanes and for no lane at all."""
        if value is None or str(value) in NON_DISPLAY_LANES:
            return None
        if str(value) not in STATUS_LANES:
            raise ProjectionError(self.mission, field_name, f"{value!r} is not a status lane")
        return str(value)


def normalise_quoted(value: Any) -> str | None:
    """``execution_mode`` is sometimes stored with literal quotes around it; strip one balanced pair."""
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return text or None


# ---------------------------------------------------------------------------
# Contract loading and validation (resolver only, no skip path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractTools:
    resolver: ModuleType
    leak: ModuleType
    formats: ModuleType
    fixtures: ModuleType


def load_contract_tools(mp: pytest.MonkeyPatch, repo_root: Path) -> ContractTools:
    """Load the three contract tools by file path through the shared loader (no sys.path or sys.modules edits of our own)."""
    tools = repo_root / "contracts" / "tools"
    return ContractTools(
        resolver=load_tool(mp, tools / "contract_resolver.py", "contract_resolver_for_status_payloads", syspath=tools),
        leak=load_tool(mp, tools / "leak_patterns.py", "leak_patterns_for_status_payloads"),
        formats=load_tool(mp, tools / "schema_formats.py", "schema_formats_for_status_payloads"),
        fixtures=load_tool(mp, tools / "fixture_builder.py", "fixture_builder_for_status_payloads"),
    )


def _schema_nodes(tree: Any, found: dict[str, dict[str, Any]]) -> None:
    if isinstance(tree, list):
        for item in tree:
            _schema_nodes(item, found)
    elif isinstance(tree, dict):
        title = tree.get("title")
        if isinstance(title, str) and isinstance(tree.get("examples"), list):
            found.setdefault(title, tree)
        for key, value in tree.items():
            if key not in {"examples", "example", "default", "enum", "const"}:
                _schema_nodes(value, found)


class Contract:
    """The resolved ``mission-status`` module and one validator per payload schema."""

    def __init__(self, tools: ContractTools, module_dir: Path) -> None:
        resolution = tools.resolver.resolve(module_dir)
        nodes: dict[str, dict[str, Any]] = {}
        _schema_nodes(resolution.tree, nodes)
        wanted = (SCHEMA_OVERVIEW, SCHEMA_DETAIL, SCHEMA_WORK_PACKAGE, SCHEMA_PROJECT, SCHEMA_TRANSITION_EVENT, SCHEMA_LIFECYCLE_EVENT)
        missing = [title for title in wanted if title not in nodes]
        if missing:
            raise RuntimeError(f"the resolved contract has no schema titled {missing}")
        self._validators = {title: Draft202012Validator(nodes[title], format_checker=tools.formats.FORMAT_CHECKER) for title in wanted}

    def errors(self, title: str, instance: Any) -> list[str]:
        """Every validation error as ``<json pointer>: <message>``, sorted by pointer."""
        found = sorted(self._validators[title].iter_errors(instance), key=lambda error: [str(part) for part in error.absolute_path])
        return ["/" + "/".join(str(part) for part in error.absolute_path) + ": " + error.message for error in found]


def payload_leaks(payload: Any, tools: ContractTools, *, authored_markdown: Sequence[str] = ("promptMarkdown",)) -> list[str]:
    """Leak findings of a built payload: strict-class fields by the strict patterns, every other string by the
    human-text patterns, every string for e-mail, every key for forbidden property names (spec D-14).

    ``promptMarkdown`` is authored markdown: it passes through and is excluded from corpus payload scans.
    """
    strict_names = frozenset(tools.fixtures.STRICT_FIELDS)
    findings: list[str] = []

    def walk(node: Any, path: str, strict: bool) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if tools.leak.is_forbidden_property_name(str(key)):
                    findings.append(f"{path}/{key}: FORBIDDEN_PROPERTY_NAME")
                if key not in authored_markdown:
                    walk(value, f"{path}/{key}", str(key) in strict_names)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}/{index}", strict)
        elif isinstance(node, str):
            field_class = tools.leak.STRICT if strict else tools.leak.HUMAN
            findings.extend(f"{path}: {code}" for code in tools.leak.leak_codes(node, field_class))

    walk(payload, "", False)
    return findings


# ---------------------------------------------------------------------------
# Reading one Mission (read-only)
# ---------------------------------------------------------------------------


@dataclass
class MissionSource:
    """What the public readers return for one Mission directory; no work package file has been read."""

    name: str
    own_dir: Path
    read_dir: Path
    fallback: str | None
    meta: dict[str, Any]
    identity: Any
    snapshot: Any
    rows: list[dict[str, Any]]
    cursor: TailCursor


def resolve_read_dir(repo_root: Path, name: str) -> tuple[Path, str | None]:
    """The coordination-aware status directory, or the Mission's own directory with the reason it fell back.

    ``MissionStatus.load`` returns the authoritative status directory. Outside this checkout (a lane worktree
    resolves to the primary checkout) or when the coordination branch is unavailable, the Mission's own
    directory is read instead, so the payload is a pure function of the checked-out tree.
    """
    own = repo_root / "kitty-specs" / name
    try:
        status = MissionStatus.load(repo_root, name)
    except (CoordinationBranchDeleted, CoordAuthorityUnavailable, MissionMetadataUnavailable) as error:
        return own, type(error).__name__
    read_dir = Path(status.read_dir)
    if read_dir.resolve() == own.resolve():
        return own, None
    try:
        read_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return own, "read directory outside this checkout"
    return read_dir, None


def load_source(repo_root: Path, name: str) -> MissionSource:
    """Read meta, identity, snapshot and the event rows of one Mission through public readers only."""
    own = repo_root / "kitty-specs" / name
    read_dir, fallback = resolve_read_dir(repo_root, name)
    meta = load_meta(own, on_malformed="raise") or {}
    log = read_dir / "status.events.jsonl"
    cursor = TailCursor(offset=0, content_invariant=EMPTY_DIGEST)
    rows: list[dict[str, Any]] = []
    if log.is_file():
        polled = poll_once(log, cursor)
        cursor, rows = polled.cursor, polled.events
    return MissionSource(
        name=name,
        own_dir=own,
        read_dir=read_dir,
        fallback=fallback,
        meta=dict(meta),
        identity=resolve_mission_identity(own),
        snapshot=materialize_snapshot(read_dir),
        rows=rows,
        cursor=cursor,
    )


def lane_counts_of(snapshot: Any) -> dict[str, int]:
    """The nine-key lane counts of a snapshot, counted from its work packages (never grouped)."""
    counts = dict.fromkeys(STATUS_LANES, 0)
    for state in snapshot.work_packages.values():
        lane = str(state.get("lane"))
        if lane in counts:
            counts[lane] += 1
    return counts


def stream_cursor_of(cursor: TailCursor) -> dict[str, Any]:
    return {"offset": cursor.offset, "invariant": cursor.content_invariant}


@dataclass(frozen=True)
class OwnMission:
    """One Mission as the cheap own-directory pass sees it (no payload built)."""

    name: str
    snapshot_work_packages: int
    work_package_files: int
    lane_counts: Mapping[str, int]
    lifecycle: str
    topology: str


def topology_of(meta: Mapping[str, Any]) -> str:
    stored = meta.get("topology")
    return stored if isinstance(stored, str) and stored in TOPOLOGIES else UNKNOWN_TOPOLOGY


def count_work_package_files(own_dir: Path) -> int:
    tasks = own_dir / "tasks"
    return sum(1 for entry in tasks.glob("WP*.md") if entry.is_file()) if tasks.is_dir() else 0


@functools.cache
def _own_pass(root: str) -> tuple[OwnMission, ...]:
    repo_root = Path(root)
    result: list[OwnMission] = []
    for name in enumerate_missions(repo_root):
        own = repo_root / "kitty-specs" / name
        meta = load_meta(own, on_malformed="raise") or {}
        snapshot = materialize_snapshot(own)
        counts = lane_counts_of(snapshot)
        total = len(snapshot.work_packages)
        lifecycle = derive_lifecycle_status(counts, total, _optional_text(meta.get("discarded_at")), _optional_text(meta.get("accepted_at")))
        result.append(OwnMission(name, total, count_work_package_files(own), counts, lifecycle, topology_of(meta)))
    return tuple(result)


def own_directory_pass(repo_root: Path) -> list[OwnMission]:
    """Snapshot counts, file counts, lane counts, lifecycle and topology per Mission, from each own directory."""
    return list(_own_pass(str(repo_root)))


def disagreement_list(own: Iterable[OwnMission]) -> list[tuple[str, int, int]]:
    """Missions whose snapshot work package count differs from their ``tasks/WP*.md`` count: (name, snapshot, files)."""
    return [(item.name, item.snapshot_work_packages, item.work_package_files) for item in own if item.snapshot_work_packages != item.work_package_files]


def floor_failures(own: Sequence[OwnMission]) -> list[str]:
    """Every floor of the corpus that is not met (empty means all are)."""
    failures: list[str] = []
    if len(own) < FLOORS.missions:
        failures.append(f"{len(own)} Missions with a meta.json, floor {FLOORS.missions}")
    if sum(item.snapshot_work_packages for item in own) < FLOORS.snapshot_work_packages:
        failures.append(f"{sum(item.snapshot_work_packages for item in own)} snapshot work packages, floor {FLOORS.snapshot_work_packages}")
    if sum(item.work_package_files for item in own) < FLOORS.work_package_payloads:
        failures.append(f"{sum(item.work_package_files for item in own)} work package files, floor {FLOORS.work_package_payloads}")
    failures.extend(f"no Mission has a work package in the {lane} lane" for lane in STATUS_LANES if not any(item.lane_counts.get(lane) for item in own))
    failures.extend(f"no Mission reads as {value}" for value in ("active", "planned", "done", "draft") if not any(item.lifecycle == value for item in own))
    failures.extend(f"no Mission has the topology {value}" for value in (*TOPOLOGIES, UNKNOWN_TOPOLOGY) if not any(item.topology == value for item in own))
    return failures


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _latest_instant(values: Iterable[Any]) -> str | None:
    stamps = [str(value) for value in values if value]
    return max(stamps, key=lambda stamp: parse_iso(stamp).timestamp()) if stamps else None


def build_overview(source: MissionSource, projector: Projector) -> dict[str, Any]:
    """One ``MissionOverview`` payload. No work package file is read: ``wpTotal`` is the snapshot's work package count (D-4)."""
    meta, identity, snapshot = source.meta, source.identity, source.snapshot
    counts = lane_counts_of(snapshot)
    wp_total = len(snapshot.work_packages)
    accepted_at, discarded_at = _optional_text(meta.get("accepted_at")), _optional_text(meta.get("discarded_at"))
    progress = compute_weighted_progress(snapshot)
    mission_id = projector.strict(identity.mission_id, "missionId", nullable=False, pattern=_MISSION_ID)
    slug = projector.strict(identity.mission_slug, "slug", nullable=False)
    friendly = projector.human(str(meta.get("friendly_name") or "").strip() or slug, "friendlyName")
    mid8 = resolve_mid8(str(slug), mission_id=identity.mission_id) or None
    return {
        "missionId": mission_id,
        "mid8": mid8,
        "slug": slug,
        "friendlyName": friendly,
        "displayNumber": identity.mission_number,
        "missionType": projector.strict(identity.mission_type or None, "missionType", nullable=True),
        "targetBranch": projector.strict(meta.get("target_branch"), "targetBranch", nullable=False),
        "topology": topology_of(meta),
        "createdAt": _optional_text(meta.get("created_at")),
        "statusLaneCounts": counts,
        "wpTotal": wp_total,
        "blockedCount": counts["blocked"],
        "progress": {
            "weightedPercentage": round(progress.percentage, 4),
            "donePercentage": round(progress.done_percentage, 4),
            "doneCount": progress.done_count,
            "semantics": "weighted_readiness",
        },
        "lifecycleStatus": derive_lifecycle_status(counts, wp_total, discarded_at, accepted_at),
        "acceptedAt": accepted_at,
        "mergedAt": _optional_text(meta.get("merged_at")),
        "discardedAt": discarded_at,
        "lastEventId": snapshot.last_event_id,
        "lastActivityAt": _latest_instant(state.get("last_transition_at") for state in snapshot.work_packages.values()),
        "eventCount": snapshot.event_count,
        "streamCursor": stream_cursor_of(source.cursor),
        "nextAction": projector.human(derive_next_action(str(slug), accepted_at, bool(meta.get("baseline_merge_commit")), counts), "nextAction"),
    }


@dataclass(frozen=True)
class AuthoredWorkPackage:
    path: Path
    metadata: WPMetadata
    body: str


def read_authored_files(own_dir: Path) -> list[AuthoredWorkPackage]:
    """Every ``tasks/WP*.md`` of a Mission through the authored-frontmatter reader, in file-name order."""
    tasks = own_dir / "tasks"
    if not tasks.is_dir():
        return []
    result: list[AuthoredWorkPackage] = []
    for path in sorted(tasks.glob("WP*.md")):
        if path.is_file():
            metadata, body = read_authored_wp_frontmatter(path)
            result.append(AuthoredWorkPackage(path, metadata, body))
    return result


def _lifecycle_types(rows: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    return frozenset(str(row["event_type"]) for row in rows if isinstance(row.get("event_type"), str))


def _lanes_of(snapshot: Any) -> dict[str, str]:
    return {wp_id: str(state.get("lane")) for wp_id, state in snapshot.work_packages.items()}


def _readiness(source: MissionSource, wp_id: str, dependencies: Sequence[str]) -> dict[str, Any]:
    result = dependency_readiness_for_wp(wp_id, dependencies, _lanes_of(source.snapshot), provenance=source.snapshot.work_packages)
    return {"satisfied": result.satisfied, "unsatisfied": list(result.unsatisfied)}


def _subtask_progress(subtasks: Mapping[str, str]) -> dict[str, int]:
    return {"done": sum(1 for value in subtasks.values() if value == "done"), "total": len(subtasks)}


def build_work_package_summary(source: MissionSource, authored: AuthoredWorkPackage, projector: Projector) -> dict[str, Any]:
    wp_id = str(projector.strict(authored.metadata.work_package_id, "wpId", nullable=False, pattern=_WP_ID))
    view = reconstruct_wp_view(source.read_dir, wp_id, metadata=authored.metadata)
    lane = projector.lane(view.resolved.lane, f"{wp_id}.statusLane")
    deps = projector.strict_list(view.authored.dependencies, f"{wp_id}.dependencies", _WP_ID)
    readiness = _readiness(source, wp_id, deps)
    state = source.snapshot.work_packages.get(wp_id) or {}
    return {
        "wpId": wp_id,
        "title": projector.human(authored.metadata.title, f"{wp_id}.title"),
        "phaseLabel": projector.human(authored.metadata.phase, f"{wp_id}.phaseLabel"),
        "statusLane": lane,
        "dependencies": deps,
        "readiness": readiness,
        "readyToStart": derive_ready_to_start(lane, bool(readiness["satisfied"])),
        "subtaskProgress": _subtask_progress(view.resolved.subtasks),
        "lastTransitionAt": state.get("last_transition_at"),
    }


def build_detail(source: MissionSource, projector: Projector, files: Sequence[AuthoredWorkPackage] | None = None) -> dict[str, Any]:
    """One ``MissionDetail`` payload: the overview plus five phases and a summary of each work package file."""
    detail = build_overview(source, projector)
    artifacts = frozenset(name for name in PHASE_ARTIFACTS.values() if (source.own_dir / name).is_file())
    authored = read_authored_files(source.own_dir) if files is None else list(files)
    summaries = [build_work_package_summary(source, item, projector) for item in authored]
    detail["phases"] = derive_phases(detail["statusLaneCounts"], detail["wpTotal"], artifacts, _lifecycle_types(source.rows))
    detail["workPackages"] = sorted(summaries, key=lambda item: str(item["wpId"]))
    return detail


def _review_result(state: Mapping[str, Any], projector: Projector, where: str) -> dict[str, Any] | None:
    raw = state.get("review_result")
    if not isinstance(raw, Mapping):
        return None
    return {
        "reviewer": projector.handle(raw.get("reviewer")),
        "verdict": raw.get("verdict"),
        "reference": projector.human(raw.get("reference") if raw.get("reference") is not None else "", f"{where}.review.latestResult.reference"),
    }


def _review_override(view_review: Mapping[str, Any] | None, projector: Projector, where: str) -> dict[str, Any] | None:
    if not isinstance(view_review, Mapping):
        return None
    return {
        "at": view_review.get("at"),
        "actor": projector.handle(view_review.get("actor")),
        "reason": projector.human(view_review.get("reason") if view_review.get("reason") is not None else "", f"{where}.review.override.reason"),
    }


def _cancellation(state: Mapping[str, Any], lane: str | None, projector: Projector, where: str) -> dict[str, Any] | None:
    if lane != "canceled":
        return None
    source = state.get("reason_source")
    return {
        "reasonSource": source if source in {"operator", "synthetic"} else "synthetic",
        "reason": projector.human(state.get("cancellation_reason"), f"{where}.cancellation.reason"),
    }


def history_entries(source: MissionSource, wp_id: str, projector: Projector) -> list[dict[str, Any]]:
    """Status transitions of one work package, oldest first by time then event id; no other row kind appears."""
    entries = []
    for row in source.rows:
        if "to_lane" in row and row.get("wp_id") == wp_id:
            verdict = row["review_result"].get("verdict") if isinstance(row.get("review_result"), Mapping) else None
            entries.append(
                {
                    "eventId": row.get("event_id"),
                    "at": row.get("at"),
                    "kind": "transition",
                    "fromStatusLane": projector.lane(row.get("from_lane"), f"{wp_id}.history.fromStatusLane"),
                    "toStatusLane": projector.lane(row.get("to_lane"), f"{wp_id}.history.toStatusLane"),
                    "actor": projector.actor(row.get("actor")),
                    "force": row.get("force") is True,
                    "reason": projector.human(row.get("reason"), f"{wp_id}.history.reason"),
                    "reviewVerdict": verdict,
                }
            )
    return sorted(entries, key=lambda item: (str(item["at"]), str(item["eventId"])))


def build_work_package(source: MissionSource, authored: AuthoredWorkPackage, projector: Projector, *, include_prompt: bool = False) -> dict[str, Any]:
    """One ``WorkPackage`` payload: authored plan from the file, resolved state from the status snapshot."""
    meta = authored.metadata
    wp_id = str(projector.strict(meta.work_package_id, "wpId", nullable=False, pattern=_WP_ID))
    view = reconstruct_wp_view(source.read_dir, wp_id, metadata=meta)
    resolved, plan = view.resolved, view.authored
    state: Mapping[str, Any] = source.snapshot.work_packages.get(wp_id) or {}
    lane = projector.lane(resolved.lane, f"{wp_id}.statusLane")
    deps = projector.strict_list(plan.dependencies, f"{wp_id}.dependencies", _WP_ID)
    readiness = _readiness(source, wp_id, deps)
    subtasks = {str(projector.strict(key, f"{wp_id}.subtasks", nullable=False, pattern=_RELATIVE_REFERENCE)): value for key, value in resolved.subtasks.items()}
    payload: dict[str, Any] = {
        "wpId": wp_id,
        "title": projector.human(meta.title, f"{wp_id}.title"),
        "phaseLabel": projector.human(meta.phase, f"{wp_id}.phaseLabel"),
        "authored": {
            "role": projector.human(plan.role, f"{wp_id}.authored.role"),
            "agentProfile": projector.human(plan.agent_profile, f"{wp_id}.authored.agentProfile"),
            "model": projector.human(plan.model, f"{wp_id}.authored.model"),
            "subtasks": projector.strict_list(list(plan.subtasks), f"{wp_id}.authored.subtasks", _RELATIVE_REFERENCE),
        },
        "ownedFiles": projector.strict_list(plan.owned_files, f"{wp_id}.ownedFiles", _RELATIVE_REFERENCE),
        "dependencies": deps,
        "requirementRefs": projector.strict_list(plan.requirement_refs, f"{wp_id}.requirementRefs", _RELATIVE_REFERENCE),
        "executionMode": projector.human(normalise_quoted(meta.execution_mode), f"{wp_id}.executionMode"),
        "taskType": projector.human(meta.task_type, f"{wp_id}.taskType"),
        "priority": projector.human(meta.priority, f"{wp_id}.priority"),
        "mergeTargetBranch": projector.strict(meta.merge_target_branch, f"{wp_id}.mergeTargetBranch", nullable=True),
        "trackerRefs": projector.strict_list(meta.tracker_refs, f"{wp_id}.trackerRefs", _RELATIVE_REFERENCE),
        "statusLane": lane,
        "assignment": {
            "agent": projector.handle(resolved.agent),
            "assignee": projector.handle(resolved.assignee),
            "role": projector.handle(resolved.role),
            "agentProfile": projector.handle(resolved.agent_profile),
            "agentProfileVersion": projector.handle(resolved.agent_profile_version),
            "model": projector.handle(resolved.model),
            "provider": projector.handle(resolved.provider),
        },
        "subtasks": subtasks,
        "subtaskProgress": _subtask_progress(resolved.subtasks),
        "implementerOfRecord": projector.handle(state.get("implementer_of_record")),
        "lastTransitionAt": state.get("last_transition_at"),
        "forceCount": int(state.get("force_count") or 0),
        "lastEventId": state.get("last_event_id"),
        "actor": projector.actor(state.get("actor")),
        "cancellation": _cancellation(state, lane, projector, wp_id),
        "readiness": readiness,
        "readyToStart": derive_ready_to_start(lane, bool(readiness["satisfied"])),
        "review": {"latestResult": _review_result(state, projector, wp_id), "override": _review_override(resolved.review, projector, wp_id)},
        "history": history_entries(source, wp_id, projector),
        "staleness": None,
    }
    if include_prompt:
        payload["promptMarkdown"] = authored.body
    return payload


def read_project_name(repo_root: Path) -> str:
    """The project slug of ``.kittify/config.yaml`` (read only)."""
    config = yaml.safe_load((repo_root / ".kittify" / "config.yaml").read_text(encoding="utf-8")) or {}
    project = config.get("project") if isinstance(config, dict) else None
    slug = project.get("slug") if isinstance(project, dict) else None
    if not isinstance(slug, str) or not slug:
        raise ProjectionError("project", "name", "config.yaml has no project.slug")
    return slug


# ---------------------------------------------------------------------------
# Event projection (allow-list, FR-007)
# ---------------------------------------------------------------------------


@dataclass
class EventProjection:
    """Projected events in log order and the rows dropped, counted per event type."""

    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    dropped: Counter[str] = field(default_factory=Counter)


def _row_label(row: Mapping[str, Any]) -> str:
    for key in ("event_type", "type", "kind"):
        if isinstance(row.get(key), str):
            return str(row[key])
    return "unknown-row"


def project_events(mission_id: str, rows: Iterable[Mapping[str, Any]], projector: Projector) -> EventProjection:
    """Forward only status transitions and the seven contract-owned lifecycle types; count and drop everything else.

    ``missionId`` is the identity of ``meta.json`` (passed in), never the row's ``aggregate_id``. The cursor of
    each event is the tail reader's own position just after the row.
    """
    projection = EventProjection()
    for row in rows:
        cursor = {"offset": row.get("tail_offset"), "invariant": row.get("tail_invariant")}
        if "to_lane" in row:
            projection.events.append(
                (
                    "status-transition",
                    {
                        "missionId": mission_id,
                        "eventId": row.get("event_id"),
                        "wpId": row.get("wp_id"),
                        "fromStatusLane": projector.lane(row.get("from_lane"), "event.fromStatusLane"),
                        "toStatusLane": projector.lane(row.get("to_lane"), "event.toStatusLane"),
                        "at": row.get("at"),
                        "actor": projector.actor(row.get("actor")),
                        "force": row.get("force") is True,
                        "streamCursor": cursor,
                    },
                )
            )
        elif row.get("event_type") in LIFECYCLE_ALLOW_LIST:
            projection.events.append(
                (
                    "mission-lifecycle",
                    {
                        "missionId": mission_id,
                        "eventId": row.get("event_id"),
                        "eventType": row["event_type"],
                        "at": row.get("timestamp"),
                        "streamCursor": cursor,
                    },
                )
            )
        else:
            projection.dropped[_row_label(row)] += 1
    return projection


def undeclared_lifecycle_types() -> list[str]:
    """``LIFECYCLE_EVENT_TYPES`` minus the allow-list: the types dropped by design, printed on every run."""
    return sorted(set(LIFECYCLE_EVENT_TYPES) - LIFECYCLE_ALLOW_LIST)


# ---------------------------------------------------------------------------
# Traps for the overview builder
# ---------------------------------------------------------------------------


def work_package_trap(mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    """Make any read of a ``tasks/WP*.md`` path raise, and return a function listing the paths that were touched."""
    touched: list[str] = []
    pattern = re.compile(r"tasks[\\/]WP[^\\/]*\.md$")
    real_open = open  # noqa: SIM115 - captured to delegate, never used as a context here
    real_read_text = Path.read_text
    real_path_open = Path.open

    def guard(path: Any) -> None:
        if isinstance(path, (str, Path)) and pattern.search(str(path)):
            touched.append(str(path))
            raise AssertionError(f"the overview builder read a work package file: {path}")

    def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        guard(file)
        return real_open(file, *args, **kwargs)

    def guarded_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        guard(self)
        return real_read_text(self, *args, **kwargs)

    def guarded_path_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        guard(self)
        return real_path_open(self, *args, **kwargs)

    mp.setattr("builtins.open", guarded_open)
    mp.setattr(Path, "read_text", guarded_read_text)
    mp.setattr(Path, "open", guarded_path_open)
    return lambda: list(touched)


# ---------------------------------------------------------------------------
# Fixture Missions built at run time (unit tests and controls)
# ---------------------------------------------------------------------------

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def fixture_ulid(number: int) -> str:
    """A deterministic 26-character Crockford ULID for fixtures."""
    digits = ""
    for _ in range(26):
        number, rest = divmod(number, 32)
        digits = _ULID_ALPHABET[rest] + digits
    return digits


def write_fixture_mission(
    root: Path,
    name: str,
    *,
    meta: Mapping[str, Any] | None = None,
    work_packages: Mapping[str, Mapping[str, Any]] | None = None,
    rows: Sequence[Mapping[str, Any]] = (),
    planning_files: Sequence[str] = (),
) -> Path:
    """Write one Mission directory (meta.json, tasks/, status.events.jsonl) under ``root/kitty-specs`` and return it."""
    mission_dir = root / "kitty-specs" / name
    (mission_dir / "tasks").mkdir(parents=True, exist_ok=True)
    base_meta: dict[str, Any] = {
        "mission_id": fixture_ulid(1),
        "mission_slug": name,
        "slug": name,
        "friendly_name": "Fixture Mission",
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-09-01T10:00:00+00:00",
    }
    base_meta.update(meta or {})
    (mission_dir / "meta.json").write_text(json.dumps(base_meta), encoding="utf-8")
    for wp_id, frontmatter in (work_packages or {}).items():
        header = {"work_package_id": wp_id, "title": f"Title of {wp_id}", **frontmatter}
        (mission_dir / "tasks" / f"{wp_id}-fixture.md").write_text(
            "---\n" + yaml.safe_dump(header, sort_keys=True) + "---\n\n# Body of " + wp_id + "\n", encoding="utf-8"
        )
    for planning_file in planning_files:
        (mission_dir / planning_file).write_text("# planning file\n", encoding="utf-8")
    if rows:
        (mission_dir / "status.events.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return mission_dir


def transition_row(
    number: int,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    *,
    at: str,
    actor: Any = "claude",
    mission_slug: str = "fixture",
    force: bool = False,
    reason: str | None = None,
    review_result: Mapping[str, Any] | None = None,
    policy_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "actor": actor,
        "at": at,
        "event_id": fixture_ulid(1000 + number),
        "evidence": None,
        "execution_mode": "worktree",
        "force": force,
        "from_lane": from_lane,
        "mission_id": fixture_ulid(1),
        "mission_slug": mission_slug,
        "policy_metadata": dict(policy_metadata) if policy_metadata is not None else None,
        "reason": reason,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }
    if review_result is not None:
        row["review_result"] = dict(review_result)
    return row


def annotation_row(number: int, wp_id: str, delta: Mapping[str, Any], *, at: str, actor: Any = "claude") -> dict[str, Any]:
    return {"actor": actor, "at": at, "delta": dict(delta), "event_id": fixture_ulid(2000 + number), "kind": "annotation", "wp_id": wp_id}


def lifecycle_row(number: int, event_type: str, timestamp: str, *, aggregate_id: str = "fixture-slug", payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """A lifecycle row of the event log; ``aggregate_id`` is deliberately not the Mission identity."""
    return {
        "aggregate_id": aggregate_id,
        "aggregate_type": "Mission",
        "event_id": fixture_ulid(3000 + number),
        "event_type": event_type,
        "payload": dict(payload or {}),
        "project_slug": None,
        "project_uuid": None,
        "schema_version": "5.0.0",
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# The pinned expected-output fixture (D-P9)
# ---------------------------------------------------------------------------

EXPECTED_FIXTURE = Path("tests") / "contract" / "fixtures" / "mission_status_expected.json"


def load_expected(repo_root: Path) -> dict[str, Any]:
    loaded = json.loads((repo_root / EXPECTED_FIXTURE).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not isinstance(loaded.get("header"), dict) or not isinstance(loaded.get("sample"), list) or not loaded["sample"]:
        raise ValueError("the pinned fixture needs a header and a non-empty sample")
    return loaded


def expected_mismatches(expected: Mapping[str, Any], overview_of: Callable[[str], Mapping[str, Any]]) -> list[str]:
    """Differences between the helper's derivations and the pinned values (empty means the helper agrees with the dashboard it replaced).

    A real entry is compared on the Mission's current overview, after checking that its lane counts still
    equal the pinned ones (otherwise the sample is stale, which is reported as such and not as a helper bug).
    A synthetic entry is derived from its stated inputs.
    """
    problems: list[str] = []
    for entry in expected["sample"]:
        label, want = str(entry["mission"]), entry["expected"]
        if entry["kind"] == "real":
            overview = overview_of(label)
            if dict(overview["statusLaneCounts"]) != entry["statusLaneCounts"]:
                problems.append(f"{label}: the Mission no longer has the pinned lane counts (stale sample)")
                continue
            got = {"lifecycleStatus": overview["lifecycleStatus"], "nextAction": overview["nextAction"]}
        else:
            given = entry["inputs"]
            got = {
                "lifecycleStatus": derive_lifecycle_status(given["statusLaneCounts"], given["wpTotal"], given["discardedAt"], given["acceptedAt"]),
                "nextAction": derive_next_action(given["slug"], given["acceptedAt"], given["hasBaseline"], given["statusLaneCounts"]),
            }
        problems.extend(
            f"{label}: {key} is {got[key]!r}, the dashboard derivation gave {want[key]!r}" for key in ("lifecycleStatus", "nextAction") if got[key] != want[key]
        )
    return problems


def sample_covers(expected: Mapping[str, Any]) -> set[str]:
    """The lifecycle values the pinned sample covers."""
    return {str(entry["expected"]["lifecycleStatus"]) for entry in expected["sample"]}
