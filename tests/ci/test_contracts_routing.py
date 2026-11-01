"""Pin the CI routing of the top-level ``contracts/`` tree (mission mission-status-contract-v1, FR-020; #6915).

One glob, ``contracts/fixtures/**``, joins the router's ``corpus`` filter group so an edit
under ``contracts/`` selects the blocking corpus job (which runs the corpus-marked
contract tests) and nothing else beyond the always-on jobs. Since #6915 only the core-owned
fixtures remain under ``contracts/``; the contract modules and tools are pinned spec-kitty-events
extras. This module pins that
effect from the parsed router, the same authority the tests-selection scripts read.

Out of scope here: the preview tag namespace guard (owned by the contracts workflow tests).
"""

from __future__ import annotations

import ast
import functools
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import load_router, select_gates, select_modules
from scripts.ci.prose_only import prose_only_pr_verdict
from tests.architectural import _gate_coverage as gc
from tests.pinned_service_assets import contract_bundle_dir

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_GLOB = "contracts/fixtures/**"
CONTRACTS_ONLY_PATHS = (
    "contracts/fixtures/fixture_01_single_wp_status_changed.json",
    "contracts/fixtures/fixture_02_mixed_batch.json",
)

_BASE_SOURCE = 'def f() -> int:\n    """Old words."""\n    return 1\n'
_DOCSTRING_ONLY_HEAD = 'def f() -> int:\n    """New words."""\n    return 1\n'
_CODE_HEAD = 'def f() -> int:\n    """Old words."""\n    return 2\n'


def _corpus_gated_jobs() -> frozenset[str]:
    router = load_router()
    return frozenset(job for job, groups in router.job_gates.items() if "corpus" in groups)


def test_contracts_glob_is_in_the_corpus_group_exactly_once() -> None:
    corpus = load_router().filters["corpus"]

    assert corpus.count(CONTRACTS_GLOB) == 1
    assert len(corpus) > 1, "the corpus group still carries its existing globs"


def test_no_other_filter_group_claims_the_contracts_glob() -> None:
    claimed_by = [group for group, globs in load_router().filters.items() if CONTRACTS_GLOB in globs]

    assert claimed_by == ["corpus"]


def test_a_corpus_gated_job_exists_to_receive_the_selection() -> None:
    """Non-vacuity: the selection assertions below compare against a non-empty set."""
    assert _corpus_gated_jobs()


def test_contracts_only_diff_selects_the_corpus_job_and_no_module_shard() -> None:
    router = load_router()

    selection = select_gates(CONTRACTS_ONLY_PATHS, router=router)

    assert selection.matched_groups == {"corpus"}
    assert selection.selected_jobs == router.always_on_jobs | _corpus_gated_jobs()
    assert selection.selected_code_shards == frozenset()
    assert not selection.unmatched_src
    assert select_modules(CONTRACTS_ONLY_PATHS, router=router) == frozenset()


@pytest.mark.parametrize("path", ["kitty-ops/x.jsonl", "kitty-ops/closures.jsonl", "kitty-ops/01ABC.jsonl"])
def test_an_ops_data_only_diff_selects_the_corpus_job(path: str) -> None:
    """The reality check reads the Op files and the closure spine, so a PR that changes only ``kitty-ops/`` runs it."""
    router = load_router()

    selection = select_gates([path], router=router)

    assert selection.matched_groups == {"corpus"}
    assert selection.selected_jobs == router.always_on_jobs | _corpus_gated_jobs()


def test_codeowners_alone_selects_nothing_in_the_router() -> None:
    router = load_router()

    selection = select_gates([".github/CODEOWNERS"], router=router)

    assert selection.matched_groups == frozenset()
    assert selection.selected_jobs == router.always_on_jobs
    assert select_modules([".github/CODEOWNERS"], router=router) == frozenset()


def test_scrub_documentation_copy_equals_the_router_corpus_group() -> None:
    scrub = json.loads((ROOT / "tests" / "release" / "ci_retirement_scrub.json").read_text(encoding="utf-8"))
    (corpus_row,) = [row for row in scrub["non_src_router_groups"] if row["group"] == "corpus"]

    assert sorted(corpus_row["roots"]) == sorted(load_router().filters["corpus"])


def _doc_globs() -> tuple[str, ...]:
    """The glob set the router's prose-scan job passes to the classifier (docs plus corpus)."""
    filters = load_router().filters
    return tuple(filters["docs"]) + tuple(filters["corpus"])


def _getter(head_by_path: dict[str, str]) -> Callable[[str, str], str | None]:
    def blob(path: str, side: str) -> str | None:
        return _BASE_SOURCE if side == "base" else head_by_path[path]

    return blob


