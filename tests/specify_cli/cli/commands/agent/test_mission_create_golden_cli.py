"""Golden pin of the ``spec-kitty agent mission create`` command surface (CLI golden cells).

Every cell drives the REAL CLI (``CliRunner`` on the real ``mission`` Typer app)
against a REAL temporary git repository.  There are zero patches: the only
environment change is ``monkeypatch.chdir(repo)``, which is how the command
locates its project root.

Captured per cell (see :func:`_observe`): the process exit code, the ``--json``
envelope (whitelist-normalised), its ``topology`` and ``error_code``, the
repository-root ``HEAD`` after the call and the sorted local branches.

Cell ids (one repository state each)::

    derived default topology
        default_primary_with_origin_head      main + origin/HEAD, no flags
        default_non_primary_branch            feat-x, origin/HEAD -> main
        default_pr_bound_unprotected_topic    --pr-bound --start-branch feat-x, main explicitly unprotected
        default_pr_bound_topic_default_protection  --pr-bound --start-branch feat-x, no protection block
        default_pr_bound_on_primary           --pr-bound on explicitly unprotected main
        default_pr_bound_protected_primary    --pr-bound from feat-x, main protected
        default_no_origin_head_non_common     origin removed, on feat-x (#5707 pin)
        default_owned_checkout                --owned-checkout, no --topology
    behaviour families, one success + one refusal each
        flat_lanes_success / flat_invalid_slug_refusal
        protected_single_branch_success / protected_single_branch_dirty_refusal
        coord_success / coord_duplicate_refusal
        owned_success / owned_not_a_worktree_refusal
        refusal_commit_to_target_with_lanes

Regenerate with ``SPEC_KITTY_REGEN_GOLDEN=1 pytest <this file> -n0``.  The
snapshot keeps its recorded ``base_commit``; only cells are rewritten.

The harness below is vendored (not imported from ``tests/_factories/coord_mission.py``)
and the normaliser is duplicated from ``tests/core/_mission_create_golden.py`` by
design, so the CLI pin stays independent of both.  Regenerate only for an intended
behaviour change (``SPEC_KITTY_REGEN_GOLDEN=1``, serial).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app
from tests._factories import provision_test_charter
from tests._support.git_template import clone_template

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_GOLDEN_FILE = Path(__file__).parent / "golden" / "mission_create_cli.json"
_REGEN_ENV = "SPEC_KITTY_REGEN_GOLDEN"
_TOPIC = "feat-x"
_MAIN = "main"

# ---------------------------------------------------------------------------
# Normaliser -- regenerate only for an intended behaviour change
# (SPEC_KITTY_REGEN_GOLDEN=1, serial).  Duplicated from the core golden harness
# by design, so the CLI pin does not import it.
# Whitelist only; any other rewriting is forbidden.
# ---------------------------------------------------------------------------
_ULID_RE = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
_MID8_AFTER_DASH_RE = re.compile(r"-([0-9A-HJKMNP-TV-Z]{8})(?![0-9A-Za-z])")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")
# Projection: the only field projected rather than substituted.
_VERSION_PROJECTION: dict[str, object] = {"present": True, "type": "str"}


def _normalise(observed: dict[str, Any], *, tmp_root: Path) -> dict[str, Any]:
    """Whitelist-normalise ``observed`` (ULID, mid8, timestamps, tmp paths; one projection)."""
    text = json.dumps(observed, sort_keys=True, ensure_ascii=False)
    for root in sorted({str(tmp_root), str(tmp_root.resolve())}, key=len, reverse=True):
        text = text.replace(root, "<TMP>")
    ulids: list[str] = []
    for found in _ULID_RE.findall(text):
        if found not in ulids:
            ulids.append(found)
    mid8s: list[str] = [ulid[:8] for ulid in ulids]
    for found in _MID8_AFTER_DASH_RE.findall(text):
        if found not in mid8s:
            mid8s.append(found)
    for number, ulid in enumerate(ulids, start=1):
        text = text.replace(ulid, f"<ULID#{number}>")
    for number, mid8 in enumerate(mid8s, start=1):
        text = text.replace(mid8, f"<MID8#{number}>")
    text = _TIMESTAMP_RE.sub("<TS>", text)
    normalised: dict[str, Any] = json.loads(text)
    envelope = normalised.get("envelope")
    if isinstance(envelope, dict) and "spec_kitty_version" in envelope:
        envelope["spec_kitty_version"] = dict(_VERSION_PROJECTION)
    return normalised


# ---------------------------------------------------------------------------
# Snapshot I/O (one file for this module, so ``--dist loadfile`` never races)
# ---------------------------------------------------------------------------
def _assert_golden(cell_id: str, observed: dict[str, Any]) -> None:
    if os.environ.get(_REGEN_ENV) == "1":
        if os.environ.get("PYTEST_XDIST_WORKER"):
            pytest.fail(f"{_REGEN_ENV}=1 refuses to run under xdist; use -n0")
        _write_cell(cell_id, observed)
        return
    document = json.loads(_GOLDEN_FILE.read_text(encoding="utf-8"))
    assert cell_id in document["cells"], f"no golden cell {cell_id!r}; regenerate with {_REGEN_ENV}=1 -n0"
    assert observed == document["cells"][cell_id]


def _write_cell(cell_id: str, observed: dict[str, Any]) -> None:
    if _GOLDEN_FILE.exists():
        document = json.loads(_GOLDEN_FILE.read_text(encoding="utf-8"))
    else:
        _GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        document = {"base_commit": _lane_base_commit(), "cells": {}}
    document["cells"][cell_id] = observed
    _GOLDEN_FILE.write_text(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _lane_base_commit() -> str:
    """Commit the snapshot was first captured on (informational; never compared)."""
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, capture_output=True, text=True, check=False)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Vendored repository builders (real git, no patches)
# ---------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _write_protected_branches(repo: Path, branches: tuple[str, ...]) -> None:
    """Write an explicit ``protection.protected_branches`` list (``()`` protects nothing)."""
    config_path = repo / ".kittify" / "config.yaml"
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    if not branches:
        block = "\nprotection:\n  protected_branches: []\n"
    else:
        block = "\nprotection:\n  protected_branches:\n" + "".join(f"    - {branch}\n" for branch in branches)
    config_path.write_text(existing + block, encoding="utf-8")


def _build_repo(tmp_path: Path, *, branch: str = _MAIN, protection: str = "default", origin_head: bool = True) -> Path:
    """Template clone + provisioned/committed charter, standing on ``branch``.

    ``protection``: ``"default"`` writes no ``protection:`` block (``main`` is
    then protected by the product default); ``"main"`` protects ``main``
    explicitly; ``"none"`` writes ``protected_branches: []`` so ``main`` is
    genuinely UNPROTECTED.

    ``origin_head=True`` re-points ``origin`` at a real bare repository and sets
    ``origin/HEAD`` to ``main``; ``False`` removes ``origin`` altogether.
    """
    repo = clone_template(tmp_path / "repo")
    provision_test_charter(repo)
    if protection == "main":
        _write_protected_branches(repo, (_MAIN,))
    elif protection == "none":
        _write_protected_branches(repo, ())
    _git(repo, "add", ".kittify")
    _git(repo, "commit", "-m", "chore(fixture): provision charter")
    if origin_head:
        bare = tmp_path / "origin.git"
        subprocess.run(["git", "init", "--bare", "-b", _MAIN, str(bare)], capture_output=True, text=True, check=True)
        _git(repo, "remote", "set-url", "origin", str(bare))
        _git(repo, "push", "origin", _MAIN)
        _git(repo, "remote", "set-head", "origin", _MAIN)
    else:
        _git(repo, "remote", "remove", "origin")
    if branch != _MAIN:
        _git(repo, "checkout", "-b", branch)
    return repo


def _add_owned_worktree(repo: Path, tmp_path: Path) -> Path:
    owned = tmp_path / "owned"
    _git(repo, "worktree", "add", str(owned), "-b", "owned-topic")
    return owned


# ---------------------------------------------------------------------------
# CLI invoker (chdir only -- never a patch)
# ---------------------------------------------------------------------------
def _cli_args(slug: str, *extra: str) -> list[str]:
    return [
        "create",
        slug,
        "--json",
        "--branch-strategy",
        "already-confirmed",
        *extra,
        "--friendly-name",
        f"{slug} fixture",
        "--purpose-tldr",
        f"Fixture mission for {slug}.",
        "--purpose-context",
        f"Fixture mission for {slug}, pinned by the CLI golden matrix.",
    ]


def _first_json_object(output: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _invoke(repo: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> tuple[int, dict[str, Any] | None, str]:
    """Run ``mission create`` from ``repo``; return ``(exit_code, parsed_json_or_None, stdout_tail)``."""
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(mission_app, args, input="")
    return result.exit_code, _first_json_object(result.output), result.output[-400:]


def _observe(repo: Path, outcome: tuple[int, dict[str, Any] | None, str], *, extra_heads: dict[str, Path] | None = None) -> dict[str, Any]:
    exit_code, envelope, tail = outcome
    heads = {"root": _git(repo, "rev-parse", "--abbrev-ref", "HEAD")}
    for name, checkout in (extra_heads or {}).items():
        heads[name] = _git(checkout, "rev-parse", "--abbrev-ref", "HEAD")
    return {
        "exit_code": exit_code,
        "topology": envelope.get("topology") if envelope else None,
        "error_code": envelope.get("error_code") if envelope else None,
        "envelope": envelope,
        "stdout_tail": None if envelope is not None else tail,
        "heads": heads,
        "branches": sorted(_git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()),
    }


def _check(cell_id: str, repo: Path, tmp_path: Path, outcome: tuple[int, dict[str, Any] | None, str], **kwargs: Any) -> None:
    _assert_golden(cell_id, _normalise(_observe(repo, outcome, **kwargs), tmp_root=tmp_path))


# ---------------------------------------------------------------------------
# Cells.  Each builder returns (repo, args, extra_heads); a few need a pre-step.
# ---------------------------------------------------------------------------
_Cell = Callable[[Path], tuple[Path, list[str], dict[str, Path]]]


def _cell_default_primary(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp), _cli_args("gold-default-primary"), {}


def _cell_default_non_primary(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, branch=_TOPIC), _cli_args("gold-default-nonprimary"), {}


def _cell_pr_bound_unprotected_topic(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, protection="none"), _cli_args("gold-prbound-topic", "--pr-bound", "--start-branch", _TOPIC), {}


def _cell_pr_bound_topic_default_protection(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    # No ``protection:`` block: the product default protects ``main``, so this
    # "no config" repository is NOT unprotected and pr-bound resolves to coord.
    return _build_repo(tmp), _cli_args("gold-prbound-default", "--pr-bound", "--start-branch", _TOPIC), {}


def _cell_pr_bound_on_primary(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, protection="none"), _cli_args("gold-prbound-primary", "--pr-bound"), {}


def _cell_pr_bound_protected_primary(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, branch=_TOPIC, protection="main"), _cli_args("gold-prbound-protected", "--pr-bound"), {}


def _cell_no_origin_head(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, branch=_TOPIC, origin_head=False), _cli_args("gold-no-origin-head"), {}


def _cell_owned_default(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    repo = _build_repo(tmp)
    owned = _add_owned_worktree(repo, tmp)
    return repo, _cli_args("gold-owned-default", "--owned-checkout", str(owned)), {"owned": owned}


def _cell_flat_success(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, branch=_TOPIC), _cli_args("gold-flat-ok", "--topology", "lanes"), {}


def _cell_flat_invalid_slug(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, branch=_TOPIC), _cli_args("Not A Valid Slug!", "--topology", "lanes"), {}


def _cell_protected_single_success(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, protection="main"), _cli_args("gold-protected-ok", "--topology", "single_branch"), {}


def _cell_protected_single_dirty(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    repo = _build_repo(tmp, protection="main")
    (repo / "stray.txt").write_text("uncommitted\n", encoding="utf-8")
    return repo, _cli_args("gold-protected-dirty", "--topology", "single_branch"), {}


def _cell_coord_success(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp), _cli_args("gold-coord-ok", "--topology", "coord"), {}


def _cell_owned_success(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    repo = _build_repo(tmp)
    owned = _add_owned_worktree(repo, tmp)
    return repo, _cli_args("gold-owned-ok", "--topology", "single_branch", "--owned-checkout", str(owned)), {"owned": owned}


def _cell_owned_not_a_worktree(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    repo = _build_repo(tmp)
    stranger = tmp / "stranger"
    stranger.mkdir()
    return repo, _cli_args("gold-owned-bad", "--topology", "single_branch", "--owned-checkout", str(stranger)), {}


def _cell_commit_to_target_with_lanes(tmp: Path) -> tuple[Path, list[str], dict[str, Path]]:
    return _build_repo(tmp, branch=_TOPIC), _cli_args("gold-ctt-lanes", "--topology", "lanes", "--commit-to-target"), {}


_SIMPLE_CELLS: dict[str, _Cell] = {
    "default_primary_with_origin_head": _cell_default_primary,
    "default_non_primary_branch": _cell_default_non_primary,
    "default_pr_bound_unprotected_topic": _cell_pr_bound_unprotected_topic,
    "default_pr_bound_topic_default_protection": _cell_pr_bound_topic_default_protection,
    "default_pr_bound_on_primary": _cell_pr_bound_on_primary,
    "default_pr_bound_protected_primary": _cell_pr_bound_protected_primary,
    "default_no_origin_head_non_common": _cell_no_origin_head,
    "default_owned_checkout": _cell_owned_default,
    "flat_lanes_success": _cell_flat_success,
    "flat_invalid_slug_refusal": _cell_flat_invalid_slug,
    "protected_single_branch_success": _cell_protected_single_success,
    "protected_single_branch_dirty_refusal": _cell_protected_single_dirty,
    "coord_success": _cell_coord_success,
    "owned_success": _cell_owned_success,
    "owned_not_a_worktree_refusal": _cell_owned_not_a_worktree,
    "refusal_commit_to_target_with_lanes": _cell_commit_to_target_with_lanes,
}


@pytest.mark.parametrize("cell_id", sorted(_SIMPLE_CELLS))
def test_cli_golden_cell(cell_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, args, extra_heads = _SIMPLE_CELLS[cell_id](tmp_path)
    outcome = _invoke(repo, monkeypatch, args)
    _check(cell_id, repo, tmp_path, outcome, extra_heads=extra_heads)


def test_cli_golden_coord_duplicate_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second create of a live slug refuses; the first mission's spec.md is committed in between.

    A genesis-only prior is abandoned and would NOT refuse, so the spec is
    given content and committed to make the prior mission live.
    """
    repo = _build_repo(tmp_path)
    args = _cli_args("gold-coord-dup", "--topology", "coord")
    exit_code, first, _tail = _invoke(repo, monkeypatch, args)
    assert exit_code == 0 and first is not None
    spec_file = Path(str(first["spec_file"]))
    spec_file.write_text("# Spec\n\nA committed, substantive specification.\n", encoding="utf-8")
    _git(repo, "add", str(spec_file))
    _git(repo, "commit", "-m", "docs: commit first mission spec")
    outcome = _invoke(repo, monkeypatch, args)
    _check("coord_duplicate_refusal", repo, tmp_path, outcome)
