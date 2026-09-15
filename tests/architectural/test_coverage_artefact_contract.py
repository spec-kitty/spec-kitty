"""Coverage/xunit artefact naming contract + aggregator gate (WP10, FR-007/FR-009/NFR-003).

Contract: ``kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/artefact-naming.md``
(E2, **authoritative**, preserve verbatim per C-005). Consumed by
``.github/workflows/ci-aggregate.yml`` (this WP's authoritative surface) and,
nightly, by ``sonar.yml`` (WP12).

This file asserts, against the ON-DISK workflows (never a duplicated/paraphrased
copy of the naming scheme):

* the producer side (``module-tests.yml``, WP09) emits the dotted ``--cov=<module>``
  form (never the path form) and the ``coverage-<tier>-<module>-shard<N-of-M>.xml`` /
  ``xunit-result-<module>-shard<N-of-M>-<run_id>.xml`` basenames are unique per
  (tier, module, shard) row of the committed registry;
* ``[tool.coverage.run] relative_files = true`` is set in ``pyproject.toml`` (T055 --
  asserted, never regressed; this WP does not edit ``pyproject.toml``);
* the consumer side (``ci-aggregate.yml``, this WP's authoritative surface) downloads
  ``pattern: '*-reports'``, dedups coverage by basename (guarding a silent-drop
  collision rather than ignoring it), runs a diff-cover gate at ``--fail-under=90``
  excluding census-``dead`` surfaces from the denominator, declares
  ``workflow_dispatch`` and honors the ``mode`` input in its own fail-fast/``needs``
  behavior, SHA-pins every action, and implements the stale-artefact fallback (a
  partial re-trigger reuses the most-recent successful run's artefact for any shard
  that did not re-run) -- proven with a REAL executable test, not left as prose.

**Collection-red lazy-load hygiene:** ``ci-aggregate.yml`` does not exist yet on
base. Every workflow/registry load below happens INSIDE the test body (never at
module import time), so this file always *collects* -- a missing file reds a
targeted assertion (``pytest.fail`` with a clear reason), never an import/collection
error.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"
_AGGREGATE_PATH = _WORKFLOWS_DIR / "ci-aggregate.yml"
_MODULE_TESTS_PATH = _WORKFLOWS_DIR / "module-tests.yml"
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"

# A 40-hex-char SHA, optionally followed by a `# vX.Y.Z` comment -- the SHA-pin
# form every other reinstated workflow in this mission already uses (DIR-051 /
# charter "Agent Push Authorization"), never a floating tag (`@v4`, `@main`).
_SHA_PIN_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}(\s*#.*)?$")


# ---------------------------------------------------------------------------
# Loading helpers -- lazy, in-test only (never at collection time)
# ---------------------------------------------------------------------------
def _load_yaml(path: Path, *, what: str) -> dict[str, Any]:
    if not path.exists():
        pytest.fail(f"{what} missing: {path.relative_to(_REPO_ROOT)} (WP10 not yet delivered)")
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _aggregate_text() -> str:
    if not _AGGREGATE_PATH.exists():
        pytest.fail(f"ci-aggregate.yml missing: {_AGGREGATE_PATH.relative_to(_REPO_ROOT)} (WP10 not yet delivered)")
    return _AGGREGATE_PATH.read_text(encoding="utf-8")


def _aggregate_yaml() -> dict[str, Any]:
    return _load_yaml(_AGGREGATE_PATH, what="ci-aggregate.yml")


def _module_tests_text() -> str:
    if not _MODULE_TESTS_PATH.exists():
        pytest.fail(f"module-tests.yml missing: {_MODULE_TESTS_PATH.relative_to(_REPO_ROOT)} (WP09 dependency not present)")
    return _MODULE_TESTS_PATH.read_text(encoding="utf-8")


def _registry() -> dict[str, Any]:
    return _load_yaml(_REGISTRY_PATH, what="ci-module-registry.yml")


def _iter_uses_values(node: Any) -> list[str]:
    """Recursively collect every ``uses:`` string in a parsed workflow mapping."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_iter_uses_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_uses_values(item))
    return found


# ---------------------------------------------------------------------------
# Producer side (module-tests.yml, WP09) -- naming contract preservation (T055)
# ---------------------------------------------------------------------------
def test_module_tests_uses_dotted_cov_form_never_path_form() -> None:
    """``--cov=<module>`` must be dotted (never ``--cov=src/...`` path form).

    The dotted form is what guarantees a cobertura XML with <=1 ``<source>``
    (contract Invariant 3) -- a path-form regression reintroduces multi-source
    ambiguity Sonar cannot resolve (C-005 risk).
    """
    text = _module_tests_text()
    has_dotted_cov = 'cov_args+=("--cov=$target")' in text or re.search(r"--cov=\$\{?target\}?", text)
    assert has_dotted_cov, "module-tests.yml must build --cov from the dotted `cov_target` field"
    # A regression to the path form would emit `--cov=src/...` or `--cov=./...`.
    has_path_form = re.search(r"--cov=[./]*src/", text)
    assert not has_path_form, "module-tests.yml must never emit the path form of --cov (breaks <=1-<source>)"


