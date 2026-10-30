"""``charter status`` must report org-pack paths that escape their roots (#6733).

``spec-kitty doctor charter-packs`` exits 1 for an authored ``drg/fragment.yaml`` node whose
``body_path`` escapes its pack root (``ORG_FRAGMENT_BODY_PATH_ESCAPE``) and for an org asset
sidecar whose ``path`` escapes the pack's ``assets/`` root (``ORG_ASSET_PATH_ESCAPE``) — #6418.
``charter status --json`` reported ``org_layer.errors: []`` for the very same pack, so the
machine-readable "what does this project govern" answer was a clean bill for a pack the doctor
fails.

RED before this fix: both escape cases below found ``errors == []``, and the crash cases had no
behaviour to pin. The contained-pack case is the positive control: it passes before and after, so
a check that simply flags every pack cannot satisfy this module. All cases share one fixture
builder, so the escaping and contained halves cannot drift apart.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT: Path = Path(__file__).resolve().parents[5]
_FIXTURE_ORG_PACK: Path = _REPO_ROOT / "tests" / "architectural" / "_fixtures" / "org_packs" / "example_org"

_ESCAPING = "../../../../etc/hostname"
_ESCAPING_NODE_ID = "team-asset"
_ESCAPING_ASSET_ID = "team-logo"

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixture builder — one pack, one configured position, three shapes
# ---------------------------------------------------------------------------


def _build_repo(tmp_path: Path) -> Path:
    """A project with the example org pack configured at ``charter_packs.org.packs[0]``."""
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
        ),
        encoding="utf-8",
    )
    return tmp_path


def _add_escaping_node(repo: Path, body_path: str) -> None:
    """Append one authored node declaring *body_path* to the pack's ``drg/fragment.yaml``."""
    fragment = repo / "example_org" / "drg" / "fragment.yaml"
    data = yaml.safe_load(fragment.read_text(encoding="utf-8"))
    data["nodes"].append({"id": _ESCAPING_NODE_ID, "kind": "assets", "title": "Team asset", "body_path": body_path})
    fragment.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _add_escaping_asset(repo: Path, path: str) -> None:
    """Write one schema-valid asset sidecar whose blob path is *path*."""
    assets = repo / "example_org" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / f"{_ESCAPING_ASSET_ID}.asset.yaml").write_text(
        yaml.safe_dump({"id": _ESCAPING_ASSET_ID, "mime": "text/plain", "path": path}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# The channel itself — org_layer.errors, read from the collector the command calls
# ---------------------------------------------------------------------------


def test_status_reports_an_escaping_body_path(tmp_path: Path) -> None:
    """An escaping authored ``body_path`` reaches ``org_layer['errors']`` (#6733, FR-001).

    RED before the fix: ``errors == []`` while ``doctor charter-packs`` reported the same node
    from the same loaded fragments.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    repo = _build_repo(tmp_path)
    _add_escaping_node(repo, _ESCAPING)

    result = _collect_org_layer_status(repo)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any(_ESCAPING_NODE_ID in entry and _ESCAPING in entry and "is not contained in the pack root" in entry for entry in errors), (
        f"charter status must name the escaping node on its errors channel; got {errors}"
    )


def test_status_reports_an_escaping_asset_path(tmp_path: Path) -> None:
    """An escaping asset sidecar ``path`` reaches ``org_layer['errors']`` (#6733, FR-002).

    RED before the fix: ``errors == []``; ``doctor charter-packs`` reported
    ``ORG_ASSET_PATH_ESCAPE`` for the same pack.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    repo = _build_repo(tmp_path)
    _add_escaping_asset(repo, _ESCAPING)

    result = _collect_org_layer_status(repo)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any(_ESCAPING_ASSET_ID in entry and _ESCAPING in entry and "assets/ root" in entry for entry in errors), (
        f"charter status must name the escaping asset on its errors channel; got {errors}"
    )


def test_status_reports_both_escapes_without_one_hiding_the_other(tmp_path: Path) -> None:
    """Two independent faults are two findings, not one (#6733, FR-001 + FR-002)."""
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    repo = _build_repo(tmp_path)
    _add_escaping_node(repo, _ESCAPING)
    _add_escaping_asset(repo, _ESCAPING)

    result = _collect_org_layer_status(repo)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any(_ESCAPING_NODE_ID in entry for entry in errors), errors
    assert any(_ESCAPING_ASSET_ID in entry for entry in errors), errors


def test_contained_pack_is_clean(tmp_path: Path) -> None:
    """The positive control: the shipped fixture's own contained paths stay clean (FR-006).

    Without this, the escaping cases above would pass on a check that flagged every pack.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    repo = _build_repo(tmp_path)
    _add_escaping_node(repo, "directives/sox-controls.directive.yaml")
    _add_escaping_asset(repo, "img/team-logo.txt")

    result = _collect_org_layer_status(repo)

    assert result["errors"] == [], result


def test_a_crashed_containment_check_is_reported_not_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A check that could not RUN is not a check that PASSED (#6733, FR-003).

    The alternative — swallowing the fault — turns "the containment check crashed" into "no
    escapes", the exact false-clean this fix exists to remove.
    """
    import charter.activation.drg_activation as drg_activation
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("registry exploded")

    monkeypatch.setattr(drg_activation, "find_org_body_path_escapes", _boom)
    monkeypatch.setattr(drg_activation, "find_org_asset_path_escapes", _boom)

    result = _collect_org_layer_status(_build_repo(tmp_path))

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any("org-layer body_path check failed" in entry and "registry exploded" in entry for entry in errors), errors
    assert any("org-layer asset path check failed" in entry and "registry exploded" in entry for entry in errors), errors


def test_escapes_are_reported_even_when_the_merge_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A refused merge must not hide the escape findings (#6733, FR-003).

    ``doctor charter-packs`` collects its escapes before it merges for exactly this reason; the
    status collector must not regress into "the merge raised, so report nothing else".
    """
    import charter.activation.drg_activation as drg_activation
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("merge exploded")

    monkeypatch.setattr(drg_activation, "merge_three_layers", _boom)

    repo = _build_repo(tmp_path)
    _add_escaping_node(repo, _ESCAPING)

    result = _collect_org_layer_status(repo)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any(_ESCAPING_NODE_ID in entry for entry in errors), errors
    assert any("merge exploded" in entry for entry in errors), errors


def test_status_json_schema_is_unchanged(tmp_path: Path) -> None:
    """No new key: the findings ride ``errors`` (NFR-003).

    A caller parsing the current ``org_layer`` shape must keep working, and an unread payload slot
    is the inert-schema defect this collector's own docstring ratchets against.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    repo = _build_repo(tmp_path)
    _add_escaping_node(repo, _ESCAPING)

    result = _collect_org_layer_status(repo)

    assert set(result) == {"has_built_in", "packs", "collision_warnings", "errors"}, result.keys()


# ---------------------------------------------------------------------------
# The command — the finding reaches the JSON and the human view
# ---------------------------------------------------------------------------


def _invoke_status(repo: Path, *args: str) -> object:
    """Run the real ``charter status`` command with only the unrelated collectors stubbed."""
    with (
        patch.object(charter_pkg, "find_repo_root", return_value=repo),
        patch.object(charter_pkg, "_collect_synthesis_status", return_value={"stub": True}),
        patch(
            "specify_cli.cli.commands.charter.status._collect_governance_reference_status",
            return_value={"available": True, "references": [], "warnings": []},
        ),
        patch("specify_cli.charter_runtime.freshness.compute_freshness") as compute_freshness,
    ):
        compute_freshness.return_value.to_dict.return_value = {}
        return runner.invoke(charter_app, ["status", *args], catch_exceptions=False)


def test_status_command_json_names_the_escaping_node(tmp_path: Path) -> None:
    """The command surfaces the finding: ``payload['org_layer']['errors']`` (#6733, FR-001)."""
    repo = _build_repo(tmp_path)
    _add_escaping_node(repo, _ESCAPING)

    result = _invoke_status(repo, "--json")

    assert result.exit_code == 0, result.output
    errors = json.loads(result.output)["org_layer"]["errors"]
    assert any(_ESCAPING_NODE_ID in entry for entry in errors), errors


def test_render_org_layer_prints_the_finding(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The one ``errors`` channel also feeds the human view (#6733, FR-001).

    ``_render_text`` calls ``_render_org_layer`` on every ``charter status`` run, so the renderer
    is the production surface for the text view; the JSON command test above covers the command
    wiring.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status
    from specify_cli.cli.commands.charter.status import _render_org_layer

    repo = _build_repo(tmp_path)
    _add_escaping_node(repo, _ESCAPING)

    _render_org_layer(_collect_org_layer_status(repo))

    printed = capsys.readouterr().out
    assert _ESCAPING_NODE_ID in printed, printed
    assert "is not contained in the pack root" in printed, printed
