"""coord-artifact-single-home-01M3V4BE WP11 -- the decision-index merge driver
(T059-T061, FR-009b / D13 / #5023 / R21).

Covers:

- R21 (red-first, C-005/ATDD-first): two lanes that each add a decision to
  ``kitty-specs/<dir>/decisions/index.json`` merge with BOTH entries present,
  through a real ``git merge`` with the driver configured -- proving the loss
  before fixing it. Without the driver, a plain ``git merge`` conflicts on
  this path (two independent adds under the same key with no common blob),
  which is itself evidence of the gap this driver closes.
- A unit-level sibling that calls :func:`run_decision_index_driver` directly
  with three temp files (base/ours/theirs), mirroring the git-level proof
  without subprocess/git overhead.
- :func:`union_decision_index` (T060/P-M6, the pure, shared union body also
  reused by ``doctor decisions --repair``): keyed union, terminal-beats-open
  fold precedence, the one legal reopen pair (deferred -> resolved),
  two-conflicting-terminals refusal, malformed-input refusal, and
  deterministic ``(created_at, decision_id)`` ordering.
- Byte-stable output for a no-op merge (``ours == theirs``), round-tripped
  through the same :class:`~specify_cli.decisions.models.DecisionIndex`
  serializer ``decisions/store.py::save_index`` uses.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from kernel.clock import UTC, datetime
from specify_cli.consolidation.drivers import (
    DecisionIndexMergeError,
    MergeDriverError,
    run_decision_index_driver,
    union_decision_index,
)
from specify_cli.decisions.models import DecisionIndex, DecisionStatus, IndexEntry, OriginFlow
from specify_cli.decisions.store import save_index

# Module-level marker convention (mirrors tests/specify_cli/cli/commands/
# test_review_cycle_merge_driver.py): most tests here shell out to real git;
# the pure in-process tests additionally carry their own @pytest.mark.unit.
pytestmark = [pytest.mark.git_repo]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

_MISSION_SLUG = "m-01ABCDEFGHJKMNPQRSTVWXYZ0"
_DECISIONS_REL_PATH = f"kitty-specs/{_MISSION_SLUG}/decisions/index.json"
_DECISION_INDEX_ATTR_ENTRY = "kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _entry(decision_id: str, *, created_at: datetime, question: str) -> IndexEntry:
    return IndexEntry(
        decision_id=decision_id,
        origin_flow=OriginFlow.SPECIFY,
        step_id="specify.step1",
        input_key=f"key-{decision_id}",
        question=question,
        status=DecisionStatus.OPEN,
        created_at=created_at,
        mission_id=_MISSION_SLUG,
        mission_slug=_MISSION_SLUG,
    )


_BASE_ENTRY = _entry(
    "01HBASE0000000000000000000",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    question="Base decision?",
)
_ENTRY_A = _entry(
    "01HLANEA00000000000000000A",
    created_at=datetime(2026, 1, 2, tzinfo=UTC),
    question="Lane A decision?",
)
_ENTRY_B = _entry(
    "01HLANEB00000000000000000B",
    created_at=datetime(2026, 1, 3, tzinfo=UTC),
    question="Lane B decision?",
)


def _mission_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / _MISSION_SLUG


def _write_index(repo: Path, entries: tuple[IndexEntry, ...]) -> None:
    """Write ``index.json`` through the production writer (decisions/store.py)."""
    save_index(_mission_dir(repo), DecisionIndex(mission_id=_MISSION_SLUG, entries=entries))


def _dump_index(path: Path, entries: tuple[IndexEntry, ...]) -> None:
    """Serialize an index the same way ``store.save_index`` does, to a bare path."""
    index = DecisionIndex(mission_id=_MISSION_SLUG, entries=entries)
    path.write_text(json.dumps(index.model_dump(mode="json"), sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _hermetic_driver_command_line() -> str:
    """An absolute-interpreter-path driver command this test builds itself --
    never bare ``spec-kitty`` on ``PATH``, never the ambient ``.git/config``."""
    return f"{shlex.quote(sys.executable)} -m specify_cli merge-driver-decision-index %O %A %B"


def _hermetic_env() -> dict[str, str]:
    """An explicit env this test constructs itself: ``PYTHONPATH`` points at
    THIS worktree's ``src/`` so the spawned subprocess imports this lane's
    ``specify_cli``, never an unrelated ambient ``PATH``/site-packages."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC_ROOT)
    return env


def _bootstrap_two_lanes(repo: Path) -> None:
    """Base commit holds one entry; ``lane-a`` adds A, ``lane-b`` adds B."""
    _init_repo(repo)
    _write_index(repo, (_BASE_ENTRY,))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base: one decision")

    _git(repo, "branch", "lane-a")
    _git(repo, "branch", "lane-b")

    _git(repo, "checkout", "-q", "lane-a")
    _write_index(repo, (_BASE_ENTRY, _ENTRY_A))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "lane-a: add decision A")

    _git(repo, "checkout", "-q", "lane-b")
    _write_index(repo, (_BASE_ENTRY, _ENTRY_B))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "lane-b: add decision B")