def test_pyproject_relative_files_true_preserved() -> None:
    """``[tool.coverage.run] relative_files = true`` already exists -- assert it,
    never regress it (this WP does not edit ``pyproject.toml``, per T055 note)."""
    if not _PYPROJECT_PATH.exists():
        pytest.fail("pyproject.toml missing")
    text = _PYPROJECT_PATH.read_text(encoding="utf-8")
    match = re.search(r"\[tool\.coverage\.run\](?P<body>(?:\n(?!\[).*)*)", text)
    assert match is not None, "pyproject.toml must carry a [tool.coverage.run] section"
    assert re.search(r"relative_files\s*=\s*true", match.group("body")), "relative_files must stay true -- guarantees a single cobertura <source> per shard"


def test_coverage_basename_unique_per_registry_row() -> None:
    """The naming template ``coverage-<tier>-<module>-shard<N-of-M>.xml`` yields a
    unique basename per (tier, module, shard) row of the committed registry --
    Invariant 1 (dedup is by basename; a collision silently drops a shard's data)."""
    registry = _registry()
    basenames: list[str] = []
    for row in registry["modules"]:
        tier = row["tier"]
        module = row["module"]
        shard_count = row["shard_count"]
        for idx in range(1, shard_count + 1):
            slug = f"{idx}-of-{shard_count}"
            basenames.append(f"coverage-{tier}-{module}-shard{slug}.xml")
    assert basenames, "registry produced zero shard rows -- non-vacuous check"
    assert len(basenames) == len(set(basenames)), f"coverage basenames are not unique per shard: {sorted([b for b in basenames if basenames.count(b) > 1])}"


# ---------------------------------------------------------------------------
# Consumer side (ci-aggregate.yml, WP10 authoritative surface)
# ---------------------------------------------------------------------------
def test_ci_aggregate_downloads_reports_glob_pattern() -> None:
    """Artifact name ends ``-reports``; consumers glob ``pattern: '*-reports'``
    (contract Invariant 2)."""
    workflow = _aggregate_yaml()
    patterns = [
        step.get("with", {}).get("pattern")
        for job in workflow.get("jobs", {}).values()
        for step in job.get("steps", [])
        if isinstance(step, dict) and "download-artifact" in str(step.get("uses", ""))
    ]
    assert any(pattern and pattern.endswith("-reports") for pattern in patterns), f"ci-aggregate.yml must download with pattern: '*-reports', found {patterns!r}"


def test_ci_aggregate_declares_workflow_dispatch_and_honors_mode() -> None:
    """T052: declare ``workflow_dispatch``; honor the ``mode`` input (PR
    fail-fast/short-circuit vs full run-all/``if: always()``) in THIS
    aggregator's own fail-fast/``needs`` behavior (FR-018/FR-019)."""
    workflow: dict[Any, Any] = _aggregate_yaml()
    # PyYAML 1.1-resolver quirk: a bare `on:` mapping key parses as the bool
    # ``True`` in some configs, so look it up defensively.
    raw_triggers = workflow.get("on")
    if raw_triggers is None:
        raw_triggers = workflow.get(True, {})
    triggers: dict[str, Any] = raw_triggers if isinstance(raw_triggers, dict) else {}
    assert "workflow_dispatch" in triggers, "ci-aggregate.yml must declare workflow_dispatch (SC-010/C-009)"
    dispatch_inputs = (triggers.get("workflow_dispatch") or {}).get("inputs", {}) or {}
    assert "mode" in dispatch_inputs, "workflow_dispatch must expose a `mode` input"

    text = _aggregate_text()
    has_always = "always()" in text
    assert has_always, "full mode's run-all behavior must use `if: always()` on the gate that must run regardless of an upstream shard result"
    honors_mode = re.search(r"inputs\.mode|needs\.[\w-]+\.outputs\.mode", text)
    assert honors_mode, "the aggregator's own fail-fast/needs behavior must reference the resolved mode"


