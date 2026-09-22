"""#4890 regression: legacy ``agent tasks finalize-tasks`` must validate the
EFFECTIVE PERSISTED dependency graph, not just the tasks.md-parsed map.

Mission ``user-content-preservation-01M3549Q`` / WP06.

Ground truth (pre-fix, verified on main@d57619a900):

* ``tasks_finalize.py::_ft_validate`` ran ``detect_dependency_cycles`` on the
  ``tasks.md``-parsed map ONLY.
* ``tasks_finalize_validation.py::compute_wp_frontmatter_updates`` preserves
  a WP's existing frontmatter ``dependencies:`` verbatim, UNVALIDATED,
  whenever ``tasks.md`` declares no dependency line for that WP.
* ``core.dependency_graph.validate_dependencies`` (self-dep / malformed-id /
  "Dependency WPxx not found in graph") was never called by this command at
  all -- its only production call site was
  ``mission_finalize.py::_validate_dependency_graph``.

So a WP01<->WP02 cycle (or an unknown-WP / self-ref dependency) living ONLY
in WP frontmatter passed straight through: exit 0, a falsified (empty)
``dependencies`` JSON payload, canonical status seeded, both WPs permanently
unclaimable.

Each rejection case below is mirrored by an ``agent mission finalize-tasks``
control invocation on the byte-identical repo state -- that command's
``_validate_dependency_graph`` already runs both ``detect_cycles`` and
``validate_dependencies`` over the effective (frontmatter-preserving) graph,
so it already refuses. This proves the bug is specific to the LEGACY command,
not the dependency shape itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.status.bootstrap import BootstrapResult
from specify_cli.status.lane_reader import has_event_log

pytestmark = pytest.mark.regression

runner = CliRunner()

_TASKS_MODULE = "specify_cli.cli.commands.agent.tasks"
_MISSION_MODULE = "specify_cli.cli.commands.agent.mission"


def _build_feature(
    tmp_path: Path,
    mission_slug: str,
    wp_deps: dict[str, list[str]],
) -> Path:
    """A mission whose ``tasks.md`` declares NO deps; frontmatter carries ``wp_deps``.

    Mirrors the #4890 repro shape: ``tasks.md`` has plain WP sections with no
    "Depends on" text, so the tasks.md-parser's dependency map is
    ``{WPxx: []}`` for every WP -- the graph under test lives ONLY in WP
    frontmatter, which the legacy command preserved unvalidated.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "spec.md").write_text(
        "---\ntitle: Test Feature\n---\n\n## Requirements\n\n- FR-001: First requirement\n",
        encoding="utf-8",
    )
    sections = "\n\n".join(f"## Work Package {wp_id}\n\nNo dependency line here." for wp_id in sorted(wp_deps))
    (feature_dir / "tasks.md").write_text(f"# Tasks\n\n{sections}\n", encoding="utf-8")
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_type": "software-dev",
                "mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "mission_slug": mission_slug,
            }
        ),
        encoding="utf-8",
    )
    for wp_id, deps in wp_deps.items():
        dep_block = "dependencies:\n" + "\n".join(f"  - {d}" for d in deps) + "\n" if deps else "dependencies: []\n"
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\nrequirement_refs:\n  - FR-001\n{dep_block}---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    return feature_dir


def _invoke_legacy(tmp_path: Path, mission_slug: str) -> Any:
    """Invoke the command under test: ``agent tasks finalize-tasks``."""
    from specify_cli.cli.commands.agent.tasks import app

    with (
        patch(f"{_TASKS_MODULE}._ensure_target_branch_checked_out", return_value=(tmp_path, "main")),
        patch(f"{_TASKS_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_TASKS_MODULE}._find_mission_slug", return_value=mission_slug),
    ):
        return runner.invoke(app, ["finalize-tasks", "--mission", mission_slug, "--json"])


