"""SC-008 — the asset how-to is executable end to end (WP14, T077).

#3037's complaint is that "ship executable logic as an asset" reads as advice a
downstream reader cannot follow. The remedy is only real if the published
how-to's commands actually run. This is the doc-as-test that keeps them running:
it reads the **asset section of the published how-to**
(``docs/development/how-to/create-a-doctrine-artifact.md``), lifts the manifest example and
the asset directory and the ``spec-kitty charter pack asset path`` invocation
*out of the doc*, replays them
against a **fresh project**, and asserts the documented command resolves the
project-tier blob. If the doc drifts (the manifest shape changes, the example id
is renamed, the resolve command is edited) the extraction or the resolution
fails here — the doc cannot claim an executable remedy it no longer delivers.

In-process against the dev layout (``unit``/``fast``); the falsifiable
clean-wheel resolution proof (SC-003) is the sibling
``test_asset_resolution_wheel.py``. Here the point is different: the *documented
authoring sequence* a downstream operator would copy, executed verbatim.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from kernel.charter_pack_paths import project_pack_path
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_HOWTO = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "development"
    / "how-to"
    / "create-a-doctrine-artifact.md"
)

#: A fenced ``yaml`` block whose body declares all three required manifest
#: fields — this is how we recognise the manifest example among any other yaml
#: blocks in the how-to without pinning a brittle line range.
_YAML_BLOCK = re.compile(r"```yaml\n(?P<body>.*?)\n```", re.DOTALL)

#: The documented resolve command, e.g.
#: ``spec-kitty charter pack asset path team-release-checklist``.
_RESOLVE_CMD = re.compile(r"spec-kitty charter pack asset path\s+(?P<asset_id>[a-z0-9-]+)")

#: The documented ``mkdir -p <project asset dir>`` step (Step A of the recipe).
_ASSET_DIR_CMD = re.compile(r"mkdir -p (?P<asset_dir>\.kittify/\S+)")


def _read_howto() -> str:
    assert _HOWTO.is_file(), f"asset how-to missing: {_HOWTO}"
    return _HOWTO.read_text(encoding="utf-8")


def _extract_manifest_example(text: str) -> dict[str, str]:
    """Return the first fenced yaml block that is a full asset manifest.

    A manifest is identified structurally — it declares ``id``, ``mime`` and
    ``path`` — so the test does not care where in the file it sits.
    """
    yaml = YAML(typ="safe")
    for match in _YAML_BLOCK.finditer(text):
        try:
            loaded = yaml.load(match.group("body"))
        except Exception:  # noqa: BLE001 — a non-yaml example is simply skipped
            continue
        if isinstance(loaded, dict) and {"id", "mime", "path"} <= loaded.keys():
            return {str(k): str(v) for k, v in loaded.items()}
    pytest.fail(
        "no asset manifest example (id + mime + path) found in the asset how-to; "
        "the section that review-gates.md promises is absent or drifted"
    )


def test_howto_has_asset_section() -> None:
    """The how-to that ``review-gates.md`` cites actually covers the asset kind."""
    text = _read_howto().lower()
    assert "asset" in text, (
        "create-a-doctrine-artifact.md contains 'asset' zero times, yet "
        "review-gates.md cites it as the asset how-to (#3037)"
    )


def test_documented_asset_flow_resolves_in_a_fresh_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replay the how-to's manifest + resolve command against a fresh project.

    Executes the documented authoring sequence exactly as a downstream operator
    would copy it: place the blob, write the sidecar manifest, then run the
    documented ``spec-kitty charter pack asset path <id>``. The command must resolve
    the project-tier blob and exit 0 (SC-008 / A-7).
    """
    text = _read_howto()
    manifest = _extract_manifest_example(text)
    asset_id = manifest["id"]
    blob_rel = manifest["path"]

    # The documented resolve command must name the very id the manifest declares
    # — otherwise the how-to would tell a reader to resolve something it never
    # authored.
    resolve_ids = {m.group("asset_id") for m in _RESOLVE_CMD.finditer(text)}
    assert asset_id in resolve_ids, (
        f"manifest id {asset_id!r} is never resolved by a documented "
        f"'spec-kitty charter pack asset path' command; found {sorted(resolve_ids)}"
    )

    # Fresh project: the documented asset directory must be the project pack's
    # assets/ directory, the one the resolver reads (kernel.charter_pack_paths).
    dir_match = _ASSET_DIR_CMD.search(text)
    assert dir_match, "the how-to has no `mkdir -p .kittify/...` step for the asset directory"
    project = tmp_path / "fresh-project"
    assets_dir = project / dir_match.group("asset_dir")
    assert assets_dir == project_pack_path(project, "assets"), (
        f"the how-to places assets in {dir_match.group('asset_dir')!r}, not the project pack's assets/ directory"
    )
    blob_path = assets_dir / blob_rel
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_text("# placeholder blob for the how-to proof\n", encoding="utf-8")
    manifest_path = assets_dir / f"{blob_rel}.asset.yaml"
    yaml = YAML()
    with manifest_path.open("w", encoding="utf-8") as handle:
        yaml.dump(manifest, handle)

    # SPECIFY_REPO_ROOT points resolution at the fresh project (highest-priority
    # override in locate_project_root) so the run is isolated from this checkout.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(project))

    result = runner.invoke(
        charter_app,
        ["pack", "asset", "path", asset_id],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    # Parse `.stdout` (stdout only), matching what a real
    # `$(spec-kitty charter pack asset path ...)` shell capture gets (bash
    # `$(...)` never captures stderr), not `.output` (Click 8.2+'s
    # stdout+stderr merge).
    resolved = Path(result.stdout.strip())
    assert resolved == blob_path.resolve() or resolved == blob_path, (
        f"documented command resolved {resolved}, expected the project blob "
        f"{blob_path}"
    )
    assert resolved.is_file(), f"resolved asset path does not exist: {resolved}"
