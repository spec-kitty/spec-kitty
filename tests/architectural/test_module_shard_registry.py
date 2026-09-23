"""Committed module-shard registry gate (FR-006/NFR-001/NFR-005, WP08 T042).

Asserts ``.github/ci-module-registry.yml`` — the single data source for the
per-module CI test matrix (WP09 realizes it as a matrix over a bounded set of
reusable workflows, never one workflow file per module) — is present,
non-vacuous, covers every live ``src/**`` module in the WP05 retirement-scrub
set (:mod:`tests.release.ci_retirement_scrub`) with no gaps and no divergent
re-scrub, and that its ``shard_count`` balancing is *measured* (from the
``--durations`` run recorded in ``.github/ci-shard-timings.json``, run-id
captured) rather than guessed or derived from file counts, with inter-shard
skew held to <=20% (NFR-005).

Also asserts the T043 heavy-pole de-serialization decisions
(``integration-tests-next`` parallelized, the architectural pole always-on
and de-serialized) are encoded in the registry, and the T044 architect HIGH
folds — single-data-source (a new module is a row, not a workflow file) and
the <=20-reusable-workflows-per-caller ceiling — are machine-checked here
rather than left as prose.

Also asserts test-directory coverage (spec-kitty#4369): every test-bearing
directory under ``tests/`` is claimed by exactly one registry row (mirrored
``tests/<module>`` or an explicit ``test_dirs`` entry) or explicitly recorded
in the registry's ``out_of_matrix_test_dirs`` inventory with a reason — a
directory that is neither is silently unrun by every shard.

Both YAML/JSON artefacts are loaded lazily inside each test (never at import
time) so a missing registry reds for the right reason — file absent — never
an ``ImportError`` or a collection-time crash.
"""

from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_TIMINGS_PATH = _REPO_ROOT / ".github" / "ci-shard-timings.json"
_SCRUB_PATH = _REPO_ROOT / "tests" / "release" / "ci_retirement_scrub.json"
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"

_MAX_SKEW = 0.20
_REQUIRED_ROW_FIELDS = ("module", "roots", "cov_targets", "tier", "shard_count")


# ---------------------------------------------------------------------------
# Loading helpers — lazy, in-test only (never at collection time)
# ---------------------------------------------------------------------------
def _load_registry() -> dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        pytest.fail(f"module-shard registry missing: {_REGISTRY_PATH.relative_to(_REPO_ROOT)} (WP08 T042 not yet delivered)")
    import yaml  # local import: keep this gate's collection cost near-zero

    payload = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{_REGISTRY_PATH} did not parse to a mapping"
    return payload


def _load_timings() -> dict[str, Any]:
    if not _TIMINGS_PATH.exists():
        pytest.fail(f"shard-timings artefact missing: {_TIMINGS_PATH.relative_to(_REPO_ROOT)} (WP08 T041 not yet delivered)")
    payload: dict[str, Any] = json.loads(_TIMINGS_PATH.read_text(encoding="utf-8"))
    return payload


def _load_scrub() -> dict[str, Any]:
    if not _SCRUB_PATH.exists():
        pytest.fail(f"retirement-scrub artefact missing: {_SCRUB_PATH.relative_to(_REPO_ROOT)} (WP05 not yet delivered)")
    payload: dict[str, Any] = json.loads(_SCRUB_PATH.read_text(encoding="utf-8"))
    return payload


