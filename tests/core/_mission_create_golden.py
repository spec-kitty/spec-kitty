"""Zero-patch golden behaviour matrix harness for ``create_mission_core``.

The create-behaviour regression net: regenerate only for an intended behaviour
change (``SPEC_KITTY_REGEN_GOLDEN=1``, serial). The golden test modules
(``tests/core/test_mission_creation_golden_*.py``), this harness and the
snapshots under ``tests/core/golden/`` form the behaviour-freeze set, together
with ``tests/_support/git_template/**`` and ``tests/_factories/__init__.py``.
A behaviour-preserving change proves byte-identical behaviour by running the
matrix with **0 diff lines** in that set. Never widen the
normaliser, drop a captured key or edit a snapshot to make a refactor pass.

What one cell records (``run_cell``):

* ``pre`` / ``post``: the repository state before and after the call
  (:func:`observe_state`): branches, worktrees, HEAD per checkout,
  ``git status --porcelain`` per checkout, every mission directory's
  ``meta.json`` (sorted, plus its key order as written) and file tree, every
  ``status.events.jsonl`` event-type sequence (with the checkout that holds
  it), and the full message (``%B``, as lines, normalised like every other
  string -- so trailers such as the coordination seed trailer are pinned) plus
  the changed paths of every commit added to each branch whose tip moved.
* ``watched`` (only when ``run_cell(watch=...)`` names other repositories):
  the same ``pre`` / ``post`` capture for each, plus its working-tree file
  list, so residue written into a repository the call must not touch is caught.
* ``outcome``: the plain-data ``MissionCreationResult`` fields on success, or
  the refusal's ``exc_type`` (``__qualname__`` only -- the module path is NOT
  pinned, because the split moves the error classes), ``message`` and
  ``error_code``.

The repository fixture is vendored here on purpose: it uses only
``clone_template`` and ``provision_test_charter`` and never imports
``tests/_factories/coord_mission.py``, so a factory change cannot move the matrix.

No attribute patching or mocking appears in the golden set. Identity
cannot be injected without a patch, so the two cells that need a known mid8
use :func:`await_fresh_mid8_bucket`: mid8 is the ULID's millisecond timestamp
in 1,024 ms buckets, so a prediction made at the start of a bucket holds for
the next ~900 ms. The cell then checks the prediction was used and fails
loudly if it was not, instead of snapshotting a wrong state.
"""

from __future__ import annotations

import dataclasses
import difflib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from ulid import ULID

from specify_cli.core.mission_creation import MissionCreationResult
from tests._factories import provision_test_charter
from tests._support.git_template import clone_template

# ---------------------------------------------------------------------------
# Normaliser whitelist -- regenerate only for an intended behaviour change
# (SPEC_KITTY_REGEN_GOLDEN=1, serial). These are the ONLY rewrites applied to
# an observed cell. Do not add patterns, do not widen them.
# ---------------------------------------------------------------------------

#: A 26-char Crockford-base32 ULID (mission_id).
_ULID_RE = re.compile(r"(?<![0-9A-Za-z])[0-9A-HJKMNP-TV-Z]{26}(?![0-9A-Za-z])")
#: The mid8 body that follows a known slug (``<slug>-<mid8>``).
_MID8_BODY = r"[0-9A-Z]{8}"
#: ISO-8601 timestamps.
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")
#: Placeholders.
_TMP_TOKEN = "<TMP>"
_TS_TOKEN = "<TS>"

# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------

_GOLDEN_DIR = Path(__file__).parent / "golden"
_SPEC_KITTY_CHECKOUT = Path(__file__).resolve().parents[2]
REGEN_ENV = "SPEC_KITTY_REGEN_GOLDEN"
_SRC_DIR = "src/"

# ---------------------------------------------------------------------------
# Fixture vocabulary
# ---------------------------------------------------------------------------

PRIMARY_BRANCH = "main"
TOPIC_BRANCH = "topic"
_MID8_BUCKET_MS = 1024
_MID8_BUCKET_MARGIN_MS = 100
_BUCKET_ATTEMPTS = 3
_KITTY_SPECS = "kitty-specs"
_STATUS_LOG = "status.events.jsonl"
_DETACHED = "(detached)"


def git(cwd: Path, *args: str, check: bool = True) -> str:
    """Run ``git`` in *cwd* and return its stdout (raises on failure when *check*)."""
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)
    return completed.stdout


