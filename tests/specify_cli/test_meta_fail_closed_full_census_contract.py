"""FR-007 / NFR-003 — the fail-closed ``meta.json`` contract gate.

This module carries TWO independent guarantees. They are deliberately
separate mechanisms, because either one alone is forgeable:

1. **The live call-site census.** An AST scan of the actual source tree
   discovers every ``load_meta`` call site that exists *right now* and
   cross-references it against the frozen ``ACCOUNTED_SITES`` ledger. The
   scanner and the ledger live in :mod:`tests.architectural._load_meta_census`
   (one home since #5138) and the always-on gate over them is
   ``tests/architectural/test_lifted_root_meta_fail_closed_census.py``; this
   module keeps only the WP09-specific projection
   (:func:`test_wp09_owned_files_retain_only_silent_sites`).

2. **The real-reader contract** (:func:`test_routed_reader_fails_closed`).
   For a representative routed site in every subsystem WP09 owns, the ACTUAL
   product function is invoked against a corrupt and a non-dict ``meta.json``
   and must answer with its declared typed/sentinel outcome. A raw
   ``ValueError`` is an explicit, unconditional failure — that leak is
   precisely what NFR-003 forbids.

The census's load-bearing design constraints (never sourced from a census
snapshot; resolves aliased imports) are documented with the scanner in
:mod:`tests.architectural._load_meta_census`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from specify_cli.core.paths import MissionMetaReadError
from tests.architectural._load_meta_census import ACCOUNTED_SITES, scan_load_meta_call_sites

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

#: Corrupt: truncated, syntactically invalid JSON — genuinely unparseable.
_CORRUPT_META = '{"mission_id": "01JABCDEFGHJKMNPQRSTVWXYZ", '
#: Non-dict: parses cleanly but the top level is a list, not an object.
#: This is a DIFFERENT failure mode from the corrupt case, not a synonym.
_NON_DICT_META = "[1, 2, 3]"

_MISSION_SLUG = "probe-mission"
_MISSION_ID = "01JABCDEFGHJKMNPQRSTVWXYZ"


# --------------------------------------------------------------------------- #
# 1. The live call-site census (scanner + ledger: tests.architectural._load_meta_census).
# --------------------------------------------------------------------------- #

#: WP09's owned batch-B subsystems. After routing, the ONLY sites these files
#: may still contain are ``silent-by-contract`` ones.
_WP09_OWNED_FILES: frozenset[str] = frozenset(
    {
        "src/specify_cli/consolidation/baseline.py",
        "src/specify_cli/consolidation/executor.py",
        "src/specify_cli/consolidation/ordering.py",
        "src/specify_cli/dashboard/diagnostics.py",
        "src/specify_cli/dashboard/scanner.py",
        "src/specify_cli/cli/commands/agent/mission_check_prerequisites.py",
        "src/specify_cli/cli/commands/agent/mission_feature_resolution.py",
        "src/specify_cli/cli/commands/agent/mission_repair.py",
        "src/specify_cli/cli/commands/agent/mission_setup_plan.py",
        "src/specify_cli/cli/commands/agent/workflow.py",
        "src/specify_cli/cli/commands/_coordination_doctor.py",
        "src/specify_cli/cli/commands/_identity_audit.py",
        "src/specify_cli/cli/commands/implement.py",
        "src/specify_cli/cli/commands/merge.py",
        "src/specify_cli/cli/commands/mission_type.py",
        "src/specify_cli/cli/commands/tracker.py",
        "src/specify_cli/doc_analysis/doc_state.py",
        "src/specify_cli/tracker/origin.py",
        "src/specify_cli/acceptance/__init__.py",
    }
)

# The always-on gate over the whole ledger (and the scanner's non-vacuity
# proofs) is tests/architectural/test_lifted_root_meta_fail_closed_census.py.


def test_wp09_owned_files_retain_only_silent_sites() -> None:
    """WP09's batch-B routing is complete: no raise-contract readers remain."""
    live = scan_load_meta_call_sites(_SRC_ROOT)
    offenders = sorted(
        f"  {rel}::{qual} ({ACCOUNTED_SITES.get((rel, qual), (0, 'UNACCOUNTED'))[1]})"
        for (rel, qual) in live
        if rel in _WP09_OWNED_FILES and ACCOUNTED_SITES.get((rel, qual), (0, "UNACCOUNTED"))[1] != "silent-by-contract"
    )
    assert not offenders, "WP09-owned files still hold non-silent `load_meta` sites:\n" + "\n".join(offenders)


