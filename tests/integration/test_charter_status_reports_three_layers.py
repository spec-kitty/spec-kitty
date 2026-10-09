"""FR-002: charter status reports all three DRG layers.

covers: FR-002 — expected GREEN at: WP07 final commit

RED on planning base: ``spec-kitty charter status`` does not yet surface
organisation-layer state.  WP07 turns this GREEN by adding an org-layer
section to the ``status`` command (charter.py) that enumerates the configured
packs with their fetched/missing status.

ATDD anchor: ``atdd-coverage.md`` FR-002 / partial AC-1.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

pytestmark = [pytest.mark.integration]

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_FIXTURE_ORG_PACK: Path = (
    _REPO_ROOT
    / "tests"
    / "architectural"
    / "_fixtures"
    / "org_packs"
    / "example_org"
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_sync_result_stub(repo_root: Path) -> object:
    """Return a minimal sync-result stub with canonical_root set."""
    class _Stub:
        canonical_root = repo_root
    return _Stub()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo_with_org_pack(tmp_path: Path) -> Path:
    """Construct a tmp repo with ``.kittify/config.yaml`` pointing at the
    fixture org pack copied alongside the repo root."""
    pack_dest = tmp_path / "example_org"
    shutil.copytree(_FIXTURE_ORG_PACK, pack_dest)
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: example-org
                    local_path: {pack_dest}
            """
        )
    )
    return tmp_path


@pytest.fixture
def tmp_repo_without_org_pack(tmp_path: Path) -> Path:
    """A minimal repo with no org packs configured (NFR-001 baseline)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            """\
            agents:
              available:
                - claude
            """
        )
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_charter_status_reports_built_in_org_and_project(
    tmp_repo_with_org_pack: Path,
    charter_cwd_isolation: Callable[..., Path],
) -> None:
    """When an org pack is configured, charter status --json must include an
    ``org_layer`` key in its payload that lists the configured packs.

    Verified via JSON output for precise structural assertions.
    """
    charter_cwd_isolation(tmp_repo_with_org_pack)
    from specify_cli.cli.commands.charter import app as charter_app

    with (
        patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            return_value=_make_sync_result_stub(tmp_repo_with_org_pack),
        ),
    ):
        result = runner.invoke(charter_app, ["status", "--json"])

    assert result.exit_code in (0, 1), (
        f"charter status exited with unexpected code {result.exit_code}: "
        f"{result.stdout}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"charter status --json did not produce valid JSON: {exc}\n"
            f"stdout: {result.stdout!r}"
        )

    assert "org_layer" in payload, (
        f"charter status JSON must include 'org_layer' key when org packs are "
        f"configured. Got keys: {list(payload.keys())}"
    )
    org_layer = payload["org_layer"]
    assert isinstance(org_layer, dict), (
        f"org_layer must be a dict, got {type(org_layer)}"
    )
    packs = org_layer.get("packs", [])
    assert len(packs) == 1, (
        f"expected 1 configured org pack, got {len(packs)}: {packs}"
    )
    pack = packs[0]
    assert pack.get("name") == "example-org", (
        f"pack name mismatch: {pack}"
    )


def test_charter_status_reports_only_two_layers_without_org_pack(
    tmp_repo_without_org_pack: Path,
    charter_cwd_isolation: Callable[..., Path],
) -> None:
    """NFR-001: when no org pack configured, charter status must not
    introduce an empty '[org]' section that would change the existing
    output contract.

    Either ``org_layer`` is absent from the JSON, OR ``org_layer.packs``
    is an empty list — never a non-empty org section for a repo with no
    configured packs.
    """
    charter_cwd_isolation(tmp_repo_without_org_pack)
    from specify_cli.cli.commands.charter import app as charter_app

    with (
        patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            return_value=_make_sync_result_stub(tmp_repo_without_org_pack),
        ),
    ):
        result = runner.invoke(charter_app, ["status", "--json"])

    assert result.exit_code in (0, 1), (
        f"charter status exited with unexpected code {result.exit_code}: "
        f"{result.stdout}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"charter status --json did not produce valid JSON: {exc}\n"
            f"stdout: {result.stdout!r}"
        )

    # When no org packs are configured, either the key is absent entirely OR
    # the packs list is empty — no non-empty fake [org] section.
    if "org_layer" in payload:
        org_layer = payload["org_layer"]
        packs = org_layer.get("packs", [])
        assert packs == [], (
            f"NFR-001: when no org packs are configured, org_layer.packs must be "
            f"empty, got: {packs}"
        )