def test_ci_aggregate_completeness_output_is_actually_consumed_downstream() -> None:
    """Review finding: `collect.outputs.complete` must not be a dead signal --
    the diff-cover job must read `needs.collect.outputs.complete` (job-level
    `if:` and/or a step `if:`), not merely compute-and-ignore it."""
    workflow = _aggregate_yaml()
    collect_outputs = workflow["jobs"]["collect"].get("outputs", {})
    assert "complete" in collect_outputs, "collect job must expose an outputs.complete signal"

    diff_cover_job = workflow["jobs"].get("diff-cover", {})
    consumers: list[str] = []
    job_if = diff_cover_job.get("if")
    if job_if and "needs.collect.outputs.complete" in str(job_if):
        consumers.append("job-level if:")
    for step in diff_cover_job.get("steps", []):
        step_if = step.get("if") if isinstance(step, dict) else None
        if step_if and "needs.collect.outputs.complete" in str(step_if):
            consumers.append(f"step {step.get('name')!r} if:")
        step_run = step.get("run") if isinstance(step, dict) else None
        if isinstance(step_run, str) and "needs.collect.outputs.complete" in step_run:
            consumers.append(f"step {step.get('name')!r} run:")
    assert consumers, "needs.collect.outputs.complete must be read somewhere in the diff-cover job -- a computed-but-unconsumed signal is a dead output"


def test_ci_aggregate_empty_selection_skips_coverage_consumers() -> None:
    """A complete zero-module selection emits no coverage artifact, so the
    workflow must gate consumers on an explicit materialized-coverage signal."""
    workflow = _aggregate_yaml()
    collect_outputs = workflow["jobs"]["collect"].get("outputs", {})
    assert "coverage" in collect_outputs
    job_if = str(workflow["jobs"]["diff-cover"].get("if", ""))
    assert "needs.collect.outputs.coverage == 'true'" in job_if


def test_ci_aggregate_diffcover_gate_fails_under_90_excluding_census_dead() -> None:
    """T053: the real PR-blocking diff-cover gate, ``--fail-under=90`` on changed
    critical-path lines, excluding census-``dead`` surfaces from the denominator
    (E3, via the WP02 census oracle) -- distinct from Sonar's informational
    whole-repo new-code gate."""
    text = _aggregate_text()
    assert "diff-cover" in text, "ci-aggregate.yml must invoke diff-cover"
    assert re.search(r"--fail-under[= ]90", text), "diff-cover must be wired at --fail-under=90 (NFR-003)"
    has_census_wiring = "denominator_excluded_surfaces" in text
    assert has_census_wiring, "census-dead exclusion must be wired from the WP02 oracle (_p1_census_oracle), never a hand-rolled list"


def test_ci_aggregate_never_produces_single_merged_coverage_xml() -> None:
    """Contract: 'Produce no single merged coverage.xml -- consumers merge as
    needed (Sonar merges server-side).'"""
    text = _aggregate_text()
    assert not re.search(r"--cov-report=xml:.*\bcoverage\.xml\b", text), "ci-aggregate.yml must not produce a single merged coverage.xml"


def test_ci_aggregate_all_actions_sha_pinned() -> None:
    """DIR-051 / Agent Push Authorization: every `uses:` reference is pinned to a
    40-hex-char commit SHA, never a floating tag."""
    workflow = _aggregate_yaml()
    uses_values = _iter_uses_values(workflow.get("jobs", {}))
    local_reusable = [u for u in uses_values if u.startswith("./")]
    external = [u for u in uses_values if not u.startswith("./")]
    assert external, "ci-aggregate.yml must reference at least one external action"
    for uses in external:
        assert _SHA_PIN_RE.match(uses), f"action not SHA-pinned: {uses!r}"
    assert not local_reusable, "ci-aggregate.yml must consume shard artefacts, never re-invoke module-tests.yml (would re-run tests, violating FR-007)"


def test_ci_aggregate_critical_path_allowlist_uses_live_modularity_ssot_paths() -> None:
    """The immutable Git diff critical-path allowlist must reference the
    CURRENT Modularity SSOT chain (``kernel <- charter <- {glossary, runtime,
    mission_runtime} <- specify_cli``) -- never the retired ``src/doctrine``
    path (absorbed into ``src/charter/offering/`` pre-fork)."""
    text = (_REPO_ROOT / "scripts/ci/aggregate_source.py").read_text()
    assert "src/kernel" in text
    assert "src/charter" in text
    assert "src/doctrine" not in text, "src/doctrine is a retired path (absorbed into src/charter/offering/) -- the critical-path allowlist must not reference it"


# ---------------------------------------------------------------------------
# T054 -- stale-artefact fallback: a REAL executable test of the reconciliation
# logic embedded in ci-aggregate.yml's `collect` job, not prose.
#
# The embedded step is a small, pure, side-effect-free function over two flat
# basename->path mappings (`current`, `previous`) plus the `expected` basename
# set the registry demands. This mirrors the established repo pattern of
# giving CI-embedded algorithms an independently-testable pure-function twin
# (see WP08/WP09's greedy-LPT bin-packing:
# tests/architectural/test_module_shard_registry.py::_lpt_bin_pack vs.
# module-tests.yml's inline re-implementation) -- proving the ALGORITHM the
# workflow embeds is correct, without spinning up real GitHub Actions runs.
# ---------------------------------------------------------------------------
class _ArtefactCollisionError(Exception):
    """Two different shards produced the same coverage basename (never silently dropped)."""


