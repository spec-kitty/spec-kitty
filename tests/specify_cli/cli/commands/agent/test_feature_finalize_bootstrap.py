"""Tests for bootstrap integration in feature.py finalize-tasks command.

Verifies that finalize-tasks calls bootstrap_canonical_state() after
dependency parsing, respects --validate-only with dry_run=True, and
includes bootstrap stats in JSON output.

WP01 additions (T009):
- test_validate_only_no_file_writes: --validate-only must not modify WP files
- test_validate_only_reports_would_modify: JSON output includes would_modify
- test_non_empty_disagreement_fails: conflicting deps → exit code 1 + diagnostic
- test_empty_parse_preserves_existing_deps: existing deps survive empty parse
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.status.bootstrap import BootstrapResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MODULE = "specify_cli.cli.commands.agent.mission"
CORE_MODULE = "specify_cli.core.mission_creation"


@pytest.fixture(autouse=True)
def _disable_saas_sync_for_finalize_bootstrap_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep these unit tests on the offline finalize-tasks path.

    ``tests/conftest.py`` enables SaaS sync globally so sync/auth tests keep
    exercising the hosted path. This module patches git, event emission, and
    bootstrap collaborators in-process; it is not testing the SaaS boundary
    preflight. Leaving the flag enabled lets a machine-local daemon owner
    record short-circuit finalize-tasks before these assertions run.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _setup_feature(tmp_path: Path, mission_slug: str = "060-test-feature") -> Path:
    """Create a minimal feature directory with spec.md, tasks.md, and WP files."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    # spec.md with at least one requirement
    spec_md = feature_dir / "spec.md"
    spec_md.write_text(
        "---\ntitle: Test Feature\n---\n\n## Requirements\n\n- FR-001: First requirement\n",
        encoding="utf-8",
    )

    # tasks.md with dependency info
    tasks_md = feature_dir / "tasks.md"
    tasks_md.write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
        encoding="utf-8",
    )

    # WP files with frontmatter
    for wp_id, refs in [("WP01", ["FR-001"]), ("WP02", ["FR-001"])]:
        wp_file = tasks_dir / f"{wp_id}-test.md"
        refs_yaml = "\n".join(f"  - {r}" for r in refs)
        wp_file.write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:\n{refs_yaml}\ndependencies: []\n---\n\n# {wp_id}\n',
            encoding="utf-8",
        )

    # meta.json for event emission
    meta = feature_dir / "meta.json"
    meta.write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")

    return feature_dir


def _make_bootstrap_result(
    total: int = 2,
    seeded: int = 2,
    existing: int = 0,
) -> BootstrapResult:
    """Create a BootstrapResult with given counts."""
    return BootstrapResult(
        total_wps=total,
        already_initialized=existing,
        newly_seeded=seeded,
        skipped=0,
    )


# Common set of patches needed to run finalize_tasks without real git/filesystem
def _common_patches(tmp_path: Path, mission_slug: str = "060-test-feature") -> dict[str, Any]:
    """Return a dict of patch targets -> mock values for finalize_tasks.

    WP02 (T027): finalize_tasks now routes git commits through
    ``commit_for_mission`` rather than calling ``safe_commit`` directly.  WP05
    (T014) removed the vestigial ``{MODULE}.safe_commit`` re-export shim, so the
    old ``{MODULE}.safe_commit`` patch (never asserted as a spy) is dropped: the
    canonical commit boundary is now
    ``specify_cli.coordination.commit_router.commit_for_mission`` which is patched
    here to prevent real git I/O in unit tests. ``ProtectionPolicy.resolve`` is
    patched in the router so it does not attempt real git operations against
    ``tmp_path``.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    _fake_commit_result = CommitRouterResult(
        status="committed",
        placement_ref="main",
        commit_hash="abc1234",
    )
    return {
        f"{MODULE}.locate_project_root": MagicMock(return_value=tmp_path),
        f"{MODULE}._find_feature_directory": MagicMock(return_value=feature_dir),
        f"{MODULE}._resolve_planning_branch": MagicMock(return_value="main"),
        f"{MODULE}._ensure_branch_checked_out": MagicMock(),
        # WP02 / T027: commit_for_mission is the canonical commit seam.
        "specify_cli.coordination.commit_router.commit_for_mission": MagicMock(
            return_value=_fake_commit_result
        ),
        f"{MODULE}.run_command": MagicMock(return_value=(0, "abc1234", "")),
        f"{MODULE}.validate_ownership": MagicMock(
            return_value=MagicMock(passed=True, warnings=[], errors=[]),
        ),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFinalizeTasksCallsBootstrap:
    """T005-a: finalize-tasks calls bootstrap_canonical_state after deps."""

    def test_bootstrap_called_after_dependency_parsing(self, tmp_path: Path) -> None:
        """Verify bootstrap_canonical_state is called during finalize-tasks."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        mock_bootstrap = MagicMock(return_value=_make_bootstrap_result())
        patches[f"{MODULE}.bootstrap_canonical_state"] = mock_bootstrap

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        mocks = {}
        for k, p in ctx_patches.items():
            mocks[k] = p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=False,
            )
        except (typer.Exit, SystemExit):
            pass  # finalize-tasks may exit
        finally:
            for p in ctx_patches.values():
                p.stop()

        mock_bootstrap.assert_called_once_with(
            tmp_path / "kitty-specs" / mission_slug,
            mission_slug,
            dry_run=False,
            # Production finalize asserts STANDARD: the seed commit is refused
            # on a protected destination, never waived (PR #1850 fix).
            capability=GuardCapability.STANDARD,
        )