def write_protected_branches(repo: Path, branches: Sequence[str]) -> None:
    """Append ``protection.protected_branches: [...]`` to ``.kittify/config.yaml``.

    A frozen local copy of the protected-branches writer: a
    separate top-level YAML key after the provisioned
    ``mission_type_activations`` block.
    """
    config_path = repo / ".kittify" / "config.yaml"
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    protected_lines = "".join(f"    - {branch}\n" for branch in branches)
    config_path.write_text(existing + f"\nprotection:\n  protected_branches:\n{protected_lines}", encoding="utf-8")


def commit_kittify(repo: Path, message: str = "chore(fixture): provision charter") -> None:
    """Commit the ``.kittify/`` directory on the current branch."""
    git(repo, "add", ".kittify")
    git(repo, "commit", "-m", message)


def build_repo(
    tmp_root: Path,
    *,
    target: str = TOPIC_BRANCH,
    protected: Sequence[str] = (),
    origin_head: bool = True,
) -> Path:
    """A provisioned repository at ``<tmp_root>/repo`` on branch *target*.

    ``clone_template`` gives one commit on ``main`` with an ``origin`` whose
    ``origin/HEAD`` names ``main``. The charter (plus *protected* as
    ``protection.protected_branches``) is committed on ``main``; then *target*
    is checked out (created from ``main``) when it is not ``main``.
    ``origin_head=False`` deletes ``refs/remotes/origin/HEAD``.
    """
    repo = clone_template(tmp_root / "repo")
    provision_test_charter(repo)
    if protected:
        write_protected_branches(repo, protected)
    commit_kittify(repo)
    if not origin_head:
        git(repo, "remote", "set-head", "origin", "--delete")
    if target != PRIMARY_BRANCH:
        git(repo, "checkout", "-b", target)
    return repo


#: The create-flag variants every topology family is crossed with (``summary``
#: -- non-default friendly name and purpose fields -- is built per slug).
FLAG_VARIANTS: dict[str, dict[str, Any]] = {
    "plain": {},
    "pr_bound": {"pr_bound": True},
    "retention": {"retain_branches": True, "retain_worktrees": True},
    "documentation": {"mission": "documentation"},
}
SUMMARY_VARIANT = "summary"


def variant_kwargs(slug: str, variant: str) -> dict[str, Any]:
    """The ``create_mission_core`` keyword arguments of *variant* for *slug*."""
    return summary(slug) if variant == SUMMARY_VARIANT else FLAG_VARIANTS[variant]


def summary(slug: str) -> dict[str, str]:
    """Non-default friendly name / purpose fields for *slug*."""
    title = slug.replace("-", " ")
    return {
        "friendly_name": f"Golden {title.title()}",
        "purpose_tldr": f"Pin the {title} create behaviour.",
        "purpose_context": f"This mission pins how {title} is created so the decomposition can prove it changes nothing observable.",
    }


def commit_spec(repo: Path, feature_dir: Path) -> None:
    """Commit substantive ``spec.md`` content so the mission reads as live (#4033)."""
    spec = feature_dir / "spec.md"
    spec.write_text("# Spec\n\nSubstantive spec content.\n", encoding="utf-8")
    git(repo, "add", str(spec.relative_to(repo)))
    git(repo, "commit", "-m", f"Add spec for {feature_dir.name}")


# ---------------------------------------------------------------------------
# mid8 bucket control (predict-then-plant)
# ---------------------------------------------------------------------------


def await_fresh_mid8_bucket() -> str:
    """Wait until a mid8 bucket has just started and return its mid8.

    mid8 is the first 8 ULID characters: the millisecond timestamp in
    1,024 ms buckets. Returning only within the first 100 ms of a bucket
    leaves ~900 ms in which a fresh ``ULID()`` keeps this mid8.
    """
    while True:
        probe = ULID()
        offset = probe.milliseconds % _MID8_BUCKET_MS
        if offset < _MID8_BUCKET_MARGIN_MS:
            return str(probe)[:8]
        time.sleep((_MID8_BUCKET_MS - offset) / 1000)