class _MissingShardArtefactError(Exception):
    """A registry-expected basename is absent from both the current and the fallback run."""


def _reconcile_with_stale_fallback(
    current: dict[str, str],
    previous: dict[str, str],
    expected: set[str],
) -> tuple[dict[str, str], set[str]]:
    """Resolve ``expected`` coverage basenames from ``current``, falling back to
    ``previous`` (the most-recent successful run) for any basename missing from
    ``current``.

    Returns ``(resolved, stale_basenames)`` where ``resolved`` maps basename ->
    source path and ``stale_basenames`` is the subset served from ``previous``.
    Raises :class:`_MissingShardArtefactError` if a basename is absent from
    both sources.

    Mirrors the embedded step in ``ci-aggregate.yml``'s ``collect`` job --
    dedup is by basename (a collision would otherwise silently drop a shard's
    data), so a basename appearing twice within ``current`` itself is refused,
    never silently overwritten.
    """
    resolved: dict[str, str] = {}
    stale: set[str] = set()
    missing: list[str] = []
    for basename in sorted(expected):
        if basename in current:
            resolved[basename] = current[basename]
        elif basename in previous:
            resolved[basename] = previous[basename]
            stale.add(basename)
        else:
            missing.append(basename)
    if missing:
        raise _MissingShardArtefactError(f"missing from both current and fallback runs: {missing}")
    return resolved, stale


def test_stale_artefact_fallback_uses_previous_run_for_missing_shard() -> None:
    """A partial re-trigger leaving one shard's coverage stale -> the aggregator
    falls back to the most-recent successful run's artefact for that shard
    (the previously-orphan edge case, now with a home + a real test)."""
    current = {
        "coverage-standard-merge-shard1-of-1.xml": "current/coverage-standard-merge-shard1-of-1.xml",
    }
    previous = {
        "coverage-standard-merge-shard1-of-1.xml": "previous/coverage-standard-merge-shard1-of-1.xml",
        "coverage-standard-missions-shard1-of-1.xml": "previous/coverage-standard-missions-shard1-of-1.xml",
    }
    expected = {"coverage-standard-merge-shard1-of-1.xml", "coverage-standard-missions-shard1-of-1.xml"}

    resolved, stale = _reconcile_with_stale_fallback(current, previous, expected)

    merge_basename = "coverage-standard-merge-shard1-of-1.xml"
    missions_basename = "coverage-standard-missions-shard1-of-1.xml"
    assert resolved[merge_basename] == f"current/{merge_basename}", "a shard present in current must never be shadowed by fallback"
    assert resolved[missions_basename] == f"previous/{missions_basename}", "a shard missing from current must fall back to the last successful run"
    assert stale == {missions_basename}


def test_stale_artefact_fallback_raises_when_shard_missing_from_both_runs() -> None:
    """Neither the current nor the most-recent successful run has the shard --
    this must be reported, never silently treated as complete."""
    with pytest.raises(_MissingShardArtefactError):
        _reconcile_with_stale_fallback(
            current={},
            previous={},
            expected={"coverage-standard-merge-shard1-of-1.xml"},
        )


# ---------------------------------------------------------------------------
# REAL-SCRIPT execution (review finding, WP10 fix; #4360-B extraction): the twin
# above proves the ALGORITHM; the tests below execute the ACTUAL shipped
# ``scripts/ci/reconcile_shards.py`` (extracted from ci-aggregate.yml's inline
# heredoc so it is unit-testable -- the reason it shipped broken) as a
# subprocess against synthetic `current`/`previous`/registry fixtures -- so a
# drift between the twin and the shipped script (e.g. the twin raising on a
# missing-from-both shard while the shipped script silently accepted it) is
# caught here, not only in the twin's own self-consistent tests above. The
# `collect` job wires this exact script (asserted by
# ``test_ci_aggregate_reconcile_step_invokes_shipped_module`` below).
# ---------------------------------------------------------------------------
_RECONCILE_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "reconcile_shards.py"


def _shipped_reconcile_script() -> Path:
    """The ACTUAL shipped reconcile script the aggregate step invokes -- never a
    re-typed copy."""
    if not _RECONCILE_SCRIPT_PATH.exists():
        pytest.fail(f"shipped reconcile script missing: {_RECONCILE_SCRIPT_PATH.relative_to(_REPO_ROOT)} (#4360-B extraction not delivered)")
    return _RECONCILE_SCRIPT_PATH


