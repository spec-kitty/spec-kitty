"""Red-first + full coverage for ``wait_for_artifacts.py``'s bounded artefact poll (FR-005/006).

RED-FIRST (charter C-011): ``wait_for_artifacts.py`` does not exist before this
mission, so "red-first through the pre-existing entry point" cannot apply
literally (plan.md's own resolution). Instead, the recovery-path tests below
are written against a single, UNRETRIED-poll STUB version of
``poll_for_artifacts`` and confirmed to fail the way a single, unretried poll
attempt fails today -- a transiently-missing artifact is treated as
permanently missing, exactly the "fails once, passes on retry no longer
reliably holds" defect #4675 describes. They pass once ``poll_for_artifacts``
is wired to WP01's ``retry_with_backoff``.

Mirrors ``test_fleet_verdict.py``'s ``API``/``GitHub``-mocking convention: a
fake implementing the same ``request``/``pages`` interface as
``GitHub``/``GitHubCLI``, returning a controllable, evolving list of artifact
names across calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci import reconcile_shards, wait_for_artifacts
from scripts.ci.reconcile_shards import RegistryShard
from scripts.ci.wait_for_artifacts import (
    MAX_ATTEMPTS,
    match_artifacts,
    must_be_fresh_shards,
    poll_for_artifacts,
    required_keys,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_AGGREGATE_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-aggregate.yml"

pytestmark = pytest.mark.fast

RUN_ID = "999"
_MERGE = RegistryShard(tier="standard", module="merge", shard_index=1, shard_count=2)
_MERGE_2 = RegistryShard(tier="standard", module="merge", shard_index=2, shard_count=2)
_UNSELECTED = RegistryShard(tier="standard", module="unselected", shard_index=1, shard_count=1)


def _artifact_name(shard: RegistryShard, attempt: int = 1) -> str:
    return f"module-tests-{shard.module}-shard-{shard.shard_index}-of-{shard.shard_count}-attempt-{attempt}-reports"


class FakeArtifactsAPI:
    """A controllable, evolving artifact list across ``pages()`` calls."""

    def __init__(self, names_by_call: list[list[str]]) -> None:
        self._names_by_call = names_by_call
        self.calls = 0

    def pages(self, path: str, field: str | None = None) -> list[dict[str, Any]]:
        assert path == f"actions/runs/{RUN_ID}/artifacts"
        assert field == "artifacts"
        self.calls += 1
        index = min(self.calls, len(self._names_by_call)) - 1
        return [{"name": name} for name in self._names_by_call[index]]


def _never_sleep(_seconds: float) -> None:
    """Keep the retry-wired path instant in tests (NFR-002/NFR-003)."""


# --- must-be-fresh predicate / key derivation ------------------------------


def test_must_be_fresh_matches_reconcile_predicate() -> None:
    """Side-by-side with reconcile_shards.py::reconcile()'s own predicate:
    `selected is not None and shard.module in selected`."""
    assert must_be_fresh_shards([_MERGE, _UNSELECTED], {"merge"}) == [_MERGE]
    assert must_be_fresh_shards([_MERGE, _UNSELECTED], None) == []
    assert must_be_fresh_shards([_MERGE, _UNSELECTED], set()) == []


def test_required_keys_is_module_shard_index_shard_count() -> None:
    assert required_keys([_MERGE, _MERGE_2]) == frozenset({("merge", 1, 2), ("merge", 2, 2)})


def test_match_artifacts_honors_carried_forward_attempt_tolerance() -> None:
    """An artifact's own attempt may be <= run_attempt, matching
    select_source_artifacts.py's own tolerance -- not necessarily equal."""
    required = required_keys([_MERGE])
    artifacts = [{"name": _artifact_name(_MERGE, attempt=1)}]
    assert match_artifacts(artifacts, run_attempt=3, required=required) == {("merge", 1, 2): _artifact_name(_MERGE, attempt=1)}
    # An artifact from a LATER attempt than the current run must never match.
    later = [{"name": _artifact_name(_MERGE, attempt=4)}]
    assert match_artifacts(later, run_attempt=3, required=required) == {}


def test_match_artifacts_ignores_unrelated_and_unselected_names() -> None:
    required = required_keys([_MERGE])
    artifacts = [{"name": "some-other-artifact"}, {"name": _artifact_name(_UNSELECTED)}]
    assert match_artifacts(artifacts, run_attempt=1, required=required) == {}


# --- red-first recovery-path anchors ----------------------------------------


