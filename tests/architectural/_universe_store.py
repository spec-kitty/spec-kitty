"""Keyed on-disk store behind ``_gate_coverage.collect_universe()``.

Mission ``shared-collection-and-shard-recapture-01M42V58`` (FR-001..FR-007, FR-010, FR-012).
One real ``pytest --collect-only`` of the test tree costs 22-95 s and several gates repeat it.
This module lets a call reuse a stored universe, but **only** when it was produced from the same
committed tree and the same collecting environment; on any doubt the caller collects afresh.

Single authority: the key and the record logic live here and nowhere else (the CI pre-step
imports this module rather than copying it). Every function takes its inputs as parameters, so
tests need no global patching.

Soundness rules (``contracts/collection-store.md``):

* the store is neither read nor written when the checkout has uncommitted changes (untracked
  files included, because an untracked test file changes collection) or the caller passed a
  ``repo_root`` override;
* a record is read back only when its schema, key, count, sanity floor and origin
  (``commit`` and ``tree``) all hold; otherwise it is treated as absent and replaced;
* writing a record evicts every other record file, so the store holds one record;
* a failed collection raises exactly what the collector raised and leaves the store untouched.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import warnings
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.clock import now_utc_iso
from kernel.locks import LockAcquireTimeout, LockNotAcquired, machine_file_lock
from specify_cli.bootstrap.env_file import OperatorEnvFileUnreadableError, load_operator_env_file

Records = list[dict[str, Any]]
Interpreter = tuple[str, int, int, int]

SCHEMA = 1
# Corruption guard, deliberately far below the real universe (54,723 records today) so it never
# needs maintenance (research D-15). It is not a ratchet.
SANITY_FLOOR = 1000

# One fixed lock file inside the store directory. A per-key lock file would escape the eviction.
LOCK_NAME = ".collect.lock"
# Above the 900 s collection timeout, or every waiting worker would give up and collect for itself.
LOCK_TIMEOUT_S = 1200.0

REPORT_ENV_VAR = "SK_GATE_REUSE_REPORT"
_CALLER_ENV_VAR = "PYTEST_CURRENT_TEST"
_DIRECT_CALLER = "direct"
_DIRTY_PATHS_SHOWN = 5
_SUPPORTED_PLATFORMS = ("linux", "darwin")
# Where the operator env file is looked up when the caller names no checkout (the CI pre-step).
_DEFAULT_REPO = Path(__file__).resolve().parents[2]

# --- The environment family of the key (research D-02) ---------------------------------------
# Everything named ``SPEC_KITTY_*`` plus ``PYTEST_ADDOPTS`` can change what is collected (two
# ``SPEC_KITTY_RUN_*`` switches do today), so the family is keyed by prefix, not by a list of
# two: a future switch is covered without an edit.
ENV_INCLUDED_PREFIXES: tuple[str, ...] = ("SPEC_KITTY_",)
ENV_INCLUDED_NAMES: frozenset[str] = frozenset({"PYTEST_ADDOPTS"})
# Variables the test session sets for itself. A CI pre-step is a plain ``python -m`` process that
# has none of them, so keying them would stop every pre-step key from matching a test's key.
# ``test_universe_store.py`` launches a fresh pytest session and fails when it sets a
# ``SPEC_KITTY_*`` name that is not listed here.
ENV_EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        # tests/conftest.py ``pytest_configure``: ``os.environ.setdefault`` into every pytest process.
        "SPEC_KITTY_REAL_HOME_FOR_TESTS",
        # tests/conftest.py ``pytest_configure`` and the autouse ``_enable_saas_sync_feature_flag``.
        "SPEC_KITTY_ENABLE_SAAS_SYNC",
        # tests/conftest.py session fixture that builds the isolated test venv.
        "SPEC_KITTY_TEST_VENV",
        # ``scripts/docs/*.py`` do ``os.environ.setdefault`` on import; two architectural modules
        # (``test_no_retired_subsystems.py``, ``test_p1_planted_regression.py``) import them, so
        # every worker that collects those modules has it, and a plain pre-step process does not.
        "SPEC_KITTY_NO_UPGRADE_CHECK",
    },
)

# Outcomes and reasons of the reuse report line (``data-model.md``).
REUSED = "reused"
COLLECTED = "collected"
BYPASSED = "bypassed"
NO_RECORD = "no-record"
INVALID_RECORD = "invalid-record"
ORIGIN_MISMATCH = "origin-mismatch"
DIRTY_CHECKOUT = "dirty-checkout"
ROOT_OVERRIDE = "root-override"
UNSUPPORTED_PLATFORM = "unsupported-platform"
# Not in the contract table: git could not describe the checkout (not a repository, git missing).
GIT_UNAVAILABLE = "git-unavailable"
# Not in the contract table: the operator env file exists but cannot be read, so the family is unknown.
ENV_FILE_UNREADABLE = "env-file-unreadable"

LockFactory = Callable[..., AbstractContextManager[Any]]


@dataclass(frozen=True)
class CheckoutState:
    """What git says about a checkout: its commit, its tree and any uncommitted paths."""

    commit: str
    tree: str
    dirty_paths: tuple[str, ...]


@dataclass(frozen=True)
class Outcome:
    """What one request did; serialised as the reuse report line."""

    outcome: str
    reason: str | None = None
    key: str | None = None
    detail: str | None = None
    dirty_paths: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Key
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str | None:
    """Run ``git -C repo ...``; stdout on success, ``None`` on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def checkout_state(repo: Path) -> CheckoutState | None:
    """Return commit, tree and uncommitted paths of ``repo``, or ``None`` when git cannot say."""
    ids = _git(repo, "rev-parse", "HEAD", "HEAD^{tree}")
    status = _git(repo, "status", "--porcelain", "--untracked-files=normal")
    if ids is None or status is None:
        return None
    parts = ids.split()
    if len(parts) != 2:
        return None
    dirty = tuple(line[3:] for line in status.splitlines() if line.strip())
    return CheckoutState(commit=parts[0], tree=parts[1], dirty_paths=dirty)


