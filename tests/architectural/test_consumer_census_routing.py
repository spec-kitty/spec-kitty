"""Consumer-census routing gate (#6173, mission derived-consumer-census-01M4V5P5).

The durable replacement for hand-maintaining the CI fan-out: it reds when a test
module consumes a mission-pack path its module would NOT be selected for under the
current router + registry, instead of letting the gap reach ``main`` (the #6166
class). It reads the committed census (``.github/ci-consumer-census.json``), the
single durable map of which test module consumes which ``src/**``/``packs/**`` path,
built by ``scripts/ci/consumer_census.py``.

Three guarantees, each red-first (ADR 2026-07-17-1 / charter C-011):

* **Pack-domain routing coverage** — every mission-pack path the census records is
  routable (matches a FANOUT_GROUPS glob). A NEW unrouted pack sub-tree reds here.
* **The three historical pins** — ``mission-steps/.../prompt.md → next``,
  ``cli/commands/lifecycle.py → agent``, ``expected-artifacts.yaml → dossier`` are
  reproduced: the census records each, and ``select_modules`` selects the module.
  Each pin is proven red against a router with its routing glob stripped.
* **Planted-consumer non-vacuity** — a synthetic census consumer under an
  un-globbed pack sub-tree makes the coverage check red (the gate's teeth).

Scope note (honest): the census records wider consumption than the human-validated
``GROUP_MODULE_FANOUT`` (many modules reference widely-used resolver entry points
without asserting on the real shipped pack). Distinguishing a real-pack assertion
from a temp-project one needs running the tests, which a freshness-checked census
build cannot do, so this gate asserts PATH-level routability + the historical pins,
not module-level routing for every census row; full module-set derivation from the
census is the tracked follow-up (see gate_selection.derive_group_module_fanout).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.ci.consumer_census import load_census, unrouted_pack_consumers
from scripts.ci.gate_selection import DEFAULT_ROUTER_PATH, Router, load_router, select_modules

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The #6166 historical pins: (module, exact historical path, the router glob line
# whose removal must red the pin). Each path is the canonical one from the #6166
# Problem table, pinned at routing level like test_gate_selection_authority.py.
_PINS = (
    (
        "next",
        "packs/built-in/missions/mission-steps/software-dev/research/prompt.md",
        "              - 'packs/built-in/missions/mission-steps/**'\n",
    ),
    (
        "agent",
        "src/specify_cli/cli/commands/lifecycle.py",
        "              - '**/specify_cli/cli/commands/lifecycle.py'\n",
    ),
    (
        "dossier",
        "packs/built-in/missions/software-dev/expected-artifacts.yaml",
        "              - 'packs/built-in/missions/**/expected-artifacts.yaml'\n",
    ),
)


@pytest.fixture(scope="module")
def census() -> dict[str, object]:
    return load_census()


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


# ---------------------------------------------------------------------------
# Pack-domain routing coverage: no census pack consumer is unrouted.
# ---------------------------------------------------------------------------
def test_no_census_pack_consumer_is_unrouted(census: dict[str, object], router: Router) -> None:
    """Every mission-pack path the census records matches a FANOUT_GROUPS glob.

    A consumed pack sub-tree with no routing group would select zero fan-out
    modules on edit — its consumers run in no per-PR shard and break ``main`` later
    (#6166). Remedy when this reds: add the sub-tree to a fan-out group's globs in
    ci-router.yml (and keep the scrub/registry lockstep), then regenerate the census.
    """
    unrouted = unrouted_pack_consumers(census, router=router)
    assert not unrouted, (
        "census records mission-pack consumers whose path matches no fan-out group glob "
        "(unrouted — a new consumer that would red main later):\n" + "\n".join(f"  {module}: {path}" for module, path in unrouted)
    )


# ---------------------------------------------------------------------------
# The three #6166 pins: recorded in the census AND routed.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("module", "path", "_glob_line"), _PINS)
def test_historical_pin_is_recorded_and_routed(census: dict[str, object], router: Router, module: str, path: str, _glob_line: str) -> None:
    """Each historical path selects its consumer module (reproduces the #6166 pins),
    and the census records that consumer (so the map agrees with the routing)."""
    assert (_REPO_ROOT / path).is_file(), f"{path} is not a tracked file: the pin would be vacuous"
    assert module in select_modules([path], router=router), f"#6166 regression: {path} no longer selects {module!r}"
    # The census records the module consuming the pin's sub-tree (prompt/manifest
    # are runtime; lifecycle.py is a static import).
    recorded = _census_paths_for(census, module)
    assert any(_same_subtree(path, p) for p in recorded), f"census does not record {module!r} consuming {path}'s sub-tree; recorded={sorted(recorded)}"


@pytest.mark.parametrize(("module", "path", "glob_line"), _PINS)
def test_pin_is_red_without_its_routing_glob(tmp_path: Path, module: str, path: str, glob_line: str) -> None:
    """Red-first provenance: stripping the pin's routing glob from the router makes
    ``select_modules`` stop selecting the module — proving the glob is load-bearing
    and the pin is non-vacuous (the #6156/#6161/#6153 pre-fix state)."""
    text = DEFAULT_ROUTER_PATH.read_text(encoding="utf-8")
    assert glob_line in text, f"router glob line not found verbatim (update the pin): {glob_line!r}"
    mutated = text.replace(glob_line, "")
    router_copy = tmp_path / "ci-router.yml"
    router_copy.write_text(mutated, encoding="utf-8")
    stripped = load_router(router_copy)
    assert module not in select_modules([path], router=stripped), f"stripping {glob_line!r} did not drop {module!r} from the selection — the pin is vacuous"


# ---------------------------------------------------------------------------
# Planted-consumer non-vacuity: a synthetic unrouted pack consumer reds.
# ---------------------------------------------------------------------------
def test_planted_unrouted_consumer_is_caught(census: dict[str, object], router: Router) -> None:
    """A planted census consumer under an un-globbed pack sub-tree makes the
    coverage check non-empty — proving the gate would red on a real new unrouted
    consumer rather than passing vacuously."""
    planted = copy.deepcopy(census)
    modules = planted["modules"]
    assert isinstance(modules, dict)
    planted_path = "packs/built-in/missions/__planted_unrouted_subtree__/thing.md"
    modules.setdefault("kernel", {"consumes": []})
    modules["kernel"]["consumes"].append({"path": planted_path, "provenance": "runtime", "via": "planted-non-vacuity-probe"})
    unrouted = unrouted_pack_consumers(planted, router=router)
    assert ("kernel", planted_path) in unrouted, "the planted unrouted consumer was not caught"
    # And the real census is clean (the probe is the only offender).
    assert not unrouted_pack_consumers(census, router=router)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _census_paths_for(census: dict[str, object], module: str) -> set[str]:
    modules = census["modules"]
    assert isinstance(modules, dict)
    data = modules.get(module, {})
    if not isinstance(data, dict):
        return set()
    return {e["path"] for e in data.get("consumes", [])}


def _same_subtree(pin_path: str, recorded: str) -> bool:
    """Whether a recorded path is in the same routing sub-tree as a pin path."""
    if pin_path == recorded:
        return True
    if "mission-steps" in pin_path and "mission-steps" in recorded:
        return True
    return pin_path.endswith("expected-artifacts.yaml") and recorded.endswith("expected-artifacts.yaml")
