"""The single gate-selection authority (FR-016 / #2476) — consistency, singularity, floor.

``scripts/ci/gate_selection.py`` is the ONE importable authority that answers
"which shards/gates does a diff select". These guards prove:

* **Consistency** — its answers agree with the two hand-authored routing sources
  (the dorny filter block + the job ``if:`` gates) for representative diffs.
* **Singularity / parses-not-re-encodes** — it reads the *real on-disk* router
  YAML; mutating a temp copy of that YAML changes its answer, proving it PARSES
  rather than carrying a second hand-maintained routing map (the #2476 hazard).
  WP17 (completeness oracle) and WP18 (local pre-PR parity) import this same
  module — there is no second parser.
* **Fail-closed (FR-004 / T039)** — an unmapped ``src/**`` change forces run-all;
  ``docs``/``corpus`` are non-src and excluded from the unmatched loop.
* **Non-vacuity floor** — the parsed model is not empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci.gate_selection import (
    DEFAULT_ROUTER_PATH,
    GateSelection,
    Router,
    load_router,
    select_gates,
    select_modules,
)

pytestmark = pytest.mark.architectural


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


def test_docs_only_diff_selects_zero_code_shards(router: Router) -> None:
    """NFR-002: a docs-only diff selects no code shards."""
    selection = select_gates(["docs/architecture/status-model.md"], router=router)
    assert selection.selected_code_shards == frozenset()
    assert not selection.unmatched_src


def test_corpus_only_diff_selects_zero_code_shards(router: Router) -> None:
    """Non-src corpus data selects no code shards and does not trip unmatched."""
    selection = select_gates(["packs/built-in/missions/foo.md"], router=router)
    assert selection.selected_code_shards == frozenset()
    assert not selection.unmatched_src


def test_src_group_diff_selects_its_shard_and_heavy_arch(router: Router) -> None:
    """A change confined to one src group selects that group's shard + the heavy battery."""
    selection = select_gates(["src/specify_cli/merge/executor.py"], router=router)
    assert selection.matched_groups == frozenset({"merge"})
    assert "tests-merge" in selection.selected_code_shards
    assert "architectural-heavy" in selection.selected_code_shards


def test_unmapped_src_change_forces_run_all_fail_closed(router: Router) -> None:
    """FR-004 / T039: a src/** change matched by no group forces run-all, never a silent skip."""
    selection = select_gates(["src/specify_cli/__unmapped_probe__/thing.py"], router=router)
    assert selection.unmatched_src is True
    # run-all: every code shard is selected, not a quiet zero.
    assert selection.selected_code_shards == router.code_shard_jobs
    assert selection.selected_code_shards


def test_docs_and_corpus_are_excluded_from_the_unmatched_loop(router: Router) -> None:
    """T039: data groups can never trip the fail-closed src catch-all."""
    for data_path in ("docs/x.md", "packs/y.md", "kitty-specs/m/spec.md"):
        assert select_gates([data_path], router=router).unmatched_src is False


def test_full_mode_runs_everything(router: Router) -> None:
    """FR-018/FR-019: full mode forces run-all even for a docs-only path set."""
    selection = select_gates(["docs/x.md"], router=router, mode="full")
    assert selection.selected_code_shards == router.code_shard_jobs


def test_fast_arch_gates_are_always_on_and_selected_even_for_docs(router: Router) -> None:
    """The fast always-on arch gates carry no filter group and always run."""
    assert {"terminology", "layer-rules"} <= router.always_on_jobs
    selection = select_gates(["docs/x.md"], router=router)
    assert {"terminology", "layer-rules"} <= selection.selected_jobs


def test_authority_is_consistent_with_the_two_hand_sources(router: Router) -> None:
    """Every selected code shard's gate references a matched (or run-all) src group.

    This ties the authority's answer back to the two hand-authored sources: a job
    is selected only because its ``if:`` (authority 2) references a group its
    globs (authority 1) matched — never from a private side-table.
    """
    selection = select_gates(["src/specify_cli/status/store.py"], router=router)
    for job in selection.selected_code_shards:
        gate_groups = router.job_gates[job]
        assert gate_groups & (selection.matched_groups | router.src_backed_groups)


def test_authority_parses_the_yaml_not_a_hardcoded_map(tmp_path: Path) -> None:
    """Singularity/anti-#2476: mutating the on-disk router changes the answer.

    If the authority re-encoded a second hand-maintained routing map instead of
    parsing, deleting a group from the YAML would not change its answer. Proving
    the answer tracks the file proves there is one authority: the file, parsed.
    """
    baseline = select_gates(["src/specify_cli/merge/x.py"])
    assert "tests-merge" in baseline.selected_code_shards

    # Remove the whole `merge` filter block from a temp copy → `merge` no longer matches.
    text = DEFAULT_ROUTER_PATH.read_text(encoding="utf-8")
    mutated = text.replace("            merge:\n              - 'src/specify_cli/merge/**'\n", "")
    assert mutated != text, "mutation fixture no longer matches the router — update it"
    router_copy = tmp_path / "ci-router.yml"
    router_copy.write_text(mutated, encoding="utf-8")

    mutated_router = load_router(router_copy)
    after = select_gates(["src/specify_cli/merge/x.py"], router=mutated_router)
    # merge/** now matches only the `any_src` probe → unmatched → run-all,
    # but crucially the `merge` group is no longer among matched groups.
    assert "merge" not in after.matched_groups
    assert after.unmatched_src is True


