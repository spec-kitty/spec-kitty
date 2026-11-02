"""Acceptance tests for the doc-kitty site scaffold (#6930; ADR 2026-10-31-1 D-1, D-2, D-8).

The ``site/`` project builds ``../docs`` with doc-kitty. These tests pin what the
committed files must say, without running Node:

* the site's folder exclusion and index basenames come from the single authority
  ``scripts/docs/_dockitty_contract.py`` through the generated
  ``site/dockitty-contract.json`` (one authority, checked for parity);
* the configuration values the ADR fixes (site URL, base, docs directory, drafts off,
  doc-kitty pinned by a 40-character commit);
* nothing the later steps own leaks in (no redirects, #6933; no diagrams, #6936);
* ``docs/_meta/sections.yaml`` registers every published top-level section.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from scripts.docs import _dockitty_contract as contract
from scripts.docs import site_contract

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
DOCS = ROOT / "docs"
CONTRACT_JSON = SITE / "dockitty-contract.json"
ASTRO_CONFIG = SITE / "astro.config.mjs"
SECTIONS = DOCS / "_meta" / "sections.yaml"

_PIN = re.compile(r"^github:spec-kitty/doc-kitty#(?P<sha>[0-9a-f]{40})&path:/src$")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- single exclusion authority (FR-003) -------------------------------------------------------


def test_contract_json_equals_the_python_authority() -> None:
    data = json.loads(_read(CONTRACT_JSON))

    assert data["exclude"] == list(contract.EXCLUDED_FOLDERS)
    assert data["indexBasename"] == list(contract.INDEX_BASENAMES)
    assert site_contract.check(CONTRACT_JSON) == []


def test_a_drifted_contract_copy_is_refused(tmp_path: Path) -> None:
    """Negative control: the parity check is not vacuous."""
    drifted = tmp_path / "dockitty-contract.json"
    data = json.loads(site_contract.render())
    data["exclude"] = data["exclude"][:-1]
    drifted.write_text(json.dumps(data), encoding="utf-8")

    problems = site_contract.check(drifted)

    assert problems, "a contract copy missing an excluded folder must be refused"
    assert any("exclude" in problem for problem in problems)


def test_a_missing_contract_copy_is_refused(tmp_path: Path) -> None:
    assert site_contract.check(tmp_path / "absent.json")


def test_write_produces_a_copy_that_checks_clean(tmp_path: Path) -> None:
    target = tmp_path / "dockitty-contract.json"

    site_contract.write(target)

    assert site_contract.check(target) == []
    assert _read(target) == site_contract.render()


def test_astro_config_reads_the_contract_and_restates_no_folder() -> None:
    config = _read(ASTRO_CONFIG)

    assert "dockitty-contract.json" in config
    for folder in contract.EXCLUDED_FOLDERS:
        assert f"'{folder}'" not in config and f'"{folder}"' not in config, f"{folder} restated in astro.config.mjs"


# --- configuration values (FR-001, FR-002) -----------------------------------------------------


def test_astro_config_fixes_the_adr_values() -> None:
    config = _read(ASTRO_CONFIG)

    assert "site: 'https://docs.spec-kitty.ai'" in config
    assert re.search(r"base: '/'", config)
    assert "docsDir: '../docs'" in config
    assert "diagrams: false" in config, "diagrams stay off until the PlantUML service (#6936)"


def test_no_redirects_are_wired_yet() -> None:
    """Redirects are #6933's: doc-kitty #253 makes Astro ``.html`` redirect keys fatal."""
    config = _read(ASTRO_CONFIG)

    assert not re.search(r"\bredirects\s*:", config), "no Astro redirects option"
    assert not re.search(r"\blegacyHtmlRedirects\s*:", config), "no legacyHtmlRedirects option"


def test_drafts_are_off_in_production() -> None:
    lines = [line.strip() for line in _read(SITE / ".env.production").splitlines()]

    assert "DK_PUBLISH_DRAFTS=off" in lines


