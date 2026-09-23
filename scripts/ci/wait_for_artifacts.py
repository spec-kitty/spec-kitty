"""Bounded pre-download poll for selected shard artefact visibility (FR-005/006).

``ci-aggregate.yml`` fires once per non-repeating ``workflow_run`` event (from
``CI Modules``); unlike ``ci-fleet-verdict.yml``'s repeating per-head events
(``fleet_verdict.py``/``fleet_main.py``'s retry-then-skip), there is no later
event to defer to here. This module polls the triggering run's artifact list
for every SELECTED (must-be-fresh) shard's expected artifact name, wrapped in
WP01's bounded ``reconcile_retry.retry_with_backoff``.

Architectural floor (do not regress): on budget exhaustion this module ALWAYS
exits 0 and never raises -- it only WIDENS the window before the workflow
falls through to the existing ``actions/download-artifact`` steps.
``scripts/ci/reconcile_shards.py::main()`` remains the single, unmodified,
fail-closed terminus that decides completeness (FR-006); this module is not
part of that decision and must never become one.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

# Support direct ``python3 scripts/ci/wait_for_artifacts.py`` invocation, which is
# how ci-aggregate.yml runs this step (no editable install, cwd not on sys.path as
# the repo root). Put the repo root on sys.path so the ``scripts.ci.*`` siblings
# below import, mirroring select_source_artifacts.py / capture_shard_timings.py.
# Without this the step crashes at import with ``ModuleNotFoundError: No module
# named 'scripts'`` — and because ci-aggregate only runs on main (workflow_run),
# that crash cannot surface until after merge.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci.fleet_verdict import GitHub  # noqa: E402
from scripts.ci.reconcile_retry import retry_with_backoff  # noqa: E402
from scripts.ci.reconcile_shards import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    DEFAULT_SELECTED_PATH,
    RegistryShard,
    parse_registry,
    read_selected_modules,
)
from scripts.ci.select_source_artifacts import ARTIFACT  # noqa: E402

__all__ = [
    "MAX_ATTEMPTS",
    "ShardKey",
    "match_artifacts",
    "must_be_fresh_shards",
    "poll_for_artifacts",
    "required_keys",
    "main",
]

ShardKey = tuple[str, int, int]

# Retry Budget Rationale (plan.md NFR-001): 8 attempts, 5s -> 10s -> 20s ->
# 30s (cap) -- 5,10,20,30,30,30,30 between the 8 attempts, ~155s (~2.6 min)
# total bounded wait.
MAX_ATTEMPTS = 8
_BACKOFF_SCHEDULE = (5.0, 10.0, 20.0, 30.0)


def _backoff_seconds(i: int) -> float:
    """5s -> 10s -> 20s -> 30s, capped at 30s for every attempt beyond that."""
    index = min(i, len(_BACKOFF_SCHEDULE)) - 1
    return _BACKOFF_SCHEDULE[index]


def must_be_fresh_shards(registry_shards: list[RegistryShard], selected: set[str] | None) -> list[RegistryShard]:
    """The exact ``must_be_fresh`` predicate ``reconcile_shards.py::reconcile()``
    applies later in the same job, computed once here and reused -- never a
    second, independently-invented definition of "must-be-fresh."
    """
    return [shard for shard in registry_shards if selected is not None and shard.module in selected]


def required_keys(shards: list[RegistryShard]) -> frozenset[ShardKey]:
    """(module, shard_index, shard_count) keys the poller must see visible."""
    return frozenset((shard.module, shard.shard_index, shard.shard_count) for shard in shards)


def match_artifacts(artifacts: list[dict[str, object]], run_attempt: int, required: frozenset[ShardKey]) -> dict[ShardKey, str]:
    """Pure: bind each REQUIRED key to the artifact name visible in ``artifacts``.

    Reuses ``select_source_artifacts.py``'s own artifact-naming regex (import,
    not a second copy that could drift) and its carried-forward-attempt
    tolerance: an artifact's own ``attempt`` may be any value ``<=
    run_attempt`` (not necessarily equal to it).
    """
    found: dict[ShardKey, str] = {}
    for artifact in artifacts:
        match = ARTIFACT.fullmatch(str(artifact.get("name", "")))
        if match is None:
            continue
        module, shard_index, shard_count, attempt = match.group(1), int(match.group(2)), int(match.group(3)), int(match.group(4))
        if attempt > run_attempt:
            continue
        key = (module, shard_index, shard_count)
        if key in required:
            found[key] = str(artifact["name"])
    return found


def poll_for_artifacts(
    api: GitHub,
    *,
    run_id: str,
    run_attempt: int,
    required: frozenset[ShardKey],
    max_attempts: int = MAX_ATTEMPTS,
    backoff_seconds: Callable[[int], float] = _backoff_seconds,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[ShardKey, str], frozenset[ShardKey]]:
    """Poll up to ``max_attempts`` times (WP01's ``retry_with_backoff``),
    stopping the moment every required shard's artifact is visible.

    On budget exhaustion, returns whatever was found on the LAST attempt plus
    the still-missing keys -- this is a WIDENED WINDOW, never a completeness
    decision. Callers (``main()`` below) must always exit 0 regardless of the
    outcome; ``reconcile_shards.py::main()`` alone decides completeness
    (FR-006).
    """
    last_found: dict[ShardKey, str] = {}

    def _attempt() -> dict[ShardKey, str] | None:
        nonlocal last_found
        try:
            artifacts = api.pages(f"actions/runs/{run_id}/artifacts", field="artifacts")
        except (ValueError, OSError) as error:
            # PR-FRESH1-001: narrowed from a bare `except Exception`. This catches
            # exactly the shapes a transient GitHub API failure actually takes --
            # GitHub.request() converts an HTTPError into a raised ValueError, and
            # a network-level failure raises OSError or one of its subclasses
            # (urllib.error.URLError, socket.timeout/TimeoutError). Treat those
            # identically to "not yet visible" and let retry_with_backoff retry
            # them -- never let them propagate. This is local to the poller's own
            # resilience and never touches reconcile_shards.py's separate,
            # unmodified fail-closed completeness guard.
            #
            # Known imprecision (documented, not silently accepted): GitHub.pages()
            # also raises a bare ValueError for "API result exceeded bounded
            # pagination", which is not actually transient -- but GitHub.request()
            # flattens every HTTP-error condition into the same ValueError type, so
            # there is no way to tell them apart without changing fleet_verdict.py,
            # which is out of scope here. Worst case this one non-transient
            # ValueError is retried up to MAX_ATTEMPTS times (~155s) before falling
            # into the ordinary "budget exhausted" ::warning:: path below -- it is
            # never silently and permanently swallowed the way KeyError/TypeError/
            # other genuine bugs were before this fix.
            print(f"wait-for-artifacts: transient error polling artifact list, will retry: {error}")
            return None
        last_found = match_artifacts(artifacts, run_attempt, required)
        return dict(last_found) if required <= last_found.keys() else None

    outcome = retry_with_backoff(_attempt, max_attempts=max_attempts, backoff_seconds=backoff_seconds, sleep=sleep)
    found = outcome if outcome is not None else last_found
    return found, required - found.keys()


def main() -> int:
    """Thin CLI edge: resolve env vars, compute the must-be-fresh set, poll,
    and ALWAYS exit 0 -- never raise, never set a failing exit code (spec
    US3 Acceptance Scenario 2 / FR-006). ``GH_TOKEN`` is consumed implicitly
    by ``GitHub.request()``; this function never reads it directly.

    PR-MERGED-002: the body below is wrapped so this contract holds even for
    a failure outside ``poll_for_artifacts``'s own retry loop (e.g. an
    unreadable registry file, a malformed env var). ``poll_for_artifacts``
    already retries a transient API error as "not yet visible"; this is
    belt-and-braces for anything that slips past that. Either way this
    module only ever WIDENS the window before the existing download steps --
    ``reconcile_shards.py::main()`` remains the sole fail-closed completeness
    authority and is untouched by this change.
    """
    try:
        run_id = os.environ["SOURCE_RUN_ID"]
        run_attempt = int(os.environ["SOURCE_RUN_ATTEMPT"])
        repository = os.environ["SOURCE_REPOSITORY"]

        registry_shards = parse_registry(DEFAULT_REGISTRY_PATH)
        selected = read_selected_modules(DEFAULT_SELECTED_PATH)
        fresh_shards = must_be_fresh_shards(registry_shards, selected)
        required = required_keys(fresh_shards)

        if not required:
            print("wait-for-artifacts: no must-be-fresh shards selected for this run; nothing to wait for")
            return 0

        api = GitHub(repository)
        _found, missing = poll_for_artifacts(api, run_id=run_id, run_attempt=run_attempt, required=required)

        if missing:
            missing_names = sorted(f"module-tests-{module}-shard-{index}-of-{count}-attempt-<={run_attempt}-reports" for module, index, count in missing)
            print(f"::warning::wait-for-artifacts: budget exhausted ({MAX_ATTEMPTS} attempts); {len(missing)} shard artefact(s) still not visible: {missing_names}")
            print("::warning::wait-for-artifacts: falling through to the existing download steps -- reconcile_shards.py's unmodified guard still applies")
        else:
            print(f"wait-for-artifacts: all {len(required)} must-be-fresh shard artefact(s) visible")
        return 0
    except Exception as error:  # noqa: BLE001 - architectural floor: this module ALWAYS
        # exits 0 (module docstring above) even for a permanent, non-transient
        # failure (e.g. a dropped/typo'd env var, a bad token, a wrong registry
        # path, or a genuine bug in GitHub.pages()) -- the documented contract this
        # step's own preconditions must never turn into a hard CI failure, and
        # poll_for_artifacts() already retries the actually-transient GitHub API
        # shapes itself (see _attempt() above), so anything reaching this handler
        # is, by construction, NOT one of those. PR-FRESH1-001: this can no longer
        # be a silent, unbounded no-op -- print a distinctly LOUD ::error::
        # annotation (never ::warning::, which is reserved for the ordinary
        # "budget exhausted, falling through" case above) so an operator scanning
        # annotations can tell "this step is permanently broken" apart from
        # "GitHub was flaky this run". This module still never decides
        # completeness -- reconcile_shards.py::main() alone does that.
        print(f"::error::wait-for-artifacts: unexpected error, falling through to existing download steps: {error}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
