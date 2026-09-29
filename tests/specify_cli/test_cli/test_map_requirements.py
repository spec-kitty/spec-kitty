"""Tests for the map-requirements command and finalize-tasks integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as feature_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.frontmatter import read_frontmatter

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()

SPEC_CONTENT = """\
# Spec
## Functional Requirements
| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement | Done | proposed |
| FR-002 | Second requirement | Done | proposed |
| FR-003 | Third requirement | Done | proposed |

## Non-Functional Requirements
| ID | Requirement |
| --- | --- |
| NFR-001 | Performance |
"""


@pytest.fixture(autouse=True)
def _bypass_protected_branch_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """These unit tests exercise mapping semantics on minimal main-branch fixtures.

    The documented operator escape hatch is the ONE sanctioned waiver for
    fixtures committing on a protected branch (SPEC_KITTY_TEST_MODE no longer
    waives the pre-check — PR #1850 guard-bypass fix).
    """
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _setup_feature(tmp_path: Path, *, wp_ids: list[str] | None = None) -> Path:
    """Create a minimal feature directory with spec.md and WP files."""
    feature_dir = tmp_path / "kitty-specs" / "001-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "spec.md").write_text(SPEC_CONTENT, encoding="utf-8")

    for wp_id in (wp_ids or ["WP01", "WP02"]):
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f"---\nwork_package_id: \"{wp_id}\"\ntitle: \"{wp_id}\"\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )

    return feature_dir


def _read_wp_refs(feature_dir: Path, wp_id: str) -> list[str]:
    """Read requirement_refs from a WP file's frontmatter."""
    tasks_dir = feature_dir / "tasks"
    wp_file = next(tasks_dir.glob(f"{wp_id}*.md"))
    frontmatter, _ = read_frontmatter(wp_file)
    return frontmatter.get("requirement_refs", [])


class TestMapRequirementsIndividual:
    """Tests for individual mode (--wp + --refs)."""

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_writes_to_frontmatter(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)
        # rc3 M5 (FR-002/FR-003): resolve_mission_identity no longer defaults a
        # typeless/absent meta.json to "software-dev" -- give the fixture an
        # explicit canonical mission_type so the identity payload assertion
        # below exercises a real software-dev mission, not the neutral case.
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "software-dev", "slug": "001-test"}),
            encoding="utf-8",
        )

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001,FR-002", "--json"],
        )

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.strip())
        assert payload["result"] == "success"
        assert payload["mission_slug"] == "001-test"
        assert payload["mission_number"] is None
        assert payload["mission_type"] == "software-dev"
        assert payload["mapped"]["WP01"] == ["FR-001", "FR-002"]
        assert _read_wp_refs(feature_dir, "WP01") == ["FR-001", "FR-002"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_individual_unions_refs(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)

        runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )
        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-002", "--json"],
        )

        assert result.exit_code == 0
        refs = _read_wp_refs(feature_dir, "WP01")
        assert "FR-001" in refs
        assert "FR-002" in refs

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_replace_overwrites_refs(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)

        runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )
        result = runner.invoke(
            tasks_app,
            [
                "map-requirements",
                "--wp",
                "WP01",
                "--refs",
                "FR-002",
                "--replace",
                "--json",
            ],
        )

        assert result.exit_code == 0
        refs = _read_wp_refs(feature_dir, "WP01")
        assert refs == ["FR-002"]
        assert "FR-001" not in refs

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_merge_individual_different_wps(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        _setup_feature(tmp_path)

        runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )
        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP02", "--refs", "FR-002", "--json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert "WP01" in payload["total_mappings"]
        assert "WP02" in payload["total_mappings"]


