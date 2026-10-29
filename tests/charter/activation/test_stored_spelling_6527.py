"""Every activation writer stores activation stems only (#6527 local slice, #6435; FR-011..FR-015).

One project carries three artifacts whose file stem differs from the spelling an
operator may type: an org toolguide (``acme-tool-file`` / ``acme-tool-id``, also
org-required), an org tactic, a project-layer tactic (``proj-tac`` /
``proj-tac-id``) and the built-in directive ``024-locality-of-change`` /
``DIRECTIVE_024``. Each writer is driven the way an operator drives it, then
every stored ``activated_<kind>`` / ``deactivated_<kind>`` list is checked: no
entry may be a declared id or a ``<kind>:<id>`` URN of an artifact that has a stem.

A second fixture shadows ``024-locality-of-change`` with an org directive of
another id, so ``DIRECTIVE_024`` has no single stem (Decision
``file_name_collision``): every writer that would store it refuses with one
message and writes nothing.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.active_charter_service_builder import build_active_charter_service
from charter.activation.activation_engine import ActivationIdCollisionError
from charter.activation.identity_index import IdentityIndex
from charter.activation.invocation_context import ProjectContext
from charter.activation.org_charter import _promote_org_required_to_config, load_org_charter_policies, org_required_stems
from charter.activation.pack_manager import ActiveCharterManager
from charter.activation.preset_application import PresetIdUnresolvedError, apply_preset_plan, plan_preset_application
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from kernel.activation_ledger_store import activation_ledger_path
from kernel.charter_pack_paths import project_pack_root
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter.interview import _promote_interview_selections
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.integration]

runner = CliRunner()

ORG_TOOL_STEM, ORG_TOOL_ID = "acme-tool-file", "acme-tool-id"  # org-required
ORG_GUIDE_STEM, ORG_GUIDE_ID = "acme-guide-file", "acme-guide-id"  # not required
ORG_TAC_STEM, ORG_TAC_ID = "acme-tac-file", "acme-tac-id"
PROJ_TAC_STEM, PROJ_TAC_ID = "proj-tac", "proj-tac-id"
DIR_STEM, DIR_ID = "024-locality-of-change", "DIRECTIVE_024"
BUILT_IN_TACTIC = "acceptance-test-first"

#: Every declared id / stem pair of the fixture, by kind (the spellings that must never be stored).
DECLARED = {
    ArtifactKind.TOOLGUIDE: {ORG_TOOL_ID: ORG_TOOL_STEM, ORG_GUIDE_ID: ORG_GUIDE_STEM},
    ArtifactKind.TACTIC: {ORG_TAC_ID: ORG_TAC_STEM, PROJ_TAC_ID: PROJ_TAC_STEM},
    ArtifactKind.DIRECTIVE: {DIR_ID: DIR_STEM},
}

_TOOLGUIDE = 'schema_version: "1.0"\nid: {id}\ntool: acme\ntitle: Acme\nsummary: Acme.\nguide_path: acme.md\napplies_to_languages: []\n'
_TACTIC = "schema_version: '1.0'\nid: {id}\nname: T\npurpose: T.\nsteps:\n  - title: Do\n    description: Do it.\n"
_DIRECTIVE = 'schema_version: "1.0"\nid: {id}\ntitle: t\nintent: i\nenforcement: required\n'
_PRESET = (
    "name: p\ndescription: stem spelling\n"
    f"activated_toolguides:\n  - gherkin\n  - {ORG_GUIDE_ID}\n"
    f"activated_tactics:\n  - {BUILT_IN_TACTIC}\n  - tactic:{PROJ_TAC_ID}\n"
    f"activated_directives:\n  - {DIR_ID}\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(tmp_path: Path, *, shadow_directive: bool = False, require_directive: bool = True) -> Path:
    """A fresh (ledger) project with the org pack ``acme`` and a project-layer tactic."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    pack = tmp_path / "acme"
    _write(pack / "toolguides" / f"{ORG_TOOL_STEM}.toolguide.yaml", _TOOLGUIDE.format(id=ORG_TOOL_ID))
    _write(pack / "toolguides" / f"{ORG_GUIDE_STEM}.toolguide.yaml", _TOOLGUIDE.format(id=ORG_GUIDE_ID))
    _write(pack / "tactics" / f"{ORG_TAC_STEM}.tactic.yaml", _TACTIC.format(id=ORG_TAC_ID))
    required = f"required_toolguides:\n  - {ORG_TOOL_ID}\n"
    if shadow_directive:
        # The org file reuses the built-in stem for another id: DIRECTIVE_024 has no single stem.
        _write(pack / "directives" / f"{DIR_STEM}.directive.yaml", _DIRECTIVE.format(id="ACME_024"))
        if require_directive:
            required += f"required_directives:\n  - {DIR_ID}\n"
    _write(pack / "org-charter.yaml", f"org_name: acme\n{required}")
    _write(pack / "presets" / "p.yaml", _PRESET)
    # Lists another directive only: the org-required DIRECTIVE_024 reaches the list through the required union.
    _write(pack / "presets" / "q.yaml", "name: q\ndescription: required union\nactivated_directives:\n  - 001-architectural-integrity-standard\n")
    project_tactics = project_pack_root(tmp_path) / PROJECT_KIND_DIRS[ArtifactKind.TACTIC]
    _write(project_tactics / f"{PROJ_TAC_STEM}.tactic.yaml", _TACTIC.format(id=PROJ_TAC_ID))
    _write(tmp_path / ".kittify" / "config.yaml", f"charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack}\n")
    return tmp_path


