"""Non-destructive boundary heal that clears stale (WP04,
charter-synthesize-reconciliation-01KZJQN6).

The implement/next boundary reconciler (``_attempt_auto_refresh`` in
``preflight/runner.py``) invokes ``spec-kitty charter synthesize`` flagless
-- no ``--prune``, no ``--dry-run`` -- which is WP01/WP03's
``SynthesizeMode.preserve`` default: a plain run never drops backed content
and exits 0 for backed divergence. This module proves that at the boundary,
end to end against the REAL ``charter.activation.synthesizer`` reconciliation seam (not
a hand-faked stand-in), and pins the companion self-clearing contract
(amendment #2): a successful heal re-stamps the synthesis manifest's
``bundle_content_hash`` (via ``rewrite_manifest``, called unconditionally by
``reconcile_synthesis``), so ``synthesized_drg`` recomputes to ``fresh`` on
its own and a second boundary call is not re-blocked.

Only the ``subprocess.run`` call for ``spec-kitty charter synthesize`` is
faked (no real CLI/subprocess is spawned, matching the existing
``charter_preflight``/``charter_runtime`` test convention) -- but the fake
invokes the real ``charter.activation.synthesizer.orchestrator.synthesize()`` library
entry point in-process with a ``FixtureAdapter``, so the reconciliation,
manifest re-stamp, and freshness recompute this module asserts on are all
production code, not test doubles.

Covers:

* ``test_authoring_only_edit_heals_non_destructively_and_clears_stale``
  (T017/T018/T020): the core boundary-heal contract -- stale -> heal
  (flagless, no --prune/--dry-run) -> 0 nodes/edges lost -> fresh.
* ``test_second_invocation_after_heal_is_not_re_blocked`` (T018/T020): a
  second ``run_charter_preflight(auto_refresh=True)`` call after a
  successful heal is a true no-op -- no re-trigger loop.
* ``test_orphaned_backing_artifact_at_boundary_still_refuses`` /
  ``test_unparseable_overlay_at_boundary_still_refuses`` (post-tasks squad
  amendment #1): the "never silently drops content" guarantee is not a
  "never refuses" guarantee -- these two causes still surface an actionable
  ``blocked_reason``, never a silently-coerced ``passed=True``.
* ``test_references_parity_hook_is_installed_and_invoked_after_a_successful_heal``
  / ``test_references_parity_hook_no_ops_for_a_non_references_parity_cause``
  (T019): the WP04 call site exists and is wired into a successful heal
  (invoked with the correct ``cause``); the "never unconditionally" gate on
  a non-references-parity cause holds even through the call-site wrapper.
  WP06's implementation itself (``preflight.references_refresh``) is covered
  in ``test_references_parity_refresh.py``.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget, synthesize
from charter.activation.synthesizer.reconcile import SynthesizeMode
from specify_cli.charter_runtime.freshness import compute_freshness
from specify_cli.charter_runtime.preflight import run_charter_preflight
from specify_cli.charter_runtime.preflight import runner as runner_module
from specify_cli.charter_runtime.preflight.references_refresh import ReferencesRefreshOutcome
from specify_cli.cli.commands.charter import app as charter_cli_app

pytestmark = [pytest.mark.git_repo]

from ..charter_preflight._fixtures import (
    init_git_repo,
    seed_bundle_files,
    seed_charter,
    seed_charter_yaml,
    write_metadata,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "t@x",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "t@x",
    "PATH": "/usr/bin:/bin",
}

# tests/specify_cli/charter_runtime/test_boundary_heal.py -> tests/
_TESTS_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _TESTS_ROOT / "charter" / "fixtures" / "synthesizer"
_GRAPH_PATH_SUFFIX = Path(".kittify") / "doctrine" / "graph.yaml"


def _fixture_adapter() -> FixtureAdapter:
    return FixtureAdapter(fixture_root=_FIXTURE_ROOT)


def _interview_snapshot() -> dict[str, Any]:
    return {
        "mission_type": "software_dev",
        "language_scope": ["python"],
        "testing_philosophy": "test-driven development with high coverage",
        "neutrality_posture": "balanced",
        "selected_directives": ["DIRECTIVE_003"],
        "risk_appetite": "moderate",
    }


def _doctrine_snapshot() -> dict[str, Any]:
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


def _drg_snapshot() -> dict[str, Any]:
    return {
        "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
        "edges": [],
        "schema_version": "1",
    }


def _request(run_id: str) -> SynthesisRequest:
    """Same target + snapshots as ``tests/charter/synthesizer``'s ``_request``
    helper (kind=directive, slug=mission-type-scope-directive) so this module
    resolves to the SAME committed fixture file deterministically -- only
    ``run_id`` differs, which ``compute_inputs_hash`` does not key on
    (mirrors ``test_noop_resynthesis_is_byte_stable_for_graph_and_manifest``).
    """
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot=_interview_snapshot(),
        doctrine_snapshot=_doctrine_snapshot(),
        drg_snapshot=_drg_snapshot(),
        run_id=run_id,
        adapter_hints={"language": "python"},
    )


def _load_graph(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8"))
    return dict(data) if data else {}


def _git_commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True, env=_GIT_ENV)


def _git_status_porcelain(repo: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout


def _seed_synthesized_and_gone_stale(tmp_path: Path) -> Path:
    """Build a real, committed-clean synthesized repo, then trip
    ``synthesized_drg`` stale via an authoring-only ``charter.yaml`` edit
    (also committed, so the tree is clean going into ``auto_refresh`` --
    FR-008's precondition). Returns the on-disk ``graph.yaml`` path.
    """
    init_git_repo(tmp_path)
    seed_charter_yaml(tmp_path)
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=_fixture_adapter(), repo_root=tmp_path)
    _git_commit_all(tmp_path, "seed synthesized state")

    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"  # baseline sanity

    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# authoring-only edit\n",
        encoding="utf-8",
    )
    _git_commit_all(tmp_path, "authoring-only charter.yaml edit")

    assert compute_freshness(tmp_path).synthesized_drg.state == "stale"  # sanity: trip confirmed
    assert _git_status_porcelain(tmp_path) == ""  # clean going into auto_refresh (FR-008)

    return tmp_path / _GRAPH_PATH_SUFFIX


def _make_heal_subprocess_fake(
    tmp_path: Path, seen_calls: list[list[str]]
) -> Any:
    """Fake ``subprocess.run`` that lets real ``git`` calls through and, for
    ``spec-kitty charter synthesize``, invokes the REAL library entry point
    in-process (``mode=SynthesizeMode.preserve`` -- exactly what the CLI
    selects for a flagless invocation) instead of hand-simulating its output.
    """
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        if cmd[:3] == ["spec-kitty", "charter", "synthesize"]:
            assert "--prune" not in cmd, "boundary heal must never invoke --prune"
            assert "--dry-run" not in cmd, "boundary heal must never invoke --dry-run"
            synthesize(
                _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"),
                adapter=_fixture_adapter(),
                repo_root=tmp_path,
                mode=SynthesizeMode.preserve,
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return fake_run


# ---------------------------------------------------------------------------
# T017/T018/T020 -- core boundary-heal contract
# ---------------------------------------------------------------------------


def test_authoring_only_edit_heals_non_destructively_and_clears_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_path = _seed_synthesized_and_gone_stale(tmp_path)
    graph_before = _load_graph(graph_path)
    nodes_before = len(graph_before.get("nodes", []))
    edges_before = len(graph_before.get("edges", []))
    assert nodes_before >= 1, "fixture setup expected real synthesized content to protect"

    seen_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_heal_subprocess_fake(tmp_path, seen_calls))

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    assert result.auto_refresh_applied is True
    assert result.passed is True, f"blocked_reason={result.blocked_reason!r}"

    cmds = [" ".join(c) for c in seen_calls]
    assert any(c.startswith("spec-kitty charter synthesize") for c in cmds), cmds
    assert not any("--prune" in c for c in cmds), "heal must never invoke the prune/refuse path"
    assert not any("--dry-run" in c for c in cmds)

    graph_after = _load_graph(graph_path)
    assert len(graph_after.get("nodes", [])) == nodes_before, "heal lost node(s)"
    assert len(graph_after.get("edges", [])) == edges_before, "heal lost edge(s)"

    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"


def test_second_invocation_after_heal_is_not_re_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo that just healed must not re-trigger the refresh sequence."""
    _seed_synthesized_and_gone_stale(tmp_path)

    seen_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_heal_subprocess_fake(tmp_path, seen_calls))

    first = run_charter_preflight(tmp_path, auto_refresh=True)
    assert first.passed is True
    assert first.auto_refresh_applied is True
    calls_after_first_heal = len(seen_calls)
    assert calls_after_first_heal > 0

    second = run_charter_preflight(tmp_path, auto_refresh=True)

    assert second.passed is True
    assert second.auto_refresh_applied is False, (
        "a healed repo must not even attempt a second refresh (no re-trigger loop)"
    )
    drg = next(c for c in second.checks if c.name == "synthesized_drg")
    assert drg.state == "fresh"
    assert len(seen_calls) == calls_after_first_heal, "second invocation shelled out again"


