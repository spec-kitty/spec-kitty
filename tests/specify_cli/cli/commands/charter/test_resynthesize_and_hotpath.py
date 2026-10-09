"""Tests for WP05/T017-T020: ``--resynthesize`` opt-in + NFR-001/NFR-003 hot-path guards.

``charter activate``/``deactivate`` mutate ``.kittify/config.yaml``, which WP03
(#2759) made visible to the freshness read-path -- a config<->references or
config<->graph parity mismatch now resolves to ``stale`` instead of silently
``fresh``. This WP (#2761) gives operators an opt-in escape hatch,
``--resynthesize``, that eagerly reconciles that signal back to fresh as part
of the activation command, while the DEFAULT (no-flag) path stays exactly as
cheap as before -- a config-only write, zero synthesis.

Covers:

- T017 (red-first NFR-001 guard, folded into the same suite as T018/T019 --
  the guard is written first and asserts the TARGET behavior, which already
  holds today since ``activate.py``/``deactivate.py`` have no synthesis
  reference at all before this WP; it becomes the regression net proving the
  new ``--resynthesize`` seam does not leak eager work onto the default path):
  ``test_default_activate_triggers_zero_synthesis_calls`` /
  ``test_default_deactivate_triggers_zero_synthesis_calls``.
- T018 (the flag, reusing the EXISTING synthesize pipeline -- single
  authority, C-007-style reuse, not a parallel implementation):
  ``test_activate_resynthesize_invokes_existing_pipeline_exactly_once`` /
  ``test_deactivate_resynthesize_invokes_existing_pipeline_exactly_once``
  prove the flag calls the REAL ``generate``/``charter_synthesize`` command
  objects (identity-checked via patched call-count spies), not a duplicate.
- T019 (behavior): ``--resynthesize`` -> signal FRESH immediately;
  default -> signal STALE and the spy records ZERO synthesis calls;
  ``deactivate`` symmetric; NFR-003 ``promote_activations`` migration path
  triggers no synthesis.
- T020 (gate) is enforced by CI, not a test in this file.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import Mock

from charter.activation.interview import default_interview, write_interview_answers

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.activation_engine import promote_activations
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import CharterPackManager
from specify_cli.charter_runtime.freshness import compute_freshness
from specify_cli.cli.commands.charter import charter_app

from charter.activation.charter_yaml_io import update_charter_yaml_section

from tests.specify_cli.charter_preflight._fixtures import (
    init_git_repo,
    seed_charter,
    seed_charter_yaml,
    seed_manifest,
    write_metadata,
)

runner = CliRunner()

pytestmark = [pytest.mark.git_repo]

# ``specify_cli.cli.commands.charter.__init__`` re-exports ``generate``/
# ``charter_synthesize`` as plain-function package attributes (the test-patch
# shim documented in ``synthesize.py``), which SHADOWS the submodule name at
# the package-attribute level: ``import specify_cli...generate as X`` (or
# ``from specify_cli...charter import generate``) resolves via attribute
# traversal and would silently bind ``X`` to the FUNCTION, not the module --
# patching that would never be seen by ``run_full_synthesize``'s lazy
# ``from ...generate import generate as _generate`` (which reads the
# submodule's OWN namespace via ``sys.modules``, not package-attribute
# traversal). ``importlib.import_module`` returns the real submodule
# unconditionally, so patch ITS ``generate``/``charter_synthesize``
# attribute.
generate_module = importlib.import_module("specify_cli.cli.commands.charter.generate")
synthesize_module = importlib.import_module("specify_cli.cli.commands.charter.synthesize")

# Real, stable built-in artifacts -- production-shaped ids, matching the
# pinning rationale WP03's own freshness-visibility suite established
# (tests/specify_cli/charter_runtime/test_freshness_activation_visibility.py).
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_REAL_DIRECTIVE_CANONICAL = "DIRECTIVE_001"
_REAL_PARADIGM_STEM_A = "domain-driven-design"
_REAL_PARADIGM_STEM_B = "atomic-design"


# ---------------------------------------------------------------------------
# Fixture helpers -- deliberately local (not imported from the WP03 freshness
# suite): this WP's owned surface is ``activate.py``/``deactivate.py`` + this
# test file, not ``charter_runtime/freshness``, so the small seed helpers are
# duplicated rather than reaching into a sibling WP's private test module.
# ---------------------------------------------------------------------------


def _minimal_project(tmp_path: Path) -> Path:
    """A minimal project with only ``.kittify/config.yaml`` (no charter bundle).

    Carries ``mission_type_activations`` (WP04, C-A1): the provisioned
    charter is the sole mission-type activation authority, so
    ``PackContext.from_config`` fails closed when the key is absent.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    init_git_repo(tmp_path)
    write_interview_answers(tmp_path / ".kittify/charter/interview/answers.yaml", default_interview(mission="software-dev"))
    return tmp_path