def test_ci_aggregate_reconcile_step_invokes_shipped_module() -> None:
    """The `collect` job's reconcile step must invoke the extracted, unit-tested
    ``scripts/ci/reconcile_shards.py`` (#4360-B) -- not an inline heredoc. This
    guards the wiring the shipped-script tests below depend on: they run the
    module directly, so a broken `run:` call would otherwise go unnoticed."""
    workflow = _aggregate_yaml()
    reconcile_steps = [
        step
        for job in workflow.get("jobs", {}).values()
        for step in job.get("steps", [])
        if isinstance(step, dict) and "Reconcile shard artefacts" in str(step.get("name", ""))
    ]
    assert reconcile_steps, "ci-aggregate.yml's `collect` job must have a 'Reconcile shard artefacts...' step"
    run_text = str(reconcile_steps[0].get("run", ""))
    assert "scripts/ci/reconcile_shards.py" in run_text, "the reconcile step must invoke the extracted scripts/ci/reconcile_shards.py module (#4360-B)"
    assert "<<'PY'" not in run_text, "the reconcile logic must live in the unit-tested module, never re-inlined as a heredoc"


def _run_reconcile_script(
    tmp_path: Path,
    *,
    current: dict[str, bytes],
    previous: dict[str, bytes],
    registry_rows: list[dict[str, Any]],
    selected: list[str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run the REAL shipped reconcile script in a scratch cwd, returning
    ``(completed_process, github_output_contents)``.

    ``selected`` (mission ci-modules-diff-scoping, Approach C), when given,
    writes ``out/aggregate/selected/selected-modules.json`` -- the diff-scoped
    module set the triggering "CI Modules" run resolved. Omitted (``None``)
    leaves that file absent entirely, matching a legacy/pre-feature run or a
    download failure -- the shipped script's documented fallback ("no
    selection info known" -> every missing shard is fallback-eligible)."""
    workdir = tmp_path / "workdir"
    current_dir = workdir / "out" / "aggregate" / "current"
    previous_dir = workdir / "out" / "aggregate" / "previous"
    github_dir = workdir / "out" / "aggregate" / "source"
    selected_dir = workdir / "out" / "aggregate" / "selected"
    for directory in (current_dir, previous_dir, github_dir):
        directory.mkdir(parents=True, exist_ok=True)
    for name, content in current.items():
        (current_dir / name).write_bytes(content)
    for name, content in previous.items():
        (previous_dir / name).write_bytes(content)
    (github_dir / "ci-module-registry.yml").write_text(yaml.safe_dump({"modules": registry_rows}), encoding="utf-8")
    if selected is not None:
        selected_dir.mkdir(parents=True, exist_ok=True)
        (selected_dir / "selected-modules.json").write_text(json.dumps(selected), encoding="utf-8")

    output_path = tmp_path / "github_output.txt"
    output_path.write_text("", encoding="utf-8")

    env = dict(os.environ)
    env["GITHUB_OUTPUT"] = str(output_path)
    completed = subprocess.run(
        [sys.executable, str(_shipped_reconcile_script())],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed, output_path.read_text(encoding="utf-8")


_MERGE_ROW = {"module": "merge", "tier": "standard", "shard_count": 1}
_MISSIONS_ROW = {"module": "missions", "tier": "standard", "shard_count": 1}
_MERGE_BASENAME = "coverage-standard-merge-shard1-of-1.xml"
_MISSIONS_BASENAME = "coverage-standard-missions-shard1-of-1.xml"


def _parse_github_output(raw: str) -> dict[str, str]:
    """Parse a $GITHUB_OUTPUT file the way GitHub's runner does
    (FileCommandManager): a line `key=value` sets one output; a line
    `key<<DELIM` starts a multi-line value terminated by a bare `DELIM`
    line. Later assignments override earlier ones (dictionary indexer),
    which is exactly why an injected `complete=true` line after a
    `complete=false` would WIN -- the property the delimiter-form write
    and the registry-row validation below must make impossible."""
    outputs: dict[str, str] = {}
    lines = raw.split("\n")
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        heredoc = re.match(r"^(?P<key>[^=]+)<<(?P<delim>.+)$", line)
        if heredoc:
            value_lines: list[str] = []
            idx += 1
            while idx < len(lines) and lines[idx] != heredoc.group("delim"):
                value_lines.append(lines[idx])
                idx += 1
            outputs[heredoc.group("key")] = "\n".join(value_lines)
        elif "=" in line:
            key, _, value = line.partition("=")
            outputs[key] = value
        idx += 1
    return outputs


def test_shipped_reconcile_script_falls_back_to_previous_run_for_missing_shard(tmp_path: Path) -> None:
    """The SHIPPED script (not the twin) must serve a registry-expected shard
    missing from `current` from `previous`, while never letting `previous`
    shadow a shard `current` DOES have."""
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={_MERGE_BASENAME: b"CURRENT-MERGE"},
        previous={_MERGE_BASENAME: b"STALE-MERGE-MUST-NOT-WIN", _MISSIONS_BASENAME: b"PREVIOUS-MISSIONS"},
        registry_rows=[_MERGE_ROW, _MISSIONS_ROW],
    )
    assert completed.returncode == 0, f"shipped script must exit 0 on a complete (current+fallback) set:\n{completed.stdout}\n{completed.stderr}"
    parsed = _parse_github_output(github_output)
    assert parsed.get("complete") == "true", github_output
    assert "missing<<RECONCILE_EOF" in github_output, "the missing output must use the runner delimiter form, never bare `missing=`"
    assert not re.search(r"^missing=", github_output, re.M), github_output

    resolved_dir = tmp_path / "workdir" / "out" / "aggregate" / "coverage"
    assert (resolved_dir / _MERGE_BASENAME).read_bytes() == b"CURRENT-MERGE", "current must never be shadowed by the stale fallback"
    assert (resolved_dir / _MISSIONS_BASENAME).read_bytes() == b"PREVIOUS-MISSIONS", "a shard missing from current must be served from the fallback run"


def test_shipped_reconcile_script_fails_loudly_when_shard_missing_from_both_runs(tmp_path: Path) -> None:
    """BLOCKING review finding: the shipped script (not just the twin) must
    fail loudly -- nonzero exit, `complete=false` -- when a registry-expected
    shard is absent from BOTH the current and fallback runs, never silently
    report `complete=true` (the C-005 cross-run silent-drop failure mode)."""
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={},
        previous={},
        registry_rows=[_MERGE_ROW],
    )
    assert completed.returncode != 0, f"shipped script must fail loudly on a shard missing from both runs, got exit 0:\n{completed.stdout}"
    parsed = _parse_github_output(github_output)
    assert parsed.get("complete") == "false", github_output
    assert parsed.get("missing") == _MERGE_BASENAME, github_output
    assert "missing from BOTH" in completed.stdout, completed.stdout


# ---------------------------------------------------------------------------
# Mission ci-modules-diff-scoping (Approach C): selection-aware backfill.
#
# ci-modules.yml no longer runs every registry module on every diff -- a
# module diff-scoping did not SELECT gets a SKIPPED leaf, never a fresh
# coverage file. The reconciler above must therefore distinguish:
#   * a SELECTED (changed) module missing from `current` -> fail closed, NEVER
#     served stale from `previous`, even when `previous` has it (a genuine
#     shard failure must never be masked by old green);
#   * an UNSELECTED (unchanged, provably byte-identical to the fallback
#     source) module missing from `current` -> backfill from `previous` is
#     safe and expected -- this is the ordinary, common case for a scoped PR.
# When no selection info is available at all (``selected=None`` -- a
# legacy/pre-feature run or a download failure), every missing shard remains
# fallback-eligible, exactly like the pre-Approach-C tests above.
# ---------------------------------------------------------------------------
def test_shipped_reconcile_script_backfills_an_unselected_module_from_previous(tmp_path: Path) -> None:
    """An UNSELECTED module (not in the diff-scoped selected set) missing from
    `current` is safely served from `previous` -- the ordinary scoped-PR case."""
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={_MERGE_BASENAME: b"CURRENT-MERGE"},
        previous={_MISSIONS_BASENAME: b"PREVIOUS-MISSIONS-UNCHANGED"},
        registry_rows=[_MERGE_ROW, _MISSIONS_ROW],
        selected=["merge"],
    )
    assert completed.returncode == 0, f"an unselected module must still backfill cleanly:\n{completed.stdout}\n{completed.stderr}"
    parsed = _parse_github_output(github_output)
    assert parsed.get("complete") == "true", github_output

    resolved_dir = tmp_path / "workdir" / "out" / "aggregate" / "coverage"
    assert (resolved_dir / _MERGE_BASENAME).read_bytes() == b"CURRENT-MERGE"
    assert (resolved_dir / _MISSIONS_BASENAME).read_bytes() == b"PREVIOUS-MISSIONS-UNCHANGED"


