"""An explicitly owned checkout supplies its own charter and templates."""

import os
from pathlib import Path
import subprocess

import pytest

from charter.activation.pack_context import ActiveCharterConfigError
from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import create_mission_core
from specify_cli.core.owned_mission import resolve_owned_create_root
from tests._factories import provision_test_charter
from tests._owned_fixtures import RSnapshotter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.mark.parametrize("owned_active", [True, False])
def test_owned_checkout_controls_charter_and_template(tmp_path, monkeypatch, owned_active):
    repository_root = tmp_path / "repository_root"
    repository_root.mkdir()
    _git(repository_root, "init", "-b", "main")
    _git(repository_root, "config", "user.email", "test@example.com")
    _git(repository_root, "config", "user.name", "Test")
    (repository_root / ".kittify").mkdir()
    (repository_root / ".kittify/config.yaml").write_text("mission_type_activations: []\n")
    _git(repository_root, "add", ".")
    _git(repository_root, "commit", "-m", "initial")
    owned = tmp_path / "owned"
    _git(repository_root, "worktree", "add", "-b", "feature", str(owned))
    active = owned if owned_active else repository_root
    (active / ".kittify/config.yaml").unlink()
    provision_test_charter(active)
    monkeypatch.chdir(owned)

    class TemplateReached(Exception):
        pass

    def resolve_template(name, root, context):
        assert name == "spec"
        assert root == owned
        raise TemplateReached

    monkeypatch.setattr("specify_cli.runtime.resolver.resolve_configured_template", resolve_template)
    expected = TemplateReached if owned_active else ActiveCharterConfigError
    owned_create_root = resolve_owned_create_root(repository_root, owned)
    with pytest.raises(expected):
        create_mission_core(
            repository_root,
            "owned-charter",
            owned_create_root=owned_create_root,
            topology=MissionTopology.SINGLE_BRANCH,
            friendly_name="Owned charter",
            purpose_tldr="Resolve the selected checkout charter.",
            purpose_context="Keep mission creation bound to the explicitly owned checkout configuration.",
        )
    assert not (repository_root / "kitty-specs").exists()
    assert not (owned / "kitty-specs").exists()


def _init_repository_root_and_owned(tmp_path: Path) -> tuple[Path, Path]:
    """Repository root checkout + a linked, activated owned checkout (T054 shared fixture)."""
    repository_root = tmp_path / "repository_root"
    repository_root.mkdir()
    _git(repository_root, "init", "-b", "main")
    _git(repository_root, "config", "user.email", "test@example.com")
    _git(repository_root, "config", "user.name", "Test")
    (repository_root / ".kittify").mkdir()
    provision_test_charter(repository_root)
    _git(repository_root, "add", ".")
    _git(repository_root, "commit", "-m", "initial")
    owned = tmp_path / "owned"
    _git(repository_root, "worktree", "add", "-b", "feature", str(owned))
    return repository_root, owned


