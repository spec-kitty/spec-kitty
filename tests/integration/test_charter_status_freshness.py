"""FR-005: ``charter status --json`` exposes a freshness sub-payload.

Verifies the contract documented in
``contracts/charter-status-json.md`` and ``data-model.md §5``, re-pointed at
``charter.yaml`` by consolidate-charter-bundle WP06 (data-model.md
Landmine 2, FR-003, FR-011, NFR-001, NFR-002).

Covers four canonical scenarios:

1. ``fresh`` — ``charter.yaml`` parses, bundle present, DRG content-hash
   matches.
2. ``invalid`` — ``charter.yaml`` present but unparseable (the retired
   ``charter.md``-hash-mismatch ``"stale"`` mechanism no longer exists at
   this layer — see ``computer.py``'s module docstring).
3. ``missing`` — no synthesis manifest, no graph.yaml.
4. ``built_in_only`` — manifest declares built-in-only, no graph.yaml.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.bundle import compute_bundle_content_hash
from charter.hasher import hash_content

pytestmark = [pytest.mark.integration]


runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sync_result_stub(repo_root: Path) -> object:
    class _Stub:
        canonical_root = repo_root
    return _Stub()


def _seed_minimum_repo(repo: Path) -> None:
    """Create the minimum filesystem layout so ``charter status`` runs."""
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text(
        dedent(
            """\
            agents:
              available:
                - claude
            """
        )
    )


_CHARTER_YAML_BODY = (
    "schema_version: '2.0.0'\n"
    "governance: {}\n"
    "directives:\n"
    "  directives: []\n"
    "catalog:\n"
    "  mission: test-mission\n"
    "  template_set: default\n"
    "  languages: []\n"
    "  references: []\n"
    "metadata:\n"
    "  generated_at: '2026-01-01T00:00:00+00:00'\n"
    "  bundle_schema_version: 2\n"
)


def _write_charter_and_metadata(
    repo: Path,
    *,
    invalid_charter_yaml: bool = False,
) -> None:
    """Seed the legacy ``charter.md``/``metadata.yaml`` pair (still consulted
    by the unrelated, still-live ``charter status`` sync-collector surface —
    see ``test_freshness_hash_unification.py``) plus ``charter.yaml`` — the
    file ``charter_source``/``synced_bundle``/``synthesized_drg`` actually
    resolve over post-Landmine-2.

    ``invalid_charter_yaml=True`` writes genuinely malformed YAML so
    ``charter_source`` reads ``invalid`` — the retired charter.md-hash-
    mismatch mechanism (formerly ``"stale"``) no longer exists at this
    layer.
    """
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.md"
    metadata_path = charter_dir / "metadata.yaml"
    charter_path.write_text("# Charter\n", encoding="utf-8")
    digest = hash_content(charter_path.read_text(encoding="utf-8")).split(":", 1)[1]
    # NOTE: omit ``timestamp_utc`` — ruamel's safe loader parses ISO
    # timestamps to ``datetime`` objects, which the existing
    # ``_collect_charter_sync_status`` payload then fails to JSON-encode.
    # Use a plain-string timestamp so the existing serialization path stays
    # green while we exercise the new freshness layer.
    metadata_path.write_text(
        dedent(
            f"""\
            charter_hash: sha256:{digest}
            extracted_at: "2026-01-01T00:00:00+00:00"
            """
        ),
        encoding="utf-8",
    )
    body = _CHARTER_YAML_BODY if not invalid_charter_yaml else "not: [valid: yaml: at: all"
    (charter_dir / "charter.yaml").write_text(body, encoding="utf-8")


def _write_manifest(
    repo: Path,
    *,
    built_in_only: bool,
    bundle_content_hash: str | None = None,
) -> None:
    path = repo / ".kittify" / "charter" / "synthesis-manifest.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    hash_line = (
        f"bundle_content_hash: {bundle_content_hash}\n"
        if bundle_content_hash is not None
        else "bundle_content_hash: null\n"
    )
    path.write_text(
        dedent(
            f"""\
            schema_version: '2'
            mission_id: null
            created_at: '2099-01-01T00:00:00+00:00'
            run_id: 01JTESTRUNIDXXXXXXXXXXXXXX
            adapter_id: test
            adapter_version: '0.0.0'
            synthesizer_version: '0.0.0'
            manifest_hash: {"a" * 64}
            artifacts: []
            built_in_only: {str(built_in_only).lower()}
            """
        )
        + hash_line,
        encoding="utf-8",
    )


def _write_graph(repo: Path) -> None:
    p = repo / ".kittify" / "charter-packs" / "graph.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")


def _invoke_status_json(repo: Path) -> dict[str, object]:
    monkey_targets = (
        "specify_cli.cli.commands.charter.find_repo_root",
        "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
        "specify_cli.cli.commands.charter._assert_bundle_compatible",
    )
    from specify_cli.cli.commands.charter import app as charter_app

    with (
        patch(monkey_targets[0], return_value=repo),
        patch(monkey_targets[1], return_value=_make_sync_result_stub(repo)),
        patch(monkey_targets[2], return_value=None),
    ):
        result = runner.invoke(charter_app, ["status", "--json"])
    if result.exit_code != 0 or not result.stdout.strip():
        raise AssertionError(
            f"charter status failed: exit_code={result.exit_code}\n"
            f"stdout={result.stdout!r}\n"
            f"exception={result.exception!r}"
        )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Scenario tests
# ---------------------------------------------------------------------------


def test_payload_includes_freshness_with_three_sub_objects(tmp_path: Path) -> None:
    _seed_minimum_repo(tmp_path)
    payload = _invoke_status_json(tmp_path)
    assert "freshness" in payload, payload.keys()
    freshness = payload["freshness"]
    assert isinstance(freshness, dict)
    assert set(freshness.keys()) == {"charter_source", "synced_bundle", "synthesized_drg"}
    for sub in freshness.values():
        assert "state" in sub
        assert "last_change" in sub
        assert "remediation" in sub


def test_freshness_state_fresh_when_all_artifacts_aligned(tmp_path: Path) -> None:
    """Tightened per research fact #21: the old ``in {"fresh", "stale"}``
    assertion was a live SYMPTOM of the #2681 mtime-comparison bug (it
    admitted ``stale`` because the mtime rule was nondeterministic). Now
    that ``bundle_content_hash`` is content-identity, a manifest whose
    stored hash matches the real bundle content is unambiguously ``fresh``.
    """
    _seed_minimum_repo(tmp_path)
    _write_charter_and_metadata(tmp_path)
    bundle_content_hash = compute_bundle_content_hash(tmp_path)
    assert bundle_content_hash is not None
    _write_manifest(tmp_path, built_in_only=False, bundle_content_hash=bundle_content_hash)
    _write_graph(tmp_path)

    payload = _invoke_status_json(tmp_path)
    freshness = payload["freshness"]
    assert freshness["charter_source"]["state"] == "fresh"
    assert freshness["synced_bundle"]["state"] == "fresh"
    assert freshness["synthesized_drg"]["state"] == "fresh"


def test_freshness_state_invalid_when_charter_yaml_unparseable(tmp_path: Path) -> None:
    """Re-pinned (WP06 / Landmine 2): the retired charter.md-hash-mismatch
    ``"stale"`` mechanism is replaced by ``charter.yaml`` being present but
    unparseable, which reads ``"invalid"`` — the only non-``fresh``,
    non-``missing`` state ``charter_source`` can report post-retirement.

    Re-pinned again (charter-preflight-remediation WP03/WP05 — narrow,
    out-of-map fix to a pre-existing stale assertion this file's owner did
    not touch): WP03 proved no write path can repair unparseable YAML and
    declared ``invalid`` exempt (C-EFF-2), so ``computer.py`` now emits
    ``remediation=None`` here rather than the ineffective ``charter sync``
    string this test used to assert. This was already red on this branch
    before WP05 touched anything — confirmed by running it pre-edit."""
    _seed_minimum_repo(tmp_path)
    _write_charter_and_metadata(tmp_path, invalid_charter_yaml=True)
    payload = _invoke_status_json(tmp_path)
    freshness = payload["freshness"]
    assert freshness["charter_source"]["state"] == "invalid"
    assert freshness["charter_source"]["remediation"] is None
    assert freshness["charter_source"]["detail"]


def test_freshness_state_missing_when_no_synthesis_artifacts(tmp_path: Path) -> None:
    """Preserved by the #2681 fix — the ``missing`` branch sits above the
    content-hash comparison. A regress here means T015 touched a branch it
    should not have."""
    _seed_minimum_repo(tmp_path)
    _write_charter_and_metadata(tmp_path)
    payload = _invoke_status_json(tmp_path)
    freshness = payload["freshness"]
    assert freshness["synthesized_drg"]["state"] == "missing"
    assert freshness["synthesized_drg"]["remediation"] == "spec-kitty charter synthesize"


def test_freshness_missing_detail_distinguishes_no_charter_from_legacy_bundle(
    tmp_path: Path,
) -> None:
    """FR-005 (charter-preflight-remediation WP05): F1 ("no charter at all")
    and F2 (legacy bundle present, no ``charter.yaml``) both report
    ``state="missing"`` — the only distinguishing signal is ``detail``. This
    is the operator-facing ``charter status`` surface WP04 converged onto
    the canonical presence seam; the distinction must not be lost here even
    though the fix lives entirely in ``computer.py`` (WP05 owns no file
    under this test's path — this is the surface-level proof the WP prompt
    asked for)."""
    _seed_minimum_repo(tmp_path)
    # F1: no charter artifact of any kind.
    payload_f1 = _invoke_status_json(tmp_path)
    detail_f1 = payload_f1["freshness"]["charter_source"]["detail"]
    assert detail_f1
    assert "no charter at all" in detail_f1

    with tempfile.TemporaryDirectory() as f2_dir:
        f2_repo = Path(f2_dir)
        _seed_minimum_repo(f2_repo)
        charter_dir = f2_repo / ".kittify" / "charter"
        charter_dir.mkdir(parents=True, exist_ok=True)
        for name in ("governance.yaml", "directives.yaml", "metadata.yaml"):
            (charter_dir / name).write_text("schema_version: '1'\n", encoding="utf-8")
        payload_f2 = _invoke_status_json(f2_repo)
        detail_f2 = payload_f2["freshness"]["charter_source"]["detail"]

    assert detail_f2
    assert "no charter at all" not in detail_f2
    assert "legacy charter bundle" in detail_f2
    # WP05 cycle 2 (review-cycle-1.md Issue 1 — BLOCKING): this fixture
    # seeds only three of the four legacy files (no ``references.yaml``) —
    # the detail must name only what is actually on disk, not overclaim the
    # fourth file is present too.
    assert "governance.yaml" in detail_f2
    assert "directives.yaml" in detail_f2
    assert "metadata.yaml" in detail_f2
    assert "references.yaml" not in detail_f2
    assert detail_f1 != detail_f2
    # Both remain the same non-blocking-eligible state; only detail differs.
    assert payload_f1["freshness"]["charter_source"]["state"] == "missing"
    assert payload_f2["freshness"]["charter_source"]["state"] == "missing"


def test_freshness_state_built_in_only_when_manifest_marks_it(tmp_path: Path) -> None:
    """Preserved by the #2681 fix — ``built_in_only`` short-circuits BEFORE
    the content-hash comparison. A regress here means T015 touched a branch
    it should not have."""
    _seed_minimum_repo(tmp_path)
    _write_charter_and_metadata(tmp_path)
    _write_manifest(tmp_path, built_in_only=True)
    payload = _invoke_status_json(tmp_path)
    freshness = payload["freshness"]
    assert freshness["synthesized_drg"]["state"] == "built_in_only"
    assert freshness["synthesized_drg"]["remediation"] is None
