"""WP05 -- activation coverage + naming footgun (charter-synthesize-reconciliation-01KZJQN6).

Covers the T023/T023b test list from ``kitty-specs/charter-synthesize-
reconciliation-01KZJQN6/tasks/WP05-activation-coverage-rename.md``:

1. ``charter activate --resynthesize`` over a backed superset overlay
   preserves backed nodes/edges (0 silent drop) -- proves the in-process
   ``run_full_synthesize`` -> ``charter_synthesize`` call reaches the WP01
   preserve seam, not just the CLI's own ``charter synthesize`` entry point.
2. ``charter deactivate --resynthesize`` is symmetric.
3. The renamed function (``run_full_synthesize``, FR-013) is referenced
   directly and the stale name is confirmed gone -- guards against a
   stale-name regression.
4. Sentinel-prune regression (T023b, #3270 re-introduction guard): spies on
   ``charter.activation.synthesizer.synthesize``'s ``mode=`` kwarg to prove the
   explicit ``prune=False`` passed at the WP05 call site resolves to
   ``SynthesizeMode.preserve`` for BOTH ``activate`` and ``deactivate`` --
   an in-process caller that forgot the explicit flag would leak a truthy
   ``OptionInfo`` sentinel into ``prune`` and silently start pruning.
5. Corrupt-overlay-via-activate (in-process fail-closed): an unparseable
   on-disk ``graph.yaml`` hit through ``activate --resynthesize`` fails
   closed (exit 1, no write) -- proving the WP01 library-seam guard (FR-007)
   fires on this in-process path too, since it bypasses WP03's CLI.

Real behavior throughout, mirroring the narrow-mocking convention already
established by ``test_synthesize_cli_reconcile.py`` (WP03) and
``test_resynthesize_and_hotpath.py`` (WP05's own ``--resynthesize`` flag
suite): only ``find_repo_root``/``_collect_evidence_result``/
``_build_synthesis_request`` are mocked so the CLI's own reconciliation
policy and the WP01 library seam run for real; ``generate`` is faked (a
no-op) because this WP's owned surface is "does activate/deactivate call
generate+synthesize with the right explicit flags", not "does generate
itself regenerate references correctly" (covered by other WPs' suites).
"""

from __future__ import annotations

import importlib
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.interview import default_interview, write_interview_answers
from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget, synthesize
from charter.activation.synthesizer.reconcile import SynthesizeMode
from tests.specify_cli.charter_preflight._fixtures import init_git_repo
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

generate_module = importlib.import_module("specify_cli.cli.commands.charter.generate")

# Real, stable built-in artifacts -- production-shaped ids, matching the
# pinning convention this mission's other suites already established
# (tests/specify_cli/charter_runtime/test_freshness_activation_visibility.py,
# tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py).
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_LEGACY_URN = "tactic:legacy-preference-order-3270"
_LEGACY_EDGE_TARGET = "directive:DIRECTIVE_003"


# ---------------------------------------------------------------------------
# Shared setup helpers -- deliberately local, mirroring
# tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py's
# own helpers rather than importing them (this WP owns activate.py/
# deactivate.py + this test file only, not the WP03 CLI suite).
# ---------------------------------------------------------------------------


def _minimal_interview_snapshot() -> dict[str, Any]:
    return {
        "mission_type": "software_dev",
        "language_scope": ["python"],
        "testing_philosophy": "test-driven development with high coverage",
        "neutrality_posture": "balanced",
        "selected_directives": ["DIRECTIVE_003"],
        "risk_appetite": "moderate",
    }


def _minimal_doctrine_snapshot() -> dict[str, Any]:
    return {
        "directives": {
            "DIRECTIVE_003": {
                "id": "DIRECTIVE_003",
                "title": "Decision Documentation",
                "body": "Document significant architectural decisions via ADRs.",
            }
        },
        "tactics": {},
        "styleguides": {},
    }


def _minimal_drg_snapshot() -> dict[str, Any]:
    return {
        "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
        "edges": [],
        "schema_version": "1",
    }


