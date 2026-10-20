"""Contract tests for the shared warmup / test-env-creation composite action.

FR-003/#3283 (mission ci-pipeline-reinstatement-01M1X35E, WP04): a shared
composite pre-builds the editable test environment exactly once and
publishes it as a cache-keyed reusable artefact so downstream shards reuse it
instead of re-running the install — dissolving the venv-lock bootstrap
cascade. PR mode resolves a **pinned** `spec_kitty_events` rev (deterministic,
cache-hit, charter pinned-rev policy); nightly/full mode resolves the
**latest** mainline (upstream-drift signal) — see research.md D2 and
data-model.md E8.

The YAML is loaded lazily inside each test (never at import time) so this
module always collects, even on base where
``.github/actions/warmup/action.yml`` does not yet exist — the T018 red-first
state fails for the right reason (missing file), not a collection error.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

ROOT = Path(__file__).resolve().parents[2]
ACTION_PATH = ROOT / ".github" / "actions" / "warmup" / "action.yml"

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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


@pytest.mark.git_repo
def test_checkout_preserves_pinned_history_for_shared_test_clones(tmp_path: Path) -> None:
    """A nested checkout must not undo the module caller's full-history fetch."""

    def git(repo: Path, *args: str) -> bytes:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout

    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "--initial-branch=main")
    git(origin, "config", "user.name", "Warmup history fixture")
    git(origin, "config", "user.email", "warmup@example.invalid")
    git(origin, "config", "commit.gpgsign", "false")
    receipt = b"immutable reviewed receipt\n"
    (origin / "receipt.json").write_bytes(receipt)
    git(origin, "add", ".")
    git(origin, "commit", "-m", "Reviewed receipt")
    pinned = git(origin, "rev-parse", "HEAD").decode().strip()
    (origin / "current.txt").write_text("later source revision\n")
    git(origin, "add", ".")
    git(origin, "commit", "-m", "Current source")
    source = tmp_path / "source"
    git(origin, "clone", "--shared", "--no-checkout", str(origin), str(source))

    # Emulate the composite's checkout after the caller already fetched history.
    # actions/checkout defaults to depth 1 unless its input explicitly says 0.
    checkouts = [step for step in _steps() if str(step.get("uses", "")).startswith("actions/checkout@")]
    assert checkouts, "warmup checkout contract disappeared"
    for checkout in checkouts:
        depth = int(checkout.get("with", {}).get("fetch-depth", 1))
        git(source, "fetch", *([f"--depth={depth}"] if depth else []), "origin", "main")
    assert git(source, "show", f"{pinned}:receipt.json") == receipt

    # Shallowing leaves objects in source, but its test clone loses the old pin.
    clone = tmp_path / "test-clone"
    git(source, "clone", "--shared", "--no-checkout", str(source), str(clone))
    assert git(clone, "show", f"{pinned}:receipt.json") == receipt


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


def test_resolution_behavior_diverges_between_pinned_pr_and_latest_full() -> None:
    """research D2: PR mode pins a recorded rev; full mode resolves latest mainline."""
    steps = _steps()
    resolve_steps = [s for s in steps if "resolve" in str(s.get("id", "")).lower()]
    assert resolve_steps, "expected a spec_kitty_events rev-resolution step"
    run_text = "\n".join(str(s.get("run", "")) for s in resolve_steps)
    assert "full" in run_text and "pr" in run_text, "the resolution step must branch explicitly on mode: pr vs full"
    assert "latest" in run_text.lower() or "pypi" in run_text.lower(), "full mode must resolve the latest spec_kitty_events mainline"
    assert "pinned-events-rev" in run_text or "pinned_events_rev" in run_text, "pr mode must resolve the recorded pinned rev input, not a moving ref"


def test_no_bare_upload_artifact_used_for_the_env_cache() -> None:
    text = _action_text()
    assert "upload-artifact" not in text, "research D2: cache semantics require actions/cache, not a bare upload-artifact (which conflates cache semantics)"


