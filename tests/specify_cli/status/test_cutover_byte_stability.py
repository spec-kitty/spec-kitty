"""WP04 (IC-03) — unconditional reader/writer cutover proofs.

This is the ATDD-first (C-011) evidence for the #2816 cutover: every branch WP04
deletes is proven dead here, and the two load-bearing invariants are pinned:

* **SC-004 / NFR-003 (byte-stability).** A real runtime-state transition
  (claim / inner-state annotation) writes **0 bytes** to ``tasks/WP##.md`` — a
  genuine before/after ``read_bytes()`` compare (never a mock). The three
  dual-write blocks and ``write_shell_pid_claim`` are gone, so the claim rides
  the event log / policy_metadata sidecar only.
* **SC-002 (predicate gone).** ``_phase1_snapshot_authority_active`` and its
  facade export have zero occurrences in WP04's owned source files, the facade
  import now raises ``ImportError``, and the name is off ``status.__all__``.
* **Per-site unconditional reads.** ``emit._infer_subtasks_complete``,
  ``tasks_status_cmd._st_gated_runtime_fields``, ``WorkPackage`` runtime
  properties, and ``wp_metadata.read_wp_frontmatter`` all resolve the reduced
  snapshot with **no** flag branch — snapshot value wins even when the WP
  frontmatter carries a stale/different value.
* **T016 lane-mirror regression (C-004 / research D-02).** Flipping
  ``status_phase`` 0->1 *activates* the retained ``_legacy_lane_mirror_enabled``
  (it writes the transitional frontmatter ``lane`` field) but never changes what
  a lane *read* (``get_wp_lane``, event-log-sourced) resolves to. Both phases are
  exercised and the resolved lane is asserted identical — a non-vacuous guard.
* **``write_shell_pid_claim`` retirement.** The symbol is fully gone from
  ``frontmatter`` (import raises ``ImportError``; off ``__all__``).

Run with: ``uv run --extra test python -m pytest -p no:cacheprovider
tests/specify_cli/status/test_cutover_byte_stability.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status import get_wp_lane, wp_snapshot_state
from specify_cli.status.emit import (
    _infer_subtasks_complete,
    build_claim_policy_metadata,
    emit_inner_state_changed,
    emit_status_transition,
)
from specify_cli.status.models import Lane, WPInnerStateDelta
from specify_cli.status.wp_metadata import read_wp_frontmatter
from specify_cli.cli.commands.agent.tasks_status_cmd import _st_gated_runtime_fields
from specify_cli.task_utils.support import WorkPackage, split_frontmatter

from tests.status.conftest import seed_wp_to_planned

pytestmark = pytest.mark.unit

_SLUG = "cutover-byte-stability"
_WP = "WP01"

# The WP04-owned source files whose predicate references must be zero (SC-002).
# ``wp_metadata.py`` is the sanctioned out-of-map edit; it is included so the
# grep proves its flag branch was removed too.
_WP04_OWNED_SRC = (
    "src/specify_cli/status/emit.py",
    "src/specify_cli/status/__init__.py",
    "src/specify_cli/status/wp_metadata.py",
    "src/specify_cli/cli/commands/implement.py",
    # implement-degod WP09: implement.py's phase blocks and --recover family moved here.
    "src/specify_cli/cli/commands/implement_phases.py",
    "src/specify_cli/cli/commands/implement_recover.py",
    "src/specify_cli/cli/commands/agent/tasks_transition_core.py",
    "src/specify_cli/cli/commands/agent/tasks_shared.py",
    "src/specify_cli/cli/commands/agent/tasks_mark_status.py",
    "src/specify_cli/cli/commands/agent/tasks_status_cmd.py",
    "src/specify_cli/cli/commands/agent/workflow_executor.py",
    "src/specify_cli/core/stale_detection.py",
    "src/specify_cli/task_utils/support.py",
    "src/specify_cli/frontmatter.py",
    "src/specify_cli/task_metadata_validation.py",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── Fixture builders (plain tmp dir — emit works without a git repo) ────────


def _make_feature_dir(tmp_path: Path, *, status_phase: int) -> Path:
    fd = tmp_path / "kitty-specs" / _SLUG
    fd.mkdir(parents=True)
    (fd / "meta.json").write_text(f'{{"status_phase": {status_phase}}}', encoding="utf-8")
    return fd


def _write_wp_file(feature_dir: Path, *, extra_frontmatter: str = "", body: str = "# WP\n") -> Path:
    """Write a WP prompt file. Callers control the runtime frontmatter so we can
    prove the snapshot (not a stale frontmatter value) is what readers surface."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_file = tasks_dir / f"{_WP}.md"
    wp_file.write_text(
        f"---\nwork_package_id: {_WP}\ntitle: Test WP\nagent_profile: python-pedro\n{extra_frontmatter}---\n{body}",
        encoding="utf-8",
    )
    return wp_file