def test_non_vacuity_floor(router: Router) -> None:
    """The parsed model must be non-empty: real groups, code shards, and data groups.

    A content floor (not a cardinality count): the well-known code groups and the
    non-src data groups must be present, so the authority can never pass vacuously
    against an empty or truncated parse.
    """
    # Representative code groups must be present (content check, not a count).
    assert {"merge", "status", "cli", "charter", "kernel"} <= router.src_backed_groups
    # The non-src data groups must be present and classified as non-code.
    assert {"docs", "corpus"} <= (router.routing_groups - router.src_backed_groups)
    assert router.code_shard_jobs  # at least one code shard is wired


def test_gate_selection_returns_typed_result(router: Router) -> None:
    """The public API returns the documented dataclass shape for WP17/WP18."""
    selection = select_gates(["docs/x.md"], router=router)
    assert isinstance(selection, GateSelection)
    assert isinstance(selection.selected_jobs, frozenset)
    assert isinstance(selection.selected_code_shards, frozenset)


# ---------------------------------------------------------------------------
# select_modules (mission ci-modules-diff-scoping) — the module-matrix twin
# of select_gates, reusing it rather than re-deriving a second map.
# ---------------------------------------------------------------------------
def _registry_modules() -> frozenset[str]:
    from scripts.ci.gate_selection import _registry_module_names

    return _registry_module_names()


def test_select_modules_full_mode_selects_all_registry_modules(router: Router) -> None:
    """FR-018/FR-019: mode="full" selects every module — run-all, never a
    quiet narrowing of the matrix, even for a docs-only diff. The universe is
    the registry inventory (which includes the non-src ``ci`` module,
    spec-kitty#4386), NOT ``src_backed_groups``."""
    selected = select_modules(["docs/x.md"], router=router, mode="full")
    assert selected == _registry_modules()
    assert selected >= router.src_backed_groups  # every src-backed group is a module


def test_select_modules_unmatched_src_forces_all_registry_modules(router: Router) -> None:
    """FR-004 fail-closed: an unmapped src/** change selects every module."""
    selected = select_modules(["src/specify_cli/__unmapped_probe__/thing.py"], router=router)
    assert selected == _registry_modules()


def test_select_modules_selects_the_ci_module_on_ci_infra_change(router: Router) -> None:
    """spec-kitty#4386 regression guard: the ``ci`` module is a registry row
    whose routing group is non-src (``scripts/ci/**`` + ``.github/workflows/**``).
    A CI-infra change must still select it — intersecting against
    ``src_backed_groups`` would silently drop it and skip ``tests/ci``."""
    assert "ci" not in router.src_backed_groups  # it is genuinely non-src
    assert "ci" in select_modules(["scripts/ci/gate_selection.py"], router=router)
    assert "ci" in select_modules([".github/workflows/ci-modules.yml"], router=router)


def test_select_modules_single_src_group_selects_only_that_module(router: Router) -> None:
    """A change confined to one src group selects exactly that module."""
    selected = select_modules(["src/specify_cli/merge/executor.py"], router=router)
    assert selected == frozenset({"merge"})


def test_select_modules_docs_only_selects_zero_modules(router: Router) -> None:
    """NFR-002 twin: a docs-only diff selects no module-registry rows."""
    selected = select_modules(["docs/architecture/status-model.md"], router=router)
    assert selected == frozenset()


def test_select_modules_multi_group_diff_selects_each_matched_module(router: Router) -> None:
    """A status/** change also selects every OTHER module whose registry roots
    overlap it (core_misc/unit/execution_context all own
    src/specify_cli/status/** too) — select_modules preserves the router's
    real overlapping ownership, never narrows to a single "owning" module."""
    selected = select_modules(
        ["src/specify_cli/merge/executor.py", "src/specify_cli/status/store.py"],
        router=router,
    )
    assert selected == frozenset({"merge", "status", "core_misc", "unit", "execution_context"})


def test_select_modules_returns_frozenset(router: Router) -> None:
    selected = select_modules(["docs/x.md"], router=router)
    assert isinstance(selected, frozenset)