def _stored(root: Path) -> dict[str, list[str]]:
    """Every stored ``activated_<kind>`` / ``deactivated_<kind>`` list (ledger, else ``config.yaml``)."""
    lists: dict[str, list[str]] = {}
    for path in (root / ".kittify" / "config.yaml", activation_ledger_path(root)):
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) if path.exists() else None
        for key, value in (data or {}).items():
            if key.startswith(("activated_", "deactivated_")) and key != "activated_kinds" and isinstance(value, list):
                lists[key] = [str(item) for item in value]
    return lists


def _kind_of(key: str) -> ArtifactKind:
    return ArtifactKind.from_plural(key.split("_", 1)[1])


def _is_non_stem(index: IdentityIndex, kind: ArtifactKind, item: str) -> bool:
    """A URN, a fixture declared id, or any known token whose stem is another spelling."""
    if ":" in item or item in DECLARED.get(kind, {}):
        return True
    return index.knows(kind, item) and index.stem(kind, item) not in (None, item)


def _non_stems(root: Path) -> dict[str, list[str]]:
    """Per stored list, the entries spelled as a declared id or a URN of an artifact that has a stem."""
    index = IdentityIndex.build(root)
    found: dict[str, list[str]] = {}
    for key, entries in _stored(root).items():
        kind = _kind_of(key)
        bad = [item for item in entries if _is_non_stem(index, kind, item)]
        if bad:
            found[key] = bad
    return found


