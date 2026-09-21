"""Regression guard for the ``ci`` module wiring (spec-kitty#4386).

``tests/ci`` — the guard suites for ``scripts/ci/`` and the CI workflows it
feeds, including the credential-holding ``sonar-pr`` path — was claimed by no
``.github/ci-module-registry.yml`` row, so no per-PR job ever selected it: the
only lane reaching it was ``ci-nightly.yml``'s scheduled, fail-soft interpreter
sweep. These tests pin the three-part wiring that closed that gap, so it cannot
silently rot back:

1. the registry carries a ``ci`` row claiming ``tests/ci`` — its per-PR
   executor is the ``ci-modules.yml`` module matrix, which runs on every PR
   and fails the PR on a regression in these suites;
2. the scrub (``tests/release/ci_retirement_scrub.json``) carries the matching
   group with the same roots/cov_targets — the registry consumes ``groups[]``
   rows verbatim, so a divergent row is a re-scrub;
3. ``ci-router.yml`` names the CI-infrastructure paths as the ``ci`` filter
   group — a ``scripts/ci``-only or workflow-only diff ROUTES (matches a named
   group) instead of silently matching nothing — while staying OUTSIDE the
   FR-004 fail-closed catch-all (that sensor is contractually unmapped
   ``src/**`` code, ``contracts/router-two-authority.md`` Invariants 1-2) and
   gating no router job (the module matrix is the executor; a router
   ``tests (ci)`` job would double-run the suite per PR, the duplicate class
   ``tests/architectural/test_no_duplicate_suite_execution.py`` exists to
   remove).

This file lives in ``tests/ci`` on purpose: it runs via the ``ci`` module
shard on every PR — including a PR that touches ONLY CI-infrastructure paths,
which is exactly the PR shape whose wiring it guards. The architectural
battery's heavy job is gated on src-backed groups, so it would skip such a PR.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import DEFAULT_ROUTER_PATH, Router, load_router, select_gates, select_modules
from scripts.ci.prose_only import reduced_paths

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_SCRUB_PATH = _REPO_ROOT / "tests" / "release" / "ci_retirement_scrub.json"

_MODULE = "ci"
_ROOTS = ["scripts/ci/**", ".github/workflows/**"]
_TEST_DIRS = ["tests/ci"]


def _registry_rows() -> list[dict[str, Any]]:
    payload = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return list(payload["modules"])


def _ci_row() -> dict[str, Any]:
    rows = [row for row in _registry_rows() if row.get("module") == _MODULE]
    assert len(rows) == 1, f"expected exactly one {_MODULE!r} registry row, found {len(rows)}"
    return rows[0]


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


# ---------------------------------------------------------------------------
# (1) the registry row — tests/ci's per-PR executor
# ---------------------------------------------------------------------------
def test_registry_ci_row_claims_tests_ci() -> None:
    """The `ci` row exists and claims exactly tests/ci as its test directory."""
    row = _ci_row()
    assert list(row["roots"]) == _ROOTS, "the ci row's roots must be the CI-infrastructure paths"
    assert list(row["test_dirs"]) == _TEST_DIRS, "the ci row must claim tests/ci explicitly"
    assert isinstance(row["shard_count"], int) and row["shard_count"] >= 1
    assert list(row["cov_targets"]), "registry rows require a non-empty cov_targets ownership declaration"


def test_registry_ci_row_is_measured_not_guessed() -> None:
    """shard_count is backed by recorded per-test durations for the ci module.

    The registry's own rule (WP08 T042/NFR-005): shard_count comes from greedy
    LPT over the MEASURED per-test durations in ci-shard-timings.json, never
    from file counts. A row with no recorded durations is a guessed count, and
    the three parallel per-module tables must stay in lockstep (a count that
    disagrees with the duration list is stale data -- the defect
    ``scripts/ci/capture_shard_timings.py``'s merge exists to close).
    """
    _ci_row()  # the row must exist; the rest of the wiring is pinned by the other tests
    timings = json.loads((_REPO_ROOT / ".github" / "ci-shard-timings.json").read_text(encoding="utf-8"))
    durations = timings["module_test_durations"][_MODULE]
    assert durations, "no measured per-test durations recorded for the ci module"
    count = timings["module_test_count"][_MODULE]
    assert count == len(durations), "module_test_count disagrees with module_test_durations for the ci module"
    provenance = timings["module_capture_provenance"][_MODULE]
    assert provenance["producer"] == "scripts/ci/capture_shard_timings.py", (
        "the ci module's durations must come from the reproducible capture producer, never a hand-edit"
    )


# ---------------------------------------------------------------------------
# (2) the scrub group — the registry consumes it verbatim
# ---------------------------------------------------------------------------
def test_scrub_carries_the_ci_group_verbatim() -> None:
    """The scrub's ci group matches the registry row's roots/cov_targets."""
    scrub = json.loads(_SCRUB_PATH.read_text(encoding="utf-8"))
    groups = [g for g in scrub["groups"] if g.get("group") == _MODULE]
    assert len(groups) == 1, f"expected exactly one {_MODULE!r} scrub group, found {len(groups)}"
    row = _ci_row()
    assert list(groups[0]["roots"]) == list(row["roots"]), "registry ci row roots diverge from the scrub group (re-scrub)"
    assert list(groups[0]["cov_targets"]) == list(row["cov_targets"]), "registry ci row cov_targets diverge from the scrub group (re-scrub)"


# ---------------------------------------------------------------------------
# (3) the router group — the paths route, and the two deliberate exclusions
# ---------------------------------------------------------------------------
def test_ci_infra_only_diffs_route_to_the_named_group(router: Router) -> None:
    """scripts/ci-only and workflow-only diffs match the named `ci` group.

    Before #4386 these path families matched NO filter group -- a PR rewriting
    a workflow, the script it runs, and the tests guarding both selected zero
    routing groups and zero code shards, so nothing path-visible in the router
    even noticed the change.
    """
    for paths in (
        ["scripts/ci/gate_selection.py"],
        ["scripts/ci/fleet_verdict.py", "scripts/ci/sonar_pr_analysis.py"],
        [".github/workflows/ci-aggregate.yml"],
        [".github/workflows/sonar.yml", "scripts/ci/sonarcloud_branch_review.sh"],
    ):
        selection = select_gates(paths, router=router)
        assert selection.matched_groups == frozenset({_MODULE}), (
            f"a CI-infrastructure diff {paths} must route to the named {_MODULE!r} group, got {sorted(selection.matched_groups)}"
        )
        assert not selection.unmatched_src, "CI-infrastructure paths are not src and must never trip the src catch-all"


def test_ci_group_gates_no_router_job_and_stays_out_of_the_catch_all(router: Router) -> None:
    """The two deliberate exclusions recorded in #4386, pinned.

    * the group is non-src, so it stays out of the FR-004 fail-closed
      ``unmatched`` union (the catch-all is the sensor for unmapped src/**
      CODE; these paths are now named);
    * no ci-router.yml job gates on it — the per-PR executor is the
      ci-modules.yml module matrix, which runs on every PR; a router
      ``tests (ci)`` job would double-run the suite per PR.

    This pin is the other half of the FR-003b exemption: the workflow-coherence
    guard (tests/architectural/test_workflow_coherence.py) exempts the ``ci``
    group from its "every filter group gates a job" rule via
    ``_DELIBERATELY_UNGATED_FILTER_GROUPS`` precisely because THIS test keeps
    the group's routing live and asserted — the exemption is only safe while
    this file pins what the group does instead of gating.
    """
    assert _MODULE not in router.src_backed_groups, "the ci group is CI infrastructure, not src code"
    gated = sorted(job for job, groups in router.job_gates.items() if _MODULE in groups)
    assert not gated, (
        f"ci-router.yml job(s) {gated} gate on the ci group -- the per-PR executor for tests/ci is the "
        "ci-modules.yml module matrix (it runs on every PR); a router job would double-run the suite per PR"
    )


def test_ci_infra_diff_alongside_src_change_keeps_the_src_routing(router: Router) -> None:
    """A mixed CI-infra + src diff selects both families' routing unchanged."""
    selection = select_gates(["scripts/ci/gate_selection.py", "src/specify_cli/merge/executor.py"], router=router)
    assert selection.matched_groups == frozenset({"ci", "merge"})
    assert "tests-merge" in selection.selected_code_shards
    assert not selection.unmatched_src


# ---------------------------------------------------------------------------
# (4) WP02 (mission ci-prose-only-downroute-01M31T5S): the prose-only
# down-route wiring in BOTH ci-modules.yml (path-list reduction ->
# select_modules) and ci-router.yml (the `prose-scan` job's output gating
# architectural-heavy / the code shards / tests-docs). `scripts/ci/
# gate_selection.py` is never touched or imported from `prose_only.py`
# (FR-007) -- these tests exercise the CALLERS' wiring, not the authority.
# ---------------------------------------------------------------------------

_PROSE_ONLY_BASE_SRC = '"""Old docstring, no code."""\n\n\ndef f(x):\n    return x + 1\n'
_PROSE_ONLY_HEAD_SRC = '"""New docstring, still no code change."""\n\n\ndef f(x):\n    return x + 1\n'
_REAL_CODE_BASE_SRC = "def g(x=1):\n    return x\n"
_REAL_CODE_HEAD_SRC = "def g(x=2):\n    return x\n"


def _fixed_blob_getter(blobs: dict[str, tuple[str | None, str | None]]) -> Any:
    """A `blob_getter` closed over a fixed base/head-source table (no git IO)."""

    def _get(path: str) -> tuple[str | None, str | None]:
        return blobs[path]

    return _get


def test_reduced_paths_drops_a_proven_prose_only_py_and_empties_select_modules(router: Router) -> None:
    """T009: a diff confined to one proven prose-only `.py` reduces to an
    empty path list, so `select_modules` (the untouched authority) selects
    NOTHING -- the ci-modules.yml matrix has no leaf to materialize."""
    path = "src/specify_cli/cli/help_text.py"
    blobs = {path: (_PROSE_ONLY_BASE_SRC, _PROSE_ONLY_HEAD_SRC)}
    reduced = reduced_paths([path], _fixed_blob_getter(blobs))
    assert reduced == []
    assert select_modules(reduced, router=router) == frozenset()


def test_reduced_paths_keeps_a_mixed_diff_unreduced(router: Router) -> None:
    """T009: a mixed diff (a proven prose-only `.py` alongside a real code
    change) is NOT collapsed -- only the proven-prose path is dropped, the
    real code path is kept and still selects its module."""
    prose_path = "src/specify_cli/cli/help_text.py"
    code_path = "src/specify_cli/merge/executor.py"
    blobs = {
        prose_path: (_PROSE_ONLY_BASE_SRC, _PROSE_ONLY_HEAD_SRC),
        code_path: (_REAL_CODE_BASE_SRC, _REAL_CODE_HEAD_SRC),
    }
    reduced = reduced_paths([prose_path, code_path], _fixed_blob_getter(blobs))
    assert reduced == [code_path]
    assert "merge" in select_modules(reduced, router=router)


@pytest.fixture(scope="module")
def router_workflow() -> dict[str, Any]:
    return yaml.safe_load(DEFAULT_ROUTER_PATH.read_text(encoding="utf-8"))


# --- a tiny, from-first-principles GitHub Actions `if:` boolean evaluator --
#
# The golden tests below must not merely grep for the guard text this WP
# wrote; they evaluate the REAL `if:` string under a synthetic `needs`
# context using ordinary boolean semantics (`&&` binds tighter than `||`,
# parentheses group), the same subset ci-router.yml's job gates use
# (`needs.<job>.outputs.<name> == 'true'` / `!= 'true'`).

_COND_RE = re.compile(r"needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_]+)\s*(==|!=)\s*'true'")


def _strip_expr_wrapper(raw: str) -> str:
    text = raw.strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    return text


def _tokenize_gh_if(expr: str) -> list[str]:
    tokens: list[str] = []
    for chunk in re.findall(r"\(|\)|&&|\|\||[^()&|]+", expr):
        stripped = chunk.strip()
        if stripped:
            tokens.append(stripped)
    return tokens


class _GhIfEvaluator:
    """Recursive-descent evaluator: `or_expr := and_expr ('||' and_expr)*`,
    `and_expr := atom ('&&' atom)*`, `atom := '(' or_expr ')' | condition`."""

    def __init__(self, tokens: list[str], context: dict[str, bool]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._context = context

    def evaluate(self) -> bool:
        value = self._or_expr()
        assert self._pos == len(self._tokens), f"unconsumed if: tokens: {self._tokens[self._pos :]!r}"
        return value

    def _or_expr(self) -> bool:
        value = self._and_expr()
        while self._peek() == "||":
            self._advance()
            value = self._and_expr() or value
        return value

    def _and_expr(self) -> bool:
        value = self._atom()
        while self._peek() == "&&":
            self._advance()
            value = self._atom() and value
        return value

    def _atom(self) -> bool:
        token = self._peek()
        if token == "(":
            self._advance()
            value = self._or_expr()
            assert self._peek() == ")", f"unbalanced parens in if: near {self._tokens[self._pos :]!r}"
            self._advance()
            return value
        assert token is not None, "ran out of if: tokens"
        self._advance()
        return self._eval_condition(token)

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _advance(self) -> None:
        self._pos += 1

    def _eval_condition(self, text: str) -> bool:
        match = _COND_RE.fullmatch(text.strip())
        assert match, f"unmodeled if: condition fragment: {text!r}"
        job, name, op = match.group(1), match.group(2), match.group(3)
        key = f"{job}.{name}"
        assert key in self._context, f"golden test context does not model {key!r}"
        value = self._context[key]
        return value if op == "==" else not value


def _eval_gh_if(raw_if: str, context: dict[str, bool]) -> bool:
    tokens = _tokenize_gh_if(_strip_expr_wrapper(raw_if))
    return _GhIfEvaluator(tokens, context).evaluate()


_ALWAYS_ON_JOB_NAMES = (
    "ruff",
    "commit-msg",
    "markdownlint",
    "uv-lock",
    "import-linter",
    "regen-check",
    "terminology",
    "layer-rules",
    "archive-freeze",
)

_CODE_SHARD_JOB_NAMES = ("tests-merge", "tests-status", "tests-cli")

_BASE_CONTEXT_ALL_FALSE: dict[str, bool] = {
    "changes.merge": False,
    "changes.auth": False,
    "changes.missions": False,
    "changes.post_merge": False,
    "changes.release": False,
    "changes.status": False,
    "changes.review": False,
    "changes.next": False,
    "changes.lanes": False,
    "changes.dashboard": False,
    "changes.upgrade": False,
    "changes.cli": False,
    "changes.charter": False,
    "changes.agent": False,
    "changes.kernel": False,
    "changes.glossary": False,
    "changes.execution_context": False,
    "changes.core_misc": False,
    "changes.unit": False,
    "changes.specify_cli_runtime": False,
    "changes.docs": False,
}


def test_golden_prose_only_pr_down_routes_matrix_arch_battery_and_code_shards(router: Router, router_workflow: dict[str, Any]) -> None:
    """SC-001 golden: a PR whose ONLY changed src is a proven prose-only
    `.py` under `merge`/`status`/`cli` down-routes to: module matrix EMPTY,
    heavy architectural battery SKIPPED, every named code shard SKIPPED,
    `tests-docs` RUNS, always-on lanes unaffected. Each shard's OWN group is
    made true so the guard is proven to SUBTRACT an otherwise-selected job,
    not merely agree with an already-off one.
    """
    jobs = router_workflow["jobs"]

    # ci-modules.yml side: the same PR shape reduces to an empty path list.
    prose_path = "src/specify_cli/cli/help_text.py"
    blobs = {prose_path: (_PROSE_ONLY_BASE_SRC, _PROSE_ONLY_HEAD_SRC)}
    reduced = reduced_paths([prose_path], _fixed_blob_getter(blobs))
    assert reduced == []
    assert select_modules(reduced, router=router) == frozenset()

    # ci-router.yml side: evaluate the REAL if: strings under a synthetic
    # context where merge/status/cli are all lit (as a multi-group
    # prose-only diff would) and prose_only is proven true.
    context = dict(_BASE_CONTEXT_ALL_FALSE)
    context["changes.merge"] = True
    context["changes.status"] = True
    context["changes.cli"] = True
    context["prose-scan.prose_only"] = True

    assert jobs["architectural-heavy"]["needs"] == ["changes", "prose-scan"]
    assert _eval_gh_if(jobs["architectural-heavy"]["if"], context) is False

    for shard in _CODE_SHARD_JOB_NAMES:
        assert jobs[shard]["needs"] == ["changes", "prose-scan"]
        assert _eval_gh_if(jobs[shard]["if"], context) is False

    assert jobs["tests-docs"]["needs"] == ["changes", "prose-scan"]
    assert _eval_gh_if(jobs["tests-docs"]["if"], context) is True

    for always_on in _ALWAYS_ON_JOB_NAMES:
        assert jobs[always_on].get("if") in (None, ""), f"{always_on} must stay unconditional, unaffected by prose_only"

    assert "prose-scan" in jobs["router-gate"]["needs"]
    assert jobs["router-gate"]["if"] == "${{ always() && !cancelled() }}"

    # Explicitly untouched: tests-corpus, tests-e2e, and the `changes` job's
    # own outputs (no `prose_only` output was added under `changes` -- FR-007
    # / the WP02 correction: `prose-scan` is a separate job, never a step
    # inside `changes`).
    assert jobs["tests-corpus"]["needs"] == ["changes"]
    assert jobs["tests-e2e"]["needs"] == ["changes"]
    assert "prose_only" not in jobs["changes"]["outputs"]


def test_golden_non_prose_pr_lane_set_is_byte_identical_to_today(router_workflow: dict[str, Any]) -> None:
    """SC-002 golden: for an ordinary code PR (`prose_only=false`), every
    guarded job's `if:` evaluates EXACTLY as it did before this WP -- the
    added `&& prose_only != 'true'` / `|| prose_only == 'true'` term is a
    no-op for a non-prose diff.
    """
    jobs = router_workflow["jobs"]
    context = dict(_BASE_CONTEXT_ALL_FALSE)
    context["changes.merge"] = True
    context["prose-scan.prose_only"] = False

    assert _eval_gh_if(jobs["architectural-heavy"]["if"], context) is True
    assert _eval_gh_if(jobs["tests-merge"]["if"], context) is True
    assert _eval_gh_if(jobs["tests-status"]["if"], context) is False
    assert _eval_gh_if(jobs["tests-cli"]["if"], context) is False
    assert _eval_gh_if(jobs["tests-docs"]["if"], context) is False