def _request(run_id: str) -> SynthesisRequest:
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot=_minimal_interview_snapshot(),
        doctrine_snapshot=_minimal_doctrine_snapshot(),
        drg_snapshot=_minimal_drg_snapshot(),
        run_id=run_id,
        adapter_hints={"language": "python"},
    )


def _minimal_project(repo_root: Path) -> Path:
    """A minimal project with only ``.kittify/config.yaml`` (no charter bundle).

    Carries ``mission_type_activations`` (WP04, C-A1): the provisioned
    charter is the sole mission-type activation authority, so
    ``PackContext.from_config`` fails closed when the key is absent.
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    init_git_repo(repo_root)
    write_interview_answers(repo_root / ".kittify/charter/interview/answers.yaml", default_interview(mission="software-dev"))
    return repo_root


def _seed_complete_bundle(repo_root: Path) -> None:
    """Materialize ``charter.yaml`` so the #2758 fail-closed preflight passes."""
    charter_yaml = repo_root / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.parent.mkdir(parents=True, exist_ok=True)
    charter_yaml.write_text(
        "schema_version: '2.0.0'\ngovernance: {}\ndirectives: {}\n",
        encoding="utf-8",
    )


def _seed_generated_marker(repo_root: Path) -> None:
    """Seed a placeholder agent-authored YAML so ``_has_generated_artifacts`` is True.

    ``run_full_synthesize`` always passes ``adapter="generated"`` at its
    in-process ``charter_synthesize`` call site. Without this marker,
    ``_has_generated_artifacts`` reads False and the T032 fresh-project
    short-circuit fires -- it returns BEFORE the WP01 reconcile seam runs at
    all, which would silently swallow both this WP's preserve and
    fail-closed assertions. ``_build_synthesis_request`` is mocked in every
    test below, so only the marker's PRESENCE matters, not its content.
    """
    directives_dir = repo_root / ".kittify" / "charter" / "generated" / "directives"
    directives_dir.mkdir(parents=True, exist_ok=True)
    (directives_dir / "placeholder.yaml").write_text("id: PLACEHOLDER\n", encoding="utf-8")


def _graph_yaml() -> YAML:
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    return yaml


