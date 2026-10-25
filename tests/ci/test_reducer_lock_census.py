"""The ``reducer_lock`` fan-out is derived from a ``spec_kitty_events`` import census (#6605).

``spec-kitty-events`` ships reducer changes in patch releases, so a ``uv.lock``-only bump must run
every module whose code or tests import it. The 10.4.0, 10.4.2 and 10.4.6 bumps went red on ``main``
in lanes the bump PR never selected (#5195, #6058, #6094, #6238). ``gate_selection`` now derives the
fan-out from the importers themselves; these tests pin that:

* every ``src/**`` importer is routed: a registry module owns it, or a reasoned
  ``REDUCER_LOCK_UNOWNED_IMPORTERS`` entry names the modules that test it;
* the second census level (``src/**`` readers of the CLI reducer) routes the modules that consume a
  reducer change only through it (consolidation, lanes, upgrade);
* a ``tests/**`` importer no module owns sits in a tree the registry records as out of matrix;
* the hand table carries no stale entry;
* the census is non-vacuous and fails closed (a seeded unowned importer is reported, an unparsable
  file raises);
* a lock-only diff selects every derived module and nothing run-all;
* the per-PR ``tests (events consumers)`` router job runs the out-of-matrix events consumers on a
  ``reducer_lock`` match (operator ruling 2026-10-25);
* the nightly ``events-latest`` lane (operator ruling 2026-10-22) runs every census test file
  against the newest spec-kitty-events the range allows, from a lock it never commits.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest
import yaml

from scripts.ci.gate_selection import (
    DEFAULT_REGISTRY_PATH,
    DEPENDENCY_MODULE_FANOUT,
    DEPENDENCY_GROUPS,
    EVENTS_CONSUMER_PR_PATHS,
    EVENTS_LATEST_EXCLUDED,
    EVENTS_LATEST_LANE_PATHS,
    REDUCER_LOCK_UNOWNED_IMPORTERS,
    _EVENTS_UNOWNED_CONSUMER_DIRS,
    ReducerLockCensus,
    _modules_for_test_paths,
    derive_reducer_lock_fanout,
    events_importers,
    events_latest_lane_paths,
    load_router,
    select_modules,
)

pytestmark = pytest.mark.fast

_REGISTRY = yaml.safe_load(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
_REPO_ROOT = DEFAULT_REGISTRY_PATH.parents[1]
_MODULES = frozenset(str(row["module"]) for row in _REGISTRY["modules"])


def _registry_owners(path: str) -> frozenset[str]:
    return frozenset(str(row["module"]) for row in _REGISTRY["modules"] if any(fnmatch.fnmatch(path, glob) for glob in row.get("roots") or ()))


@pytest.fixture(scope="module")
def census() -> ReducerLockCensus:
    return derive_reducer_lock_fanout()


def test_every_src_importer_is_routed(census: ReducerLockCensus) -> None:
    assert not census.unrouted, (
        f"{sorted(census.unrouted)} import spec_kitty_events but no registry module owns them and no "
        "REDUCER_LOCK_UNOWNED_IMPORTERS entry in scripts/ci/gate_selection.py covers them, so a uv.lock "
        "bump would run none of their tests. Fix: add the entry with the modules whose per-PR tests exercise "
        "the file and a one-line reason (or give the package a registry row)."
    )
    assert all(census.src_owners.values())


def test_census_is_non_vacuous(census: ReducerLockCensus) -> None:
    # Floors, not exact counts: the known boundary files must be found, and the census must not shrink to a handful.
    assert len(census.src_owners) >= 15, sorted(census.src_owners)
    assert len(census.test_importers) >= 30, census.test_importers
    for path in ("src/specify_cli/status/reducer.py", "src/glossary/events.py", "src/specify_cli/dossier/events.py"):
        assert path in census.src_owners
    # The #6605 problem list: each consumer the old {upgrade, status} set left out is routed now.
    assert {"status", "upgrade", "consolidation", "core_misc", "glossary", "next", "dossier", "lanes"} <= census.modules
    assert census.modules <= _MODULES


def test_unowned_importer_table_has_no_stale_entry(census: ReducerLockCensus) -> None:
    src = list(census.src_owners)
    for key, (modules, reason) in REDUCER_LOCK_UNOWNED_IMPORTERS.items():
        covered = [path for path in src if path == key or (key.endswith("/") and path.startswith(key))]
        assert covered, f"REDUCER_LOCK_UNOWNED_IMPORTERS[{key!r}] covers no spec_kitty_events importer any more; remove it."
        owned = [path for path in covered if _registry_owners(path)]
        assert not owned, f"{owned} now have a registry owner; REDUCER_LOCK_UNOWNED_IMPORTERS[{key!r}] is stale."
        assert modules and modules <= _MODULES, f"REDUCER_LOCK_UNOWNED_IMPORTERS[{key!r}] names non-registry modules {sorted(modules - _MODULES)}"
        assert reason.strip()


def test_reducer_readers_route_the_indirect_consumers(census: ReducerLockCensus) -> None:
    """The modules that consume the reducer only through the CLI (no file of theirs imports the
    package) come from the second census level, not from a hand list."""
    via_reducer = frozenset().union(*census.reducer_owners.values())
    for module in ("consolidation", "lanes", "upgrade"):
        assert module in via_reducer, f"{module!r} reads the CLI reducer but the second census level lost it"
    assert "src/specify_cli/consolidation/reconciliation.py" in census.reducer_owners


def test_unowned_test_importers_are_recorded_out_of_matrix(census: ReducerLockCensus) -> None:
    """A test importer no module owns runs in no per-PR shard on a lock bump; it must sit in a tree the
    registry records under out_of_matrix_test_dirs (each with its own reason and home)."""
    recorded = [d for entry in _REGISTRY["out_of_matrix_test_dirs"] for d in entry["dirs"] if d != "tests"]
    router = load_router()
    for path in census.test_importers:
        if _modules_for_test_paths([path], router=router, registry_path=None, modules=_MODULES):
            continue
        assert any(path.startswith(f"{d}/") for d in recorded), (
            f"{path} imports spec_kitty_events, no module owns it and no out_of_matrix_test_dirs entry records it"
        )


def test_live_fanout_keys_and_floor(census: ReducerLockCensus) -> None:
    assert set(DEPENDENCY_MODULE_FANOUT) == DEPENDENCY_GROUPS
    # agent comes only from a test importer, lanes only from the reducer level: both levels must feed it.
    assert {"agent", "lanes"} <= DEPENDENCY_MODULE_FANOUT["reducer_lock"]


def test_lock_only_change_selects_every_consumer_and_is_not_run_all(census: ReducerLockCensus) -> None:
    """Done-when of #6605: a lock-only events bump selects every consumer module in its own PR."""
    selected = select_modules(["uv.lock"], router=load_router())
    assert census.modules <= selected
    assert selected != _MODULES, "a lock-only diff must stay a fan-out, not a run-all"


