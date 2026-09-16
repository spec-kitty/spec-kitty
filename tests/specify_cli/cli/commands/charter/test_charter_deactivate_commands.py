"""Tests for WP06/T026+T029: spec-kitty charter deactivate command.

Covers FR-005, FR-006, FR-007, FR-010:
- Happy path: deactivate an activated artifact
- Unknown kind: exits 1 with "Unknown kind" in output
- None-state: exits 1 with "spec-kitty upgrade" guidance
- Cascade flag: accepted and processed
- Shared artifact protection: skipped with appropriate message
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root_with_directive(tmp_path: Path) -> Path:
    """A project with activated_directives: [some-directive] in config.yaml.

    Also carries ``mission_type_activations`` (WP04, C-A1): the provisioned
    charter is the sole mission-type activation authority, so
    ``PackContext.from_config`` fails closed when the key is absent.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config_data = (
        "activated_directives:\n  - some-directive\n"
        "mission_type_activations:\n  - software-dev\n"
    )
    (kittify / "config.yaml").write_text(config_data, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def empty_project_root(tmp_path: Path) -> Path:
    """A project with empty config.yaml (no activation keys)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("# empty config\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A minimal project with no pre-activated artifacts (org-pack fixtures build state).

    Mirrors ``test_charter_activate_commands_cascade_output.py``'s own
    ``project_root`` fixture -- same shape, so the WP04 cross-command test
    below can activate and then deactivate the SAME org-pack-declared source.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    return tmp_path


def _invoke_deactivate(project_root: Path, *args: str) -> Result:
    """Invoke charter deactivate with --repo-root placed before positional args."""
    return runner.invoke(
        charter_app,
        ["deactivate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


def _invoke_activate(project_root: Path, *args: str) -> Result:
    """Invoke charter activate with --repo-root placed before positional args."""
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Org-pack fixture builders (WP04, mirrors
# ``test_charter_activate_commands_cascade_output.py``'s module-level
# builders of the same name -- same fixture shape, no shared test-helper
# module exists to import from instead; see this WP's prompt file).
# ---------------------------------------------------------------------------


def _write_org_pack_config(project_root: Path, packs: list[tuple[str, str]]) -> None:
    """Write ``.kittify/config.yaml`` with a declaration-ordered org-pack chain."""
    lines: list[str] = ["doctrine:", "  org:", "    packs:"]
    for name, local_path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {local_path}")
    lines.append("mission_type_activations:")
    lines.append("  - software-dev")
    config_path = project_root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_artifact(pack_root: Path, plural_dir: str, kind_singular: str, stem: str, declared_id: str) -> None:
    """Write a flat-layout artifact file: ``<pack>/<plural_dir>/<stem>.<kind_singular>.yaml``.

    The config-stem (``stem``) is deliberately distinct from the DRG ``id:``
    field (``declared_id``) so a fixture that made stem == id could never
    catch a stem/id-confusion bug (this WP's ID-resolution assertion relies
    on this).
    """
    target_dir = pack_root / plural_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / f"{stem}.{kind_singular}.yaml").write_text(
        f"id: {declared_id}\ntype: {kind_singular}\ntitle: {stem}\n", encoding="utf-8"
    )


def _write_graph_fragment(
    pack_root: Path,
    filename: str,
    *,
    nodes: list[tuple[str, str]],
    edges: list[tuple[str, str, str]],
) -> None:
    """Write a root-level ``*.graph.yaml`` DRG fragment for *pack_root*."""
    node_lines = "\n".join(f'  - urn: "{urn}"\n    kind: {kind}' for urn, kind in nodes)
    nodes_section = f"nodes:\n{node_lines}" if nodes else "nodes: []"

    edge_lines = "\n".join(
        f'  - source: "{src}"\n    target: "{tgt}"\n    relation: {rel}'
        for src, tgt, rel in edges
    )
    edges_section = f"edges:\n{edge_lines}" if edges else "edges: []"

    body = (
        'schema_version: "1.0"\n'
        'generated_at: "2026-08-17T00:00:00Z"\n'
        'generated_by: "test"\n'
        f"{nodes_section}\n"
        f"{edges_section}\n"
    )
    (pack_root / filename).write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# test_deactivate_happy_path
# ---------------------------------------------------------------------------


class TestDeactivateHappyPath:
    def test_deactivate_directive_removes_from_config(self, project_root_with_directive: Path) -> None:
        """Deactivating a directive removes it from config.yaml."""
        result = _invoke_deactivate(project_root_with_directive, "directive", "some-directive")
        assert result.exit_code == 0, result.output
        config = project_root_with_directive / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "some-directive" not in (data.get("activated_directives") or [])

    def test_deactivate_happy_path_prints_deactivated(self, project_root_with_directive: Path) -> None:
        """Successful deactivation prints 'Deactivated' in output."""
        result = _invoke_deactivate(project_root_with_directive, "directive", "some-directive")
        assert result.exit_code == 0, result.output
        assert "Deactivated" in result.output


# ---------------------------------------------------------------------------
# test_deactivate_unknown_kind_exits_1
# ---------------------------------------------------------------------------


class TestDeactivateUnknownKind:
    def test_unknown_kind_exits_1(self, empty_project_root: Path) -> None:
        """Deactivating with an unknown kind exits with code 1."""
        result = runner.invoke(
            charter_app,
            ["deactivate", "--repo-root", str(empty_project_root), "nonsense", "some-id"],
        )
        assert result.exit_code == 1
        assert "Unknown kind" in result.output


# ---------------------------------------------------------------------------
# test_deactivate_none_state_exits_1
# ---------------------------------------------------------------------------


class TestDeactivateNoneState:
    def test_none_state_exits_one_with_upgrade_guidance(self, empty_project_root: Path) -> None:
        """Deactivating from None-state exits 1 with rendered upgrade guidance (WP12/T054).

        WP09 replaced the legacy ``sys.exit(1)`` in ``CharterPackManager.deactivate``
        with the engine's typed ``NoActivationRestrictionsError`` (carrying the
        "run upgrade first" guidance). WP12 now **catches** that error in the CLI and
        renders it as a clean exit-1 with guidance (no propagated exception) — the
        behavior previously deferred to WP12. Assert the WP12 contract here.
        """
        result = runner.invoke(
            charter_app,
            ["deactivate", "--repo-root", str(empty_project_root), "directive", "some-directive"],
        )
        assert result.exit_code == 1
        assert "spec-kitty upgrade" in result.output


# ---------------------------------------------------------------------------
# test_deactivate_cascade
# ---------------------------------------------------------------------------


class TestDeactivateCascade:
    def test_cascade_flag_accepted(self, project_root_with_directive: Path) -> None:
        """--cascade flag is accepted without error."""
        result = runner.invoke(
            charter_app,
            [
                "deactivate",
                "--repo-root",
                str(project_root_with_directive),
                "--cascade",
                "all",
                "directive",
                "some-directive",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    def test_deactivate_accepts_options_after_positional_args(self, project_root_with_directive: Path) -> None:
        """Contract examples place --cascade after <kind> <id>."""
        result = runner.invoke(
            charter_app,
            [
                "deactivate",
                "directive",
                "some-directive",
                "--cascade",
                "all",
                "--repo-root",
                str(project_root_with_directive),
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output

    def test_cascade_no_deferral_warning(self, project_root_with_directive: Path) -> None:
        """--cascade does NOT emit stale deferral warnings (SC-005 / DD-4)."""
        result = runner.invoke(
            charter_app,
            [
                "deactivate",
                "--repo-root",
                str(project_root_with_directive),
                "--cascade",
                "all",
                "directive",
                "some-directive",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # SC-005: stale deferral strings must be absent
        assert "not yet implemented" not in result.output
        assert "deferred" not in result.output.lower()


# ---------------------------------------------------------------------------
# test_deactivate_shared_artifact_skipped
# ---------------------------------------------------------------------------


class TestDeactivateSharedArtifactSkipped:
    def test_not_in_activation_set_emits_warning(self, project_root_with_directive: Path) -> None:
        """Deactivating an artifact not in the set emits a warning and exits 0."""
        result = _invoke_deactivate(project_root_with_directive, "directive", "nonexistent-directive")
        # Not in set → warning, exit 0
        assert result.exit_code == 0, result.output
        assert "Warning" in result.output or "not in" in result.output.lower()


# ---------------------------------------------------------------------------
# T017 — cascade-output absence test (SC-005)
# ---------------------------------------------------------------------------


class TestDeactivateCascadeOutputAbsence:
    """Verify that stale deferral warning strings are absent from --cascade deactivate output."""

    def test_deactivate_cascade_no_not_yet_implemented(self, project_root_with_directive: Path) -> None:
        """'not yet implemented' must not appear in charter deactivate --cascade output."""
        result = runner.invoke(
            charter_app,
            [
                "deactivate",
                "--repo-root",
                str(project_root_with_directive),
                "--cascade",
                "all",
                "directive",
                "some-directive",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "not yet implemented" not in result.output

    def test_deactivate_cascade_no_deferred(self, project_root_with_directive: Path) -> None:
        """'deferred' must not appear in charter deactivate --cascade output."""
        result = runner.invoke(
            charter_app,
            [
                "deactivate",
                "--repo-root",
                str(project_root_with_directive),
                "--cascade",
                "all",
                "directive",
                "some-directive",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "deferred" not in result.output.lower()

    def test_deactivate_cascade_still_deactivates(self, project_root_with_directive: Path) -> None:
        """cascade=True still deactivates the target artifact (real behavior unchanged)."""
        result = runner.invoke(
            charter_app,
            [
                "deactivate",
                "--repo-root",
                str(project_root_with_directive),
                "--cascade",
                "all",
                "directive",
                "some-directive",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        config = project_root_with_directive / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "some-directive" not in (data.get("activated_directives") or [])


# ---------------------------------------------------------------------------
# T017 (mission cascade-asset-silent-drop-01M0RME0, WP04) -- the deactivation
# side of C-002's cross-command symmetry (NFR-003/SC-003): `charter
# activate --cascade all` and `charter deactivate --cascade all` must AGREE
# on the same kind-filtered node, using the SAME shared rendering helper
# (`render_kind_filtered_line`/`KIND_FILTERED_LABEL`, defined in the neutral
# `_cascade_shared.py` module both commands import since issue #3772's
# de-dup -- previously `activate.py`'s `_render_kind_filtered_line`, imported
# cross-module by `deactivate.py`) -- never a second, divergent render path.
# ---------------------------------------------------------------------------


class TestDeactivateKindFilteredNodeRendering:
    """FR-007: `_render_cascade_deactivation` renders kind-filtered nodes too."""

    def test_deactivate_cascade_reports_same_kind_filtered_line_as_activate_with_resolved_id(
        self, project_root: Path
    ) -> None:
        """Activate then deactivate the SAME source; both must render the
        SAME kind-filtered line for the SAME asset.

        Two org packs (packA declares the source directive with a `suggests`
        edge to a bare DRG id; packB declares the asset artifact under a
        DIFFERENT config-stem id) so this also pins the ID-resolution
        requirement: the deactivation-side line must render the RESOLVED
        config-stem id (matching the activation-side line), never the raw
        bare DRG id -- this assertion fails if `_render_cascade_deactivation`
        passed `urn.partition(":")[2]` straight to `render_kind_filtered_line`
        instead of resolving through `resolve_config_id(...)` first.
        """
        pack_a_root = project_root / "org-packs" / "deact-packA"
        pack_b_root = project_root / "org-packs" / "deact-packB"
        _write_artifact(
            pack_a_root, "directives", "directive", "deact-stem-source", "DIRECTIVE_DEACT_STEM_SRC"
        )
        _write_graph_fragment(
            pack_a_root,
            "fixture.graph.yaml",
            nodes=[("directive:DIRECTIVE_DEACT_STEM_SRC", "directive")],
            edges=[
                (
                    "directive:DIRECTIVE_DEACT_STEM_SRC",
                    "asset:ASSET_DEACT_RAW_BARE_ID",
                    "suggests",
                )
            ],
        )
        _write_artifact(
            pack_b_root, "assets", "asset", "deact-resolved-asset-stem", "ASSET_DEACT_RAW_BARE_ID"
        )
        _write_graph_fragment(
            pack_b_root,
            "fixture.graph.yaml",
            nodes=[("asset:ASSET_DEACT_RAW_BARE_ID", "asset")],
            edges=[],
        )
        _write_org_pack_config(
            project_root,
            [("deact-packA", "org-packs/deact-packA"), ("deact-packB", "org-packs/deact-packB")],
        )

        # Step 1 (precondition -- already-landed WP01/WP02 behavior): activate
        # with --cascade all renders the resolved-id kind-filtered line.
        activate_result = _invoke_activate(
            project_root, "--cascade", "all", "directive", "deact-stem-source"
        )
        assert activate_result.exit_code == 0, activate_result.output
        assert (
            "Not cascaded: asset/deact-resolved-asset-stem (kind not charter-activatable)"
            in activate_result.output
        )

        # Step 2 (this WP's new behavior): deactivate with --cascade all
        # renders the EQUIVALENT line -- same helper, same wording, same
        # resolved id.
        deactivate_result = _invoke_deactivate(
            project_root, "--cascade", "all", "directive", "deact-stem-source"
        )
        assert deactivate_result.exit_code == 0, deactivate_result.output
        assert (
            "Not cascaded: asset/deact-resolved-asset-stem (kind not charter-activatable)"
            in deactivate_result.output
        )
        assert "ASSET_DEACT_RAW_BARE_ID" not in deactivate_result.output
        # NFR-004/SC-006: the pre-existing lines are unrelated and unchanged
        # by this fixture -- the asset is kind-filtered, so it was never a
        # `.deactivate` or `.skipped_shared` candidate in the first place.
        assert "Cascade-deactivated" not in deactivate_result.output
        assert "Skipped (shared artifact)" not in deactivate_result.output


# ---------------------------------------------------------------------------
# #4115 — warn when a deactivated agent profile is a built-in mission-step
# default (the executor's role-based fallback is the behavioral half).
# ---------------------------------------------------------------------------


def test_deactivate_agent_profile_warns_when_mission_step_default(tmp_path: Path) -> None:
    """``charter deactivate agent-profile researcher-robbie`` must WARN that
    the removed profile is the built-in default for mission steps, naming a
    bound step and the role the fallback will look for — not succeed
    silently while every built-in mission heads for a blocked composition."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "activated_agent_profiles:\n  - researcher-robbie\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )

    result = _invoke_deactivate(tmp_path, "agent-profile", "researcher-robbie")

    assert result.exit_code == 0, result.output
    assert "Deactivated" in result.output
    assert "built-in default profile" in result.output
    assert "software-dev/specify" in result.output
    assert "'researcher'-role" in result.output


def test_deactivate_agent_profile_no_warning_for_ordinary_profile(tmp_path: Path) -> None:
    """Negative case: a profile no mission step binds deactivates with the
    pre-#4115 output and no mission warning."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "activated_agent_profiles:\n  - scribe-sally\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )

    result = _invoke_deactivate(tmp_path, "agent-profile", "scribe-sally")

    assert result.exit_code == 0, result.output
    assert "Deactivated" in result.output
    assert "built-in default profile" not in result.output