# ---------------------------------------------------------------------------
# Post-tasks squad amendment #1 -- boundary-refuse honesty
# ---------------------------------------------------------------------------


def _seed_needs_refresh_repo(tmp_path: Path) -> None:
    """A committed-clean repo whose ``synthesized_drg`` is ``missing`` (no
    manifest/graph yet) -- ``auto_refresh`` will attempt a heal."""
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    seed_charter_yaml(tmp_path)
    _git_commit_all(tmp_path, "seed")


def test_orphaned_backing_artifact_at_boundary_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-014: an orphan-refusal from ``charter synthesize`` (exit 1) must
    surface as an actionable ``blocked_reason`` -- the boundary never
    coerces this into ``passed=True`` just because the heal is otherwise
    non-destructive."""
    _seed_needs_refresh_repo(tmp_path)
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        if cmd[:3] == ["spec-kitty", "charter", "synthesize"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=(
                    "Refused: this run preserved orphaned content instead of dropping it; "
                    "the following references are dangling (backing artifact deleted):\n"
                    "node directive:PROJECT_999 (backing artifact deleted)\n"
                ),
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    assert result.passed is False
    assert result.auto_refresh_applied is True
    assert result.blocked_reason is not None
    assert "orphan" in result.blocked_reason.lower()


def test_unparseable_overlay_at_boundary_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-007: an unparseable on-disk doctrine overlay (``DRGLoadError``)
    makes ``charter synthesize`` exit non-zero -- the boundary surfaces that
    as a refusal too, never a silently-coerced pass."""
    _seed_needs_refresh_repo(tmp_path)
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        if cmd[:3] == ["spec-kitty", "charter", "synthesize"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=(
                    "Refused: the on-disk doctrine overlay could not be parsed. "
                    "No write was made.\n"
                ),
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    assert result.passed is False
    assert result.auto_refresh_applied is True
    assert result.blocked_reason is not None
    assert "parsed" in result.blocked_reason.lower()


# ---------------------------------------------------------------------------
# T019 -- references-parity extension point (installed by WP04, implemented
# by WP06 in ``preflight.references_refresh`` -- see
# ``tests/specify_cli/charter_runtime/test_references_parity_refresh.py``
# for the real-behavior coverage of the implementation itself; this module
# only pins the call-site wiring WP04 owns).
# ---------------------------------------------------------------------------


def test_references_parity_hook_is_installed_and_invoked_after_a_successful_heal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_synthesized_and_gone_stale(tmp_path)

    seen_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_heal_subprocess_fake(tmp_path, seen_calls))

    hook_calls: list[tuple[Path, str]] = []
    original = runner_module.refresh_references_if_needed

    def spy(repo_root: Path, cause: str) -> ReferencesRefreshOutcome:
        hook_calls.append((repo_root, cause))
        return original(repo_root, cause)

    monkeypatch.setattr(runner_module, "refresh_references_if_needed", spy)

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    assert result.passed is True
    assert hook_calls == [(tmp_path, "synthesized_drg")]


