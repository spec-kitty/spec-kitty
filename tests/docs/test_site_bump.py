"""The doc-kitty bump helper (#6930; ADR 2026-10-31-1 D-2 steps 1 and 2), tested offline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.docs import site_bump
from scripts.docs.site_bump import BumpError, bump_manifest, fetch_toolkit_manifest, pin_spec, resolve_ref

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
OLD = "1" * 40
TAG_OBJECT = "a" * 40
TAG_COMMIT = "b" * 40
BRANCH = "c" * 40
TOOLKIT_MANIFEST: dict[str, Any] = {
    "name": "@spec-kitty/doc-toolkit",
    "peerDependencies": {
        "astro": ">=7.9.0 <8",
        "@astrojs/starlight": ">=0.44.0 <0.45.0",
        "@astrojs/markdown-remark": ">=7.5.0 <8",
        "starlight-openapi": "0.27.0",
    },
}


def _site_manifest() -> dict[str, Any]:
    return {
        "name": "spec-kitty-docsite",
        "dependencies": {
            "@spec-kitty/doc-toolkit": pin_spec(OLD),
            "astro": ">=7.2.10 <8",
            "@astrojs/starlight": ">=0.42.0 <0.43.0",
            "@astrojs/markdown-remark": ">=7.3.0 <8",
        },
    }


def _ls_remote(_ref: str) -> str:
    return f"{TAG_OBJECT}\trefs/tags/v1.0.0\n{TAG_COMMIT}\trefs/tags/v1.0.0^{{}}\n{BRANCH}\trefs/heads/main\n"


# --- step 1: resolve the ref ---------------------------------------------------------------------


def test_a_commit_is_taken_as_given_without_a_network_read() -> None:
    def refuse(_ref: str) -> str:
        raise AssertionError("a 40-character commit needs no ls-remote")

    assert resolve_ref(TAG_COMMIT.upper(), ls_remote=refuse) == TAG_COMMIT


def test_a_tag_resolves_to_the_commit_it_points_at() -> None:
    assert resolve_ref("v1.0.0", ls_remote=_ls_remote) == TAG_COMMIT


def test_a_lightweight_tag_and_a_branch_resolve() -> None:
    assert resolve_ref("v2", ls_remote=lambda _r: f"{TAG_OBJECT}\trefs/tags/v2\n") == TAG_OBJECT
    assert resolve_ref("main", ls_remote=_ls_remote) == BRANCH


def test_an_unknown_ref_is_refused() -> None:
    with pytest.raises(BumpError, match="names no tag"):
        resolve_ref("v9.9.9", ls_remote=lambda _r: "")


# --- step 2: rewrite the pin and the peers -------------------------------------------------------


def test_the_pin_and_the_peer_ranges_follow_the_toolkit() -> None:
    bumped = bump_manifest(_site_manifest(), TAG_COMMIT, TOOLKIT_MANIFEST)

    deps = bumped["dependencies"]
    assert deps["@spec-kitty/doc-toolkit"] == f"github:spec-kitty/doc-kitty#{TAG_COMMIT}&path:/src"
    assert deps["astro"] == ">=7.9.0 <8"
    assert deps["@astrojs/starlight"] == ">=0.44.0 <0.45.0"
    assert deps["@astrojs/markdown-remark"] == ">=7.5.0 <8"
    assert "starlight-openapi" not in deps, "optional peers are not added"
    assert bumped["name"] == "spec-kitty-docsite"


def test_the_input_manifest_is_not_mutated() -> None:
    original = _site_manifest()

    bump_manifest(original, TAG_COMMIT, TOOLKIT_MANIFEST)

    assert original == _site_manifest()


def test_a_toolkit_without_a_required_peer_is_refused() -> None:
    toolkit = {"peerDependencies": {"astro": ">=7 <8"}}

    with pytest.raises(BumpError, match="@astrojs/starlight"):
        bump_manifest(_site_manifest(), TAG_COMMIT, toolkit)


def test_a_site_without_the_toolkit_is_refused() -> None:
    with pytest.raises(BumpError, match="does not depend"):
        bump_manifest({"dependencies": {}}, TAG_COMMIT, TOOLKIT_MANIFEST)


def test_the_toolkit_manifest_is_read_at_the_commit() -> None:
    urls: list[str] = []

    def fetch(url: str) -> str:
        urls.append(url)
        return json.dumps(TOOLKIT_MANIFEST)

    assert fetch_toolkit_manifest(TAG_COMMIT, fetch=fetch) == TOOLKIT_MANIFEST
    assert urls == [f"https://raw.githubusercontent.com/spec-kitty/doc-kitty/{TAG_COMMIT}/src/package.json"]


def test_an_unreadable_toolkit_manifest_is_refused() -> None:
    def fail(_url: str) -> str:
        raise OSError("offline")

    with pytest.raises(BumpError, match="cannot read"):
        fetch_toolkit_manifest(TAG_COMMIT, fetch=fail)
    with pytest.raises(BumpError, match="40-character"):
        fetch_toolkit_manifest("v1.0.0", fetch=fail)


# --- the command ---------------------------------------------------------------------------------


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    site.mkdir()
    (site / "package.json").write_text(json.dumps(_site_manifest(), indent=2) + "\n", encoding="utf-8")
    return site


def test_the_command_rewrites_package_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    site = _site(tmp_path)
    monkeypatch.setattr(site_bump, "_git_ls_remote", _ls_remote)
    monkeypatch.setattr(site_bump, "_http_get", lambda _url: json.dumps(TOOLKIT_MANIFEST))

    assert site_bump.main(["v1.0.0", "--site-dir", str(site), "--no-install"]) == 0

    deps = json.loads((site / "package.json").read_text(encoding="utf-8"))["dependencies"]
    assert deps["@spec-kitty/doc-toolkit"] == pin_spec(TAG_COMMIT)


def test_an_unresolvable_ref_leaves_package_json_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    site = _site(tmp_path)
    before = (site / "package.json").read_text(encoding="utf-8")
    monkeypatch.setattr(site_bump, "_git_ls_remote", lambda _r: "")

    assert site_bump.main(["v9.9.9", "--site-dir", str(site), "--no-install"]) == 1

    assert (site / "package.json").read_text(encoding="utf-8") == before


def test_the_committed_site_pin_is_the_shape_the_helper_writes() -> None:
    manifest = json.loads((ROOT / "site" / "package.json").read_text(encoding="utf-8"))
    pin = manifest["dependencies"]["@spec-kitty/doc-toolkit"]
    sha = pin.split("#", 1)[1].split("&", 1)[0]

    assert pin == pin_spec(sha)


# --- the make targets (FR-005, FR-006) -----------------------------------------------------------


def _make_recipe(target: str) -> str:
    lines = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(f"{target}:"))
    recipe = []
    for line in lines[start + 1 :]:
        if not line.startswith("\t"):
            break
        recipe.append(line.strip())
    return "\n".join(recipe)


def test_make_docs_site_checks_the_contract_and_installs_frozen() -> None:
    recipe = _make_recipe("docs-site")

    assert "scripts.docs.site_contract --check" in recipe
    assert "pnpm install --frozen-lockfile" in recipe
    assert "pnpm run build" in recipe


def test_make_docs_site_bump_runs_the_helper_and_requires_ref() -> None:
    recipe = _make_recipe("docs-site-bump")

    assert "scripts.docs.site_bump" in recipe
    assert "$(REF)" in recipe