def test_contracts_files_plus_a_docstring_only_edit_classify_as_prose_only() -> None:
    """R-11: contracts paths count as corpus, so they no longer block the prose-only down-route."""
    paths = ["contracts/fixtures/fixture_01_single_wp_status_changed.json", "contracts/fixtures/fixture_02_mixed_batch.json", "src/pkg/mod.py"]

    assert prose_only_pr_verdict(paths, _getter({"src/pkg/mod.py": _DOCSTRING_ONLY_HEAD}), _doc_globs()) is True


def test_contracts_files_plus_a_code_edit_do_not_classify_as_prose_only() -> None:
    paths = ["contracts/fixtures/fixture_01_single_wp_status_changed.json", "src/pkg/mod.py"]

    assert prose_only_pr_verdict(paths, _getter({"src/pkg/mod.py": _CODE_HEAD}), _doc_globs()) is False


def test_a_contracts_only_diff_is_not_prose_only_because_it_never_needed_the_down_route() -> None:
    assert prose_only_pr_verdict(list(CONTRACTS_ONLY_PATHS[:2]), _getter({}), _doc_globs()) is False


# -- the one CI home of every corpus-marked tests/contract module (moved from test_contracts_workflows.py, #6915) ----------------
#
# Both router jobs select ``-m "corpus and not windows_ci"``: ``tests (corpus-blocking)`` names its contract modules, and
# ``tests (contract tools)`` runs the rest of the directory (``--ignore`` the former). A corpus-marked module must run in exactly
# one of them, so a new module is never silently unrun and never run twice.

ROUTER_WORKFLOW = ROOT / ".github" / "workflows" / "ci-router.yml"
ROUTER_CORPUS_JOB = "tests-corpus-blocking"
TOOL_TEST_JOB = "tests-contract-tools"
CONTRACT_TESTS_DIR = ROOT / "tests" / "contract"
TOOL_TEST_MARKER = "corpus and not windows_ci"
# The modules the router's corpus job owns: the two that read the committed corpus, plus the example round trip.
ROUTER_CONTRACT_MODULES = frozenset(
    {
        "tests/contract/test_example_round_trip.py",
        "tests/contract/test_mission_status_payloads.py",
        "tests/contract/test_mission_status_reality.py",
    }
)