def test_references_parity_hook_no_ops_for_a_non_references_parity_cause(
    tmp_path: Path,
) -> None:
    """WP06: the call site is wired for ANY cause, but the implementation
    itself only acts on the references-parity (``synthesized_drg``) cause —
    see ``references_refresh.is_references_parity_cause``. Calling the
    call-site wrapper directly with a cause that does not name
    ``synthesized_drg`` must never raise and must never touch the
    filesystem, proving the "never unconditionally" gate holds even when
    invoked through ``runner.refresh_references_if_needed`` rather than the
    implementation module directly.

    T017 (WP04 auto-refresh swallow fold-in, #5257) widened this call
    site's return type from a bare ``bool`` to ``ReferencesRefreshOutcome`` — assert
    the full no-op contract (``attempted=False``, and the ``succeeded``/
    ``detail`` values the no-op shape always carries), not just a weaker
    truthiness check.
    """
    result = runner_module.refresh_references_if_needed(tmp_path, cause="charter_source")
    assert result.attempted is False
    assert result.succeeded is False
    assert result.detail is None
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# MAJOR-1/MAJOR-3 (WP06 rejection cycle 1) -- manifest-coherent heal with a
# REAL `generate`, driven end to end through `run_charter_preflight`.
#
# `_make_heal_subprocess_fake` (above) stubs `spec-kitty charter generate` to
# a no-op, so the hook tests above never actually mutate `charter.yaml` and
# cannot exercise MAJOR-1 (a `generate` that rewrites the catalog without
# re-stamping the synthesis manifest leaves `synthesized_drg` stale, turning
# a heal that should pass into `passed=False`). The fixture below cannot
# reuse `_seed_synthesized_and_gone_stale`'s synthetic
# ``catalog.mission: preflight-fixture`` / ``template_set: default`` body --
# a REAL `generate` invocation rejects that combination outright ("Unknown
# template set 'default'"), it is a synthetic literal never produced by
# `generate` itself -- so this seeds a REAL baseline via the same
# `--no-from-interview` in-process `generate` invocation
# ``test_references_parity_refresh.py`` uses.
# ---------------------------------------------------------------------------

