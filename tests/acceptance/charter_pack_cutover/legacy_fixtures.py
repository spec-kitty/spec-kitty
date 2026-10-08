"""Deterministic builders for legacy (pre-cutover) project shapes (#3732, T002).

One builder per legacy shape; the golden generator (``generate_golden_before.py``)
and the acceptance tests share them. Every builder writes ``.kittify/config.yaml``
(or the pointed ``charter.yaml``), ``.kittify/metadata.yaml``, any pack
directories, then ``git init -b main`` and commits. No builder imports a
post-cutover module, and no builder reads a source file the cutover deletes:
anything taken from the base tree is frozen under ``tests/fixtures/charter_pack_cutover/static/``.

* :data:`BUILDERS` maps every fixture name to its builder.
* :func:`project_from_template` copies a pristine per-session template of a builder's
  output into a test's own directory (each builder is deterministic, so it runs once).
* :data:`NFR001_FIXTURES` is the subset golden-compared (spec NFR-001's list).
* :data:`EXPECTED_RELATION` maps each NFR-001 fixture to its spec NFR-001 class.
"""

from __future__ import annotations

import atexit
import json
import shutil
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from ._support import git, git_init_commit, sha256_hex

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "charter_pack_cutover"
SNAPSHOTS_PATH = FIXTURES_ROOT / "default_yaml_snapshots.yaml"
STATIC_ROOT = FIXTURES_ROOT / "static"

DEFAULT_VERSION = "4.0.0rc5"
PRE_RC35_VERSION = "3.2.0rc30"

ORG_PACK_NAME = "acme"
ORG_PACK_DIR = "org-packs/acme"
ORG2_PACK_NAME = "acme-two"
ORG2_PACK_DIR = "org-packs/acme-two"

#: Org pack 1 artifacts (declared id == stem).
ORG_DIRECTIVE_ID = "ACME-001-REVIEW-GATE"
ORG_DIRECTIVE_STEM = "acme-001-review-gate"
ORG_TACTIC_ID = "acme-pairing"
#: Org pack 2 artifact whose declared ``id:`` differs from its file stem (#4399).
ORG2_DIRECTIVE_ID = "ACME-002-RELEASE-TRAIN"
ORG2_DIRECTIVE_STEM = "release-train"
ORG2_PROCEDURE_ID = "acme-release-procedure"
ORG2_PROCEDURE_STEM = "release-procedure"

PROJECT_SKILL_NAMESPACE = "acme"
PROJECT_SKILL_ID = "triage"

MISSION_TYPES = ["software-dev"]

_YAML = YAML(typ="safe")
_YAML.default_flow_style = False