def _cli(root: Path, *args: str) -> None:
    result = runner.invoke(charter_app, [args[0], "--repo-root", str(root), "--no-compile", *args[1:]], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def _manager(root: Path) -> tuple[ActiveCharterManager, ProjectContext]:
    return ActiveCharterManager(), ProjectContext.from_repo(root)


# --------------------------------------------------------------- writers --


def _activate_declared_id(root: Path) -> None:
    _cli(root, "activate", "toolguide", "gherkin")  # materialise first, then name declared ids
    _cli(root, "activate", "toolguide", ORG_GUIDE_ID)
    _cli(root, "activate", "directive", DIR_ID)


def _activate_urn(root: Path) -> None:
    _cli(root, "activate", "toolguide", f"toolguide:{ORG_GUIDE_ID}")
    _cli(root, "activate", "tactic", f"tactic:{PROJ_TAC_ID}")
    _cli(root, "activate", "directive", f"directive:{DIR_ID}")


def _activate_absent_key(root: Path) -> None:
    _cli(root, "activate", "toolguide", "gherkin")
    _cli(root, "activate", "tactic", BUILT_IN_TACTIC)


def _activate_only(root: Path) -> None:
    _cli(root, "activate", "toolguide", "gherkin", "--only")
    _cli(root, "activate", "tactic", PROJ_TAC_ID, "--only")


def _cascade(root: Path) -> None:
    _cli(root, "activate", "directive", "001-architectural-integrity-standard", "--cascade", "all")


def _deactivate(root: Path) -> None:
    _cli(root, "deactivate", "toolguide", ORG_GUIDE_ID)
    _cli(root, "deactivate", "tactic", f"tactic:{PROJ_TAC_ID}")
    _cli(root, "deactivate", "directive", DIR_ID)


def _preset(root: Path) -> None:
    apply_preset_plan(root, plan_preset_application(root, "acme", "p"))


def _interview(narrow: bool) -> Callable[[Path], None]:
    def write(root: Path) -> None:
        selections = SimpleNamespace(selected_directives=[DIR_ID], selected_tactics=[PROJ_TAC_ID, ORG_TAC_ID], selected_paradigms=[])
        _promote_interview_selections(root, selections, narrow=narrow)

    return write


def _org_required_union(root: Path) -> None:
    _promote_org_required_to_config(load_org_charter_policies(root), root)


WRITERS: dict[str, Callable[[Path], None]] = {
    "activate-declared-id": _activate_declared_id,
    "activate-urn": _activate_urn,
    "activate-absent-key": _activate_absent_key,
    "activate-only": _activate_only,
    "cascade": _cascade,
    "deactivate": _deactivate,
    "preset": _preset,
    "interview": _interview(narrow=False),
    "interview-narrow": _interview(narrow=True),
    "org-required-union": _org_required_union,
}


@pytest.mark.parametrize("writer", list(WRITERS))
def test_writer_stores_stems_only(tmp_path: Path, writer: str) -> None:
    root = _project(tmp_path)

    WRITERS[writer](root)

    stored = _stored(root)
    assert stored, "fixture invalid: the writer stored nothing"
    assert _non_stems(root) == {}, stored


@pytest.mark.parametrize(
    ("writer", "key", "stems"),
    [
        ("activate-declared-id", "activated_toolguides", {ORG_GUIDE_STEM}),
        ("activate-urn", "activated_tactics", {PROJ_TAC_STEM}),
        ("activate-absent-key", "activated_toolguides", {ORG_TOOL_STEM, ORG_GUIDE_STEM, "gherkin"}),
        ("activate-absent-key", "activated_tactics", {ORG_TAC_STEM, PROJ_TAC_STEM, BUILT_IN_TACTIC}),
        ("activate-only", "activated_toolguides", {ORG_TOOL_STEM, "gherkin"}),
        ("deactivate", "deactivated_tactics", {PROJ_TAC_STEM}),
        ("preset", "activated_toolguides", {ORG_TOOL_STEM, ORG_GUIDE_STEM, "gherkin"}),
        ("preset", "activated_directives", {DIR_STEM}),
        ("preset", "activated_tactics", {PROJ_TAC_STEM, BUILT_IN_TACTIC}),
        ("interview", "activated_tactics", {ORG_TAC_STEM, PROJ_TAC_STEM}),
        ("interview-narrow", "activated_tactics", {ORG_TAC_STEM, PROJ_TAC_STEM}),
        ("org-required-union", "activated_toolguides", {ORG_TOOL_STEM}),
    ],
)
def test_writer_stores_the_stem_of_every_artifact_it_names(tmp_path: Path, writer: str, key: str, stems: set[str]) -> None:
    """Positive control: the artifact is stored (by its stem), not dropped."""
    root = _project(tmp_path)

    WRITERS[writer](root)

    assert stems <= set(_stored(root).get(key, ())), _stored(root).get(key)


def _served(root: Path) -> dict[str, set[str]]:
    """The served (in-force) set of each kind the absent-key materialisation writes."""
    service = build_active_charter_service(root)
    return {
        "toolguides": {str(key) for key in service.toolguides},
        "tactics": {str(key) for key in service.tactics},
    }


def test_the_in_force_set_is_unchanged_by_the_spelling(tmp_path: Path) -> None:
    """An absent-key materialisation stores one entry per artifact, and every artifact once in force stays in force."""
    root = _project(tmp_path)
    index = IdentityIndex.build(root)
    served_before = _served(root)

    _activate_absent_key(root)

    served_after = _served(root)
    # The one artifact the writer names is in force either way (absent key = all in force), so nothing else moves.
    assert served_after == served_before
    assert {ORG_TOOL_ID, ORG_GUIDE_ID} <= served_after["toolguides"], served_after
    assert {ORG_TAC_ID, PROJ_TAC_ID} <= served_after["tactics"], served_after

    for key in ("activated_toolguides", "activated_tactics"):
        entries = _stored(root)[key]
        assert len(entries) == len({index.declared_id(_kind_of(key), item) or item for item in entries}), entries


def test_a_preset_re_applied_over_its_old_declared_id_spelling_is_not_a_customisation(tmp_path: Path) -> None:
    """A list a pre-#6527 preset stored verbatim (``DIRECTIVE_024``) is normalised on the next write, without ``--force``."""
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_directives=[DIR_ID])

    plan = plan_preset_application(root, "acme", "p")

    assert plan.written["activated_directives"] == [DIR_STEM]
    assert "activated_directives" not in plan.customised_changes