_runner = CliRunner()

_CURATED_CHARTER_MD = "# Curated Charter\n\nHand-authored governance prose.\n"


def _write_curated_charter_md(repo: Path) -> Path:
    """Seed a hand-authored ``charter.md`` -- ``generate`` must never write it
    (data-model.md Landmine 3 / #2772 -- NFR-006)."""
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    path = charter_dir / "charter.md"
    path.write_text(_CURATED_CHARTER_MD, encoding="utf-8")
    return path


def _invoke_generate_in_process(repo: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the REAL ``generate`` Typer command in-process via ``CliRunner``.

    Mirrors ``test_references_parity_refresh.py``'s helper of the same name
    -- ``find_repo_root()`` resolves from ``os.getcwd()``, so cwd is
    switched to *repo* for the call and restored afterwards.
    """
    with contextlib.chdir(repo):
        result = _runner.invoke(charter_cli_app, argv, catch_exceptions=False)
    return subprocess.CompletedProcess(
        args=["spec-kitty", "charter", *argv],
        returncode=result.exit_code,
        stdout=result.stdout,
        stderr="",
    )


def _make_real_heal_subprocess_fake(
    tmp_path: Path, seen_calls: list[list[str]]
) -> Any:
    """Like ``_make_heal_subprocess_fake``, but ``spec-kitty charter
    generate`` also routes to the REAL in-process command (not a no-op
    stub) -- the fix for MAJOR-3's masking coverage gap."""
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        if cmd[:3] == ["spec-kitty", "charter", "synthesize"]:
            assert "--prune" not in cmd, "boundary heal must never invoke --prune"
            assert "--dry-run" not in cmd, "boundary heal must never invoke --dry-run"
            synthesize(
                _request("01CCCCCCCCCCCCCCCCCCCCCCCCC"),
                adapter=_fixture_adapter(),
                repo_root=tmp_path,
                mode=SynthesizeMode.preserve,
            )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        if cmd[:3] == ["spec-kitty", "charter", "generate"]:
            return _invoke_generate_in_process(tmp_path, cmd[2:])
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return fake_run


def _seed_real_generated_and_gone_stale(tmp_path: Path) -> None:
    """Build a real, committed-clean repo via a REAL ``generate`` baseline
    (so ``catalog.mission``/``template_set`` are genuine, unlike the
    synthetic ``_seed_synthesized_and_gone_stale`` fixture above), stamp a
    real, matching synthesis manifest so ``synthesized_drg`` starts
    ``fresh``, then trip it ``stale`` via a committed authoring-only
    ``charter.yaml`` edit -- the exact non-``built_in_only`` shape MAJOR-1
    diagnosed."""
    init_git_repo(tmp_path)
    _write_curated_charter_md(tmp_path)

    baseline = _invoke_generate_in_process(tmp_path, ["generate", "--no-from-interview"])
    assert baseline.returncode == 0, f"baseline generate failed: {baseline.stdout!r}"

    synthesize(_request("01DDDDDDDDDDDDDDDDDDDDDDDDD"), adapter=_fixture_adapter(), repo_root=tmp_path)
    _git_commit_all(tmp_path, "seed real generated + synthesized baseline")

    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"  # baseline sanity

    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# authoring-only edit\n",
        encoding="utf-8",
    )
    _git_commit_all(tmp_path, "authoring-only charter.yaml edit")

    assert compute_freshness(tmp_path).synthesized_drg.state == "stale"  # sanity: trip confirmed
    assert _git_status_porcelain(tmp_path) == ""  # clean going into auto_refresh (FR-008)


