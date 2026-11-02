"""Routing pins for the charter activation store and the internal-pack pin (#6336).

An activation-store edit (``.kittify/charter/charter.yaml``,
``.kittify/charter/activation.yaml``) or an internal-pack pin bump
(``packs/internal.source.yaml``) can change what the charter module's
config-parity tests assert, but on pre-#6336 ``main`` such a diff matched only
the non-src ``corpus`` group and selected **zero** modules — so
``module-tests (charter shard …)`` never ran. That is how #6333 reached ``main``
green and then reddened every later PR (which is tested as merged).

#6334 refused the obvious fix (appending the store to the router's ``charter``
filter group) because a router group's globs must be a verbatim transcription of
that group's roots in ``tests/release/ci_retirement_scrub.json`` and the ``charter``
group is the charter *source* subsystem. This module pins the fix that was
accepted instead: a NON-src ``charter_activation`` router group fanned out to the
``charter`` registry module by the single gate-selection authority
(``scripts/ci/gate_selection.py``), plus the activation ledger's kernel floor
joining the ``charter`` group's roots so the ``tests/charter/activation/**``
readers run when it changes.

Every assertion drives the production entry point ``select_gates`` /
``select_modules`` — the same call ``.github/workflows/ci-modules.yml`` makes to
build the module matrix — never a helper copy of the routing. The group's
declaration (fan-out table, ``changes.outputs`` row, non-src, ungated) is pinned by
``tests/architectural/test_gate_selection_authority.py``,
``test_ci_router_transcription_guards.py`` and ``test_workflow_coherence.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci.gate_selection import (
    Router,
    load_router,
    select_gates,
    select_modules,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRUB_PATH = _REPO_ROOT / "tests" / "release" / "ci_retirement_scrub.json"

ACTIVATION_GROUP = "charter_activation"
CHARTER_MODULE = "charter"

#: The in-repo triggers of an activation change (#6336, with the two maintainer
#: amendments: ``packs/internal/**`` is untracked since #6451, so the pin lockfile
#: is the live internal-pack signal; the two activation-store files arrive with the
#: persistent-deactivation-ledger mission).
ACTIVATION_TRIGGERS: tuple[str, ...] = (
    ".kittify/charter/charter.yaml",
    ".kittify/charter/activation.yaml",
    "packs/internal.source.yaml",
)

#: The activation ledger's kernel-side floor. A ``src/`` file, so it cannot live in
#: the non-src ``charter_activation`` group; it joins the ``charter`` scrub group's
#: roots instead (its readers are ``tests/charter/activation/**``).
LEDGER_FLOOR = "src/kernel/activation_ledger_store.py"
LEDGER_READER = "src/charter/activation/activation_ledger.py"


def _router_without(globs_to_drop: dict[str, tuple[str, ...] | list[str]]) -> Router:
    router = load_router()
    filters = dict(router.filters)
    for group, globs in globs_to_drop.items():
        filters[group] = tuple(glob for glob in filters[group] if glob not in tuple(globs))
    return Router(filters=filters, job_gates=router.job_gates)


def _scrub_roots(group: str) -> list[str]:
    scrub = json.loads(_SCRUB_PATH.read_text(encoding="utf-8"))
    return list(next(row for row in scrub["groups"] if row["group"] == group)["roots"])


# ---------------------------------------------------------------------------
# FR-002 / FR-003 — the activation store and the internal-pack pin select charter
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", ACTIVATION_TRIGGERS)
def test_activation_trigger_selects_the_charter_module(path: str) -> None:
    """#6336 acceptance: an activation/pin edit selects the charter module shard."""
    router = load_router()

    selection = select_gates([path], router=router)

    assert ACTIVATION_GROUP in selection.matched_groups, f"{path} does not match the {ACTIVATION_GROUP!r} router group, so the charter shard is not selected for it"
    assert select_modules([path], router=router) == frozenset({CHARTER_MODULE}), (
        f"{path} must select exactly the {CHARTER_MODULE!r} module (the shard that owns the config-parity tests reading it)"
    )


