"""WP05 / T013-T014 / FR-009: advisory issue-matrix lint at ``finalize-tasks``.

#2223 — ``validate_issue_matrix`` (the closed-set schema engine) already runs
at the approve gate (``review/__init__.py``). The "correct-but-late" gap is that
a malformed ``issue-matrix.md`` is not surfaced until acceptance. This WP wires
the SAME engine as a second, **advisory (never-blocking)** caller at
``finalize-tasks`` — one rule engine, two callers (NFR-002).

These tests drive the real ``finalize_tasks`` Typer callable end-to-end (the
pre-existing entry point) with the heavy collaborators patched, mirroring the
harness in ``test_feature_finalize_bootstrap.py``. The contract:

* a malformed matrix emits a non-blocking advisory naming the violated rule AND
  finalize still completes (exit 0);
* a valid matrix is silent;
* the finalize path invokes the *same* exported ``validate_issue_matrix`` engine
  the approve gate uses — proven by CALL IDENTITY (spy/monkeypatch), not by
  matching rendered message strings (a copied rule set would pass a string
  match — the drift-masking anti-pattern);
* the lint never blocks finalize, even if the engine itself raises.

Scope binding: this WP binds to ``validate_issue_matrix`` ONLY. The completeness
"row-for-every-#ref" scan lives in ``agent/tasks_parsing_validation.py::
_issue_matrix_evaluation`` (private) and is intentionally NOT cross-imported.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.status.bootstrap import BootstrapResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MODULE = "specify_cli.cli.commands.agent.mission"
REVIEW_ENGINE = "specify_cli.cli.commands.review.validate_issue_matrix"

_MISSION_SLUG = "060-issue-matrix-finalize-lint"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# A production-shaped, schema-valid matrix: one table, mandatory columns
# (Issue / Verdict / Evidence ref), an allow-list verdict, non-empty evidence.
_VALID_MATRIX = """# Issue Matrix

| Issue | Title | Verdict | Evidence ref |
|-------|-------|---------|--------------|
| #2223 | Advisory issue-matrix lint at finalize | fixed | tests/specify_cli/cli/commands/review/test_issue_matrix_finalize_lint.py |
"""

# Malformed: two Markdown tables → ISSUE_MATRIX_MULTI_TABLE (exactly one allowed).
_MALFORMED_MATRIX = """# Issue Matrix

| Issue | Title | Verdict | Evidence ref |
|-------|-------|---------|--------------|
| #2223 | Advisory issue-matrix lint at finalize | fixed | tests/...lint.py |

The operator accidentally pasted a second table below.

| Issue | Title | Verdict | Evidence ref |
|-------|-------|---------|--------------|
| #2224 | Stray duplicate table | fixed | tests/...other.py |
"""


@pytest.fixture(autouse=True)
def _disable_saas_sync_for_finalize_lint_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep these unit tests on the offline finalize-tasks path.

    ``tests/conftest.py`` enables SaaS sync globally so sync/auth tests keep
    exercising the hosted path. These tests patch git/event/bootstrap/commit
    collaborators in-process and are not testing the SaaS boundary preflight;
    leaving the flag enabled makes finalize refuse before the lint phase runs.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _make_bootstrap_result() -> BootstrapResult:
    return BootstrapResult(total_wps=2, already_initialized=0, newly_seeded=2, skipped=0)


def _setup_mission(tmp_path: Path, *, matrix: str | None) -> Path:
    """Create a minimal-but-complete mission directory for ``finalize_tasks``.

    Mirrors ``test_feature_finalize_bootstrap._setup_feature`` (2 WPs, FR-001)
    and optionally seeds an ``issue-matrix.md`` with ``matrix`` content.
    """
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "spec.md").write_text(
        "---\ntitle: Test Mission\n---\n\n## Requirements\n\n- FR-001: First requirement\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\n'
            f"requirement_refs:\n  - FR-001\ndependencies: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": _MISSION_SLUG}), encoding="utf-8"
    )
    if matrix is not None:
        (feature_dir / "issue-matrix.md").write_text(matrix, encoding="utf-8")
    return feature_dir


def _common_patches(tmp_path: Path) -> dict[str, MagicMock]:
    """Patch the heavy finalize collaborators (git / events / bootstrap / commit)."""
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    fake_commit = CommitRouterResult(
        status="committed", placement_ref="main", commit_hash="abc1234"
    )
    return {
        f"{MODULE}.locate_project_root": MagicMock(return_value=tmp_path),
        f"{MODULE}._find_feature_directory": MagicMock(return_value=feature_dir),
        f"{MODULE}._resolve_planning_branch": MagicMock(return_value="main"),
        f"{MODULE}.bootstrap_canonical_state": MagicMock(
            return_value=_make_bootstrap_result()
        ),
        "specify_cli.coordination.commit_router.commit_for_mission": MagicMock(
            return_value=fake_commit
        ),
        f"{MODULE}.run_command": MagicMock(return_value=(0, "abc1234", "")),
        # finalize reads dirty candidates through ``kernel.git.status_entries`` (no longer
        # ``run_command`` porcelain text); this narrow seam keeps the commit path hermetic.
        "specify_cli.cli.commands.agent.mission_finalize._finalize_candidates_dirty": MagicMock(return_value=True),
        # Leak #1 (mission integration-boundary-01KW0PBE) removed the module-level
        # ``emit_mission_created`` import from core.mission_creation; the MissionCreated
        # projection now flows through the canonical status facade
        # ``emit_mission_created_local`` -> registered observers. Patch the facade entry
        # so the finalize path stays hermetic (no network) regardless of whether it emits.
        "specify_cli.status.emit_mission_created_local": MagicMock(),
        f"{MODULE}.validate_ownership": MagicMock(
            return_value=MagicMock(passed=True, warnings=[], errors=[]),
        ),
    }


def _run_finalize(
    patches: dict[str, MagicMock], *, extra: dict[str, object] | None = None
) -> int:
    """Drive the real ``finalize_tasks`` callable; return its exit code (0 = no raise)."""
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    ctx = {k: patch(k, v) for k, v in {**patches, **(extra or {})}.items()}
    for p in ctx.values():
        p.start()
    try:
        finalize_tasks(feature=_MISSION_SLUG, json_output=False, validate_only=False)
        return 0
    except typer.Exit as exc:
        return int(exc.exit_code)
    finally:
        for p in ctx.values():
            p.stop()


def _clean(captured: str) -> str:
    return _ANSI_RE.sub("", captured)


def test_finalize_advisory_flags_malformed_matrix_and_does_not_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed matrix is advisory-flagged at finalize AND finalize still succeeds."""
    _setup_mission(tmp_path, matrix=_MALFORMED_MATRIX)

    exit_code = _run_finalize(_common_patches(tmp_path))

    out = _clean(capsys.readouterr().out)
    # Advisory surfaced, naming the violated rule, and finalize was NOT blocked.
    assert "Advisory" in out
    assert "issue-matrix.md" in out
    assert "exactly one is allowed" in out  # the multi-table rule message
    assert exit_code == 0