def _modules(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return list(registry.get("modules", []))


def _scrub_groups(scrub: dict[str, Any]) -> list[dict[str, Any]]:
    return list(scrub.get("groups", []))


def _module_duration_seconds(timings: dict[str, Any], module: str) -> float:
    """Total measured duration (seconds) attributed to *module* in the timings file."""
    per_module = timings.get("module_duration_seconds", {})
    value = per_module.get(module)
    assert value is not None, f"timings file has no measured duration for module {module!r}"
    assert isinstance(value, (int, float)), f"module {module!r} duration is not numeric: {value!r}"
    return float(value)


def _module_test_durations(timings: dict[str, Any], module: str) -> list[float]:
    """The individual measured per-test durations (seconds) for *module*."""
    per_module = timings.get("module_test_durations", {})
    values = per_module.get(module)
    assert values is not None, f"timings file has no per-test durations recorded for module {module!r}"
    assert isinstance(values, list), f"module {module!r} test durations is not a list: {values!r}"
    return [float(v) for v in values]


def _lpt_bin_pack(durations: list[float], n: int) -> list[float]:
    """Greedy LPT (longest-processing-time-first) bin packing into *n* bins.

    Mirrors the algorithm used to derive ``shard_count`` (WP08 T042 generation
    script): always place the next-largest remaining item into the
    currently least-loaded bin. Standard, well-known approximation for
    balanced multiway partitioning.
    """
    bins = [0.0] * n
    for d in sorted(durations, reverse=True):
        i = min(range(n), key=lambda k: bins[k])
        bins[i] += d
    return bins


def _skew_of(bins: list[float]) -> float:
    if not bins or max(bins) <= 0:
        return 0.0
    return (max(bins) - min(bins)) / max(bins)


# ---------------------------------------------------------------------------
# DoD: non-vacuity floor
# ---------------------------------------------------------------------------
def test_registry_present_and_non_vacuous() -> None:
    """The registry exists and declares at least one module row (non-vacuous)."""
    registry = _load_registry()
    modules = _modules(registry)
    assert modules, "module registry declares no modules (vacuous)"


def test_timings_present_and_non_vacuous() -> None:
    """The shard-timings artefact exists and records a real run (non-vacuous)."""
    timings = _load_timings()
    assert timings.get("run_id"), "timings file has no run_id — a real run must be captured (not asserted)"
    assert timings.get("command"), "timings file does not record the pytest command that produced it"
    per_module = timings.get("module_duration_seconds", {})
    assert per_module, "timings file records no per-module durations (vacuous)"
    assert sum(per_module.values()) > 0, "timings file's total measured duration is zero"


# ---------------------------------------------------------------------------
# DoD: covers every live src/** module in the WP05 scrub set — no gaps, no
# retired surfaces, no divergent re-scrub.
# ---------------------------------------------------------------------------
def test_registry_covers_every_scrub_group_no_gaps_no_extras() -> None:
    """Registry module names == the WP05 scrub's kept group names (bijective).

    A missing name is a gap (an un-covered live module); an extra name that
    is not a scrub group cannot be verified against the census-authorized
    scrub and is a smell (either a stale/renamed group or a re-introduced
    retired surface the scrub already excluded).
    """
    registry = _load_registry()
    scrub = _load_scrub()

    registry_names: set[str] = {str(row.get("module")) for row in _modules(registry)}
    scrub_names: set[str] = {str(g.get("group")) for g in _scrub_groups(scrub)}

    missing = scrub_names - registry_names
    extra = registry_names - scrub_names
    assert not missing, f"module registry has gaps — scrub groups not covered: {sorted(missing)}"
    assert not extra, f"module registry declares modules the scrub does not recognize (possible re-scrub / retired-surface leak): {sorted(extra)}"


def test_registry_consumes_scrub_verbatim_no_divergent_rescrub() -> None:
    """Each row's ``roots``/``cov_targets`` equal its scrub group's — no re-scrub.

    T042 explicitly forbids a second, divergent derivation of roots/cov
    targets: the registry must consume WP05's scrub, not recompute it.
    """
    registry = _load_registry()
    scrub = _load_scrub()
    scrub_by_name = {g.get("group"): g for g in _scrub_groups(scrub)}

    problems: list[str] = []
    for row in _modules(registry):
        name = row.get("module")
        scrub_group = scrub_by_name.get(name)
        if scrub_group is None:
            continue  # covered by test_registry_covers_every_scrub_group_no_gaps_no_extras
        if list(row.get("roots", [])) != list(scrub_group.get("roots", [])):
            problems.append(f"module {name!r} roots diverge from the scrub group's roots")
        if list(row.get("cov_targets", [])) != list(scrub_group.get("cov_targets", [])):
            problems.append(f"module {name!r} cov_targets diverge from the scrub group's cov_targets")
    assert not problems, "registry re-derives roots/cov_targets instead of consuming the scrub verbatim:\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# DoD: every row has the required shape
# ---------------------------------------------------------------------------
def test_every_row_has_required_fields() -> None:
    registry = _load_registry()
    problems: list[str] = []
    for row in _modules(registry):
        name = row.get("module", "<unnamed>")
        for field in _REQUIRED_ROW_FIELDS:
            if field not in row:
                problems.append(f"module {name!r} is missing required field {field!r}")
        if "roots" in row and not row["roots"]:
            problems.append(f"module {name!r} declares an empty roots list")
        if "cov_targets" in row and not row["cov_targets"]:
            problems.append(f"module {name!r} declares an empty cov_targets list")
        if "tier" in row and not row["tier"]:
            problems.append(f"module {name!r} declares an empty tier")
    assert not problems, "module registry rows are malformed:\n" + "\n".join(problems)


def test_cov_targets_are_dotted_form() -> None:
    """``cov_targets`` stay dotted (``specify_cli.merge``), never path form (C-005)."""
    registry = _load_registry()
    bad: list[str] = []
    for row in _modules(registry):
        for target in row.get("cov_targets", []):
            if "/" in target or target.startswith("src"):
                bad.append(f"module {row.get('module')!r} cov_target {target!r} is not dotted form")
    assert not bad, "\n".join(bad)


def test_shard_counts_are_positive_integers() -> None:
    registry = _load_registry()
    bad = [
        f"module {row.get('module')!r} has non-positive/non-integer shard_count {row.get('shard_count')!r}"
        for row in _modules(registry)
        if not isinstance(row.get("shard_count"), int) or row.get("shard_count", 0) < 1
    ]
    assert not bad, "\n".join(bad)


# ---------------------------------------------------------------------------
# WP09 landing fold: an optional ``test_dirs`` override for AGGREGATE modules
# (e.g. core_misc, execution_context) whose ``roots`` span several src/**
# trees with no single tests/<module> mirror -- module-tests.yml's shard
# selection step (.github/workflows/module-tests.yml) consumes this list
# verbatim when present, instead of guessing tests/{module}. When declared,
# every entry must be a real, existing tests/ directory -- never an invented
# path that would silently collect zero tests in CI (the exit-64 defect this
# field exists to fix).
# ---------------------------------------------------------------------------
def test_declared_test_dirs_exist_and_are_directories() -> None:
    registry = _load_registry()
    problems: list[str] = []
    for row in _modules(registry):
        name = row.get("module", "<unnamed>")
        test_dirs = row.get("test_dirs")
        if test_dirs is None:
            continue  # optional field -- rows without it fall back to tests/{module}
        assert isinstance(test_dirs, list), f"module {name!r} declares test_dirs but it is not a list: {test_dirs!r}"
        assert test_dirs, f"module {name!r} declares an empty test_dirs list (omit the field instead of an empty override)"
        for entry in test_dirs:
            path = _REPO_ROOT / str(entry)
            if not path.is_dir():
                problems.append(f"module {name!r} test_dirs entry {entry!r} does not exist as a directory ({path})")
    assert not problems, "registry declares test_dirs entries that are not real directories:\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# DoD: shard_count is balanced on MEASURED duration — inter-shard skew <=20%
# (NFR-005). Recomputed independently from the timings file, not trusted from
# the registry's own claim.
# ---------------------------------------------------------------------------
def test_inter_shard_skew_within_twenty_percent() -> None:
    """Recompute EVERY module's within-module shard skew from measured durations.

    Independently re-derives the balance the registry claims: for each row,
    greedy-LPT-pack its module's individual measured per-test durations
    (``module_test_durations`` in the timings file) into ``shard_count`` bins
    and require ``(max_bin - min_bin) / max_bin <= 20%`` (NFR-005). A module
    with ``shard_count == 1`` trivially satisfies this (nothing to balance
    against) — the check has bite precisely for the multi-shard modules the
    duration-target sizing actually splits.
    """
    registry = _load_registry()
    timings = _load_timings()
    modules = _modules(registry)
    assert modules, "no modules to check skew for"

    problems: list[str] = []
    worst_skew = 0.0
    checked_multi_shard = 0
    for row in modules:
        name = row["module"]
        shard_count = row["shard_count"]
        durations = _module_test_durations(timings, name)
        assert durations, f"module {name!r} has no recorded per-test durations"
        bins = _lpt_bin_pack(durations, shard_count)
        skew = _skew_of(bins)
        worst_skew = max(worst_skew, skew)
        if shard_count > 1:
            checked_multi_shard += 1
        if skew > _MAX_SKEW:
            problems.append(f"module {name!r} (shard_count={shard_count}) recomputed skew {skew:.1%} exceeds {_MAX_SKEW:.0%}: bins={bins}")

    assert not problems, "inter-shard skew exceeds the NFR-005 ceiling:\n" + "\n".join(problems)
    assert checked_multi_shard >= 1, (
        "no module needed more than one shard — the duration-target sizing never actually exercised the skew constraint (vacuous coverage of NFR-005)"
    )


# ---------------------------------------------------------------------------
# T041: the timings artefact documents excluded/truncated directories (if any)
# with a reason — never silent.
# ---------------------------------------------------------------------------
def test_timings_excluded_dirs_are_documented() -> None:
    timings = _load_timings()
    excluded = timings.get("excluded", [])
    assert isinstance(excluded, list)
    bad = [e for e in excluded if not (isinstance(e, dict) and e.get("path") and e.get("reason"))]
    assert not bad, f"excluded entries must each carry a path and a reason: {bad}"


# ---------------------------------------------------------------------------
# T043: heavy-pole de-serialization encoded (integration-tests-next
# parallelized; architectural pole always-on + de-serialized, no filter
# group — consistent with WP07's fast/heavy split in ci-router.yml).
# ---------------------------------------------------------------------------
def test_special_tiers_encode_heavy_pole_deserialization() -> None:
    registry = _load_registry()
    special = registry.get("special_tiers", {})
    assert special, "registry declares no special_tiers (T043 de-serialization must be encoded, not left to prose)"

    integration_next = special.get("integration_tests_next")
    assert integration_next is not None, "special_tiers.integration_tests_next is missing"
    assert integration_next.get("parallel_mode") == "-n auto", (
        f"integration-tests-next must be encoded as parallelized ('-n auto'), got {integration_next.get('parallel_mode')!r}"
    )

    architectural = special.get("architectural")
    assert architectural is not None, "special_tiers.architectural is missing"
    assert architectural.get("always_on") is True, "architectural pole must be encoded as always-on (no filter group)"
    assert architectural.get("deserialized") is True, "architectural pole must be encoded as de-serialized"
    assert architectural.get("filter_group") in (None, ""), "the architectural pole must add NO filter group (consistent with WP07's fast/heavy split)"


# ---------------------------------------------------------------------------
# T044(a): the registry is the single data source — adding a module is a
# registry ROW, never a new workflow file.
# ---------------------------------------------------------------------------
def test_registry_rows_never_declare_a_dedicated_workflow_file() -> None:
    """No row may name its own workflow file — that is the ~40-file anti-pattern.

    A module is realized purely as data (roots/cov/tier/shard_count) consumed
    by a bounded matrix; if a row started carrying a ``workflow``/
    ``workflow_file`` key it would signal a regression back toward one
    workflow per module.
    """
    registry = _load_registry()
    bad = [row.get("module") for row in _modules(registry) if "workflow" in row or "workflow_file" in row]
    assert not bad, f"modules declare a dedicated workflow file (anti-pattern — must be matrix-over-registry): {bad}"


# ---------------------------------------------------------------------------
# T044(b): the realization stays within GitHub's 20-reusable-workflows-per-
# caller ceiling — NOT ~40 separate module-*.yml files.
#
# Folds in the intent of the retired
# ``test_module_count_would_breach_ceiling_if_realized_one_file_per_module``,
# which asserted ``assert True`` inside an ``if len(modules) > ceiling:``
# guard — a tautology that passed unconditionally regardless of the actual
# module count, since the branch not taken asserted nothing at all. The
# module count is data-driven (currently 17, below the declared ceiling of
# 20), so asserting "would breach the ceiling" outright would be a false
# claim, not a real bound. What IS a genuine, checkable property is that the
# module set stays large enough for the "no per-module workflow file"
# anti-pattern check below to be worth running at all — below that floor,
# the ceiling could never be at risk regardless of realization strategy, and
# the check would be vacuous for a different reason (too few rows to ever
# fail it).
# ---------------------------------------------------------------------------
def test_reusable_workflow_ceiling_respected() -> None:
    registry = _load_registry()
    ceiling = registry.get("reusable_workflow_ceiling")
    assert isinstance(ceiling, int) and ceiling > 0, "registry must declare a positive integer reusable_workflow_ceiling"
    assert ceiling <= 20, f"declared ceiling {ceiling} exceeds GitHub's 20-reusable-workflows-per-caller limit"

    actual_workflow_count = len(list(_WORKFLOWS_DIR.glob("*.yml")))
    assert actual_workflow_count <= ceiling, (
        f"{actual_workflow_count} workflow files under {_WORKFLOWS_DIR.relative_to(_REPO_ROOT)} exceed the declared ceiling {ceiling}"
    )

    modules = _modules(registry)
    non_vacuity_floor = ceiling // 2
    assert len(modules) > non_vacuity_floor, (
        f"module count ({len(modules)}) has shrunk to <= half the declared ceiling "
        f"({ceiling}) -- the one-file-per-module anti-pattern check below is no longer "
        "meaningful (there are too few modules for a per-module-file realization to ever "
        "threaten the ceiling); revisit this test's premise instead of letting it pass "
        "vacuously"
    )

    per_module_workflow_files = [f"module-{row.get('module')}.yml" for row in modules if (_WORKFLOWS_DIR / f"module-{row.get('module')}.yml").exists()]
    assert not per_module_workflow_files, (
        f"one-workflow-file-per-module anti-pattern detected (breaches the ceiling for any non-trivial module count): {per_module_workflow_files}"
    )


# ---------------------------------------------------------------------------
# spec-kitty#4369: test-directory coverage. Every test-bearing directory
# under tests/ must be claimed by EXACTLY ONE registry row (its
# tests/<module> mirror or an explicit test_dirs entry) or explicitly
# recorded in the registry's out_of_matrix_test_dirs inventory with a
# reason. A directory that is neither is selected by no shard: its tests
# can neither fail a PR nor contribute coverage evidence -- exactly the
# tests/test_dashboard/ defect (its containment suites ran nowhere; the
# gap surfaced only as a confusing diff-cover failure on #4249).
# ---------------------------------------------------------------------------
# pytest's default python_files patterns (pytest.ini does not override
# python_files) -- the collection basis for "a directory that holds tests".
_PYTHON_FILE_PATTERNS = ("test_*.py", "*_test.py")


def test_pytest_ini_does_not_override_python_files_4388() -> None:
    """Anchor for #4388: ``_PYTHON_FILE_PATTERNS`` above is a hardcoded
    restatement of pytest's *default* collection patterns, held together with
    ``pytest.ini`` only by a prose comment. If ``pytest.ini`` ever grew a
    ``python_files`` override, the hardcoded basis this gate's
    test-bearing-directory scan (:func:`_test_bearing_dirs`) relies on would
    silently diverge from what pytest actually collects. Anchor it: either
    ``pytest.ini`` carries no override at all (the status quo), or its
    override equals ``_PYTHON_FILE_PATTERNS`` exactly.

    Non-vacuity is verified manually, not via a committed fixture, per the
    WP01 task note: transiently (uncommitted) add ``python_files =
    check_*.py`` under ``[pytest]`` in the real ``pytest.ini`` and re-run this
    test -- it fails; revert and it passes again. This test only reads
    ``pytest.ini`` and never edits it.
    """
    parser = configparser.ConfigParser()
    read_files = parser.read(_REPO_ROOT / "pytest.ini")
    assert read_files, f"could not read {_REPO_ROOT / 'pytest.ini'}"
    section = parser["pytest"]
    if "python_files" not in section:
        return
    configured = tuple(section["python_files"].split())
    assert configured == _PYTHON_FILE_PATTERNS, (
        f"pytest.ini's python_files override {configured} diverges from the hardcoded "
        f"_PYTHON_FILE_PATTERNS {_PYTHON_FILE_PATTERNS} this gate's test-bearing-directory "
        "scan assumes -- update _PYTHON_FILE_PATTERNS to match pytest.ini"
    )


def _test_bearing_dirs() -> set[str]:
    """Every directory under tests/ that directly holds a collectible test module."""
    tests_root = _REPO_ROOT / "tests"
    dirs: set[str] = set()
    for pattern in _PYTHON_FILE_PATTERNS:
        for path in tests_root.rglob(pattern):
            if path.is_file():
                dirs.add(path.parent.relative_to(_REPO_ROOT).as_posix())
    assert dirs, "no test-bearing directories found under tests/ (scanner is broken, not the tree empty)"
    return dirs


def _effective_test_dir_claims(registry: dict[str, Any]) -> dict[str, list[str]]:
    """dir -> claiming module names, mirroring module-tests.yml's selection step.

    A row's explicit ``test_dirs`` list wins when present; otherwise the row
    claims its mirrored ``tests/<module>`` directory. This is the same
    precedence the shard-selection step in ``.github/workflows/module-tests.yml``
    applies, so what this gate computes as "claimed" is what CI actually runs.
    """
    claims: dict[str, list[str]] = {}
    for row in _modules(registry):
        name = str(row.get("module", ""))
        for entry in row.get("test_dirs") or [f"tests/{name}"]:
            claims.setdefault(str(entry), []).append(name)
    return claims


def _claimants(claims: dict[str, list[str]], test_dir: str) -> list[str]:
    """Modules whose effective test dirs select *test_dir* (pytest runs a
    directory recursively, so a descendant of a claimed dir is claimed too)."""
    return sorted({name for claimed, names in claims.items() if test_dir == claimed or test_dir.startswith(claimed + "/") for name in names})


def _out_of_matrix_dirs(registry: dict[str, Any]) -> set[str]:
    entries = registry.get("out_of_matrix_test_dirs", [])
    assert isinstance(entries, list), "out_of_matrix_test_dirs must be a list of {reason, dirs} entries"
    recorded: set[str] = set()
    for entry in entries:
        assert isinstance(entry, dict), f"out_of_matrix entry is not a mapping: {entry!r}"
        for d in entry.get("dirs", []):
            recorded.add(str(d))
    return recorded


def test_every_test_directory_is_claimed_once_or_recorded_out_of_matrix() -> None:
    """No test-bearing tests/ directory may be silently unrun (spec-kitty#4369).

    Each directory must be claimed by exactly one registry row (two claimants
    double-run its tests in both shards) or carry an explicit out-of-matrix
    record -- never both, never neither.
    """
    registry = _load_registry()
    claims = _effective_test_dir_claims(registry)
    recorded = _out_of_matrix_dirs(registry)

    problems: list[str] = []
    for test_dir in sorted(_test_bearing_dirs()):
        claimants = _claimants(claims, test_dir)
        if len(claimants) > 1:
            problems.append(f"tests/{test_dir} is claimed by more than one registry row ({claimants}) -- every shard would double-run it")
        elif len(claimants) == 1:
            if test_dir in recorded:
                problems.append(f"{test_dir} is claimed by row {claimants[0]!r} AND recorded out-of-matrix (remove one)")
        elif test_dir not in recorded:
            problems.append(
                f"{test_dir} is selected by no registry row and recorded nowhere -- its tests can neither "
                "fail a PR nor contribute coverage (the tests/test_dashboard/ defect, spec-kitty#4369); "
                "claim it in a row or record it in out_of_matrix_test_dirs with a reason"
            )
    assert not problems, "test-directory coverage gaps:\n" + "\n".join(problems)


def test_out_of_matrix_inventory_entries_are_real_directories_with_real_reasons() -> None:
    """The out-of-matrix inventory is alive: entries exist, hold tests, and reason.

    A recorded directory that has vanished (or never held a test module) is
    stale inventory; a placeholder reason is no reason.
    """
    registry = _load_registry()
    entries = registry.get("out_of_matrix_test_dirs")
    assert isinstance(entries, list) and entries, (
        "registry declares no out_of_matrix_test_dirs inventory (spec-kitty#4369: every unclaimed "
        "test directory must be recorded here with a reason, or claimed by a row)"
    )

    universe = _test_bearing_dirs()
    seen: set[str] = set()
    problems: list[str] = []
    for entry in entries:
        reason = entry.get("reason")
        assert isinstance(reason, str) and reason.strip(), f"out_of_matrix entry carries no reason: {entry!r}"
        assert reason.strip().lower() not in {"n/a", "none", "tbd", "todo", "pending"}, f"out_of_matrix reason is a placeholder, not a reason: {reason!r}"
        dirs = entry.get("dirs")
        assert isinstance(dirs, list) and dirs, f"out_of_matrix entry declares no dirs: {entry!r}"
        for d in dirs:
            assert isinstance(d, str) and d, f"out_of_matrix dirs entry is not a path string: {d!r}"
            if d in seen:
                problems.append(f"{d} is recorded out-of-matrix more than once")
            seen.add(d)
            if d not in universe:
                problems.append(f"{d} is recorded out-of-matrix but is not a test-bearing directory on disk (stale inventory)")
    assert not problems, "out-of-matrix inventory problems:\n" + "\n".join(problems)


def test_registry_test_dirs_are_pairwise_non_nested() -> None:
    """No row's effective test dir may contain another row's.

    pytest collects a directory recursively, so a nested pair of claims would
    run the nested directory's tests in BOTH modules' shards -- double wall
    clock and double-counted coverage for the same module set.
    """
    registry = _load_registry()
    claims = _effective_test_dir_claims(registry)
    dirs = sorted(claims)
    nested = [
        f"{ancestor} ({claims[ancestor]}) contains {descendant} ({claims[descendant]})"
        for ancestor in dirs
        for descendant in dirs
        if ancestor != descendant and descendant.startswith(ancestor + "/")
    ]
    assert not nested, "registry test_dirs are nested across rows (double-run):\n" + "\n".join(nested)


# ---------------------------------------------------------------------------
# spec-kitty#4386: the `ci` module row. tests/ci (the guard suites for
# scripts/ci/ and the CI workflows it feeds, including the credential-holding
# sonar-pr path) was previously recorded in out_of_matrix_test_dirs -- claimed
# by no row, its only reach was ci-nightly.yml's scheduled, fail-soft sweep.
# The generic coverage guards above keep it claimed-or-recorded; this targeted
# regression test pins the ROW itself, so the wiring cannot silently rot back
# to an out-of-matrix "reasoned decision" (which the generic guard would
# accept) without a loud red naming #4386.
# ---------------------------------------------------------------------------
def test_ci_module_row_claims_the_ci_guard_suites() -> None:
    """The `ci` row exists with the CI-infrastructure roots and tests/ci dirs.

    The row's per-PR executor is the ci-modules.yml matrix (it runs on every
    PR), so a regression in tests/ci fails the PR that caused it. Its roots
    are deliberately NON-src (CI infrastructure, not product code) -- the
    first such row -- and are mirrored 1:1 as the `ci` filter group in
    ci-router.yml (outside the FR-004 src catch-all, gating no router job; see
    tests/ci/test_ci_module_wiring.py, which runs on CI-infra-only PRs too).
    """
    registry = _load_registry()
    rows = [row for row in _modules(registry) if row.get("module") == "ci"]
    assert len(rows) == 1, "expected exactly one `ci` module row (spec-kitty#4386)"
    row = rows[0]
    assert list(row["roots"]) == ["scripts/ci/**", ".github/workflows/**"], (
        "the ci row's roots must be the CI-infrastructure paths whose regressions tests/ci guards"
    )
    assert list(row.get("test_dirs", [])) == ["tests/ci"], "the ci row must claim tests/ci explicitly"

    recorded = _out_of_matrix_dirs(registry)
    assert "tests/ci" not in recorded, "tests/ci is claimed by the `ci` row -- it must not also be recorded out-of-matrix"
