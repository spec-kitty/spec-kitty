"""Activation visibility in the freshness read-path — RETIREMENT pin
(consolidate-charter-bundle WP06 / #2759, data-model.md / contracts/
manifest-v2.md).

History: the synthesized-drg-stale-refresh mission's WP03 wired
``charter.activation.consistency_check.run_consistency_check`` into
``computer._compute_synthesized_drg`` as a SEPARATE config<->derived
activation-parity signal, because ``charter activate``/``deactivate`` wrote
to ``.kittify/config.yaml`` (``activated_*``), which was NOT one of the four
files the content-hash covered — so activation drift was otherwise invisible
to ``synthesized_drg``.

consolidate-charter-bundle retires that separate parity read
(``_activation_parity_drift_reason`` / ``_PARITY_DRIFT_REMEDIATION``)
outright: it is moot once freshness hashes ``charter.yaml`` directly, because
activation is relocated INTO ``charter.yaml`` (data-model.md Entity:
``.kittify/config.yaml`` after relocation) — the same file the content hash
already covers. A config<->references/graph divergence of the
pre-relocation kind cannot exist anymore: there is no longer a second file
for activation to drift *away from* the hash input. The content-identity
comparison in ``_synthesized_drg_graph_state`` subsumes what the parity read
used to catch — any edit to ``charter.yaml`` (governance, directives, OR
activation) flips the whole-file hash and therefore ``synthesized_drg``.

Covers:
- ``test_activation_parity_mechanism_retired``: structural pin — the
  retired symbols no longer exist on ``computer``.
- ``test_charter_yaml_edit_without_reconcile_is_stale`` /
  ``test_reconcile_after_edit_returns_to_fresh``: the SAME visibility
  guarantee the retired parity read used to provide, now delivered by the
  unified content-hash comparison alone — an edit to ``charter.yaml`` (the
  post-relocation home for activation) is visible as ``stale`` until the
  next synth reconciles it. This is also the spurious-authoring-staleness
  decision (data-model.md Landmine 2 extension, option (b) — see
  ``traces/decisions.md``).
- ``test_unchanged_bundle_hash_stable_across_freshness_calls``: NFR-002 —
  ``compute_freshness`` is a pure observer; calling it never mutates the
  content-identity hash of the bundle it inspects.
- ``test_fresh_seed_built_in_only_project_not_forced_stale``: R-01 — a
  never-synthesized (``built_in_only``) project is a structural
  short-circuit that returns BEFORE any content-hash comparison, so it is
  never forced stale regardless of ``charter.yaml`` content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.charter_runtime.freshness import compute_freshness

pytestmark = [pytest.mark.git_repo]

from ..charter_preflight._fixtures import (
    init_git_repo,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
)

# Mirrors the preflight runner's own pass-state set (``_PASS_STATES`` in
# ``specify_cli.charter_runtime.preflight.runner``) -- kept local rather than
# imported so this test asserts the *contract*, not an implementation detail
# reachable only via the preflight package.
_PASS_STATES = frozenset({"fresh", "built_in_only"})


def _synthesized_drg_state(repo: Path) -> str:
    return compute_freshness(repo).synthesized_drg.state


def _seed_fresh_synthesized_repo(repo: Path) -> Path:
    """Build a fully-synthesized, freshness-``fresh`` repo: ``charter.yaml``
    + a real ``graph.yaml`` + a manifest whose ``bundle_content_hash``
    genuinely matches a fresh recompute."""
    from charter.bundle import compute_bundle_content_hash

    init_git_repo(repo)
    charter_yaml_path = seed_charter_yaml(repo)
    seed_graph(repo)
    real_hash = compute_bundle_content_hash(repo)
    assert real_hash is not None
    seed_manifest(repo, built_in_only=False, bundle_content_hash=real_hash)
    return charter_yaml_path


# ---------------------------------------------------------------------------
# Retirement pin
# ---------------------------------------------------------------------------


def test_activation_parity_mechanism_retired() -> None:
    """The #2759 config<->derived activation-parity read no longer exists on
    ``computer`` — it is moot once freshness hashes ``charter.yaml`` (the
    activation-owning file) directly."""
    from specify_cli.charter_runtime.freshness import computer as freshness_computer

    assert not hasattr(freshness_computer, "_activation_parity_drift_reason")
    assert not hasattr(freshness_computer, "_PARITY_DRIFT_REMEDIATION")


def test_compute_freshness_never_calls_consistency_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Behavioural companion to the structural pin above: even if a caller
    imports ``run_consistency_check`` independently, ``compute_freshness``
    itself never invokes it — the read-path is decoupled from the retired
    parity guard entirely, not merely stripped of its own private helper."""
    import charter.activation.consistency_check as consistency_check_module

    def _must_not_be_called(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "compute_freshness must not invoke run_consistency_check "
            "(#2759 parity read retired by consolidate-charter-bundle WP06)"
        )

    monkeypatch.setattr(consistency_check_module, "run_consistency_check", _must_not_be_called)

    _seed_fresh_synthesized_repo(tmp_path)

    assert _synthesized_drg_state(tmp_path) == "fresh"  # sanity: exercised the real path


# ---------------------------------------------------------------------------
# Unified content-hash visibility (subsumes what the parity read used to do)
# ---------------------------------------------------------------------------