def _load_graph(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", _graph_yaml().load(path.read_text()))


def _dump_graph(path: Path, data: dict[str, Any]) -> None:
    buffer = io.StringIO()
    _graph_yaml().dump(data, buffer)
    path.write_text(buffer.getvalue())


def _graph_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / "doctrine" / "graph.yaml"


def _manifest_path(repo_root: Path) -> Path:
    from charter.activation.synthesizer.manifest import MANIFEST_PATH

    return repo_root / MANIFEST_PATH


def _inject_backed_legacy_content(repo_root: Path) -> None:
    """Append a backed (artifact file present) on-disk-only node+edge.

    Mirrors ``test_synthesize_cli_reconcile.py``'s own injection helper: a
    genuine "preserved-but-untargeted" case with a real backing artifact
    file, so it is never orphaned -- the WP01 preserve seam retains it, a
    prune run would remove it.
    """
    import hashlib

    from charter.activation.synthesizer.manifest import ManifestArtifactEntry, finalize_manifest, load_yaml as load_manifest
    from charter.activation.synthesizer.provenance import load_yaml as load_provenance
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

    doctrine_dir = repo_root / ".kittify" / "doctrine"
    graph_path = _graph_path(repo_root)
    graph = _load_graph(graph_path)
    graph["nodes"].append(
        {"urn": _LEGACY_URN, "kind": "tactic", "label": "Legacy Preference Order Tactic (3270)"}
    )
    graph.setdefault("edges", []).append(
        {
            "source": _LEGACY_URN,
            "target": _LEGACY_EDGE_TARGET,
            "relation": "applies",
            "reason": "Derived from synthesis target 'legacy-preference-order-3270'",
        }
    )
    _dump_graph(graph_path, graph)

    existing_artifact = doctrine_dir / "tactic" / "how-we-apply-directive-003.tactic.yaml"
    legacy_artifact = doctrine_dir / "tactic" / "legacy-preference-order-3270.tactic.yaml"
    legacy_content = YAML().load(existing_artifact.read_text())
    legacy_content["id"] = _LEGACY_URN.split(":", 1)[1]
    with legacy_artifact.open("w") as stream:
        YAML().dump(legacy_content, stream)

    # Register a manifest + provenance entry so the backing-artifact probe
    # (reconcile._backing_path_by_urn) resolves this URN as BACKED, not
    # orphaned -- mirroring what a real prior synthesis run would have
    # written for it.
    rel_content = ".kittify/doctrine/tactic/legacy-preference-order-3270.tactic.yaml"
    rel_prov = ".kittify/charter/provenance/tactic-legacy-preference-order-3270.yaml"
    content_hash = hashlib.sha256(legacy_artifact.read_bytes()).hexdigest()  # noqa: TID251 -- test-only fixture hash, not a production owner

    manifest_path = _manifest_path(repo_root)
    manifest = load_manifest(manifest_path)
    new_entry = ManifestArtifactEntry(
        kind="tactic",
        slug="legacy-preference-order-3270",
        path=rel_content,
        provenance_path=rel_prov,
        content_hash=content_hash,
    )
    updated_manifest = finalize_manifest(manifest.model_copy(update={"artifacts": [*manifest.artifacts, new_entry]}))
    manifest_path.write_text(
        canonical_yaml(updated_manifest.model_dump(mode="python")).decode("utf-8"), encoding="utf-8"
    )

    existing_prov_path = repo_root / ".kittify" / "charter" / "provenance" / "tactic-how-we-apply-directive-003.yaml"
    existing_prov_entry = load_provenance(existing_prov_path)
    legacy_prov_entry = existing_prov_entry.model_copy(
        update={
            "artifact_slug": "legacy-preference-order-3270",
            "artifact_urn": _LEGACY_URN,
            "artifact_content_hash": content_hash,
        }
    )
    (repo_root / rel_prov).write_bytes(canonical_yaml(legacy_prov_entry.model_dump(mode="python")))


def _seed_baseline_overlay(repo_root: Path) -> None:
    """Establish a REAL on-disk overlay + backed legacy content via the library seam.

    A real prior ``synthesize()`` call (``FixtureAdapter``) creates
    ``.kittify/doctrine/graph.yaml`` + the synthesis manifest, then a backed
    legacy node/edge is appended -- the "backed superset overlay" this WP's
    own in-process resynthesize run must preserve (or, for the corrupt-
    overlay test, the file that gets truncated).
    """
    adapter = FixtureAdapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=repo_root)


def _invoke_with_resynthesize(
    command: str,
    repo_root: Path,
    request: SynthesisRequest,
    syn_adapter: Any,
    *extra_args: str,
) -> tuple[Any, Mock]:
    """Invoke ``charter <command> ... --resynthesize`` with narrow, real-behavior mocks.

    Mocks only ``find_repo_root``/``_collect_evidence_result``/
    ``_build_synthesis_request`` (the same narrow-mocking convention
    ``test_synthesize_cli_reconcile.py`` established) plus fakes ``generate``
    (a no-op -- WP05 does not own the generate pipeline). Every other line
    from ``activate_cmd``/``deactivate_cmd`` through ``run_full_synthesize``
    to the real ``charter.activation.synthesizer.synthesize`` reconcile seam runs for
    real. Returns ``(CliRunner result, synthesize spy)`` so callers can
    additionally assert on the ``mode=`` kwarg actually passed (T023b).
    """
    synth_spy = Mock(wraps=synthesize)
    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=repo_root),
        patch(
            "specify_cli.cli.commands.charter._collect_evidence_result",
            return_value=SimpleNamespace(warnings=[], bundle=SimpleNamespace()),
        ),
        patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            return_value=(request, syn_adapter),
        ),
        patch.object(generate_module, "generate", Mock(return_value=None)),
        patch("charter.activation.synthesizer.synthesize", synth_spy),
    ):
        result = runner.invoke(
            charter_app,
            [command, "--repo-root", str(repo_root), *extra_args, "--resynthesize"],
            catch_exceptions=False,
        )
    return result, synth_spy