# --------------------------------------------------------------------------------------
# Small writers
# --------------------------------------------------------------------------------------


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_yaml(path: Path, data: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        _YAML.dump(dict(data), handle)
    return path


def stamp_metadata(project: Path, version: str = DEFAULT_VERSION) -> None:
    """Write ``.kittify/metadata.yaml`` at *version* with the CLI's schema version."""
    from kernel.clock import now_utc
    from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
    from specify_cli.upgrade.metadata import ProjectMetadata
    from specify_cli.upgrade.runner import MigrationRunner

    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    ProjectMetadata(
        version=version,
        initialized_at=now_utc(),
        python_version="3.11",
        platform="test",
        platform_version="test",
    ).save(kittify)
    MigrationRunner._stamp_schema_version(kittify, MAX_SUPPORTED_SCHEMA)


def write_org_directive(pack: Path, *, stem: str, directive_id: str) -> None:
    write_text(
        pack / "directives" / f"{stem}.directive.yaml",
        f'schema_version: "1.0"\nid: {directive_id}\ntitle: {stem}\nintent: Apply org policy.\nenforcement: required\n',
    )


def write_org_tactic(pack: Path, tactic_id: str) -> None:
    write_text(
        pack / "tactics" / f"{tactic_id}.tactic.yaml",
        f'schema_version: "1.0"\nid: {tactic_id}\nname: {tactic_id}\npurpose: Org fixture tactic.\nsteps:\n  - title: Act\n    description: Do the thing.\n',
    )


def write_org_procedure(pack: Path, *, stem: str, procedure_id: str) -> None:
    write_text(
        pack / "procedures" / f"{stem}.procedure.yaml",
        'schema_version: "1.0"\n'
        f"id: {procedure_id}\n"
        f"name: {procedure_id} fixture procedure\n"
        "purpose: Org fixture procedure.\n"
        "entry_condition: Always.\n"
        "exit_condition: Done.\n"
        "steps:\n  - title: Act\n    description: Do the thing.\n    actor: agent\n",
    )


def build_org_pack(project: Path) -> Path:
    """Org pack 1 (``org-packs/acme``): one directive and one tactic, id == stem."""
    pack = project / ORG_PACK_DIR
    write_org_directive(pack, stem=ORG_DIRECTIVE_STEM, directive_id=ORG_DIRECTIVE_ID)
    write_org_tactic(pack, ORG_TACTIC_ID)
    return pack


def build_second_org_pack(project: Path) -> Path:
    """Org pack 2 (``org-packs/acme-two``): artifacts whose declared id differs from the stem."""
    pack = project / ORG2_PACK_DIR
    write_org_directive(pack, stem=ORG2_DIRECTIVE_STEM, directive_id=ORG2_DIRECTIVE_ID)
    write_org_procedure(pack, stem=ORG2_PROCEDURE_STEM, procedure_id=ORG2_PROCEDURE_ID)
    return pack


def canonical_org_packs(*names_and_dirs: tuple[str, str]) -> dict[str, Any]:
    return {"charter_packs": {"org": {"packs": [{"name": n, "local_path": d} for n, d in names_and_dirs]}}}


def finish(project: Path, config: Mapping[str, Any], *, version: str = DEFAULT_VERSION) -> Path:
    """Write ``config.yaml`` and ``metadata.yaml``, then commit everything."""
    write_yaml(project / ".kittify" / "config.yaml", config)
    stamp_metadata(project, version)
    git_init_commit(project)
    return project


def copy_static(name: str, project: Path) -> None:
    """Copy the frozen tree ``static/<name>/`` into *project*."""
    source = STATIC_ROOT / name
    if not source.is_dir():
        raise FileNotFoundError(f"frozen fixture tree missing: {source} (run generate_golden_before at the base)")
    shutil.copytree(source, project, dirs_exist_ok=True)


# --------------------------------------------------------------------------------------
# Released default.yaml / minimal.yaml documents (from the frozen snapshot data)
# --------------------------------------------------------------------------------------


@cache
def snapshot_data() -> dict[str, Any]:
    data = YAML(typ="safe").load(SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _document_for(pack: str, version: str) -> dict[str, list[str]]:
    keys = snapshot_data()["snapshots"][pack]["keys"]
    doc: dict[str, list[str]] = {}
    for key, entries in keys.items():
        for entry in entries:
            if entry["form"] == "original" and version in entry["versions"]:
                doc[key] = list(entry["ids"])
    return doc


def released_documents(pack: str) -> list[dict[str, list[str]]]:
    """Distinct released documents of *pack* (``default`` -> D1..D5), in release order."""
    seen: list[dict[str, list[str]]] = []
    for version in snapshot_data()["snapshots"][pack]["released_versions"]:
        doc = _document_for(pack, version)
        if doc not in seen:
            seen.append(doc)
    return seen


#: ``m_3_2_6_retire_rtk_search_tooling``.
RTK_RETIREMENTS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (("activated_toolguides", "rtk-search-tooling", ()),)
#: ``m_4_0_0rc5_retire_single_owner_doctrine_ids`` RETIREMENTS, in table order.
RC5_RETIREMENTS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    ("activated_styleguides", "adversarial-squad-cadence", ()),
    ("activated_tactics", "bug-fixing-checklist", (("activated_procedures", "test-first-bug-fixing"),)),
    ("activated_tactics", "locality-of-change", (("activated_tactics", "avoid-gold-plating"),)),
    (
        "activated_tactics",
        "common-docs-curation",
        (("activated_tactics", "common-docs-scaffold"), ("activated_tactics", "common-docs-write"), ("activated_tactics", "common-docs-find")),
    ),
    ("activated_tactics", "boring-code-review", (("activated_styleguides", "boring-code-review"),)),
    ("activated_tactics", "behavior-driven-development", (("activated_tactics", "bdd-scenario-formulation"),)),
    ("activated_tactics", "iterative-deepening-review", ()),
    ("activated_procedures", "tracker-organisation-workflow", ()),
)


def apply_retirements(doc: Mapping[str, list[str]], table: Iterable[tuple[str, str, tuple[tuple[str, str], ...]]]) -> dict[str, list[str]]:
    """The shared retirement engine's per-key rule (``_retired_activation.py``), on a copy."""
    out = {key: list(ids) for key, ids in doc.items()}
    for key, stem, successors in table:
        if key not in out or stem not in out[key]:
            continue
        out[key] = [i for i in out[key] if i != stem]
        for successor_key, successor in successors:
            if successor_key in out and successor not in out[successor_key]:
                out[successor_key].append(successor)
    return out


_FORMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("original", ()),
    ("rtk", (RTK_RETIREMENTS,)),
    ("rc5", (RC5_RETIREMENTS,)),
    ("rtk+rc5", (RTK_RETIREMENTS, RC5_RETIREMENTS)),
)