def test_unrelated_activation_paths_stay_unrouted() -> None:
    """A sibling charter-state file that no test reads is NOT dragged in.

    Positive control for the pin above: the group names three concrete paths, not
    ``.kittify/charter/**``, so ``graph.yml``/``provenance/**`` keep selecting only
    ``corpus`` (no module) — the blast radius stays exactly as narrow as the tests
    that read those files.
    """
    router = load_router()

    for path in (".kittify/charter/graph.yml", ".kittify/charter/interview/x.yaml"):
        selection = select_gates([path], router=router)
        assert ACTIVATION_GROUP not in selection.matched_groups, f"{path} is not an activation trigger"
        assert select_modules([path], router=router) == frozenset()


def test_an_unmapped_src_change_still_forces_run_all_alongside_an_activation_edit() -> None:
    """The non-src group can never mask the fail-closed catch-all.

    Same-fixture positive control: the activation path alone leaves
    ``unmatched_src`` false, the unmapped ``src/**`` path sets it true, and the two
    together still set it true (run-all, every code shard selected).
    """
    router = load_router()

    activation_only = select_gates([ACTIVATION_TRIGGERS[0]], router=router)
    assert activation_only.unmatched_src is False

    unmapped = "src/specify_cli/__unmapped_probe__/thing.py"
    assert select_gates([unmapped], router=router).unmatched_src is True

    combined = select_gates([unmapped, *ACTIVATION_TRIGGERS], router=router)
    assert combined.unmatched_src is True
    assert combined.selected_code_shards == router.code_shard_jobs


# ---------------------------------------------------------------------------
# FR-004 / FR-005 — the ledger's kernel floor and its reader
# ---------------------------------------------------------------------------
def test_kernel_ledger_floor_selects_the_charter_module() -> None:
    """The floor's readers live in ``tests/charter/activation/**`` (the charter module)."""
    selected = select_modules([LEDGER_FLOOR])

    assert CHARTER_MODULE in selected, f"{LEDGER_FLOOR} does not select the {CHARTER_MODULE!r} module"
    # Ratchet, not a widening: the pre-#6336 selection must survive untouched.
    assert {"kernel", "core_misc", "unit"} <= selected
    assert selected == frozenset({"charter", "core_misc", "kernel", "unit"})


def test_activation_ledger_reader_stays_selected() -> None:
    """``src/charter/activation/**`` already routes to charter; the pin keeps it that way."""
    assert select_modules([LEDGER_READER]) == frozenset({CHARTER_MODULE})


def test_the_ledger_floor_is_a_charter_group_root_and_is_transcribed_verbatim() -> None:
    """The floor joins the ``charter`` scrub roots, and both transcriptions agree.

    The router filter and the module registry both consume the scrub ``charter``
    row verbatim; this pins the row itself, and leaves the two consumers to their
    existing guards (``test_ci_router_transcription_guards`` /
    ``test_module_shard_registry``).
    """
    roots = _scrub_roots(CHARTER_MODULE)

    assert LEDGER_FLOOR in roots
    assert tuple(load_router().filters[CHARTER_MODULE]) == tuple(roots)


# ---------------------------------------------------------------------------
# FR-007 / NFR-001 — no routing blast radius for diffs that cannot be affected
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path",
    [
        "docs/architecture/status-model.md",
        "packs/built-in.source.yaml",
        "src/specify_cli/review/verdict.py",
        ".kittify/glossaries/_global.glossary.yaml",
    ],
)
def test_unrelated_diffs_keep_their_selection(path: str) -> None:
    """The new group adds no module selection unless one of its own globs matched.

    Compared against the same router with this mission's group stripped, so the pin
    freezes *this mission's* delta and never the unrelated fan-out sets (another
    mission adding a consumer of the built-in pack must not red this file).
    """
    router = load_router()
    before_6336 = _router_without({ACTIVATION_GROUP: router.filters[ACTIVATION_GROUP]})

    assert ACTIVATION_GROUP not in select_gates([path], router=router).matched_groups
    assert select_modules([path], router=router) == select_modules([path], router=before_6336)


def test_docs_only_still_selects_zero_modules() -> None:
    """NFR-002 of the router contract: a docs-only diff stays free of code shards."""
    assert select_modules(["docs/architecture/status-model.md"]) == frozenset()


def test_activation_and_other_group_in_one_diff_selects_the_union() -> None:
    """Multi-group diffs stay additive — never narrowed to one group."""
    selected = select_modules([ACTIVATION_TRIGGERS[0], "src/specify_cli/review/verdict.py"])

    assert selected == frozenset({"charter", "review"})