# ---------------------------------------------------------------------------
# 1/2 -- activate/deactivate --resynthesize preserve backed overlay content
# ---------------------------------------------------------------------------


def test_activate_resynthesize_preserves_backed_overlay_content(tmp_path: Path) -> None:
    """``activate --resynthesize`` over a backed superset overlay drops nothing."""
    project_root = _minimal_project(tmp_path)
    _seed_complete_bundle(project_root)
    _seed_generated_marker(project_root)
    _seed_baseline_overlay(project_root)
    _inject_backed_legacy_content(project_root)

    result, _spy = _invoke_with_resynthesize(
        "activate",
        project_root,
        _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"),
        FixtureAdapter(),
        "directive",
        _REAL_DIRECTIVE_STEM,
    )

    assert result.exit_code == 0, result.output
    graph = _load_graph(_graph_path(project_root))
    node_urns = {n["urn"] for n in graph["nodes"]}
    assert _LEGACY_URN in node_urns, (
        "activate --resynthesize silently dropped backed overlay content"
    )
    assert any(e["source"] == _LEGACY_URN for e in graph.get("edges", [])), (
        "activate --resynthesize dropped the legacy node's edge"
    )


def test_deactivate_resynthesize_preserves_backed_overlay_content(tmp_path: Path) -> None:
    """``deactivate --resynthesize`` is symmetric: preserves backed content too."""
    project_root = _minimal_project(tmp_path)
    (project_root / ".kittify" / "config.yaml").write_text(
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    _seed_complete_bundle(project_root)
    _seed_generated_marker(project_root)
    _seed_baseline_overlay(project_root)
    _inject_backed_legacy_content(project_root)

    result, _spy = _invoke_with_resynthesize(
        "deactivate",
        project_root,
        _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"),
        FixtureAdapter(),
        "directive",
        _REAL_DIRECTIVE_STEM,
    )

    assert result.exit_code == 0, result.output
    graph = _load_graph(_graph_path(project_root))
    node_urns = {n["urn"] for n in graph["nodes"]}
    assert _LEGACY_URN in node_urns, (
        "deactivate --resynthesize silently dropped backed overlay content"
    )


# ---------------------------------------------------------------------------
# 3 -- renamed function is the live symbol (FR-013 stale-name regression guard)
# ---------------------------------------------------------------------------


def test_renamed_function_is_the_live_symbol() -> None:
    """FR-013: ``run_full_synthesize`` is the live symbol; the old name is gone."""
    import specify_cli.cli.commands.charter.activate as activate_mod
    import specify_cli.cli.commands.charter.deactivate as deactivate_mod

    assert hasattr(activate_mod, "run_full_synthesize"), (
        "the renamed function must exist on activate.py"
    )
    assert not hasattr(activate_mod, "run_resynthesize_pipeline"), (
        "the mis-named symbol must be gone, not aliased"
    )
    # C-006 reconciliation (#4785 WP03): deactivate.py no longer imports
    # run_full_synthesize directly -- it imports the shared
    # recompile_or_notify tail activate.py defines (T012/T013 campsite),
    # which is what now calls run_full_synthesize under --resynthesize. The
    # invariant this test protects (deactivate calls the SAME full-synthesize
    # pipeline activate does, never a re-implementation) still holds -- it is
    # now witnessed one level up, at the shared seam both commands route
    # through, rather than as a direct attribute on deactivate_mod.
    assert not hasattr(deactivate_mod, "run_full_synthesize"), (
        "deactivate.py should route through the shared recompile_or_notify "
        "seam, not re-import run_full_synthesize directly"
    )
    assert activate_mod.recompile_or_notify is deactivate_mod.recompile_or_notify, (
        "deactivate.py must import the SAME shared tail activate.py defines "
        "(recompile_or_notify) -- the single call site that invokes "
        "run_full_synthesize under --resynthesize for both commands"
    )
    docstring = activate_mod.run_full_synthesize.__doc__ or ""
    assert "full" in docstring.lower() and "synthesize" in docstring.lower(), (
        "the renamed function's docstring should clarify it calls FULL synthesize"
    )


# ---------------------------------------------------------------------------
# 4 -- T023b sentinel-prune regression (#3270): activate/deactivate never
# leak the truthy OptionInfo sentinel into `prune`.
#
# The first two tests isolate the WP05-OWNED call site inside
# ``run_full_synthesize`` from ``synthesize.py``'s own ``_coerce_cli_bool``
# belt-and-suspenders guard (WP03) by mocking ``charter_synthesize`` itself
# (not the underlying ``synthesize()`` library call) and asserting on the
# ``prune``/``dry_run`` kwargs it actually received -- this is what proves
# the explicit keyword is present at the CALL SITE per se: dropping
# ``prune=False`` from ``activate.py``/``deactivate.py`` would still be
# masked end-to-end by WP03's belt-and-suspenders coercion (verified: a
# local revert of the WP05 fix alone left the heavier integration variant
# below green), so only a call-site-level assertion actually regresses on
# that specific mistake. The heavier integration tests that follow keep the
# real ``synthesize()``/``mode=`` behavioral corroboration.
# ---------------------------------------------------------------------------


def test_activate_resynthesize_call_site_passes_prune_false_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T023b (#3270): the ``run_full_synthesize`` call site passes real ``prune=False``.

    Patches ``charter_synthesize`` (the CLI command body itself) so this
    test is blind to ``_coerce_cli_bool``'s own downstream save -- it fails
    if the explicit ``prune=False``/``dry_run=False`` keywords are ever
    dropped from the ``activate.py`` call site, which the belt-and-
    suspenders coercion alone would NOT catch.
    """
    project_root = _minimal_project(tmp_path)
    synthesize_module = importlib.import_module("specify_cli.cli.commands.charter.synthesize")
    mock_generate = Mock(return_value=None)
    mock_synthesize = Mock(return_value=None)
    monkeypatch.setattr(generate_module, "generate", mock_generate)
    monkeypatch.setattr(synthesize_module, "charter_synthesize", mock_synthesize)

    result = runner.invoke(
        charter_app,
        [
            "activate",
            "--repo-root",
            str(project_root),
            "directive",
            _REAL_DIRECTIVE_STEM,
            "--resynthesize",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert mock_synthesize.call_count == 1
    assert mock_synthesize.call_args.kwargs["prune"] is False, (
        "run_full_synthesize must pass prune=False explicitly -- an omitted "
        "keyword would resolve to Typer's truthy OptionInfo sentinel and "
        "silently prune (#3270)"
    )
    assert mock_synthesize.call_args.kwargs["dry_run"] is False


def test_deactivate_resynthesize_call_site_passes_prune_false_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T023b (#3270): the ``deactivate`` --resynthesize call site is symmetric."""
    project_root = _minimal_project(tmp_path)
    (project_root / ".kittify" / "config.yaml").write_text(
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    synthesize_module = importlib.import_module("specify_cli.cli.commands.charter.synthesize")
    mock_generate = Mock(return_value=None)
    mock_synthesize = Mock(return_value=None)
    monkeypatch.setattr(generate_module, "generate", mock_generate)
    monkeypatch.setattr(synthesize_module, "charter_synthesize", mock_synthesize)

    result = runner.invoke(
        charter_app,
        [
            "deactivate",
            "--repo-root",
            str(project_root),
            "directive",
            _REAL_DIRECTIVE_STEM,
            "--resynthesize",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert mock_synthesize.call_count == 1
    assert mock_synthesize.call_args.kwargs["prune"] is False, (
        "run_full_synthesize must pass prune=False explicitly -- an omitted "
        "keyword would resolve to Typer's truthy OptionInfo sentinel and "
        "silently prune (#3270)"
    )
    assert mock_synthesize.call_args.kwargs["dry_run"] is False


def test_activate_resynthesize_never_enters_prune_mode(tmp_path: Path) -> None:
    """Behavioral corroboration: ``activate --resynthesize`` synthesizes in preserve mode."""
    project_root = _minimal_project(tmp_path)
    _seed_complete_bundle(project_root)
    _seed_generated_marker(project_root)
    _seed_baseline_overlay(project_root)
    _inject_backed_legacy_content(project_root)

    result, synth_spy = _invoke_with_resynthesize(
        "activate",
        project_root,
        _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"),
        FixtureAdapter(),
        "directive",
        _REAL_DIRECTIVE_STEM,
    )

    assert result.exit_code == 0, result.output
    assert synth_spy.call_count == 1
    assert synth_spy.call_args.kwargs["mode"] is SynthesizeMode.preserve, (
        "activate --resynthesize must never leak an unset OptionInfo sentinel "
        "into `prune` -- it must call synthesize() in explicit preserve mode"
    )
    # Behavioral corroboration: preserve mode really did keep the backed node.
    graph = _load_graph(_graph_path(project_root))
    assert {n["urn"] for n in graph["nodes"]} >= {_LEGACY_URN}


def test_deactivate_resynthesize_never_enters_prune_mode(tmp_path: Path) -> None:
    """Behavioral corroboration: ``deactivate --resynthesize`` synthesizes in preserve mode."""
    project_root = _minimal_project(tmp_path)
    (project_root / ".kittify" / "config.yaml").write_text(
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    _seed_complete_bundle(project_root)
    _seed_generated_marker(project_root)
    _seed_baseline_overlay(project_root)
    _inject_backed_legacy_content(project_root)

    result, synth_spy = _invoke_with_resynthesize(
        "deactivate",
        project_root,
        _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"),
        FixtureAdapter(),
        "directive",
        _REAL_DIRECTIVE_STEM,
    )

    assert result.exit_code == 0, result.output
    assert synth_spy.call_count == 1
    assert synth_spy.call_args.kwargs["mode"] is SynthesizeMode.preserve, (
        "deactivate --resynthesize must never leak an unset OptionInfo sentinel "
        "into `prune` -- it must call synthesize() in explicit preserve mode"
    )


# ---------------------------------------------------------------------------
# 5 -- Corrupt-overlay-via-activate: in-process fail-closed (FR-007)
# ---------------------------------------------------------------------------


def test_corrupt_overlay_via_activate_fails_closed_with_no_write(tmp_path: Path) -> None:
    """An unparseable ``graph.yaml`` hit through ``activate --resynthesize`` fails closed.

    Uses ``kind="mission-type"`` (a kind with no DRG artifact-node
    representation, so ``_source_urn`` short-circuits to ``None``) so the
    ONLY code path that touches ``graph.yaml`` before this assertion is the
    ``--resynthesize`` call itself -- proving the WP01 library-seam guard
    (FR-007) fires on the in-process ``activate`` path (which bypasses
    WP03's CLI), not some unrelated cascade-rendering read.
    """
    project_root = _minimal_project(tmp_path)
    _seed_complete_bundle(project_root)
    _seed_generated_marker(project_root)
    _seed_baseline_overlay(project_root)

    manifest_path = _manifest_path(project_root)
    manifest_before = manifest_path.read_bytes()

    # Half-written / unparseable YAML (truncated mapping, bad indentation) --
    # same corruption shape WP01's and WP03's own fail-closed suites use.
    _graph_path(project_root).write_text(
        "schema_version: '1.0'\nnodes: [\n  {urn: broken\n", encoding="utf-8"
    )

    result, _spy = _invoke_with_resynthesize(
        "activate",
        project_root,
        _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"),
        FixtureAdapter(),
        "mission-type",
        "research",
    )

    assert result.exit_code == 1, result.output
    assert manifest_path.read_bytes() == manifest_before, (
        "a corrupt-overlay refusal reached through activate must not rewrite the manifest"
    )
