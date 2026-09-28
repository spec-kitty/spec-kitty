"""Red-first pins for WP08 (#5221 section C, supply-chain doctrine owner).

DIRECTIVE_051 states its five threat-class pillars exactly once; the
ecosystem-neutral ``supply-chain-install-safety`` tactic (pinned id, per
plan.md "Pinned successor ids") carries the operational checklist with no
ecosystem-specific tokens; the JS/TS-specific steps (lockfile file names,
lifecycle-script commands, Node LTS) move to the ``javascript-supply-chain``
toolguide; a ``python-supply-chain`` toolguide is added; ``dependency-hygiene``
references the tactic instead of restating its pillar list.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKS = _REPO_ROOT / "packs" / "built-in"

_DIRECTIVE_PATH = _PACKS / "directives" / "051-supply-chain-install-safety.directive.yaml"
_TACTIC_PATH = _PACKS / "tactics" / "security" / "supply-chain-install-safety.tactic.yaml"
_DEP_HYGIENE_PATH = _PACKS / "tactics" / "architecture" / "dependency-hygiene.tactic.yaml"
_JS_TOOLGUIDE_YAML = _PACKS / "toolguides" / "javascript-supply-chain.toolguide.yaml"
_JS_TOOLGUIDE_MD = _PACKS / "toolguides" / "JAVASCRIPT_SUPPLY_CHAIN.md"
_PY_TOOLGUIDE_YAML = _PACKS / "toolguides" / "python-supply-chain.toolguide.yaml"
_PY_TOOLGUIDE_MD = _PACKS / "toolguides" / "PYTHON_SUPPLY_CHAIN.md"

_YAML = YAML(typ="safe")

# The five ecosystem-neutral pillars DIRECTIVE_051 must state EXACTLY ONCE
# (in `intent`) and never restate elsewhere in the same file.
_PILLAR_TERMS = (
    "registry authenticity",
    "package freshness",
    "lifecycle-script",
    "lockfile-driven",
    "IoC",
)

_ECOSYSTEM_TOKENS = ("npm", "pnpm", "yarn", "package-lock", "pip", "poetry", "maven")


def _read_text(path: Path) -> str:
    assert path.exists(), f"expected file missing: {path}"
    return path.read_text(encoding="utf-8")


def _count(text: str, term: str) -> int:
    return len(re.findall(re.escape(term), text, flags=re.IGNORECASE))


class TestDirective051StatesPillarsOnce:
    def test_each_pillar_term_appears_exactly_once(self) -> None:
        text = _read_text(_DIRECTIVE_PATH)
        for term in _PILLAR_TERMS:
            assert _count(text, term) == 1, f"pillar term {term!r} must appear exactly once in DIRECTIVE_051, found {_count(text, term)}"

    def test_no_node_lts_language(self) -> None:
        text = _read_text(_DIRECTIVE_PATH)
        assert "Node LTS" not in text
        assert "Node Active LTS" not in text

    def test_directive_still_loads_as_valid_yaml(self) -> None:
        data = _YAML.load(_read_text(_DIRECTIVE_PATH))
        assert data["id"] == "DIRECTIVE_051"
        assert data["enforcement"] == "required"

    def test_integrity_rules_forbid_silently_accepting_an_adverse_result(self) -> None:
        """C-005: base directive forbade silently ACCEPTING a bad outcome
        (unexpected registry, stale/too-new package, unexpected lifecycle
        script, IoC hit) — not merely forbade skipping the check. The
        rework must restate this as a rule, once, without repeating a
        counted pillar phrase."""
        data = _YAML.load(_read_text(_DIRECTIVE_PATH))
        rules = " ".join(data["integrity_rules"]).lower()
        assert "adverse" in rules or "never silently accepted" in rules
        assert "never silently accepted" in rules

    def test_integrity_rules_forbid_blanket_lifecycle_script_enablement(self) -> None:
        """C-005: blanket enablement of install-time hook scripts must be
        stated as a violation of the directive, not merely a
        failure_mode in the tactic (a tactic's failure_modes is not
        normative)."""
        data = _YAML.load(_read_text(_DIRECTIVE_PATH))
        rules = " ".join(data["integrity_rules"]).lower()
        assert "blanket" in rules
        assert "violation" in rules


class TestTacticIsEcosystemNeutral:
    def test_no_applies_to_languages_field(self) -> None:
        data = _YAML.load(_read_text(_TACTIC_PATH))
        assert "applies_to_languages" not in data

    def test_id_is_pinned(self) -> None:
        data = _YAML.load(_read_text(_TACTIC_PATH))
        assert data["id"] == "supply-chain-install-safety"

    def test_no_ecosystem_tokens(self) -> None:
        text = _read_text(_TACTIC_PATH)
        lowered = text.lower()
        for token in _ECOSYSTEM_TOKENS:
            assert token not in lowered, f"ecosystem token {token!r} must not appear in the ecosystem-neutral supply-chain-install-safety tactic"

    def test_no_node_lts_language(self) -> None:
        text = _read_text(_TACTIC_PATH)
        assert "Node LTS" not in text
        assert "Node Active LTS" not in text

    def test_no_adversarial_evidence_contract_literal_path(self) -> None:
        text = _read_text(_TACTIC_PATH)
        assert "adversarial-evidence-contract.md" not in text

    def test_references_javascript_and_python_toolguides(self) -> None:
        data = _YAML.load(_read_text(_TACTIC_PATH))
        ref_ids = {(r.get("type"), r.get("id")) for r in data.get("references", [])}
        assert ("toolguide", "javascript-supply-chain") in ref_ids
        assert ("toolguide", "python-supply-chain") in ref_ids


class TestJavaScriptToolguideCarriesTheMovedSteps:
    def test_toolguide_yaml_exists_and_loads(self) -> None:
        data = _YAML.load(_read_text(_JS_TOOLGUIDE_YAML))
        assert data["id"] == "javascript-supply-chain"
        assert data["guide_path"] == "packs/built-in/toolguides/JAVASCRIPT_SUPPLY_CHAIN.md"
        assert data["applies_to_languages"] == ["javascript", "typescript"]

    def test_guide_covers_lockfile_lifecycle_scripts_and_node_lts(self) -> None:
        text = _read_text(_JS_TOOLGUIDE_MD)
        lowered = text.lower()
        assert "lockfile" in lowered
        assert "lifecycle script" in lowered
        assert "node" in lowered and "lts" in lowered
        # Ecosystem-specific evidence must actually be concrete, not a
        # restatement of the neutral pillar list.
        assert "package-lock.json" in text or "pnpm-lock.yaml" in text or "yarn.lock" in text

    def test_guide_names_the_frozen_lockfile_install_commands(self) -> None:
        """Non-blocking review note: a trimmed guide that drops `npm ci`
        and its frozen/immutable lockfile flags must fail this test."""
        text = _read_text(_JS_TOOLGUIDE_MD)
        assert "npm ci" in text
        assert "--frozen-lockfile" in text or "--immutable" in text

    def test_pnpm_enable_pre_post_scripts_replaced_with_real_dependency_gate(self) -> None:
        """C-005 fix 3: `pnpm config set enable-pre-post-scripts false`
        governs the PROJECT's own `pnpm run` pre/post hooks, not dependency
        install scripts. Dependency lifecycle scripts are governed by
        `ignore-scripts`/`onlyBuiltDependencies`."""
        text = _read_text(_JS_TOOLGUIDE_MD)
        assert "enable-pre-post-scripts" not in text
        assert "onlyBuiltDependencies" in text or "ignore-scripts=true" in text

    def test_yarn_classic_and_berry_lockfile_flags_both_named(self) -> None:
        """`--frozen-lockfile` is Yarn classic; Yarn Berry uses
        `--immutable`. Both must be named, not conflated."""
        text = _read_text(_JS_TOOLGUIDE_MD)
        assert "--immutable" in text
        assert "Berry" in text
        assert "classic" in text.lower()

    def test_yarn_berry_enable_scripts_false_named(self) -> None:
        text = _read_text(_JS_TOOLGUIDE_MD)
        assert "enableScripts" in text


class TestJavaToolguideLoads:
    _JAVA_TOOLGUIDE_YAML = _PACKS / "toolguides" / "java-supply-chain.toolguide.yaml"
    _JAVA_TOOLGUIDE_MD = _PACKS / "toolguides" / "JAVA_SUPPLY_CHAIN.md"

    def test_toolguide_yaml_exists_and_loads(self) -> None:
        data = _YAML.load(_read_text(self._JAVA_TOOLGUIDE_YAML))
        assert data["id"] == "java-supply-chain"
        assert data["guide_path"] == "packs/built-in/toolguides/JAVA_SUPPLY_CHAIN.md"
        assert data["applies_to_languages"] == ["java"]

    def test_guide_exists_and_is_non_empty(self) -> None:
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        assert len(text) > 0

    def test_no_gpg_skip_as_a_dependency_check(self) -> None:
        """`mvn verify -Dgpg.skip=false` signs the project's OWN artifacts;
        it verifies nothing about dependencies."""
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        yaml_text = _read_text(self._JAVA_TOOLGUIDE_YAML)
        assert "gpg.skip" not in text
        assert "gpg.skip" not in yaml_text

    def test_no_offline_go_offline_in_the_lockfile_section(self) -> None:
        """`mvn -o dependency:go-offline` is Maven-only, does not read
        Gradle's lockfile/verification-metadata, and `-o` contradicts
        `go-offline` (which exists to download)."""
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        yaml_text = _read_text(self._JAVA_TOOLGUIDE_YAML)
        assert "go-offline" not in text
        assert "go-offline" not in yaml_text

    def test_covers_maven_strict_checksums_and_gradle_write_verification(self) -> None:
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        assert "--strict-checksums" in text or " -C" in text
        assert "--write-verification-metadata" in text
        assert "verification-metadata.xml" in text
        assert "--write-locks" in text

    def test_dependency_tree_comment_does_not_claim_repositories(self) -> None:
        """`mvn dependency:tree` does not show repositories."""
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        assert "dependency:tree" in text
        for line in text.splitlines():
            if "dependency:tree" in line and "#" in line:
                assert "repositories" not in line.lower()

    def test_maven_central_timestamp_gap_is_not_overstated(self) -> None:
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        assert "does not publish a first-seen timestamp api" not in text.lower()

    def test_maven_checksum_guarantee_is_not_overclaimed(self) -> None:
        """Review cycle 2, fix 1: Maven's `-C`/`checksumPolicy: fail` only
        verifies against checksums the SAME repository serves — it catches
        transfer corruption/mismatch, not a substituted artifact from a
        compromised repository/mirror. It must not be described as the
        same guarantee as Gradle's committed verification metadata."""
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        lowered = text.lower()
        assert "same fail-closed guarantee" not in lowered
        assert "substituted artifact fails" not in lowered
        assert "mutated or substituted artifact fails" not in lowered

    def test_write_locks_precondition_is_documented(self) -> None:
        """Review cycle 2, fix 3: `gradle --write-locks` only persists
        resolution for configurations that already have dependency
        locking enabled (`dependencyLocking { lockAllConfigurations() }`
        or per-configuration) — it is a no-op otherwise."""
        text = _read_text(self._JAVA_TOOLGUIDE_MD)
        assert "dependencyLocking" in text or "lockAllConfigurations" in text