class TestValidateOnlyDryRun:
    """T005-b: --validate-only calls bootstrap with dry_run=True."""

    def test_validate_only_uses_dry_run(self, tmp_path: Path) -> None:
        """Verify --validate-only passes dry_run=True to bootstrap."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        mock_bootstrap = MagicMock(return_value=_make_bootstrap_result())
        patches[f"{MODULE}.bootstrap_canonical_state"] = mock_bootstrap

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=True,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        mock_bootstrap.assert_called_once_with(
            tmp_path / "kitty-specs" / mission_slug,
            mission_slug,
            dry_run=True,
        )

    def test_validate_only_console_output_reports_bootstrap_summary(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Non-JSON validate-only output should include bootstrap dry-run stats."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result(total=2, seeded=1, existing=1))

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=False,
                validate_only=True,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        # Rich auto-highlights numerics with ANSI color codes (e.g.
        # ``\x1b[1;36m1\x1b[0m``), so the digits in the summary line are not
        # byte-contiguous with the surrounding words. Strip ANSI before the
        # substring check to pin the contract (the summary text is rendered)
        # without coupling to rich's highlighting.
        output = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
        assert "Bootstrap:" in output
        assert "1 WPs would be seeded, 1 already initialized" in output


class TestBootstrapStatsInJson:
    """T005-c: Bootstrap stats appear in JSON output."""

    def test_json_output_includes_bootstrap_stats(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify JSON output contains bootstrap key with correct counts."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        mock_bootstrap = MagicMock(return_value=_make_bootstrap_result(total=2, seeded=1, existing=1))
        patches[f"{MODULE}.bootstrap_canonical_state"] = mock_bootstrap

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=False,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        captured = capsys.readouterr()
        # Find the JSON line that contains "result"
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
                if data.get("result") == "success":
                    assert "bootstrap" in data
                    assert data["bootstrap"]["total_wps"] == 2
                    assert data["bootstrap"]["newly_seeded"] == 1
                    assert data["bootstrap"]["already_initialized"] == 1
                    return
            except json.JSONDecodeError:
                continue

        pytest.fail("No JSON output with 'result': 'success' found in captured output")

    def test_validate_only_json_includes_validation_preview(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify --validate-only JSON output contains validation.bootstrap_preview."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        mock_bootstrap = MagicMock(return_value=_make_bootstrap_result(total=3, seeded=3, existing=0))
        patches[f"{MODULE}.bootstrap_canonical_state"] = mock_bootstrap

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=True,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
                if data.get("result") == "validation_passed":
                    assert "bootstrap" not in data
                    assert "validation" in data
                    preview = data["validation"]["bootstrap_preview"]
                    assert preview["total_wps"] == 3
                    assert preview["newly_seeded"] == 3
                    assert preview["already_initialized"] == 0
                    assert data["validate_only"] is True
                    return
            except json.JSONDecodeError:
                continue

        pytest.fail("No JSON output with 'result': 'validation_passed' found")


def _setup_undeclared_fr_feature(tmp_path: Path, mission_slug: str) -> Path:
    """Like :func:`_setup_feature`, but spec.md ALSO carries a "Functional
    Requirements" section written as bare, unbulleted, unbolded sentences
    (FR-001, FR-002) -- the #3394 review F1 declared-shape-miss scenario.
    ``parse_requirement_ids_from_spec_md`` never counts FR-001/FR-002 (no
    recognized declared shape), so they are invisible to the coverage gate.

    A SEPARATE, properly-declared FR-100 exists (table row) and is the only
    id both WP files reference -- reproducing the review's exact complaint:
    finalize-tasks reaches the SUCCESS path (``unmapped_functional_requirements
    == []``) even though the spec's own FR-001/FR-002 were never counted,
    because ``missing_requirement_refs_wps``/``unknown_requirement_refs``
    would otherwise hard-fail for unrelated reasons if the WPs referenced
    nothing, or referenced the undeclared ids directly.
    """
    feature_dir = _setup_feature(tmp_path, mission_slug)
    (feature_dir / "spec.md").write_text(
        "---\ntitle: Test Feature\n---\n\n"
        "## Functional Requirements\n\nFR-001 must hold. FR-002 too.\n\n"
        "## Declared Functional Requirements\n\n"
        "| ID | Requirement |\n|----|-------------|\n| FR-100 | The one WPs map to. |\n",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02"):
        wp_file = feature_dir / "tasks" / f"{wp_id}-test.md"
        wp_file.write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:\n  - FR-100\ndependencies: []\n---\n\n# {wp_id}\n',
            encoding="utf-8",
        )
    return feature_dir


class TestRequirementExtractionWarningsInJson:
    """#3394 review F1: finalize-tasks' non-blocking ``requirement_extraction_
    warnings`` signal for a Requirements section matching none of the four
    recognized declared shapes at all (the "reports success while measuring
    nothing" gap the review flagged for a WHOLLY-undeclared section).

    RE-PINNED (operator ruling 2026-08-14; same DIRECTIVE_041 conflict as
    ``1b5b86e0f``'s spec-kitty-next re-pin): this class used to ALSO pin the
    "mixed declared + bare-prose" shape (a Requirements section that
    correctly declares SOME ids while writing OTHERS as bare prose) as
    non-blocking. #3396 exists specifically to supersede that advisory-only
    decision for the mixed shape -- see
    ``test_bare_sentence_frs_now_block_finalize_tasks_per_3396`` below.
    """

    def test_bare_sentence_frs_now_block_finalize_tasks_per_3396(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """RE-PINNED (operator ruling 2026-08-14, same conflict as ``1b5b86e0f``'s
        spec-kitty-next re-pin): the F4 finding's own repro fixture (bare-prose
        FR-001/FR-002 alongside a properly DECLARED table-row FR-100 that both
        WP01/WP02 map to) IS #3396's own target repro -- the mission's whole
        reason to exist (Story 1 AC1/AC2). Under #3395's fix this shape reached
        finalize-tasks' SUCCESS path with only the non-blocking
        ``requirement_extraction_warnings`` entry below (formerly asserted by
        this test under its old name,
        ``test_bare_sentence_frs_surface_a_non_blocking_warning_on_success``).
        #3396 (WP06) wires ``find_bare_prose_requirement_ids`` into
        ``_validate_requirement_mapping``, so this exact shape now BLOCKS
        (exit code 1), naming FR-001/FR-002 explicitly in the distinct
        ``bare_prose_requirement_ids`` field -- DIRECTIVE_041: the product
        decision this test pins deliberately changed, so the old
        non-blocking assertion was stale, not the new wiring.
        """
        mission_slug = "060-test-feature"
        _setup_undeclared_fr_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        exit_code = 0
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
        except typer.Exit as exc:
            exit_code = exc.exit_code if exc.exit_code is not None else 1
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
        finally:
            for p in ctx_patches.values():
                p.stop()

        assert exit_code == 1, "#3396 (WP06) supersedes #3395: this mixed shape must now block"

        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "bare_prose_requirement_ids" in data:
                assert data["bare_prose_requirement_ids"] == ["FR-001", "FR-002"]
                assert data["unmapped_functional_requirements"] == []
                return
        pytest.fail("No JSON output carrying 'bare_prose_requirement_ids' found in captured output")


# ---------------------------------------------------------------------------
# WP01 regression tests (T009)
# ---------------------------------------------------------------------------


def _setup_feature_with_existing_deps(
    tmp_path: Path,
    mission_slug: str = "060-test-feature",
    wp02_existing_deps: list[str] | None = None,
) -> Path:
    """Create feature where WP02 already has frontmatter dependencies."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "spec.md").write_text(
        "---\ntitle: Test Feature\n---\n\n## Requirements\n\n- FR-001: First requirement\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")

    for wp_id, refs in [("WP01", ["FR-001"]), ("WP02", ["FR-001"])]:
        dep_lines = ""
        if wp_id == "WP02" and wp02_existing_deps is not None:
            dep_items = "\n".join(f"  - {d}" for d in wp02_existing_deps)
            dep_lines = f"dependencies:\n{dep_items}\n" if dep_items else "dependencies: []\n"
        else:
            dep_lines = "dependencies: []\n"
        refs_yaml = "\n".join(f"  - {r}" for r in refs)
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:\n{refs_yaml}\n{dep_lines}---\n\n# {wp_id}\n',
            encoding="utf-8",
        )

    return feature_dir


