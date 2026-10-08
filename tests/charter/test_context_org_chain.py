"""FR-002 (WP03, SPEC-ARCH-002) — ``charter context`` (plain-text AND
``--json``) must resolve the FULL configured org-pack chain, not just pack 1.

Root cause (see this WP's own review finding, SPEC-ARCH-002, and
``spec.md`` User Story 4's "Corrected scope" note): the truncation is not
JSON-only. ``build_charter_context`` already routed through the
self-resolving wrapper ``charter.activation.action_doctrine_bundle._resolve_action_bundle``
— but that wrapper only widens to the full org-pack chain when its caller
passes ``org_root=None``; an *explicit* (already-truncated) ``org_root`` is
honoured verbatim and never widens. ``build_charter_context_json`` had a
SECOND, independent defect on top of this: it called the private
``_load_action_doctrine_bundle`` directly, bypassing ``_resolve_action_bundle``
entirely -- so even a caller passing ``org_root=None`` never widened.

Both halves are required together (T017 stops the CLI-level truncation that
fed an already-narrowed ``org_root`` into both entry points; T018 routes the
JSON path through ``_resolve_action_bundle``, mirroring the plain-text
path). This module proves BOTH are required, empirically, not just that a
plausible-looking fix landed -- see the non-vacuity mutation-matrix evidence
recorded in ``kitty-specs/cascade-org-inert-01M07E9P/
fr002-non-vacuity-mutation-matrix.md`` (also in the PR #3534 description;
there is no separate "WP report" artifact in this repo).

Fixture shape: a minimal action node lives in an isolated (patched) built-in
graph; each org pack contributes its own self-contained ``*.graph.yaml``
fragment declaring one ``directive`` node reached from the action node via a
depth-1 ``scope`` edge (``charter.offering.drg.query.resolve_context``'s step 1 only
walks ``scope`` edges directly off the action URN -- see that function's
docstring), plus a real ``<id>.directive.yaml`` artifact file so the
directive's real content (not just a catalog-miss ID stub) is what's being
proven present, mirroring ``tests/specify_cli/mission_step_contracts/
test_executor.py``'s ``write_org_tier_step_contract_fixture``/
``write_second_org_pack_fixture`` chain-fixture pattern (that module proves
the analogous #3525 DRG-merge fix at the executor seam; this module proves
FR-002's caller-level fix at the ``charter.activation.context`` public API seam).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.context import build_charter_context, build_charter_context_json
from charter.offering.drg.loader import load_graph_or_dir

pytestmark = pytest.mark.fast

_ACTION = "specify"
_MISSION_TYPE = "software-dev"
_ACTION_URN = f"action:{_MISSION_TYPE}/{_ACTION}"

_PACK_A_ID = "ORG_CHAIN_FIXTURE_PACK_A"
_PACK_B_ID = "ORG_CHAIN_FIXTURE_PACK_B"
_PACK_A_URN = f"directive:{_PACK_A_ID}"
_PACK_B_URN = f"directive:{_PACK_B_ID}"


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_project_fixture(repo_root: Path) -> None:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(
        "# Project Charter\n\n## Policy Summary\n\n- Intent: FR-002 org-chain fixture\n",
        encoding="utf-8",
    )
    (charter_dir / "governance.yaml").write_text(
        textwrap.dedent(
            """\
            charter:
              template_set: software-dev-default
              selected_paradigms: []
              selected_directives: []
              available_tools: []
            """
        ),
        encoding="utf-8",
    )


def _write_config(repo_root: Path, org_roots: list[Path]) -> None:
    """Register *org_roots* (declaration order) in ``.kittify/config.yaml``.

    ``mission_type_activations`` is provisioned unconditionally --
    ``PackContext.from_config`` is read on every ``build_charter_context``/
    ``build_charter_context_json`` call and must not hard-fail on a
    genuinely absent key (mirrors ``tests/charter/test_context_org_governance
    .py``'s ``_write_config``).
    """
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["mission_type_activations:", "  - software-dev"]
    if org_roots:
        lines.append("charter_packs:")
        lines.append("  org:")
        lines.append("    packs:")
        for index, root in enumerate(org_roots):
            lines.append(f"      - name: chain-fixture-pack-{index}")
            lines.append(f"        local_path: {root}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_pack(org_root: Path, *, directive_id: str, directive_urn: str) -> None:
    """One self-contained org pack: a real directive artifact + a DRG
    fragment scoping it directly off the action node (depth-1 ``scope``
    edge -- ``resolve_context`` step 1 is the only step that walks edges
    straight from the action URN itself)."""
    directives_dir = org_root / "directives"
    directives_dir.mkdir(parents=True, exist_ok=True)
    (directives_dir / f"{directive_id.lower()}.directive.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: "1.0"
            id: {directive_id}
            title: "{directive_id} fixture directive"
            intent: "Prove org-chain content (FR-002) reaches charter context."
            enforcement: advisory
            """
        ),
        encoding="utf-8",
    )
    (org_root / f"{directive_id.lower()}.graph.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: "1.0"
            generated_at: "2026-08-17T00:00:00Z"
            generated_by: "test"
            nodes:
              - urn: "{directive_urn}"
                kind: directive
                label: "{directive_id} fixture directive"
            edges:
              - source: "{_ACTION_URN}"
                target: "{directive_urn}"
                relation: scope
            """
        ),
        encoding="utf-8",
    )


def _isolated_built_in_graph(tmp_path: Path):
    """A built-in graph containing ONLY the action node this fixture needs
    -- decoupled from the real, evolving built-in doctrine catalog (mirrors
    ``tests/charter/test_org_pack_chain_drg_merge.py``'s ``_empty_built_in``/
    ``_built_in_from`` pattern, extended with the one action node this
    module's ``resolve_context`` traversal needs a start point for)."""
    root = tmp_path / "isolated-built-in-graph"
    root.mkdir(exist_ok=True)
    (root / "graph.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: "1.0"
            generated_at: "2026-08-17T00:00:00Z"
            generated_by: "test"
            nodes:
              - urn: "{_ACTION_URN}"
                kind: action
                label: "Specify"
            edges: []
            """
        ),
        encoding="utf-8",
    )
    return load_graph_or_dir(root)


def _render_both(repo_root: Path, tmp_path: Path) -> tuple[str, dict[str, object]]:
    """Render both the plain-text and JSON ``charter context`` payloads for
    ``_ACTION``, patched onto the isolated built-in graph, calling
    ``build_charter_context``/``build_charter_context_json`` exactly the way
    the FIXED ``context()`` CLI command now does: ``org_root=None`` (T017),
    letting the charter-layer self-resolution walk the full configured
    chain."""
    mock_built_in = _isolated_built_in_graph(tmp_path)
    with patch(
        "charter.activation._drg_helpers.load_built_in_graph",
        return_value=mock_built_in,
    ):
        text_result = build_charter_context(
            repo_root,
            action=_ACTION,
            depth=2,
            mark_loaded=False,
            org_root=None,
            mission_type=_MISSION_TYPE,
        )
        json_payload = build_charter_context_json(
            repo_root,
            action=_ACTION,
            depth=2,
            org_root=None,
            mission_type=_MISSION_TYPE,
        )
    return str(text_result.text), json_payload


def _directive_ids(json_payload: dict[str, object]) -> set[str]:
    directives = json_payload.get("directives", [])
    assert isinstance(directives, list)
    return {entry["id"] for entry in directives}  # type: ignore[index]


# ---------------------------------------------------------------------------
# T019 -- FR-002 AC2: two-pack chain, pack-2-only content, both paths
# ---------------------------------------------------------------------------


class TestTwoPackChainReachesBothPaths:
    """Red-first (pre-fix): pack B's directive is absent from BOTH the JSON
    ``directives`` array and the plain-text ``Action Doctrine`` stanza --
    the JSON path never even threads a chain (bug #1: ``_load_action_doctrine_bundle``
    called directly, no ``org_roots``), and the plain-text path's already-
    "correct" wrapper (``_resolve_action_bundle``) never widens because the
    CLI truncates ``org_root`` to ``org_roots[0]`` before either call (bug #2,
    the CLI-level truncation this WP also owns). Post-fix: pack B's content
    is present in both.

    Non-vacuity: mutating either T017 (CLI truncation removal, modelled here
    by the ``org_root=None`` call convention in ``_render_both``) or T018
    (the internal ``_resolve_action_bundle`` swap in
    ``build_charter_context_json``) back out independently must turn this RED
    again -- recorded via manual revert-and-rerun in
    ``kitty-specs/cascade-org-inert-01M07E9P/
    fr002-non-vacuity-mutation-matrix.md`` (and the PR #3534 description),
    per this mission's stricter-than-default FR-002 test strategy (both
    halves proven necessary, not just the whole change).

    ``_render_both`` above proves T017/T018 at the library-function level
    only (``org_root=None`` passed directly to
    ``build_charter_context``/``build_charter_context_json``, never through
    the real ``charter context`` Typer command). ``TestContextCliTwoPackChain``
    below closes that gap by driving the actual CLI command through
    ``CliRunner`` so a regression of the CLI-level truncation itself
    (reintroducing ``org_root = org_roots[0] if org_roots else None`` at
    ``context.py``'s two call sites) would be caught here too.
    """

    def test_pack_two_directive_present_in_json_and_text(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _write_project_fixture(repo_root)
        org_root_a = tmp_path / "org-pack-a"
        org_root_b = tmp_path / "org-pack-b"
        _write_org_pack(org_root_a, directive_id=_PACK_A_ID, directive_urn=_PACK_A_URN)
        _write_org_pack(org_root_b, directive_id=_PACK_B_ID, directive_urn=_PACK_B_URN)
        _write_config(repo_root, [org_root_a, org_root_b])

        text, payload = _render_both(repo_root, tmp_path)

        # Pack A (declared first) already worked pre-fix for a single pack --
        # a required companion assertion, not the load-bearing one.
        assert _PACK_A_ID in _directive_ids(payload), (
            "regression: pack A (first-declared) dropped out of the JSON "
            "bundle -- the fix must not break the already-working single-pack case"
        )
        assert _PACK_A_ID in text, (
            "regression: pack A dropped out of the plain-text Action Doctrine stanza"
        )

        # Pack B (second-declared) is the load-bearing assertion: it was
        # UNREACHABLE before this WP's fix at this call site, regardless of
        # which single root the pre-fix code happened to resolve.
        assert _PACK_B_ID in _directive_ids(payload), (
            "pack B (second org pack in the chain) is missing from the JSON "
            "``directives`` array -- build_charter_context_json is still "
            "truncating to a single org root instead of resolving the full "
            "configured chain"
        )
        assert _PACK_B_ID in text, (
            "pack B (second org pack in the chain) is missing from the "
            "plain-text ``Action Doctrine`` stanza -- build_charter_context "
            "is still truncating to a single org root"
        )


# ---------------------------------------------------------------------------
# T020(i) -- FR-002 AC1: single healthy org pack, unchanged (no regression)
# ---------------------------------------------------------------------------


class TestSinglePackRegression:
    def test_single_org_pack_content_present_in_json_and_text(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _write_project_fixture(repo_root)
        org_root_a = tmp_path / "org-pack-a"
        _write_org_pack(org_root_a, directive_id=_PACK_A_ID, directive_urn=_PACK_A_URN)
        _write_config(repo_root, [org_root_a])

        text, payload = _render_both(repo_root, tmp_path)

        assert _PACK_A_ID in _directive_ids(payload)
        assert _PACK_A_ID in text


# ---------------------------------------------------------------------------
# T020(ii) -- FR-002 AC3: no org pack configured, unchanged (no regression)
# ---------------------------------------------------------------------------


class TestNoOrgPackRegression:
    def test_no_org_pack_configured_no_org_content_no_crash(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _write_project_fixture(repo_root)
        _write_config(repo_root, [])

        text, payload = _render_both(repo_root, tmp_path)

        assert _PACK_A_ID not in _directive_ids(payload)
        assert _PACK_B_ID not in _directive_ids(payload)
        assert _PACK_A_ID not in text
        assert _PACK_B_ID not in text
        # Bootstrap mode still renders cleanly -- org-inert is a no-op, not a
        # degraded/erroring render.
        assert "Action Doctrine (specify):" in text


# ---------------------------------------------------------------------------
# T021 -- graphless pack in the chain: per-root degrade, healthy packs survive
# ---------------------------------------------------------------------------


class TestGraphlessPackInChainDegradesPerRoot:
    """A chain pack that ships **neither a root-level ``*.graph.yaml`` nor a
    ``drg/fragment.yaml``** contributes no charter-DRG layer, so
    ``load_validated_graph`` skips just that root (``has_graph_files`` is
    ``False``) and ``load_org_drg(strict=False)`` skips it too -- every other,
    healthy pack in the chain still resolves. Per-root degrade, not
    whole-bundle collapse.

    This is the durable per-root behaviour the superseded #3401 was going to
    supply (its guide-shape ``drg/*.graph.yaml`` mechanism was superseded by
    #3387; only this graphless-root runtime sliver survives). It is folded
    into ``_drg_helpers.load_validated_graph``. Before the guard, this call
    site's single ``except DRGLoadError`` wrapper collapsed the WHOLE bundle
    whenever any one root was graphless, taking a structurally-fine sibling
    pack down with it.

    Note (#3530/#3693): a pack's ``drg/fragment.yaml`` is **no longer invisible
    to this runtime path** -- the action-doctrine-bundle seam now threads
    ``load_org_drg(repo_root, strict=False)``, so a *present* fragment is read
    and (when malformed) fails loud. That fragment-is-read behaviour is pinned
    by ``test_action_doctrine_bundle_org_fragment.py`` and
    ``test_org_pack_chain_delivery.py``; this test deliberately ships *no*
    fragment so it isolates the pure graphless-root per-root-degrade case.
    """

    def test_graphless_second_pack_skipped_healthy_pack_survives(
        self, tmp_path: Path
    ) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _write_project_fixture(repo_root)
        org_root_a = tmp_path / "org-pack-a"
        _write_org_pack(org_root_a, directive_id=_PACK_A_ID, directive_urn=_PACK_A_URN)

        # Graphless: the directory exists on disk but ships neither a
        # root-level ``*.graph.yaml`` (has_graph_files is False -> the graph
        # loader skips it) nor a ``drg/fragment.yaml`` (load_org_drg(strict=
        # False) skips it too). The pack therefore contributes nothing.
        org_root_b = tmp_path / "graphless-org-pack-b"
        org_root_b.mkdir(parents=True)
        _write_config(repo_root, [org_root_a, org_root_b])

        # Must not raise, and must not collapse the whole bundle.
        text, payload = _render_both(repo_root, tmp_path)

        # Per-root degrade: pack A (healthy, declared first) survives; the
        # graphless pack B contributes nothing.
        assert _directive_ids(payload) == {_PACK_A_ID}
        assert _PACK_A_ID in text
        assert _PACK_B_ID not in text
        # Still a clean bootstrap render, not a stack trace.
        assert "Action Doctrine (specify):" in text


# ---------------------------------------------------------------------------
# R2-001 (pr-correctness.findings.yaml) -- drive the REAL ``charter context``
# Typer command through CliRunner, not the library functions directly.
#
# Everything above this point calls ``build_charter_context``/
# ``build_charter_context_json`` with a hardcoded ``org_root=None`` literal
# (via ``_render_both``) -- it never imports or invokes
# ``specify_cli.cli.commands.charter.context.context()``, the actual Typer
# command T017 touches. A regression that reintroduces
# ``org_root = org_roots[0] if org_roots else None`` at ``context.py``'s two
# ``build_charter_context``/``build_charter_context_json`` call sites would
# go undetected by every test above. This class closes that gap.
# ---------------------------------------------------------------------------


class TestContextCliTwoPackChain:
    """Same two-org-pack, pack-B-only-content fixture as
    ``TestTwoPackChainReachesBothPaths`` above, but driven through
    ``spec-kitty charter context`` via ``CliRunner`` -- pinning the CLI
    command's own ``org_root=None`` call sites (T017), not just the library
    functions it calls.
    """

    def _invoke(
        self,
        repo_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        json_output: bool,
    ):
        from typer.testing import CliRunner

        import specify_cli.cli.commands.charter as charter_pkg
        from specify_cli.cli.commands.charter import charter_app

        monkeypatch.setattr(charter_pkg, "find_repo_root", lambda: repo_root)

        mock_built_in = _isolated_built_in_graph(tmp_path)
        with patch(
            "charter.activation._drg_helpers.load_built_in_graph",
            return_value=mock_built_in,
        ):
            runner = CliRunner()
            args = ["context", "--action", _ACTION, "--mission-type", _MISSION_TYPE]
            if json_output:
                args.append("--json")
            return runner.invoke(charter_app, args)

    def test_pack_two_directive_present_in_cli_text_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _write_project_fixture(repo_root)
        org_root_a = tmp_path / "org-pack-a"
        org_root_b = tmp_path / "org-pack-b"
        _write_org_pack(org_root_a, directive_id=_PACK_A_ID, directive_urn=_PACK_A_URN)
        _write_org_pack(org_root_b, directive_id=_PACK_B_ID, directive_urn=_PACK_B_URN)
        _write_config(repo_root, [org_root_a, org_root_b])

        result = self._invoke(repo_root, tmp_path, monkeypatch, json_output=False)

        assert result.exit_code == 0, result.output
        assert _PACK_A_ID in result.output, (
            "regression: pack A dropped out of the real CLI's plain-text output"
        )
        assert _PACK_B_ID in result.output, (
            "pack B (second org pack in the chain) is missing from the real "
            "`spec-kitty charter context` plain-text output -- the CLI command "
            "itself is truncating org_root to org_roots[0] again (T017 regressed)"
        )

    def test_pack_two_directive_present_in_cli_json_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _write_project_fixture(repo_root)
        org_root_a = tmp_path / "org-pack-a"
        org_root_b = tmp_path / "org-pack-b"
        _write_org_pack(org_root_a, directive_id=_PACK_A_ID, directive_urn=_PACK_A_URN)
        _write_org_pack(org_root_b, directive_id=_PACK_B_ID, directive_urn=_PACK_B_URN)
        _write_config(repo_root, [org_root_a, org_root_b])

        result = self._invoke(repo_root, tmp_path, monkeypatch, json_output=True)

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        directive_ids = _directive_ids(payload)
        assert _PACK_A_ID in directive_ids, (
            "regression: pack A dropped out of the real CLI's --json output"
        )
        assert _PACK_B_ID in directive_ids, (
            "pack B (second org pack in the chain) is missing from the real "
            "`spec-kitty charter context --json` output -- the CLI command "
            "itself is truncating org_root to org_roots[0] again (T017 regressed)"
        )
        # Same content must also reach the JSON payload's embedded plain-text
        # ``context``/``text`` fields, not just the structured ``directives``
        # array.
        assert _PACK_B_ID in payload["text"]