def test_owned_checkout_template_marker_wins_over_repository_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US5-AS3: P's spec template (carrying a marker) is used, never R's.

    Red-first (T054, committed before T053's fix): before FR-016's
    re-expression, ``resolve_configured_template`` still reads R, so the
    scaffolded ``spec.md`` carries R's content, not P's marker.
    """
    repository_root, owned = _init_repository_root_and_owned(tmp_path)
    monkeypatch.chdir(owned)

    owned_override = owned / ".kittify" / "overrides" / "missions" / "software-dev" / "templates"
    owned_override.mkdir(parents=True)
    (owned_override / "spec-template.md").write_text("# OWNED-TEMPLATE-MARKER\n", encoding="utf-8")

    repository_root_override = repository_root / ".kittify" / "overrides" / "missions" / "software-dev" / "templates"
    repository_root_override.mkdir(parents=True)
    (repository_root_override / "spec-template.md").write_text("# repository-root-template\n", encoding="utf-8")

    result = create_mission_core(
        repository_root,
        "owned-marker",
        owned_create_root=resolve_owned_create_root(repository_root, owned),
        topology=MissionTopology.SINGLE_BRANCH,
        friendly_name="Owned marker",
        purpose_tldr="Resolve the owned checkout's own spec template.",
        purpose_context="The owned checkout's project-local template override must win over the repository root's.",
    )
    spec_content = result.feature_dir.joinpath("spec.md").read_text(encoding="utf-8")
    assert "OWNED-TEMPLATE-MARKER" in spec_content
    assert "repository-root-template" not in spec_content


def _write_mission_step_template_override(root: Path, *, template_file: str) -> None:
    """Shadow the software-dev ``specify`` step's ``template_file`` mapping at the project layer.

    ``<root>/.kittify/overrides/mission-steps/<mission_type>/<step_id>/step.yaml``
    is the project layer ``MissionStepRepository._resolve_project_layer`` checks
    FIRST (project beats org beats built-in) -- see
    ``charter/offering/missions/mission_step_repository.py``. Copies the real
    built-in step.yaml verbatim and only overwrites ``template.template_file``,
    so every other field (``step_type``, ``prompt_template``, ``sequence_index``,
    ...) stays byte-identical to the shipped step -- never a hand-authored guess
    at the schema.
    """
    import yaml

    # Resolved relative to THIS file, never the process cwd: the caller
    # ``monkeypatch.chdir(owned)``s before calling this helper.
    repo_root_of_this_checkout = Path(__file__).resolve().parents[2]
    builtin_step = repo_root_of_this_checkout / "packs/built-in/missions/mission-steps/software-dev/specify/step.yaml"
    step_data = yaml.safe_load(builtin_step.read_text(encoding="utf-8"))
    step_data["template"]["template_file"] = template_file

    override_dir = root / ".kittify" / "overrides" / "mission-steps" / "software-dev" / "specify"
    override_dir.mkdir(parents=True, exist_ok=True)
    (override_dir / "step.yaml").write_text(yaml.safe_dump(step_data, sort_keys=False), encoding="utf-8")


def test_owned_checkout_mission_type_context_wins_over_repository_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T054 step 1b, the mission-type-context divergence row (FR-016's third read).

    P and R shadow the software-dev ``specify`` step's ``template_file``
    mapping differently at the project layer -- P maps ``spec`` to
    ``owned-spec-template.md`` (a template carrying ``OWNED-CONTEXT-MARKER``),
    R keeps the built-in ``spec-template.md``. This exercises
    ``resolve_mission_type_context`` itself (the read a mutation reverting
    ONLY the context read to R would still trip, unlike the plain
    template-marker test above, which a context-read reversion does not
    catch since it asserts on the resolved template's CONTENT, not on which
    checkout's step mapping produced the filename).

    Red-first ruling (orchestrator, review cycle 1 HIGH-1): the reviewer
    proved this row red at cc6230ede (before T053's fix) and green at head;
    that stands as the commit-anchored red proof. See this WP's Activity Log.
    """
    repository_root, owned = _init_repository_root_and_owned(tmp_path)
    monkeypatch.chdir(owned)

    _write_mission_step_template_override(owned, template_file="owned-spec-template.md")
    owned_templates = owned / ".kittify" / "overrides" / "missions" / "software-dev" / "templates"
    owned_templates.mkdir(parents=True)
    (owned_templates / "owned-spec-template.md").write_text("# OWNED-CONTEXT-MARKER\n", encoding="utf-8")

    from charter.activation.mission_type_profiles import resolve_mission_type_context

    # Sanity pins (reviewer-verified shape): the project-layer step override
    # changes the RESOLVED template_set mapping, not just which file content
    # ends up on disk -- proving the two checkouts' CONTEXT reads genuinely
    # diverge, not merely their template file contents.
    owned_context = resolve_mission_type_context(owned, mission_type="software-dev")
    repository_root_context = resolve_mission_type_context(repository_root, mission_type="software-dev")
    assert owned_context.template_set is not None
    assert owned_context.template_set["spec"] == "owned-spec-template.md"
    assert repository_root_context.template_set is not None
    assert repository_root_context.template_set["spec"] == "spec-template.md"

    result = create_mission_core(
        repository_root,
        "owned-context",
        owned_create_root=resolve_owned_create_root(repository_root, owned),
        topology=MissionTopology.SINGLE_BRANCH,
        friendly_name="Owned context",
        purpose_tldr="Resolve the owned checkout's own mission-type context.",
        purpose_context="The owned checkout's mission-step template mapping must be the one create_mission_core resolves.",
    )
    spec_content = result.feature_dir.joinpath("spec.md").read_text(encoding="utf-8")
    assert "OWNED-CONTEXT-MARKER" in spec_content


def test_fr017_charter_authoring_still_refused_for_the_same_owned_fixture(tmp_path: Path) -> None:
    """FR-017 ratchet, paired on the SAME fixture as the marker test above.

    Charter *authoring* stays refused for a linked owned checkout (#4785)
    even though create-time *reads* now resolve against it (FR-016). This
    assertion is green both before and after T053 -- that is correct for a
    ratchet requirement.
    """
    from specify_cli.cli.commands.charter._charter_write_root import (
        LinkedWorktreeCharterWriteError,
        resolve_charter_write_root,
    )

    repository_root, owned = _init_repository_root_and_owned(tmp_path)

    with pytest.raises(LinkedWorktreeCharterWriteError):
        resolve_charter_write_root(owned)


def test_owned_create_leaves_repository_root_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T053 checklist: the repository root checkout around an owned create is unchanged.

    Uses the canonical NFR-001 oracle (``RSnapshotter``, WP02/WP06) rather
    than a parallel local reimplementation (MEDIUM-9 fix-cycle-2): it also
    covers the shared lock root and ``SPEC_KITTY_HOME``, neither of which a
    plain tree-hash-plus-git-facts snapshot reaches. An owned create
    acquires the pre-existing per-mission status mutex in R's shared git
    common directory (predates this fixture, out of scope to convert) --
    the ONE tolerated delta ``tolerate_status_mutex_for`` names; every other
    shape in ``files``/``head``/``index_stage``/``index_diff``/``lock_files``/
    ``home_files`` still fails closed.
    """
    repository_root, owned = _init_repository_root_and_owned(tmp_path)
    monkeypatch.chdir(owned)

    home = Path(os.environ["SPEC_KITTY_HOME"]) if os.environ.get("SPEC_KITTY_HOME") else None
    snapshotter = RSnapshotter(repository_root, owned, home)

    before = snapshotter.take()
    result = create_mission_core(
        repository_root,
        "owned-r-untouched",
        owned_create_root=resolve_owned_create_root(repository_root, owned),
        topology=MissionTopology.SINGLE_BRANCH,
        friendly_name="Owned R untouched",
        purpose_tldr="Prove R stays untouched by an owned create.",
        purpose_context="Every write for this create must land on the owned checkout, never the repository root.",
    )
    after = snapshotter.take()

    snapshotter.assert_unchanged(before, after, tolerate_status_mutex_for=result.feature_dir.name)


# ---------------------------------------------------------------------------
# B5' (review cycle 2, ruling reversed, coord-artifact-single-home-01M3V4BE):
# an owned-checkout create combined with a coordination-routed topology is a
# SUPPORTED path (FR-022's TestFr022CoordinationTwin ratchet), not a refusal
# target. INV-COORD-HOME residual: the status log is never seeded onto the
# coordination surface for an owned create -- it stays in the owned
# checkout's own PRIMARY dir, scaffolded and committed exactly as at base
# (e7b085d26c).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD], ids=lambda t: t.value)
def test_owned_checkout_with_coordination_topology_scaffolds_status_log_at_base_shape(tmp_path: Path, topology: MissionTopology) -> None:
    """An owned coordination-routed create keeps the base (pre-WP06) scaffold shape.

    INV-COORD-HOME residual: ``_seed_coord_surface_for_create`` never seeds
    the coordination surface for an owned create (an ``OwnedCreateMission``
    does not satisfy the ``mission_runtime.OwnedCheckout`` contract the
    coordination write-path requires), so ``MissionCreated`` lands on
    ``feature_dir`` in the owned checkout instead. This pins that the status
    log is present there, carries ``MissionCreated``, and is part of the
    owned checkout's own HEAD commit for this create -- not merely written
    to disk and left uncommitted (the regression a prior cycle-2 fix
    introduced by keying the scaffold's coordination-routed branch on
    ``topology`` alone, ignoring ``owned``).
    """
    from specify_cli.status import MISSION_CREATED, read_lifecycle_events

    repository_root, owned = _init_repository_root_and_owned(tmp_path)
    slug = f"owned-coord-log-{topology.value.replace('_', '-')}"

    result = create_mission_core(
        repository_root,
        slug,
        owned_create_root=resolve_owned_create_root(repository_root, owned),
        topology=topology,
        friendly_name="Owned coord log",
        purpose_tldr="Pin the owned coordination-topology create's status log shape.",
        purpose_context="An owned coordination create keeps its status log in its own PRIMARY dir, committed exactly as at base.",
    )

    log_path = result.feature_dir / "status.events.jsonl"
    assert log_path.exists(), "the status log must be scaffolded in the owned checkout's own PRIMARY dir"
    event_types = [event.get("event_type") for event in read_lifecycle_events(log_path)]
    assert MISSION_CREATED in event_types

    committed = subprocess.run(
        ["git", "show", f"HEAD:kitty-specs/{result.mission_slug}/status.events.jsonl"],
        cwd=owned,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "MissionCreated" in committed.stdout, "the status log must be part of the owned checkout's own scaffold commit, not merely written-but-uncommitted"