class TestMapRequirementsBatch:
    """Tests for batch mode (--batch)."""

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_writes_all_mappings_to_frontmatter(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)
        # rc3 M5 (FR-002/FR-003): resolve_mission_identity no longer defaults a
        # typeless/absent meta.json to "software-dev" -- give the fixture an
        # explicit canonical mission_type so the identity payload assertion
        # below exercises a real software-dev mission, not the neutral case.
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "software-dev", "slug": "001-test"}),
            encoding="utf-8",
        )

        batch = json.dumps({"WP01": ["FR-001", "FR-002"], "WP02": ["FR-003"]})
        result = runner.invoke(tasks_app, ["map-requirements", "--batch", batch, "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["result"] == "success"
        assert payload["mission_slug"] == "001-test"
        assert payload["mission_number"] is None
        assert payload["mission_type"] == "software-dev"
        assert payload["mapped"]["WP01"] == ["FR-001", "FR-002"]
        assert payload["mapped"]["WP02"] == ["FR-003"]
        assert _read_wp_refs(feature_dir, "WP01") == ["FR-001", "FR-002"]
        assert _read_wp_refs(feature_dir, "WP02") == ["FR-003"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_batch_non_string_refs_p3_regression(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        _setup_feature(tmp_path)

        batch = json.dumps({"WP01": [1, 2]})
        result = runner.invoke(tasks_app, ["map-requirements", "--batch", batch, "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert "list of strings" in payload["error"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_batch_replace_overwrites(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)

        runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )
        batch = json.dumps({"WP01": ["FR-002"], "WP02": ["FR-003"]})
        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--batch", batch, "--replace", "--json"],
        )

        assert result.exit_code == 0
        assert _read_wp_refs(feature_dir, "WP01") == ["FR-002"]
        assert _read_wp_refs(feature_dir, "WP02") == ["FR-003"]


class TestMapRequirementsValidation:
    """Validation and migration tests."""

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_rejects_unknown_ref(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        _setup_feature(tmp_path)

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-999", "--json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert payload["error"] == "Invalid requirement refs"
        assert payload["unknown_refs"] == ["FR-999"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_rejects_unknown_wp(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        _setup_feature(tmp_path)

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP99", "--refs", "FR-001", "--json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert payload["error"] == "Unknown WP IDs"
        assert payload["unknown_wps"] == ["WP99"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_rejects_invalid_format(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        _setup_feature(tmp_path)

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "INVALID-REF", "--json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert payload["error"] == "Invalid requirement ref format"
        assert "INVALID-REF" in payload["malformed_refs"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_requires_one_mode(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        _setup_feature(tmp_path)

        result = runner.invoke(tasks_app, ["map-requirements", "--json"])
        assert result.exit_code == 1
        assert "Provide either --wp + --refs" in result.stdout

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_coverage_summary(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        _setup_feature(tmp_path)

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        coverage = payload["coverage"]
        assert coverage["total_functional"] == 3
        assert coverage["mapped_functional"] == 1
        assert "FR-002" in coverage["unmapped_functional"]
        assert "FR-003" in coverage["unmapped_functional"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_seeds_from_tasks_md_on_first_migration(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)
        (feature_dir / "tasks.md").write_text(
            """## Work Package WP01
**Requirements Refs**: FR-002
## Work Package WP02
**Requirements Refs**: FR-003
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )

        assert result.exit_code == 0
        refs = _read_wp_refs(feature_dir, "WP01")
        # FR-005 append-only: order preserved (was sorted) -- the tasks.md
        # fallback (FR-002) seeds the base, the new ref (FR-001) is appended.
        assert refs == ["FR-002", "FR-001"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_replace_clears_stale_invalid_refs(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)
        tasks_dir = feature_dir / "tasks"
        wp_file = next(tasks_dir.glob("WP01*.md"))
        frontmatter, body = read_frontmatter(wp_file)
        frontmatter["requirement_refs"] = ["FR-999"]
        from specify_cli.frontmatter import write_frontmatter

        write_frontmatter(wp_file, frontmatter, body)

        result = runner.invoke(
            tasks_app,
            [
                "map-requirements",
                "--wp",
                "WP01",
                "--refs",
                "FR-001,FR-002,FR-003",
                "--replace",
                "--json",
            ],
        )

        assert result.exit_code == 0
        refs = _read_wp_refs(feature_dir, "WP01")
        assert refs == ["FR-001", "FR-002", "FR-003"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_reports_stale_invalid_refs(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)
        tasks_dir = feature_dir / "tasks"
        wp_file = next(tasks_dir.glob("WP02*.md"))
        frontmatter, body = read_frontmatter(wp_file)
        frontmatter["requirement_refs"] = ["BOGUS"]
        from specify_cli.frontmatter import write_frontmatter

        write_frontmatter(wp_file, frontmatter, body)

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert payload["error"] == "Stale or invalid refs in WP frontmatter"
        assert "WP02" in payload["stale_refs"]
        # #2066: payload now surfaces the parsed spec FR set, per-WP offender
        # classification, and a hint naming the grammar.
        assert payload["parsed_spec_ids"] == ["FR-001", "FR-002", "FR-003", "NFR-001"]
        assert payload["stale_ref_reasons"]["WP02"]["malformed"] == ["BOGUS"]
        assert payload["stale_ref_reasons"]["WP02"]["unknown_spec_id"] == []
        # requirement-id-grammar-01M3NRCA WP03 (FR-019): the reason partition
        # gains a foreign_qualified bucket, and the hint now names the grammar
        # rule text rather than restating "FR-NNN, NFR-NNN, or C-NNN".
        assert payload["stale_ref_reasons"]["WP02"]["foreign_qualified"] == []
        assert "kind FR, NFR, C or SC" in payload["hint"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_stale_refs_classify_format_vs_unknown(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ):
        """#2066 Repro A, re-pinned by requirement-id-grammar-01M3NRCA WP03:
        ``FR-003a`` is now WELL-FORMED grammar (a letter suffix), so on this
        fixture (which declares only FR-001..FR-003 and NFR-001) it reads as
        unknown_spec_id, not malformed. A genuinely malformed token (``FR_003``,
        underscore) proves the malformed bucket instead, so the test still
        exercises both buckets on one fixture."""
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path)
        tasks_dir = feature_dir / "tasks"
        wp_file = next(tasks_dir.glob("WP02*.md"))
        frontmatter, body = read_frontmatter(wp_file)
        frontmatter["requirement_refs"] = ["FR_003", "FR-999"]
        from specify_cli.frontmatter import write_frontmatter

        write_frontmatter(wp_file, frontmatter, body)

        result = runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        reasons = payload["stale_ref_reasons"]["WP02"]
        assert reasons["malformed"] == ["FR_003"]
        assert reasons["unknown_spec_id"] == ["FR-999"]


class TestFinalizeTasksWithFrontmatterRefs:
    """Tests for finalize-tasks reading from WP frontmatter."""

    @patch("specify_cli.cli.commands.agent.mission.locate_project_root")
    @patch("specify_cli.cli.commands.agent.mission._find_feature_directory")
    @patch(
        "specify_cli.cli.commands.agent.mission._show_branch_context",
        return_value=(None, "main"),
    )
    @patch(
        "specify_cli.coordination.commit_router.commit_for_mission",
        return_value=CommitRouterResult(status="committed", placement_ref="main", commit_hash="a" * 40),
    )
    @patch(
        "specify_cli.cli.commands.agent.mission.run_command",
        return_value=(0, "a" * 40, ""),
    )
    def test_finalize_reads_requirement_refs_from_frontmatter(
        self,
        mock_run: Mock,
        mock_commit: Mock,
        mock_show_branch: Mock,
        mock_find: Mock,
        mock_locate: Mock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        mock_locate.return_value = tmp_path
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        mock_find.return_value = feature_dir

        (feature_dir / "spec.md").write_text(SPEC_CONTENT, encoding="utf-8")
        (feature_dir / "tasks.md").write_text(
            "## Work Package WP01\n**Dependencies**: None\n## Work Package WP02\n**Dependencies**: None\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP01-test.md").write_text(
            '---\nwork_package_id: "WP01"\ntitle: "WP01"\n'
            "requirement_refs:\n  - FR-001\n  - NFR-001\n"
            "owned_files:\n  - src/module_a/**\nauthoritative_surface: src/module_a/\n"
            "---\n\n# WP01\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02-test.md").write_text(
            '---\nwork_package_id: "WP02"\ntitle: "WP02"\n'
            "requirement_refs:\n  - FR-002\n  - FR-003\n"
            "owned_files:\n  - src/module_b/**\nauthoritative_surface: src/module_b/\n"
            "---\n\n# WP02\n",
            encoding="utf-8",
        )

        result = runner.invoke(feature_app, ["finalize-tasks", "--target-branch", "main", "--json"])
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["result"] == "success"
        assert "FR-001" in payload["requirement_refs_parsed"]["WP01"]
        assert "NFR-001" in payload["requirement_refs_parsed"]["WP01"]
        assert "FR-002" in payload["requirement_refs_parsed"]["WP02"]

    @patch("specify_cli.cli.commands.agent.mission.locate_project_root")
    @patch("specify_cli.cli.commands.agent.mission._find_feature_directory")
    @patch(
        "specify_cli.cli.commands.agent.mission._show_branch_context",
        return_value=(None, "main"),
    )
    @patch(
        "specify_cli.coordination.commit_router.commit_for_mission",
        return_value=CommitRouterResult(status="committed", placement_ref="main", commit_hash="a" * 40),
    )
    @patch(
        "specify_cli.cli.commands.agent.mission.run_command",
        return_value=(0, "a" * 40, ""),
    )
    def test_frontmatter_takes_priority_over_stale_tasks_md(
        self,
        mock_run: Mock,
        mock_commit: Mock,
        mock_show_branch: Mock,
        mock_find: Mock,
        mock_locate: Mock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        mock_locate.return_value = tmp_path
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        mock_find.return_value = feature_dir

        (feature_dir / "spec.md").write_text(SPEC_CONTENT, encoding="utf-8")
        (feature_dir / "tasks.md").write_text(
            "## Work Package WP01\n**Requirements Refs**: FR-001\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP01-test.md").write_text(
            '---\nwork_package_id: "WP01"\ntitle: "WP01"\n'
            "requirement_refs:\n  - FR-001\n  - FR-002\n  - FR-003\n  - NFR-001\n---\n\n# WP01\n",
            encoding="utf-8",
        )

        result = runner.invoke(feature_app, ["finalize-tasks", "--target-branch", "main", "--json"])
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        wp01_refs = payload["requirement_refs_parsed"]["WP01"]
        assert wp01_refs == ["FR-001", "FR-002", "FR-003", "NFR-001"]


class TestMapRequirementsAutoCommitJson:
    """Issue #1891 Finding 1: ``--json`` must serialize the commit result.

    ``safe_commit`` returns a ``CommitResult`` (not a bool). Previously that
    object was placed directly into the ``--json`` payload, so on the
    auto-commit success path ``json.dumps`` failed with "Object of type
    CommitResult is not JSON serializable" and the mutation's result was
    unparseable by an orchestrating agent.
    """

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_auto_commit_json_payload_is_serializable(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        mock_commit_for_mission: Mock,
        tmp_path: Path,
    ) -> None:
        from specify_cli.coordination.commit_router import CommitRouterResult

        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        # WP07 / FR-006: the WP-file commit routes through ``commit_for_mission``.
        # A committed router result carries the placement ref + commit hash; the
        # command reconstructs the serializable ``commit_result`` envelope (#1891).
        mock_commit_for_mission.return_value = CommitRouterResult(
            status="committed", placement_ref="main", commit_hash="abc1234def"
        )
        _setup_feature(tmp_path)

        result = runner.invoke(
            tasks_app,
            [
                "map-requirements",
                "--wp",
                "WP01",
                "--refs",
                "FR-001",
                "--auto-commit",
                "--json",
            ],
        )

        assert result.exit_code == 0, result.stdout
        # Pre-fix this raised / produced an {"error": ...} payload.
        payload = json.loads(result.stdout.strip())
        assert payload["result"] == "success"
        assert payload["committed"] is True
        assert payload["commit_sha"] == "abc1234def"
        mock_commit_for_mission.assert_called_once()