def test_shipped_reconcile_script_refuses_to_backfill_a_selected_module_even_when_previous_has_it(tmp_path: Path) -> None:
    """A SELECTED (changed) module missing from `current` must fail closed --
    it must NEVER be silently served stale data from `previous`, even when
    `previous` genuinely has a coverage file for it. This is the Approach C
    guarantee: a real shard failure on a changed module can never be masked
    by old green."""
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={},
        previous={_MERGE_BASENAME: b"STALE-MERGE-MUST-NOT-WIN"},
        registry_rows=[_MERGE_ROW],
        selected=["merge"],
    )
    assert completed.returncode != 0, f"a selected module missing from current must fail closed, got exit 0:\n{completed.stdout}"
    parsed = _parse_github_output(github_output)
    assert parsed.get("complete") == "false", github_output
    assert parsed.get("missing") == _MERGE_BASENAME, github_output

    resolved_dir = tmp_path / "workdir" / "out" / "aggregate" / "coverage"
    assert not (resolved_dir / _MERGE_BASENAME).exists(), "a selected-but-missing module must never be resolved from the stale fallback"


def test_shipped_reconcile_script_falls_back_for_every_module_when_selection_info_is_absent(tmp_path: Path) -> None:
    """No `selected-modules.json` at all (legacy/pre-feature run, or a failed
    artifact download) -> every missing shard remains fallback-eligible,
    identical to the pre-Approach-C behavior (the ``selected=None`` case)."""
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={},
        previous={_MERGE_BASENAME: b"PREVIOUS-MERGE"},
        registry_rows=[_MERGE_ROW],
        selected=None,
    )
    assert completed.returncode == 0, f"with no selection info every missing shard must still be fallback-eligible:\n{completed.stdout}\n{completed.stderr}"
    parsed = _parse_github_output(github_output)
    assert parsed.get("complete") == "true", github_output
    resolved_dir = tmp_path / "workdir" / "out" / "aggregate" / "coverage"
    assert (resolved_dir / _MERGE_BASENAME).read_bytes() == b"PREVIOUS-MERGE"


