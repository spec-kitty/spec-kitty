"""Read-only decision-stream fork detector and coordination-only-ledger finder.

Mission ``coord-artifact-single-home-01M3V4BE`` WP17 (FR-009c/FR-010/FR-010a/
FR-011; ``contracts/doctor-decisions-fork-report.md``). The ONE place that
knows how to compare the PRIMARY and COORDINATION copies of a Mission's
decision streams (``status.events.jsonl`` decision rows,
``decisions.events.jsonl``) and ledger (``decisions/index.json`` +
``decisions/DM-*.md``) -- shared by ``doctor decisions``, ``decision
verify``, coordination teardown and the consolidation preflight (NFR-004
single authority; DIRECTIVE_044). No second fork/prefix classifier is
written here: both :func:`detect_decision_forks` and
:func:`coordination_only_ledger` reuse
:func:`specify_cli.coordination.event_prefix.classify_prefix` (WP03).

READ-ONLY by construction (FR-016 US4.1 control): this module never calls
``write_dir``, ``CoordinationWorkspace.resolve``/``teardown``, or any
status/decisions append primitive -- only :meth:`PlacementSeam.read_dir`,
:func:`~specify_cli.missions._read_path_resolver.coord_feature_dir` (pure path
composition, no filesystem touch) and ``git show``/``git ls-tree``. A worktree is preferred
when present for the event streams; a fresh clone with no coordination
worktree falls back to reading the committed ref directly, so the detector
reports the same fork from a bare clone (US4.1 "fresh clone" case). The
coordination side of the LEDGER comparison always reads the branch tip
(never the worktree copy, which may be stale and is not what teardown
destroys -- contract rule 4 / T092).

C-003: this module never merges or re-sequences a forked log. The
``reconcile_steps`` it returns are human-readable guidance, never executed
code.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kernel.git import GitCommandError, GitPath, tree_entry, tree_paths

from mission_runtime import MissionArtifactKind, placement_seam
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED, DECISION_POINT_RESOLVED

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.git_ops import run_command
from specify_cli.coordination.event_prefix import classify_prefix
from specify_cli.lanes.branch_naming import coord_mission_dir_name
from specify_cli.missions._read_path_resolver import coord_feature_dir, read_primary_meta

__all__ = [
    "SurfaceLog",
    "StreamForkFinding",
    "LedgerHomeFinding",
    "DecisionsForkReport",
    "detect_decision_forks",
    "coordination_only_ledger",
    "ledger_is_coordination_only",
    "read_coordination_ledger_raw",
    "LedgerProbeError",
]

#: The two decision-event streams compared per-mission (contract "Inputs read").
STATUS_STREAM = "status.events.jsonl"
DECISION_LOG_STREAM = "decisions.events.jsonl"
_STREAMS: tuple[str, str] = (STATUS_STREAM, DECISION_LOG_STREAM)

_DECISION_STATUS_EVENT_TYPES: tuple[str, str] = (DECISION_POINT_OPENED, DECISION_POINT_RESOLVED)

Surface = Literal["primary", "coordination"]
Source = Literal["worktree", "ref"]
StreamState = Literal["single_home", "prefix", "forked", "absent"]
LedgerState = Literal["primary", "coordination_only", "both", "absent"]


class LedgerProbeError(RuntimeError):
    """The coordination-side ledger could not be READ (as opposed to being absent).

    A ref that does not resolve at all (the coordination branch is already gone), and
    a resolvable ref whose ``decisions/`` directory or ``index.json`` is simply not
    in the tree, are genuine absence and are NOT this error: there is no ledger left
    to protect. A resolvable ref whose listing or ``git show`` then fails is: reporting
    it as an empty ledger would let a teardown destroy the only copy. Only the
    tolerant ``doctor decisions`` consumer (:func:`detect_decision_forks`) catches
    it; the teardown and consolidation guards let it propagate so they refuse.
    """

    def __init__(self, ref: str, detail: str) -> None:
        self.ref = ref
        self.detail = detail
        super().__init__(f"could not read the decisions ledger on coordination ref {ref!r}: {detail}")


@dataclass(frozen=True)
class SurfaceLog:
    """One surface's read of one event-log stream (data-model.md §4)."""

    surface: Surface
    source: Source
    ref: str | None
    path: str
    event_ids: tuple[str, ...]