def await_mid8_bucket_after(prior_mid8: str, *, timeout_s: float = 5.0) -> str:
    """Wait until the current mid8 bucket differs from *prior_mid8*; return it.

    Unlike a second :func:`await_fresh_mid8_bucket`, this cannot hand back the
    bucket a create just used: a warm create takes about 100 ms, so a fresh
    "bucket just started" await issued straight after it can return the very
    same bucket. Time is monotonic, so once the bucket differs from the prior
    one, every later ``ULID()`` also differs from it.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        probe = ULID()
        current = str(probe)[:8]
        if current != prior_mid8:
            return current
        if time.monotonic() >= deadline:
            raise TimeoutError(f"mid8 bucket {prior_mid8!r} did not roll over within {timeout_s} s")
        remaining_ms = _MID8_BUCKET_MS - probe.milliseconds % _MID8_BUCKET_MS
        time.sleep(remaining_ms / 1000)


def still_in_bucket(predicted_mid8: str) -> bool:
    """True while a fresh ``ULID()`` still carries *predicted_mid8*.

    Time is monotonic, so when this holds AFTER a create, the create minted
    *predicted_mid8* -- a behaviour-independent proof the planted state was hit.
    """
    return str(ULID())[:8] == predicted_mid8


# ---------------------------------------------------------------------------
# State capture
# ---------------------------------------------------------------------------


def branch_tips(repo: Path) -> dict[str, str]:
    """``{branch: sha}`` for every local branch."""
    out = git(repo, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads")
    return dict(line.split(" ", 1) for line in out.splitlines() if line)


def _worktrees(repo: Path) -> list[tuple[Path, str]]:
    """``(path, branch-or-'(detached)')`` per registered worktree, main checkout first."""
    entries: list[tuple[Path, str]] = []
    path: Path | None = None
    branch = _DETACHED
    for line in [*git(repo, "worktree", "list", "--porcelain").splitlines(), ""]:
        if line.startswith("worktree "):
            path = Path(line.removeprefix("worktree "))
            branch = _DETACHED
        elif line.startswith("branch "):
            branch = line.removeprefix("branch refs/heads/")
        elif not line and path is not None:
            entries.append((path, branch))
            path = None
    return entries[:1] + sorted(entries[1:])


def _head(checkout: Path) -> str:
    completed = subprocess.run(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=checkout, capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else _DETACHED


def _new_commits(repo: Path, base_tips: dict[str, str]) -> dict[str, list[dict[str, list[str]]]]:
    """Full messages (``%B`` lines) and changed paths of the commits each moved branch gained."""
    after = branch_tips(repo)
    known = sorted(set(base_tips.values()))
    moved: dict[str, list[dict[str, list[str]]]] = {}
    for branch, tip in sorted(after.items()):
        if base_tips.get(branch) == tip:
            continue
        shas = git(repo, "rev-list", "--reverse", tip, "--not", *known).split() if known else git(repo, "rev-list", "--reverse", tip).split()
        moved[branch] = [
            {
                "message": git(repo, "log", "-1", "--format=%B", sha).strip().splitlines(),
                "paths": sorted(git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha).split()),
            }
            for sha in shas
        ]
    return moved


def _tree(directory: Path) -> list[str]:
    """Sorted paths under *directory*; directories carry a trailing ``/``."""
    return sorted(f"{p.relative_to(directory).as_posix()}{'/' if p.is_dir() else ''}" for p in directory.rglob("*"))


def _read_meta(meta_path: Path) -> tuple[Any, list[str] | None]:
    try:
        parsed = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return meta_path.read_text(encoding="utf-8"), None
    return parsed, list(parsed) if isinstance(parsed, dict) else None


def _missions(checkout: Path, label: str) -> dict[str, dict[str, Any]]:
    specs = checkout / _KITTY_SPECS
    if not specs.is_dir():
        return {}
    missions: dict[str, dict[str, Any]] = {}
    for mission_dir in sorted(p for p in specs.iterdir() if p.is_dir()):
        record: dict[str, Any] = {"tree": _tree(mission_dir)}
        meta_path = mission_dir / "meta.json"
        if meta_path.is_file():
            record["meta"], record["meta_key_order"] = _read_meta(meta_path)
        missions[f"{label}/{_KITTY_SPECS}/{mission_dir.name}"] = record
    return missions


def _status_logs(checkout: Path, label: str) -> dict[str, list[str]]:
    specs = checkout / _KITTY_SPECS
    if not specs.is_dir():
        return {}
    logs: dict[str, list[str]] = {}
    for log in sorted(specs.rglob(_STATUS_LOG)):
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        logs[f"{label}/{log.relative_to(checkout).as_posix()}"] = [str(row.get("event_type") or f"lane:{row.get('to_lane')}") for row in rows]
    return logs


def observe_state(repo: Path, *, base_tips: dict[str, str]) -> dict[str, Any]:
    """The observable repository state, every checkout included."""
    worktrees = _worktrees(repo)
    labelled = [(os.path.relpath(path, repo.parent), path, branch) for path, branch in worktrees]
    state: dict[str, Any] = {
        "branches": sorted(branch_tips(repo)),
        "worktrees": [{"path": label, "branch": branch} for label, _path, branch in labelled],
        "head": {},
        "porcelain": {},
        "missions": {},
        "status_log": {},
        "new_commits": _new_commits(repo, base_tips),
    }
    for label, path, _branch in labelled:
        if not path.is_dir():
            continue
        state["head"][label] = _head(path)
        state["porcelain"][label] = sorted(git(path, "status", "--porcelain=v1", "--untracked-files=all").splitlines())
        state["missions"].update(_missions(path, label))
        state["status_log"].update(_status_logs(path, label))
    return state


def _working_tree(repo: Path) -> list[str]:
    """Sorted working-tree paths of *repo*, ``.git`` excluded."""
    return [path for path in _tree(repo) if path != ".git" and not path.startswith(".git/")]


def _observe_watched(repo: Path, base_tips: dict[str, str]) -> dict[str, Any]:
    return {**observe_state(repo, base_tips=base_tips), "working_tree": _working_tree(repo)}


def _plain(value: Any) -> Any:
    """Plain JSON data: paths as strings, dataclasses as their ``repr`` fields."""
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value) if f.repr}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def outcome_of(call: Callable[[], MissionCreationResult]) -> dict[str, Any]:
    """Run *call*; return the result fields, or the refusal's kind, message and code."""
    try:
        result = call()
    except Exception as exc:
        return {
            "exc_type": type(exc).__qualname__,
            "message": str(exc),
            "error_code": getattr(exc, "error_code", None),
        }
    return {"result": _plain(result)}


