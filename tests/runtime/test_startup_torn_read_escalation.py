"""Issue #3998 red-first regression: an unlocked torn read on a fresh (cold)
shared home crashes the actual command a user or agent ran, instead of
waiting for the concurrent installer and converging.

Today's failure path: ``AssetPreparation.observe()`` sees an owner's own
inventory file in two different states within one unlocked assessment pass
(a benign concurrent peer mid-write) and raises ``ValueError("Asset changed
during preparation: <path>")``. ``retry_torn_read`` re-races the writer three
times WITHOUT waiting, ``incomplete()`` collapses the error into the generic
``global_assets_unavailable`` diagnostic, and ``ensure_*`` raises a bare
``RuntimeError`` that the CLI renders as a traceback.

This file drives EACH owner's PRE-EXISTING startup entry point
(``bootstrap.ensure_runtime``, ``agent_commands.ensure_global_agent_commands``,
``agent_skills.ensure_global_agent_skills``), injecting the torn read ONLY at
leaf I/O (``asset_preparation.node_state`` / ``asset_preparation.
machine_file_lock``) -- never by patching ``assess_*``, ``retry_torn_read``,
``build_serialized`` or any other helper. See spec.md/plan.md for the fix
design (serialization-point escalation) this test proves.

Must be RED on the planning base for all three owner parameters with the
exact production failure ``Asset changed during preparation`` (C-007,
ADR 2026-07-17-1). See the WP Activity Log for the captured red evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import specify_cli.runtime.agent_commands as agent_commands
import specify_cli.runtime.agent_skills as agent_skills
import specify_cli.runtime.asset_preparation as asset_preparation
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.home import get_kittify_home
from specify_cli.skills.registry import SkillRegistry
from specify_cli.tool_surface.operations import FileState

pytestmark = [pytest.mark.unit, pytest.mark.fast]

TORN_READ_SIGNAL = "Asset changed during preparation"

#: owner key -> the pre-existing startup entry point this WP must drive
#: through, never a lower-level helper. ``commands`` scopes to one agent and
#: ``fake_command_templates`` trims the template source so the render stays
#: fast and never touches the real ``packs/built-in`` corpus (see that
#: fixture's docstring).
_ENTRY_POINTS: dict[str, Callable[[], None]] = {
    "runtime": bootstrap.ensure_runtime,
    "commands": lambda: agent_commands.ensure_global_agent_commands(agent_keys=["claude"]),
    "skills": agent_skills.ensure_global_agent_skills,
}
_OWNER_KEYS = {"runtime": "runtime_bootstrap", "commands": "slash_commands", "skills": "global_skills"}


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``SPEC_KITTY_HOME``/``HOME`` at a genuinely cold home.

    Mirrors ``tests/runtime/test_generic_asset_scope.py``'s identically-named
    fixture.
    """
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    return home


@pytest.fixture()
def fake_package_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal fake package asset root for the RUNTIME family.

    Kept OUTSIDE the kittify home (a sibling of ``fake_home``'s ``home``, both
    under ``tmp_path``) so a source-role observation of a package asset never
    shares a path with a destination-probe of the runtime owner's own
    managed tree -- source-role stickiness must never accidentally reclassify
    the injected destination tear as source drift.
    """
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"
    (missions / "software-dev").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates").mkdir()
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")

    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate")

    (pkg_root / "AGENTS.md").write_text("# Agents")

    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions


@pytest.fixture()
def fake_command_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trimmed command-templates dir (``PROMPT_DRIVEN_COMMANDS`` only).

    With the REAL templates, the commands param takes ~15s and reading
    ``packs/built-in`` trips the corpus-marker guard -- see fold note 5 on
    the WP prompt. Mirrors ``tests/specify_cli/runtime/test_agent_commands.py``'s
    ``TestFreshnessPrecheck._write_prompt_templates``.
    """
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

    templates_dir = tmp_path / "command-templates"
    for command in PROMPT_DRIVEN_COMMANDS:
        step_dir = templates_dir / command
        step_dir.mkdir(parents=True)
        (step_dir / "prompt.md").write_text(f"---\ndescription: {command}\n---\n# {command}\n", encoding="utf-8")
    monkeypatch.setattr(agent_commands, "_get_command_templates_dir", lambda: templates_dir)
    return templates_dir


@pytest.fixture()
def fake_skill_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SkillRegistry:
    """A minimal real canonical skill registry.

    Mirrors ``tests/runtime/test_generic_asset_scope.py``'s identically-named
    fixture -- lets ``agent_skills``'s assess/ensure entry points run for real
    against a tiny, deterministic catalog instead of the full package registry.
    """
    skills_root = tmp_path / "doctrine_skills"
    skill_dir = skills_root / "spec-kitty-test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: spec-kitty-test-skill\ndescription: test\n---\n# test\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_root)
    monkeypatch.setattr(agent_skills, "_discover_registry", lambda: registry)
    return registry


def _tear_owner_inventory_while_peer_active(
    inventory: Path,
    peer: dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrap leaf I/O ONLY to model a concurrent peer mid-write to *inventory*.

    Every unlocked observation of *inventory* alternates absent/file (a
    changing digest) while ``peer["active"]`` is True -- exactly the shape an
    in-flight writer produces (each fresh ``AssetPreparation`` observes its
    inventory exactly twice per pass: once at ``__init__``, once again at
    ``finish()``'s effect computation, so the alternation naturally starts
    from ``absent`` for every fresh attempt). Wrapping
    ``machine_file_lock`` (never any higher-level assess/retry/escalation
    helper) clears the flag the instant this process is granted a REAL lock,
    modeling "the writer already finished by the time I hold its lock".
    """
    real_node_state = asset_preparation.node_state
    real_lock = asset_preparation.machine_file_lock
    calls = {"n": 0}

    def fake_node_state(path: Path, *, read_content: bool = True) -> FileState:
        if peer["active"] and path == inventory:
            calls["n"] += 1
            if calls["n"] % 2 == 1:
                return FileState("absent")
            changing_digest = asset_preparation.digest(str(calls["n"]).encode())
            return FileState("file", sha256=changing_digest, mode=0o644)
        return real_node_state(path, read_content=read_content)

    def fake_machine_file_lock(*args: object, **kwargs: object):  # noqa: ANN002, ANN003
        peer["active"] = False
        return real_lock(*args, **kwargs)

    monkeypatch.setattr(asset_preparation, "node_state", fake_node_state)
    monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_machine_file_lock)


@pytest.mark.regression
@pytest.mark.parametrize("owner", ["runtime", "commands", "skills"])
def test_ensure_converges_when_unlocked_assessment_tears(
    owner: str,
    fake_home: Path,
    fake_package_assets: Path,
    fake_command_templates: Path,
    fake_skill_registry: SkillRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-001/FR-002/FR-006, C-007, SC-002.

    Given a cold home and a peer mid-write to this owner's inventory, when the
    owner's pre-existing startup entry point runs and its unlocked assessment
    tears, the command must converge (acquire the serialization point,
    reassess once under it, and run) rather than crash.
    """
    inventory = get_kittify_home() / "cache" / f"{_OWNER_KEYS[owner]}-assets.json"
    peer = {"active": True}
    _tear_owner_inventory_while_peer_active(inventory, peer, monkeypatch)

    _ENTRY_POINTS[owner]()  # must NOT raise "Asset changed during preparation"

    assert inventory.is_file(), f"{owner} owner inventory must materialize once the assessment converges"