class TestWP01Regressions:
    """WP01 regression tests (T009)."""

    def test_validate_only_no_file_writes(self, tmp_path: Path) -> None:
        """--validate-only must not modify WP files (files byte-identical before/after)."""
        mission_slug = "060-test-feature"
        feature_dir = _setup_feature(tmp_path, mission_slug)
        tasks_dir = feature_dir / "tasks"

        # Capture checksums before
        checksums_before = {f.name: f.read_bytes() for f in tasks_dir.glob("WP*.md")}

        patches = _common_patches(tmp_path, mission_slug)
        mock_bootstrap = MagicMock(return_value=_make_bootstrap_result())
        patches[f"{MODULE}.bootstrap_canonical_state"] = mock_bootstrap

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=True)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        # Capture checksums after — must be identical
        checksums_after = {f.name: f.read_bytes() for f in tasks_dir.glob("WP*.md")}
        assert checksums_before == checksums_after, "validate_only=True must not modify any WP files on disk"

    def test_validate_only_reports_would_modify(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """--validate-only JSON output must include would_modify field."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=True)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
                if data.get("result") == "validation_passed":
                    assert "would_modify" in data, "JSON must include would_modify"
                    assert "would_preserve" in data, "JSON must include would_preserve"
                    assert "unchanged" in data, "JSON must include unchanged"
                    assert "bootstrap" not in data
                    assert "validation" in data
                    assert "bootstrap_preview" in data["validation"]
                    assert data["validate_only"] is True
                    return
            except json.JSONDecodeError:
                continue
        pytest.fail("No JSON output with 'result': 'validation_passed' found")


# ---------------------------------------------------------------------------
# Finding 6: finalize-tasks scaffolds acceptance-matrix.json for lane-based
# missions (those that produce lanes.json).
# ---------------------------------------------------------------------------


def _setup_lane_based_feature(tmp_path: Path, mission_slug: str = "061-lane-feature") -> Path:
    """Create a feature whose WPs have disjoint owned_files so lanes compute."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "spec.md").write_text(
        "---\ntitle: Lane Feature\n---\n\n## Requirements\n\n- FR-001: First requirement\n- FR-002: Second requirement\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nNo dependencies.\n",
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "alpha.py").write_text("# alpha\n", encoding="utf-8")
    (src_dir / "beta.py").write_text("# beta\n", encoding="utf-8")

    # Two independent WPs owning disjoint files → compute_lanes yields lanes.
    for wp_id, owned, refs in [
        ("WP01", ["src/alpha.py"], ["FR-001"]),
        ("WP02", ["src/beta.py"], ["FR-002"]),
    ]:
        owned_yaml = "\n".join(f"  - {o}" for o in owned)
        refs_yaml = "\n".join(f"  - {r}" for r in refs)
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\n'
            f"requirement_refs:\n{refs_yaml}\n"
            f"owned_files:\n{owned_yaml}\n"
            f"dependencies: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )

    return feature_dir


