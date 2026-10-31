"""Promotion seeds from the effective set: FR-015, US5, C-007 (#3732, T007, #4400).

Fixture: two org packs, pack 2 holding artifacts whose declared ``id:`` differs
from the file stem (#4399), every activation key absent. Each caller is driven
through its CLI entry point; after the promotion every artifact effective before
must still be effective (one parametrised row per caller, so reverting one caller
turns exactly one row red).
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import ActiveCharterManager

from ._effective_set import builtin_inventory, effective_set, expand
from ._requirements import REPO_ROOT
from ._support import active_charter, covers, describe, load_yaml, output_of, run_cli
from .legacy_fixtures import (
    ORG2_DIRECTIVE_ID,
    ORG2_DIRECTIVE_STEM,
    ORG2_PACK_DIR,
    ORG_DIRECTIVE_ID,
    ORG_PACK_DIR,
    ORG_TACTIC_ID,
    finish,
    project_from_template,
    write_yaml,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

PROMOTED_DIRECTIVE = "001-architectural-integrity-standard"
PRESENT_DIRECTIVE = "024-locality-of-change"
EFFECTIVE_SET_CALLERS = (
    "src/specify_cli/cli/commands/charter/interview.py",
    "src/charter/activation/org_charter.py",
    "src/specify_cli/upgrade/migrations/m_unify_charter_activation.py",
    "src/specify_cli/cli/commands/charter/_resynthesis_preflight.py",
)


def _fixture(tmp_path: Path) -> Path:
    project = project_from_template("two_org_packs", tmp_path / "two-org-packs")
    packs = load_yaml(project / ".kittify" / "config.yaml")["charter_packs"]["org"]["packs"]
    assert len(packs) == 2, "precondition: two declared org packs"
    assert (project / ORG2_PACK_DIR / "directives" / f"{ORG2_DIRECTIVE_STEM}.directive.yaml").is_file()
    assert ORG2_DIRECTIVE_ID.lower() != ORG2_DIRECTIVE_STEM, "precondition: an id that differs from its stem"
    assert not [k for k in active_charter(project) if k.startswith("activated_")], "precondition: every key absent"
    return project


def _interview(project: Path) -> Result:
    return run_cli(
        ["charter", "interview", "--defaults", "--selected-directives", PROMOTED_DIRECTIVE, "--selected-paradigms", "atomic-design"],
        project,
    )


def _prepare_org_charter_union(project: Path) -> None:
    """Org pack 1 requires a directive and a tactic; the union caller is the interview that reads it."""
    write_yaml(
        project / ORG_PACK_DIR / "org-charter.yaml",
        {"schema_version": "1", "org_name": "acme", "required_directives": [ORG_DIRECTIVE_ID], "required_tactics": [ORG_TACTIC_ID]},
    )
    finish(project, load_yaml(project / ".kittify" / "config.yaml"))


def _org_charter_union(project: Path) -> Result:
    # ``apply_org_charter_to_interview`` -> ``_promote_org_required_to_config`` runs only from
    # ``charter interview``. No ``--selected-*`` here: the union, not the operator, promotes.
    return run_cli(["charter", "interview", "--defaults"], project)


def _upgrade_unify(project: Path) -> Result:
    write_yaml(
        project / ".kittify" / "charter" / "interview" / "answers.yaml",
        {
            "schema_version": "1",
            "mission": "software-dev",
            "profile": "minimal",
            "answers": {},
            "selected_directives": [PROMOTED_DIRECTIVE],
            "selected_paradigms": [],
        },
    )
    finish(project, load_yaml(project / ".kittify" / "config.yaml"), version="3.2.5")
    return run_cli(["upgrade", "--yes", "--no-worktrees"], project)


#: Callers that must leave an absent ``activated_directives`` key absent: every writer that
#: promotes a *selection* (#6629 for the upgrade, #6685 for the interview) never writes an
#: absent key, because every available artifact of the kind is already in force while it is
#: absent. Only the callers that must materialise to keep an activation alive -- the org
#: required union on a listed kind, and a narrowing activation -- still write one.
KEY_STAYS_ABSENT = frozenset({"upgrade_unify", "interview", "resynthesize"})


def _prepare_resynthesize(project: Path) -> None:
    """Interview answers present, every activation key absent again.

    With the key absent the resynthesis preflight must seed its proposed selection; the
    effective-set rule (WP06) seeds it from the effective set, the base seeds it from the
    narrow ``default.yaml`` list.
    """
    original = load_yaml(project / ".kittify" / "config.yaml")
    seeded = run_cli(["charter", "interview", "--defaults"], project)
    assert seeded.exit_code == 0, describe(seeded)
    finish(project, original)
    assert not [k for k in active_charter(project) if k.startswith("activated_")], "precondition: the keys are absent again"


def _resynthesize(project: Path) -> Result:
    return run_cli(["charter", "activate", "directive", PROMOTED_DIRECTIVE, "--resynthesize"], project)


def _no_preparation(project: Path) -> None:
    del project


PREPARE: dict[str, Callable[[Path], None]] = {
    "interview": _no_preparation,
    "org_charter_union": _prepare_org_charter_union,
    "upgrade_unify": _no_preparation,
    "resynthesize": _prepare_resynthesize,
}

CALLERS: dict[str, Callable[[Path], Result]] = {
    "interview": _interview,
    "org_charter_union": _org_charter_union,
    "upgrade_unify": _upgrade_unify,
    "resynthesize": _resynthesize,
}

#: Where the resynthesis preflight hands its proposed selection to the resolver.
PREFLIGHT_MODULE = "specify_cli.cli.commands.charter._resynthesis_preflight"
PREFLIGHT_RESOLVER = "resolve_config_activated_roots"


def _spy_on_preflight(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Record the ``pack_context`` the resynthesis preflight proposes (it writes nothing itself)."""
    module = importlib.import_module(PREFLIGHT_MODULE)
    real = getattr(module, PREFLIGHT_RESOLVER)
    proposals: list[Any] = []

    def spy(*args: Any, **kwargs: Any) -> Any:
        proposals.append(kwargs.get("pack_context"))
        return real(*args, **kwargs)

    monkeypatch.setattr(module, PREFLIGHT_RESOLVER, spy)
    return proposals