def test_finalize_is_silent_for_valid_matrix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A schema-valid matrix produces no advisory and finalize succeeds."""
    _setup_mission(tmp_path, matrix=_VALID_MATRIX)

    exit_code = _run_finalize(_common_patches(tmp_path))

    out = _clean(capsys.readouterr().out)
    assert "Advisory" not in out
    assert exit_code == 0


def test_finalize_invokes_the_shared_validate_issue_matrix_engine(
    tmp_path: Path,
) -> None:
    """CALL IDENTITY: finalize invokes the SAME exported engine the approve gate uses.

    We spy on ``specify_cli.cli.commands.review.validate_issue_matrix`` (the symbol
    the approve gate calls) and assert the finalize path invokes that exact callable
    with the mission's matrix path — proving one engine, two callers, not a copy.
    """
    import specify_cli.cli.commands.review as review_pkg

    feature_dir = _setup_mission(tmp_path, matrix=_VALID_MATRIX)
    real_engine = review_pkg.validate_issue_matrix
    calls: list[Path] = []

    def _spy(path: Path) -> object:
        calls.append(path)
        return real_engine(path)

    exit_code = _run_finalize(
        _common_patches(tmp_path), extra={REVIEW_ENGINE: _spy}
    )

    assert calls == [feature_dir / "issue-matrix.md"]
    assert exit_code == 0


def test_finalize_lint_never_blocks_even_if_engine_raises(
    tmp_path: Path,
) -> None:
    """The advisory lint must never block finalize — even if the engine itself raises."""
    _setup_mission(tmp_path, matrix=_VALID_MATRIX)

    def _boom(_path: Path) -> object:
        raise RuntimeError("engine exploded")

    exit_code = _run_finalize(
        _common_patches(tmp_path), extra={REVIEW_ENGINE: _boom}
    )
    assert exit_code == 0


def test_finalize_lint_validates_a_json_only_mission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """C1 fold (write-side-seam-matrix-tracer-01KYP3MH WP05): a mission with
    ONLY ``issue-matrix.json`` (no ``.md``) must still be linted -- the prior
    ``.md``-only ``.exists()`` precheck returned early for exactly this case,
    silently skipping the lint (dead code behind the precheck)."""
    feature_dir = _setup_mission(tmp_path, matrix=None)
    (feature_dir / "issue-matrix.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rows": {"#2223": {"verdict": "not-a-real-verdict", "evidence_ref": "x"}},
            }
        ),
        encoding="utf-8",
    )

    exit_code = _run_finalize(_common_patches(tmp_path))

    out = _clean(capsys.readouterr().out)
    assert "Advisory" in out
    assert exit_code == 0

    assert exit_code == 0