# ---------------------------------------------------------------------------
# R21 -- two lanes adding decisions merge without loss (real git merge)
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
@pytest.mark.non_sandbox  # shells out to a real `python -m specify_cli` subprocess
def test_two_lanes_adding_decisions_merge_without_loss(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _bootstrap_two_lanes(repo)

    # The ``.gitattributes`` mapping must be committed on the MERGE-TARGET
    # (``ours``) branch -- git resolves attributes from the checked-out
    # side being merged INTO, not from ``theirs``. Committing it onto
    # ``lane-b`` (the side merged FROM) would leave ``lane-a`` without the
    # mapping once checked out below, and the driver would never fire.
    _git(repo, "checkout", "-q", "lane-a")
    (repo / ".gitattributes").write_text(_DECISION_INDEX_ATTR_ENTRY + "\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "attrs")

    _git(repo, "config", "merge.spec-kitty-decision-index.name", "decision-index test driver")
    _git(repo, "config", "merge.spec-kitty-decision-index.driver", _hermetic_driver_command_line())

    result = subprocess.run(
        ["git", "merge", "lane-b"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=_hermetic_env(),
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    merged_text = (repo / _DECISIONS_REL_PATH).read_text(encoding="utf-8")
    merged = json.loads(merged_text)
    ids = {entry["decision_id"] for entry in merged["entries"]}
    assert ids == {_BASE_ENTRY.decision_id, _ENTRY_A.decision_id, _ENTRY_B.decision_id}, f"expected base + both lanes' entries to survive the merge, got {ids!r}"
    assert "<<<<<<<" not in merged_text, "no conflict markers must remain"


@pytest.mark.unit
def test_run_decision_index_driver_unions_disjoint_additions_directly(tmp_path: Path) -> None:
    """Unit-level sibling of R21: calls the driver body directly with three
    temp files (base/ours/theirs), no subprocess/git overhead."""
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    _dump_index(base, (_BASE_ENTRY,))
    _dump_index(ours, (_BASE_ENTRY, _ENTRY_A))
    _dump_index(theirs, (_BASE_ENTRY, _ENTRY_B))

    run_decision_index_driver(str(base), str(ours), str(theirs))

    merged = json.loads(ours.read_text(encoding="utf-8"))
    ids = {entry["decision_id"] for entry in merged["entries"]}
    assert ids == {_BASE_ENTRY.decision_id, _ENTRY_A.decision_id, _ENTRY_B.decision_id}


@pytest.mark.unit
def test_run_decision_index_driver_byte_stable_when_ours_equals_theirs(tmp_path: Path) -> None:
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    index = DecisionIndex(mission_id=_MISSION_SLUG, entries=(_BASE_ENTRY, _ENTRY_A))
    payload = json.dumps(index.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
    base.write_text("", encoding="utf-8")
    ours.write_text(payload, encoding="utf-8")
    theirs.write_text(payload, encoding="utf-8")

    run_decision_index_driver(str(base), str(ours), str(theirs))

    assert ours.read_text(encoding="utf-8") == payload


@pytest.mark.unit
def test_run_decision_index_driver_malformed_ours_raises(tmp_path: Path) -> None:
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text("{not json", encoding="utf-8")
    theirs.write_text("{}", encoding="utf-8")

    with pytest.raises(MergeDriverError):
        run_decision_index_driver(str(base), str(ours), str(theirs))


# ---------------------------------------------------------------------------
# union_decision_index (T060/P-M6): the pure, shared union body
# ---------------------------------------------------------------------------


def _raw_entry(decision_id: str, *, status: str = "open", created_at: str = "2026-01-01T00:00:00Z", **overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "decision_id": decision_id,
        "origin_flow": "specify",
        "step_id": "specify.step1",
        "slot_key": None,
        "input_key": f"key-{decision_id}",
        "question": "Q?",
        "options": [],
        "status": status,
        "final_answer": None,
        "rationale": None,
        "other_answer": False,
        "summary_json": None,
        "created_at": created_at,
        "resolved_at": None,
        "resolved_by": None,
        "opened_by": None,
        "mission_id": _MISSION_SLUG,
        "mission_slug": _MISSION_SLUG,
    }
    entry.update(overrides)
    return entry


def _doc(*, entries: object = (), mission_id: str = _MISSION_SLUG, **extra: object) -> dict[str, object]:
    doc: dict[str, object] = {"version": 1, "mission_id": mission_id, "entries": entries}
    doc.update(extra)
    return doc


@pytest.mark.unit
def test_union_decision_index_disjoint_additions() -> None:
    merged = union_decision_index(_doc(entries=[_raw_entry("id-a")]), _doc(entries=[_raw_entry("id-b")]))
    ids = {entry["decision_id"] for entry in merged["entries"]}
    assert ids == {"id-a", "id-b"}


@pytest.mark.unit
def test_union_decision_index_identical_entry_kept_once() -> None:
    entry = _raw_entry("id-a")
    merged = union_decision_index(_doc(entries=[entry]), _doc(entries=[dict(entry)]))
    assert len(merged["entries"]) == 1
    assert merged["entries"][0] == entry


@pytest.mark.unit
def test_union_decision_index_terminal_beats_open_ours_terminal() -> None:
    open_entry = _raw_entry("id-a", status="open")
    resolved_entry = _raw_entry("id-a", status="resolved", resolved_at="2026-01-02T00:00:00Z", resolved_by="agent", final_answer="yes")
    merged = union_decision_index(_doc(entries=[resolved_entry]), _doc(entries=[open_entry]))
    assert merged["entries"][0]["status"] == "resolved"


@pytest.mark.unit
def test_union_decision_index_terminal_beats_open_theirs_terminal() -> None:
    """Same precedence, opposite side -- proving it is not simply 'ours wins'."""
    open_entry = _raw_entry("id-a", status="open")
    resolved_entry = _raw_entry("id-a", status="resolved", resolved_at="2026-01-02T00:00:00Z", resolved_by="agent", final_answer="yes")
    merged = union_decision_index(_doc(entries=[open_entry]), _doc(entries=[resolved_entry]))
    assert merged["entries"][0]["status"] == "resolved"


@pytest.mark.unit
def test_union_decision_index_allowed_reopen_deferred_to_resolved_either_direction() -> None:
    deferred = _raw_entry("id-a", status="deferred", resolved_at="2026-01-02T00:00:00Z", resolved_by="agent")
    resolved = _raw_entry("id-a", status="resolved", resolved_at="2026-01-03T00:00:00Z", resolved_by="agent", final_answer="yes")
    merged_ours_deferred = union_decision_index(_doc(entries=[deferred]), _doc(entries=[resolved]))
    assert merged_ours_deferred["entries"][0]["status"] == "resolved"

    merged_theirs_deferred = union_decision_index(_doc(entries=[resolved]), _doc(entries=[deferred]))
    assert merged_theirs_deferred["entries"][0]["status"] == "resolved"


@pytest.mark.unit
def test_union_decision_index_two_conflicting_terminals_raises() -> None:
    resolved = _raw_entry("id-a", status="resolved", resolved_at="2026-01-02T00:00:00Z", resolved_by="a", final_answer="yes")
    canceled = _raw_entry("id-a", status="canceled", resolved_at="2026-01-02T00:00:00Z", resolved_by="b")
    with pytest.raises(DecisionIndexMergeError):
        union_decision_index(_doc(entries=[resolved]), _doc(entries=[canceled]))


@pytest.mark.unit
def test_union_decision_index_malformed_entries_not_a_list_raises() -> None:
    with pytest.raises(DecisionIndexMergeError):
        union_decision_index(_doc(entries="not-a-list"), _doc(entries=[]))


@pytest.mark.unit
def test_union_decision_index_entry_missing_decision_id_raises() -> None:
    bad_entry = _raw_entry("id-a")
    del bad_entry["decision_id"]
    with pytest.raises(DecisionIndexMergeError):
        union_decision_index(_doc(entries=[bad_entry]), _doc(entries=[]))


@pytest.mark.unit
def test_union_decision_index_invalid_status_raises() -> None:
    bad_entry = _raw_entry("id-a", status="open")
    other_entry = _raw_entry("id-a", status="not-a-real-status")
    with pytest.raises(DecisionIndexMergeError):
        union_decision_index(_doc(entries=[bad_entry]), _doc(entries=[other_entry]))


@pytest.mark.unit
def test_union_decision_index_deterministic_order() -> None:
    entry_b = _raw_entry("id-b", created_at="2026-01-01T00:00:00Z")
    entry_a = _raw_entry("id-a", created_at="2026-01-02T00:00:00Z")
    merged = union_decision_index(_doc(entries=[entry_b, entry_a]), _doc(entries=[]))
    assert [entry["decision_id"] for entry in merged["entries"]] == ["id-b", "id-a"]


@pytest.mark.unit
def test_union_decision_index_top_level_keys_prefer_ours_fall_back_to_theirs() -> None:
    merged = union_decision_index(
        _doc(entries=[], mission_id=""),
        _doc(entries=[], mission_id="theirs-mission"),
    )
    assert merged["mission_id"] == "theirs-mission"

    merged2 = union_decision_index(
        _doc(entries=[], mission_id="ours-mission"),
        _doc(entries=[], mission_id="theirs-mission"),
    )
    assert merged2["mission_id"] == "ours-mission"
