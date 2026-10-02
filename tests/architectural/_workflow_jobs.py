"""Per-change workflow enumeration and classification (shared, non-test helper).

The one place that answers "which workflow files exist" (:func:`enumerate_workflows`,
a directory read) and "does this workflow run once per change" (:func:`change_triggered`,
a fail-closed classifier), plus :func:`advisory_jobs` -- which jobs cannot fail the change
because their suite run is ``continue-on-error``. The first two were born in
``test_no_duplicate_suite_execution`` (mission ``sonar-per-pr-coverage-reuse-01M2FR32``
WP04) and moved here so helper modules such as :mod:`tests.architectural._live_uniqueness`
import them from a helper, never from a test module (C-010: one classifier, no layering
inversion). Behaviour is unchanged by the move; the fault-injection battery that pins it
still lives in ``test_no_duplicate_suite_execution``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from tests.architectural import _gate_coverage as gc

__all__ = [
    "NON_CHANGE_TRIGGER_EVENTS",
    "PER_CHANGE_PUSH_FILTERS",
    "advisory_jobs",
    "change_triggered",
    "enumerate_workflows",
    "normalized_triggers",
    "push_is_per_change",
]

# Events that do NOT put a workflow on the per-change path.
#
# This is a CLOSED WORLD by deliberate inversion. An allow-list of per-change
# events fails OPEN: every trigger spelling it has not heard of -- and
# ``on: [push, pull_request]``, the most ordinary spelling in GitHub Actions, is
# one of them -- silently drops its workflow out of every assertion in this
# module. The two errors do not cost the same. A workflow wrongly called
# per-change costs one reviewed ledger row; a workflow wrongly called NOT
# per-change is invisible, which is exactly the "gate stays green while the tree
# violates the property" failure this battery exists to make unrepeatable. So
# anything not named here -- an unrecognised event, an ``on:`` block in a shape
# this module cannot parse, a missing ``on:`` block -- counts as change-triggered.
#
# Every row below widens the blind spot and must earn its place:
#   ``schedule``          a cron run is not a change (ci-nightly, sonar).
#   ``workflow_dispatch`` a human-initiated run is not a change.
#   ``workflow_call``     a reusable workflow has no triggers of its own; it is
#                         spliced into its caller by ``load_spliced_workflow``,
#                         so counting it standalone would double-count THE
#                         matrix (module-tests.yml).
#   ``release``           a publication event, like the tags-only push below.
NON_CHANGE_TRIGGER_EVENTS: frozenset[str] = frozenset({"schedule", "workflow_dispatch", "workflow_call", "release"})

# ``on.push`` keys that make a push a per-change event. Only a tags-only push
# (``release.yml``) is exempt: tags are publication refs, whereas branch and
# path filters select *changes*. A ``push:`` with no filters at all fires on
# every push and is per-change too.
PER_CHANGE_PUSH_FILTERS: tuple[str, ...] = (
    "branches",
    "branches-ignore",
    "paths",
    "paths-ignore",
    "tags-ignore",
)


def normalized_triggers(data: dict[Any, Any]) -> dict[str, Any] | None:
    """A workflow's ``on:`` block as ``event -> config``, or ``None`` if unreadable.

    GitHub accepts three spellings -- a mapping, a list (``on: [push,
    pull_request]``) and a bare string (``on: push``) -- and YAML 1.1 parses the
    bare key ``on`` as the boolean ``True``, so the block also arrives under
    either key depending on the loader's mood. The parameter is therefore
    ``dict[Any, Any]`` and not ``dict[str, Any]``: a parsed workflow genuinely
    does NOT have string keys throughout, and annotating it as if it did made
    the ``data.get(True)`` lookup below an overload error under ``mypy
    --strict`` (WP06/T029b -- no CI workflow runs mypy, so a green pipeline was
    never evidence this was fine).

    ``None`` means "this module does not understand the block". It is NOT the
    same as "the block declares nothing": :func:`change_triggered` resolves it
    to *visible*, never to *skipped*.
    """
    section = data.get("on", data.get(True))
    if isinstance(section, dict):
        return {str(event): config for event, config in section.items()}
    if isinstance(section, str):
        return {section: None}
    if isinstance(section, list) and all(isinstance(item, str) for item in section):
        return dict.fromkeys(section)
    return None


def push_is_per_change(config: Any) -> bool:
    """Whether an ``on.push`` configuration fires per change.

    Only a tags-only push is exempt. A bare ``push:``, a ``push:`` filtered by
    branches or paths, and a ``push:`` of an unrecognised shape all fire per
    change -- the last by the same fail-closed rule as everything else here.
    """
    if not isinstance(config, dict):
        return True
    if any(config.get(key) for key in PER_CHANGE_PUSH_FILTERS):
        return True
    return not config.get("tags")


def change_triggered(path: Path) -> bool:
    """Whether *path* runs once per change -- FAILING CLOSED on anything unfamiliar.

    A workflow that is not change-triggered is invisible to every assertion in
    the per-change scan, so "I could not classify this" must resolve to *visible*. The
    workflow is excluded only when EVERY event it declares is a known
    non-per-change event (:data:`NON_CHANGE_TRIGGER_EVENTS`, plus a tags-only
    push); one unrecognised event, an unparseable ``on:`` block or no ``on:``
    block at all puts it back in scope.
    """
    data = gc.load_spliced_workflow(path)
    events = normalized_triggers(data) if isinstance(data, dict) else None
    if not events:
        return True
    return any(push_is_per_change(config) if event == "push" else event not in NON_CHANGE_TRIGGER_EVENTS for event, config in events.items())


def enumerate_workflows(workflows_dir: Path) -> list[Path]:
    """Every workflow file in *workflows_dir*, read from the DIRECTORY.

    Not from a closed list. ``_gate_coverage.WORKFLOW_FILES`` is an allowlist of
    files known to run the suite; a net-new file is by definition not in it, and
    a rule anchored to it would exempt exactly the case mutation 4 injects.
    """
    return sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))


def _continues_on_error(node: Mapping[str, Any]) -> bool:
    """Whether a job or step declares ``continue-on-error`` that may be true at runtime.

    Fails toward ADVISORY: only an absent key, a literal ``false`` or the string
    ``"false"`` is blocking. An expression (``${{ matrix.experimental }}``) may
    evaluate true, so it cannot be counted on to fail the change.
    """
    value = node.get("continue-on-error", False)
    return value is not False and str(value).strip().lower() != "false"


def _step_runs_suite(job: Mapping[str, Any], step: Mapping[str, Any]) -> bool:
    """Whether *step*'s ``run`` reaches the suite in ANY matrix leg (``_gate_coverage``'s detector)."""
    run = step.get("run")
    if not isinstance(run, str):
        return False
    variants: list[dict[str, Any]] = gc._matrix_includes(dict(job)) or [{}]
    return any(gc.suite_invocations(line) for mvars in variants for line in gc.join_continuations(gc.substitute_matrix(run, mvars)))


def _delegate_continues_on_error(job: Mapping[str, Any], workflows_dir: Path) -> bool:
    """Job-level ``continue-on-error`` on a local reusable workflow's job.

    ``load_spliced_workflow`` inlines the delegate's STEPS into the caller but not its
    job-level keys, so a delegate declared advisory would otherwise read as blocking.
    """
    called = gc._job_uses_local(dict(job))
    target = workflows_dir / called if called else None
    if target is None or not target.exists():
        return False
    delegate_jobs = (yaml.safe_load(target.read_text(encoding="utf-8")) or {}).get("jobs") or {}
    return any(isinstance(delegate, dict) and _continues_on_error(delegate) for delegate in delegate_jobs.values())


def advisory_jobs(path: Path) -> frozenset[str]:
    """Names of *path*'s jobs whose suite run cannot fail the change (advisory, not a home).

    A job is advisory when ``continue-on-error`` may be true on the job itself, on the
    local reusable workflow it delegates to, or on any step that runs the suite. A step
    that does NOT run the suite (a skip-if-green probe, an artefact download) does not
    make its job advisory.
    """
    data = gc.load_spliced_workflow(path)
    advisory: set[str] = set()
    for name, job in (data.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        steps = [step for step in job.get("steps") or [] if isinstance(step, dict)]
        if (
            _continues_on_error(job)
            or _delegate_continues_on_error(job, path.parent)
            or any(_continues_on_error(step) and _step_runs_suite(job, step) for step in steps)
        ):
            advisory.add(str(name))
    return frozenset(advisory)