def test_doc_kitty_is_pinned_by_commit_in_manifest_and_lockfile() -> None:
    manifest = json.loads(_read(SITE / "package.json"))
    match = _PIN.match(manifest["dependencies"]["@spec-kitty/doc-toolkit"])

    assert match, "doc-kitty must be a git dependency pinned by a 40-character commit (ADR D-2)"
    assert match["sha"] in _read(SITE / "pnpm-lock.yaml")
    for peer in ("astro", "@astrojs/starlight", "@astrojs/markdown-remark"):
        assert peer in manifest["dependencies"], f"{peer} is declared next to the toolkit"


_HTTPS_REPO = "https://github.com/spec-kitty/doc-kitty.git"


def _toolkit_lock_lines() -> list[str]:
    return [line for line in _read(SITE / "pnpm-lock.yaml").splitlines() if "doc-kitty" in line]


def test_the_lockfile_fetches_doc_kitty_over_https_with_no_ssh_key() -> None:
    """pnpm clones whatever ``resolution.repo`` names; a runner has no SSH key (ADR D-2, review cycle 1).

    pnpm writes the SSH form when its public-repository probe fails (as behind a proxy), and a
    local ``url.insteadOf`` rewrite then hides it. The lockfile must name the HTTPS repository.
    """
    lines = _toolkit_lock_lines()

    assert lines, "the lockfile records the toolkit"
    assert _ssh_lock_lines("\n".join(lines)) == []
    assert any(f"repo: {_HTTPS_REPO}" in line for line in lines)


def _ssh_lock_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if re.search(r"git@github\.com|ssh://|git\+ssh", line)]


def test_an_ssh_lockfile_repo_is_caught() -> None:
    """Negative control: the SSH form pnpm writes behind a proxy is refused."""
    mutant = "    resolution: {commit: abc, path: /src, repo: git@github.com:spec-kitty/doc-kitty.git, type: git}\n"

    assert _ssh_lock_lines(mutant) == [mutant.strip()]


def test_content_config_uses_the_native_loader_without_a_shim() -> None:
    content = _read(SITE / "src" / "content.config.ts")

    assert "docKittyDocsLoader({ base: '../docs' })" in content
    assert "filter" not in content, "native exclude replaces the spike's shim"
    assert "exclude" not in content, "the loader reads exclude from the integration"


def test_public_files_and_404_notice() -> None:
    assert _read(SITE / "public" / "CNAME").strip() == "docs.spec-kitty.ai"
    robots = _read(SITE / "public" / "robots.txt")
    assert "Sitemap: https://docs.spec-kitty.ai/sitemap-index.xml" in robots
    assert "/kitty-specs/" in _read(SITE / "src" / "pages" / "404.astro")


# --- section registry (FR-004) -----------------------------------------------------------------


def _published_top_level_folders() -> set[str]:
    folders = set()
    for path in DOCS.iterdir():
        if path.is_dir() and not path.name.startswith(("_", ".")) and not contract.is_excluded(path.name) and any(path.rglob("*.md")):
            folders.add(path.name)
    return folders


def test_every_published_section_is_registered() -> None:
    registry = yaml.safe_load(_read(SECTIONS))
    ids = [section["id"] for section in registry["sections"]]

    assert len(ids) == len(set(ids)), "section ids are unique"
    assert set(ids) == _published_top_level_folders()
    for section in registry["sections"]:
        assert isinstance(section["label"], str) and section["label"]
        assert isinstance(section["order"], int)


def test_plans_has_restricted_feeds_and_development_is_its_own_section() -> None:
    sections = {section["id"]: section for section in yaml.safe_load(_read(SECTIONS))["sections"]}

    assert sections["plans"]["feeds"] == ["sitemap"], "plans: no llms, agent or rss feed (ADR D-8)"
    assert "development" in sections