@dataclass(frozen=True)
class StreamForkFinding:
    """The fork/prefix verdict for one stream, both surfaces."""

    stream: str
    state: StreamState
    primary: SurfaceLog | None
    coordination: SurfaceLog | None
    decisions_only_on_primary: tuple[str, ...]
    decisions_only_on_coordination: tuple[str, ...]
    decisions_on_both: tuple[str, ...]


@dataclass(frozen=True)
class LedgerHomeFinding:
    """Where the decision ledger (``decisions/index.json`` + ``DM-*.md``) lives."""

    state: LedgerState
    entries_only_on_coordination: tuple[str, ...]
    dm_files_only_on_coordination: tuple[str, ...]


@dataclass(frozen=True)
class DecisionsForkReport:
    """The full ``doctor decisions`` fork report for one Mission."""

    mission_slug: str
    topology: str | None
    streams: tuple[StreamForkFinding, ...]
    ledger: LedgerHomeFinding
    forked: bool
    reconcile_steps: tuple[str, ...]


@dataclass(frozen=True)
class _CoordSide:
    """Resolved coordination-surface addressing for one Mission (private)."""

    mission_dir: Path
    branch: str
    mission_subdir: str


# ---------------------------------------------------------------------------
# Meta helpers
# ---------------------------------------------------------------------------


def _meta_str(meta: Mapping[str, object], key: str) -> str:
    value = meta.get(key)
    return value.strip() if isinstance(value, str) else ""


def _resolve_coord_side(
    repo_root: Path,
    meta: Mapping[str, object],
    declares_coordination: bool,
    primary_dir_name: str,
) -> _CoordSide | None:
    """Resolve the coordination surface, or ``None`` when there is none to compare.

    Mirrors ``_resolve_coord_worktree_for_preflight``'s defensive gate: an
    undeclared ``coordination_branch`` (legacy mission, non-coordination
    topology, or ``COORD_BRANCH_UNDECLARED_AND_ABSENT`` -- "no coordination
    home exists", never a fork) or an absent ``mid8`` both mean there is no
    coordination surface to compare against, so every stream/ledger degrades
    to PRIMARY-only (``single_home`` / ``absent`` / ``primary``), never a
    fork and never ``coordination_only``.
    """
    if not declares_coordination:
        return None
    mid8 = _meta_str(meta, "mid8")
    branch = _meta_str(meta, "coordination_branch")
    if not mid8 or not branch:
        return None
    # Pure path composition (no filesystem touch, never materializes a
    # worktree) through the ONE coordination mission-dir composer.
    mission_dir = coord_feature_dir(repo_root, primary_dir_name, mid8)
    mission_subdir = coord_mission_dir_name(primary_dir_name, mid8=mid8)
    return _CoordSide(mission_dir=mission_dir, branch=branch, mission_subdir=mission_subdir)


# ---------------------------------------------------------------------------
# Reading (worktree preferred, ref fallback)
# ---------------------------------------------------------------------------


def _surface_text(
    mission_dir_on_disk: Path,
    repo_root: Path,
    ref: str | None,
    mission_subdir: str,
    filename: str,
) -> tuple[str, Source]:
    """Read *filename* from *mission_dir_on_disk* when present, else from *ref*.

    Never raises on a missing file/ref: both degrade to an empty string, the
    benign "absent on this surface" case.
    """
    candidate = mission_dir_on_disk / filename
    if candidate.exists():
        return candidate.read_text(encoding="utf-8"), "worktree"
    if ref:
        relpath = f"{KITTY_SPECS_DIR}/{mission_subdir}/{filename}"
        ret, out, _err = run_command(["git", "show", f"{ref}:{relpath}"], capture=True, check_return=False, cwd=repo_root)
        if ret == 0:
            return out, "ref"
    return "", "worktree"


def _parse_jsonl_tolerant(text: str) -> tuple[list[dict[str, object]], int]:
    """Parse *text* as JSONL, never raising (NFR-002 zero-loss: surface, never crash/drop).

    Returns ``(rows, malformed_line_count)``. A malformed line is skipped
    and counted rather than aborting the whole read.
    """
    rows: list[dict[str, object]] = []
    malformed = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            malformed += 1
    return rows, malformed


def _decision_id_from_status_row(row: Mapping[str, object]) -> str | None:
    """``status.events.jsonl``: a DecisionPointOpened/Resolved row's ``decision_point_id``."""
    if row.get("event_type") not in _DECISION_STATUS_EVENT_TYPES:
        return None
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    value = payload.get("decision_point_id")
    return str(value) if value else None


