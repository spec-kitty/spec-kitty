"""Architectural guards for the CI path-router two-authority model.

The restored interim ``ci-quality.yml`` husk deliberately still runs on every
pull request with **no** path filter: it is a small five-job producer (the four
blocking producers plus ``quality-gate``) cheap enough to run unconditionally.
It carried a sixth job until mission ``sonar-per-pr-coverage-reuse`` (#4334) —
the non-blocking ``sonarcloud`` reporter reinstated by spec-kitty#3993, which
re-ran the whole fast tier for a coverage report the ``ci-modules`` shards had
already produced. Its retirement is what makes "cheap enough to run
unconditionally" true of this file again; the per-PR Sonar report now lives in
``ci-aggregate.yml``'s ``sonar-pr`` job, which executes no tests. The exact job
set is pinned by ``tests/release/test_release_ci_ownership.py``, not here.
The path→job *routing* lives in its own workflow, ``ci-router.yml`` (mission
``ci-pipeline-reinstatement``, WP07), which reinstates the two-authority model:

1. the dorny ``changes`` filter block (``group → globs[]``, path→group), and
2. the job ``if: needs.changes.outputs.<group>`` gates (group→job).

Everything else — the fail-closed unmatched catch-all, the fast/heavy
architectural split, the docs-only-selects-zero-code-shards property — is
**derived and asserted against** those two hand-authored sources by the tests
below. The assertions parse the *real on-disk* workflow YAML; they do not
re-encode the routing as a second hand-maintained map (that duplication is the
very #2476 hazard the gate-selection authority closes — see
``test_gate_selection_authority.py``).
"""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_QUALITY = _REPO_ROOT / ".github" / "workflows" / "ci-quality.yml"
_CI_ROUTER = _REPO_ROOT / ".github" / "workflows" / "ci-router.yml"