def _control_mission_patches(tmp_path: Path, mission_slug: str) -> dict[str, Any]:
    """Patch targets for the ``agent mission finalize-tasks`` control invocation.

    Mirrors ``tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py``'s
    ``_common_patches`` -- the established pattern for driving the canonical
    ``finalize_tasks`` function in-process without real git I/O.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    fake_commit_result = CommitRouterResult(status="committed", placement_ref="main", commit_hash="abc1234")
    total_wps = len(list((feature_dir / "tasks").glob("WP*.md")))
    return {
        f"{_MISSION_MODULE}.locate_project_root": MagicMock(return_value=tmp_path),
        f"{_MISSION_MODULE}._find_feature_directory": MagicMock(return_value=feature_dir),
        f"{_MISSION_MODULE}._resolve_planning_branch": MagicMock(return_value="main"),
        f"{_MISSION_MODULE}._ensure_branch_checked_out": MagicMock(),
        "specify_cli.coordination.commit_router.commit_for_mission": MagicMock(return_value=fake_commit_result),
        f"{_MISSION_MODULE}.run_command": MagicMock(return_value=(0, "abc1234", "")),
        f"{_MISSION_MODULE}.validate_ownership": MagicMock(
            return_value=MagicMock(passed=True, warnings=[], errors=[]),
        ),
        f"{_MISSION_MODULE}.bootstrap_canonical_state": MagicMock(
            return_value=BootstrapResult(total_wps=total_wps, already_initialized=0, newly_seeded=total_wps, skipped=0)
        ),
    }


def _invoke_control(tmp_path: Path, mission_slug: str) -> int:
    """Invoke the control command: ``agent mission finalize-tasks``."""
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    patches = _control_mission_patches(tmp_path, mission_slug)
    ctx_patches = {target: patch(target, value) for target, value in patches.items()}
    for p in ctx_patches.values():
        p.start()
    exit_code = 0
    try:
        finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
    except typer.Exit as exc:
        exit_code = exc.exit_code if exc.exit_code is not None else 1
    finally:
        for p in ctx_patches.values():
            p.stop()
    return exit_code


def _parse_json_payload(output: str) -> dict[str, Any]:
    for line in output.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return dict(json.loads(stripped))
    pytest.fail(f"No JSON object found in output:\n{output}")


class TestLegacyFinalizeValidatesEffectiveGraph:
    """#4890: the legacy command must reject a frontmatter-only bad graph."""

    def test_frontmatter_only_cycle_is_rejected(self, tmp_path: Path) -> None:
        mission_slug = "060-frontmatter-cycle"
        _build_feature(tmp_path, mission_slug, {"WP01": ["WP02"], "WP02": ["WP01"]})

        control_exit = _invoke_control(tmp_path, mission_slug)
        assert control_exit != 0, "control: agent mission finalize-tasks must already refuse this cycle"

        result = _invoke_legacy(tmp_path, mission_slug)
        assert result.exit_code != 0, f"#4890: a frontmatter-only WP01<->WP02 cycle finalized with exit 0 on the pre-fix tree. Output: {result.output}"
        assert "circular" in result.output.lower()

        feature_dir = tmp_path / "kitty-specs" / mission_slug
        assert not has_event_log(feature_dir), "#4890: a rejected finalize must seed NO canonical status"

    def test_frontmatter_unknown_wp_is_rejected(self, tmp_path: Path) -> None:
        mission_slug = "060-frontmatter-unknown"
        _build_feature(tmp_path, mission_slug, {"WP01": [], "WP02": ["WP99"]})

        control_exit = _invoke_control(tmp_path, mission_slug)
        assert control_exit != 0, "control: agent mission finalize-tasks must already refuse an unknown WP"

        result = _invoke_legacy(tmp_path, mission_slug)
        assert result.exit_code != 0, f"#4890: a frontmatter dependency on unknown WP99 finalized with exit 0 on the pre-fix tree. Output: {result.output}"

        feature_dir = tmp_path / "kitty-specs" / mission_slug
        assert not has_event_log(feature_dir), "#4890: a rejected finalize must seed NO canonical status"

    def test_frontmatter_self_dependency_is_rejected(self, tmp_path: Path) -> None:
        mission_slug = "060-frontmatter-selfdep"
        _build_feature(tmp_path, mission_slug, {"WP01": [], "WP02": ["WP02"]})

        control_exit = _invoke_control(tmp_path, mission_slug)
        assert control_exit != 0, "control: agent mission finalize-tasks must already refuse a self-dependency"

        result = _invoke_legacy(tmp_path, mission_slug)
        assert result.exit_code != 0, f"#4890: a frontmatter self-dependency WP02->WP02 finalized with exit 0 on the pre-fix tree. Output: {result.output}"

        feature_dir = tmp_path / "kitty-specs" / mission_slug
        assert not has_event_log(feature_dir), "#4890: a rejected finalize must seed NO canonical status"

    def test_valid_acyclic_frontmatter_graph_finalizes_with_effective_payload(self, tmp_path: Path) -> None:
        """Anchor (green on base too): a genuinely acyclic frontmatter graph
        must still succeed, and the JSON ``dependencies`` payload must equal
        the EFFECTIVE persisted graph (parsed deps merged with preserved
        frontmatter deps) -- not the empty tasks.md-parsed map (#4890 T022).
        """
        mission_slug = "060-frontmatter-valid"
        _build_feature(tmp_path, mission_slug, {"WP01": [], "WP02": ["WP01"]})

        result = _invoke_legacy(tmp_path, mission_slug)
        assert result.exit_code == 0, f"Expected success for a valid acyclic graph: {result.output}"

        payload = _parse_json_payload(result.output)
        assert payload["dependencies"] == {"WP01": [], "WP02": ["WP01"]}, (
            f"#4890: dependencies payload must equal the effective persisted graph (frontmatter-preserved deps included), got: {payload['dependencies']}"
        )
