"""Integration tests: org pack subdir resolution e2e (WP02 SC-001/002/003).

Covers:
  SC-001 — a pack whose artifacts live under ``subdir`` loads healthy via
            both ``_collect_org_layer_data`` (T007) and ``_build_pack_entries``
            (T009).
  SC-002 — a no-subdir pack is byte-identical in behavior (regression guard).
  SC-003 — a wrong ``subdir`` → errors reported (effective root missing).

FR-007 fetch_pack reporting (added cycle-2 fix):
  fetch_pack_int_contract — ``artifacts_written`` is a scalar ``int`` (not dict).
  fetch_pack_wrong_subdir_zero_count — wrong subdir → ``artifacts_written == 0``
    (SC-003 on the fetch reporting leg).
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_PACK_NAME = "acme-doctrine-pack"

_DRG_FRAGMENT_YAML = dedent("""\
    pack_name: acme-doctrine-pack
    source_kind: local_path
    source_ref: org-doctrine-store/pack
    layer_index: 1
    provenance_marker: org
    nodes: []
    edges: []
""")

_ORG_CHARTER_YAML = dedent("""\
    schema_version: "1"
    org_name: Acme Corp
""")


def _write_config(repo_root: Path, *, local_path: Path, subdir: str | None = None) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    subdir_line = f"\n                    subdir: {subdir}" if subdir else ""
    (kittify / "config.yaml").write_text(
        dedent(f"""\
            charter_packs:
              org:
                packs:
                  - name: {_PACK_NAME}
                    local_path: {local_path}{subdir_line}
            """),
        encoding="utf-8",
    )


def _build_pack_at(pack_root: Path) -> None:
    """Write a minimal valid pack (org-charter.yaml + drg/fragment.yaml) at ``pack_root``."""
    (pack_root / "drg").mkdir(parents=True, exist_ok=True)
    (pack_root / "org-charter.yaml").write_text(_ORG_CHARTER_YAML, encoding="utf-8")
    (pack_root / "drg" / "fragment.yaml").write_text(_DRG_FRAGMENT_YAML, encoding="utf-8")


# ---------------------------------------------------------------------------
# SC-001: subdir-rooted pack loads healthy
# ---------------------------------------------------------------------------


def test_sc001_subdir_pack_loads_healthy(tmp_path: Path) -> None:
    """SC-001: a pack configured with ``subdir: pack`` resolves artifacts
    under ``<local_path>/pack/`` and makes doctor charter-packs report healthy
    (both T007 load_org_drg path and T009 _build_pack_entries path).
    """
    from specify_cli.cli.commands.doctor import _build_pack_entries, _collect_org_layer_data  # noqa: PLC0415
    from charter.offering.drg.org_pack_config import load_pack_registry  # noqa: PLC0415

    repo_root = tmp_path / "consumer"
    repo_root.mkdir()

    local_path = tmp_path / "org-doctrine-store"
    pack_artifacts = local_path / "pack"
    _build_pack_at(pack_artifacts)

    _write_config(repo_root, local_path=local_path, subdir="pack")

    # T007 coverage: _collect_org_layer_data calls load_org_drg → build_org_drg_fragments
    result = _collect_org_layer_data(repo_root)
    assert result["errors"] == [], (
        f"SC-001: doctor charter-packs must be healthy for a subdir pack. errors={result['errors']!r}"
    )

    # T009 coverage: _build_pack_entries must resolve the effective root
    registry = load_pack_registry(repo_root)
    entries = _build_pack_entries(registry, repo_root)
    assert len(entries) == 1
    assert entries[0]["snapshot_present"] is True, (
        f"SC-001: _build_pack_entries must find the pack at its effective root. entry={entries[0]!r}"
    )


# ---------------------------------------------------------------------------
# SC-002: no-subdir pack (regression)
# ---------------------------------------------------------------------------


def test_sc002_no_subdir_pack_unchanged(tmp_path: Path) -> None:
    """SC-002: a pack without ``subdir`` behaves identically to before WP02."""
    from specify_cli.cli.commands.doctor import _build_pack_entries, _collect_org_layer_data  # noqa: PLC0415
    from charter.offering.drg.org_pack_config import load_pack_registry  # noqa: PLC0415

    repo_root = tmp_path / "consumer"
    repo_root.mkdir()

    local_path = tmp_path / "org-doctrine-store"
    _build_pack_at(local_path)

    _write_config(repo_root, local_path=local_path)  # no subdir

    result = _collect_org_layer_data(repo_root)
    assert result["errors"] == [], (
        f"SC-002: no-subdir pack must still load healthy. errors={result['errors']!r}"
    )

    registry = load_pack_registry(repo_root)
    entries = _build_pack_entries(registry, repo_root)
    assert len(entries) == 1
    assert entries[0]["snapshot_present"] is True, (
        f"SC-002: no-subdir pack must show snapshot_present=True. entry={entries[0]!r}"
    )


# ---------------------------------------------------------------------------
# SC-003: wrong subdir → errors reported
# ---------------------------------------------------------------------------


def test_sc003_wrong_subdir_reports_errors(tmp_path: Path) -> None:
    """SC-003: a pack with ``subdir: nonexistent`` → effective root doesn't
    exist → doctor charter-packs reports errors; _build_pack_entries shows
    snapshot_present=False.
    """
    from specify_cli.cli.commands.doctor import _build_pack_entries, _collect_org_layer_data  # noqa: PLC0415
    from charter.offering.drg.org_pack_config import load_pack_registry  # noqa: PLC0415

    repo_root = tmp_path / "consumer"
    repo_root.mkdir()

    local_path = tmp_path / "org-doctrine-store"
    local_path.mkdir()  # pack root exists, but "wrong-subdir" subdirectory does not

    _write_config(repo_root, local_path=local_path, subdir="wrong-subdir")

    result = _collect_org_layer_data(repo_root)
    assert result["errors"] != [], (
        f"SC-003: wrong subdir must produce errors. result={result!r}"
    )

    registry = load_pack_registry(repo_root)
    entries = _build_pack_entries(registry, repo_root)
    assert len(entries) == 1
    assert entries[0]["snapshot_present"] is False, (
        f"SC-003: wrong subdir → effective root doesn't exist → snapshot_present=False. entry={entries[0]!r}"
    )


# ---------------------------------------------------------------------------
# FR-007: fetch_pack artifacts_written int contract
# ---------------------------------------------------------------------------


def _make_fake_source(local_path: Path) -> MagicMock:
    """Return a MagicMock OrgDoctrineSource whose fetch() writes minimal YAML artifacts.

    The source writes a single directive YAML into the target directory so that
    ``_count_artifacts`` returns a non-empty dict for no-subdir packs.
    Used to drive ``fetch_pack`` without a real git/https/api remote.
    """
    from specify_cli.charter_packs.sources.protocol import FetchResult  # noqa: PLC0415

    def _fake_fetch(target_dir: Path) -> FetchResult:
        (target_dir / "directives").mkdir(parents=True, exist_ok=True)
        (target_dir / "directives" / "sample.yaml").write_text(
            "id: test\n", encoding="utf-8"
        )
        return FetchResult(ok=True, artifacts_written=1, pack_version="v0.0.1")

    fake = MagicMock()
    fake.fetch.side_effect = _fake_fetch
    return fake


def test_fetch_pack_int_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007: fetch_pack must return artifacts_written as a scalar int, not a dict."""
    from charter.offering.drg.org_pack_config import load_pack_registry  # noqa: PLC0415
    from specify_cli.charter_packs.snapshot import fetch_pack  # noqa: PLC0415

    local_path = tmp_path / "pack-store"
    repo_root = tmp_path / "consumer"
    repo_root.mkdir()

    _write_config(repo_root, local_path=local_path, subdir=None)

    registry = load_pack_registry(repo_root)
    assert len(registry.packs) == 1
    pack = registry.packs[0]

    monkeypatch.setattr(
        "specify_cli.charter_packs.snapshot._build_source",
        lambda p: _make_fake_source(local_path),
    )

    result = fetch_pack(pack, repo_root)

    assert result.ok, f"Expected fetch to succeed, got errors={result.errors!r}"
    assert isinstance(result.artifacts_written, int), (
        f"FR-007: artifacts_written must be int, got {type(result.artifacts_written)!r}: "
        f"{result.artifacts_written!r}"
    )
    assert result.artifacts_written > 0, (
        f"FR-007: artifacts_written must be > 0 when artifacts were written, "
        f"got {result.artifacts_written!r}"
    )