# ----------------------------------------- Decision ``file_name_collision`` --
#
# ``DIRECTIVE_024`` is a known declared id whose file name the org pack uses for
# ``ACME_024``: a pack-content error. Every writer that would store the id refuses
# with the one collision message and writes no activation list.

COLLISION_REFUSAL_PARTS = ("directive", f"'{DIR_ID}'", f"'{DIR_STEM}'", "'ACME_024'", "org file", "built-in file", "Rename the org file")


def _assert_collision_message(text: str) -> None:
    flat = " ".join(text.split())
    missing = [part for part in COLLISION_REFUSAL_PARTS if part not in flat]
    assert not missing, (missing, flat)


def _collision_interview(narrow: bool) -> Callable[[Path], object]:
    def write(root: Path) -> object:
        selections = SimpleNamespace(selected_directives=[DIR_ID], selected_tactics=[], selected_paradigms=[])
        return _promote_interview_selections(root, selections, narrow=narrow)

    return write


def _collision_org_required_union(root: Path) -> object:
    return _promote_org_required_to_config(load_org_charter_policies(root), root)


def _collision_org_required_stems(root: Path) -> object:
    """``--only``'s org-required base."""
    return org_required_stems(root, "directives", [])


def _collision_activate(*args: str, only: bool = False) -> Callable[[Path], object]:
    def write(root: Path) -> object:
        manager, ctx = _manager(root)
        return manager.activate(ctx, *args, only=only)

    return write


def _collision_deactivate(root: Path) -> object:
    manager, ctx = _manager(root)
    return manager.deactivate(ctx, "directive", DIR_ID)


#: Writers that raise :class:`ActivationIdCollisionError` (``required``: the fixture lists DIRECTIVE_024 as org-required).
COLLISION_WRITERS: dict[str, tuple[Callable[[Path], object], bool]] = {
    "interview": (_collision_interview(narrow=False), False),
    "interview-narrow": (_collision_interview(narrow=True), False),
    "org-required-union": (_collision_org_required_union, True),
    "org-required-stems": (_collision_org_required_stems, True),
    "activate-declared-id": (_collision_activate("directive", DIR_ID), False),
    "activate-absent-key": (_collision_activate("directive", "001-architectural-integrity-standard"), True),
    "activate-only-base": (_collision_activate("directive", "001-architectural-integrity-standard", only=True), True),
    "deactivate": (_collision_deactivate, False),
}


@pytest.mark.parametrize("writer", list(COLLISION_WRITERS))
def test_every_writer_refuses_a_colliding_declared_id_and_writes_nothing(tmp_path: Path, writer: str) -> None:
    write, required = COLLISION_WRITERS[writer]
    root = _project(tmp_path, shadow_directive=True, require_directive=required)
    if writer == "activate-only-base":
        seed_activation_ledger(root, activated_directives=["001-architectural-integrity-standard"])  # a present list: only the base collides
    index = IdentityIndex.build(root)
    assert index.knows(ArtifactKind.DIRECTIVE, DIR_ID) and index.stem(ArtifactKind.DIRECTIVE, DIR_ID) is None, "fixture invalid: no collision"
    before = _stored(root)

    with pytest.raises(ActivationIdCollisionError) as excinfo:
        write(root)

    _assert_collision_message(str(excinfo.value))
    assert _stored(root) == before


def test_a_preset_whose_org_required_union_collides_is_refused_as_a_collision(tmp_path: Path) -> None:
    root = _project(tmp_path, shadow_directive=True)

    with pytest.raises(PresetIdUnresolvedError) as excinfo:
        plan_preset_application(root, "acme", "q")

    _assert_collision_message(str(excinfo.value))
    assert _stored(root) == {}