def test_recovery_within_budget_becomes_visible_after_retry() -> None:
    """RED-FIRST ANCHOR: absent on poll 1, present on poll 2. FAILS against
    the T011 single-attempt stub (it only polls once, so it never sees the
    artifact appear); PASSES once T012 wires retry_with_backoff."""
    api = FakeArtifactsAPI([[], [_artifact_name(_MERGE)]])
    required = required_keys([_MERGE])

    found, missing = poll_for_artifacts(api, run_id=RUN_ID, run_attempt=1, required=required, sleep=_never_sleep)

    assert missing == frozenset()
    assert found[("merge", 1, 2)] == _artifact_name(_MERGE)
    assert api.calls == 2


def test_present_by_final_attempt_within_the_real_budget() -> None:
    """RED-FIRST ANCHOR: present only on the 8th poll (the last one inside the
    real 8-attempt budget). FAILS against the T011 stub (one poll only);
    PASSES once T012 wires retry_with_backoff with MAX_ATTEMPTS=8."""
    calls = [[] for _ in range(MAX_ATTEMPTS - 1)] + [[_artifact_name(_MERGE)]]
    api = FakeArtifactsAPI(calls)
    required = required_keys([_MERGE])

    found, missing = poll_for_artifacts(api, run_id=RUN_ID, run_attempt=1, required=required, sleep=_never_sleep)

    assert missing == frozenset()
    assert found[("merge", 1, 2)] == _artifact_name(_MERGE)
    assert api.calls == MAX_ATTEMPTS


def test_exhausted_budget_never_raises_and_reports_missing() -> None:
    """Terminal path: the artifact never appears within the budget. Must
    never raise -- returns the still-missing key set instead (the caller,
    main(), is what turns this into exit 0 with a diagnostic)."""
    api = FakeArtifactsAPI([[]])
    required = required_keys([_MERGE])

    found, missing = poll_for_artifacts(api, run_id=RUN_ID, run_attempt=1, required=required, sleep=_never_sleep)

    assert found == {}
    assert missing == frozenset({("merge", 1, 2)})
    assert api.calls == MAX_ATTEMPTS


def test_no_must_be_fresh_shards_never_polls() -> None:
    """No must-be-fresh shards selected -- poll_for_artifacts is never even
    called by main() in that case; this pins the required-set-empty shape
    poll_for_artifacts itself must also handle harmlessly if ever called."""
    api = FakeArtifactsAPI([[]])
    found, missing = poll_for_artifacts(api, run_id=RUN_ID, run_attempt=1, required=frozenset(), sleep=_never_sleep)
    assert found == {}
    assert missing == frozenset()
    assert api.calls == 1


# --- T014: composing test -- reconcile_shards.py's fail-closed floor -------


def test_composing_reconcile_shards_still_fails_closed_when_poller_exhausts(tmp_path: Any, capsys: pytest.CaptureFixture[str]) -> None:
    """The poller WIDENS the window; it never DECIDES completeness.

    Constructs the on-disk state ``actions/download-artifact`` would leave
    behind when the poller exhausts its budget for a must-be-fresh shard that
    is genuinely still absent (``out/aggregate/current/`` has nothing for
    it), then invokes the REAL, untouched ``reconcile_shards.py::main()``
    against that state -- proving invariant (b) (FR-006/C-002) end to end
    without a real workflow run.
    """
    aggregate_root = tmp_path / "out" / "aggregate"
    registry_path = aggregate_root / "source" / "ci-module-registry.yml"
    selected_path = aggregate_root / "selected" / "selected-modules.json"
    registry_path.parent.mkdir(parents=True)
    selected_path.parent.mkdir(parents=True)
    registry_path.write_text(yaml.safe_dump({"modules": [{"tier": "standard", "module": "merge", "shard_count": 1}]}))
    selected_path.write_text(json.dumps(["merge"]))
    # out/aggregate/current/ and out/aggregate/previous/ are left entirely
    # absent -- the shard the poller was waiting for never became visible in
    # either, exactly the exhausted-budget circumstance wait_for_artifacts.py
    # falls through on.

    exit_code = reconcile_shards.main(aggregate_root=aggregate_root, registry_path=registry_path, selected_path=selected_path)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "refusing to silently treat this run as complete" in captured.out


def test_reconcile_shards_module_is_untouched_by_this_wp() -> None:
    """Key Entities item 3 / T015: reconcile_shards.py gains a new importer
    only -- its public contract used by this WP is exactly what plan.md
    pins, unmodified."""
    assert hasattr(reconcile_shards, "parse_registry")
    assert hasattr(reconcile_shards, "read_selected_modules")
    assert hasattr(reconcile_shards, "reconcile")
    assert hasattr(reconcile_shards, "main")


# --- PR-MERGED-001: the poll step must run only after PyYAML is installed --


def _collect_job_step_names() -> list[str]:
    workflow = yaml.safe_load(_CI_AGGREGATE_PATH.read_text(encoding="utf-8"))
    return [step["name"] for step in workflow["jobs"]["collect"]["steps"] if "name" in step]