def _assert_preflight_seeded_from_effective_set(proposals: list[Any], project: Path) -> None:
    """The preflight's proposed directive selection covers everything in force.

    #6685: the activation writes no list for an in-force artifact, so the reference is the
    in-force set itself (the resolver's available directives) rather than a written key; a
    written key, where one exists, is compared as before. Both sides are config ids.
    """
    assert proposals and proposals[-1] is not None, "control: the resynthesis preflight ran"
    proposed = set(proposals[-1].activated_directives or ())
    assert PROMOTED_DIRECTIVE in proposed, "control: the preflight proposes the requested directive"
    written_value = active_charter(project).get("activated_directives")
    reference = (
        {str(i) for i in written_value}
        if isinstance(written_value, list)
        else set(ActiveCharterManager().list_available(ProjectContext.from_repo(project), "directive"))
    )
    narrowed = sorted(reference - proposed)
    assert not narrowed, f"the resynthesis preflight seeded a narrower set than what was in force: {narrowed}"


#: The synthesis step that follows a resynthesizing activation needs the agent-authored
#: artifacts under ``.kittify/charter/generated/`` (one per interview target, the
#: ``how-we-apply-*`` tactics included), which this fixture deliberately does not provide.
#: Before #6685 the activation wrote a list here and the command therefore exited 1 in that
#: step. With no write there is nothing to resynthesize, so the command completes.
SYNTHESIS_NEEDS_GENERATED_ARTIFACTS = "GeneratedArtifactMissingError"


def _assert_caller_ran(caller: str, result: Result) -> None:
    text = output_of(result)
    if caller != "resynthesize":
        assert result.exit_code == 0, describe(result)
        return
    # #6685: an activation that changes nothing writes nothing, so no resynthesis is triggered
    # and the missing generated artifacts are never demanded.
    assert result.exit_code == 0, describe(result)
    assert "Activated" in text, describe(result)
    assert SYNTHESIS_NEEDS_GENERATED_ARTIFACTS not in text, describe(result)


