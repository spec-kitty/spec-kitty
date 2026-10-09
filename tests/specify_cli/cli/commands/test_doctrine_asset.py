"""CLI tests for ``spec-kitty charter pack asset`` (WP05, T026/T027).

The asset operator surface is a *read-only* window over the WP04 resolution
repository (:class:`charter.offering.assets.repository.AssetRepository`, reached through
:class:`charter.offering.service.CharterOfferingService` ``.assets``):

* ``asset list [--json]`` enumerates every resolvable asset with its source tier.
* ``asset path <id> [--json]`` resolves one identifier to a filesystem path,
  exiting 0 on success and non-zero — with the id named — on an unknown id (A-7).

Nothing here installs anything (C-002); these tests assert resolution only.
They run in-process against the dev layout; the falsifiable clean-environment
proof (SC-003) lives in ``tests/docs/test_asset_resolution_wheel.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import pack_asset as asset_module
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

#: The single built-in asset shipped today (WP04). Its blob is the structural
#: docs-lint script; the manifest declares this stable identifier.
_SHIPPED_ASSET_ID = "common-docs-structural-lint"


def _write_asset_manifest(path: Path, *, asset_id: str, mime: str, blob_path: str) -> None:
    """Write one ``*.asset.yaml`` sidecar manifest (mirrors ``tests/charter_offering/assets``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump({"id": asset_id, "mime": mime, "path": blob_path}, handle)


def test_asset_path_resolves_shipped_asset() -> None:
    """``asset path <shipped-id>`` prints an existing filesystem path, exit 0."""
    from pathlib import Path

    result = runner.invoke(
        charter_app,
        ["pack", "asset", "path", _SHIPPED_ASSET_ID],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    resolved = Path(result.stdout.strip())  # CR-02: stderr now carries a deprecation notice
    assert resolved.is_file(), f"resolved path does not exist: {resolved}"
    assert resolved.name == "docs_structural_lint.py"


def test_asset_path_json_carries_id_path_and_tier() -> None:
    """``asset path <id> --json`` emits a machine-readable id/path/tier record."""
    result = runner.invoke(
        charter_app,
        ["pack", "asset", "path", _SHIPPED_ASSET_ID, "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["id"] == _SHIPPED_ASSET_ID
    assert payload["tier"] == "builtin"
    assert payload["path"].endswith("docs_structural_lint.py")


def test_asset_path_unknown_id_exits_nonzero_naming_it() -> None:
    """An unknown asset id exits non-zero and names the offending id (A-7)."""
    result = runner.invoke(
        charter_app,
        ["pack", "asset", "path", "no-such-asset-xyz"],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "no-such-asset-xyz" in result.output


#: The repository's own org-tier pack; its sidecars anchor at this ``assets/`` dir.
_INTERNAL_ASSETS_DIR = Path(__file__).resolve().parents[4] / "packs" / "internal" / "assets"
_INTERNAL_ASSET_IDS = sorted(
    YAML(typ="safe").load(sidecar.read_text(encoding="utf-8"))["id"]
    for sidecar in _INTERNAL_ASSETS_DIR.glob("*.asset.yaml")
)


@pytest.mark.parametrize("asset_id", _INTERNAL_ASSET_IDS)
def test_asset_path_resolves_every_internal_pack_asset_to_its_blob(asset_id: str) -> None:
    """Each org-tier asset in ``packs/internal`` resolves to a file that exists.

    Org sidecar ``path`` values are relative to the pack's ``assets/`` folder;
    a ``path: assets/<blob>`` sidecar resolves to a doubled ``assets/assets/``
    path that is not on disk.
    """
    result = runner.invoke(
        charter_app,
        ["pack", "asset", "path", asset_id, "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["tier"] == "org"
    assert Path(payload["path"]).parent == _INTERNAL_ASSETS_DIR
    assert Path(payload["path"]).is_file()


def test_asset_list_includes_shipped_asset_and_tier() -> None:
    """``asset list`` names the shipped asset and its built-in tier."""
    result = runner.invoke(
        charter_app,
        ["pack", "asset", "list"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert _SHIPPED_ASSET_ID in result.output
    assert "builtin" in result.output


def test_asset_list_json_is_a_record_list() -> None:
    """``asset list --json`` yields a list of id/tier/path records."""
    result = runner.invoke(
        charter_app,
        ["pack", "asset", "list", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    shipped = next(row for row in payload if row["id"] == _SHIPPED_ASSET_ID)
    assert shipped["tier"] == "builtin"
    assert shipped["path"].endswith("docs_structural_lint.py")


def test_resolved_path_str_renders_marker_on_not_found_not_just_escape() -> None:
    """``_resolved_path_str`` must not crash ``asset list`` on an anchoring miss.

    ``resolve_path`` raises :class:`AssetNotFoundError` (not only
    :class:`AssetPathEscapeError`) when a loaded manifest's anchor can't be
    determined -- e.g. an org-tier manifest whose source isn't under any
    currently configured org dir, or a project-provenance manifest with no
    project dir (``AssetRepository._anchor_for``). Before this fix
    ``_resolved_path_str`` caught only ``AssetPathEscapeError``, so
    ``asset list`` (which iterates every loaded manifest) would crash with an
    uncaught traceback instead of rendering the unresolvable marker it already
    renders for the escape case.
    """
    from unittest.mock import create_autospec

    from charter.offering.assets.repository import AssetNotFoundError, AssetRepository

    from specify_cli.cli.commands.charter.pack_asset import _UNRESOLVABLE, _resolved_path_str

    repo = create_autospec(AssetRepository, instance=True)
    repo.resolve_path.side_effect = AssetNotFoundError("orphaned-org-asset")

    assert _resolved_path_str(repo, "orphaned-org-asset") == _UNRESOLVABLE


def test_asset_list_empty_prints_message_and_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No resolvable manifests at all -> a friendly message, exit 0 (not a crash)."""
    from charter.offering.assets.repository import AssetRepository

    empty_built_in = tmp_path / "shipped" / "assets" / "built-in"
    empty_built_in.mkdir(parents=True)
    monkeypatch.setattr(
        asset_module, "_build_asset_repository", lambda: AssetRepository(built_in_dir=empty_built_in)
    )

    result = runner.invoke(charter_app, ["pack", "asset", "list"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "No charter pack assets found." in result.output


def test_asset_path_escape_exits_nonzero_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A manifest whose blob path escapes its anchoring root refuses fail-closed (NFR-006)."""
    from charter.offering.assets.repository import AssetRepository

    built_in = tmp_path / "shipped" / "assets" / "built-in"
    _write_asset_manifest(
        built_in / "evil.asset.yaml",
        asset_id="evil",
        mime="text/plain",
        blob_path="../../../../etc/passwd",
    )
    monkeypatch.setattr(
        asset_module, "_build_asset_repository", lambda: AssetRepository(built_in_dir=built_in)
    )

    result = runner.invoke(charter_app, ["pack", "asset", "path", "evil"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "evil" in result.output


def test_asset_path_unknown_id_json_carries_id_and_error() -> None:
    """``path --json`` on a failure renders the id/error record, not rich text."""
    result = runner.invoke(
        charter_app,
        ["pack", "asset", "path", "no-such-asset-xyz", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["id"] == "no-such-asset-xyz"
    assert "no-such-asset-xyz" in payload["error"]