def test_shipped_reconcile_script_reports_empty_selection_has_no_coverage(tmp_path: Path) -> None:
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={},
        previous={},
        registry_rows=[_MERGE_ROW],
        selected=[],
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    parsed = _parse_github_output(github_output)
    assert parsed.get("complete") == "true", github_output
    assert parsed.get("coverage") == "false", github_output


def test_shipped_reconcile_script_ignores_a_malformed_selected_modules_file(tmp_path: Path) -> None:
    """A corrupt/malformed selected-modules.json must never crash the job --
    it degrades to "no selection info known" (fallback-eligible for all),
    the same fail-safe default as a missing file."""
    workdir = tmp_path / "workdir"
    current_dir = workdir / "out" / "aggregate" / "current"
    previous_dir = workdir / "out" / "aggregate" / "previous"
    github_dir = workdir / "out" / "aggregate" / "source"
    selected_dir = workdir / "out" / "aggregate" / "selected"
    for directory in (current_dir, previous_dir, github_dir, selected_dir):
        directory.mkdir(parents=True, exist_ok=True)
    (previous_dir / _MERGE_BASENAME).write_bytes(b"PREVIOUS-MERGE")
    (github_dir / "ci-module-registry.yml").write_text(yaml.safe_dump({"modules": [_MERGE_ROW]}), encoding="utf-8")
    (selected_dir / "selected-modules.json").write_text("{not valid json", encoding="utf-8")

    output_path = tmp_path / "github_output.txt"
    output_path.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["GITHUB_OUTPUT"] = str(output_path)
    completed = subprocess.run(
        [sys.executable, str(_shipped_reconcile_script())],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, f"a malformed selected-modules.json must degrade to fallback-eligible, never crash:\n{completed.stdout}\n{completed.stderr}"
    parsed = _parse_github_output(output_path.read_text(encoding="utf-8"))
    assert parsed.get("complete") == "true", output_path.read_text(encoding="utf-8")


def test_shipped_reconcile_script_rejects_same_run_basename_collision(tmp_path: Path) -> None:
    """The shipped script must fail loudly (never silently pick a winner) when
    two different shard outputs collide on the same basename within a single
    run's downloaded artefacts (Invariant 1)."""
    current_dir = tmp_path / "workdir" / "out" / "aggregate" / "current"
    (current_dir / "artifact-a").mkdir(parents=True, exist_ok=True)
    (current_dir / "artifact-b").mkdir(parents=True, exist_ok=True)
    (current_dir / "artifact-a" / _MERGE_BASENAME).write_bytes(b"SHARD-A")
    (current_dir / "artifact-b" / _MERGE_BASENAME).write_bytes(b"SHARD-B")

    github_dir = tmp_path / "workdir" / "out" / "aggregate" / "source"
    github_dir.mkdir(parents=True, exist_ok=True)
    (github_dir / "ci-module-registry.yml").write_text(yaml.safe_dump({"modules": [_MERGE_ROW]}), encoding="utf-8")
    output_path = tmp_path / "github_output.txt"
    output_path.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["GITHUB_OUTPUT"] = str(output_path)

    completed = subprocess.run(
        [sys.executable, str(_shipped_reconcile_script())],
        cwd=tmp_path / "workdir",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0, f"shipped script must reject a same-run basename collision:\n{completed.stdout}"
    assert "collision" in completed.stdout.lower(), completed.stdout


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("module", "kernel\ncomplete=true\nx="),
        ("module", "kernel\nRECONCILE_EOF\ncomplete=true\nx="),
        ("module", "kernel; rm -rf /"),
        ("tier", "standard\ncomplete=true"),
        ("tier", "tier with spaces"),
        ("shard_count", "2"),
        ("shard_count", True),
        ("shard_count", 1.5),
        ("shard_count", 0),
        ("shard_count", -1),
    ],
)
def test_shipped_reconcile_script_rejects_untrusted_registry_row_values(tmp_path: Path, field: str, bad_value: Any) -> None:
    """BLOCKING squad finding (pass 2, #4068): the expected-shard set is
    sourced from the UNTRUSTED PR merge tree (`out/aggregate/source/`,
    not the trusted checkout), and the derived basenames used to reach
    `$GITHUB_OUTPUT`. A PR whose registry row carries a `module` value with
    an embedded newline could inject arbitrary `key=value` step outputs --
    the runner assigns outputs line-by-line with a dictionary indexer, so
    an injected `complete=true` would override the real `complete=false`
    and defeat the full-mode completeness re-check. The shipped script
    must REFUSE the row outright: nonzero exit, an untrusted-value error,
    and nothing written to $GITHUB_OUTPUT."""
    row: dict[str, Any] = dict(_MERGE_ROW)
    row[field] = bad_value
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={_MERGE_BASENAME: b"CURRENT-MERGE"},
        previous={},
        registry_rows=[row],
    )
    assert completed.returncode != 0, f"shipped script must reject an untrusted registry {field} value {bad_value!r}:\n{completed.stdout}"
    assert "untrusted PR-authored registry value refused" in completed.stdout, completed.stdout
    # Fail-closed means the outputs are never written at all -- the refusal
    # happens in expected_basenames(), before the summary write.
    assert github_output == "", f"a refused registry row must not reach $GITHUB_OUTPUT:\n{github_output}"


