"""Contract tests for the shared warmup / test-env-creation composite action.

FR-003/#3283 (mission ci-pipeline-reinstatement-01M1X35E, WP04) made the composite
the one place that builds the editable pytest environment and lets downstream
shards reuse it. The later cache-honesty fixes keep that single-build contract but
remove what was not true about it:

* **No duplicate checkout.** The action used to run ``actions/checkout`` itself,
  though a local composite can only be loaded *after* the caller's checkout — so
  every caller paid for two clones. The caller now owns the checkout; the action
  fails closed when the repository is not on disk. ``test_every_caller_...`` is the
  caller-side half of that contract.
* **The revision is the lock's.** ``pr`` mode used to advertise a
  ``pinned-events-rev`` default (10.4.6) that had drifted from ``uv.lock``
  (``>=11.3.0,<12``); ``uv sync --frozen`` installs the locked version regardless,
  so the input was an authority that lied. The revision now comes from
  ``scripts/ci/warmup_events_rev.py`` (lock for ``pr``, PyPI for ``full``) and is
  verified against the built environment afterwards.
* **No fragile whole-``.venv`` cache.** A cached ``.venv`` is not self-contained:
  its ``bin/python`` symlinks to a uv-managed interpreter outside the cache, which
  is why the old fast path had to probe for a dangling symlink and rebuild anyway.
  The action caches uv's dependency cache and the managed interpreter instead
  (``setup-uv``) and always runs an honest ``uv sync`` — a warm cache makes it
  cheap, and no ``cache-hit`` flag ever stands in for a working environment.
* **Packs are cached before anything can fetch them.** The editable build hook
  fetches ``packs/built-in`` when the tree is absent, so the restore-only
  open-packs cache action runs before ``uv sync``; ``sync-packs`` still verifies
  and places the trees afterwards.

The YAML is loaded lazily inside each test so the module always collects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

ROOT = Path(__file__).resolve().parents[2]
ACTION_PATH = ROOT / ".github" / "actions" / "warmup" / "action.yml"
RESTORE_OPEN_PACKS_PATH = ROOT / ".github" / "actions" / "restore-open-packs" / "action.yml"
WORKFLOWS = ROOT / ".github" / "workflows"
RESOLVER_RELPATH = "scripts/ci/warmup_events_rev.py"

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CHECKOUT_PREFIX = "actions/checkout@"
SETUP_UV_PREFIX = "astral-sh/setup-uv@"
RESTORE_OPEN_PACKS = "./.github/actions/restore-open-packs"
SYNC_PACKS = "./.github/actions/sync-packs"


def _load_action() -> dict[str, Any]:
    action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
    assert isinstance(action, dict)
    return action


def _action_text() -> str:
    return ACTION_PATH.read_text(encoding="utf-8")


def _steps() -> list[dict[str, Any]]:
    steps = _load_action()["runs"]["steps"]
    assert isinstance(steps, list)
    return steps


def _run_texts() -> str:
    return "\n".join(str(step.get("run", "")) for step in _steps())


def _single_step(predicate: Any) -> dict[str, Any]:
    matches = [step for step in _steps() if predicate(step)]
    assert len(matches) == 1, f"expected exactly one matching step, found {len(matches)}"
    return matches[0]


def _setup_uv_step() -> dict[str, Any]:
    return _single_step(lambda step: str(step.get("uses", "")).startswith(SETUP_UV_PREFIX))


def _uses_uv_sync(step: dict[str, Any]) -> bool:
    """True when the step actually *runs* ``uv sync`` (a comment mentioning it is not a run)."""
    return any(line.strip().startswith("uv sync") for line in str(step.get("run", "")).splitlines())


def _sync_step() -> dict[str, Any]:
    return _single_step(_uses_uv_sync)


def _index_of_predicate(predicate: Any) -> int:
    for index, step in enumerate(_steps()):
        if predicate(step):
            return index
    raise AssertionError("step not found")


def _index_of_id(step_id: str) -> int:
    return _index_of_predicate(lambda step: str(step.get("id", "")) == step_id)


# --------------------------------------------------------------------------- #
# The composite's shape
# --------------------------------------------------------------------------- #


def test_action_file_exists() -> None:
    assert ACTION_PATH.is_file(), (
        "expected the shared warmup composite at "
        ".github/actions/warmup/action.yml (FR-003/#3283) — see "
        "kitty-specs/ci-pipeline-reinstatement-01M1X35E/tasks/"
        "WP04-warmup-bootstrap-3283.md"
    )


def test_is_a_composite_action() -> None:
    action = _load_action()
    assert action["runs"]["using"] == "composite"


def test_declares_a_mode_input_covering_pr_and_full() -> None:
    action = _load_action()
    inputs = action["inputs"]
    assert "mode" in inputs, "expected an input named 'mode' (pr|full)"
    description = inputs["mode"]["description"]
    assert "pr" in description
    assert "full" in description


def test_mode_defaults_to_pr() -> None:
    action = _load_action()
    assert action["inputs"]["mode"].get("default") == "pr"


# --------------------------------------------------------------------------- #
# The checkout belongs to the caller, never to the composite
# --------------------------------------------------------------------------- #


def test_the_composite_does_not_check_out_the_repository() -> None:
    """A local composite can only be loaded after the caller's checkout, so its own is a duplicate clone."""
    assert CHECKOUT_PREFIX not in _action_text(), (
        "warmup must not run actions/checkout: the caller already checked the repository out to load this "
        "local action, so a second checkout re-clones and can shallow away the caller's full history"
    )