def _digest(text: str) -> str:
    # A cache key, not a charter hash: blake2b keeps this clear of the sha256 ban (TID251) on purpose.
    return hashlib.blake2b(text.encode("utf-8"), digest_size=32).hexdigest()


@functools.cache
def dependency_digest() -> str:
    """Digest of the sorted ``name==version`` of every installed distribution."""
    pairs = {f"{re.sub(r'[-_.]+', '-', name).lower()}=={dist.version}" for dist in importlib.metadata.distributions() if (name := dist.metadata["Name"])}
    return _digest("\n".join(sorted(pairs)))


def operator_environment(environ: Mapping[str, str] | None = None, *, repo: Path | None = None) -> dict[str, str]:
    """A copy of ``environ`` after the product's own operator env file loader ran on it.

    ``specify_cli`` seeds ``<state-root>/.kitty.env`` and ``<repo>/.kittify/.kitty.env`` into
    ``os.environ`` (``setdefault``: a real value wins) the moment it is imported, so a pytest session
    has those variables and a plain pre-step process may not. Applying the same loader to a copy
    makes the keyed family the same in both, and makes a change of the file change the key. The
    given mapping and ``os.environ`` are never mutated.

    Raises ``OperatorEnvFileUnreadableError`` when a configured file exists but cannot be read.
    """
    merged = dict(os.environ if environ is None else environ)
    load_operator_env_file(start=repo or _DEFAULT_REPO, environ=merged)
    return merged


def environment_family(environ: Mapping[str, str] | None = None, *, repo: Path | None = None) -> dict[str, str]:
    """The keyed part of the environment: ``SPEC_KITTY_*`` and ``PYTEST_ADDOPTS``, minus exclusions.

    Taken after the operator env file was overlaid (see :func:`operator_environment`).
    """
    env = operator_environment(environ, repo=repo)
    return {name: value for name, value in sorted(env.items()) if _in_family(name)}


def _in_family(name: str) -> bool:
    if name in ENV_EXCLUDED_NAMES:
        return False
    return name.startswith(ENV_INCLUDED_PREFIXES) or name in ENV_INCLUDED_NAMES


def _current_interpreter() -> Interpreter:
    version = sys.version_info
    return (sys.implementation.name, version.major, version.minor, version.micro)


def compute_key(
    tree: str,
    *,
    environ: Mapping[str, str] | None = None,
    interpreter: Interpreter | None = None,
    platform: str | None = None,
    dependencies: str | None = None,
    repo: Path | None = None,
) -> str:
    """Hex digest of (committed tree, interpreter, platform, distributions, environment family).

    ``repo`` is where the operator env file tier is looked up; it defaults to this checkout.
    """
    payload = {
        "tree": tree,
        "interpreter": list(interpreter or _current_interpreter()),
        "platform": platform or sys.platform,
        "dependencies": dependencies if dependencies is not None else dependency_digest(),
        "environment": environment_family(environ, repo=repo),
    }
    return _digest(json.dumps(payload, sort_keys=True))


def collection_key(
    repo: Path,
    *,
    environ: Mapping[str, str] | None = None,
    interpreter: Interpreter | None = None,
    platform: str | None = None,
    dependencies: str | None = None,
) -> str | None:
    """The collection key of ``repo``, or ``None`` when the checkout is dirty or git fails."""
    state = checkout_state(repo)
    if state is None or state.dirty_paths:
        return None
    return compute_key(
        state.tree,
        environ=environ,
        interpreter=interpreter,
        platform=platform,
        dependencies=dependencies,
        repo=repo,
    )


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