def test_pyyaml_install_precedes_the_wait_for_artifacts_step() -> None:
    """RED-FIRST for PR-MERGED-001: wait_for_artifacts.py (and its transitive
    imports fleet_verdict.py/reconcile_shards.py) carry a module-level
    ``import yaml``. If "Install PyYAML" runs AFTER the "Wait for..." step, that
    step crashes with ModuleNotFoundError at import time on 100% of
    non-workflow_dispatch runs (the ubuntu-24.04 runner image has no
    python3-yaml). This pins the fix's ordering invariant directly in the parsed
    YAML -- a unit test cannot otherwise catch a workflow step-ordering defect.
    RED against the pre-fix ordering, where "Install PyYAML" was 72 lines AFTER
    the poll step, right before the "Reconcile shard artefacts" step.
    """
    names = _collect_job_step_names()
    install_index = names.index("Install PyYAML (registry parsing only, no editable install needed)")
    wait_index = names.index("Wait for selected shard artefact visibility (mission reconcile-flake-family, FR-005)")
    assert install_index < wait_index, "PyYAML must be installed before wait_for_artifacts.py runs (module-level `import yaml`)"


def test_wait_for_artifacts_step_still_precedes_the_download_steps() -> None:
    """HARD CONSTRAINT pin: the poll step's entire purpose is to run ahead of the
    download-artifact steps -- moving the PyYAML install earlier must never
    regress the poll step back below them."""
    names = _collect_job_step_names()
    wait_index = names.index("Wait for selected shard artefact visibility (mission reconcile-flake-family, FR-005)")
    for download_step in (
        "Download the triggering run's shard artefacts",
        "Download the fallback run's shard artefacts (stale shards only)",
    ):
        assert wait_index < names.index(download_step), f"the poll step must remain ahead of {download_step!r}"


# --- PR-MERGED-002: a transient GitHub API error must be retried, never raised --


class _AlwaysRaisingAPI:
    """Simulates a persistent transient GitHub API failure (e.g. repeated 5xx)."""

    def __init__(self, exception: Exception) -> None:
        self._exception = exception
        self.calls = 0

    def pages(self, path: str, field: str | None = None) -> list[dict[str, Any]]:
        self.calls += 1
        raise self._exception


class _RaisesOnceThenSucceedsAPI:
    """Simulates a single transient blip that clears on the next attempt."""

    def __init__(self, exception: Exception, names_after: list[str]) -> None:
        self._exception = exception
        self._names_after = names_after
        self.calls = 0

    def pages(self, path: str, field: str | None = None) -> list[dict[str, Any]]:
        self.calls += 1
        if self.calls == 1:
            raise self._exception
        return [{"name": name} for name in self._names_after]


def test_transient_api_error_is_retried_not_raised() -> None:
    """RED-FIRST for PR-MERGED-002: api.pages() raising on the first poll (the
    shape GitHub.request() raises for an HTTPError, or an OSError/URLError for a
    network-level failure) must be treated exactly like "not yet visible" and
    retried -- never propagate out of poll_for_artifacts(). RED against the
    unfixed _attempt(): the exception propagates straight out with no try/except
    anywhere in the file, so this test raises instead of returning normally."""
    api = _RaisesOnceThenSucceedsAPI(ValueError("GitHub API HTTP 503: service unavailable"), [_artifact_name(_MERGE)])
    required = required_keys([_MERGE])

    found, missing = poll_for_artifacts(api, run_id=RUN_ID, run_attempt=1, required=required, sleep=_never_sleep)

    assert missing == frozenset()
    assert found[("merge", 1, 2)] == _artifact_name(_MERGE)
    assert api.calls == 2


def test_persistent_api_error_exhausts_budget_without_raising() -> None:
    """A transient error on EVERY attempt must still exhaust the retry budget
    cleanly (never raise) and report the shard as missing, exactly like an
    ordinary exhaustion -- the poller only ever widens the window, it never
    raises regardless of WHY the artifact never became visible."""
    api = _AlwaysRaisingAPI(ValueError("GitHub API HTTP 500: internal error"))
    required = required_keys([_MERGE])

    found, missing = poll_for_artifacts(api, run_id=RUN_ID, run_attempt=1, required=required, sleep=_never_sleep)

    assert found == {}
    assert missing == frozenset({("merge", 1, 2)})
    assert api.calls == MAX_ATTEMPTS