def _decision_id_from_decision_log_row(row: Mapping[str, object]) -> str | None:
    """``decisions.events.jsonl``: a DecisionInputRequested row's ``decision_id``."""
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    value = payload.get("decision_id")
    return str(value) if value else None


_DECISION_ID_EXTRACTORS: Mapping[str, Callable[[Mapping[str, object]], str | None]] = {
    STATUS_STREAM: _decision_id_from_status_row,
    DECISION_LOG_STREAM: _decision_id_from_decision_log_row,
}


def _extract_ids(stream: str, rows: list[dict[str, object]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(event_ids, decision_ids)`` for the decision-bearing rows of *rows*."""
    extractor = _DECISION_ID_EXTRACTORS[stream]
    event_ids: list[str] = []
    decision_ids: list[str] = []
    for row in rows:
        decision_id = extractor(row)
        if decision_id is None:
            continue
        event_id = row.get("event_id")
        if event_id is not None:
            event_ids.append(str(event_id))
        decision_ids.append(decision_id)
    return tuple(event_ids), tuple(decision_ids)


def _build_surface(
    surface: Surface,
    stream: str,
    mission_dir_on_disk: Path,
    repo_root: Path,
    ref: str | None,
    mission_subdir: str,
) -> tuple[SurfaceLog, tuple[str, ...], int]:
    text, source = _surface_text(mission_dir_on_disk, repo_root, ref, mission_subdir, stream)
    rows, malformed = _parse_jsonl_tolerant(text)
    event_ids, decision_ids = _extract_ids(stream, rows)
    path = str(mission_dir_on_disk / stream) if source == "worktree" else f"{KITTY_SPECS_DIR}/{mission_subdir}/{stream}"
    log = SurfaceLog(surface=surface, source=source, ref=ref, path=path, event_ids=event_ids)
    return log, decision_ids, malformed


# ---------------------------------------------------------------------------
# Stream classification (reuses WP03's pure prefix classifier)
# ---------------------------------------------------------------------------


def _stream_state(primary_ids: tuple[str, ...], coord_ids: tuple[str, ...] | None) -> StreamState:
    if coord_ids is None:
        return "single_home" if primary_ids else "absent"
    if not primary_ids and not coord_ids:
        return "absent"
    if not primary_ids or not coord_ids:
        return "single_home"
    verdict = classify_prefix(primary_ids, coord_ids)
    return "forked" if verdict.kind == "fork" else "prefix"


def _stream_finding(
    stream: str,
    primary_log: SurfaceLog,
    primary_decision_ids: tuple[str, ...],
    coord_log: SurfaceLog | None,
    coord_decision_ids: tuple[str, ...],
) -> StreamForkFinding:
    coord_event_ids = coord_log.event_ids if coord_log is not None else None
    state = _stream_state(primary_log.event_ids, coord_event_ids)
    primary_set = set(primary_decision_ids)
    coord_set = set(coord_decision_ids) if coord_log is not None else set()
    return StreamForkFinding(
        stream=stream,
        state=state,
        primary=primary_log,
        coordination=coord_log,
        decisions_only_on_primary=tuple(sorted(primary_set - coord_set)),
        decisions_only_on_coordination=tuple(sorted(coord_set - primary_set)),
        decisions_on_both=tuple(sorted(primary_set & coord_set)),
    )


def _fork_reconcile_text(stream: str, finding: StreamForkFinding) -> str:
    only_primary = ", ".join(finding.decisions_only_on_primary) or "none"
    only_coord = ", ".join(finding.decisions_only_on_coordination) or "none"
    return (
        f"{stream} is forked: decisions only on PRIMARY = [{only_primary}]; decisions only on "
        f"COORDINATION = [{only_coord}]. This is never auto-merged (C-003) -- inspect both copies "
        "by hand, decide which decisions to keep, and record the kept ones yourself on the "
        "correct surface (never run --repair expecting it to merge or re-sequence a fork)."
    )


def _one_stream(
    stream: str,
    primary_dir: Path,
    repo_root: Path,
    target_branch: str,
    coord_info: _CoordSide | None,
) -> tuple[StreamForkFinding, tuple[str, ...]]:
    steps: list[str] = []
    primary_log, primary_ids, primary_malformed = _build_surface("primary", stream, primary_dir, repo_root, target_branch or None, primary_dir.name)
    if primary_malformed:
        steps.append(f"{primary_log.path}: {primary_malformed} malformed line(s) ignored on PRIMARY -- inspect and fix by hand.")

    coord_log: SurfaceLog | None = None
    coord_ids: tuple[str, ...] = ()
    if coord_info is not None:
        coord_log, coord_ids, coord_malformed = _build_surface(
            "coordination", stream, coord_info.mission_dir, repo_root, coord_info.branch, coord_info.mission_subdir
        )
        if coord_malformed:
            steps.append(f"{coord_log.path}: {coord_malformed} malformed line(s) ignored on COORDINATION -- inspect and fix by hand.")

    finding = _stream_finding(stream, primary_log, primary_ids, coord_log, coord_ids)
    if finding.state == "forked":
        steps.append(_fork_reconcile_text(stream, finding))
    return finding, tuple(steps)


# ---------------------------------------------------------------------------
# Ledger home (coordination side always reads the branch tip -- T092 step 3)
# ---------------------------------------------------------------------------


def _index_entry_ids_from_text(text: str) -> set[str]:
    if not text.strip():
        return set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, dict):
        return set()
    entries = data.get("entries")
    if not isinstance(entries, list):
        return set()
    ids: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict) and "decision_id" in entry:
            ids.add(str(entry["decision_id"]))
    return ids


def _is_dm_file(name: str) -> bool:
    """True for a Decision Moment ledger file basename (``DM-<id>.md``)."""
    return name.startswith("DM-") and name.endswith(".md")


def _dm_file_names(names: Iterable[str]) -> set[str]:
    return {name for name in names if _is_dm_file(name)}


def _coordination_ref_resolves(repo_root: Path, ref: str) -> bool:
    """Whether *ref* names a commit: ``False`` is genuine absence, not a failed probe.

    ``git rev-parse --verify --quiet`` exits 1 when the ref does not resolve; any
    other non-zero exit (a broken repository, ...) means the probe itself failed
    and raises :class:`LedgerProbeError`.
    """
    ret, _out, err = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret == 0:
        return True
    if ret == 1:
        return False
    raise LedgerProbeError(ref, f"git rev-parse failed: {err.strip()}")


def _child_names_at_ref(repo_root: Path, ref: str, tree_relpath: str) -> list[str]:
    """Names of the files directly under *tree_relpath* at *ref*.

    A *ref* that does not resolve, or a resolvable *ref* whose *tree_relpath* is
    absent (``ls-tree`` exits 0 with empty output), is genuine absence, returned as
    ``[]``. A listing that fails on a resolvable ref raises :class:`LedgerProbeError`.
    """
    if not _coordination_ref_resolves(repo_root, ref):
        return []
    depth = len(GitPath.parse(tree_relpath).parts)
    try:
        paths = tree_paths(repo_root, ref, pathspecs=(tree_relpath,))
    except GitCommandError as exc:
        raise LedgerProbeError(ref, f"git ls-tree {tree_relpath} failed: {exc}") from exc
    return sorted(path.parts[-1] for path in paths if len(path.parts) == depth + 1)


def _text_at_ref(repo_root: Path, ref: str, relpath: str) -> str | None:
    """The text of *relpath* at *ref*, ``None`` when the ref or that path is absent.

    Distinguishes absence (``None``: the ref does not resolve, or the tree lacks the
    path) from a failed probe (:class:`LedgerProbeError`): the tree entry of a
    resolvable ref is looked up first, so only a path the tree genuinely lacks reads
    as absent, and a ``git show`` that then fails is an error rather than an empty file.
    """
    if not _coordination_ref_resolves(repo_root, ref):
        return None
    try:
        entry = tree_entry(repo_root, ref, relpath)
    except GitCommandError as exc:
        raise LedgerProbeError(ref, f"git ls-tree {relpath} failed: {exc}") from exc
    if entry is None:
        return None
    ret, out, err = run_command(["git", "show", f"{ref}:{relpath}"], capture=True, check_return=False, cwd=repo_root)
    if ret != 0:
        raise LedgerProbeError(ref, f"git show {relpath} failed: {err.strip()}")
    text: str = out
    return text


def _ledger_contents_worktree(mission_dir: Path) -> tuple[set[str], set[str]]:
    """The PRIMARY side: read ``decisions/`` directly off the repository-root checkout."""
    decisions_path = mission_dir / "decisions"
    index_file = decisions_path / "index.json"
    entries = _index_entry_ids_from_text(index_file.read_text(encoding="utf-8")) if index_file.exists() else set()
    dm_files = _dm_file_names(p.name for p in decisions_path.glob("DM-*.md")) if decisions_path.exists() else set()
    return entries, dm_files


def _ledger_contents_ref(repo_root: Path, ref: str, mission_subdir: str) -> tuple[set[str], set[str]]:
    """The COORDINATION side: always the branch tip (the worktree copy may be stale, and the
    branch is what teardown destroys -- contract rule 4 / T092 step 3).

    Raises :class:`LedgerProbeError` when a resolvable branch tip cannot be read; a
    missing branch, or a missing ``decisions/`` directory or ``index.json`` on a
    readable tip, is empty.
    """
    index_text = _text_at_ref(repo_root, ref, f"{KITTY_SPECS_DIR}/{mission_subdir}/decisions/index.json")
    entries = _index_entry_ids_from_text(index_text) if index_text is not None else set()

    tree_relpath = f"{KITTY_SPECS_DIR}/{mission_subdir}/decisions"
    return entries, _dm_file_names(_child_names_at_ref(repo_root, ref, tree_relpath))


def _classify_ledger(
    primary_entries: set[str],
    primary_dm: set[str],
    coord_entries: set[str],
    coord_dm: set[str],
) -> LedgerHomeFinding:
    primary_has = bool(primary_entries or primary_dm)
    coord_has = bool(coord_entries or coord_dm)
    state: LedgerState
    if not primary_has and not coord_has:
        state = "absent"
    elif coord_has and not primary_has:
        state = "coordination_only"
    elif primary_has and not coord_has:
        state = "primary"
    else:
        state = "both"

    return LedgerHomeFinding(
        state=state,
        entries_only_on_coordination=tuple(sorted(coord_entries - primary_entries)),
        dm_files_only_on_coordination=tuple(sorted(coord_dm - primary_dm)),
    )


def coordination_only_ledger(repo_root: Path, mission_slug: str) -> LedgerHomeFinding:
    """Detect a pre-fix Mission whose ledger was committed only on the coordination branch.

    FR-009c: the bookkeeping-projection teardown path excludes PRIMARY kinds,
    so such a ledger would otherwise be silently lost at teardown.

    Raises:
        LedgerProbeError: an existing coordination branch tip could not be read. Callers
            that gate a destroy (teardown, consolidation) must not catch it.
    """
    meta, declares_coordination = read_primary_meta(repo_root, mission_slug)
    primary_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    primary_entries, primary_dm = _ledger_contents_worktree(primary_dir)

    coord_info = _resolve_coord_side(repo_root, meta, declares_coordination, primary_dir.name)
    coord_entries: set[str] = set()
    coord_dm: set[str] = set()
    if coord_info is not None:
        coord_entries, coord_dm = _ledger_contents_ref(repo_root, coord_info.branch, coord_info.mission_subdir)
    return _classify_ledger(primary_entries, primary_dm, coord_entries, coord_dm)


def _primary_only_ledger(repo_root: Path, mission_slug: str) -> LedgerHomeFinding:
    """The ledger verdict from the PRIMARY side alone (no coordination read)."""
    primary_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    primary_entries, primary_dm = _ledger_contents_worktree(primary_dir)
    return _classify_ledger(primary_entries, primary_dm, set(), set())


def ledger_is_coordination_only(ledger: LedgerHomeFinding) -> bool:
    """Contract rule 4/6: ``coordination_only``, or ``both`` with coordination-only residue."""
    return ledger.state == "coordination_only" or (ledger.state == "both" and bool(ledger.entries_only_on_coordination or ledger.dm_files_only_on_coordination))


def _ledger_reconcile_steps(
    ledger: LedgerHomeFinding,
    mission_slug: str,
    primary_dir_name: str,
    coord_info: _CoordSide | None,
) -> tuple[str, ...]:
    if not ledger_is_coordination_only(ledger):
        return ()
    branch_note = f" (branch {coord_info.branch!r})" if coord_info is not None else ""
    return (
        f"decisions ledger exists only on the coordination branch{branch_note} for {mission_slug}: run "
        f"`spec-kitty doctor decisions --mission {mission_slug} --repair` to copy decisions/index.json "
        f"entries and DM-*.md files into the PRIMARY ledger (kitty-specs/{primary_dir_name}/decisions/); "
        'it creates no commit -- commit the copy yourself with `spec-kitty spec-commit -m "..." '
        f"kitty-specs/{primary_dir_name}/decisions/` or `spec-kitty accept`.",
    )


def read_coordination_ledger_raw(repo_root: Path, mission_slug: str) -> tuple[dict[str, object] | None, dict[str, str]]:
    """Read the coordination branch's ledger documents verbatim, for an additive repair copy.

    Returns ``(index_document, dm_file_contents)`` -- the parsed
    ``decisions/index.json`` (``None`` when absent/malformed/not a dict) and
    a mapping of ``DM-<id>.md`` basename to its raw text content, both read
    from the coordination branch TIP (never the worktree -- T092 step 3).
    ``(None, {})`` when there is no coordination surface to read (contract
    rule 4 / ``doctor decisions --repair``'s coordination-only-ledger copy).
    """
    meta, declares_coordination = read_primary_meta(repo_root, mission_slug)
    primary_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    coord_info = _resolve_coord_side(repo_root, meta, declares_coordination, primary_dir.name)
    if coord_info is None:
        return None, {}

    index_relpath = f"{KITTY_SPECS_DIR}/{coord_info.mission_subdir}/decisions/index.json"
    ret, out, _err = run_command(["git", "show", f"{coord_info.branch}:{index_relpath}"], capture=True, check_return=False, cwd=repo_root)
    index_document: dict[str, object] | None = None
    if ret == 0:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            index_document = parsed

    tree_relpath = f"{KITTY_SPECS_DIR}/{coord_info.mission_subdir}/decisions"
    dm_contents: dict[str, str] = {}
    for name in _child_names_at_ref(repo_root, coord_info.branch, tree_relpath):
        if not _is_dm_file(name):
            continue
        file_relpath = f"{tree_relpath}/{name}"
        ret3, out3, _err3 = run_command(["git", "show", f"{coord_info.branch}:{file_relpath}"], capture=True, check_return=False, cwd=repo_root)
        if ret3 == 0:
            dm_contents[name] = out3
    return index_document, dm_contents


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def detect_decision_forks(repo_root: Path, mission_slug: str) -> DecisionsForkReport:
    """Compare both decision-event streams on both surfaces (FR-010, US4.1).

    Read-only: reads a worktree when present, else the declared ref (so it
    works from a fresh clone with no coordination worktree). Never writes,
    never materializes a worktree, never merges or re-sequences a forked log
    (C-003) -- it reports ``forked`` per stream and returns human-readable
    ``reconcile_steps``.
    """
    meta, declares_coordination = read_primary_meta(repo_root, mission_slug)
    primary_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    target_branch = _meta_str(meta, "target_branch")
    topology = _meta_str(meta, "topology") or None
    coord_info = _resolve_coord_side(repo_root, meta, declares_coordination, primary_dir.name)

    streams: list[StreamForkFinding] = []
    reconcile_steps: list[str] = []
    for stream in _STREAMS:
        finding, steps = _one_stream(stream, primary_dir, repo_root, target_branch, coord_info)
        streams.append(finding)
        reconcile_steps.extend(steps)

    # ``doctor decisions`` is a read-only report, so it tolerates an unreadable
    # coordination ledger (degrading to the PRIMARY-side verdict plus a warning
    # step). The destroy guards call ``coordination_only_ledger`` directly and
    # let :class:`LedgerProbeError` propagate.
    try:
        ledger = coordination_only_ledger(repo_root, mission_slug)
    except LedgerProbeError as exc:
        ledger = _primary_only_ledger(repo_root, mission_slug)
        reconcile_steps.append(f"the coordination ledger could not be read, so only the PRIMARY ledger is reported: {exc}")
    reconcile_steps.extend(_ledger_reconcile_steps(ledger, mission_slug, primary_dir.name, coord_info))

    forked = any(s.state == "forked" for s in streams)
    return DecisionsForkReport(
        mission_slug=mission_slug,
        topology=topology,
        streams=tuple(streams),
        ledger=ledger,
        forked=forked,
        reconcile_steps=tuple(reconcile_steps),
    )
