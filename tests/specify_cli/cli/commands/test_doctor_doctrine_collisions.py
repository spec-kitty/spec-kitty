"""CLI test: `spec-kitty doctor charter-packs` surfaces collision summary (MEDIUM-1).

The mission-review remediation for MEDIUM-1 added `ArtifactLayerCollisionWarning`
emission in the loaders plus a `Collisions` section in `doctor charter-packs` so
operators can audit which artifacts in their resolved doctrine surface come
from shadowed lower layers (ADR `docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md`).
"""

from __future__ import annotations

import contextlib
import json
import textwrap
from pathlib import Path

from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_directive(path: Path, item_id: str, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""
            schema_version: "1.0"
            id: {item_id}
            title: "{title}"
            intent: "Test intent."
            enforcement: required
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _write_kittify_config_with_pack(repo_root: Path, pack_path: Path) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        textwrap.dedent(
            f"""
            charter_packs:
              org:
                packs:
                  - name: test-pack
                    local_path: {pack_path}
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _resolve_built_in_directive_id(repo_root: Path) -> str:
    """Pick a known shipped directive id so we can collide against it."""
    built_in_dir = repo_root / "packs" / "built-in" / "directives"
    for path in sorted(built_in_dir.glob("*.directive.yaml")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("id:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("no shipped directive found")


def test_doctor_doctrine_text_shows_collisions(tmp_path: Path) -> None:
    """When an org pack shadows a shipped directive, `doctor charter-packs` lists it."""
    real_repo = Path(__file__).resolve().parents[4]
    built_in_id = _resolve_built_in_directive_id(real_repo)

    pack_dir = tmp_path / "pack"
    _write_directive(
        pack_dir / "directives" / "override.directive.yaml",
        item_id=built_in_id,
        title="Org Override Title",
    )
    _write_kittify_config_with_pack(tmp_path, pack_dir)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(doctor_app, ["charter-packs"], catch_exceptions=False)

    # WP01 (C5): the configured org pack has no fetched DRG fragment, so the
    # org-DRG load records a "pack missing" error → the honest health flag
    # reports unhealthy and the command exits 1 (loud over hidden). Collision
    # rendering is unaffected.
    assert result.exit_code == 1, result.stdout
    # The Collisions section must appear and include the shadowed id.
    assert "Collisions" in result.stdout
    assert built_in_id in result.stdout
    assert "shadowed" in result.stdout


def test_doctor_doctrine_text_reports_no_collisions_when_pack_disjoint(tmp_path: Path) -> None:
    """A pack whose directives have novel IDs produces no collision lines."""
    pack_dir = tmp_path / "pack"
    _write_directive(
        pack_dir / "directives" / "novel.directive.yaml",
        item_id="DIRECTIVE_FRESH_999",
        title="Novel directive",
    )
    _write_kittify_config_with_pack(tmp_path, pack_dir)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(doctor_app, ["charter-packs"], catch_exceptions=False)

    # WP01 (C5): missing org-DRG fragment → unhealthy → RC=1 (loud over hidden).
    assert result.exit_code == 1, result.stdout
    assert "none — every artifact resolves from a single layer" in result.stdout


def test_doctor_doctrine_json_emits_collisions_array(tmp_path: Path) -> None:
    """The --json output includes a `collisions` array describing each shadowed id."""
    real_repo = Path(__file__).resolve().parents[4]
    built_in_id = _resolve_built_in_directive_id(real_repo)

    pack_dir = tmp_path / "pack"
    _write_directive(
        pack_dir / "directives" / "override.directive.yaml",
        item_id=built_in_id,
        title="Org Override Title",
    )
    _write_kittify_config_with_pack(tmp_path, pack_dir)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"], catch_exceptions=False)

    # WP01 (C5): missing org-DRG fragment → unhealthy → RC=1 (loud over hidden).
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["org_configured"] is True
    assert isinstance(payload["collisions"], list)
    ids = [c["item_id"] for c in payload["collisions"]]
    assert built_in_id in ids
    # Schema sanity: each entry carries the expected fields.
    match = next(c for c in payload["collisions"] if c["item_id"] == built_in_id)
    assert match["higher_layer"] == "org"
    assert match["lower_layer"] == "builtin"
    assert match["kind"] == "directive"
    assert isinstance(match["replaced"], int)
    assert isinstance(match["inherited"], int)
