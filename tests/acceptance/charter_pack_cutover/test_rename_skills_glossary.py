"""Skill families, three names, glossary and reachability pins: FR-008, FR-009, FR-013, FR-014, US4, OD-1, OD-5, OD-7 (#3732, T008)."""

from __future__ import annotations

import ast
import importlib
import json
import re
import shutil
from pathlib import Path

import pytest

from ._requirements import REMOVED_SKILL_IDS, REPO_ROOT, RETIRED_EXTRA_SKILL_IDS, is_living_path
from ._support import covers, describe, git_init_commit, load_yaml, output_of, read_json_output, run_cli
from .legacy_fixtures import MISSION_TYPES, EDITED_SKILL, finish, project_from_template, write_doctrine_pack, write_yaml
from .test_package_split import _python_names

SKILLS_ROOT = REPO_ROOT / "src" / "charter" / "offering" / "skills"
NEW_SKILLS = (
    "spk-charter-governance",
    "spk-charter-glossary",
    "spk-charter-profile-load",
    "spk-charter-spdd-reasons",
    "spk-practice-bulk-edit",
    "spk-practice-semantic-compression",
    "spk-practice-show-me",
)
#: Shipped bytes of removed skills, frozen at the mission base (WP01).
STATIC_REMOVED_SKILLS = REPO_ROOT / "tests" / "fixtures" / "charter_pack_cutover" / "static" / "removed_skills"
GLOSSARY = REPO_ROOT / "docs" / "context" / "charter.md"
#: The FR-018-exempt glossary surfaces that record retired terms as deprecated (WP24 plan).
GLOSSARY_SEED = REPO_ROOT / ".kittify" / "glossaries" / "spec_kitty_core.yaml"
GLOSSARY_PACK = REPO_ROOT / "packs" / "built-in" / "glossary_packs" / "spec-kitty-core.glossary-pack.yaml"
NEW_TERMS = ("Charter offering", "Charter Pack", "Activation preset", "Active charter", "Project layer", "Charter Bundle")
RETIRED_TERMS = ("Doctrine Pack", "Doctrine Pack ID", "Doctrine Catalog", "Charter Selection", "Pack Default Charter")
#: A term both seed and pack already record as deprecated (control for the reader).
KNOWN_DEPRECATED_TERM = "main repo"
MISSING_ADR = "2026-08-22-2"
CUTOVER_ADR = REPO_ROOT / "docs" / "adr" / "4.x" / "2026-10-06-2-charter-offering-active-charter-and-activation-presets.md"


# --------------------------------------------------------------------------------------
# FR-008 / US4 / OD-7: skill families
# --------------------------------------------------------------------------------------


@covers("FR-008", "OD-7", "C-004")
@pytest.mark.corpus
def test_fr008_skill_families_present() -> None:
    assert (REPO_ROOT / "packs" / "built-in" / "agent_profiles" / "doctrine-daphne.agent.yaml").is_file(), "doctrine-daphne is unchanged (C-004)"
    missing = [name for name in NEW_SKILLS if not (SKILLS_ROOT / name / "SKILL.md").is_file()]
    assert missing == [], missing
    remaining = [name for name in REMOVED_SKILL_IDS if (SKILLS_ROOT / name).exists()]
    assert remaining == [], remaining


@covers("FR-008")
def test_fr008_removed_names_are_retired() -> None:
    retired = importlib.import_module("specify_cli.skills.retired").RETIRED_CANONICAL_SKILL_NAMES
    assert retired, "control: the retired set is the real one"
    missing = sorted((set(REMOVED_SKILL_IDS) | set(RETIRED_EXTRA_SKILL_IDS)) - set(retired))
    assert missing == [], missing


