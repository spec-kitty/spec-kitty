"""CLI command fan-out routing gate (#6221).

Every ``src/specify_cli/cli/commands/**`` module whose tests live in OTHER modules
must route to those modules, so a PR that breaks a command goes red PER-PR instead
of first reding the nightly (the #6166 residue: a cli/commands change matched only
the broad ``cli`` group -> the ``cli`` module, whose shard runs ``tests/cli`` alone,
while the command delegates into domain packages whose tests live elsewhere).

The fan-out is the non-census ``gate_selection.CLI_COMMAND_MODULE_FANOUT`` (the
sibling of ``DEPENDENCY_MODULE_FANOUT``). This gate pins the #6166/#6174 maintainer
inventory as the expected test-owner set per representative command and proves
``select_modules`` selects it — the sibling of
``test_consumer_census_routing.py``'s historical pins, red-first by mutation.

Scope note (operator ruling, 2026-10-14): #6221's src fan-out is landed here in
full; the orphaned *test* tree ``tests/specify_cli/cli/commands`` (220 files, nested
under the execution_context-claimed ``commands/agent`` and the #4732-deferred
``commands/charter`` + ``commands/review``) is a separate structural restructure
filed-and-linked as a follow-up, while ``tests/specify_cli/mission_step_contracts``
(the clean, non-nested tree) is claimed in the module registry in this change.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci.gate_selection import (
    CLI_COMMAND_MODULE_FANOUT,
    DEFAULT_ROUTER_PATH,
    Router,
    load_router,
    select_modules,
)

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]

# (router group, representative on-disk command path, the test-owning modules the
# #6166/#6174 inventory records). ``select_modules`` must select a SUPERSET of the
# expected set (the owning ``cli`` module always rides along via the ``cli`` group,
# and a cluster may legitimately over-route a sibling by one module -- see the
# CLI_COMMAND_MODULE_FANOUT comments). Each path is a tracked file so the pin is
# never vacuous.
_INVENTORY: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("cli_cmd_charter", "src/specify_cli/cli/commands/charter/_app.py", frozenset({"charter", "agent", "upgrade", "consolidation", "core_misc"})),
    (
        "cli_cmd_consolidate",
        "src/specify_cli/cli/commands/consolidate.py",
        frozenset({"consolidation", "agent", "core_misc", "execution_context", "lanes", "post_merge", "missions"}),
    ),
    ("cli_cmd_agent", "src/specify_cli/cli/commands/tracker.py", frozenset({"agent"})),
    ("cli_cmd_implement", "src/specify_cli/cli/commands/implement.py", frozenset({"agent", "lanes", "core_misc", "execution_context"})),
    ("cli_cmd_init", "src/specify_cli/cli/commands/init.py", frozenset({"core_misc", "upgrade", "agent", "execution_context"})),
    ("cli_cmd_doctor", "src/specify_cli/cli/commands/doctor.py", frozenset({"charter", "core_misc", "agent", "consolidation", "upgrade"})),
    ("cli_cmd_upgrade", "src/specify_cli/cli/commands/upgrade.py", frozenset({"upgrade", "core_misc", "kernel"})),
    ("cli_cmd_next", "src/specify_cli/cli/commands/next_cmd.py", frozenset({"next"})),
    ("cli_cmd_mission_type", "src/specify_cli/cli/commands/mission_type.py", frozenset({"missions", "core_misc", "unit"})),
    ("cli_cmd_merge_driver", "src/specify_cli/cli/commands/merge_driver.py", frozenset({"consolidation"})),
    ("cli_cmd_charter_pack", "src/specify_cli/cli/commands/profiles_cmd.py", frozenset({"charter"})),
    ("cli_cmd_status", "src/specify_cli/cli/commands/materialize.py", frozenset({"status", "core_misc"})),
    ("cli_cmd_plugin", "src/specify_cli/cli/commands/plugin.py", frozenset({"core_misc"})),
    (
        "cli_cmd_agent_subdir",
        "src/specify_cli/cli/commands/agent/config.py",
        frozenset({"agent", "status", "review", "core_misc", "lanes", "consolidation", "release"}),
    ),
)


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


def test_inventory_covers_every_cli_command_fanout_group() -> None:
    """Non-vacuity: every ``CLI_COMMAND_MODULE_FANOUT`` group has a pinned inventory row,
    and every pinned group is a real fan-out group (no stale rows)."""
    pinned = {group for group, _path, _mods in _INVENTORY}
    fanout = set(CLI_COMMAND_MODULE_FANOUT)
    assert pinned == fanout, f"inventory pins {sorted(pinned)} but CLI_COMMAND_MODULE_FANOUT has {sorted(fanout)}"


@pytest.mark.parametrize(("group", "path", "expected"), _INVENTORY, ids=[row[0] for row in _INVENTORY])
def test_each_command_module_routes_to_its_test_owning_modules(router: Router, group: str, path: str, expected: frozenset[str]) -> None:
    """Each command path selects (at least) its #6166/#6174 test-owning modules, and
    never loses the owning ``cli`` module."""
    assert (_REPO_ROOT / path).is_file(), f"{path} is not a tracked file: the pin would be vacuous"
    selected = select_modules([path], router=router)
    missing = expected - selected
    assert not missing, f"{group}: {path} does not route to {sorted(missing)} (its tests live there — #6221). selected={sorted(selected)}"
    assert "cli" in selected, f"{group}: the fan-out dropped the owning `cli` module for {path}"
    assert expected == CLI_COMMAND_MODULE_FANOUT[group], f"{group}: inventory row diverged from CLI_COMMAND_MODULE_FANOUT"


def test_routing_is_red_without_its_fanout_glob(tmp_path: Path) -> None:
    """Red-first provenance / mutation proof: stripping ``cli_cmd_next``'s router glob makes
    ``select_modules`` stop selecting ``next`` for ``next_cmd.py`` — proving the glob is
    load-bearing and the fan-out is non-vacuous (the pre-#6221 state, where the path matched
    only the ``cli`` group). ``next_cmd.py`` reaches the ``next`` module ONLY through this
    fan-out, so it is the clean single-module witness."""
    glob_line = "              - '**/specify_cli/cli/commands/next_cmd.py'\n"
    path = "src/specify_cli/cli/commands/next_cmd.py"
    text = DEFAULT_ROUTER_PATH.read_text(encoding="utf-8")
    assert glob_line in text, f"router glob line not found verbatim (update the mutation witness): {glob_line!r}"
    assert "next" in select_modules([path]), "baseline: next_cmd.py must route to `next` before the mutation"

    mutated = text.replace(glob_line, "")
    router_copy = tmp_path / "ci-router.yml"
    router_copy.write_text(mutated, encoding="utf-8")
    stripped = load_router(router_copy)
    assert "next" not in select_modules([path], router=stripped), "stripping the cli_cmd_next glob did not drop `next` — the fan-out is vacuous"


def test_mission_step_contracts_tree_is_claimed(router: Router) -> None:
    """#6221: the previously-orphaned ``tests/specify_cli/mission_step_contracts`` tree now
    routes to a per-PR module (claimed by ``missions`` in the registry), so a change to those
    test files runs in a per-PR shard instead of only the nightly interpreter sweep."""
    tree = "tests/specify_cli/mission_step_contracts"
    assert (_REPO_ROOT / tree).is_dir()
    selected = select_modules([f"{tree}/test_executor.py"], router=router)
    assert "missions" in selected, f"{tree} routes to no per-PR module (expected `missions`); selected={sorted(selected)}"
