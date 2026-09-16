"""Tests for WP06/T024: spec-kitty charter activate refactored command.

Split from the original `test_charter_activate_commands.py` (ci-test-topology-
performance-01KXBJRT WP05/T021, FR-005) to break the `fast-tests-cli` job's
single-worker tail: `--dist loadfile` pins every test in a file to one xdist
worker, so one heavy monolith caps the job regardless of idle workers.

This sibling covers `TestCascadeOutputAbsence` in full (measured as the
heaviest of the three siblings, ~3.6s call time per test) — the happy-path/
error tests live in the `_core` sibling and the cascade-flag-handling tests
live in the `_cascade_flags` sibling.

Covers:
- T017: cascade-output absence test (SC-005)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from charter.activation.cascade import (
    CascadeScope,
    cascade_activation_targets,
    referenced_but_not_cascaded,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A minimal project with .kittify/config.yaml.

    Carries ``mission_type_activations`` (WP04, C-A1): the provisioned
    charter is the sole mission-type activation authority, so
    ``PackContext.from_config`` fails closed when the key is absent.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# T017 — cascade-output absence test (SC-005)
# ---------------------------------------------------------------------------


class TestCascadeOutputAbsence:
    """Verify that stale deferral warning strings are absent from --cascade output."""

    def test_activate_cascade_no_not_yet_implemented(self, project_root: Path) -> None:
        """'not yet implemented' must not appear in charter activate --cascade output."""
        result = runner.invoke(
            charter_app,
            [
                "activate",
                "--repo-root",
                str(project_root),
                "--cascade",
                "all",
                "directive",
                "001-architectural-integrity-standard",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "not yet implemented" not in result.output

    def test_activate_cascade_no_deferred(self, project_root: Path) -> None:
        """'deferred' must not appear in charter activate --cascade output."""
        result = runner.invoke(
            charter_app,
            [
                "activate",
                "--repo-root",
                str(project_root),
                "--cascade",
                "all",
                "directive",
                "001-architectural-integrity-standard",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "deferred" not in result.output.lower()

    def test_activate_cascade_still_activates(self, project_root: Path) -> None:
        """cascade=True still activates the target artifact (real behavior unchanged)."""
        result = runner.invoke(
            charter_app,
            [
                "activate",
                "--repo-root",
                str(project_root),
                "--cascade",
                "all",
                "directive",
                "001-architectural-integrity-standard",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "001-architectural-integrity-standard" in data["activated_directives"]


# ---------------------------------------------------------------------------
# T008 (mission cascade-asset-silent-drop-01M0RME0, WP02) — kind-filtered
# rendering in `_render_cascade_activation` (FR-003/FR-004/FR-008/FR-009).
#
# Fixture builders mirror the established org-pack fixture pattern from
# ``tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py`` (no
# reusable conftest helper exists for this shape -- each CLI-level cascade
# test module writes its own small fixture builders). A synthetic org pack is
# required here (rather than a real doctrine artifact) because the User
# Story 1 fixture (``toolguide:qa-carrier-lint --suggests--> tactic:qa`` /
# ``--suggests--> asset:qa-traceability-lint``) exists only as a hand-built
# DRG in the engine-level unit tests (``tests/charter/test_cascade.py``); the
# CLI-level ATDD tests here need real on-disk artifact files so
# ``_cascade_shared.py``'s ``drg_urn_to_config_id``/``CharterPackManager.activate`` can resolve them,
# and use directive/tactic/asset kinds as the fixture's equivalent kind/id
# (a directive source rather than a toolguide -- same DRG shape).
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
    field (``declared_id``) -- matching the established convention in
    ``test_org_cascade_chain.py`` -- so a fixture that made stem == id could
    never catch a stem/id-confusion bug (T008's fourth test relies on this).
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


def _activate_kind_filtered_fixture(project_root: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


class TestKindFilteredNodeRendering:
    """FR-003/FR-004/FR-008: `_render_cascade_activation` renders kind-filtered nodes."""

    def test_cascade_all_renders_kind_filtered_asset_alongside_activated_tactic(
        self, project_root: Path
    ) -> None:
        """Scenario 1 (spec.md User Story 1): a source with one `suggests` edge to
        an activatable-kind node (`tactic`) and one to a kind-filtered node
        (`asset`) renders BOTH the existing `Cascade-activated` line (tactic,
        unchanged wording) AND a new, distinct kind-filtered line (asset).
        """
        pack_root = project_root / "org-packs" / "pack1"
        _write_artifact(pack_root, "directives", "directive", "source-directive", "DIRECTIVE_SRC")
        _write_artifact(pack_root, "tactics", "tactic", "cascade-tactic", "TACTIC_ONE")
        _write_artifact(pack_root, "assets", "asset", "cascade-asset", "ASSET_ONE")
        _write_graph_fragment(
            pack_root,
            "fixture.graph.yaml",
            nodes=[
                ("directive:DIRECTIVE_SRC", "directive"),
                ("tactic:TACTIC_ONE", "tactic"),
                ("asset:ASSET_ONE", "asset"),
            ],
            edges=[
                ("directive:DIRECTIVE_SRC", "tactic:TACTIC_ONE", "suggests"),
                ("directive:DIRECTIVE_SRC", "asset:ASSET_ONE", "suggests"),
            ],
        )
        _write_org_pack_config(project_root, [("pack1", "org-packs/pack1")])

        result = _activate_kind_filtered_fixture(
            project_root, "--cascade", "all", "directive", "source-directive"
        )
        assert result.exit_code == 0, result.output
        assert "Cascade-activated: tactic/cascade-tactic" in result.output
        assert (
            "Not cascaded: asset/cascade-asset (kind not charter-activatable)"
            in result.output
        )
        # FR-004 must NOT fire: at least one referenced node landed in `activated`.
        assert "resolved zero activatable targets" not in result.output

    def test_cascade_all_asset_only_source_states_zero_activatable_targets(
        self, project_root: Path
    ) -> None:
        """Scenario 2 (SC-002): a source whose ONLY outgoing reference-relation
        edges target non-activatable kinds explicitly states the cascade
        resolved zero activatable targets. Exit code stays 0 (FR-004).
        """
        pack_root = project_root / "org-packs" / "pack2"
        _write_artifact(pack_root, "directives", "directive", "asset-only-source", "DIRECTIVE_ASSET_ONLY")
        _write_artifact(pack_root, "assets", "asset", "only-asset", "ASSET_ONLY")
        _write_graph_fragment(
            pack_root,
            "fixture.graph.yaml",
            nodes=[
                ("directive:DIRECTIVE_ASSET_ONLY", "directive"),
                ("asset:ASSET_ONLY", "asset"),
            ],
            edges=[("directive:DIRECTIVE_ASSET_ONLY", "asset:ASSET_ONLY", "suggests")],
        )
        _write_org_pack_config(project_root, [("pack2", "org-packs/pack2")])

        result = _activate_kind_filtered_fixture(
            project_root, "--cascade", "all", "directive", "asset-only-source"
        )
        assert result.exit_code == 0, result.output
        assert (
            "Not cascaded: asset/only-asset (kind not charter-activatable)"
            in result.output
        )
        assert "resolved zero activatable targets" in result.output

    def test_cascade_narrow_scope_does_not_trigger_zero_activatable_message(
        self, project_root: Path
    ) -> None:
        """Scenario 4 / SC-007 (over-reporting guard): a source whose referenced
        nodes are ALL activatable-kind but ALL excluded by a narrow
        `--cascade <scope>` must NOT print the FR-004 message -- that case is
        already fully communicated by the existing `Skipped (out of scope)`
        lines, and there are zero kind-filtered nodes involved at all.

        ATDD note: unlike the other three T008 tests, this scenario's
        assertions are already true on `fix/cascade-asset-silent-drop-3705`
        before this WP's implementation exists -- there is no message-printing
        code path yet for ANY input, so "the message is absent" trivially
        holds pre-implementation too. It only becomes a meaningful red-catcher
        against an INCORRECT future implementation that used the broader
        `not result.activated` condition instead of FR-004's exact
        `not result.activated and bool(result.not_cascaded_kind_filtered)` --
        which the mutation-style companion test directly below proves is a
        real risk for this exact fixture, not a vacuous one (T012-style
        non-vacuity proof, mirroring
        `test_org_cascade_chain.py::TestIdMappingWideningNonVacuous`).
        """
        pack_root = project_root / "org-packs" / "pack3"
        _write_artifact(pack_root, "directives", "directive", "narrow-source", "DIRECTIVE_NARROW_SRC")
        _write_artifact(pack_root, "directives", "directive", "narrow-target", "DIRECTIVE_NARROW_TGT")
        _write_graph_fragment(
            pack_root,
            "fixture.graph.yaml",
            nodes=[
                ("directive:DIRECTIVE_NARROW_SRC", "directive"),
                ("directive:DIRECTIVE_NARROW_TGT", "directive"),
            ],
            edges=[("directive:DIRECTIVE_NARROW_SRC", "directive:DIRECTIVE_NARROW_TGT", "suggests")],
        )
        _write_org_pack_config(project_root, [("pack3", "org-packs/pack3")])

        result = _activate_kind_filtered_fixture(
            project_root, "--cascade", "tactic", "directive", "narrow-source"
        )
        assert result.exit_code == 0, result.output
        assert "Skipped (out of scope): directive/narrow-target" in result.output
        assert "resolved zero activatable targets" not in result.output
        assert "Not cascaded" not in result.output

    def test_narrow_scope_guard_scenario_is_not_vacuous(self) -> None:
        """Non-vacuity proof for the guard above (T012-style, mirroring
        `test_org_cascade_chain.py::TestIdMappingWideningNonVacuous`): calls
        the SAME `cascade_activation_targets` engine `_render_cascade_activation`
        calls, over the equivalent pure-scope-narrowing graph, and shows
        directly that the broader `not result.activated` condition alone
        WOULD have evaluated truthy for this exact fixture (`result.activated
        == {}`), while FR-004's exact condition -- which also requires
        `bool(result.not_cascaded_kind_filtered)` -- correctly evaluates
        falsy (`result.not_cascaded_kind_filtered == {}`). This is the
        concrete evidence that the guard test above is not vacuous with
        respect to which condition is chosen.
        """
        graph = DRGGraph(
            schema_version="1.0",
            generated_at="2026-08-17T00:00:00Z",
            generated_by="test",
            nodes=[
                DRGNode(urn="directive:src", kind=NodeKind.DIRECTIVE),
                DRGNode(urn="directive:tgt", kind=NodeKind.DIRECTIVE),
            ],
            edges=[DRGEdge(source="directive:src", target="directive:tgt", relation=Relation.SUGGESTS)],
        )
        scope = CascadeScope.parse("tactic")
        assert scope is not None
        result = cascade_activation_targets(graph, "directive:src", scope)

        assert result.activated == {}, "the broader `not result.activated` condition would be truthy here"
        assert result.not_cascaded_kind_filtered == {}, (
            "FR-004's exact condition adds `and bool(result.not_cascaded_kind_filtered)`, "
            "which must be falsy here -- proving the exact condition (not the broader one) "
            "is what keeps this pure scope-narrowing case from wrongly printing the message"
        )

    def test_mixed_scope_narrowed_and_kind_filtered_does_not_claim_all_kind_filtered(
        self, project_root: Path
    ) -> None:
        """M1 regression (PR #3711 landing review): in the MIXED case -- a
        source with one activatable-kind ref excluded by a narrow
        `--cascade <scope>` AND one kind-filtered ref -- the FR-004 summary
        must NOT fire. `result.activated` is empty, so the original guard
        `not result.activated and bool(result.not_cascaded_kind_filtered)`
        wrongly printed "every referenced node was kind-filtered", directly
        contradicted by the `Skipped (out of scope)` line above it. The guard
        must also require `not result.skipped_by_scope` (SC-007's intent, which
        the inline comment already claimed but the condition did not enforce).
        """
        pack_root = project_root / "org-packs" / "mixed-pack"
        _write_artifact(pack_root, "directives", "directive", "mixed-source", "DIRECTIVE_MIX_SRC")
        _write_artifact(pack_root, "directives", "directive", "mixed-target", "DIRECTIVE_MIX_TGT")
        _write_artifact(pack_root, "assets", "asset", "mixed-asset", "ASSET_MIX_ONE")
        _write_graph_fragment(
            pack_root,
            "fixture.graph.yaml",
            nodes=[
                ("directive:DIRECTIVE_MIX_SRC", "directive"),
                ("directive:DIRECTIVE_MIX_TGT", "directive"),
                ("asset:ASSET_MIX_ONE", "asset"),
            ],
            edges=[
                ("directive:DIRECTIVE_MIX_SRC", "directive:DIRECTIVE_MIX_TGT", "suggests"),
                ("directive:DIRECTIVE_MIX_SRC", "asset:ASSET_MIX_ONE", "suggests"),
            ],
        )
        _write_org_pack_config(project_root, [("mixed-pack", "org-packs/mixed-pack")])

        result = _activate_kind_filtered_fixture(
            project_root, "--cascade", "tactic", "directive", "mixed-source"
        )
        assert result.exit_code == 0, result.output
        # Both facts are reported per-node...
        assert "Skipped (out of scope): directive/mixed-target" in result.output
        assert (
            "Not cascaded: asset/mixed-asset (kind not charter-activatable)"
            in result.output
        )
        # ...but the summary that claims EVERY referenced node was kind-filtered
        # must NOT fire, because a scope-skipped activatable-kind node exists.
        assert "resolved zero activatable targets" not in result.output

    def test_cascade_kind_filtered_line_renders_resolved_config_stem_not_raw_bare_id(
        self, project_root: Path
    ) -> None:
        """The kind-filtered line renders the RESOLVED config-stem ID, not the
        raw DRG bare ID (`drg_urn_to_config_id`'s docstring,
        `_cascade_shared.py`):
        an org-pack-2..N node's bare DRG id and config-stem id differ. This
        assertion fails if the implementation passes the unresolved bare ID
        straight to `render_kind_filtered_line`.
        """
        pack_a_root = project_root / "org-packs" / "packA"
        pack_b_root = project_root / "org-packs" / "packB"
        _write_artifact(pack_a_root, "directives", "directive", "stem-source", "DIRECTIVE_STEM_SRC")
        _write_graph_fragment(
            pack_a_root,
            "fixture.graph.yaml",
            nodes=[("directive:DIRECTIVE_STEM_SRC", "directive")],
            edges=[("directive:DIRECTIVE_STEM_SRC", "asset:ASSET_RAW_BARE_ID", "suggests")],
        )
        _write_artifact(pack_b_root, "assets", "asset", "resolved-asset-stem", "ASSET_RAW_BARE_ID")
        _write_graph_fragment(
            pack_b_root,
            "fixture.graph.yaml",
            nodes=[("asset:ASSET_RAW_BARE_ID", "asset")],
            edges=[],
        )
        _write_org_pack_config(
            project_root, [("packA", "org-packs/packA"), ("packB", "org-packs/packB")]
        )

        result = _activate_kind_filtered_fixture(
            project_root, "--cascade", "all", "directive", "stem-source"
        )
        assert result.exit_code == 0, result.output
        assert (
            "Not cascaded: asset/resolved-asset-stem (kind not charter-activatable)"
            in result.output
        )
        assert "ASSET_RAW_BARE_ID" not in result.output


# ---------------------------------------------------------------------------
# T012 (mission cascade-asset-silent-drop-01M0RME0, WP03) — kind-filtered
# rendering in `_render_no_cascade_warning` (FR-005/FR-005a). Reuses the
# module-level fixture builders (`_write_org_pack_config`, `_write_artifact`,
# `_write_graph_fragment`) and `_activate_kind_filtered_fixture` established
# above by WP02 -- same fixture shape, just invoked WITHOUT `--cascade`.
# ---------------------------------------------------------------------------


class TestNoCascadeKindFilteredRendering:
    """FR-005/FR-005a: `_render_no_cascade_warning` renders kind-filtered nodes too."""

    def test_no_cascade_renders_kind_filtered_asset_alongside_existing_warning(
        self, project_root: Path
    ) -> None:
        """Scenario 1 (spec.md User Story 2): a source with one `suggests` edge
        to an activatable-kind node (`tactic`) and one to a kind-filtered node
        (`asset`), run WITHOUT `--cascade`, renders BOTH the existing
        `[yellow]Warning[/yellow]: referenced .../was not activated (no
        --cascade)` line for the tactic (unchanged wording, unchanged recovery
        hint) AND a new, distinctly-labelled line for the asset that does NOT
        reuse the recovery-hint wording verbatim.
        """
        pack_root = project_root / "org-packs" / "nc-pack1"
        _write_artifact(pack_root, "directives", "directive", "nc-source", "DIRECTIVE_NC_SRC")
        _write_artifact(pack_root, "tactics", "tactic", "nc-tactic", "TACTIC_NC_ONE")
        _write_artifact(pack_root, "assets", "asset", "nc-asset", "ASSET_NC_ONE")
        _write_graph_fragment(
            pack_root,
            "fixture.graph.yaml",
            nodes=[
                ("directive:DIRECTIVE_NC_SRC", "directive"),
                ("tactic:TACTIC_NC_ONE", "tactic"),
                ("asset:ASSET_NC_ONE", "asset"),
            ],
            edges=[
                ("directive:DIRECTIVE_NC_SRC", "tactic:TACTIC_NC_ONE", "suggests"),
                ("directive:DIRECTIVE_NC_SRC", "asset:ASSET_NC_ONE", "suggests"),
            ],
        )
        _write_org_pack_config(project_root, [("nc-pack1", "org-packs/nc-pack1")])

        result = _activate_kind_filtered_fixture(
            project_root, "directive", "nc-source"
        )
        assert result.exit_code == 0, result.output
        assert (
            "Warning: referenced tactic/nc-tactic was not activated (no --cascade)."
            in result.output
        )
        assert (
            "Not cascaded: asset/nc-asset (kind not charter-activatable)"
            in result.output
        )
        # The kind-filtered line must never suggest `--cascade` as a recovery
        # path for a kind-filtered node -- re-running with `--cascade` would
        # NOT activate an asset/template (spec.md FAILS-if, User Story 2).
        # The existing recovery-hint sentence is still fine (it's about the
        # tactic), so scope this check to the kind-filtered line itself.
        kind_filtered_line = next(
            line for line in result.output.splitlines() if "Not cascaded: asset" in line
        )
        assert "--cascade" not in kind_filtered_line

    def test_no_cascade_kind_filtered_only_source_still_renders_despite_empty_skipped(
        self, project_root: Path
    ) -> None:
        """Scenario 2 (spec.md User Story 2, FR-005a): a source whose ONLY
        referenced nodes are kind-filtered (zero activatable-kind refs at
        all) still renders the kind-filtered line when run WITHOUT
        `--cascade`, even though `NoCascadeReport.skipped` is empty and the
        pre-fix `has_skipped` guard (`any(self.skipped.values())` alone)
        would have returned early before ever reaching the render loop --
        reproducing the exact silent-drop bug #3705 reports, one level up,
        inside this mission's own fix.
        """
        pack_root = project_root / "org-packs" / "nc-pack2"
        _write_artifact(pack_root, "directives", "directive", "nc-asset-only-source", "DIRECTIVE_NC_ASSET_ONLY")
        _write_artifact(pack_root, "assets", "asset", "nc-only-asset", "ASSET_NC_ONLY")
        _write_graph_fragment(
            pack_root,
            "fixture.graph.yaml",
            nodes=[
                ("directive:DIRECTIVE_NC_ASSET_ONLY", "directive"),
                ("asset:ASSET_NC_ONLY", "asset"),
            ],
            edges=[("directive:DIRECTIVE_NC_ASSET_ONLY", "asset:ASSET_NC_ONLY", "suggests")],
        )
        _write_org_pack_config(project_root, [("nc-pack2", "org-packs/nc-pack2")])

        result = _activate_kind_filtered_fixture(
            project_root, "directive", "nc-asset-only-source"
        )
        assert result.exit_code == 0, result.output
        assert (
            "Not cascaded: asset/nc-only-asset (kind not charter-activatable)"
            in result.output
        )
        # Implementation choice (beyond T012's letter, in FR-005's spirit):
        # the summary `[yellow]Hint[/yellow]: Re-run with --cascade ...`
        # line is gated on `report.skipped` specifically, not the broader
        # `has_skipped` -- it literally says "to activate the referenced
        # artifacts", which is only true of `skipped` entries. Printing it
        # here (skipped is empty; every referenced node is kind-filtered)
        # would be the same misleading "--cascade would fix this" recovery
        # hint FR-005 forbids for the per-node line, just at the summary
        # level instead. See the non-vacuity proof directly below.
        assert "Re-run with" not in result.output
        assert "Hint" not in result.output

    def test_hint_gate_on_skipped_not_has_skipped_is_not_vacuous(self) -> None:
        """Non-vacuity proof for the assertion above: shows directly that
        `report.has_skipped` (the broader, pre-existing guard) evaluates
        `True` for this exact kind-filtered-only shape while `report.skipped`
        (what the implementation actually gates the Hint line on) evaluates
        falsy -- i.e. gating on `has_skipped` alone WOULD have printed the
        misleading Hint here; gating on `report.skipped` specifically is what
        prevents it. Mirrors WP02's
        `test_narrow_scope_guard_scenario_is_not_vacuous`.
        """
        graph = DRGGraph(
            schema_version="1.0",
            generated_at="2026-08-17T00:00:00Z",
            generated_by="test",
            nodes=[
                DRGNode(urn="directive:src", kind=NodeKind.DIRECTIVE),
                DRGNode(urn="asset:tgt", kind=NodeKind.ASSET),
            ],
            edges=[DRGEdge(source="directive:src", target="asset:tgt", relation=Relation.SUGGESTS)],
        )
        report = referenced_but_not_cascaded(graph, "directive:src")

        assert report.has_skipped, (
            "has_skipped must be True here (kind-filtered nodes present) -- "
            "if it were False, gating the render loop on it (FR-005a) would "
            "itself be the silent-drop bug this WP fixes"
        )
        assert not report.skipped, (
            "skipped must be empty here -- proving that gating the Hint line "
            "on the broader has_skipped (instead of report.skipped) would "
            "have printed the misleading 'Re-run with --cascade to activate "
            "the referenced artifacts' hint despite there being none"
        )

    def test_no_cascade_kind_filtered_line_renders_resolved_config_stem_not_raw_bare_id(
        self, project_root: Path
    ) -> None:
        """The no-cascade kind-filtered line renders the RESOLVED config-stem
        ID, not the raw DRG bare ID (`drg_urn_to_config_id`'s docstring,
        `_cascade_shared.py`): an org-pack-2..N node's bare DRG id and
        config-stem id differ. This assertion fails if the implementation
        passes the unresolved bare ID straight to `render_kind_filtered_line`.
        """
        pack_a_root = project_root / "org-packs" / "nc-packA"
        pack_b_root = project_root / "org-packs" / "nc-packB"
        _write_artifact(pack_a_root, "directives", "directive", "nc-stem-source", "DIRECTIVE_NC_STEM_SRC")
        _write_graph_fragment(
            pack_a_root,
            "fixture.graph.yaml",
            nodes=[("directive:DIRECTIVE_NC_STEM_SRC", "directive")],
            edges=[("directive:DIRECTIVE_NC_STEM_SRC", "asset:ASSET_NC_RAW_BARE_ID", "suggests")],
        )
        _write_artifact(pack_b_root, "assets", "asset", "nc-resolved-asset-stem", "ASSET_NC_RAW_BARE_ID")
        _write_graph_fragment(
            pack_b_root,
            "fixture.graph.yaml",
            nodes=[("asset:ASSET_NC_RAW_BARE_ID", "asset")],
            edges=[],
        )
        _write_org_pack_config(
            project_root, [("nc-packA", "org-packs/nc-packA"), ("nc-packB", "org-packs/nc-packB")]
        )

        result = _activate_kind_filtered_fixture(
            project_root, "directive", "nc-stem-source"
        )
        assert result.exit_code == 0, result.output
        assert (
            "Not cascaded: asset/nc-resolved-asset-stem (kind not charter-activatable)"
            in result.output
        )
        assert "ASSET_NC_RAW_BARE_ID" not in result.output