def run_cell(
    repo: Path,
    tmp_root: Path,
    call: Callable[[], MissionCreationResult],
    *,
    slugs: Sequence[str],
    watch: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Capture ``pre``, run *call*, capture ``outcome`` and ``post``; return the normalised cell.

    *watch* maps a label to another repository whose ``pre`` / ``post`` state
    (plus working-tree file list) is captured under ``watched`` in the same cell.
    """
    watched_repos = dict(sorted((watch or {}).items()))
    tips = branch_tips(repo)
    watched_tips = {label: branch_tips(path) for label, path in watched_repos.items()}
    pre = observe_state(repo, base_tips=tips)
    watched_pre = {label: _observe_watched(path, watched_tips[label]) for label, path in watched_repos.items()}
    outcome = outcome_of(call)
    post = observe_state(repo, base_tips=tips)
    raw: dict[str, Any] = {"pre": pre, "outcome": outcome, "post": post}
    if watched_repos:
        raw["watched"] = {label: {"pre": watched_pre[label], "post": _observe_watched(path, watched_tips[label])} for label, path in watched_repos.items()}
    cell: dict[str, Any] = normalise(raw, tmp_root=tmp_root, slugs=slugs)
    return cell


def run_cell_in_one_mid8_bucket(
    tmp_path: Path,
    build: Callable[[Path], Path],
    plant: Callable[[Path, str], Callable[[], MissionCreationResult]],
    *,
    slugs: Sequence[str],
) -> dict[str, Any]:
    """Predict-then-plant for a cell whose state depends on the minted mid8.

    Per attempt: ``build(attempt_root)`` makes the repository, the next mid8
    bucket is awaited and predicted, ``plant(repo, predicted_mid8)`` plants the
    mid8-dependent state and returns the create call, and :func:`run_cell`
    captures it. The cell is accepted only when the whole call stayed inside
    the predicted bucket (:func:`still_in_bucket`); otherwise the attempt is
    discarded and retried in a fresh directory, and after
    ``_BUCKET_ATTEMPTS`` misses the cell fails loudly. Paths normalise against
    the attempt root, so an accepted attempt is byte-identical to any other.
    """
    for attempt in range(_BUCKET_ATTEMPTS):
        root = tmp_path / f"attempt-{attempt}"
        repo = build(root)
        predicted = await_fresh_mid8_bucket()
        call = plant(repo, predicted)
        observed = run_cell(repo, root, call, slugs=slugs)
        if still_in_bucket(predicted):
            return observed
    pytest.fail(f"the create left its predicted mid8 bucket in {_BUCKET_ATTEMPTS} attempts; the planted state was never hit")


# ---------------------------------------------------------------------------
# Normalisation (whitelist only)
# ---------------------------------------------------------------------------


def _strings(obj: Any) -> Iterator[str]:
    """Every string in *obj* (keys included), in canonical sort-keyed order."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for key in sorted(obj):
            yield key
            yield from _strings(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            yield from _strings(item)


def _rewrite(obj: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, dict):
        return {fn(k): _rewrite(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rewrite(v, fn) for v in obj]
    return obj


def _first_seen(pattern: re.Pattern[str], obj: Any, group: int = 0) -> list[str]:
    seen: list[str] = []
    for text in _strings(obj):
        for match in pattern.finditer(text):
            token = match.group(group)
            if token not in seen:
                seen.append(token)
    return seen


def normalise(obj: Any, *, tmp_root: Path, slugs: Sequence[str]) -> Any:
    """Apply the frozen whitelist: temp root, ULIDs, mid8s, ISO timestamps.

    ULIDs and mid8s are numbered in order of first appearance (``<ULID#1>``,
    ``<MID8#1>`` ...) so a cell holding several missions stays exact. A mid8
    is recognised only as ``<known-slug>-<8 chars>`` and then replaced wherever
    it occurs (dir names, branch names, worktree paths, meta values, messages).
    """
    roots = sorted({str(tmp_root), str(tmp_root.resolve())}, key=len, reverse=True)

    def strip_tmp(text: str) -> str:
        for root in roots:
            text = text.replace(root, _TMP_TOKEN)
        return text

    obj = _rewrite(obj, strip_tmp)
    mid8_re = re.compile("(?:" + "|".join(re.escape(s) for s in slugs) + r")-(" + _MID8_BODY + r")(?![0-9A-Za-z])") if slugs else None
    mid8s = _first_seen(mid8_re, obj, group=1) if mid8_re is not None else []
    ulids = _first_seen(_ULID_RE, obj)
    ulid_tokens = {u: f"<ULID#{i}>" for i, u in enumerate(ulids, start=1)}
    mid8_tokens = [(m, f"<MID8#{i}>") for i, m in enumerate(mid8s, start=1)]

    def rewrite(text: str) -> str:
        text = _ULID_RE.sub(lambda m: ulid_tokens[m.group(0)], text)
        for mid8, token in mid8_tokens:
            text = text.replace(mid8, token)
        return _TS_RE.sub(_TS_TOKEN, text)

    return _rewrite(obj, rewrite)


# ---------------------------------------------------------------------------
# Snapshot comparison / regeneration
# ---------------------------------------------------------------------------


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _snapshot_path(family: str) -> Path:
    return _GOLDEN_DIR / f"mission_create_{family}.json"


def _base_commit(existing: str | None) -> str:
    """Keep *existing* while ``src/`` still equals it (worktree included); else ``HEAD``.

    The base commit names the code the snapshot was captured on, so a
    regeneration on the same code reproduces the file byte for byte even after
    test-only commits moved ``HEAD``.
    """
    if existing:
        unchanged = subprocess.run(
            ["git", "diff", "--quiet", existing, "--", _SRC_DIR],
            cwd=_SPEC_KITTY_CHECKOUT,
            capture_output=True,
            check=False,
        )
        if unchanged.returncode == 0:
            return existing
    return git(_SPEC_KITTY_CHECKOUT, "rev-parse", "HEAD").strip()


def assert_golden(family: str, cell_id: str, observed: dict[str, Any]) -> None:
    """Compare *observed* with the snapshot cell, or write it under ``SPEC_KITTY_REGEN_GOLDEN=1``."""
    path = _snapshot_path(family)
    snapshot: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"base_commit": None, "cells": {}}
    if os.environ.get(REGEN_ENV) == "1":
        if os.environ.get("PYTEST_XDIST_WORKER"):
            pytest.fail(f"{REGEN_ENV}=1 must run serially (-n0): regeneration rewrites one file per module.")
        snapshot["base_commit"] = _base_commit(snapshot.get("base_commit"))
        snapshot["cells"][cell_id] = observed
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(snapshot), encoding="utf-8")
        return
    expected = snapshot["cells"].get(cell_id)
    if expected is None:
        pytest.fail(f"golden cell {family}/{cell_id} is missing; capture it with {REGEN_ENV}=1 on the unchanged base.")
    if observed != expected:
        diff = "".join(difflib.unified_diff(_dump(expected).splitlines(True), _dump(observed).splitlines(True), "expected", "observed"))
        pytest.fail(f"golden cell {family}/{cell_id} drifted from {path.name}:\n{diff}")