def _normalised(doc: Mapping[str, list[str]]) -> dict[str, list[str]]:
    return {key: sorted(set(ids)) for key, ids in sorted(doc.items())}


@cache
def stale_documents() -> dict[str, dict[str, list[str]]]:
    """``stale_<doc>_<form>`` -> document; D1..D5 x original/rtk/rc5/rtk+rc5, deduplicated."""
    result: dict[str, dict[str, list[str]]] = {}
    seen: list[dict[str, list[str]]] = []
    for index, doc in enumerate(released_documents("default"), start=1):
        for form, tables in _FORMS:
            current = dict(doc)
            for table in tables:
                current = apply_retirements(current, table)
            normalised = _normalised(current)
            if normalised not in seen:
                seen.append(normalised)
                result[f"stale_d{index}_{form.replace('+', '_')}"] = normalised
    return result


def snapshot_lists(pack: str, key: str) -> list[list[str]]:
    """Every list (original and post-rewrite) the snapshot file records for *pack*/*key*."""
    return [sorted(entry["ids"]) for entry in snapshot_data()["snapshots"][pack]["keys"].get(key, [])]


def latest_default() -> dict[str, list[str]]:
    """D5 (the 4.0.0rc5 ``default.yaml``)."""
    return _normalised(released_documents("default")[-1])


def latest_minimal() -> dict[str, list[str]]:
    """M2 (the 4.0.0rc5 ``minimal.yaml``)."""
    return _normalised(released_documents("minimal")[-1])


# --------------------------------------------------------------------------------------
# NFR-001 builders
# --------------------------------------------------------------------------------------


def build_legacy_keys_only(project: Path) -> Path:
    # INV: Org packs list; Governance selection (config.yaml)
    build_org_pack(project)
    config = {
        "doctrine": {"org": {"packs": [{"name": ORG_PACK_NAME, "local_path": ORG_PACK_DIR}]}},
        "governance": {"doctrine": {"selected_directives": ["003-decision-documentation-requirement"]}},
        "mission_type_activations": MISSION_TYPES,
    }
    return finish(project, config)


def build_single_pack_legacy_form(project: Path) -> Path:
    # INV: Single-pack legacy form
    build_org_pack(project)
    config = {
        "doctrine": {"org": {"local_path": "org-packs", "subdir": "acme", "source_type": "git"}},
        "mission_type_activations": MISSION_TYPES,
    }
    return finish(project, config)


def build_organisation_packs(project: Path) -> Path:
    # INV: Flat org list
    build_org_pack(project)
    config = {
        "organisation_packs": [{"name": ORG_PACK_NAME, "path": ORG_PACK_DIR, "source": "local_path"}],
        "mission_type_activations": MISSION_TYPES,
    }
    return finish(project, config)


def build_legacy_directory_only(project: Path) -> Path:
    # INV: Project layer (directive/tactic/styleguide + graph.yaml + overlays), canonical keys
    copy_static("synthesized", project)
    for leftover in ("charter/synthesis-manifest.yaml", "charter/provenance"):
        target = project / ".kittify" / leftover
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    copy_static("overlays", project)
    return finish(project, {"charter_packs": {"org": {"packs": []}}, "mission_type_activations": MISSION_TYPES})


def _stale_builder(name: str) -> Callable[[Path], Path]:
    def build(project: Path) -> Path:
        # INV: Stale activation lists; Stale kind gate
        config: dict[str, Any] = dict(stale_documents()[name])
        return finish(project, config)

    build.__name__ = f"build_{name}"
    return build


