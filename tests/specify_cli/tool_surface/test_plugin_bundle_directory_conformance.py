"""Directory conformance for the ``spec-kitty plugin build`` bundles (issue #6479).

Each assertion runs against a bundle produced by the real build entry point, so a
wiring regression fails here and not only in a helper test. The absence
assertions each carry a positive control on the same fixture: a probe that could
not see anything must not be able to report "absent".

Pinned requirements (``spec-kitty-internal-plugins#2`` §2.2/§2.3, recorded in the
mission's ``research.md`` Decision 3):

* Claude.ai and Cowork refuse a plugin with a top-level ``bin/``.
* ``hooks/hooks.json`` is the host default; declaring it is redundant.
* Codex/OpenAI ``interface`` field limits: displayName ≤30, shortDescription ≤30,
  longDescription ≤4000, developerName ≤80, capabilities ≤20 × ≤120,
  defaultPrompt ≤3 × ≤128; images are square, ≥48px, ≤5 MiB, ``./`` paths.
"""

from __future__ import annotations

import importlib.util
import json
import re
import struct
from pathlib import Path

import pytest

from specify_cli.tool_surface.bundles.claude import ClaudeBundleProjector
from specify_cli.tool_surface.bundles.codex import CodexBundleProjector

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?$")

#: Pinned limit for the OpenAI ``interface`` listing fields.
INTERFACE_LIMITS = {
    "displayName": 30,
    "shortDescription": 30,
    "longDescription": 4000,
    "developerName": 80,
}

#: Pinned image limits for ``logo`` / ``composerIcon``.
IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MIN_EDGE = 48


def _build_claude(tmp_path: Path) -> Path:
    return ClaudeBundleProjector(tmp_path / "dist").build(skip_validate=True)


def _build_codex(tmp_path: Path) -> Path:
    return CodexBundleProjector(tmp_path / "dist").build()


def _manifest(bundle_dir: Path, relative: str) -> dict[str, object]:
    return json.loads((bundle_dir / relative).read_text(encoding="utf-8"))


def _png_edge_lengths(path: Path) -> tuple[int, int]:
    """Read a PNG's pixel dimensions straight from its IHDR chunk."""
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    width, height = struct.unpack(">II", header[16:24])
    return width, height


# ---------------------------------------------------------------------------
# Claude Code: no top-level bin/, no redundant hooks pointer, real links
# ---------------------------------------------------------------------------


def test_claude_bundle_has_no_top_level_bin_directory(tmp_path: Path) -> None:
    """Claude.ai and Cowork refuse a plugin that contains a top-level ``bin/``."""
    bundle_dir = _build_claude(tmp_path)

    # Positive control: the tree probe does see real top-level directories, so an
    # empty result below means "no bin/", not "nothing was built".
    top_level = sorted(entry.name for entry in bundle_dir.iterdir())
    assert "skills" in top_level and "agents" in top_level, top_level

    assert "bin" not in top_level
    wrappers = [path for path in bundle_dir.rglob("*") if path.is_file() and path.parent.name == "bin"]
    assert not wrappers, f"bundle still stages a wrapper under bin/: {wrappers}"


def test_claude_bundle_no_longer_ships_the_wrapper_module(tmp_path: Path) -> None:
    """The generator goes with the output it existed to produce (NFR-004)."""
    assert importlib.util.find_spec("specify_cli.tool_surface.bundles.claude_wrapper") is None
    _build_claude(tmp_path)