def _load_work_package(wp_file: Path) -> WorkPackage:
    text = wp_file.read_text(encoding="utf-8")
    frontmatter, body, padding = split_frontmatter(text)
    return WorkPackage(
        feature=_SLUG,
        path=wp_file,
        current_lane="planned",
        relative_subpath=Path(wp_file.name),
        frontmatter=frontmatter,
        body=body,
        padding=padding,
    )


def _claim(feature_dir: Path, *, shell_pid: int, agent: str = "claude") -> None:
    """Drive a REAL planned -> claimed transition carrying the claim triple on
    the transition's policy_metadata sidecar (the post-cutover claim shape)."""
    seed_wp_to_planned(feature_dir, _WP, slug=_SLUG)
    emit_status_transition(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id=_WP,
        to_lane="claimed",
        actor=agent,
        policy_metadata=build_claim_policy_metadata(shell_pid, "2026-07-20T00:00:00Z", agent),
    )


@pytest.fixture(autouse=True)
def _no_emit_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the transitions local — no SaaS fan-out, no dossier sync."""
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None, raising=False)
# ── 1. Byte-stability (SC-004 / NFR-003) — the headline ─────────────────────


def test_claim_writes_zero_bytes_to_wp_file(tmp_path: Path) -> None:
    """A real claim transition leaves ``tasks/WP##.md`` byte-identical while the
    event log gains the event and the snapshot reflects the claim triple."""
    fd = _make_feature_dir(tmp_path, status_phase=1)
    # Modern WP shape: no runtime frontmatter, no ``lane:`` field -> the retained
    # lane mirror is a no-op and the deleted dual-write cannot fire.
    wp_file = _write_wp_file(fd)

    before = wp_file.read_bytes()
    events_before = (fd / "status.events.jsonl").read_bytes() if (fd / "status.events.jsonl").exists() else b""

    _claim(fd, shell_pid=424242, agent="claude")

    after = wp_file.read_bytes()
    events_after = (fd / "status.events.jsonl").read_bytes()

    # Real before/after compare (SC-004 — not a mock).
    assert after == before, "the claim must write 0 bytes to tasks/WP01.md"
    # The transition genuinely happened: the event log grew and the snapshot
    # carries the claim triple (proving the runtime slots rode the event log).
    assert events_after != events_before
    snap = wp_snapshot_state(fd, _WP)
    assert snap is not None
    assert str(snap.get("lane")) == str(Lane.CLAIMED)
    assert str(snap.get("shell_pid")) == "424242"
    assert snap.get("agent") == "claude"


def test_inner_state_annotation_writes_zero_bytes_to_wp_file(tmp_path: Path) -> None:
    """The runtime-slot annotation path (shell_pid/agent/subtasks) — the write
    the deleted dual-write blocks used to mirror — writes 0 WP-file bytes."""
    fd = _make_feature_dir(tmp_path, status_phase=1)
    wp_file = _write_wp_file(fd)
    seed_wp_to_planned(fd, _WP, slug=_SLUG)

    before = wp_file.read_bytes()
    emit_inner_state_changed(
        fd,
        _WP,
        WPInnerStateDelta(shell_pid=777001, agent="codex", subtasks={"T001": Lane.DONE}),
        actor="codex",
        mission_slug=_SLUG,
    )
    after = wp_file.read_bytes()

    assert after == before, "an inner-state annotation must write 0 bytes to tasks/WP01.md"
    snap = wp_snapshot_state(fd, _WP)
    assert snap is not None and str(snap.get("shell_pid")) == "777001"


# ── 2. Predicate gone (SC-002) + write_shell_pid_claim retirement ───────────


def test_predicate_has_zero_occurrences_in_owned_files() -> None:
    """SC-002: no WP04-owned source line names the deleted predicate/facade."""
    root = _repo_root()
    offenders: list[str] = []
    for rel in _WP04_OWNED_SRC:
        text = (root / rel).read_text(encoding="utf-8")
        if "phase1_snapshot_authority_active" in text:
            offenders.append(rel)
    assert offenders == [], f"predicate/facade still referenced in: {offenders}"


def test_facade_export_import_raises() -> None:
    """The facade export is gone: the import raises and the name is off __all__."""
    import specify_cli.status as status_pkg

    assert "phase1_snapshot_authority_active" not in status_pkg.__all__
    with pytest.raises(ImportError):
        from specify_cli.status import phase1_snapshot_authority_active  # noqa: F401


def test_predicate_symbol_deleted_from_emit() -> None:
    """The private predicate itself is deleted from ``status.emit`` (C-002)."""
    import specify_cli.status.emit as status_emit

    assert not hasattr(status_emit, "_phase1_snapshot_authority_active")
    # C-004: the retained twin + phase reader are untouched and still present.
    assert hasattr(status_emit, "_legacy_lane_mirror_enabled")
    assert hasattr(status_emit, "_read_status_phase")


def test_write_shell_pid_claim_is_retired() -> None:
    """T015: ``write_shell_pid_claim`` is fully retired from ``frontmatter``."""
    import specify_cli.frontmatter as frontmatter

    assert "write_shell_pid_claim" not in frontmatter.__all__
    assert not hasattr(frontmatter, "write_shell_pid_claim")
    with pytest.raises(ImportError):
        from specify_cli.frontmatter import write_shell_pid_claim  # noqa: F401


# ── 3. Per-site unconditional-read behaviour ────────────────────────────────


def test_infer_subtasks_complete_reads_snapshot_regardless_of_status_phase(tmp_path: Path) -> None:
    """emit._infer_subtasks_complete resolves completion from the snapshot ``subtasks``
    slot with NO flag branch — it reads the snapshot even at ``status_phase=0``.

    The roster is the authored ``subtasks:`` frontmatter list (#2816 IC-10); the
    snapshot supplies completion."""
    fd = _make_feature_dir(tmp_path, status_phase=0)  # flag would have been OFF
    _write_wp_file(fd, extra_frontmatter="subtasks:\n- T001\n- T002\n")
    seed_wp_to_planned(fd, _WP, slug=_SLUG)
    emit_inner_state_changed(
        fd,
        _WP,
        WPInnerStateDelta(subtasks={"T001": Lane.DONE, "T002": Lane.DONE}),
        actor="claude",
        mission_slug=_SLUG,
    )
    # All roster ids DONE in the snapshot -> complete (no tasks.md consulted).
    assert _infer_subtasks_complete(fd, _WP) is True

    # An incomplete subtask flips it False (still snapshot-sourced).
    emit_inner_state_changed(
        fd,
        _WP,
        WPInnerStateDelta(subtasks={"T001": Lane.DONE, "T002": Lane.IN_PROGRESS}),
        actor="claude",
        mission_slug=_SLUG,
    )
    assert _infer_subtasks_complete(fd, _WP) is False


def test_infer_subtasks_complete_silent_snapshot_blocks_fail_closed(tmp_path: Path) -> None:
    """Fail-closed: an authored frontmatter roster with NO event-sourced ``subtasks``
    slot BLOCKS (unprovable completeness). The retired ``tasks.md`` checkbox proxy no
    longer provides any fallback completion source (#2816 IC-10) — an unchecked
    ``tasks.md`` row can no longer move the gate."""
    fd = _make_feature_dir(tmp_path, status_phase=1)
    _write_wp_file(fd, extra_frontmatter="subtasks:\n- T001\n")
    # A tasks.md unchecked row is now IRRELEVANT — the roster is snapshot-gated.
    (fd / "tasks.md").write_text(
        f"## {_WP}: Repro\n- [ ] T001 First ({_WP})\n", encoding="utf-8"
    )
    # No snapshot subtasks slot -> silent -> fail-closed BLOCK on the roster id.
    assert _infer_subtasks_complete(fd, _WP) is False


def test_st_gated_runtime_fields_returns_snapshot_never_frontmatter(tmp_path: Path) -> None:
    """tasks_status_cmd._st_gated_runtime_fields resolves the snapshot slots and
    never the frontmatter ``extract_scalar`` values (there is no flag branch)."""
    fd = _make_feature_dir(tmp_path, status_phase=1)
    _claim(fd, shell_pid=515151, agent="snapshot-agent")

    agent, shell_pid = _st_gated_runtime_fields(fd, _WP)
    assert agent == "snapshot-agent"
    assert shell_pid == "515151"

    # An unidentifiable WP (wp_id is None) yields the conservative empty result.
    assert _st_gated_runtime_fields(fd, None) == ("", "")


def test_workpackage_runtime_properties_are_snapshot_sourced(tmp_path: Path) -> None:
    """WorkPackage.{agent,assignee,shell_pid} resolve the snapshot; a DIFFERENT
    frontmatter value is never surfaced (C-001 — no frontmatter fallback)."""
    fd = _make_feature_dir(tmp_path, status_phase=1)
    # Stale/wrong frontmatter values that must NOT leak through.
    wp_file = _write_wp_file(fd, extra_frontmatter='agent: frontmatter-agent\nshell_pid: "111"\n')
    _claim(fd, shell_pid=626262, agent="snapshot-agent")
    emit_inner_state_changed(
        fd,
        _WP,
        WPInnerStateDelta(assignee="snapshot-assignee"),
        actor="snapshot-agent",
        mission_slug=_SLUG,
    )

    wp = _load_work_package(wp_file)
    assert wp.agent == "snapshot-agent"  # snapshot, not "frontmatter-agent"
    assert wp.shell_pid == "626262"  # snapshot, not "111"
    assert wp.assignee == "snapshot-assignee"


def test_workpackage_absent_snapshot_is_authoritative_empty(tmp_path: Path) -> None:
    """An absent snapshot entry is authoritative empty (None), NOT a frontmatter
    fallback — even though the frontmatter carries a value."""
    fd = _make_feature_dir(tmp_path, status_phase=1)
    wp_file = _write_wp_file(fd, extra_frontmatter='agent: frontmatter-agent\nshell_pid: "111"\n')
    # A canonical log exists, but has no snapshot entry for WP01. This is
    # distinct from a missing log, which correctly fails closed.
    seed_wp_to_planned(fd, "WP99", slug=_SLUG)
    wp = _load_work_package(wp_file)
    assert wp.agent is None
    assert wp.shell_pid is None
    assert wp.assignee is None


def test_read_wp_frontmatter_runtime_fields_are_snapshot_sourced(tmp_path: Path) -> None:
    """wp_metadata.read_wp_frontmatter (the collapsed out-of-map site) re-points
    the runtime fields to the snapshot; agent_profile stays frontmatter-canonical."""
    fd = _make_feature_dir(tmp_path, status_phase=1)
    wp_file = _write_wp_file(fd, extra_frontmatter='agent: frontmatter-agent\nshell_pid: "111"\n')
    _claim(fd, shell_pid=636363, agent="snapshot-agent")

    metadata, _body = read_wp_frontmatter(wp_file)
    assert str(metadata.shell_pid) == "636363"  # snapshot, not "111"
    assert metadata.agent == "snapshot-agent"  # snapshot, not "frontmatter-agent"
    assert metadata.agent_profile == "python-pedro"  # design-intent, frontmatter-canonical


# ── 4. Lane-mirror activation regression (T016 / C-004 / research D-02) ──────


def test_lane_mirror_activation_does_not_change_lane_read(tmp_path: Path) -> None:
    """Flipping status_phase 0->1 ACTIVATES the retained lane mirror (it rewrites
    the transitional frontmatter ``lane`` field) but the resolved lane READ
    (event-log-sourced) is IDENTICAL across both phases.

    Non-vacuous: the WP file carries a STALE ``lane: planned`` field. If a lane
    read consulted frontmatter, the mirror-off (phase 0) and mirror-on (phase 1)
    reads would diverge. They must not.
    """
    results: dict[int, Lane] = {}
    mirrored_lane_field: dict[int, str | None] = {}

    for phase in (0, 1):
        sub = tmp_path / f"phase{phase}"
        sub.mkdir()
        fd = _make_feature_dir(sub, status_phase=phase)
        # Stale ``lane:`` field present -> the mirror has something to update.
        wp_file = _write_wp_file(fd, extra_frontmatter="lane: planned\n")

        _claim(fd, shell_pid=900000 + phase, agent="claude")

        results[phase] = get_wp_lane(fd, _WP)
        # Read the raw frontmatter ``lane:`` field post-transition.
        front, _b, _p = split_frontmatter(wp_file.read_text(encoding="utf-8"))
        from specify_cli.task_utils.support import extract_scalar

        mirrored_lane_field[phase] = extract_scalar(front, "lane")

    # Load-bearing: the resolved lane READ is identical across phases.
    assert results[0] == results[1] == Lane.CLAIMED

    # Non-vacuous proof that the flip is NOT inert (research D-02): the mirror
    # is OFF at phase 0 (stale ``lane: planned`` survives) and ON at phase 1
    # (rewritten to the canonical ``claimed``). If activation had been a no-op
    # both would read ``planned``; if it had changed the lane read the first
    # assertion would have failed.
    assert mirrored_lane_field[0] == "planned"
    assert mirrored_lane_field[1] == "claimed"