def build_stale_in_pointed_charter_yaml(project: Path) -> Path:
    # INV: Stale activation lists (in the pointed charter.yaml)
    charter = {"schema_version": "2.0.0", "governance": {}, "directives": [], **latest_default()}
    write_yaml(project / ".kittify" / "charter" / "charter.yaml", charter)
    return finish(project, {"charter": ".kittify/charter/charter.yaml"})


def build_near_miss_stale(project: Path) -> Path:
    # INV: Customised lists (EC: Stale list plus one customisation, near-miss form)
    doc = latest_default()
    doc["activated_tactics"] = doc["activated_tactics"][1:]
    return finish(project, doc)


def build_customised_lists(project: Path) -> Path:
    # INV: Customised lists (stale plus one id; one entry in DIRECTIVE_NNN spelling)
    doc = latest_default()
    directives = [d for d in doc["activated_directives"] if not d.startswith("003-")]
    doc["activated_directives"] = sorted([*directives, "DIRECTIVE_003", "052-prefer-durable-fixes"])
    return finish(project, doc)


def build_minimal_equal(project: Path) -> Path:
    # INV: Released `minimal` kind gate; Customised lists, `minimal`-equal lists
    return finish(project, latest_minimal())


def build_governance_doctrine_in_charter_yaml(project: Path) -> Path:
    # INV: Governance selection (charter.yaml)
    charter = {
        "schema_version": "2.0.0",
        "governance": {"doctrine": {"selected_directives": ["003-decision-documentation-requirement"]}},
        "directives": [],
        "mission_type_activations": MISSION_TYPES,
    }
    write_yaml(project / ".kittify" / "charter" / "charter.yaml", charter)
    return finish(project, {"charter": ".kittify/charter/charter.yaml"})


def build_two_org_packs(project: Path) -> Path:
    # INV: Org packs list (canonical, two packs; pack 2 has id != stem, #4399)
    build_org_pack(project)
    build_second_org_pack(project)
    config = {**canonical_org_packs((ORG_PACK_NAME, ORG_PACK_DIR), (ORG2_PACK_NAME, ORG2_PACK_DIR)), "mission_type_activations": MISSION_TYPES}
    return finish(project, config)


def build_mixed_stale_and_custom(project: Path) -> Path:
    # INV: Stale activation lists (tactics) + Customised lists (directives)
    doc = latest_default()
    config = {
        "activated_tactics": doc["activated_tactics"],
        "activated_directives": ["001-architectural-integrity-standard", "024-locality-of-change"],
        "mission_type_activations": MISSION_TYPES,
    }
    return finish(project, config)


def build_pre_rc35(project: Path) -> Path:
    # NFR-001 pre-rc35: no activation keys, no mission_type_activations
    return finish(project, {"vcs": {"type": "git"}}, version=PRE_RC35_VERSION)


def build_synthesized_with_provenance(project: Path) -> Path:
    # INV: Project layer; Synthesis manifest; Provenance sidecars
    copy_static("synthesized", project)
    return finish(project, {"mission_type_activations": MISSION_TYPES})


def build_project_pack_skills(project: Path) -> Path:
    # INV: Project layer (skills); Pack-skill manifest (source_ref under the old root)
    copy_static("project_pack_skills", project)
    config = {
        "agents": {"available": ["claude"]},
        "charter_packs": {"project": {"skill_namespace": PROJECT_SKILL_NAMESPACE}},
        "mission_type_activations": MISSION_TYPES,
        "activated_skills": [PROJECT_SKILL_ID],
    }
    return finish(project, config)


def build_normalizer_empty_lists(project: Path) -> Path:
    # INV: Normalizer empty lists (DM-01M497EW60HNWWJQCXDFA99R0H)
    config = {"activated_glossary_packs": [], "activated_paradigms": [], "mission_type_activations": MISSION_TYPES}
    return finish(project, config)


# --------------------------------------------------------------------------------------
# FR-012-only builders (not golden-compared)
# --------------------------------------------------------------------------------------