def test_fetch_pack_wrong_subdir_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured effective root with no artifacts must not replace last-good."""
    from charter.offering.drg.org_pack_config import load_pack_registry  # noqa: PLC0415
    from specify_cli.charter_packs.snapshot import fetch_pack  # noqa: PLC0415

    local_path = tmp_path / "pack-store"
    repo_root = tmp_path / "consumer"
    repo_root.mkdir()

    _write_config(repo_root, local_path=local_path, subdir="nonexistent-subdir")

    registry = load_pack_registry(repo_root)
    assert len(registry.packs) == 1
    pack = registry.packs[0]

    monkeypatch.setattr(
        "specify_cli.charter_packs.snapshot._build_source",
        lambda p: _make_fake_source(local_path),
    )

    result = fetch_pack(pack, repo_root)

    assert result.ok is False
    assert isinstance(result.artifacts_written, int), (
        f"artifacts_written must be int even for wrong subdir, "
        f"got {type(result.artifacts_written)!r}: {result.artifacts_written!r}"
    )
    assert any("nonexistent-subdir" in error for error in result.errors)
    assert not local_path.exists()


def test_config_schema_contract_documents_subdir() -> None:
    """FR-008: the org-pack config-schema contract documents the ``subdir`` field.

    The named contract file must keep ``additionalProperties: false`` (so an
    unknown key is rejected) AND declare ``subdir`` on BOTH the canonical
    multi-pack form (Form A) and the legacy single-pack form (Form B); otherwise
    a consumer validating config against the documented schema would reject a
    ``subdir`` that the runtime now accepts.
    """
    import yaml as _yaml  # local import; stdlib-safe

    repo_root = Path(__file__).resolve().parents[2]
    schema_path = (
        repo_root
        / "kitty-specs"
        / "layered-doctrine-org-layer-01KRNPEE"
        / "contracts"
        / "config-schema.yaml"
    )
    assert schema_path.exists(), f"contract schema missing at {schema_path}"
    doc = _yaml.safe_load(schema_path.read_text(encoding="utf-8"))

    org = doc["properties"]["doctrine"]["properties"]["org"]
    forms = org["oneOf"]
    # Form A — items in the packs list.
    form_a_item = forms[0]["properties"]["packs"]["items"]
    assert "subdir" in form_a_item["properties"], "Form A must document subdir"
    assert form_a_item["additionalProperties"] is False
    # Form B — legacy single inline pack.
    form_b = forms[1]
    assert "subdir" in form_b["properties"], "Form B must document subdir"
    assert form_b["additionalProperties"] is False


def test_config_schema_accepts_every_runtime_source_type() -> None:
    """Public config schema and runtime source-type contract cannot drift."""
    from typing import get_args

    import yaml as _yaml
    from jsonschema import Draft202012Validator

    from charter.offering.drg.org_pack_config import SourceType

    repo_root = Path(__file__).resolve().parents[2]
    schema_path = (
        repo_root
        / "kitty-specs"
        / "layered-doctrine-org-layer-01KRNPEE"
        / "contracts"
        / "config-schema.yaml"
    )
    schema = _yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    forms = schema["properties"]["doctrine"]["properties"]["org"]["oneOf"]
    runtime_types = set(get_args(SourceType))
    form_a_types = set(
        forms[0]["properties"]["packs"]["items"]["properties"]["source_type"][
            "enum"
        ]
    )
    form_b_types = set(forms[1]["properties"]["source_type"]["enum"])

    assert form_a_types == runtime_types
    assert form_b_types == runtime_types
    Draft202012Validator(schema).validate(
        {
            "charter_packs": {
                "org": {
                    "packs": [
                        {
                            "name": "release-doctrine",
                            "local_path": "/opt/doctrine/release",
                            "source_type": "artifactory",
                            "url": (
                                "https://jfrog.example.com/artifactory/"
                                "doctrine-local/release.tar.gz"
                            ),
                        }
                    ]
                }
            }
        }
    )