class TestFinalizeScaffoldsAcceptanceMatrix:
    """Finding 6: lane-based finalize-tasks creates acceptance-matrix.json."""

    def test_lane_based_finalize_creates_valid_matrix(self, tmp_path: Path) -> None:
        mission_slug = "061-lane-feature"
        feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        # Lane-based: lanes.json was written, so the matrix must exist.
        assert (feature_dir / "lanes.json").exists(), "test setup must produce a lane-based feature"

        from specify_cli.acceptance.matrix import read_acceptance_matrix

        matrix_path = feature_dir / "acceptance-matrix.json"
        assert matrix_path.exists(), "lane-based finalize must scaffold acceptance-matrix.json"

        # Schema-valid + derived from functional requirements.
        matrix = read_acceptance_matrix(feature_dir)
        assert matrix is not None
        assert matrix.mission_slug == mission_slug
        criterion_ids = {c.criterion_id for c in matrix.criteria}
        assert {"FR-001", "FR-002"} <= criterion_ids

    def test_validate_only_does_not_scaffold_matrix(self, tmp_path: Path) -> None:
        mission_slug = "061-lane-feature"
        feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=True)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        assert not (feature_dir / "acceptance-matrix.json").exists(), "validate-only must not write the acceptance-matrix scaffold"

    def test_explicit_frontmatter_dependencies_beat_tasks_md_parser(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Non-empty WP frontmatter deps are authoritative over tasks.md prose.

        #4135 reclassified a present-but-*empty* ``dependencies: []`` as a
        map-requirements serialization artifact (covered by
        test_issue_4135_empty_frontmatter_deps_fallback.py), so TIER-2
        authority here is exercised with a non-empty disagreement: frontmatter
        declares WP02 → WP01 while tasks.md declares no dependency for WP02.
        """
        mission_slug = "060-test-feature"
        # WP02 frontmatter says [WP01] but tasks.md says nothing.
        feature_dir = _setup_feature_with_existing_deps(
            tmp_path,
            mission_slug,
            wp02_existing_deps=["WP01"],
        )
        (feature_dir / "tasks.md").write_text(
            "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nSome content, no dep line.\n",
            encoding="utf-8",
        )

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
        finally:
            for p in ctx_patches.values():
                p.stop()

        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
                if data.get("result") == "success":
                    assert data["dependencies_parsed"]["WP02"] == ["WP01"]
                    return
            except json.JSONDecodeError:
                continue
        pytest.fail("No JSON success payload found")

    def test_empty_frontmatter_artifact_lets_tasks_md_cycle_surface(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A cyclic tasks.md chain is surfaced, not masked, behind empty frontmatter.

        Pre-#4135, a present-but-empty ``dependencies: []`` (the map-requirements
        serialization artifact) was treated as an authoritative dependency-free
        declaration and silently discarded the parsed back-edges. #4135
        reclassifies the empty list as absent, so the cyclic tasks.md chain now
        resolves and the circular-dependency gate fires visibly instead of the
        chain being silently dropped. An operator who genuinely wants a
        dependency-free WP against tasks.md prose declares it in wps.yaml
        (TIER-1, ``dependencies_are_explicit``), which still wins.
        """
        mission_slug = "060-test-feature"
        feature_dir = _setup_feature(tmp_path, mission_slug)
        (feature_dir / "tasks.md").write_text(
            "# Tasks\n\n## WP01\n\n**Dependencies**: WP02\n\n## WP02\n\n**Dependencies**: WP01\n",
            encoding="utf-8",
        )

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        exit_code: int | None = None
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=True)
        except (typer.Exit, SystemExit) as exc:
            exit_code = exc.exit_code if isinstance(exc, typer.Exit) else exc.code
        finally:
            for p in ctx_patches.values():
                p.stop()

        assert exit_code == 1, "A cyclic dependency chain must exit with code 1"
        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
                if "Circular dependencies detected" in str(data.get("error", "")):
                    assert data["cycles"]
                    return
            except json.JSONDecodeError:
                continue
        pytest.fail("No circular-dependency error payload found")

    def test_empty_parse_preserves_existing_deps(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """When parser finds no deps but frontmatter has deps, preserve existing."""
        mission_slug = "060-test-feature"
        # tasks.md declares no dependencies for WP02; frontmatter has [WP01]
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        (feature_dir / "spec.md").write_text(
            "---\ntitle: Test Feature\n---\n\n## Requirements\n\n- FR-001: First requirement\n",
            encoding="utf-8",
        )
        # tasks.md has no dependency declaration for WP02
        (feature_dir / "tasks.md").write_text(
            "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nSome content, no dep line.\n",
            encoding="utf-8",
        )
        (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")

        for wp_id, refs in [("WP01", ["FR-001"]), ("WP02", ["FR-001"])]:
            dep_line = "dependencies: []\n" if wp_id == "WP01" else "dependencies:\n  - WP01\n"
            refs_yaml = "\n".join(f"  - {r}" for r in refs)
            (tasks_dir / f"{wp_id}-test.md").write_text(
                f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:\n{refs_yaml}\n{dep_line}---\n\n# {wp_id}\n',
                encoding="utf-8",
            )

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        # WP02 file should still have WP01 in its dependencies
        wp02_file = tasks_dir / "WP02-test.md"
        assert wp02_file.exists()
        content = wp02_file.read_text(encoding="utf-8")
        assert "WP01" in content, "Existing WP01 dependency must be preserved when parser finds nothing"

    def test_json_reports_modified_unchanged_preserved(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Success JSON output must include modified_wps, unchanged_wps, preserved_wps."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
                if data.get("result") == "success":
                    assert "modified_wps" in data, "JSON must include modified_wps"
                    assert "unchanged_wps" in data, "JSON must include unchanged_wps"
                    assert "preserved_wps" in data, "JSON must include preserved_wps"
                    assert isinstance(data["modified_wps"], list)
                    assert isinstance(data["unchanged_wps"], list)
                    assert isinstance(data["preserved_wps"], list)
                    return
            except json.JSONDecodeError:
                continue
        pytest.fail("No JSON output with 'result': 'success' found")

    def test_finalize_rejects_incomplete_tasks_md_wp_coverage(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Fail loudly when tasks.md headings do not cover all WP files."""
        mission_slug = "060-test-feature"
        feature_dir = _setup_feature(tmp_path, mission_slug)
        (feature_dir / "tasks.md").write_text(
            "# Tasks\n\n## Package 1\n\nNo dependencies.\n\n## Package 2\n\nDepends on WP01.\n",
            encoding="utf-8",
        )

        patches = _common_patches(tmp_path, mission_slug)
        mock_bootstrap = MagicMock(return_value=_make_bootstrap_result())
        patches[f"{MODULE}.bootstrap_canonical_state"] = mock_bootstrap

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            with pytest.raises(typer.Exit):
                finalize_tasks(
                    feature=mission_slug,
                    json_output=True,
                    validate_only=False,
                )
        finally:
            for p in ctx_patches.values():
                p.stop()

        mock_bootstrap.assert_not_called()
        captured = capsys.readouterr()
        for line in captured.out.strip().splitlines():
            try:
                data = json.loads(line)
                assert data["missing_wp_sections"] == ["WP01", "WP02"]
                assert "coverage is incomplete" in data["error"]
                return
            except json.JSONDecodeError:
                continue
        pytest.fail("No JSON error payload found for incomplete WP coverage")

    def test_finalize_commits_status_but_excludes_dossier_snapshot(self, tmp_path: Path) -> None:
        """Commit set must include bootstrap status artifacts but NEVER the dossier snapshot.

        WP02 (T027): commits now route through ``commit_for_mission``.  The spy
        is attached to that boundary (capturing the ``files`` kwarg tuple) rather
        than to the old ``safe_commit`` direct call.

        FIX-M2-05: this test previously asserted the OPPOSITE — that
        ``snapshot-latest.json`` WAS in the committed set. That assertion
        directly violated the already-ratified ownership contract
        (``contracts/dossier-snapshot-ownership.md``, D1, mission
        ``charter-e2e-827-followups-01KQAJA0`` / #845): "save_snapshot() ...
        No staging, no committing, no special branch interaction. The file is
        just a file." Committing it here made the file tracked on every
        branch/worktree the target commit touched, and every later
        fire-and-forget dossier-sync write then left that worktree locally
        modified/uncommitted — exactly the drift that blocked
        ``git/ref_advance.py``'s merge-time dirty-worktree resync (#1826) on
        a mission's coordination worktree during ``spec-kitty merge``. The
        snapshot write itself is still exercised below to prove the fix is
        "stop committing it", not "stop writing it". (The sync-side trigger that
        used to perform the write retired with the sync transport, so the harness
        writes the snapshot directly.)
        """
        mission_slug = "060-test-feature"
        feature_dir = _setup_feature(tmp_path, mission_slug)
        captured_files: list[Path] = []

        def _bootstrap_side_effect(
            feature_path: Path,
            slug: str,
            dry_run: bool,
            capability: GuardCapability = GuardCapability.STANDARD,
        ) -> BootstrapResult:
            assert feature_path == feature_dir
            assert slug == mission_slug
            assert dry_run is False
            # Production finalize asserts STANDARD (PR #1850 fix).
            assert capability is GuardCapability.STANDARD
            (feature_path / "status.events.jsonl").write_text('{"event":"seeded"}\n', encoding="utf-8")
            (feature_path / "status.json").write_text("{}", encoding="utf-8")
            _write_snapshot(feature_path)
            return _make_bootstrap_result()

        def _commit_for_mission_spy(**kwargs: object) -> CommitRouterResult:
            nonlocal captured_files
            # ``files`` is a tuple[Path, ...] keyword arg.
            captured_files = list(kwargs.get("files", ()))
            return CommitRouterResult(
                status="committed",
                placement_ref="main",
                commit_hash="abc1234",
            )


        def _write_snapshot(feature_path: Path) -> None:
            snapshot_path = (
                feature_path / ".kittify" / "dossiers" / mission_slug / "snapshot-latest.json"
            )
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text("{}", encoding="utf-8")

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(side_effect=_bootstrap_side_effect)
        # Override the common commit_for_mission mock with the spy.
        patches["specify_cli.coordination.commit_router.commit_for_mission"] = _commit_for_mission_spy

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=False,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        committed_paths = {path.relative_to(tmp_path).as_posix() for path in captured_files}
        assert "kitty-specs/060-test-feature/status.events.jsonl" in committed_paths
        assert "kitty-specs/060-test-feature/status.json" in committed_paths
        # FIX-M2-05 / D1: the dossier snapshot must NEVER be a commit candidate.
        assert "kitty-specs/060-test-feature/.kittify/dossiers/060-test-feature/snapshot-latest.json" not in committed_paths
        # The snapshot write itself is unaffected — it still lands on disk,
        # just outside git's view (D1's "just a file" contract).
        snapshot_path = tmp_path / "kitty-specs/060-test-feature/.kittify/dossiers/060-test-feature/snapshot-latest.json"
        assert snapshot_path.exists(), "save_snapshot's write path must be unchanged by the commit-candidate fix"


class TestValidateOnlyUsesInMemoryOwnership:
    """Regression test for validate-only ownership inference and manifest reuse."""

    def _setup_feature_no_ownership(self, tmp_path: Path, mission_slug: str = "060-test-feature") -> Path:
        """Create WP files WITHOUT ownership fields."""
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        spec_md = feature_dir / "spec.md"
        spec_md.write_text(
            "---\ntitle: Test Feature\n---\n\n## Requirements\n\n- FR-001: First\n",
            encoding="utf-8",
        )

        tasks_md = feature_dir / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
            encoding="utf-8",
        )

        for wp_id, refs in [("WP01", ["FR-001"]), ("WP02", ["FR-001"])]:
            wp_file = tasks_dir / f"{wp_id}-test.md"
            refs_yaml = "\n".join(f"  - {r}" for r in refs)
            wp_file.write_text(
                f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\n'
                f"requirement_refs:\n{refs_yaml}\ndependencies: []\n---\n\n# {wp_id}\n"
                f"\n## Files\n\n- src/specify_cli/foo.py\n",
                encoding="utf-8",
            )

        meta = feature_dir / "meta.json"
        meta.write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")

        return feature_dir

    def test_validate_only_infers_ownership_in_memory(self, tmp_path: Path) -> None:
        """validate_ownership must receive non-empty manifests in validate-only mode."""
        mission_slug = "060-test-feature"
        self._setup_feature_no_ownership(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result(total=2, seeded=0, existing=2))
        mock_validate = MagicMock(return_value=MagicMock(passed=True, warnings=[], errors=[]))
        patches[f"{MODULE}.validate_ownership"] = mock_validate

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=True,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        mock_validate.assert_called_once()
        actual_manifests = mock_validate.call_args[0][0]
        assert len(actual_manifests) > 0, "validate_ownership received empty wp_manifests in validate-only mode"

    def test_validate_only_no_disk_mutation_even_with_ownership_inference(self, tmp_path: Path) -> None:
        """Ownership inference in validate-only mode must not mutate WP files."""
        mission_slug = "060-test-feature"
        self._setup_feature_no_ownership(tmp_path, mission_slug)
        tasks_dir = tmp_path / "kitty-specs" / mission_slug / "tasks"

        wp_snapshots: dict[str, bytes] = {}
        for wp_file in sorted(tasks_dir.glob("WP*.md")):
            wp_snapshots[wp_file.name] = wp_file.read_bytes()

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result(total=2, seeded=0, existing=2))

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=True,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        for wp_name, before_bytes in wp_snapshots.items():
            after_bytes = (tasks_dir / wp_name).read_bytes()
            assert after_bytes == before_bytes, f"{wp_name} was modified by --validate-only even though ownership inference should only operate in memory"


# ---------------------------------------------------------------------------
# Unit B: Typed frontmatter migration tests for finalize_tasks()
# ---------------------------------------------------------------------------


class TestTypedFrontmatterMigration:
    """Verify finalize_tasks() uses WPMetadata typed reads instead of raw dicts.

    These tests validate the consumer migration from raw ``read_frontmatter()``
    to ``read_wp_frontmatter()`` and the builder pattern for mutations.
    """

    def test_finalize_reads_wp_via_typed_reader(self, tmp_path: Path) -> None:
        """finalize_tasks() must use read_wp_frontmatter, not raw read_frontmatter."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        # Spy on read_wp_frontmatter to verify it is called
        with patch(
            f"{MODULE}.read_wp_frontmatter",
            wraps=__import__("specify_cli.status.wp_metadata", fromlist=["read_wp_frontmatter"]).read_wp_frontmatter,
        ) as spy_typed:
            try:
                finalize_tasks(
                    feature=mission_slug,
                    json_output=True,
                    validate_only=False,
                )
            except (typer.Exit, SystemExit):
                pass
            finally:
                for p in ctx_patches.values():
                    p.stop()

            assert spy_typed.call_count >= 2, f"Expected read_wp_frontmatter to be called at least twice (pre-loop + main loop), got {spy_typed.call_count}"

    def test_finalize_does_not_call_raw_read_frontmatter(self, tmp_path: Path) -> None:
        """After migration, finalize_tasks must NOT use raw read_frontmatter for WP files."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        # Spy on the frontmatter module's read_frontmatter to verify it is NOT called
        # by finalize_tasks (which should use read_wp_frontmatter instead)
        import specify_cli.frontmatter as _fm_mod

        with patch.object(_fm_mod, "read_frontmatter", wraps=_fm_mod.read_frontmatter) as spy_raw:
            try:
                finalize_tasks(
                    feature=mission_slug,
                    json_output=True,
                    validate_only=False,
                )
            except (typer.Exit, SystemExit):
                pass
            finally:
                for p in ctx_patches.values():
                    p.stop()

            # read_wp_frontmatter internally calls FrontmatterManager.read(), not
            # the module-level read_frontmatter function.  So spy_raw should be 0.
            assert spy_raw.call_count == 0, f"Expected read_frontmatter to not be called after migration, but it was called {spy_raw.call_count} time(s)"

    def test_written_frontmatter_validates_as_wp_metadata(self, tmp_path: Path) -> None:
        """Frontmatter written by finalize_tasks must round-trip through WPMetadata."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=False,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        # After finalize, every WP file's frontmatter must be valid WPMetadata
        from specify_cli.status.wp_metadata import read_wp_frontmatter

        tasks_dir = tmp_path / "kitty-specs" / mission_slug / "tasks"
        for wp_file in sorted(tasks_dir.glob("WP*.md")):
            wp_meta, _body = read_wp_frontmatter(wp_file)
            assert wp_meta.work_package_id is not None
            assert wp_meta.display_title != ""

    def test_finalize_updates_branch_fields_via_typed_api(self, tmp_path: Path) -> None:
        """Branch contract fields must be set correctly after finalize_tasks."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=False,
            )
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        from specify_cli.status.wp_metadata import read_wp_frontmatter

        tasks_dir = tmp_path / "kitty-specs" / mission_slug / "tasks"
        for wp_file in sorted(tasks_dir.glob("WP*.md")):
            wp_meta, _ = read_wp_frontmatter(wp_file)
            # finalize_tasks sets these branch fields
            assert wp_meta.planning_base_branch == "main"
            assert wp_meta.merge_target_branch == "main"
            assert wp_meta.branch_strategy is not None
            assert "Planning artifacts" in wp_meta.branch_strategy

    def test_ownership_manifest_receives_typed_metadata(self, tmp_path: Path) -> None:
        """OwnershipManifest.from_frontmatter() must receive WPMetadata, not raw dict."""
        mission_slug = "060-test-feature"
        _setup_feature(tmp_path, mission_slug)

        # Add ownership fields so the post-loop validation path is exercised
        tasks_dir = tmp_path / "kitty-specs" / mission_slug / "tasks"
        for wp_file in sorted(tasks_dir.glob("WP*.md")):
            content = wp_file.read_text(encoding="utf-8")
            # Insert ownership fields before the closing ---
            content = content.replace(
                "dependencies: []",
                'dependencies: []\nexecution_mode: "code_change"\nowned_files:\n  - "src/**"',
            )
            wp_file.write_text(content, encoding="utf-8")

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks
        from specify_cli.ownership.models import OwnershipManifest
        from specify_cli.status.wp_metadata import WPMetadata

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()

        # Spy on OwnershipManifest.from_frontmatter to check arg types
        original_from_fm = OwnershipManifest.from_frontmatter
        received_args: list[object] = []

        def spy_from_frontmatter(data: object) -> object:
            received_args.append(data)
            return original_from_fm(data)

        with patch.object(OwnershipManifest, "from_frontmatter", staticmethod(spy_from_frontmatter)):
            try:
                finalize_tasks(
                    feature=mission_slug,
                    json_output=True,
                    validate_only=False,
                )
            except (typer.Exit, SystemExit):
                pass
            finally:
                for p in ctx_patches.values():
                    p.stop()

        assert len(received_args) >= 1, "OwnershipManifest.from_frontmatter was never called"
        for arg in received_args:
            assert isinstance(arg, WPMetadata), f"Expected WPMetadata instance, got {type(arg).__name__}"


# ---------------------------------------------------------------------------
# #3941: legacy string-form dependencies frontmatter is normalized on write
# ---------------------------------------------------------------------------


def _setup_feature_with_string_form_deps(tmp_path: Path, mission_slug: str = "060-test-feature") -> Path:
    """Create a feature whose WP files carry legacy string-form dependencies.

    WP01 stores ``dependencies: "[]"`` and WP02 the bare scalar
    ``dependencies: WP01`` — two of the three legacy forms observed in F-55
    (#3941). ``WPMetadata`` coerces both to the canonical list at read time,
    which is exactly the shape that used to slip past finalize-tasks'
    change detector.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "spec.md").write_text(
        "---\ntitle: Test Feature\n---\n\n## Requirements\n\n- FR-001: First requirement\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")

    for wp_id, dep_line in [("WP01", 'dependencies: "[]"'), ("WP02", "dependencies: WP01")]:
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:\n  - FR-001\n{dep_line}\n---\n\n# {wp_id}\n',
            encoding="utf-8",
        )

    return feature_dir


class TestStringFormDependenciesNormalization:
    """finalize-tasks normalizes string-form dependencies to the canonical list (#3941)."""

    def test_string_form_dependencies_normalized_on_disk(self, tmp_path: Path) -> None:
        """A real run rewrites the string forms to canonical list frontmatter."""
        mission_slug = "060-test-feature"
        feature_dir = _setup_feature_with_string_form_deps(tmp_path, mission_slug)

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        from specify_cli.frontmatter import FrontmatterManager

        manager = FrontmatterManager()
        tasks_dir = feature_dir / "tasks"
        raw_wp01, _ = manager.read(tasks_dir / "WP01-test.md")
        raw_wp02, _ = manager.read(tasks_dir / "WP02-test.md")
        # Only the canonical list form reaches the tree — the raw YAML value
        # must now be a list, not a string, with the coerced semantics intact.
        assert raw_wp01["dependencies"] == []
        assert isinstance(raw_wp01["dependencies"], list)
        assert raw_wp02["dependencies"] == ["WP01"]
        assert isinstance(raw_wp02["dependencies"], list)

    def test_string_form_dependencies_validate_only_previews_without_writing(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--validate-only reports the normalization as would_modify, disk untouched."""
        mission_slug = "060-test-feature"
        feature_dir = _setup_feature_with_string_form_deps(tmp_path, mission_slug)
        tasks_dir = feature_dir / "tasks"
        before = {f.name: f.read_bytes() for f in tasks_dir.glob("WP*.md")}

        patches = _common_patches(tmp_path, mission_slug)
        patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())

        from specify_cli.cli.commands.agent.mission import finalize_tasks

        ctx_patches = {k: patch(k, v) for k, v in patches.items()}
        for p in ctx_patches.values():
            p.start()
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=True)
        except (typer.Exit, SystemExit):
            pass
        finally:
            for p in ctx_patches.values():
                p.stop()

        assert {f.name: f.read_bytes() for f in tasks_dir.glob("WP*.md")} == before

        normalized = set()
        for line in capsys.readouterr().out.strip().splitlines():
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            for entry in data.get("would_modify", []):
                if "dependencies" in entry.get("changes", {}):
                    normalized.add(entry["wp_id"])
        assert normalized == {"WP01", "WP02"}, "both string-form WPs must preview as dependencies changes"


# ---------------------------------------------------------------------------
# Acceptance: ownership overlap fails regardless of lane / dependency hierarchy
#
# Invariant under test (#1753 follow-up): the ONLY way two WPs may claim the
# same code is by declaring the broadly-overlapping one `scope: codebase-wide`.
# Being in different lanes (independent) OR linked in a dependency hierarchy
# (linearized into one lane) does NOT exempt narrow WPs from the overlap check.
# ---------------------------------------------------------------------------


def _write_overlap_feature(
    tmp_path: Path,
    wps: list[tuple[str, list[str], str, list[str], str | None]],
    tasks_md: str,
    mission_slug: str = "060-test-feature",
) -> None:
    """Write a feature whose WP files carry explicit (overlapping) ownership.

    Each WP tuple is ``(wp_id, owned_files, authoritative_surface, deps, scope)``.
    All ownership fields are explicit so finalize does not infer/clobber them.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "---\ntitle: Test Feature\n---\n\n## Requirements\n\n- FR-001: First requirement\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")
    for wp_id, owned, surface, deps, scope in wps:
        lines = [
            "---",
            f'work_package_id: "{wp_id}"',
            f'title: "Test {wp_id}"',
            "requirement_refs:",
            "  - FR-001",
            "execution_mode: code_change",
            "owned_files:",
            *[f"  - {p}" for p in owned],
            f'authoritative_surface: "{surface}"',
        ]
        if deps:
            lines.append("dependencies:")
            lines.extend(f"  - {d}" for d in deps)
        else:
            lines.append("dependencies: []")
        if scope is not None:
            lines.append(f'scope: "{scope}"')
        lines.extend(["---", "", f"# {wp_id}", ""])
        (tasks_dir / f"{wp_id}-test.md").write_text("\n".join(lines), encoding="utf-8")


def _run_finalize_validate_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mission_slug: str = "060-test-feature",
) -> list[dict[str, object]]:
    """Run finalize-tasks --validate-only with the REAL ownership validator."""
    patches = _common_patches(tmp_path, mission_slug)
    del patches[f"{MODULE}.validate_ownership"]  # exercise the real validator
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    started = [patch(target, value) for target, value in patches.items()]
    for p in started:
        p.start()
    try:
        finalize_tasks(feature=mission_slug, json_output=True, validate_only=True)
    except (typer.Exit, SystemExit):
        pass
    finally:
        for p in started:
            p.stop()

    results: list[dict[str, object]] = []
    for line in capsys.readouterr().out.strip().splitlines():
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


class TestOwnershipOverlapAcceptance:
    """Overlap fails for narrow WPs regardless of lane/dependency structure."""

    def test_independent_wps_overlap_fails(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Two independent (different-lane) narrow WPs on the same files fail."""
        _write_overlap_feature(
            tmp_path,
            wps=[
                ("WP01", ["src/foo/**"], "src/foo/", [], None),
                ("WP02", ["src/foo/**"], "src/foo/", [], None),
            ],
            tasks_md="# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nNo dependencies.\n",
        )
        results = _run_finalize_validate_only(tmp_path, capsys)
        failures = [r for r in results if r.get("error") == "Ownership validation failed"]
        assert failures, f"expected ownership failure, got {results}"
        errors = failures[0]["ownership_errors"]
        assert isinstance(errors, list)
        assert any("WP01" in e and "WP02" in e for e in errors)

    def test_dependent_wps_overlap_collapses_into_one_lane(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """WP02→WP01 dependency makes overlap legitimate: it collapses, not fails.

        Contract pinned by #2087/#2088 ("make ownership overlap lane-aware",
        ``ownership/validation.py`` ``validate_no_overlap``): two WPs joined by a
        directed dependency path own the same files legitimately because their
        execution is forced into a sequential order. The no-overlap guard targets
        *parallel* (dependency-unordered) WPs only — see ``test_independent_wps_
        overlap_fails`` for the failing counterpart. Rather than erroring, the
        dependent overlapping pair is collapsed into a single lane and validation
        passes. This test keeps teeth by asserting the collapse is *recorded*
        (a ``write_scope_overlap`` event), not silently dropped.
        """
        _write_overlap_feature(
            tmp_path,
            wps=[
                ("WP01", ["src/foo/**"], "src/foo/", [], None),
                ("WP02", ["src/foo/**"], "src/foo/", ["WP01"], None),
            ],
            tasks_md="# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
        )
        results = _run_finalize_validate_only(tmp_path, capsys)
        assert not [r for r in results if r.get("error") == "Ownership validation failed"], (
            f"dependency-ordered overlap is legitimate and must NOT fail ownership validation; got {results}"
        )
        passed = [r for r in results if r.get("result") == "validation_passed"]
        assert passed, f"expected validation_passed for dependency-ordered overlap; got {results}"
        validation = passed[0].get("validation")
        assert isinstance(validation, dict)
        lanes_preview = validation.get("lanes_preview")
        assert isinstance(lanes_preview, dict)
        collapse_report = lanes_preview.get("collapse_report")
        assert isinstance(collapse_report, dict)
        events = collapse_report.get("events")
        assert isinstance(events, list)
        assert any(isinstance(e, dict) and e.get("rule") == "write_scope_overlap" for e in events), (
            f"dependent overlap must be recorded as a write_scope_overlap collapse, not silently dropped; got {results}"
        )

    def test_codebase_wide_is_the_only_exemption(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A codebase-wide WP overlapping a narrow WP passes (end-to-end #1753)."""
        # Create the literal-path file so the glob-match validator doesn't
        # raise a hard error for a non-existent path (FR-006 / WP04).
        bar_py = tmp_path / "src" / "foo" / "bar.py"
        bar_py.parent.mkdir(parents=True, exist_ok=True)
        bar_py.write_text("# placeholder\n", encoding="utf-8")

        _write_overlap_feature(
            tmp_path,
            wps=[
                ("WP01", ["src/**"], "src/", [], "codebase-wide"),
                ("WP02", ["src/foo/bar.py"], "src/foo/bar.py", ["WP01"], None),
            ],
            tasks_md="# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
        )
        results = _run_finalize_validate_only(tmp_path, capsys)
        assert not [r for r in results if r.get("error") == "Ownership validation failed"], f"codebase-wide WP must be exempt from overlap; got {results}"
        assert any(r.get("result") == "validation_passed" for r in results), f"expected validation_passed; got {results}"