def test_cache_key_derives_from_uv_lock_and_the_resolved_events_rev() -> None:
    """data-model E8: cache key = hash(uv.lock + resolved spec_kitty_events rev)."""
    steps = _steps()
    cache_steps = [s for s in steps if str(s.get("uses", "")).startswith("actions/cache@")]
    assert cache_steps, "expected an actions/cache step publishing the warmup artefact"
    cache_step = cache_steps[0]
    key_expr = cache_step["with"]["key"]

    key_source_steps = [s for s in steps if "cache" in str(s.get("id", "")).lower() and "key" in str(s.get("id", "")).lower()]
    assert key_source_steps, "expected a step computing the warmup cache key"
    key_step = key_source_steps[0]
    run_text = str(key_step.get("run", ""))
    assert "uv.lock" in run_text, "cache key must be derived from uv.lock"
    assert "resolved-events-rev" in run_text or "resolved_events_rev" in run_text, "cache key must be derived from the resolved spec_kitty_events rev"
    assert str(key_step.get("id", "")) in key_expr or "cache-key" in key_expr, "the actions/cache key must consume the computed cache-key step output"


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
    assert uses_steps, "expected at least one `uses:` step (checkout / setup-uv / cache)"
    for uses in uses_steps:
        _, _, ref = uses.partition("@")
        assert ref and FULL_SHA_RE.match(ref), f"'{uses}' is not pinned to a full 40-character commit SHA (DIR-051)"


def test_local_composite_uses_are_followed() -> None:
    """The pin check reaches the remote actions of the local sync-packs composite (#6432)."""
    sync_packs = ROOT / ".github" / "actions" / "sync-packs" / "action.yml"
    own = [str(s["uses"]) for s in yaml.safe_load(sync_packs.read_text(encoding="utf-8"))["runs"]["steps"] if "uses" in s]
    assert own, "sync-packs composite has no remote `uses:` to follow"
    assert set(own) <= set(_remote_uses(ACTION_PATH))


def test_editable_install_runs_exactly_once_gated_on_cache_miss() -> None:
    """#3283: the composite must build the env once and let a cache hit skip the rebuild."""
    steps = _steps()
    cache_steps = [s for s in steps if str(s.get("uses", "")).startswith("actions/cache@")]
    assert cache_steps, "expected an actions/cache step so a valid warmup can be reused"

    build_steps = [s for s in steps if "uses" not in s and "uv sync" in str(s.get("run", ""))]
    assert build_steps, "expected exactly one build step invoking `uv sync`"
    assert len(build_steps) == 1, "the editable install must run in exactly one step — a single pre-warm reused by all downstream shards"
    # #3283 reuse is gated INSIDE the build step's run body (not a bare step-level
    # `if: cache-hit`): a restored `.venv` is not self-contained — its
    # `bin/python` symlinks to a uv-managed interpreter outside the cache — so a
    # blind cache-hit skip reuses a dangling venv and every downstream
    # `.venv/bin/python` dies with exit 127. The step must reuse a VALID cache hit
    # (fast-path) but rebuild when the restored interpreter is broken.
    run_body = str(build_steps[0].get("run", ""))
    assert "cache-hit" in run_body, "the build step must gate the reuse fast-path on the cache-hit signal so a valid cache hit skips the reinstall (#3283)"
    assert ".venv/bin/python" in run_body, (
        "the build step must validate the restored interpreter (and rebuild a dangling-symlink venv), not blindly reuse a cache hit"
    )


def test_composite_exposes_the_built_environment_for_downstream_reuse() -> None:
    action = _load_action()
    outputs = action.get("outputs", {})
    assert outputs, "expected outputs exposing the built env for downstream shard reuse"
    assert any("venv" in name or "env" in name for name in outputs), "expected an output exposing the built environment path"
    assert any("cache-hit" in name or "cache_hit" in name for name in outputs), "expected a cache-hit output so callers can observe single-build-then-reuse"