def _load_workflow() -> dict[str, Any]:
    return yaml.safe_load(_CI_QUALITY.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# ci-quality husk contract (unchanged by WP07): the interim producer keeps
# running filter-free on every PR; filters now live in ci-router.yml.
# ---------------------------------------------------------------------------
def test_reduced_ci_quality_runs_without_path_filters_live() -> None:
    workflow = _load_workflow()
    on_section = workflow.get("on") or workflow[True]

    for event in ("pull_request", "push"):
        assert "paths" not in on_section[event]


def test_reduced_ci_quality_uses_stock_runners_live() -> None:
    workflow = _load_workflow()
    text = _CI_QUALITY.read_text(encoding="utf-8")

    assert {job["runs-on"] for job in workflow["jobs"].values()} == {"ubuntu-latest"}
    assert "blacksmith" not in text.lower()
    assert "runner-group" not in text.lower()


# ---------------------------------------------------------------------------
# ci-router.yml two-authority model (WP07). Helpers parse the two hand-authored
# sources straight out of the on-disk workflow.
# ---------------------------------------------------------------------------
def _load_router() -> dict[str, Any]:
    return yaml.safe_load(_CI_ROUTER.read_text(encoding="utf-8"))


def _router_on_section(workflow: dict[str, Any]) -> dict[str, Any]:
    # PyYAML parses the bare ``on:`` key as the boolean ``True``.
    return workflow.get("on") or workflow[True]


def _changes_filters(workflow: dict[str, Any]) -> dict[str, list[str]]:
    """Authority 1: the dorny ``filters:`` block (``group → globs[]``)."""
    changes = workflow["jobs"]["changes"]
    for step in changes["steps"]:
        if "dorny/paths-filter" in str(step.get("uses", "")):
            filters = step["with"]["filters"]
            parsed = yaml.safe_load(filters) if isinstance(filters, str) else filters
            return {group: list(globs) for group, globs in parsed.items()}
    raise AssertionError("changes job has no dorny/paths-filter step")


# The `any_src` filter row is the FR-004 catch-all PROBE (matches any src/**),
# consumed only by the `unmatched` step — never a routing group and never gated
# on a job (contract Invariant 1). It is excluded from the routing-group set.
_PROBE_GROUPS = frozenset({"any_src"})

_GROUP_REF = re.compile(r"needs\.changes\.outputs\.([A-Za-z0-9_]+)")


def _job_group_gates(workflow: dict[str, Any]) -> dict[str, frozenset[str]]:
    """Authority 2: each non-``changes`` job → the groups its ``if:`` references."""
    gates: dict[str, frozenset[str]] = {}
    for name, job in workflow["jobs"].items():
        if name == "changes" or not isinstance(job, dict):
            continue
        condition = job.get("if")
        gates[name] = frozenset(_GROUP_REF.findall(str(condition))) if condition else frozenset()
    return gates


def _src_backed_groups(filters: dict[str, list[str]]) -> set[str]:
    """Routing groups carrying a ``src/`` glob are code-backed; the rest are data.

    The ``any_src`` probe row is excluded — it is the fail-closed sensor, not a
    routing group (contract Invariant 1).
    """
    return {group for group, globs in filters.items() if group not in _PROBE_GROUPS and any(str(g).startswith("src/") for g in globs)}


def _match_groups(paths: list[str], filters: dict[str, list[str]]) -> set[str]:
    hit: set[str] = set()
    for group, globs in filters.items():
        for pattern in globs:
            if any(fnmatch.fnmatch(path, str(pattern)) for path in paths):
                hit.add(group)
                break
    return hit


def _selected_code_shards(paths: list[str], workflow: dict[str, Any]) -> set[str]:
    """Code-shard jobs a changed-path set selects, derived from the two authorities."""
    filters = _changes_filters(workflow)
    matched = _match_groups(paths, filters)
    src = _src_backed_groups(filters)
    return {job for job, groups in _job_group_gates(workflow).items() if groups and (groups & src) and (groups & matched)}


def test_ci_router_workflow_exists() -> None:
    assert _CI_ROUTER.exists(), "ci-router.yml must exist: WP07 reinstates the path→job router as its own workflow (the two-authority model)."


def test_ci_router_declares_workflow_dispatch_and_mode_input() -> None:
    workflow = _load_router()
    on_section = _router_on_section(workflow)
    assert "workflow_dispatch" in on_section
    dispatch = on_section["workflow_dispatch"] or {}
    assert "mode" in (dispatch.get("inputs") or {}), "router must expose a `mode` input (FR-018/FR-019)"
    # The router must actually honor the mode input, not merely declare it.
    assert "inputs.mode" in _CI_ROUTER.read_text(encoding="utf-8")


def test_ci_router_dorny_paths_filter_is_sha_pinned() -> None:
    workflow = _load_router()
    uses = [str(step.get("uses")) for step in workflow["jobs"]["changes"]["steps"] if "dorny/paths-filter" in str(step.get("uses", ""))]
    assert uses, "changes job must use dorny/paths-filter (SO#6: reuse, do not hand-roll)"
    for ref in uses:
        assert re.fullmatch(r"dorny/paths-filter@[0-9a-f]{40}", ref.split()[0]), f"dorny/paths-filter must be SHA-pinned (DIR-051), got: {ref}"


def test_ci_router_two_authority_every_src_group_is_job_gated() -> None:
    """Derived-surface consistency: no src-backed filter group is zero-gated."""
    workflow = _load_router()
    filters = _changes_filters(workflow)
    src = _src_backed_groups(filters)
    referenced = set().union(*_job_group_gates(workflow).values()) if workflow["jobs"] else set()
    zero_gated = src - referenced
    assert not zero_gated, f"src-backed filter groups referenced by no job if: {sorted(zero_gated)}"


def test_ci_router_docs_only_selects_zero_code_shards() -> None:
    """NFR-002: a docs-only diff selects 0 code shards — objective, not eyeballed."""
    workflow = _load_router()
    assert _selected_code_shards(["docs/architecture/status-model.md"], workflow) == set()


def test_ci_router_unmatched_src_forces_run_all_not_silent_skip() -> None:
    """FR-004 fail-closed: an unmapped src/** change trips the loud catch-all."""
    workflow = _load_router()
    changes = workflow["jobs"]["changes"]
    text = _CI_ROUTER.read_text(encoding="utf-8")

    # There is an `unmatched` step that emits a LOUD alarm, never a silent skip.
    assert "unmatched" in changes["outputs"]
    assert "::warning::" in text and "unmatched=true" in text

    # A src path in no named group must match no src-backed group (→ trips unmatched).
    filters = _changes_filters(workflow)
    unmapped = ["src/specify_cli/__wp07_unmapped_probe__/thing.py"]
    assert not (_match_groups(unmapped, filters) & _src_backed_groups(filters))


def test_ci_router_fast_arch_gates_are_always_on_without_filter_group() -> None:
    """FR-008/NFR-002: terminology + layer-rule run unconditionally, no filter group."""
    workflow = _load_router()
    gates = _job_group_gates(workflow)
    for fast in ("terminology", "layer-rules"):
        assert fast in gates, f"fast always-on arch gate `{fast}` missing from router"
        assert gates[fast] == frozenset(), f"`{fast}` must carry no filter group (always-on)"


def test_ci_router_heavy_arch_battery_is_code_scoped() -> None:
    """FR-008/NFR-002: the heavy battery is code-scoped, so a docs-only PR skips it."""
    workflow = _load_router()
    gates = _job_group_gates(workflow)
    assert "architectural-heavy" in gates, "heavy architectural battery job missing"
    src = _src_backed_groups(_changes_filters(workflow))
    assert gates["architectural-heavy"] & src, "heavy battery must gate on src-backed groups"
    # Objective docs-only check: the heavy battery is not among the selected code shards.
    assert "architectural-heavy" not in _selected_code_shards(["docs/x.md"], workflow)


# ---------------------------------------------------------------------------
# Quarantine-owner discovery (orthogonal guard, retained): the owner-manifest
# check must discover every direct quarantine marker.
# ---------------------------------------------------------------------------
def _is_direct_pytest_quarantine_marker(node: ast.AST) -> bool:
    """Return whether *node* is the canonical ``pytest.mark.quarantine`` chain."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "quarantine"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


def _discover_quarantine_owner_paths(tests_root: Path) -> tuple[str, ...]:
    """Find test files that directly use the canonical quarantine marker."""
    repository_root = tests_root.parent
    owners: list[str] = []
    for test_path in sorted(tests_root.rglob("*.py")):
        tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
        if any(_is_direct_pytest_quarantine_marker(node) for node in ast.walk(tree)):
            owners.append(test_path.relative_to(repository_root).as_posix())
    return tuple(owners)


def test_quarantine_marker_discovery_finds_module_and_function_markers(
    tmp_path: Path,
) -> None:
    """The owner-manifest guard must discover every direct quarantine marker."""
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    (tests_root / "test_module_marker.py").write_text(
        "import pytest\n\npytestmark = [pytest.mark.quarantine]\n",
        encoding="utf-8",
    )
    (tests_root / "test_function_marker.py").write_text(
        "import pytest\n\n@pytest.mark.quarantine\ndef test_flake():\n    pass\n",
        encoding="utf-8",
    )
    (tests_root / "test_unmarked.py").write_text(
        "def test_stable():\n    pass\n",
        encoding="utf-8",
    )

    assert _discover_quarantine_owner_paths(tests_root) == (
        "tests/test_function_marker.py",
        "tests/test_module_marker.py",
    )


# T021 (mission review-cycle-verdict-seam-rebuild-01KZ2W7W, WP05): a shard job
# must not condition its own execution on a predecessor's `.result` — it
# should still run and report its own outcome regardless of whether the
# predecessor passed or failed. This regex catches both classes of gate this
# WP removed: `needs.<job>.result != 'failure'` (Class 1, e.g. a coverage
# shard gated on kernel-tests/fast-tests-status) and `needs.<job>.result ==
# 'success'` (Class 2, an integration-tests-* job gated on its fast-tests-*
# counterpart).
_RESULT_GATE_PATTERN = re.compile(r"needs\.[\w-]+\.result\s*(?:!=\s*'failure'|==\s*'success')")

# Single named, justified exception (see the DoD in
# kitty-specs/review-cycle-verdict-seam-rebuild-01KZ2W7W/tasks/WP05-ci-shard-independence.md):
# ``consumer-compatibility``'s ``needs.build-wheel.result == 'success'`` gate
# is a release-packaging aggregator dependency (a wheel it consumes), not a
# coverage-shard result-gate the way the removed edges were — build-wheel
# produces the artifact consumer-compatibility installs, so gating on its
# result is a genuine "don't bother installing a wheel that was never built"
# check, not the redundant "predecessor's test outcome shouldn't block my own
# report" coupling this test exists to forbid. This is a single named
# constant, not a general allowlist: any job matching the pattern that is NOT
# named here fails the test below, and adding a name here requires the same
# explicit justification as this comment.
_NON_SHARD_AGGREGATOR_EXCEPTIONS = frozenset({"consumer-compatibility"})


def _find_result_gated_jobs(jobs: dict[str, Any]) -> dict[str, str]:
    """Return ``{job_name: if_expr}`` for jobs gating on a predecessor's ``.result``.

    A job's ``if:`` arrives here, post-PyYAML-parse, as one of three shapes: a
    plain string, a folded ``>-`` block scalar (also just a ``str`` once
    parsed), or absent (key missing, defaults to always-run) — all three are
    handled uniformly by coercing to ``str`` and skipping ``None``.
    """
    offending: dict[str, str] = {}
    for job_name, job in jobs.items():
        if job_name in _NON_SHARD_AGGREGATOR_EXCEPTIONS:
            continue
        if_expr = job.get("if") if isinstance(job, dict) else None
        if if_expr is None:
            continue
        if _RESULT_GATE_PATTERN.search(str(if_expr)):
            offending[job_name] = str(if_expr)
    return offending


def test_result_gate_checker_catches_a_reintroduced_gate() -> None:
    """Synthetic-poison proof that ``_find_result_gated_jobs`` reds on a new gate.

    Permanent regression proof for T021: constructs a minimal synthetic
    ``jobs`` mapping containing a deliberately (re)introduced Class 1 style
    gate (``!= 'failure'``, folded ``if: >-`` block shape) and a Class 2 style
    gate (``== 'success'``), alongside an ungated job and a job with no ``if:``
    key at all, and confirms the checker flags exactly the two poisoned jobs.
    This is what proves the checker actually catches the regression it exists
    to prevent — not merely that it currently passes against an
    already-fixed workflow.
    """
    poisoned_jobs = {
        "fast-tests-example": {
            "if": ("always()\n&& (needs.changes.outputs.example == 'true' || github.event_name == 'push')\n&& needs.fast-tests-status.result != 'failure'\n"),
        },
        "integration-tests-example": {
            "if": ("always()\n&& (needs.changes.outputs.example == 'true' || github.event_name == 'push')\n&& needs.fast-tests-example.result == 'success'\n"),
        },
        "clean-job": {
            "if": "always() && (needs.changes.outputs.example == 'true' || github.event_name == 'push')",
        },
        "no-if-job": {},
        "consumer-compatibility": {
            "if": "always() && needs.changes.outputs.release == 'true' && needs.build-wheel.result == 'success'",
        },
    }
    offending = _find_result_gated_jobs(poisoned_jobs)
    assert set(offending) == {"fast-tests-example", "integration-tests-example"}