def store_dir(repo: Path) -> Path:
    """The one git-ignored location of the store (``.pytest_cache`` is ignored repository-wide)."""
    return repo / ".pytest_cache" / "universe-store"


def record_path(store: Path, key: str) -> Path:
    return store / f"{key}.json"


def _is_valid_payload(data: object, key: str) -> bool:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("key") != key:
        return False
    records = data.get("records")
    return isinstance(records, list) and data.get("count") == len(records) and len(records) >= SANITY_FLOOR


def load_record(store: Path, key: str, *, commit: str, tree: str) -> tuple[Records | None, str]:
    """Return ``(records, REUSED)`` for a valid record, else ``(None, reason)``."""
    path = record_path(store, key)
    if not path.exists():
        return None, NO_RECORD
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, INVALID_RECORD
    if not _is_valid_payload(data, key):
        return None, INVALID_RECORD
    if data.get("commit") != commit or data.get("tree") != tree:
        return None, ORIGIN_MISMATCH
    records: Records = data["records"]
    return records, REUSED


def write_record(store: Path, key: str, *, commit: str, tree: str, records: Records) -> None:
    """Write ``records`` atomically under ``key`` and evict every other record file."""
    store.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "key": key,
        "commit": commit,
        "tree": tree,
        "created_at": now_utc_iso(),
        "count": len(records),
        "records": records,
    }
    handle, tmp_name = tempfile.mkstemp(dir=store, prefix=".record-", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, separators=(",", ":"))
        os.replace(tmp, record_path(store, key))
    finally:
        tmp.unlink(missing_ok=True)
    for other in store.glob("*.json"):
        if other.name != f"{key}.json":
            other.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Report line (FR-010)
# ---------------------------------------------------------------------------


def _caller(environ: Mapping[str, str]) -> str:
    current = environ.get(_CALLER_ENV_VAR)
    return current.split("::", 1)[0] if current else _DIRECT_CALLER


def _report_line(outcome: Outcome, *, caller: str, seconds: float) -> str:
    line: dict[str, Any] = {
        "outcome": outcome.outcome,
        "reason": outcome.reason,
        "key": outcome.key,
        "caller": caller,
        "seconds": round(seconds, 3),
    }
    if outcome.detail is not None:
        line["detail"] = outcome.detail
    if outcome.dirty_paths:
        line["dirty_paths"] = list(outcome.dirty_paths)
    return json.dumps(line)


def _append_report(path: str, line: str) -> None:
    """Append one line with a single ``write`` so parallel workers never interleave partial lines."""
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(descriptor, f"{line}\n".encode())
    finally:
        os.close(descriptor)


def _emit_report(environ: Mapping[str, str], outcome: Outcome, *, caller: str | None, seconds: float) -> None:
    path = environ.get(REPORT_ENV_VAR)
    if not path:
        return
    line = _report_line(outcome, caller=caller or _caller(environ), seconds=seconds)
    try:
        _append_report(path, line)
    except OSError as exc:
        warnings.warn(f"could not append the universe reuse report to {path}: {exc}", stacklevel=2)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _describe(failure: Exception) -> str:
    return f"{type(failure).__name__}: {failure}"


def _acquire_lock(stack: ExitStack, lock_factory: LockFactory, store: Path, timeout_s: float) -> Exception | None:
    """Create the store directory and take the lock; return the failure instead of raising."""
    try:
        store.mkdir(parents=True, exist_ok=True)
        stack.enter_context(lock_factory(store / LOCK_NAME, blocking=True, timeout_s=timeout_s))
    except (OSError, LockAcquireTimeout, LockNotAcquired) as failure:
        return failure
    return None


def _moved_during_collection(repo: Path, before: CheckoutState) -> str | None:
    """Describe how the checkout differs from ``before`` now, or ``None`` when it is the same and clean.

    The lock wait and the collection can take minutes; a commit, a branch switch or an edit in that
    time means the collected universe describes content the key and origin do not.
    """
    after = checkout_state(repo)
    if after is None:
        return "git can no longer describe the checkout"
    if (after.commit, after.tree) != (before.commit, before.tree):
        return f"commit {before.commit[:12]} -> {after.commit[:12]}"
    if after.dirty_paths:
        return f"uncommitted changes in {', '.join(after.dirty_paths[:_DIRTY_PATHS_SHOWN])}"
    return None