def test_the_composite_fails_closed_when_the_caller_did_not_check_out() -> None:
    precondition = _single_step(lambda step: str(step.get("id", "")) == "require-checkout")
    run = str(precondition["run"])
    assert "pyproject.toml" in run and "uv.lock" in run, "the precondition step must look for the files it needs"
    assert "actions/checkout" in run, "the error must name the fix: the caller adds actions/checkout before this step"
    assert "::error::" in run and "exit 1" in run, "a missing checkout must be a named, fail-closed error, not a fallback"


def _workflow_jobs() -> list[tuple[str, str, dict[str, Any]]]:
    jobs: list[tuple[str, str, dict[str, Any]]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_id, job in (loaded.get("jobs") or {}).items():
            if isinstance(job, dict) and "steps" in job:
                jobs.append((path.name, job_id, job))
    return jobs


def _warmup_callers() -> list[tuple[str, str, dict[str, Any], int]]:
    callers: list[tuple[str, str, dict[str, Any], int]] = []
    for name, job_id, job in _workflow_jobs():
        steps = job.get("steps") or []
        for index, step in enumerate(steps):
            if str(step.get("uses", "")).startswith("./.github/actions/warmup"):
                callers.append((name, job_id, job, index))
    return callers


def test_every_caller_checks_out_before_warmup() -> None:
    """The caller-side half of the contract: warmup never fixes the checkout up for it.

    Every caller must own its checkout: a local composite can only load once the
    repository is on disk, so warmup checking it out again was a duplicate clone.
    How much history that checkout fetches is the caller's own requirement — jobs
    whose tests ``git archive`` historical commits pin ``fetch-depth: 0`` in their
    own tests (e.g. tests/ci/test_reducer_lock_census.py for module-tests) — so this
    contract only insists the checkout exists first.
    """
    callers = _warmup_callers()
    assert callers, "non-vacuity: at least one workflow job must call ./.github/actions/warmup"

    problems = [
        f"{name}:{job_id}: no actions/checkout before ./.github/actions/warmup"
        for name, job_id, job, warmup_index in callers
        if not any(str(step.get("uses", "")).startswith(CHECKOUT_PREFIX) for step in job["steps"][:warmup_index])
    ]
    assert problems == []


# --------------------------------------------------------------------------- #
# Resolution: uv.lock in pr mode, PyPI in full mode
# --------------------------------------------------------------------------- #


def test_resolution_runs_the_one_resolver_for_the_mode() -> None:
    text = str(_single_step(lambda step: "resolve" in str(step.get("id", "")).lower()).get("run", ""))
    assert RESOLVER_RELPATH in text, "the revision must come from the one resolver script, not inline re-implementations"
    assert "--mode" in text and "resolved-events-rev" in text


def test_pr_mode_has_no_stale_pinned_events_rev_authority() -> None:
    assert "pinned-events-rev" not in _action_text(), "the pinned-events-rev input was a second authority that drifted from uv.lock; pr mode reads the lock instead"
    assert "10.4.6" not in _action_text(), "the stale 10.4.6 default must not survive anywhere in the action"


def test_the_resolver_reads_the_lock_in_pr_mode() -> None:
    source = (ROOT / RESOLVER_RELPATH).read_text(encoding="utf-8")
    assert "uv.lock" in source or "lock_path" in source
    assert "10.4.6" not in source


# --------------------------------------------------------------------------- #
# Cache key: lock + revision, separated by mode, relevant to platform/runtime
# --------------------------------------------------------------------------- #


def test_cache_key_derives_from_uv_lock_and_the_resolved_events_rev() -> None:
    """data-model E8: cache key = hash(uv.lock + resolved spec_kitty_events rev)."""
    with_ = _setup_uv_step()["with"]
    assert with_["cache-dependency-glob"] == "uv.lock", "a frozen sync is determined by uv.lock; a broader glob would also re-key on files the install ignores"
    suffix = str(with_["cache-suffix"])
    assert "steps.resolve-rev.outputs.resolved-events-rev" in suffix, "the resolved (lock-derived) rev must key the cache"


def test_cache_key_separates_pr_from_full() -> None:
    """The two modes build different environments (frozen lock vs upgrade-to-latest)."""
    with_ = _setup_uv_step()["with"]
    suffix = str(with_["cache-suffix"])
    assert "inputs.mode" in suffix, "a mode-less key lets a pr-built env satisfy a full-mode run"


def test_cache_key_is_relevant_to_platform_and_runtime() -> None:
    with_ = _setup_uv_step()["with"]
    suffix = str(with_["cache-suffix"])
    assert "runner.os" in suffix, "uv cache entries are not portable across operating systems"
    assert "runner.arch" in suffix, "uv cache entries are not portable across architectures"
    assert with_.get("cache-python") is True, "the managed interpreter lives outside .venv and must be cached with it"


def test_dependency_caching_is_enabled_explicitly() -> None:
    """setup-uv's default ('auto') silently disables caching on some events; the policy is reviewed here."""
    with_ = _setup_uv_step()["with"]
    assert with_.get("enable-cache") is True, "the dependency cache policy must be explicit, not setup-uv's 'auto'"


# --------------------------------------------------------------------------- #
# An honest install every run — no whole-venv cache, no cache-hit skip
# --------------------------------------------------------------------------- #


def test_the_composite_caches_no_virtualenv() -> None:
    cache_steps = [step for step in _steps() if str(step.get("uses", "")).startswith("actions/cache")]
    assert cache_steps == [], (
        "a cached .venv is not self-contained (bin/python symlinks outside it), so it must not be cached; "
        "uv's dependency + managed-interpreter caches make an honest frozen sync cheap instead"
    )
    cached_paths = [str(step.get("with", {}).get("path", "")) for step in _steps()]
    assert not any(".venv" in path for path in cached_paths), cached_paths


def test_the_environment_is_synced_exactly_once_and_never_skipped() -> None:
    sync_steps = [step for step in _steps() if _uses_uv_sync(step)]
    assert len(sync_steps) == 1, "the editable install must run in exactly one step"
    sync = sync_steps[0]
    assert "if" not in sync, "the sync must never be skipped (no cache-hit fast path standing in for a real environment)"
    run = str(sync["run"])
    assert "cache-hit" not in run and "restore-cache" not in run, "a cache-hit flag is not proof the environment is the expected one; the sync always runs"


def test_pr_mode_uses_the_frozen_lock_and_full_mode_upgrades_the_resolved_release() -> None:
    sync = _sync_step()
    run = str(sync["run"])
    assert str(sync.get("env", {}).get("WARMUP_MODE")) == "${{ inputs.mode }}", "the sync must receive the mode"
    assert '"$WARMUP_MODE" = "full"' in run, "the sync must branch on the mode"
    assert "--frozen" in run, "pr mode installs exactly what uv.lock pins"
    assert "--upgrade-package" in run and "spec-kitty-events" in run, "full mode resolves the latest release as an upstream-drift signal"
    assert str(sync.get("env", {}).get("RESOLVED_REV")) == "${{ steps.resolve-rev.outputs.resolved-events-rev }}", (
        "the resolved rev reaches the sync through the environment, never interpolated into its shell body"
    )
    assert '"$RESOLVED_REV"' in run, "full mode installs the revision this run resolved"


def test_the_mode_input_reaches_shell_steps_through_the_environment() -> None:
    """An input interpolated into a `run:` body is shell injection (and unvalidated); pass it via env."""
    for step in _steps():
        assert "${{ inputs.mode }}" not in str(step.get("run", "")), f"step {step.get('name')!r} interpolates inputs.mode into its shell body"
    mode_steps = [step for step in _steps() if str(step.get("env", {}).get("WARMUP_MODE", "")) == "${{ inputs.mode }}"]
    assert len(mode_steps) >= 3, "resolution, sync and verification all need the mode"


def test_the_built_environment_is_verified_against_the_resolved_revision() -> None:
    verify = _single_step(lambda step: "verify" in str(step.get("id", "")).lower())
    run = str(verify["run"])
    assert "importlib.metadata" in run, "the check must read the installed distribution's version"
    assert "spec-kitty-events" in run
    assert str(verify.get("env", {}).get("RESOLVED_REV")) == "${{ steps.resolve-rev.outputs.resolved-events-rev }}", (
        "the resolved rev reaches the verify step through the environment, never interpolated into its shell body"
    )
    assert '"$RESOLVED_REV"' in run, "the installed revision is compared with this run's resolved revision"
    assert "::error::" in run and "exit 1" in run, "a mismatch fails closed — a cache hit cannot excuse it"
    assert _index_of_id("sync-env") < _index_of_id("verify-env"), "verify the environment after the sync"


# --------------------------------------------------------------------------- #
# Packs: restore the cache before the build hook can fetch, then place+verify
# --------------------------------------------------------------------------- #


def test_the_open_packs_cache_is_restored_before_the_environment_sync() -> None:
    """The hatch build hook fetches packs/built-in during `uv sync`; the cache must already be warm."""
    restore_index = _index_of_predicate(lambda step: str(step.get("uses", "")) == RESTORE_OPEN_PACKS)
    sync_index = _index_of_predicate(_uses_uv_sync)
    assert restore_index < sync_index, "restore the open-packs cache before the editable install can fetch packs"
    assert RESTORE_OPEN_PACKS_PATH.is_file(), "the reusable restore-only action must exist for raw pack-sync jobs too"


def test_the_composite_still_places_and_verifies_the_packs_after_the_sync() -> None:
    sync_index = _index_of_predicate(_uses_uv_sync)
    sync_packs_index = _index_of_predicate(lambda step: str(step.get("uses", "")) == SYNC_PACKS)
    assert sync_packs_index > sync_index, "placing packs needs the environment; sync-packs re-verifies every tree against its pin"


# --------------------------------------------------------------------------- #
# Supply chain and outputs
# --------------------------------------------------------------------------- #


def test_no_bare_upload_artifact_used_for_the_env_cache() -> None:
    text = _action_text()
    assert "upload-artifact" not in text, "research D2: cache semantics require actions/cache, not a bare upload-artifact (which conflates cache semantics)"


def _remote_uses(action_path: Path, seen: frozenset[Path] = frozenset()) -> list[str]:
    """Every remote `uses:` of *action_path*, recursing into the local (`./`) composites it calls.

    A local action is checked out with the repository, so it carries no `@ref`;
    the remote actions it calls in turn are what DIR-051 pins.
    """
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    remote: list[str] = []
    for step in action["runs"]["steps"]:
        uses = str(step.get("uses", ""))
        if not uses:
            continue
        if uses.startswith("./"):
            local = (ROOT / uses / "action.yml").resolve()
            assert local.is_file(), f"local action '{uses}' has no action.yml"
            if local not in seen:
                remote.extend(_remote_uses(local, seen | {action_path.resolve()}))
            continue
        remote.append(uses)
    return remote


def test_every_uses_step_is_pinned_to_a_full_commit_sha() -> None:
    """DIR-051 supply-chain: every remote `uses:` must be a full commit SHA, never a moving tag.

    Local `./` composites (e.g. sync-packs, #6451) cannot carry a ref; their own
    remote `uses:` are checked instead.
    """
    uses_steps = _remote_uses(ACTION_PATH)
    assert uses_steps, "expected at least one `uses:` step (setup-uv / cache)"
    for uses in uses_steps:
        _, _, ref = uses.partition("@")
        assert ref and FULL_SHA_RE.match(ref), f"'{uses}' is not pinned to a full 40-character commit SHA (DIR-051)"


def test_local_composite_uses_are_followed() -> None:
    """The pin check reaches the remote actions of the local composites the warmup calls."""
    followed = set(_remote_uses(ACTION_PATH))
    for local in (SYNC_PACKS, RESTORE_OPEN_PACKS):
        local_action = ROOT / local / "action.yml"
        assert local_action.is_file()
        assert set(_remote_uses(local_action)) <= followed, local


def test_composite_exposes_the_built_environment_for_downstream_reuse() -> None:
    action = _load_action()
    outputs = action.get("outputs", {})
    assert outputs, "expected outputs exposing the built env for downstream shard reuse"
    assert any("venv" in name or "env" in name for name in outputs), "expected an output exposing the built environment path"
    assert any("cache-hit" in name or "cache_hit" in name for name in outputs), "expected a cache-hit output so callers can observe the dependency-cache reuse"