def build_doctrine_pack_id_activations(project: Path) -> Path:
    # INV: Activation entry key (OD-1)
    charter = {
        "schema_version": "2.0.0",
        "governance": {},
        "directives": [],
        "mission_type_activations": MISSION_TYPES,
        "activations": [
            {
                "activation_context": {"mission_type": "software-dev", "action": "implement"},
                "doctrine_pack_id": ORG_PACK_NAME,
                "artifact_id": ORG_TACTIC_ID,
                "artifact_kind": "tactics",
            }
        ],
    }
    build_org_pack(project)
    write_yaml(project / ".kittify" / "charter" / "charter.yaml", charter)
    return finish(project, {**canonical_org_packs((ORG_PACK_NAME, ORG_PACK_DIR)), "charter": ".kittify/charter/charter.yaml"})


def build_tracker_doctrine_key(project: Path) -> Path:
    # INV: Tracker ownership (CR-03)
    config = {
        "tracker": {"provider": "github", "doctrine": {"mode": "external_authoritative", "field_owners": {}}},
        "mission_type_activations": MISSION_TYPES,
    }
    return finish(project, config)


def build_answers_doctrine_key(project: Path) -> Path:
    # INV: Interview answers
    write_yaml(
        project / ".kittify" / "charter" / "interview" / "answers.yaml",
        {"schema_version": "1", "mission": "software-dev", "doctrine": {"selected_directives": ["DIRECTIVE_003"]}, "answers": {}},
    )
    return finish(project, {"mission_type_activations": MISSION_TYPES})


def build_standalone_governance_yaml(project: Path) -> Path:
    # INV: Governance selection (standalone legacy governance.yaml)
    write_yaml(
        project / ".kittify" / "charter" / "governance.yaml",
        {"doctrine": {"selected_directives": ["003-decision-documentation-requirement"]}},
    )
    return finish(project, {"mission_type_activations": MISSION_TYPES})


COLLISION_PATH = "directive/001-mission-type-scope-directive.directive.yaml"


def build_both_roots_collision(project: Path) -> Path:
    # EC: Both project roots present (same path, different content)
    copy_static("synthesized", project)
    write_text(project / ".kittify" / "charter-packs" / COLLISION_PATH, "id: PROJECT_001\ntitle: diverged copy\n")
    return finish(project, {"mission_type_activations": MISSION_TYPES})


def build_both_roots_disjoint(project: Path) -> Path:
    # EC: Both project roots present (no shared path)
    copy_static("synthesized", project)
    write_text(project / ".kittify" / "charter-packs" / "overlays" / "extra.yaml", "overlay: extra\n")
    return finish(project, {"mission_type_activations": MISSION_TYPES})


USER_PACK_DIR = "packs/doctrine-foo"


def build_user_path_value_with_doctrine(project: Path) -> Path:
    # EC: User-chosen path values containing "doctrine"
    write_org_tactic(project / USER_PACK_DIR, "foo-tactic")
    return finish(project, {**canonical_org_packs(("foo", USER_PACK_DIR)), "mission_type_activations": MISSION_TYPES})


#: (installed path, kind) for the installed-removed-skills fixture.
MANIFESTED_SKILL = ".claude/skills/spk-doctrine-charter/SKILL.md"
UNMANIFESTED_EQUAL_SKILL = ".agents/skills/spk-doctrine-glossary/SKILL.md"
EDITED_SKILL = ".claude/skills/spk-doctrine-show-me/SKILL.md"


@dataclass(frozen=True)
class _InstalledSkill:
    installed_path: str
    skill_name: str
    agent_key: str
    manifested: bool
    edited: bool


_INSTALLED_SKILLS = (
    _InstalledSkill(MANIFESTED_SKILL, "spk-doctrine-charter", "claude", manifested=True, edited=False),
    _InstalledSkill(UNMANIFESTED_EQUAL_SKILL, "spk-doctrine-glossary", "codex", manifested=False, edited=False),
    _InstalledSkill(EDITED_SKILL, "spk-doctrine-show-me", "claude", manifested=True, edited=True),
)