def test_claude_manifest_does_not_redeclare_the_default_hooks_file(tmp_path: Path) -> None:
    """``hooks/hooks.json`` is the host default; the pointer was the bare-path bug."""
    bundle_dir = _build_claude(tmp_path)
    manifest = _manifest(bundle_dir, ".claude-plugin/plugin.json")

    # Positive control on the same fixture: the manifest is real and readable.
    assert manifest["name"] == "spec-kitty"
    assert "hooks" not in manifest
    # The hooks file itself is still staged and still a valid empty record.
    assert json.loads((bundle_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")) == {"hooks": {}}


def test_claude_manifest_carries_identity_links_and_semver(tmp_path: Path) -> None:
    bundle_dir = _build_claude(tmp_path)
    manifest = _manifest(bundle_dir, ".claude-plugin/plugin.json")

    version = manifest["version"]
    assert isinstance(version, str) and _SEMVER.match(version), version
    assert manifest["homepage"] == "https://spec-kitty.ai/"
    assert manifest["repository"] == "https://github.com/spec-kitty/spec-kitty"
    assert manifest["license"] == "MIT"
    assert manifest["author"]["url"] == "https://github.com/spec-kitty/spec-kitty"
    # Component declarations keep the ``./`` form the host resolves.
    assert all(str(path).startswith("./skills/") for path in manifest["skills"])
    assert all(str(path).startswith("./agents/") for path in manifest["agents"])


# ---------------------------------------------------------------------------
# Codex / OpenAI: pinned interface limits, ./ paths, declared images
# ---------------------------------------------------------------------------


def test_codex_manifest_meets_the_pinned_directory_limits(tmp_path: Path) -> None:
    bundle_dir = _build_codex(tmp_path)
    manifest = _manifest(bundle_dir, ".codex-plugin/plugin.json")

    # Positive control: the manifest is real before we assert its shape.
    assert manifest["name"] == "spec-kitty"
    assert _SEMVER.match(str(manifest["version"])), manifest["version"]

    interface = manifest["interface"]
    assert isinstance(interface, dict)
    missing = set(INTERFACE_LIMITS) - set(interface)
    assert not missing, f"Codex manifest is missing listing fields: {sorted(missing)}"
    for field, limit in INTERFACE_LIMITS.items():
        value = interface[field]
        assert isinstance(value, str) and value, field
        assert len(value) <= limit, f"{field} is {len(value)} characters (limit {limit})"

    for url_field in ("websiteURL", "supportURL", "privacyPolicyURL"):
        assert str(interface[url_field]).startswith("https://"), url_field

    prompts = interface["defaultPrompt"]
    assert 1 <= len(prompts) <= 3, prompts
    assert all(isinstance(prompt, str) and len(prompt) <= 128 for prompt in prompts), prompts

    capabilities = interface["capabilities"]
    assert isinstance(capabilities, list) and len(capabilities) <= 20
    assert all(len(capability) <= 120 for capability in capabilities)

    assert interface["category"] == "Developer Tools"
    assert manifest["skills"] == "./skills/"
    assert manifest["requires_local_executor"] is True
    assert manifest["homepage"] == "https://spec-kitty.ai/"
    assert manifest["repository"] == "https://github.com/spec-kitty/spec-kitty"
    assert manifest["license"] == "MIT"


def test_codex_manifest_keeps_the_forbidden_key_guard(tmp_path: Path) -> None:
    bundle_dir = _build_codex(tmp_path)
    manifest = _manifest(bundle_dir, ".codex-plugin/plugin.json")
    assert manifest["name"] == "spec-kitty"  # positive control
    assert "hooks" not in manifest
    assert "agents" not in manifest


def test_codex_declared_images_exist_inside_the_bundle(tmp_path: Path) -> None:
    """A manifest that points at a file it did not stage is worse than no field."""
    bundle_dir = _build_codex(tmp_path)
    interface = _manifest(bundle_dir, ".codex-plugin/plugin.json")["interface"]

    for field in ("logo", "composerIcon"):
        declared = interface[field]
        assert declared.startswith("./assets/"), declared
        asset = bundle_dir / declared[2:]
        assert asset.is_file(), f"{field} points at a file the bundle does not contain: {declared}"
        assert asset.stat().st_size <= IMAGE_MAX_BYTES
        width, height = _png_edge_lengths(asset)
        assert width == height >= IMAGE_MIN_EDGE, f"{declared} is {width}x{height}"


def test_codex_build_refuses_when_the_packaged_asset_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A manifest that declares an image the package cannot supply is a refusal."""
    from specify_cli.tool_surface.bundles import codex as codex_module

    monkeypatch.setattr(codex_module, "_BRAND_LOGO_NAME", "not-shipped.png")
    with pytest.raises(codex_module.BuildError, match="Brand asset is missing"):
        codex_module.CodexBundleProjector(tmp_path / "dist").build()
