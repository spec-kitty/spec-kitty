"""Pre-merge squad fold-in (#5257): CLI-level coverage for a DRG-*transitively*-
reached missing id (WP03-C1-002) and the whole-kind fail-closed path
(WP03-C1-004), both driven through the real ``charter generate --json`` CLI
entry point rather than an internal compiler-level helper call.

New file rather than an addition to ``test_charter_generate_autotrack.py``:
that file is on ``pyproject.toml``'s ``[tool.ruff.format]`` formatter-debt
exclude list (``ruff format`` would reformat the WHOLE file), so adding tests
there would either entangle this change with an unrelated repo-wide
reformat, or require a local ``# fmt: off`` carve-out neither this fix nor
that file's own history uses. This file is a normal, ruff-formatted file.

Both fixtures below declare a project-level DRG overlay (``.kittify/charter-packs/
graph.yaml``) adding one new node plus one ``requires`` edge FROM a real,
already-activated built-in directive node (``directive:DIRECTIVE_001``) TO
the new node -- so the id is reached purely via DRG-transitive closure (never
listed in ``.kittify/config.yaml``'s own ``activated_*`` lists), landing in
``_render_kind_references``'s per-id raw-repository lookup rather than the
``config.activated_*`` direct-id path that ``_resolve_config_activated_roots``
hard-fails on for a genuinely-unknown id (wp-WP03.yaml's WP03-C1-002
finding). ``DIRECTIVE_001`` requires no real built-in ``toolguide`` at all
(confirmed: no ``toolguide`` urn appears alongside ``DIRECTIVE_001`` in
``packs/built-in/*.graph.yaml``'s edge declarations), so the ``toolguide``
fixture below isolates the whole-kind check to the one ghost id without any
real toolguide reference muddying the count.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from tests.specify_cli.cli.commands.test_charter_generate_autotrack import (
    _git_init,
    _write_curated_charter_md,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

#: A real, already-activated built-in directive node (``packs/built-in/directive.graph.yaml``)
#: that requires no real built-in ``toolguide`` -- used as the edge SOURCE so
#: the transitive walk reaches the ghost node without needing a fabricated
#: root of its own (which config-level activation would hard-validate).
_REAL_DIRECTIVE_URN = "directive:DIRECTIVE_001"


def _write_directive_activation_config(repo: Path) -> None:
    """Activate the one real directive whose closure we extend below."""
    config_path = repo / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload = {
        "vcs": {"type": "git"},
        "activated_directives": ["001-architectural-integrity-standard"],
    }
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def _write_project_drg_overlay(repo: Path, *, kind: str, ghost_id: str) -> None:
    """Add one project-only DRG node of *kind* plus a ``requires`` edge from
    :data:`_REAL_DIRECTIVE_URN` to it -- a valid (non-dangling) overlay the
    real ``load_validated_graph`` merge accepts, so the transitive walk
    reaches ``<kind>:<ghost_id>`` with no backing on-disk artifact.
    """
    overlay_dir = repo / ".kittify" / "charter-packs"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload = {
        "schema_version": "1.0",
        "generated_at": "2026-04-14T00:00:00Z",
        "generated_by": "test",
        "nodes": [
            {"urn": f"{kind}:{ghost_id}", "kind": kind, "label": "Ghost DRG-transitive id (no backing artifact)"},
        ],
        "edges": [
            {"source": _REAL_DIRECTIVE_URN, "target": f"{kind}:{ghost_id}", "relation": "requires"},
        ],
    }
    with (overlay_dir / "graph.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


# ---------------------------------------------------------------------------
# WP03-C1-002: a DRG-transitively-reached missing id reaches
# `unresolved_references` with `missing_artifact`/`typo_suspected`.
# ---------------------------------------------------------------------------


def test_generate_json_reports_missing_artifact_for_a_drg_transitively_reached_id(
    tmp_path: Path,
) -> None:
    """A ``styleguide`` id reachable ONLY via DRG-transitive closure (a
    ``requires`` edge from an activated real directive, never listed in
    ``.kittify/config.yaml``'s own ``activated_styleguides``) that has no
    backing on-disk artifact must reach ``--json``'s ``unresolved_references``
    with a ``missing_artifact`` (or ``typo_suspected``) cause -- proving
    WP03's cause-agnostic ``list(compiled.unresolved_reference_records)``
    pass-through actually carries this cause through the real CLI, not only
    the ``scope_filtered`` cause the pre-existing fixture in
    ``test_charter_generate_autotrack.py`` exercises (wp-WP03.yaml
    WP03-C1-002).
    """
    ghost_id = "ghost-drg-transitive-01M3M1KF"
    _git_init(tmp_path)
    _write_curated_charter_md(tmp_path)
    _write_directive_activation_config(tmp_path)
    _write_project_drg_overlay(tmp_path, kind="styleguide", ghost_id=ghost_id)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(
            charter_app,
            ["generate", "--no-from-interview", "--force", "--json"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"generate failed: {result.stdout!r}"
    payload = json.loads(result.stdout)

    unresolved = payload["unresolved_references"]
    matches = [entry for entry in unresolved if entry.get("kind") == "styleguide" and entry.get("id") == ghost_id]
    assert len(matches) == 1, f"expected exactly one unresolved_references entry for styleguide/{ghost_id}, got {matches!r} (full list: {unresolved!r})"
    assert matches[0]["cause"] in ("missing_artifact", "typo_suspected"), (
        f"expected a missing_artifact/typo_suspected cause for a genuinely-nonexistent DRG-transitive id, got: {matches[0]!r}"
    )


# ---------------------------------------------------------------------------
# WP03-C1-004: the whole-kind fail-closed path yields a non-zero exit and
# the command's existing error-JSON shape naming the kind.
# ---------------------------------------------------------------------------


def test_generate_json_whole_kind_fail_closed_exits_non_zero_naming_the_kind(
    tmp_path: Path,
) -> None:
    """When a tracked kind's ONLY activated id (here ``toolguide``, which
    ``DIRECTIVE_001`` requires none of in the real built-in graph) is
    DRG-transitively reached but unresolvable, the whole-kind aggregate
    fail-closed check (I1/I2, compiler.py's ``_check_whole_kind_unresolved``)
    must raise, and ``charter generate --json`` must surface that as a
    non-zero exit with the command's EXISTING error-JSON shape
    (``{"result": "error", "success": false, "error": <message naming the
    kind>}``) -- pinned at the literal CLI-invocation level SC-005 describes,
    not only the compiler-unit level (wp-WP03.yaml WP03-C1-004).
    """
    ghost_id = "ghost-drg-transitive-01M3M1KF"
    _git_init(tmp_path)
    _write_curated_charter_md(tmp_path)
    _write_directive_activation_config(tmp_path)
    _write_project_drg_overlay(tmp_path, kind="toolguide", ghost_id=ghost_id)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(
            charter_app,
            ["generate", "--no-from-interview", "--force", "--json"],
            catch_exceptions=True,
        )

    assert result.exit_code != 0, f"expected a non-zero exit for the whole-kind fail-closed path, got 0: {result.stdout!r}"
    payload = json.loads(result.stdout)

    assert payload["result"] == "error"
    assert payload["success"] is False
    assert "toolguide" in payload["error"], f"error message must name the unresolvable kind, got: {payload['error']!r}"
    # The machine-readable records ride along on the error path too, so a CI
    # probe does not have to parse the prose to learn which ids were unresolved.
    unresolved = payload["unresolved_references"]
    assert [(e["kind"], e["id"]) for e in unresolved if e["kind"] == "toolguide"] == [("toolguide", ghost_id)], unresolved

    # No catalog must have been written for this run (fail-closed, not a
    # partial/silently-empty write).
    assert not (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()