def test_a_preset_listing_a_colliding_declared_id_is_refused_as_a_collision(tmp_path: Path) -> None:
    """The listed id was already refused (``PRESET_ID_UNRESOLVED``); the message now names the collision."""
    root = _project(tmp_path, shadow_directive=True, require_directive=False)

    with pytest.raises(PresetIdUnresolvedError) as excinfo:
        plan_preset_application(root, "acme", "p")

    assert "resolve nowhere" not in str(excinfo.value)
    _assert_collision_message(str(excinfo.value))
    # The --json payload keeps naming the refused id under ``unresolved`` (contract unchanged); the reason explains it.
    payload = excinfo.value.payload()
    assert payload["unresolved"] == {"activated_directives": [DIR_ID]}
    _assert_collision_message(payload["reasons"]["activated_directives"])


@pytest.mark.parametrize(
    ("args", "required"),
    [
        pytest.param(("activate", "directive", DIR_ID), False, id="activate-declared-id"),
        pytest.param(("activate", "directive", "001-architectural-integrity-standard"), True, id="activate-absent-key"),
        pytest.param(("activate", "--pack", "acme", "--preset", "q"), True, id="preset-union"),
        pytest.param(("activate", "--pack", "acme", "--preset", "p"), False, id="preset-listed"),
    ],
)
def test_charter_activate_renders_the_collision_as_an_error(tmp_path: Path, args: tuple[str, ...], required: bool) -> None:
    root = _project(tmp_path, shadow_directive=True, require_directive=required)
    before = _stored(root)

    result = runner.invoke(charter_app, [args[0], "--repo-root", str(root), "--no-compile", *args[1:]])

    assert result.exit_code == 1, result.output
    assert "Error" in result.output
    _assert_collision_message(result.output)
    assert _stored(root) == before


@pytest.mark.parametrize("narrow", [False, True], ids=["append", "narrow"])
def test_charter_interview_renders_the_collision_as_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, narrow: bool) -> None:
    root = _project(tmp_path, shadow_directive=True, require_directive=False)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    monkeypatch.chdir(root)
    before = _stored(root)
    args = ["interview", "--defaults", "--profile", "minimal", "--selected-directives", DIR_ID, *(["--narrow-activation"] if narrow else [])]

    result = runner.invoke(charter_app, args)

    assert result.exit_code == 1, result.output
    _assert_collision_message(result.output)
    assert "The interview answers were saved; no activation list was written." in " ".join(result.output.split())
    # The selection promotion wrote nothing; the org pre-fill (the required toolguide) ran before it, as before.
    assert "activated_directives" not in _stored(root), _stored(root)
    assert before == {}


def test_charter_interview_refuses_a_colliding_org_required_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The org pre-fill (the org-required union) is best-effort, but a collision is not swallowed."""
    root = _project(tmp_path, shadow_directive=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    monkeypatch.chdir(root)
    before = _stored(root)

    result = runner.invoke(charter_app, ["interview", "--defaults", "--profile", "minimal"])

    assert result.exit_code == 1, result.output
    _assert_collision_message(result.output)
    assert _stored(root) == before


def test_deactivating_the_colliding_declared_id_refuses_it_as_org_required(tmp_path: Path) -> None:
    """An org-required colliding id is refused as org-required; nothing is recorded.

    The floor is a reader, not a writer: it keeps the declared id the org pack
    lists, so the required-floor refusal names it. On ``origin/main`` this exited 1
    with "Unknown directive ID" (the floor's normaliser skipped an id with no single
    stem) and recorded nothing either; the message is what changed.
    """
    root = _project(tmp_path, shadow_directive=True)

    result = runner.invoke(charter_app, ["deactivate", "--repo-root", str(root), "--no-compile", "directive", DIR_ID])

    assert result.exit_code == 1, result.output
    assert "required by org pack 'acme'" in " ".join(result.output.split())
    assert _stored(root) == {}


def test_deactivating_a_colliding_declared_id_that_no_org_requires_names_the_collision(tmp_path: Path) -> None:
    """``deactivate`` is a writer: the collision is named, not reported as an unknown id."""
    root = _project(tmp_path, shadow_directive=True, require_directive=False)

    result = runner.invoke(charter_app, ["deactivate", "--repo-root", str(root), "--no-compile", "directive", DIR_ID])

    assert result.exit_code == 1, result.output
    assert "Error" in result.output
    assert "Unknown directive ID" not in " ".join(result.output.split())
    _assert_collision_message(result.output)
    assert _stored(root) == {}