def test_charter_yaml_edit_without_reconcile_is_stale(tmp_path: Path) -> None:
    """An edit to ``charter.yaml`` (the post-relocation home for activation,
    data-model.md) without a following synth is visible as ``stale`` — the
    SAME guarantee the retired parity read used to provide, now delivered by
    the unified content-hash comparison alone."""
    charter_yaml_path = _seed_fresh_synthesized_repo(tmp_path)
    assert _synthesized_drg_state(tmp_path) == "fresh"  # baseline

    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# activation-shaped edit\n",
        encoding="utf-8",
    )

    assert _synthesized_drg_state(tmp_path) == "stale"


def test_reconcile_after_edit_returns_to_fresh(tmp_path: Path) -> None:
    """edit -> stale -> reconcile (re-stamp the manifest, what ``spec-kitty
    charter synthesize`` does) -> fresh again. Proves the visibility gap the
    retired parity read used to close is not a permanent-stale dead-end
    (data-model.md Landmine 2 extension, decision (b))."""
    from charter.bundle import compute_bundle_content_hash

    charter_yaml_path = _seed_fresh_synthesized_repo(tmp_path)
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# activation-shaped edit\n",
        encoding="utf-8",
    )
    assert _synthesized_drg_state(tmp_path) == "stale"

    real_hash = compute_bundle_content_hash(tmp_path)
    assert real_hash is not None
    seed_manifest(tmp_path, built_in_only=False, bundle_content_hash=real_hash)

    assert _synthesized_drg_state(tmp_path) == "fresh"


def test_reconcile_after_edit_returns_to_fresh_via_resynthesize_shaped_stamp(tmp_path: Path) -> None:
    """Cascade-shaped edge: reconciling from a genuinely different prior
    manifest (a real re-stamp, not just re-seeding the same value) also
    clears the drift — proves the recompute reads current content, not a
    cached value."""
    from charter.bundle import compute_bundle_content_hash

    charter_yaml_path = _seed_fresh_synthesized_repo(tmp_path)
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# first edit\n", encoding="utf-8"
    )
    assert _synthesized_drg_state(tmp_path) == "stale"

    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# second edit\n", encoding="utf-8"
    )
    assert _synthesized_drg_state(tmp_path) == "stale"  # still stale after a second, unstamped edit

    real_hash = compute_bundle_content_hash(tmp_path)
    assert real_hash is not None
    seed_manifest(tmp_path, built_in_only=False, bundle_content_hash=real_hash)

    assert _synthesized_drg_state(tmp_path) == "fresh"


# ---------------------------------------------------------------------------
# NFR-002 (#2732) preserve: pure observer, fresh-seed intact
# ---------------------------------------------------------------------------


def test_unchanged_bundle_hash_stable_across_freshness_calls(tmp_path: Path) -> None:
    """``compute_freshness`` is a pure observer: calling it repeatedly never
    mutates the content-identity hash of the bundle it inspects."""
    from charter.bundle import compute_bundle_content_hash

    _seed_fresh_synthesized_repo(tmp_path)

    hash_before = compute_bundle_content_hash(tmp_path)
    result = compute_freshness(tmp_path)
    hash_after = compute_bundle_content_hash(tmp_path)

    assert hash_before is not None
    assert hash_before == hash_after
    assert result.synthesized_drg.state == "fresh"


def test_fresh_seed_built_in_only_project_not_forced_stale(tmp_path: Path) -> None:
    """A never-synthesized (``built_in_only``) project is a structural
    short-circuit that returns BEFORE any content-hash comparison is ever
    reached (R-01) — even when ``charter.yaml`` content looks
    activation-shaped. Asserts PASS-STATE membership, not the literal
    ``"fresh"`` string (``built_in_only`` is itself a distinct passing
    state)."""
    init_git_repo(tmp_path)
    seed_charter_yaml(tmp_path)
    seed_manifest(tmp_path, built_in_only=True)  # no graph.yaml

    state = _synthesized_drg_state(tmp_path)

    assert state in _PASS_STATES
    assert state == "built_in_only"


def test_multi_edit_drift_reports_single_stale_signal(tmp_path: Path) -> None:
    """A simultaneous multi-section edit (what a real activation write PLUS
    a governance edit would produce once both live in ``charter.yaml``)
    still resolves to exactly ONE ``synthesized_drg``
    :class:`FreshnessSubState` per freshness computation — the whole-file
    hash comparison runs once per ``compute_freshness`` call, not once per
    edited section."""
    charter_yaml_path = _seed_fresh_synthesized_repo(tmp_path)

    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# governance + activation edit\n",
        encoding="utf-8",
    )

    result = compute_freshness(tmp_path)

    assert result.synthesized_drg.state == "stale"
    assert result.synthesized_drg.remediation == "spec-kitty charter synthesize"


def test_graph_schema_valid_seed_used_by_this_suite(tmp_path: Path) -> None:
    """Sanity: ``seed_graph`` (shared fixture) produces a schema-conformant
    graph accepted by this module's real ``compute_freshness`` path (no
    pydantic validation surprises at the freshness layer, which only checks
    existence/mtime of ``graph.yaml`` — unlike ``consistency_check``, which
    this module no longer calls at all)."""
    # The shared ``seed_graph`` fixture (tests/specify_cli/charter_preflight/_fixtures.py,
    # used by ~15 suites) still seeds the retired root; freshness reads it through
    # the temporary read fallback (FR-011) until WP14 removes it.
    graph_path = tmp_path / ".kittify" / "doctrine" / "graph.yaml"
    seed_graph(tmp_path)
    assert graph_path.exists()
    assert "nodes" in graph_path.read_text(encoding="utf-8")