def build_installed_removed_skills(project: Path) -> Path:
    # INV: Installed skills (manifested, unmanifested hash-equal, edited copy)
    entries: list[dict[str, str]] = []
    for skill in _INSTALLED_SKILLS:
        shipped = (STATIC_ROOT / "removed_skills" / skill.skill_name / "SKILL.md").read_bytes()
        body = shipped + b"\n<!-- operator edit -->\n" if skill.edited else shipped
        target = project / skill.installed_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        if skill.manifested:
            entries.append(
                {
                    "skill_name": skill.skill_name,
                    "source_file": "SKILL.md",
                    "installed_path": skill.installed_path,
                    "installation_class": "native-root-required",
                    "agent_key": skill.agent_key,
                    "content_hash": f"sha256:{sha256_hex(shipped)}",
                    "installed_at": "2026-10-01T00:00:00+00:00",
                    "delivery_mode": "copy",
                }
            )
    manifest = {
        "version": 1,
        "created_at": "2026-10-01T00:00:00+00:00",
        "updated_at": "2026-10-01T00:00:00+00:00",
        "spec_kitty_version": DEFAULT_VERSION,
        "entries": entries,
    }
    write_text(project / ".kittify" / "skills-manifest.json", json.dumps(manifest, indent=2) + "\n")
    return finish(project, {"agents": {"available": ["claude", "codex"]}, "mission_type_activations": MISSION_TYPES})


def build_lane_in_approved(project: Path) -> Path:
    # US2-7 / EC: Lane worktrees created before the upgrade
    repo: Path = build_lane_project(project).repo
    return repo


#: The legacy project layer the lane fixture commits on the target before any lane is cut.
LANE_LEGACY_LAYER = ".kittify/doctrine"


def build_lane_project(project: Path) -> Any:
    """A ``lanes`` mission with one live lane worktree whose WP is ``approved`` (stamped).

    Reuses the real-git lanes builder of the target-owned bookkeeping mission
    (``tests/integration/target_owned_fixtures.py``), with a legacy project layer
    (the frozen ``static/synthesized`` tree: ``.kittify/doctrine/`` plus the synthesis
    manifest and provenance sidecars) committed on the target right after the repository
    is initialised, so every lane cut afterwards carries it too.
    """
    from tests.integration import target_owned_fixtures as owned

    real_init_repo = owned._init_repo

    def init_repo_with_legacy_layer(repo: Path, target_branch: str) -> None:
        real_init_repo(repo, target_branch)
        copy_static("synthesized", repo)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--no-verify", "-m", "fixture: legacy project layer on the target")

    project.mkdir(parents=True, exist_ok=True)
    owned._init_repo = init_repo_with_legacy_layer
    try:
        return owned.build_older_version_lanes_project(project, topology="lanes", lanes=1, target_branch="work", approvals_stamped=True)
    finally:
        owned._init_repo = real_init_repo


# --------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------

_NFR001_STATIC: dict[str, Callable[[Path], Path]] = {
    "legacy_keys_only": build_legacy_keys_only,
    "single_pack_legacy_form": build_single_pack_legacy_form,
    "organisation_packs": build_organisation_packs,
    "legacy_directory_only": build_legacy_directory_only,
}
_NFR001_TAIL: dict[str, Callable[[Path], Path]] = {
    "stale_in_pointed_charter_yaml": build_stale_in_pointed_charter_yaml,
    "near_miss_stale": build_near_miss_stale,
    "customised_lists": build_customised_lists,
    "minimal_equal": build_minimal_equal,
    "governance_doctrine_in_charter_yaml": build_governance_doctrine_in_charter_yaml,
    "two_org_packs": build_two_org_packs,
    "mixed_stale_and_custom": build_mixed_stale_and_custom,
    "pre_rc35": build_pre_rc35,
    "synthesized_with_provenance": build_synthesized_with_provenance,
    "project_pack_skills": build_project_pack_skills,
    "normalizer_empty_lists": build_normalizer_empty_lists,
}
_FR012_ONLY: dict[str, Callable[[Path], Path]] = {
    "doctrine_pack_id_activations": build_doctrine_pack_id_activations,
    "tracker_doctrine_key": build_tracker_doctrine_key,
    "answers_doctrine_key": build_answers_doctrine_key,
    "standalone_governance_yaml": build_standalone_governance_yaml,
    "both_roots_collision": build_both_roots_collision,
    "both_roots_disjoint": build_both_roots_disjoint,
    "user_path_value_with_doctrine": build_user_path_value_with_doctrine,
    "installed_removed_skills": build_installed_removed_skills,
    "lane_in_approved": build_lane_in_approved,
}