def _seed(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_census_detects_imports_and_fails_closed(tmp_path: Path) -> None:
    """Self-mutation: a seeded tree proves what the census counts and that an unowned importer reds."""
    _seed(tmp_path, "src/specify_cli/status/a.py", "from spec_kitty_events.diary import reduce\n")
    _seed(tmp_path, "src/specify_cli/status/b.py", "def f():\n    import spec_kitty_events.status as s\n    return s\n")
    _seed(tmp_path, "src/specify_cli/status/c.py", "import spec_kitty_events_other\nfrom .spec_kitty_events import x\n# spec_kitty_events\n")
    _seed(tmp_path, "src/specify_cli/brand_new_pkg/d.py", "import spec_kitty_events\n")
    _seed(tmp_path, "src/specify_cli/lanes/f.py", "from importlib import import_module\nm = import_module('spec_kitty_events.retrospective')\n")
    _seed(tmp_path, "src/specify_cli/lanes/g.py", "from specify_cli.status import materialize_snapshot\n")
    _seed(tmp_path, "src/specify_cli/lanes/h.py", "from specify_cli.status import Lane\n")
    _seed(tmp_path, "tests/status/test_e.py", "from spec_kitty_events import Event\n")
    (tmp_path / "tests/status/latin1_fixture.py").write_bytes(b"x = '\xe9'\n")  # no marker: never decoded

    assert events_importers(tmp_path) == (
        "src/specify_cli/brand_new_pkg/d.py",
        "src/specify_cli/lanes/f.py",
        "src/specify_cli/status/a.py",
        "src/specify_cli/status/b.py",
        "tests/status/test_e.py",
    )
    seeded = derive_reducer_lock_fanout(repo_root=tmp_path)
    assert seeded.unrouted == ("src/specify_cli/brand_new_pkg/d.py",)
    assert "status" in seeded.src_owners["src/specify_cli/status/a.py"]
    assert "status" in seeded.test_modules
    assert seeded.reducer_owners == {"src/specify_cli/lanes/g.py": frozenset({"lanes"})}

    _seed(tmp_path, "src/specify_cli/status/broken.py", "import spec_kitty_events\ndef (:\n")
    with pytest.raises(ValueError, match="import census"):
        events_importers(tmp_path)


_NIGHTLY = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"


def test_events_latest_lane_paths_cover_every_census_test_file(census: ReducerLockCensus) -> None:
    paths = events_latest_lane_paths()
    assert paths[: len(EVENTS_LATEST_LANE_PATHS)] == EVENTS_LATEST_LANE_PATHS
    # The unowned consumer dirs both lanes share are exactly the registry's `events consumers` entry.
    registry_dirs = next(r["dirs"] for r in _REGISTRY["out_of_matrix_test_dirs"] if "tests/migration" in r["dirs"])
    assert set(registry_dirs) == set(_EVENTS_UNOWNED_CONSUMER_DIRS)
    assert set(_EVENTS_UNOWNED_CONSUMER_DIRS) <= set(EVENTS_CONSUMER_PR_PATHS)
    for path in EVENTS_LATEST_LANE_PATHS:
        assert (_REPO_ROOT / path).exists(), f"events-latest lane path {path} does not exist"
    for path in census.test_importers:
        if path.rsplit("/", 1)[-1].startswith("test_") and path not in EVENTS_LATEST_EXCLUDED:
            assert any(path == p or path.startswith(f"{p}/") for p in paths), f"{path} imports spec_kitty_events but the events-latest lane skips it"
    assert all(p.rsplit("/", 1)[-1].startswith("test_") for p in paths[len(EVENTS_LATEST_LANE_PATHS) :]), "helpers are not test modules"
    assert len(set(paths)) == len(paths)
    assert "tests" not in paths, "the lane is a targeted consumer run, not the whole suite"
    assert not EVENTS_LATEST_EXCLUDED & set(paths)


def test_events_latest_job_resolves_newest_and_never_commits() -> None:
    workflow = yaml.safe_load(_NIGHTLY.read_text(encoding="utf-8"))
    job = workflow["jobs"]["events-latest"]
    runs = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "uv lock --upgrade-package spec-kitty-events" in runs
    assert "uv sync --locked --all-extras" in runs and "--frozen --all-extras" not in runs, "the lane must test the upgraded lock"
    assert "events_latest_lane_paths" in runs
    assert '"${#paths[@]}" -eq 0' in runs, "an empty path list must fail closed, not run the whole suite"
    assert "--suite-key events-latest" in runs
    for forbidden in ("git commit", "git push", "git add"):
        assert forbidden not in runs, f"the throwaway lock must never be committed ({forbidden!r})"
    assert job["permissions"]["contents"] == "read"
    checkout = next(step for step in job["steps"] if "actions/checkout" in str(step.get("uses", "")))
    assert checkout.get("with", {}).get("fetch-depth") == 0, "the corpus-recovery tests git-archive historical SHAs"
    assert "events-latest" in workflow["jobs"]["nightly-summary"]["needs"]


_ROUTER = _REPO_ROOT / ".github" / "workflows" / "ci-router.yml"


def _pytest_paths(run: str) -> list[str]:
    """The ``tests/...`` arguments of the single pytest command in ``run``."""
    command = " ".join(run.replace("\\\n", " ").split())
    return [token for token in command.split() if token.startswith("tests/")]


def test_events_consumers_job_runs_the_out_of_matrix_consumers_on_a_lock_change() -> None:
    """#6605 (operator ruling 2026-10-25): a uv.lock change runs the events consumers no module
    shard owns, in a router job the router gate blocks on."""
    workflow = yaml.safe_load(_ROUTER.read_text(encoding="utf-8"))
    job = workflow["jobs"]["tests-events-consumers"]
    assert job["name"] == "tests (events consumers)"
    assert " ".join(str(job["if"]).split()) == "${{ needs.changes.outputs.reducer_lock == 'true' }}"
    assert "tests-events-consumers" in workflow["jobs"]["router-gate"]["needs"]
    runs = [str(step["run"]) for step in job["steps"] if "pytest" in str(step.get("run", ""))]
    assert len(runs) == 1, "one pytest invocation, so the gate model sees exactly one execution"
    assert tuple(_pytest_paths(runs[0])) == EVENTS_CONSUMER_PR_PATHS
    checkout = next(step for step in job["steps"] if "actions/checkout" in str(step.get("uses", "")))
    assert checkout.get("with", {}).get("fetch-depth") == 0
    # The paths stay out of every module row, so this job is their only per-PR execution.
    claimed = [d for row in _REGISTRY["modules"] for d in row.get("test_dirs") or ()]
    for path in EVENTS_CONSUMER_PR_PATHS:
        assert not any(path == d or path.startswith(f"{d}/") for d in claimed), f"{path} is also claimed by a module row"