# --------------------------------------------------------------------------- #
# 5. The real-reader contract: drive ACTUAL product functions.
# --------------------------------------------------------------------------- #

_RAISES_TYPED = "raises-typed"
_RAISES_DOMAIN = "raises-domain"
_RETURNS = "returns"


@dataclass(frozen=True)
class RoutedReader:
    """One routed census site, driven through its real public entry point."""

    subsystem: str
    label: str
    invoke: Callable[[Path], Any]
    outcome: str
    domain_exc: type[BaseException] | None = None
    expected: Any = None


def _seed_mission(tmp_path: Path, payload: str) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(payload, encoding="utf-8")
    return feature_dir


def _drive_merge_baseline(feature_dir: Path) -> Any:
    from specify_cli.consolidation.baseline import record_baseline_merge_commit

    return record_baseline_merge_commit(feature_dir, "deadbeef", mission_id=_MISSION_ID)


def _drive_merge_baseline_soft(feature_dir: Path) -> Any:
    from specify_cli.consolidation.baseline import _recorded_baseline_from_working_meta

    return _recorded_baseline_from_working_meta(feature_dir)


def _drive_dashboard(feature_dir: Path) -> Any:
    from specify_cli.dashboard.diagnostics import _resolve_mission_from_feature

    return _resolve_mission_from_feature(feature_dir)


def _drive_cli_mission_type(feature_dir: Path) -> Any:
    from specify_cli.cli.commands.mission_type import _safe_load_meta

    return _safe_load_meta(feature_dir)


def _drive_cli_identity_audit(feature_dir: Path) -> Any:
    from specify_cli.cli.commands._identity_audit import _read_stored_topology

    return _read_stored_topology(feature_dir)


def _drive_cli_agent_setup_plan(feature_dir: Path) -> Any:
    from specify_cli.cli.commands.agent.mission_setup_plan import _resolve_plan_template

    return _resolve_plan_template(feature_dir.parent.parent, feature_dir)


def _drive_doc_read(feature_dir: Path) -> Any:
    from specify_cli.doc_analysis.doc_state import read_documentation_state

    return read_documentation_state(feature_dir / "meta.json")


def _drive_doc_write(feature_dir: Path) -> Any:
    from specify_cli.doc_analysis.doc_state import set_iteration_mode

    return set_iteration_mode(feature_dir / "meta.json", "initial")


def _drive_tracker(feature_dir: Path) -> Any:
    from specify_cli.tracker.origin import bind_mission_origin
    from specify_cli.tracker.origin_models import OriginCandidate

    candidate = OriginCandidate(
        external_issue_id="1",
        external_issue_key="PROBE-1",
        title="probe",
        status="open",
        url="https://example.invalid/1",
        match_type="exact",
    )
    return bind_mission_origin(feature_dir, candidate, "github")


def _drive_acceptance(feature_dir: Path) -> Any:
    """Drive ``acceptance._commit_acceptance_meta`` against a real git repo.

    ``record_acceptance`` is stubbed because it lives in ``mission_metadata.py``
    -- the module that defines the DEF A parser itself, classified
    ``authority`` in the ledger above (routing it onto the wrapper would be
    circular) -- and would raise its own raw ``ValueError`` before control
    ever reaches the acceptance-owned routed read. Stubbing it isolates the
    site actually under test here; it does not weaken the assertion, which
    still runs against the real product function.
    """
    import specify_cli.acceptance as acc

    repo_root = feature_dir.parent.parent

    def _git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)

    _git("init", "-b", "mission-lane")
    _git("config", "user.email", "pedro@example.com")
    _git("config", "user.name", "Python Pedro")
    (repo_root / "README.md").write_text("probe\n", encoding="utf-8")
    # Commit ONLY the README: meta.json must stay untracked so the function's
    # own ``git add`` stages it and the flow reaches the routed read (an
    # already-committed meta.json short-circuits on "nothing staged").
    _git("add", "README.md")
    _git("commit", "-m", "init")

    summary = acc.AcceptanceSummary(
        feature=_MISSION_SLUG,
        repo_root=repo_root,
        feature_dir=feature_dir,
        tasks_dir=feature_dir / "tasks",
        branch="mission-lane",
        worktree_root=repo_root,
        primary_repo_root=repo_root,
        lanes={},
        work_packages=[],
        metadata_issues=[],
        activity_issues=[],
        unchecked_tasks=[],
        needs_clarification=[],
        missing_artifacts=[],
        optional_missing=[],
        git_dirty=[],
        path_violations=[],
        warnings=[],
    )

    original = acc.record_acceptance
    acc.record_acceptance = lambda *a, **k: None
    try:
        return acc._commit_acceptance_meta(summary, "pedro", "standard")
    finally:
        acc.record_acceptance = original