def test_references_parity_heal_recompiles_with_real_generate_and_stays_manifest_coherent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MAJOR-1/MAJOR-3: the boundary heal on a stale, non-``built_in_only``
    repo must pass end to end with a REAL ``generate`` -- not a stubbed
    no-op. Before the manifest-coherent fix, this reproduces MAJOR-1
    exactly: ``generate`` rewrites ``charter.yaml``'s catalog, the synthesis
    manifest is never re-stamped, and the post-refresh recompute reports
    ``synthesized_drg="stale"`` -> ``passed=False`` for a heal that should
    have succeeded.
    """
    _seed_real_generated_and_gone_stale(tmp_path)
    charter_md_path = tmp_path / ".kittify" / "charter" / "charter.md"
    charter_md_before = charter_md_path.read_bytes()

    seen_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_real_heal_subprocess_fake(tmp_path, seen_calls))

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    assert result.passed is True, f"blocked_reason={result.blocked_reason!r}"
    assert result.auto_refresh_applied is True

    drg = next(c for c in result.checks if c.name == "synthesized_drg")
    assert drg.state == "fresh", drg

    cmds = [" ".join(c) for c in seen_calls]
    assert any(c.startswith("spec-kitty charter generate") for c in cmds), cmds
    # references were actually recompiled -- generate ran for real, so the
    # catalog reflects genuine doctrine content, not a stub/no-op.
    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    yaml = YAML(typ="safe")
    catalog = yaml.load(charter_yaml_path.read_text(encoding="utf-8"))["catalog"]
    assert catalog["references"], "references-parity refresh must recompile a non-empty catalog"

    # NFR-006 (#2772): curated charter.md is untouched by the whole heal.
    assert charter_md_path.read_bytes() == charter_md_before

    # A second invocation must not be re-blocked -- the manifest-coherent
    # re-stamp must have landed a truly fresh, self-consistent state.
    seen_calls.clear()
    second = run_charter_preflight(tmp_path, auto_refresh=True)
    assert second.passed is True
    assert second.auto_refresh_applied is False, (
        "a genuinely-healed repo must not re-trigger the refresh sequence"
    )
    assert seen_calls == [], "second invocation shelled out again"