def _store_fresh(repo: Path, store: Path, key: str, state: CheckoutState, fresh: Records) -> str | None:
    """Persist ``fresh`` when it is worth reading back; return a detail when it was not stored."""
    if len(fresh) < SANITY_FLOOR:
        return "not stored: below the sanity floor"
    moved = _moved_during_collection(repo, state)
    if moved is not None:
        return f"not stored: the checkout changed during the collection ({moved})"
    try:
        write_record(store, key, commit=state.commit, tree=state.tree, records=fresh)
    except OSError as failure:
        return f"not stored: {_describe(failure)}"
    return None


def _read_or_collect(
    repo: Path,
    collect: Callable[[], Records],
    store: Path,
    key: str,
    state: CheckoutState,
) -> tuple[Records, Outcome]:
    stored, reason = load_record(store, key, commit=state.commit, tree=state.tree)
    if stored is not None:
        return stored, Outcome(REUSED, key=key)
    fresh = collect()
    detail = _store_fresh(repo, store, key, state, fresh)
    return fresh, Outcome(COLLECTED, reason, key=key, detail=detail)


def _state_and_key(
    repo: Path,
    *,
    environ: Mapping[str, str],
    interpreter: Interpreter | None,
    platform: str,
    dependencies: str | None,
) -> tuple[CheckoutState, str] | Outcome:
    """The clean checkout state and its key, or the bypass outcome that says why there is none."""
    state = checkout_state(repo)
    if state is None:
        return Outcome(BYPASSED, GIT_UNAVAILABLE)
    if state.dirty_paths:
        return Outcome(BYPASSED, DIRTY_CHECKOUT, dirty_paths=state.dirty_paths[:_DIRTY_PATHS_SHOWN])
    try:
        key = compute_key(
            state.tree,
            environ=environ,
            interpreter=interpreter,
            platform=platform,
            dependencies=dependencies,
            repo=repo,
        )
    except OperatorEnvFileUnreadableError as failure:
        return Outcome(BYPASSED, ENV_FILE_UNREADABLE, detail=_describe(failure))
    return state, key


def _decide(
    repo: Path,
    collect: Callable[[], Records],
    *,
    root_override: bool,
    environ: Mapping[str, str],
    interpreter: Interpreter | None,
    platform: str,
    dependencies: str | None,
    lock_factory: LockFactory,
    lock_timeout_s: float,
) -> tuple[Records, Outcome]:
    if root_override:
        return collect(), Outcome(BYPASSED, ROOT_OVERRIDE)
    if not platform.startswith(_SUPPORTED_PLATFORMS):
        return collect(), Outcome(BYPASSED, UNSUPPORTED_PLATFORM)
    look = functools.partial(_state_and_key, repo, environ=environ, interpreter=interpreter, platform=platform, dependencies=dependencies)
    # This first look only decides whether the store is worth a lock at all.
    first = look()
    if isinstance(first, Outcome):
        return collect(), first
    store = store_dir(repo)
    with ExitStack() as stack:
        lock_failure = _acquire_lock(stack, lock_factory, store, lock_timeout_s)
        if lock_failure is not None:
            return collect(), Outcome(BYPASSED, UNSUPPORTED_PLATFORM, detail=_describe(lock_failure))
        # The wait can last minutes: the key, the dirty check, the record check and the origin
        # all use the state as it is now, not as it was before the wait.
        current = look()
        if isinstance(current, Outcome):
            return collect(), current
        state, key = current
        return _read_or_collect(repo, collect, store, key, state)


def collect_through_store(
    repo: Path,
    collect: Callable[[], Records],
    *,
    root_override: bool = False,
    environ: Mapping[str, str] | None = None,
    caller: str | None = None,
    interpreter: Interpreter | None = None,
    platform: str | None = None,
    dependencies: str | None = None,
    lock_factory: LockFactory = machine_file_lock,
    lock_timeout_s: float = LOCK_TIMEOUT_S,
) -> Records:
    """Return the universe of ``repo``, reusing the stored one when the key and origin match.

    ``collect`` performs one real collection. It is called at most once per request, while the
    store lock is held, so concurrent processes serialise on it and the later ones reuse the
    record the first wrote. An error it raises propagates unchanged with the store untouched. Every other store-layer failure falls back to ``collect``
    and is reported as ``bypassed``; the store never raises in place of returning a universe.
    """
    env = os.environ if environ is None else environ
    started = time.perf_counter()
    records, outcome = _decide(
        repo,
        collect,
        root_override=root_override,
        environ=env,
        interpreter=interpreter,
        platform=platform or sys.platform,
        dependencies=dependencies,
        lock_factory=lock_factory,
        lock_timeout_s=lock_timeout_s,
    )
    _emit_report(env, outcome, caller=caller, seconds=time.perf_counter() - started)
    return records