STALE_FIXTURES: tuple[str, ...] = tuple(stale_documents())

BUILDERS: dict[str, Callable[[Path], Path]] = {
    **_NFR001_STATIC,
    **{name: _stale_builder(name) for name in STALE_FIXTURES},
    **_NFR001_TAIL,
    **_FR012_ONLY,
}

NFR001_FIXTURES: tuple[str, ...] = (*_NFR001_STATIC, *STALE_FIXTURES, *_NFR001_TAIL)
FR012_ONLY_FIXTURES: tuple[str, ...] = tuple(_FR012_ONLY)

#: Kinds the released ``[directives, tactics]`` gate excluded (every activation kind but those two).
#: Spec NFR-001 expected relation per fixture class. Comments cite the FR-012 inventory row.
EXPECTED_RELATION: dict[str, str] = {
    "legacy_keys_only": "equal",  # Org packs list; Governance selection
    "single_pack_legacy_form": "equal",  # Single-pack legacy form
    "organisation_packs": "equal",  # Flat org list
    "legacy_directory_only": "equal",  # Project layer
    **dict.fromkeys(STALE_FIXTURES, "stale"),  # Stale activation lists; Stale kind gate
    "stale_in_pointed_charter_yaml": "stale",  # Stale activation lists (pointed charter.yaml)
    "near_miss_stale": "stale",  # Stale activation lists for every key but tactics (near miss kept)
    "customised_lists": "stale",  # directives kept for review; every other key is a snapshot
    "minimal_equal": "minimal_equal",  # Released `minimal` kind gate; `minimal`-equal lists
    "governance_doctrine_in_charter_yaml": "equal",  # Governance selection (charter.yaml)
    "two_org_packs": "equal",  # Org packs list (canonical)
    "mixed_stale_and_custom": "stale",  # Stale tactics reset, custom directives kept
    "pre_rc35": "pre_rc35",  # rc35 recorded no-op; default preset mission types
    "synthesized_with_provenance": "equal",  # Synthesis manifest; Provenance sidecars
    "project_pack_skills": "equal",  # Pack-skill manifest
    "normalizer_empty_lists": "normalizer_empty_lists",  # Normalizer empty lists
}

#: For ``stale`` fixtures: the activation keys that equal a snapshot (reset to absent by the
#: migration); every other key is kept. ``None`` means "every snapshot key the fixture carries".
STALE_KEYS_KEPT: dict[str, tuple[str, ...]] = {
    "near_miss_stale": ("activated_tactics",),
    "customised_lists": ("activated_directives",),
    "mixed_stale_and_custom": ("activated_directives",),
}

#: For ``normalizer_empty_lists``: the per-artifact ``[]`` keys the migration resets.
NORMALIZER_RESET_KEYS: tuple[str, ...] = ("activated_glossary_packs", "activated_paradigms")


# --------------------------------------------------------------------------------------
# SC-004 doctrine-command fixture (old leaves and their charter homes run on it)
# --------------------------------------------------------------------------------------

DOCTRINE_PACK_DIR = "orgpack"
DOCTRINE_REMOTE_DIR = "remote-pack"
DOCTRINE_FETCHED_DIR = "orgpack-fetched"
AUTHORING_TACTIC = "authoring/fixture-tactic.tactic.yaml"

_ORG_CHARTER = (
    'schema_version: "1"\norg_name: acme\nrequired_directives: []\nrequired_tactics: []\nrequired_paradigms: []\n'
    "required_styleguides: []\nrequired_toolguides: []\nrequired_procedures: []\nrequired_agent_profiles: []\n"
    "required_mission_step_contracts: []\ngovernance_policies: []\nactivations: []\n"
)
_FRAGMENT = "pack_name: acme\nsource_kind: local_path\nsource_ref: .\nlayer_index: 1\nprovenance_marker: org\nnodes: []\nedges: []\n"


def write_doctrine_pack(pack: Path) -> Path:
    """A minimal valid org pack (``org-charter.yaml`` + DRG fragment), as ``org init`` scaffolds at base."""
    write_text(pack / "org-charter.yaml", _ORG_CHARTER)
    write_text(pack / "drg" / "fragment.yaml", _FRAGMENT)
    return pack


