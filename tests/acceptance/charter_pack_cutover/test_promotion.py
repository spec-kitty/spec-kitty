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
    """The preflight's proposed directive selection covers the selection the activation wrote.

    The activation write already preserves the effective set at base (#4253), so the written
    key is the reference; both sides are config ids.
    """
    assert proposals and proposals[-1] is not None, "control: the resynthesis preflight ran"
    proposed = set(proposals[-1].activated_directives or ())
    written_value = active_charter(project).get("activated_directives")
    assert isinstance(written_value, list), written_value
    written = {str(i) for i in written_value}
    assert PROMOTED_DIRECTIVE in proposed, "control: the preflight proposes the requested directive"
    narrowed = sorted(written - proposed)
    assert not narrowed, f"the resynthesis preflight seeded a narrower set than the activation wrote: {narrowed}"


#: The synthesis step that follows a resynthesizing activation needs the agent-authored
#: artifacts under ``.kittify/charter/generated/`` (one per interview target, the
#: ``how-we-apply-*`` tactics included), which this fixture deliberately does not provide.
#: The command therefore exits 1 there, after the preflight and the activation write.
SYNTHESIS_NEEDS_GENERATED_ARTIFACTS = "GeneratedArtifactMissingError"


def _assert_caller_ran(caller: str, result: Result) -> None:
    if caller != "resynthesize":
        assert result.exit_code == 0, describe(result)
        return
    text = output_of(result)
    assert result.exit_code == 1, describe(result)
    assert "Activated" in text and SYNTHESIS_NEEDS_GENERATED_ARTIFACTS in text, describe(result)


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
    assert "activated_directives" in active_charter(project), "control: the caller promoted the directive key"
    if caller == "resynthesize":
        _assert_preflight_seeded_from_effective_set(proposals, project)
    after = expand(effective_set(project, inventory), inventory)
    lost = {kind: sorted(before[kind] - after[kind]) for kind in before if before[kind] - after[kind]}
    assert not lost, f"{caller} narrowed the effective set: {lost}"


@covers("FR-015", "US5-2")
def test_fr015_unresolvable_set_leaves_key_absent_and_reports(tmp_path: Path) -> None:
    healthy = _fixture(tmp_path / "healthy")
    assert _interview(healthy).exit_code == 0
    assert "activated_directives" in active_charter(healthy), "control: the healthy fixture promotes"
    broken = _fixture(tmp_path / "broken")
    config = load_yaml(broken / ".kittify" / "config.yaml")
    config["charter_packs"]["org"]["packs"][1]["local_path"] = "org-packs/does-not-exist"
    finish(broken, config)
    result = _interview(broken)
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