def install_old_global_skill(catalog: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Install *name* into the user-global roots the way an older CLI did (its shipped bytes, recorded in the global inventory).

    The global retirement removes only inventory-owned, unchanged copies; a hand-written
    directory under a retired name is preserved as unproven content (asset preservation, #4017).
    """
    agent_skills = importlib.import_module("specify_cli.runtime.agent_skills")
    registry = importlib.import_module("specify_cli.skills.registry")
    shutil.copytree(STATIC_REMOVED_SKILLS / name, catalog / name)
    with monkeypatch.context() as patch:
        patch.setattr(agent_skills, "_discover_registry", lambda: registry.SkillRegistry(catalog))
        agent_skills.ensure_global_agent_skills()


@covers("FR-008", "US4-1")
@pytest.mark.integration
@pytest.mark.git_repo
def test_fr008_upgrade_installs_new_and_removes_old(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    global_copy = home / ".claude" / "skills" / "spk-doctrine-charter" / "SKILL.md"
    install_old_global_skill(tmp_path / "old-catalog", "spk-doctrine-charter", monkeypatch)
    assert global_copy.is_file(), "control: the old skill is installed in the user-global root"
    project = project_from_template("installed_removed_skills", tmp_path / "p")
    upgraded = run_cli(["upgrade", "--yes", "--no-worktrees"], project)
    # The fixture's edited copy is a managed file left for review: the upgrade contract exits 1 for it.
    assert upgraded.exit_code in (0, 1), describe(upgraded)
    if upgraded.exit_code == 1:
        # Exit 1 is acceptable only for that reason: the edited copy was kept for review.
        text = output_of(upgraded)
        assert EDITED_SKILL in text and "kept" in text.lower(), describe(upgraded)
    listed = run_cli(["charter", "list"], project)
    assert listed.exit_code == 0, describe(listed)
    for root in (project / ".claude" / "skills", project / ".agents" / "skills", home / ".claude" / "skills"):
        names = {p.name for p in root.iterdir()} if root.is_dir() else set()
        assert not names & set(REMOVED_SKILL_IDS) - {"spk-doctrine-show-me"}, (root, sorted(names))
    assert (project / ".claude" / "skills" / "spk-charter-governance" / "SKILL.md").is_file()
    manifest = json.loads((project / ".kittify" / "skills-manifest.json").read_text(encoding="utf-8"))
    orphans = [e["installed_path"] for e in manifest["entries"] if not (project / e["installed_path"]).exists()]
    assert orphans == [], orphans
    command_manifest = json.loads((project / ".kittify" / "command-skills-manifest.json").read_text(encoding="utf-8"))
    assert command_manifest["entries"], "control: the command-skill manifest is populated"
    command_orphans = [e["path"] for e in command_manifest["entries"] if not (project / e["path"]).exists()]
    assert command_orphans == [], command_orphans


# --------------------------------------------------------------------------------------
# FR-009: three meanings, three names
# --------------------------------------------------------------------------------------

OLD_CLASS_NAMES = ("CharterPackManager", "CharterPackConfigError")


def _src_bindings(names: tuple[str, ...], root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        found = set(names) & _python_names(path.read_text(encoding="utf-8"))
        hits += [f"{path}: {n}" for n in sorted(found)]
    return hits


@covers("FR-009")
def test_fr009_three_names_no_alias(tmp_path: Path) -> None:
    (tmp_path / "planted.py").write_text("CharterPackManager = object\n", encoding="utf-8")
    assert _src_bindings(OLD_CLASS_NAMES, tmp_path), "self-test: a planted alias is found"
    assert importlib.import_module("charter.activation.pack_manager").ActiveCharterManager
    assert importlib.import_module("charter.activation.pack_context").ActiveCharterConfigError
    src = REPO_ROOT / "src"
    assert _src_bindings(OLD_CLASS_NAMES, src) == []
    literal = [str(p) for p in src.rglob("*.py") if "CHARTER_PACK_CONFIG_INVALID" in p.read_text(encoding="utf-8")]
    assert literal == [], literal


@covers("FR-009")
@pytest.mark.integration
@pytest.mark.git_repo
def test_fr009_json_error_code(tmp_path: Path) -> None:
    project = project_from_template("two_org_packs", tmp_path / "p")
    (project / ".kittify" / "config.yaml").write_text("charter_packs: [unclosed\n", encoding="utf-8")
    git_init_commit(project, "fixture: malformed config")
    result = run_cli(["agent", "mission", "create", "demo-mission", "--json"], project)
    assert result.exit_code != 0, describe(result)
    text = output_of(result)
    assert "ACTIVE_CHARTER_CONFIG_INVALID" in text and "CHARTER_PACK_CONFIG_INVALID" not in text, describe(result)


@covers("FR-009")
@pytest.mark.integration
def test_fr009_tool_surface_kind(tmp_path: Path) -> None:
    enums = importlib.import_module("specify_cli.tool_surface.enums")
    assert enums.ToolSurfaceKind.CHARTER_SKILL.value == "charter_skill"
    assert not hasattr(enums.ToolSurfaceKind, "DOCTRINE_SKILL")
    project = project_from_template("two_org_packs", tmp_path / "p")
    ok = run_cli(["doctor", "tool-surfaces", "--kind", "charter-skill", "--json"], project)
    assert ok.exit_code == 0, describe(ok)
    payload = json.dumps(read_json_output(ok))
    assert "doctrine_skill" not in payload
    old = run_cli(["doctor", "tool-surfaces", "--kind", "doctrine-skill", "--json"], project)
    assert old.exit_code == 2, describe(old)


@covers("US3-4", "OD-1")
@pytest.mark.integration
def test_us3_4_doctrine_pack_id_rejected_in_org_charter(tmp_path: Path) -> None:
    entry = {"activation_context": {"mission_type": "software-dev"}, "artifact_id": "acceptance-test-first", "artifact_kind": "tactics"}
    base = load_yaml(write_doctrine_pack(tmp_path / "scaffold") / "org-charter.yaml")
    good = write_doctrine_pack(tmp_path / "good")
    write_yaml(good / "org-charter.yaml", {**base, "schema_version": "2", "activations": [{**entry, "charter_pack_id": "built-in"}]})
    ok = run_cli(["charter", "org", "validate", str(good)], tmp_path)
    assert ok.exit_code == 0, describe(ok)
    bad = write_doctrine_pack(tmp_path / "bad")
    write_yaml(bad / "org-charter.yaml", {**base, "schema_version": "2", "activations": [{**entry, "doctrine_pack_id": "built-in"}]})
    refused = run_cli(["charter", "org", "validate", str(bad)], tmp_path)
    assert refused.exit_code != 0, describe(refused)
    assert "doctrine_pack_id" in output_of(refused) and "charter_pack_id" in output_of(refused), describe(refused)


def _project_with_org_activation(project: Path, pack_field: str) -> Path:
    entry = {"activation_context": {"mission_type": "software-dev"}, "artifact_id": "acceptance-test-first", "artifact_kind": "tactics"}
    pack = write_doctrine_pack(project / "orgpack")
    base = load_yaml(pack / "org-charter.yaml")
    write_yaml(pack / "org-charter.yaml", {**base, "schema_version": "2", "activations": [{**entry, pack_field: "built-in"}]})
    return finish(project, {"charter_packs": {"org": {"packs": [{"name": "acme", "local_path": "orgpack"}]}}, "mission_type_activations": MISSION_TYPES})


@covers("US3-4", "OD-1")
@pytest.mark.integration
def test_us3_4_doctrine_pack_id_rejected_on_load(tmp_path: Path) -> None:
    """Loading an org pack that carries the retired field exits 1 naming code, file, field and replacement."""
    good = _project_with_org_activation(tmp_path / "good", "charter_pack_id")
    ok = run_cli(["charter", "context", "--action", "implement", "--json"], good)
    assert ok.exit_code == 0, describe(ok)
    assert read_json_output(ok)["org_charter"]["present"] is True, describe(ok)
    bad = _project_with_org_activation(tmp_path / "bad", "doctrine_pack_id")
    org_charter = str(bad / "orgpack" / "org-charter.yaml")
    refused = run_cli(["charter", "context", "--action", "implement", "--json"], bad)
    assert refused.exit_code == 1, describe(refused)
    payload = read_json_output(refused)
    assert payload["code"] == "RETIRED_PACK_FIELD", describe(refused)
    assert org_charter in payload["error"] and "doctrine_pack_id" in payload["error"] and "charter_pack_id" in payload["error"], describe(refused)
    text = run_cli(["charter", "generate", "--no-from-interview"], bad)
    assert text.exit_code == 1, describe(text)
    flat = " ".join(output_of(text).split())
    assert "Error (RETIRED_PACK_FIELD):" in flat and "docs/migrations/charter-pack-cutover.md" in flat, describe(text)
    assert "doctrine_pack_id" in flat and "charter_pack_id" in flat and "org-charter.yaml" in flat, describe(text)
    lint = run_cli(["charter", "lint"], bad)
    assert "retired_pack_field" in output_of(lint) and "RETIRED_PACK_FIELD" in output_of(lint), describe(lint)


@covers("OD-5", "C-005")
@pytest.mark.integration
def test_od5_charter_sync_noop_left_in_place(tmp_path: Path) -> None:
    """Regression guard (passes at base): compatibility residue unrelated to doctrine vocabulary stays (OD-5, follow-up #5828)."""
    project = project_from_template("two_org_packs", tmp_path / "p")
    result = run_cli(["charter", "sync", "--help"], project)
    assert result.exit_code == 0, describe(result)
    assert "sync" in output_of(run_cli(["charter", "--help"], project))


# --------------------------------------------------------------------------------------
# FR-013: glossary and citations
# --------------------------------------------------------------------------------------


def _glossary_sections() -> dict[str, str]:
    text = GLOSSARY.read_text(encoding="utf-8")
    parts = re.split(r"^### (.+)$", text, flags=re.MULTILINE)
    return {parts[i].strip().lower(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _status(section: str) -> str:
    match = re.search(r"\*\*Status\*\*\s*\|\s*([^|]+)\|", section)
    return match.group(1).strip().lower() if match else ""


@covers("FR-013")
@pytest.mark.corpus
def test_fr013_glossary_defines_terms() -> None:
    sections = _glossary_sections()
    assert "charter" in sections, "control: the glossary parses"
    missing = [term for term in NEW_TERMS if term.lower() not in sections]
    assert missing == [], missing
    assert all(_status(sections[t.lower()]) == "canonical" for t in NEW_TERMS)


def _glossary_entries(path: Path) -> dict[str, dict[str, object]]:
    """Glossary seed or pack entries keyed by lower-cased ``surface``."""
    data = load_yaml(path)
    terms = data.get("terms", []) if isinstance(data, dict) else []
    return {str(t["surface"]).strip().lower(): t for t in terms if isinstance(t, dict) and "surface" in t}


def _deprecated_with_replacement(entry: dict[str, object] | None) -> bool:
    """``status: deprecated`` and a definition that names one of the new terms."""
    if entry is None or str(entry.get("status", "")).strip().lower() != "deprecated":
        return False
    definition = str(entry.get("definition", "")).lower()
    return any(term.lower() in definition for term in NEW_TERMS)


@covers("FR-013")
@pytest.mark.corpus
def test_fr013_retired_terms_redirected() -> None:
    """Retire, do not redefine: FR-018 forbids the retired spellings on charter.md, so they live on only
    as ``deprecated`` entries in the FR-018-exempt seed and built-in glossary pack, each naming its successor."""
    sections = _glossary_sections()
    assert "charter" in sections, "control: the glossary parses"
    defined_here = [term for term in RETIRED_TERMS if term.lower() in sections]
    assert defined_here == [], f"retired terms still defined in {GLOSSARY.name}: {defined_here}"
    for surface in (GLOSSARY_SEED, GLOSSARY_PACK):
        entries = _glossary_entries(surface)
        assert str(entries[KNOWN_DEPRECATED_TERM].get("status")) == "deprecated", "control: the reader sees a deprecated entry"
        not_deprecated = [term for term in RETIRED_TERMS if not _deprecated_with_replacement(entries.get(term.lower()))]
        assert not_deprecated == [], f"{surface.relative_to(REPO_ROOT)}: not deprecated with a replacement: {not_deprecated}"
    guard = sections["charter"]
    assert "Pack Default Charter" not in guard and "[Doctrine Pack]" not in guard
    assert "active charter" in guard.lower(), "the 'active' guard names the active charter"
    assert "charter pack" in sections, "control: the new term resolves"


@covers("FR-013")
@pytest.mark.corpus
def test_fr013_no_living_citation_of_missing_adr() -> None:
    assert CUTOVER_ADR.is_file(), "control: the new citation target exists"
    offenders: list[str] = []
    for top in ("src", "docs", "packs"):
        for path in (REPO_ROOT / top).rglob("*"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if not path.is_file() or "__pycache__" in rel or not is_living_path(rel):
                continue
            if MISSING_ADR in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(rel)
    assert offenders == [], offenders


# --------------------------------------------------------------------------------------
# FR-014: reachability pins
# --------------------------------------------------------------------------------------


def _reachability_test() -> Path:
    found = sorted(p for p in (REPO_ROOT / "tests").rglob("test_reachability.py") if p.parent.name == "drg")
    assert len(found) == 1, found
    return found[0]


@covers("FR-014")
@pytest.mark.corpus
def test_fr014_reachability_pins_reasserted_or_recorded() -> None:
    path = _reachability_test()
    source = path.read_text(encoding="utf-8")
    assert "def test_" in source, "control: the real reachability module"
    for stale in ("default.yaml", "default_pack", "charter_pack_registry"):
        assert stale not in source, stale
    docstring = ast.get_docstring(ast.parse(source)) or ""
    assert "FR-014" in docstring, "the module docstring records the FR-014 re-assertion"
    if "Deleted pins (FR-014)" in docstring:
        section = docstring.split("Deleted pins (FR-014)", 1)[1]
        entries = [line for line in section.splitlines() if line.strip().startswith(("-", "*"))]
        assert entries and all(":" in line or "—" in line for line in entries), "each deleted pin carries a reason"