def test_main_never_raises_on_unexpected_error_outside_the_poll_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """RED-FIRST defense-in-depth for PR-MERGED-002: an error OUTSIDE
    poll_for_artifacts's own retry loop -- here, GitHub.__init__ rejecting a
    malformed ``SOURCE_REPOSITORY`` -- must still honor the module's documented
    "ALWAYS exit 0 -- never raise" contract. RED against the unfixed main(): the
    ValueError propagates straight out, which the collect job's
    `set -euo pipefail` step turns into a hard CI failure -- the same defect
    class as PR-MERGED-002, from a different call site.
    """
    registry_path = tmp_path / "registry.yml"
    selected_path = tmp_path / "selected.json"
    registry_path.write_text(yaml.safe_dump({"modules": [{"tier": "standard", "module": "merge", "shard_count": 1}]}))
    selected_path.write_text(json.dumps(["merge"]))
    monkeypatch.setattr(wait_for_artifacts, "DEFAULT_REGISTRY_PATH", registry_path)
    monkeypatch.setattr(wait_for_artifacts, "DEFAULT_SELECTED_PATH", selected_path)
    monkeypatch.setenv("SOURCE_RUN_ID", "999")
    monkeypatch.setenv("SOURCE_RUN_ATTEMPT", "1")
    monkeypatch.setenv("SOURCE_REPOSITORY", "not a valid repository")  # GitHub() rejects this with ValueError

    exit_code = wait_for_artifacts.main()

    assert exit_code == 0
    assert "unexpected error" in capsys.readouterr().out


# --- PR-FRESH1-001: except Exception is not scoped to "transient" --


class _RaisesProgrammingBugAPI:
    """Simulates a genuine bug (e.g. in ``GitHub.pages()``), never a transient
    GitHub API condition -- ``TypeError`` is not a shape ``GitHub.request()``
    ever raises for an HTTP or network failure (that shape is ``ValueError``
    for a converted ``HTTPError``, or ``OSError``/``URLError`` at the network
    level)."""

    def __init__(self) -> None:
        self.calls = 0

    def pages(self, path: str, field: str | None = None) -> list[dict[str, Any]]:
        self.calls += 1
        raise TypeError("boom: not a transient GitHub API shape")


def test_programming_bug_in_poll_is_not_silently_retried_as_transient() -> None:
    """RED-FIRST for PR-FRESH1-001: a genuine programming bug surfacing through
    ``api.pages()`` (here, a ``TypeError`` -- not the ``ValueError``/``OSError``
    shape a transient GitHub API failure actually takes) must propagate out of
    ``poll_for_artifacts`` on the FIRST attempt, not be silently swallowed and
    retried through the whole budget like "not yet visible". RED against the
    unfixed ``_attempt()``: its bare ``except Exception`` catches everything,
    including this ``TypeError``, retries it ``MAX_ATTEMPTS`` times, and
    returns normally instead of raising."""
    api = _RaisesProgrammingBugAPI()
    required = required_keys([_MERGE])

    with pytest.raises(TypeError):
        poll_for_artifacts(api, run_id=RUN_ID, run_attempt=1, required=required, sleep=_never_sleep)

    assert api.calls == 1


def test_permanent_setup_failure_is_reported_as_error_not_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """RED-FIRST for PR-FRESH1-001: a permanent misconfiguration -- here, a
    dropped ``SOURCE_RUN_ID`` env var producing ``KeyError`` -- must still
    honor "ALWAYS exit 0" (main()'s architectural floor), but the annotation
    it prints must be LOUD and DISTINGUISHABLE (``::error::``) from the
    ordinary "budget exhausted, falling through" ``::warning::`` case, so an
    operator scanning annotations can tell a permanently-broken step apart
    from a merely-flaky one. RED against the unfixed main(): the outer handler
    prints ``::warning::wait-for-artifacts: unexpected error, ...`` for BOTH
    cases identically -- no ``::error::`` annotation is ever emitted."""
    registry_path = tmp_path / "registry.yml"
    selected_path = tmp_path / "selected.json"
    registry_path.write_text(yaml.safe_dump({"modules": [{"tier": "standard", "module": "merge", "shard_count": 1}]}))
    selected_path.write_text(json.dumps(["merge"]))
    monkeypatch.setattr(wait_for_artifacts, "DEFAULT_REGISTRY_PATH", registry_path)
    monkeypatch.setattr(wait_for_artifacts, "DEFAULT_SELECTED_PATH", selected_path)
    monkeypatch.delenv("SOURCE_RUN_ID", raising=False)
    monkeypatch.setenv("SOURCE_RUN_ATTEMPT", "1")
    monkeypatch.setenv("SOURCE_REPOSITORY", "spec-kitty/spec-kitty")

    exit_code = wait_for_artifacts.main()

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "::error::wait-for-artifacts: unexpected error" in output
    assert "::warning::wait-for-artifacts: unexpected error" not in output