def test_shipped_reconcile_script_output_cannot_inject_step_outputs(tmp_path: Path) -> None:
    """Validated missing names produce exactly the two intended outputs.

    The real script preserves its incomplete verdict and uses delimiter form;
    the separate refusal cases guard newline and delimiter-bearing row values.
    """
    completed, github_output = _run_reconcile_script(
        tmp_path,
        current={},
        previous={},
        registry_rows=[_MERGE_ROW],
    )
    assert completed.returncode != 0, completed.stdout
    # No bare `key=value` write for either output: the delimiter form is
    # structural, not incidental.
    assert not re.search(r"^(complete|missing)=", github_output, re.M), github_output
    parsed = _parse_github_output(github_output)
    assert set(parsed) == {"complete", "missing", "coverage"}, f"injected or stray step outputs: {sorted(parsed)}"
    assert parsed["complete"] == "false", github_output
    assert parsed["missing"] == _MERGE_BASENAME, github_output


def test_delimiter_output_form_neutralizes_newline_injection() -> None:
    """WHY the delimiter form, pinned as runner semantics: a newline-carrying
    `missing` value written the OLD bare way (`missing=<value>`) lets the
    runner's line-based parser see `complete=true` as a fresh output line
    and override the real `complete=false` (dictionary indexer, file order
    -- FileCommandManager); the SAME value written with the delimiter form
    is absorbed into the `missing` value and the completeness re-check
    survives. The registry-row validation refuses newline-carrying values
    outright, including delimiter collisions; this pins containment for the
    demonstrated payload, not safety for arbitrary unvalidated values."""
    malicious = "coverage-standard-merge-shard1-of-1.xml\ncomplete=true\nx="
    bare_form = f"complete=false\nmissing={malicious}\n"
    parsed_bare = _parse_github_output(bare_form)
    assert parsed_bare.get("complete") == "true", "the bare `key=value` form IS injectable -- the vulnerability the delimiter form removes"

    delimiter_form = f"complete<<RECONCILE_EOF\nfalse\nRECONCILE_EOF\nmissing<<RECONCILE_EOF\n{malicious}\nRECONCILE_EOF\n"
    parsed_delim = _parse_github_output(delimiter_form)
    assert parsed_delim.get("complete") == "false", "an injected line inside a delimiter-form value must never override a real output"
    assert parsed_delim.get("missing") == malicious
    assert set(parsed_delim) == {"complete", "missing"}


def test_ci_aggregate_embeds_stale_fallback_and_collision_guard_language() -> None:
    """Static cross-check that the embedded step this test's pure-function twin
    mirrors actually exists in ci-aggregate.yml -- the fallback is not left as
    prose in a docstring only."""
    text = _aggregate_text().lower()
    has_fallback = "previous" in text or "most-recent" in text or "fallback" in text
    assert has_fallback, "ci-aggregate.yml must implement the stale-artefact fallback for a shard that did not re-run"
    has_collision_guard = "collision" in text or "duplicate" in text
    assert has_collision_guard, "ci-aggregate.yml must guard a basename collision rather than silently dropping data"