def _write_config(repo: Path, content: str) -> None:
    kittify = repo / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _reference_entry(ref_id: str, kind: str) -> dict[str, str]:
    return {
        "id": ref_id,
        "kind": kind,
        "title": "x",
        "summary": "x",
        "source_path": "",
        "local_path": "x",
    }


def _write_references(charter_dir: Path, entries: list[dict[str, str]]) -> None:
    charter_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "generated_at": "2026-07-17T00:00:00Z",
        "mission": "software-dev",
        "template_set": "software-dev-default",
        "languages": ["python"],
        "references": entries,
    }
    yaml = YAML()
    yaml.default_flow_style = False
    with (charter_dir / "references.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def _seed_project_graph(repo: Path) -> Path:
    """Create a schema-valid, empty ``.kittify/charter-packs/graph.yaml``.

    Matches ``test_freshness_activation_visibility.py``'s own local helper:
    a bare ``schema_version``/``nodes``/``edges`` document is REJECTED by
    ``charter.offering.drg.models.DRGGraph`` (``generated_at``/``generated_by`` are
    required) once ``charter.activation.consistency_check``'s graph-kind-parity check
    pydantic-validates it via ``load_validated_graph``.
    """
    graph_path = repo / ".kittify" / "charter-packs" / "graph.yaml"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(
        dedent(
            """\
            schema_version: '1.0'
            generated_at: '2026-07-17T00:00:00Z'
            generated_by: test-fixture
            nodes: []
            edges: []
            """
        ),
        encoding="utf-8",
    )
    return graph_path


def _seed_synthesized_repo(
    repo: Path,
    ref_entries: list[dict[str, str]],
    activation: dict[str, list[str]] | None = None,
) -> Path:
    """Build a fully-synthesized, freshness-``fresh`` repo and return its charter dir.

    Post-#2773 the freshness read-path resolves ``.kittify/charter/charter.yaml``
    (``compute_bundle_content_hash`` hashes that one authoritative file, the
    retired ``governance.yaml``/``directives.yaml``/``metadata.yaml`` triad no
    longer feeds it -- see ``freshness/computer.py`` docstring). So a genuinely
    ``fresh`` seed must:

    1. seed ``charter.yaml`` (:func:`seed_charter_yaml`) -- the resolving source;
    2. bake any pre-existing ``activation`` state INTO ``charter.yaml`` (its
       post-#2773 home, data-model.md) BEFORE stamping the manifest, so the
       stamped ``bundle_content_hash`` matches a fresh recompute of the seeded
       charter.yaml (precondition reads ``fresh``);
    3. write ``.kittify/config.yaml`` with a repo-root-relative ``charter:``
       pointer so ``activate``/``deactivate`` route their write INTO
       ``charter.yaml`` (the migrated-project path). That write flips the
       whole-file hash away from the stamped manifest hash, which is exactly
       what makes the default (no-``--resynthesize``) path observably ``stale``
       after the mutation (the "spurious authoring-staleness" the freshness
       computer documents as expected, self-clearing behaviour).

    The retired triad + ``charter.md``/``metadata.yaml`` seeding is kept as a
    harmless companion (some non-freshness consumers under test still reference
    it); it no longer drives freshness on its own.
    """
    init_git_repo(repo)
    write_interview_answers(repo / ".kittify/charter/interview/answers.yaml", default_interview(mission="software-dev"))
    charter_path, metadata_path = seed_charter(repo)
    write_metadata(metadata_path, charter_path)
    charter_dir = repo / ".kittify" / "charter"
    (charter_dir / "governance.yaml").write_text("schema_version: '1'\n", encoding="utf-8")
    (charter_dir / "directives.yaml").write_text("schema_version: '1'\n", encoding="utf-8")
    _write_references(charter_dir, ref_entries)
    charter_yaml_path = seed_charter_yaml(repo)
    # Bake the pre-mutation activation state into charter.yaml BEFORE the
    # manifest is stamped, so the recomputed bundle hash covers it and the
    # precondition reads ``fresh``. ``mission_type_activations`` is always
    # baked (WP04, C-A1): the provisioned charter (here, this fixture's
    # charter.yaml, which config.yaml's ``charter:`` pointer routes activation
    # reads to) is the sole mission-type activation authority, so
    # ``PackContext.from_config`` fails closed when the key is absent.
    update_charter_yaml_section(
        charter_yaml_path,
        "activation",
        {"mission_type_activations": ["software-dev"], **(activation or {})},
    )
    seed_manifest(repo, built_in_only=False)
    _seed_project_graph(repo)
    # Migrated-project shape: config.yaml points at charter.yaml so activation
    # writes land in charter.yaml (the hash input), not the legacy config keys.
    (repo / ".kittify" / "config.yaml").write_text(
        "charter: .kittify/charter/charter.yaml\n", encoding="utf-8"
    )
    return charter_dir


def _ctx(repo: Path) -> ProjectContext:
    return ProjectContext.from_repo(repo)


def _synthesized_drg_state(repo: Path) -> str:
    return compute_freshness(repo).synthesized_drg.state


def _invoke(subcommand: str, project_root: Path, *args: str) -> Any:
    return runner.invoke(
        charter_app,
        [subcommand, "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


def _patch_synthesis_spies(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    """Replace the real ``generate``/``charter_synthesize`` entry points with spies.

    Patched on the SOURCE modules -- ``run_full_synthesize`` imports
    them lazily (``from ...generate import generate as _generate``) inside
    its own body, so the patched object is what the lazy import resolves at
    call time.
    """
    mock_generate = Mock(return_value=None)
    mock_synthesize = Mock(return_value=None)
    monkeypatch.setattr(generate_module, "generate", mock_generate)
    monkeypatch.setattr(synthesize_module, "charter_synthesize", mock_synthesize)
    return mock_generate, mock_synthesize


def _reconcile_via_fakes(monkeypatch: pytest.MonkeyPatch, repo: Path, charter_dir: Path, ref_entries: list[dict[str, str]]) -> None:
    """Patch the two entry points with fakes that perform a REAL reconcile.

    Mirrors what the real ``charter generate`` (recompile references.yaml)
    + ``charter synthesize`` (re-stamp the manifest hash) pair does --
    matching ``test_freshness_activation_visibility.py``'s own
    ``_reconcile_references`` simulation -- so the ORCHESTRATION (this WP's
    owned surface: does activate.py call both, in the right order, after the
    config write) is exercised without depending on the full production
    synthesize pipeline's evidence/adapter machinery (owned by other WPs and
    covered by their own suites).
    """

    def _fake_generate(**_kwargs: object) -> None:
        _write_references(charter_dir, ref_entries)

    def _fake_synthesize(**_kwargs: object) -> None:
        seed_manifest(repo, built_in_only=False)

    monkeypatch.setattr(generate_module, "generate", Mock(side_effect=_fake_generate))
    monkeypatch.setattr(synthesize_module, "charter_synthesize", Mock(side_effect=_fake_synthesize))


# ---------------------------------------------------------------------------
# T017 / NFR-001 -- default path spawns ZERO synthesis calls
# ---------------------------------------------------------------------------


def test_default_activate_triggers_zero_synthesis_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``charter activate`` without ``--resynthesize`` never calls generate/synthesize."""
    project_root = _minimal_project(tmp_path)
    mock_generate, mock_synthesize = _patch_synthesis_spies(monkeypatch)

    result = _invoke("activate", project_root, "directive", _REAL_DIRECTIVE_STEM)

    assert result.exit_code == 0, result.output
    assert mock_generate.call_count == 0
    assert mock_synthesize.call_count == 0


def test_default_deactivate_triggers_zero_synthesis_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``charter deactivate`` without ``--resynthesize`` never calls generate/synthesize."""
    project_root = _minimal_project(tmp_path)
    _write_config(
        project_root,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
        "mission_type_activations:\n  - software-dev\n",
    )
    mock_generate, mock_synthesize = _patch_synthesis_spies(monkeypatch)

    result = _invoke("deactivate", project_root, "directive", _REAL_DIRECTIVE_STEM)

    assert result.exit_code == 0, result.output
    assert mock_generate.call_count == 0
    assert mock_synthesize.call_count == 0


# ---------------------------------------------------------------------------
# T018 -- --resynthesize reuses the EXISTING pipeline (single authority)
# ---------------------------------------------------------------------------


def test_activate_resynthesize_invokes_existing_pipeline_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--resynthesize`` calls the REAL ``generate``/``charter_synthesize`` objects once each."""
    project_root = _minimal_project(tmp_path)
    mock_generate, mock_synthesize = _patch_synthesis_spies(monkeypatch)

    result = _invoke(
        "activate", project_root, "directive", _REAL_DIRECTIVE_STEM, "--resynthesize"
    )

    assert result.exit_code == 0, result.output
    assert mock_generate.call_count == 1
    assert mock_synthesize.call_count == 1
    # C-007-style reuse lock: the orchestration calls the production
    # entry points with THEIR production defaults, not a bespoke shape --
    # `force=True` because activate always targets an already-materialized
    # bundle, `adapter="generated"` because that is the production adapter.
    assert mock_generate.call_args.kwargs["force"] is True
    assert mock_synthesize.call_args.kwargs["adapter"] == "generated"


def test_deactivate_resynthesize_invokes_existing_pipeline_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``deactivate --resynthesize`` is symmetric with ``activate --resynthesize``."""
    project_root = _minimal_project(tmp_path)
    _write_config(
        project_root,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
        "mission_type_activations:\n  - software-dev\n",
    )
    mock_generate, mock_synthesize = _patch_synthesis_spies(monkeypatch)

    result = _invoke(
        "deactivate", project_root, "directive", _REAL_DIRECTIVE_STEM, "--resynthesize"
    )

    assert result.exit_code == 0, result.output
    assert mock_generate.call_count == 1
    assert mock_synthesize.call_count == 1


def test_no_resynthesize_flag_is_off_by_default_and_documented(tmp_path: Path) -> None:
    """The flag is discoverable and defaults to off (FR-007).

    Rich renders ``--help`` with ANSI styling that colors the leading ``--``
    separately from the option name, so this checks for the un-dashed
    ``resynthesize``/``no-resynthesize`` substrings (each contiguous in the
    styled output) plus the printed default, rather than the exact
    ``--resynthesize`` token.
    """
    result = runner.invoke(charter_app, ["activate", "--help"])
    output_lower = result.output.lower()
    assert "resynthesize" in output_lower
    assert "no-resynthesize" in output_lower
    assert "default: no-resynthesize" in output_lower


# ---------------------------------------------------------------------------
# T019 -- behavior: fresh with the flag, stale + zero-synthesis without it
# ---------------------------------------------------------------------------


def test_activate_resynthesize_reconciles_signal_to_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-04: ``charter activate <kind> <id> --resynthesize`` leaves the signal FRESH."""
    charter_dir = _seed_synthesized_repo(tmp_path, ref_entries=[])
    assert _synthesized_drg_state(tmp_path) == "fresh"  # baseline precondition

    _reconcile_via_fakes(
        monkeypatch,
        tmp_path,
        charter_dir,
        [_reference_entry(f"DIRECTIVE:{_REAL_DIRECTIVE_CANONICAL}", "directive")],
    )

    result = _invoke(
        "activate", tmp_path, "directive", _REAL_DIRECTIVE_STEM, "--resynthesize"
    )

    assert result.exit_code == 0, result.output
    assert _synthesized_drg_state(tmp_path) == "fresh"


def test_activate_without_resynthesize_stays_stale_and_spawns_no_synthesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-04: default ``charter activate`` leaves the signal STALE, zero synthesis calls."""
    _seed_synthesized_repo(tmp_path, ref_entries=[])
    assert _synthesized_drg_state(tmp_path) == "fresh"  # baseline precondition
    mock_generate, mock_synthesize = _patch_synthesis_spies(monkeypatch)

    result = _invoke("activate", tmp_path, "directive", _REAL_DIRECTIVE_STEM)

    assert result.exit_code == 0, result.output
    assert _synthesized_drg_state(tmp_path) == "stale"
    assert mock_generate.call_count == 0
    assert mock_synthesize.call_count == 0


def test_deactivate_resynthesize_reconciles_signal_to_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deactivate symmetric: ``--resynthesize`` reconciles an orphaned paradigm back to fresh."""
    charter_dir = _seed_synthesized_repo(
        tmp_path,
        ref_entries=[
            _reference_entry(f"PARADIGM:{_REAL_PARADIGM_STEM_A}", "paradigm"),
            _reference_entry(f"PARADIGM:{_REAL_PARADIGM_STEM_B}", "paradigm"),
        ],
        activation={
            "activated_paradigms": [_REAL_PARADIGM_STEM_A, _REAL_PARADIGM_STEM_B],
        },
    )
    assert _synthesized_drg_state(tmp_path) == "fresh"  # baseline precondition

    _reconcile_via_fakes(
        monkeypatch,
        tmp_path,
        charter_dir,
        [_reference_entry(f"PARADIGM:{_REAL_PARADIGM_STEM_A}", "paradigm")],
    )

    result = _invoke(
        "deactivate", tmp_path, "paradigm", _REAL_PARADIGM_STEM_B, "--resynthesize"
    )

    assert result.exit_code == 0, result.output
    assert _synthesized_drg_state(tmp_path) == "fresh"


def test_deactivate_without_resynthesize_stays_stale_and_spawns_no_synthesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deactivate symmetric: default leaves the signal STALE, zero synthesis calls."""
    _seed_synthesized_repo(
        tmp_path,
        ref_entries=[
            _reference_entry(f"PARADIGM:{_REAL_PARADIGM_STEM_A}", "paradigm"),
            _reference_entry(f"PARADIGM:{_REAL_PARADIGM_STEM_B}", "paradigm"),
        ],
        activation={
            "activated_paradigms": [_REAL_PARADIGM_STEM_A, _REAL_PARADIGM_STEM_B],
        },
    )
    assert _synthesized_drg_state(tmp_path) == "fresh"  # baseline precondition
    mock_generate, mock_synthesize = _patch_synthesis_spies(monkeypatch)

    result = _invoke("deactivate", tmp_path, "paradigm", _REAL_PARADIGM_STEM_B)

    assert result.exit_code == 0, result.output
    assert _synthesized_drg_state(tmp_path) == "stale"
    assert mock_generate.call_count == 0
    assert mock_synthesize.call_count == 0


# ---------------------------------------------------------------------------
# NFR-003 -- migration / org_charter promote_activations path: no synthesis
# ---------------------------------------------------------------------------


def test_promote_activations_migration_path_triggers_no_synthesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``promote_activations`` (upgrade migration + ``org_charter`` union) never synthesizes.

    Structural by construction (``charter.activation.activation_engine`` never imports
    ``specify_cli`` -- C-001) -- this test locks that invariant in behavior,
    not just by inspection: the write path taken by ``spec-kitty upgrade``'s
    ``m_unify_charter_activation`` migration and ``charter.offering.org_charter``'s
    ``required_*`` union both funnel through this exact function.
    """
    mock_generate, mock_synthesize = _patch_synthesis_spies(monkeypatch)
    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_data: dict[str, Any] = {"activated_directives": [_REAL_DIRECTIVE_STEM]}
    saved: dict[str, Any] = {}

    def _save(path: Path, data: dict[str, Any]) -> None:
        saved["path"] = path
        saved["data"] = dict(data)

    promote_activations(
        {"activated_paradigms": [_REAL_PARADIGM_STEM_A]},
        config_path=config_path,
        config_data=config_data,
        save=_save,
    )

    assert saved["data"]["activated_paradigms"] == [_REAL_PARADIGM_STEM_A]
    assert mock_generate.call_count == 0
    assert mock_synthesize.call_count == 0


# ---------------------------------------------------------------------------
# Sanity: writer-agnostic activation is not accidentally required for the
# flag to exist -- CharterPackManager itself is untouched (C-001 sanity via
# direct exercise, complementing the AST-level guard other WPs already run).
# ---------------------------------------------------------------------------


def test_merge_defaults_writer_unaffected_by_resynthesize_flag(tmp_path: Path) -> None:
    """The ``merge_defaults`` bypass writer still works with the flag machinery present."""
    _seed_synthesized_repo(tmp_path, ref_entries=[])
    result = CharterPackManager().merge_defaults(_ctx(tmp_path))
    assert result.kinds_written  # sanity: the bypass writer still works unmodified