@covers("FR-015", "US5-1")
@pytest.mark.parametrize("caller", list(CALLERS))
def test_fr015_promotion_preserves_effective_set(caller: str, tmp_path: Path, charter_cwd_isolation: Callable[..., Path], monkeypatch: pytest.MonkeyPatch) -> None:
    project = _fixture(tmp_path)
    charter_cwd_isolation(project)
    PREPARE[caller](project)
    inventory = builtin_inventory()
    before = expand(effective_set(project, inventory), inventory)
    assert ORG2_DIRECTIVE_ID in before["directives"] and ORG_DIRECTIVE_ID in before["directives"]
    proposals = _spy_on_preflight(monkeypatch) if caller == "resynthesize" else []
    result = CALLERS[caller](project)
    _assert_caller_ran(caller, result)
    if caller in KEY_STAYS_ABSENT:
        assert "activated_directives" not in active_charter(project), f"{caller} wrote an absent key (#6629)"
    else:
        assert "activated_directives" in active_charter(project), "control: the caller promoted the directive key"
    if caller == "resynthesize":
        _assert_preflight_seeded_from_effective_set(proposals, project)
    after = expand(effective_set(project, inventory), inventory)
    lost = {kind: sorted(before[kind] - after[kind]) for kind in before if before[kind] - after[kind]}
    assert not lost, f"{caller} narrowed the effective set: {lost}"


@covers("FR-015", "US5-1")
def test_fr015_upgrade_promotion_appends_to_present_key(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """With the key present, the upgrade promotion appends the interview selection it lacks (#6629)."""
    project = _fixture(tmp_path)
    charter_cwd_isolation(project)
    config = load_yaml(project / ".kittify" / "config.yaml")
    config["activated_directives"] = [PRESENT_DIRECTIVE]
    finish(project, config)
    result = _upgrade_unify(project)
    assert result.exit_code == 0, describe(result)
    written = active_charter(project).get("activated_directives")
    assert isinstance(written, list), written
    assert {PRESENT_DIRECTIVE, PROMOTED_DIRECTIVE} <= {str(i) for i in written}, written


@covers("FR-015", "US5-2")
def test_fr015_interview_never_writes_a_bare_list_whatever_the_effective_set(tmp_path: Path) -> None:
    """An absent key stays absent whether or not the effective set resolves (#6685, keeping #4400's guarantee).

    Before #6685 the interview seeded the absent key from the effective set and had to fall
    back to leaving it absent when that set could not be resolved. Not writing at all satisfies
    the #4400 guarantee (never a bare restrictive list) more strongly: an absent key is the
    unrestricted state, so nothing in force is lost either way.
    """
    healthy = _fixture(tmp_path / "healthy")
    healthy_result = _interview(healthy)
    assert healthy_result.exit_code == 0, describe(healthy_result)
    assert "activated_directives" not in active_charter(healthy), "a resolving set must not seed the key either (#6685)"
    assert "activated_directives" in output_of(healthy_result), "the run names the key it left absent"
    broken = _fixture(tmp_path / "broken")
    config = load_yaml(broken / ".kittify" / "config.yaml")
    config["charter_packs"]["org"]["packs"][1]["local_path"] = "org-packs/does-not-exist"
    finish(broken, config)
    result = _interview(broken)
    assert result.exit_code == 0, describe(result)
    assert "activated_directives" not in active_charter(broken)
    assert "activated_directives" in output_of(result), describe(result)


@covers("FR-015", "C-007")
def test_fr015_effective_set_seam_is_public() -> None:
    seam = importlib.import_module("charter.activation.effective_set")
    public = [name for name, value in vars(seam).items() if callable(value) and not name.startswith("_") and getattr(value, "__module__", "") == seam.__name__]
    assert len(public) == 1, public
    for rel in EFFECTIVE_SET_CALLERS:
        path = REPO_ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert "charter.activation.effective_set" in imports, rel


@covers("C-007")
def test_c007_interview_does_not_import_a_migration_module() -> None:
    tree = ast.parse((REPO_ROOT / "src/specify_cli/cli/commands/charter/interview.py").read_text(encoding="utf-8"))
    modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert modules, "control: the AST walk sees the imports"
    assert not [m for m in modules if "upgrade.migrations" in m], modules


@covers("FR-005")
def test_fr005_merge_defaults_removed() -> None:
    pack_manager = importlib.import_module("charter.activation.pack_manager")
    assert hasattr(pack_manager, "YAML_KEY_MAP"), "control: the real module"
    manager = next(v for k, v in vars(pack_manager).items() if k.endswith("CharterManager") or k == "CharterPackManager")
    assert not hasattr(manager, "merge_defaults")
    assert not hasattr(pack_manager, "_load_default_pack") and not hasattr(manager, "_load_default_pack")