def _routed_readers() -> list[RoutedReader]:
    from specify_cli.consolidation.baseline import BaselineMergeCommitError
    from specify_cli.tracker.origin import OriginBindingError

    return [
        RoutedReader("merge", "baseline.record_baseline_merge_commit", _drive_merge_baseline, _RAISES_DOMAIN, BaselineMergeCommitError),
        RoutedReader("merge", "baseline._recorded_baseline_from_working_meta", _drive_merge_baseline_soft, _RETURNS, expected=""),
        RoutedReader("dashboard", "diagnostics._resolve_mission_from_feature", _drive_dashboard, _RETURNS, expected=None),
        RoutedReader("cli", "mission_type._safe_load_meta", _drive_cli_mission_type, _RETURNS, expected=None),
        RoutedReader("cli", "_identity_audit._read_stored_topology", _drive_cli_identity_audit, _RETURNS),
        RoutedReader("cli/agent", "mission_setup_plan._resolve_plan_template", _drive_cli_agent_setup_plan, _RAISES_TYPED),
        RoutedReader("doc_analysis", "doc_state.read_documentation_state", _drive_doc_read, _RAISES_TYPED),
        RoutedReader("doc_analysis", "doc_state.set_iteration_mode", _drive_doc_write, _RAISES_TYPED),
        RoutedReader("tracker", "origin.bind_mission_origin", _drive_tracker, _RAISES_DOMAIN, OriginBindingError),
        RoutedReader("acceptance", "_commit_acceptance_meta", _drive_acceptance, _RAISES_TYPED),
    ]


def _reader_ids() -> list[str]:
    return [f"{r.subsystem}:{r.label}" for r in _routed_readers()]


@pytest.mark.parametrize("reader", _routed_readers(), ids=_reader_ids())
@pytest.mark.parametrize(
    ("scenario", "payload"),
    [("corrupt-json", _CORRUPT_META), ("non-dict-json", _NON_DICT_META)],
)
def test_routed_reader_fails_closed(tmp_path: Path, reader: RoutedReader, scenario: str, payload: str) -> None:
    """NFR-003: a routed reader answers typed-or-sentinel — never raw ValueError.

    Each case invokes the REAL product function at a routed census site (not a
    synthetic call to the raw reader) against a genuinely unparseable
    ``meta.json`` and, separately, a well-formed but non-object one.
    """
    feature_dir = _seed_mission(tmp_path, payload)

    try:
        result = reader.invoke(feature_dir)
    except MissionMetaReadError:
        assert reader.outcome == _RAISES_TYPED, f"{reader.label} ({scenario}) raised MissionMetaReadError but its declared contract is {reader.outcome!r}"
        return
    except ValueError as exc:  # noqa: TRY302 - the assertion IS the point
        # MissionMetaReadError is a RuntimeError, so it never lands here. A raw
        # ValueError reaching this arm is exactly the NFR-003 leak.
        pytest.fail(
            f"NFR-003 VIOLATION: {reader.label} ({scenario}) surfaced a raw "
            f"{type(exc).__name__}: {exc}. A routed reader must raise "
            f"MissionMetaReadError (or its own typed domain error), never ValueError."
        )
    except BaseException as exc:  # noqa: BLE001 - classify anything else explicitly
        assert reader.outcome == _RAISES_DOMAIN and reader.domain_exc is not None, f"{reader.label} ({scenario}) raised unexpected {type(exc).__name__}: {exc}"
        assert isinstance(exc, reader.domain_exc), (
            f"{reader.label} ({scenario}) raised {type(exc).__name__}, expected the declared domain error {reader.domain_exc.__name__}"
        )
        assert not isinstance(exc, ValueError), f"NFR-003 VIOLATION: {reader.label} ({scenario}) domain error {type(exc).__name__} subclasses ValueError"
        return
    else:
        assert reader.outcome == _RETURNS, (
            f"{reader.label} ({scenario}) returned {result!r} but its declared contract is {reader.outcome!r} (it should have raised)"
        )
        if reader.expected is not None or reader.label.endswith("_resolve_mission_from_feature"):
            assert result == reader.expected, f"{reader.label} ({scenario}) returned {result!r}, expected {reader.expected!r}"