class TestPythonToolguideExists:
    def test_toolguide_yaml_exists_and_loads(self) -> None:
        data = _YAML.load(_read_text(_PY_TOOLGUIDE_YAML))
        assert data["id"] == "python-supply-chain"
        assert data["guide_path"] == "packs/built-in/toolguides/PYTHON_SUPPLY_CHAIN.md"
        assert data["applies_to_languages"] == ["python"]

    def test_guide_covers_pip_uv_poetry_lock_hashes_and_index_pinning(self) -> None:
        text = _read_text(_PY_TOOLGUIDE_MD)
        lowered = text.lower()
        for token in ("pip", "uv", "poetry", "hash", "index"):
            assert token in lowered, f"expected {token!r} coverage in PYTHON_SUPPLY_CHAIN.md"

    def test_uv_sync_locked_is_the_drift_gate_not_frozen(self) -> None:
        """C-005 fix 2: `--frozen` installs without checking staleness;
        `--locked` is the mode that fails when the lock is out of date."""
        text = _read_text(_PY_TOOLGUIDE_MD)
        assert "uv sync --locked" in text
        assert "uv sync --frozen           # frozen install from uv.lock, fails on drift" not in text

    def test_no_pip_index_versions_claim(self) -> None:
        """`pip index versions` neither confirms the resolved index nor
        shows timestamps, and is experimental — it must not be cited as
        evidence for either the registry or the freshness control."""
        text = _read_text(_PY_TOOLGUIDE_MD)
        assert "pip index versions" not in text

    def test_covers_extra_index_url_dependency_confusion_risk(self) -> None:
        text = _read_text(_PY_TOOLGUIDE_MD)
        assert "--extra-index-url" in text

    def test_covers_hash_generation_commands(self) -> None:
        text = _read_text(_PY_TOOLGUIDE_MD)
        assert "--generate-hashes" in text

    def test_yaml_commands_use_locked_not_frozen_for_drift_gate(self) -> None:
        data = _YAML.load(_read_text(_PY_TOOLGUIDE_YAML))
        commands = data.get("commands", [])
        assert any("uv sync --locked" in c for c in commands)
        assert not any(c.strip() == "pip index versions <package>" for c in commands)

    def test_drift_gate_does_not_rewrite_the_lock_before_checking_it(self) -> None:
        """Review cycle 2, fix 2: `uv lock && uv sync --locked` on one line
        defeats itself — `uv lock` rewrites a stale lock, so `--locked`
        then always passes. The gate must be `uv sync --locked` alone
        and/or `uv lock --check`, with `uv lock` kept only as a separate
        developer refresh step."""
        text = _read_text(_PY_TOOLGUIDE_MD)
        assert "uv lock && uv sync --locked" not in text
        assert "uv lock --check" in text or "uv sync --locked" in text


class TestDependencyHygieneReferencesTheTactic:
    def test_references_supply_chain_tactic_by_id(self) -> None:
        data = _YAML.load(_read_text(_DEP_HYGIENE_PATH))
        ref_ids = {(r.get("type"), r.get("id")) for r in data.get("references", [])}
        assert ("tactic", "supply-chain-install-safety") in ref_ids

    def test_when_text_cites_javascript_supply_chain_toolguide_by_id(self) -> None:
        """Non-blocking review note: cite the toolguide by id, cheap and
        avoids ambiguity about which JS/TS guidance is meant."""
        text = _read_text(_DEP_HYGIENE_PATH)
        assert "javascript-supply-chain" in text

    def test_restates_no_pillar_list(self) -> None:
        text = _read_text(_DEP_HYGIENE_PATH)
        lowered = text.lower()
        # The moved JS/TS install-safety sub-steps must not be restated here.
        for banned in (
            "preinstall",
            "postinstall",
            ".nvmrc",
            "package-lock.json",
            "registry.npmjs.org",
        ):
            assert banned not in lowered, f"dependency-hygiene must not restate the moved supply-chain install-safety step content ({banned!r} found)"
