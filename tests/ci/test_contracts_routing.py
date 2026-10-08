"""Pin the CI routing of the top-level ``contracts/`` tree (mission mission-status-contract-v1, FR-020).

One glob, ``contracts/**``, joins the router's ``corpus`` filter group so an edit
under ``contracts/`` selects the blocking corpus job (which runs the corpus-marked
contract tests) and nothing else beyond the always-on jobs. This module pins that
effect from the parsed router, the same authority the tests-selection scripts read.

Out of scope here: the preview tag namespace guard (owned by the contracts workflow tests).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.ci.gate_selection import load_router, select_gates, select_modules
from scripts.ci.prose_only import prose_only_pr_verdict

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_GLOB = "contracts/**"
CONTRACTS_ONLY_PATHS = (
    "contracts/README.md",
    "contracts/_shared/schemas/Problem.yaml",
    "contracts/tools/contract_resolver.py",
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
    paths = ["contracts/README.md", "contracts/_shared/schemas/Problem.yaml", "src/pkg/mod.py"]

    assert prose_only_pr_verdict(paths, _getter({"src/pkg/mod.py": _DOCSTRING_ONLY_HEAD}), _doc_globs()) is True


def test_contracts_files_plus_a_code_edit_do_not_classify_as_prose_only() -> None:
    paths = ["contracts/README.md", "src/pkg/mod.py"]

    assert prose_only_pr_verdict(paths, _getter({"src/pkg/mod.py": _CODE_HEAD}), _doc_globs()) is False


def test_a_contracts_only_diff_is_not_prose_only_because_it_never_needed_the_down_route() -> None:
    assert prose_only_pr_verdict(list(CONTRACTS_ONLY_PATHS[:2]), _getter({}), _doc_globs()) is False