def build_doctrine_command_fixture(project: Path) -> Path:
    """Project + local pack dir + a local git remote for ``fetch`` (SC-004)."""
    write_doctrine_pack(project / DOCTRINE_PACK_DIR)
    remote = write_doctrine_pack(project / DOCTRINE_REMOTE_DIR)
    write_org_tactic(remote, ORG_TACTIC_ID)
    git_init_commit(remote, "fixture: remote org pack")
    write_org_tactic(project / "authoring-src", "fixture-tactic")
    authored = project / "authoring-src" / "tactics" / "fixture-tactic.tactic.yaml"
    write_text(project / AUTHORING_TACTIC, authored.read_text(encoding="utf-8"))
    shutil.rmtree(project / "authoring-src")
    config = {
        "charter_packs": {
            "org": {
                "packs": [
                    {
                        "name": ORG_PACK_NAME,
                        "local_path": DOCTRINE_FETCHED_DIR,
                        "source_type": "git",
                        "url": (project / DOCTRINE_REMOTE_DIR).as_uri(),
                        "ref": "main",
                    }
                ]
            }
        },
        "mission_type_activations": MISSION_TYPES,
    }
    (project / ".gitignore").write_text(f"{DOCTRINE_REMOTE_DIR}/\n", encoding="utf-8")
    return finish(project, config)


# --------------------------------------------------------------------------------------
# Per-session templates (#3732 cycle 2: build once, copy per test)
# --------------------------------------------------------------------------------------

#: Builders whose output records its own absolute location (a ``file://`` remote URL, git
#: worktree links) and therefore cannot be copied elsewhere; they always build in place.
LOCATION_DEPENDENT_BUILDERS = frozenset({"lane_in_approved"})

_TEMPLATES: dict[str, Path] = {}
_TEMPLATE_ROOT: list[Path] = []


def _template_root() -> Path:
    if not _TEMPLATE_ROOT:
        root = Path(tempfile.mkdtemp(prefix="charter-pack-cutover-templates-"))
        atexit.register(shutil.rmtree, root, True)
        _TEMPLATE_ROOT.append(root)
    return _TEMPLATE_ROOT[0]


def project_from_template(name: str, dest: Path, builder: Callable[[Path], Path] | None = None) -> Path:
    """A fresh copy of fixture *name* at *dest* (built once per session, then copied).

    *builder* defaults to ``BUILDERS[name]``. The template is never handed to a test,
    so every test still owns an isolated project (its own files and its own ``.git``).
    """
    build = builder if builder is not None else BUILDERS[name]
    if name in LOCATION_DEPENDENT_BUILDERS:
        return build(dest)
    template = _TEMPLATES.get(name)
    if template is None:
        template = build(_template_root() / name)
        _TEMPLATES[name] = template
    shutil.copytree(template, dest, symlinks=True)
    return dest


@dataclass(frozen=True)
class UpgradedTemplate:
    """One ``spec-kitty upgrade --yes --json --no-worktrees`` run on a pristine template."""

    pristine: Path
    upgraded: Path
    exit_code: int
    output: str
    payload: Any


_UPGRADED: dict[str, UpgradedTemplate] = {}


def upgraded_template(name: str) -> UpgradedTemplate:
    """The first upgrade of fixture *name*, run once per session on a template copy.

    The upgrade is deterministic and location-independent (a copied upgraded project and
    the original change identically on a further upgrade), so tests that only need the
    first upgrade's outcome share it and work on their own copy of the result.
    """
    cached = _UPGRADED.get(name)
    if cached is None:
        from ._support import run_cli

        root = _template_root() / "upgraded"
        pristine = project_from_template(name, root / "pristine" / name)
        upgraded = project_from_template(name, root / "upgraded" / name)
        result = run_cli(["upgrade", "--yes", "--json", "--no-worktrees"], upgraded)
        try:
            from ._support import read_json_output

            payload: Any = read_json_output(result)
        except AssertionError:
            payload = None
        cached = UpgradedTemplate(pristine, upgraded, result.exit_code, result.output, payload)
        _UPGRADED[name] = cached
    return cached


def upgraded_copy(name: str, dest: Path) -> tuple[Path, UpgradedTemplate]:
    """A private copy of fixture *name* after its first upgrade, plus that upgrade's outcome."""
    template = upgraded_template(name)
    shutil.copytree(template.upgraded, dest, symlinks=True)
    return dest, template