# ---------------------------------------------------------------------------
# spec-kitty#4454 — a tests-only diff must select the SAME module set the
# corresponding src change selects (mirror, never narrow). Before the fix,
# select_modules matched only src/ globs, so a tests/<dir>-only diff selected
# frozenset() and its tests ran in no per-PR shard (a false green). The mapping
# is derived from the registry inventory (test_dirs + canonical root mirror),
# not a hand-authored second map (the #2476 hazard stays closed).
# ---------------------------------------------------------------------------
def test_select_modules_tests_only_change_mirrors_the_src_selection(router: Router) -> None:
    """T006: a diff confined to ``tests/status/**`` selects the status module's
    full group set — identical to the ``src/specify_cli/status/**`` selection,
    not narrowed to a single owning module."""
    tests_only = select_modules(["tests/status/test_store.py"], router=router)
    src_twin = select_modules(["src/specify_cli/status/store.py"], router=router)
    assert tests_only == src_twin
    assert tests_only == frozenset({"status", "core_misc", "execution_context", "unit"})


def test_select_modules_tests_ci_change_selects_the_ci_module(router: Router) -> None:
    """T006: a ``tests/ci/**``-only diff selects the ``ci`` module (previously
    frozenset()), matching the ``scripts/ci/**`` src change — so the tests/ci
    guard suite is actually selected per PR."""
    tests_only = select_modules(["tests/ci/test_ci_module_wiring.py"], router=router)
    assert tests_only == frozenset({"ci"})
    assert tests_only == select_modules(["scripts/ci/gate_selection.py"], router=router)


def test_select_modules_tests_only_diff_is_never_narrower_than_its_src_twin(router: Router) -> None:
    """The mirror property across several representative test trees: a
    tests-only change is never a strict subset of (narrower than) the module
    set its corresponding src change selects."""
    cases = {
        "tests/merge/test_x.py": "src/specify_cli/merge/executor.py",
        "tests/coordination/test_x.py": "src/specify_cli/coordination/x.py",
        "tests/core/test_x.py": "src/specify_cli/core/x.py",
    }
    for test_path, src_path in cases.items():
        src_twin = select_modules([src_path], router=router)
        tests_only = select_modules([test_path], router=router)
        assert src_twin <= tests_only, f"{test_path}: {sorted(tests_only)} narrows the src twin {sorted(src_twin)}"


# ---------------------------------------------------------------------------
# spec-kitty#4454 reachability (renata MINOR-2) — every registry module that
# owns a tests/ tree must be REACHED by a tests-only diff in that tree. The
# canonical-mirror heuristic (`_canonical_test_mirror`) assumes a module's
# tests live at ``tests/<src-leaf>``; a FUTURE module whose test dir differs
# from the mirror AND lacks explicit ``test_dirs`` would silently select
# nothing on a tests-only change -- reintroducing the exact false green #4454
# closes. This guard ties `select_modules` reachability to the registry
# inventory: the module/test-dir set is DERIVED from the registry (explicit
# ``test_dirs`` when present, else the canonical mirror of each ``root``), never
# hand-listed, so such a future module fails here instead of routing nowhere.
# ---------------------------------------------------------------------------
def _module_test_dirs(row: dict[str, object]) -> list[str]:
    """The tests/ directories a registry module owns, derived from the registry.

    Explicit ``test_dirs`` when the row declares them (the registry's own
    authority); otherwise the canonical ``tests/`` mirror of each ``root`` --
    the same deterministic transform ``select_modules`` uses to route a
    tests-only diff back to its owning module.
    """
    from scripts.ci.gate_selection import _canonical_test_mirror

    explicit = row.get("test_dirs")
    if isinstance(explicit, list) and explicit:
        return [str(test_dir) for test_dir in explicit]
    roots = row.get("roots")
    roots_list = roots if isinstance(roots, list) else []
    return [_canonical_test_mirror(str(root)) for root in roots_list]


def test_every_registry_module_test_tree_is_reachable(router: Router) -> None:
    """T-reach: a tests-only diff in each registry module's declared/mirrored
    test tree selects that module (never ``frozenset()``).

    Reachability is derived from the registry inventory, so it fails closed for
    a future module whose test dir does not match the canonical mirror and that
    declares no explicit ``test_dirs`` -- exactly the silent-nothing false green
    #4454 removed. A currently-unreachable module is a REAL finding, surfaced
    here rather than papered over.
    """
    from scripts.ci.gate_selection import _registry_rows

    unreachable: list[str] = []
    for row in _registry_rows():
        module = str(row["module"])
        for test_dir in _module_test_dirs(row):
            probe = f"{test_dir}/test_ci_reachability_probe.py"
            selected = select_modules([probe], router=router)
            if module not in selected:
                unreachable.append(f"{module}: a tests-only diff in {test_dir!r} selected {sorted(selected)} (module not reached)")
    assert not unreachable, "registry module(s) whose test tree routes to no owning module (spec-kitty#4454 false-green vector):\n" + "\n".join(unreachable)