def _router_jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(ROUTER_WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    return jobs


def _pytest_command_of(job: Mapping[str, Any]) -> str:
    logical = "\n".join(str(step.get("run", "")) for step in job.get("steps", [])).replace("\\\n", " ")
    commands = [line for line in logical.splitlines() if re.search(r"(?<![\w-])pytest(?![\w-])", line)]
    assert len(commands) == 1, f"expected exactly one pytest command, found {commands}"
    return commands[0]


def router_contract_modules() -> frozenset[str]:
    return frozenset(re.findall(r"tests/contract/test_\w+\.py", _pytest_command_of(_router_jobs()[ROUTER_CORPUS_JOB])))


def tool_job_ignores() -> frozenset[str]:
    command = _pytest_command_of(_router_jobs()[TOOL_TEST_JOB])
    assert re.search(r"\stests/contract/?(?=\s)", command), "the contract-tools job must select the whole tests/contract directory"
    return frozenset(re.findall(r"--ignore=(\S+)", command))


def homes_of(module: str, corpus_modules: frozenset[str], router_modules: frozenset[str], ignored: frozenset[str]) -> list[str]:
    """Which router jobs run *module*; *corpus_modules* is the really collected set, so an indirect mark counts too."""
    if module not in corpus_modules:
        return []
    homes = []
    if module in router_modules:
        homes.append("router corpus job")
    if module not in ignored:
        homes.append("router tool-test job")
    return homes


def home_problems(modules: frozenset[str], corpus_modules: frozenset[str], router_modules: frozenset[str], ignored: frozenset[str]) -> list[str]:
    problems = []
    for module in sorted(modules):
        homes = homes_of(module, corpus_modules, router_modules, ignored)
        if module in corpus_modules and len(homes) != 1:
            problems.append(f"{module} is run by {homes or 'nothing'}")
    for name in sorted(ignored | router_modules):
        if name not in modules:
            problems.append(f"{name} is named by a job but is not a tests/contract module")
    return problems


def live_contract_modules() -> frozenset[str]:
    found = frozenset(f"tests/contract/{path.name}" for path in sorted(CONTRACT_TESTS_DIR.glob("test_*.py")))
    assert found, "no tests/contract module was found"
    return found


@functools.cache
def collected_corpus_modules() -> frozenset[str]:
    """The ``tests/contract`` modules that really collect a test under the jobs' marker (``pytest --collect-only``)."""
    probe = gc.Gate(workflow="probe", job="probe", shard=None, paths=["tests/contract"], marker_expr=TOOL_TEST_MARKER)
    nodeids = gc.collect_job_nodeids(probe)
    modules = frozenset(nodeid.split("::", 1)[0] for nodeid in nodeids if nodeid.startswith("tests/contract/"))
    assert modules, "non-vacuity: the corpus marker collected no tests/contract module"
    return modules


def test_the_two_router_jobs_split_the_contract_modules_the_corpus_job_owns() -> None:
    assert router_contract_modules() == ROUTER_CONTRACT_MODULES
    assert tool_job_ignores() == ROUTER_CONTRACT_MODULES


def test_every_corpus_marked_contract_module_has_exactly_one_home() -> None:
    modules, corpus = live_contract_modules(), collected_corpus_modules()
    router, ignored = router_contract_modules(), tool_job_ignores()

    assert corpus <= modules
    assert home_problems(modules, corpus, router, ignored) == []
    # Non-vacuity: both homes really run something.
    assert any(homes_of(name, corpus, router, ignored) == ["router corpus job"] for name in modules)
    assert any(homes_of(name, corpus, router, ignored) == ["router tool-test job"] for name in modules)


def test_planted_unrun_twice_run_and_renamed_modules_are_refused() -> None:
    modules, corpus = live_contract_modules(), collected_corpus_modules()
    router, ignored = router_contract_modules(), tool_job_ignores()
    unrun, twice, gone = "tests/contract/test_planted_unrun.py", "tests/contract/test_planted_twice.py", "tests/contract/test_renamed_away.py"

    assert home_problems(modules | {unrun}, corpus | {unrun}, router, ignored | {unrun}) == [f"{unrun} is run by nothing"]
    assert home_problems(modules | {unrun}, corpus | {unrun}, router, ignored) == [], "control: left alone, the tool-test job runs a new module"
    assert home_problems(modules | {twice}, corpus | {twice}, router | {twice}, ignored) == [f"{twice} is run by ['router corpus job', 'router tool-test job']"]
    assert home_problems(modules, corpus, router, ignored | {gone}) == [f"{gone} is named by a job but is not a tests/contract module"]


# -- the src files the mission-status reader imports or the contract cites route to `tests (contract tools)` --------------------
# (moved from test_contracts_workflows.py, #6915; the contract's x-derived citations are read from the pinned bundle)

_SRC_ROOT = ROOT / "src"
_SRC_PACKAGES = frozenset(entry.name for entry in _SRC_ROOT.iterdir() if entry.is_dir() and not entry.name.startswith((".", "_")))


def _src_files_imported_by_the_mission_status_contract_tests() -> set[str]:
    """The ``src/`` files that the mission-status reference reader and its tests import (``tests/contract/*mission_status*.py``)."""
    imported: set[str] = set()
    for module_file in sorted(CONTRACT_TESTS_DIR.glob("*mission_status*.py")):
        for node in ast.walk(ast.parse(module_file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            for name in names:
                if name.split(".")[0] not in _SRC_PACKAGES:
                    continue
                base = Path("src", *name.split("."))
                for candidate in (base.with_suffix(".py"), base / "__init__.py"):
                    if (ROOT / candidate).is_file():
                        imported.add(candidate.as_posix())
    return imported


def _src_files_cited_by_the_contract_x_derived_blocks() -> set[str]:
    """The ``src/`` files the bundled mission-status contract cites as provenance (``path: src/...``)."""
    text = (contract_bundle_dir("mission-status") / "openapi.yaml").read_text(encoding="utf-8")
    return set(re.findall(r"path: (src/[A-Za-z0-9_/]+\.py)", text))


def _group_selects(group: list[str], path: str) -> bool:
    """True when a ``**/<tail>`` glob of the group names ``path`` (the group spells src files without their ``src/`` prefix)."""
    return any(glob.startswith("**/") and path.endswith("/" + glob[3:]) for glob in group)


def test_the_contract_tools_group_names_every_src_file_the_mission_status_reader_imports_or_the_contract_cites() -> None:
    group = load_router().filters["contract_tools"]
    imported = _src_files_imported_by_the_mission_status_contract_tests()
    assert len(imported) > 20, f"the import scan found too little: {sorted(imported)}"
    cited = _src_files_cited_by_the_contract_x_derived_blocks()
    assert "src/specify_cli/cli/commands/invocations_cmd.py" in cited, "the provenance scan found nothing it should"
    missing = sorted(path for path in imported | cited if not _group_selects(group, path))
    assert missing == [], f"a change to these src files selects no `tests (contract tools)` run: {missing}"
    assert not _group_selects(group, "src/specify_cli/planted/never_imported.py"), "control: an unnamed file is not selected"


# -- the shape of the two router jobs the one-home rule assumes (moved from test_contracts_workflows.py, #6915) -----------------


def _normalised(condition: str) -> str:
    text = " ".join(str(condition).split())
    return text[3:-2].strip() if text.startswith("${{") and text.endswith("}}") else text


def test_both_router_jobs_select_the_marker_the_one_home_rule_probes_with() -> None:
    jobs = _router_jobs()
    for job in (ROUTER_CORPUS_JOB, TOOL_TEST_JOB):
        assert f'-m "{TOOL_TEST_MARKER}"' in _pytest_command_of(jobs[job]), f"{job} must select -m {TOOL_TEST_MARKER!r}"


def test_the_contract_tools_job_is_a_router_job_gated_on_the_contract_path_groups() -> None:
    job = _router_jobs()[TOOL_TEST_JOB]
    command = _pytest_command_of(job)

    assert job["name"] == "tests (contract tools)"
    assert "uv run --frozen --no-sync pytest" in command
    assert re.search(r"\stests/contract/?(?=\s)", command), "the job must select the whole tests/contract directory"
    needs = job.get("needs", [])
    assert (needs if isinstance(needs, list) else [needs]) == ["changes"]
    assert _normalised(job["if"]) == "needs.changes.outputs.corpus == 'true' || needs.changes.outputs.contract_tools == 'true'"


def test_the_shape_check_sees_a_planted_marker_change() -> None:
    planted = {"steps": [{"run": 'uv run --frozen --no-sync pytest -m "corpus" tests/contract'}]}
    assert f'-m "{TOOL_TEST_MARKER}"' not in _pytest_command_of(planted)


def test_a_module_with_an_unmarked_source_and_a_real_corpus_collection_is_still_judged(tmp_path: Path) -> None:
    """The mark can arrive without the literal text ``pytest.mark.corpus`` in the module: only the real collection sees it."""
    plugin = tmp_path / "indirect_mark.py"
    plugin.write_text('import pytest\nMARKS = [getattr(pytest.mark, "cor" + "pus")]\n', encoding="utf-8")
    planted = tmp_path / "test_indirect.py"
    planted.write_text("import indirect_mark\nimport pytest\n\npytestmark = indirect_mark.MARKS\n\n\ndef test_x() -> None:\n    pass\n", encoding="utf-8")
    assert "pytest.mark.corpus" not in planted.read_text(encoding="utf-8")
    probe = gc.Gate(workflow="probe", job="probe", shard=None, paths=[str(planted)], marker_expr=TOOL_TEST_MARKER)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PYTHONPATH", str(tmp_path))
        collected = gc.collect_job_nodeids(probe)
    assert collected, "the indirectly applied corpus mark must be collected under the jobs' marker"
    name = "tests/contract/test_indirect.py"
    modules, corpus = live_contract_modules() | {name}, collected_corpus_modules() | {name}
    assert home_problems(modules, corpus, router_contract_modules(), tool_job_ignores() | {name}) == [f"{name} is run by nothing"]


# -- the Packs advisory corpus lane deselects only live modules (moved from test_mission_status_routing.py, #6915) ---------------

PACKS_WORKFLOW = ROOT / ".github" / "workflows" / "packs.yml"
PACKS_CORPUS_JOB = "built-in-corpus-suite"


def _packs_contract_deselects(path: Path = PACKS_WORKFLOW) -> list[str]:
    gates = [gate for gate in gc.parse_workflow(path) if gate.job == PACKS_CORPUS_JOB]
    assert len(gates) == 1, "the Packs corpus job runs exactly one pytest command"
    return [entry for entry in gates[0].ignores if entry.startswith("tests/contract/")]


def test_every_contract_module_the_packs_corpus_lane_deselects_exists() -> None:
    deselected = _packs_contract_deselects()
    assert deselected, "non-vacuity: the Packs corpus lane deselects the router-owned contract modules"
    assert [entry for entry in deselected if not (ROOT / entry.split("::", 1)[0]).is_file()] == []


def test_a_planted_stale_deselect_is_seen(tmp_path: Path) -> None:
    text = PACKS_WORKFLOW.read_text(encoding="utf-8")
    token = " --deselect tests/contract/test_mission_status_reality.py"
    assert text.count(token) == 1, "control: the Packs command names the token once"
    planted = tmp_path / "packs.yml"
    planted.write_text(text.replace(token, token + " --deselect tests/contract/test_gone_away.py"), encoding="utf-8")
    assert "tests/contract/test_gone_away.py" in _packs_contract_deselects(planted)
    assert not (ROOT / "tests/contract/test_gone_away.py").is_file()
