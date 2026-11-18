"""Unit coverage for the #7692 retarget verdicts in ``consolidation/preflight.py``.

* ``target_override_verdict`` -- the ONE owner of the ``--target`` override chain
  (#6464 first, then the record check: #5783 for a plain ``--target``, the retarget
  record check for ``--retarget``).
* ``retarget_record_refusal`` / ``retarget_record_holders`` -- FR-011: a retarget whose
  record (``meta.json``) cannot be committed on the new target is refused before
  anything moves (``RETARGET_RECORD_UNWRITABLE``).
* ``refuse_protected_status_target(retarget_to=...)`` -- D2: the #5385 probe is
  re-pointed at the new target, never skipped (C-001: the policy's own verdict).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from specify_cli.consolidation import preflight
from specify_cli.consolidation import preflight_retarget
from specify_cli.coordination import transaction
from specify_cli.coordination.types import PROTECTED_BRANCH_REFUSED, STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH, Refused

if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest

pytestmark = [pytest.mark.fast]

_SLUG = "retarget-verdict"
_MISSION_BRANCH = "kitty/mission-retarget-verdict"
_REL_META = f"kitty-specs/{_SLUG}/meta.json"

_PROTECTED = Refused(error_code=PROTECTED_BRANCH_REFUSED, message="protected", destination_ref="main", next_step="drop it")
_UNWRITABLE = Refused(error_code="X", message="unwritable", destination_ref="main", next_step="fix it")
_HOLD = Refused(
    error_code=STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH,
    message="the status write checkout /repo is on branch 'main', not on the write branch 'develop'.",
    destination_ref="develop",
    next_step="checkout develop",
)


# --- the codes ---------------------------------------------------------------


def test_the_new_codes_equal_their_own_names() -> None:
    assert preflight_retarget.RETARGET_RECORD_UNWRITABLE == "RETARGET_RECORD_UNWRITABLE"
    assert preflight_retarget.RETARGET_RESUME_MISMATCH == "RETARGET_RESUME_MISMATCH"
    # Orchestrator ruling (A), WP03: attestations under a retarget are routed to the new target,
    # never refused, so the refusal code does not exist.
    assert not hasattr(preflight, "RETARGET_WITH_ATTESTATION_UNSUPPORTED")


# --- target_override_verdict ---------------------------------------------------


def _recording(calls: list[str], name: str, verdict: Refused | None) -> Callable[..., Refused | None]:
    def _probe(main_repo: Path, mission_slug: str, *, recorded_target: str, effective_target: str) -> Refused | None:
        calls.append(name)
        assert (main_repo, mission_slug, recorded_target, effective_target) == (Path("/repo"), "m", "main", "develop")
        return verdict

    return _probe


@pytest.mark.parametrize(
    ("protected", "record", "expected", "expected_calls"),
    [
        (_PROTECTED, _UNWRITABLE, _PROTECTED, ["protected"]),
        (None, _UNWRITABLE, _UNWRITABLE, ["protected", "record"]),
        (None, None, None, ["protected", "record"]),
    ],
    ids=["protected-wins", "record-check-second", "clean"],
)
@pytest.mark.parametrize("retarget", [False, True], ids=["plain-target", "retarget"])
def test_target_override_verdict_runs_6464_first_then_the_record_check(
    monkeypatch: pytest.MonkeyPatch,
    retarget: bool,
    protected: Refused | None,
    record: Refused | None,
    expected: Refused | None,
    expected_calls: list[str],
) -> None:
    calls: list[str] = []
    record_name, other_name = (
        ("retarget_record_refusal", "refuse_unwritable_recorded_target") if retarget else ("refuse_unwritable_recorded_target", "retarget_record_refusal")
    )
    monkeypatch.setattr(preflight_retarget, "refuse_protected_target_override", _recording(calls, "protected", protected))
    monkeypatch.setattr(preflight_retarget, record_name, _recording(calls, "record", record))
    monkeypatch.setattr(preflight_retarget, other_name, _recording(calls, "wrong-record-check", _UNWRITABLE))

    verdict = preflight_retarget.target_override_verdict(Path("/repo"), "m", recorded_target="main", effective_target="develop", retarget=retarget)

    assert verdict is expected
    assert calls == expected_calls, "a plain --target never runs the retarget check, a retarget never runs #5783"


def test_target_override_verdict_defaults_to_the_plain_target_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(preflight_retarget, "refuse_protected_target_override", _recording(calls, "protected", None))
    monkeypatch.setattr(preflight_retarget, "refuse_unwritable_recorded_target", _recording(calls, "record", _UNWRITABLE))

    assert preflight_retarget.target_override_verdict(Path("/repo"), "m", recorded_target="main", effective_target="develop") is _UNWRITABLE
    assert calls == ["protected", "record"]


# --- retarget_record_refusal / retarget_record_holders (real git) ------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _write_meta(repo: Path) -> None:
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, "target_branch": "main"}, indent=2) + "\n", encoding="utf-8")


def _repo(tmp_path: Path, *, develop_carries_record: bool, mission_branch_carries_record: bool = True) -> Path:
    """``main`` carries the Mission; ``develop`` is cut before or after it; the Mission branch from main."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    if not develop_carries_record:
        _git(repo, "branch", "develop")
    if not mission_branch_carries_record:
        _git(repo, "branch", _MISSION_BRANCH)
    _write_meta(repo)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    if develop_carries_record:
        _git(repo, "branch", "develop")
    if mission_branch_carries_record:
        _git(repo, "branch", _MISSION_BRANCH)
    return repo


@pytest.fixture
def _mission_branch_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight_retarget, "_manifest_mission_branch", lambda *_a: _MISSION_BRANCH)


def _fail_if_called(*_a: object, **_k: object) -> Refused | None:
    raise AssertionError("this arm must not probe the write checkout")


def test_restating_the_recorded_target_is_not_a_retarget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transaction, "write_checkout_refusal", _fail_if_called)
    monkeypatch.setattr(preflight_retarget, "_manifest_mission_branch", _fail_if_called)

    assert preflight_retarget.retarget_record_refusal(Path("/repo"), "m", recorded_target="main", effective_target="main") is None


@pytest.mark.usefixtures("_mission_branch_named")
def test_holders_lists_each_branch_whose_tree_carries_the_record(tmp_path: Path) -> None:
    both = _repo(tmp_path / "both", develop_carries_record=True)
    mission_only = _repo(tmp_path / "mission", develop_carries_record=False)
    neither = _repo(tmp_path / "neither", develop_carries_record=False, mission_branch_carries_record=False)

    assert preflight_retarget.retarget_record_holders(both, _SLUG, mission_branch=_MISSION_BRANCH, effective_target="develop") == (_MISSION_BRANCH, "develop")
    assert preflight_retarget.retarget_record_holders(mission_only, _SLUG, mission_branch=_MISSION_BRANCH, effective_target="develop") == (_MISSION_BRANCH,)
    assert preflight_retarget.retarget_record_holders(neither, _SLUG, mission_branch=_MISSION_BRANCH, effective_target="develop") == ()
    assert preflight_retarget.retarget_record_holders(both, _SLUG, mission_branch=None, effective_target="develop") == ("develop",)
    assert preflight_retarget.retarget_record_holders(both, _SLUG, mission_branch="develop", effective_target="develop") == ("develop",), "deduplicated"
    assert preflight_retarget.retarget_record_holders(both, _SLUG, mission_branch="no-such-branch", effective_target="develop") == ("develop",)


@pytest.mark.usefixtures("_mission_branch_named")
def test_a_record_on_neither_branch_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, develop_carries_record=False, mission_branch_carries_record=False)
    monkeypatch.setattr(transaction, "write_checkout_refusal", _fail_if_called)

    verdict = preflight_retarget.retarget_record_refusal(repo, _SLUG, recorded_target="main", effective_target="develop")

    assert verdict is not None
    assert verdict.error_code == preflight_retarget.RETARGET_RECORD_UNWRITABLE
    assert verdict.destination_ref == "develop"
    expected_head = "Refusing to retarget the mission from 'main' to 'develop': its record (meta.json) cannot be committed on 'develop' in this run: "
    assert verdict.message.startswith(expected_head)
    assert _MISSION_BRANCH in verdict.message and _REL_META in verdict.message
    assert "'main'" in verdict.next_step and "develop" in verdict.next_step


def test_a_record_on_neither_branch_without_a_mission_branch_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, develop_carries_record=False, mission_branch_carries_record=False)
    monkeypatch.setattr(preflight_retarget, "_manifest_mission_branch", lambda *_a: None)

    verdict = preflight_retarget.retarget_record_refusal(repo, _SLUG, recorded_target="main", effective_target="develop")

    assert verdict is not None and verdict.error_code == preflight_retarget.RETARGET_RECORD_UNWRITABLE
    assert "names no mission branch" in verdict.message


@pytest.mark.usefixtures("_mission_branch_named")
def test_a_record_only_on_the_mission_branch_needs_no_root_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default-topology shape: the landing carries the record to ``<b>``."""
    repo = _repo(tmp_path, develop_carries_record=False)
    _git(repo, "checkout", "-q", "develop")
    assert not (repo / "kitty-specs").exists()
    monkeypatch.setattr(transaction, "write_checkout_refusal", _fail_if_called)

    assert preflight_retarget.retarget_record_refusal(repo, _SLUG, recorded_target="main", effective_target="develop") is None


@pytest.mark.usefixtures("_mission_branch_named")
def test_a_clean_root_checkout_on_the_new_target_is_not_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, develop_carries_record=True)
    _git(repo, "checkout", "-q", "develop")
    probed: list[str] = []

    def _writable(_repo: Path, _slug: str, ref: str, *, operation: str) -> Refused | None:
        probed.append(ref)
        return None

    monkeypatch.setattr(transaction, "write_checkout_refusal", _writable)

    assert preflight_retarget.retarget_record_refusal(repo, _SLUG, recorded_target="main", effective_target="develop") is None
    assert probed == ["develop"], "the hold check judges the NEW target"


@pytest.mark.usefixtures("_mission_branch_named")
def test_a_write_checkout_hold_on_the_new_target_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, develop_carries_record=True)
    monkeypatch.setattr(transaction, "write_checkout_refusal", lambda *_a, **_k: _HOLD)

    verdict = preflight_retarget.retarget_record_refusal(repo, _SLUG, recorded_target="main", effective_target="develop")

    assert verdict is not None and verdict.error_code == preflight_retarget.RETARGET_RECORD_UNWRITABLE
    assert _HOLD.message.rstrip(".") in verdict.message
    assert "git checkout develop" in verdict.next_step


@pytest.mark.usefixtures("_mission_branch_named")
@pytest.mark.parametrize("shape", ["off-target", "dirty", "detached"])
def test_a_root_checkout_that_cannot_take_the_record_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str) -> None:
    repo = _repo(tmp_path, develop_carries_record=True)
    if shape == "dirty":
        _git(repo, "checkout", "-q", "develop")
        (repo / _REL_META).write_text("{}\n", encoding="utf-8")
    elif shape == "detached":
        _git(repo, "checkout", "-q", "--detach", "develop")
    monkeypatch.setattr(transaction, "write_checkout_refusal", lambda *_a, **_k: None)

    verdict = preflight_retarget.retarget_record_refusal(repo, _SLUG, recorded_target="main", effective_target="develop")

    assert verdict is not None and verdict.error_code == preflight_retarget.RETARGET_RECORD_UNWRITABLE
    expected = {"off-target": "not the merge target 'develop'", "dirty": "uncommitted changes", "detached": "detached HEAD"}[shape]
    assert expected in verdict.message
    assert _REL_META in verdict.next_step


# --- refuse_protected_status_target(retarget_to=...) (D2) ----------------------------


_MISSION_ID = "01M7692X0000000000000000AB"
_MID8 = _MISSION_ID[:8]
_PROBE_SLUG = f"retarget-probe-{_MID8}"
_NO_LANES = cast("LanesManifest", SimpleNamespace(lanes=[]))  # pending_done_wp_ids is patched; never read


def _status_mission(tmp_path: Path, *, coordination: bool) -> Path:
    from specify_cli.coordination.workspace import CoordinationWorkspace

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    feature_dir = repo / "kitty-specs" / _PROBE_SLUG
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _PROBE_SLUG,
        "mid8": _MID8,
        "mission_type": "research",
        "target_branch": "main",
        "topology": "coord" if coordination else "lanes",
        "created_at": "2026-01-01T00:00:00+00:00",
        "friendly_name": "retarget probe",
    }
    if coordination:
        meta["coordination_branch"] = CoordinationWorkspace.branch_name(_PROBE_SLUG, _MID8)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    if coordination:
        _git(repo, "branch", CoordinationWorkspace.branch_name(_PROBE_SLUG, _MID8), "main")
    return repo


def _capture_preflight_destinations(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def _capture(**kwargs: object) -> Refused | None:
        seen.append(str(kwargs["destination_ref"]))
        return None

    monkeypatch.setattr(transaction.BookkeepingTransaction, "preflight_refusal", staticmethod(_capture))
    monkeypatch.setattr(preflight, "pending_done_wp_ids", lambda *_a, **_k: ["WP01"])
    return seen


@pytest.mark.parametrize("retarget_to", [None, "develop"], ids=["recorded", "retarget"])
def test_the_5385_probe_is_re_pointed_for_a_coordination_less_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retarget_to: str | None) -> None:
    repo = _status_mission(tmp_path, coordination=False)
    seen = _capture_preflight_destinations(monkeypatch)

    assert preflight.refuse_protected_status_target(repo, _PROBE_SLUG, _NO_LANES, excluded_canceled_wp_ids=frozenset(), retarget_to=retarget_to) is None
    assert seen == [retarget_to or "main"], "a retarget re-points the probe at the new target; it is never skipped"


@pytest.mark.parametrize("retarget_to", [None, "develop"], ids=["recorded", "retarget"])
def test_the_5385_probe_leaves_a_coordination_destination_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retarget_to: str | None) -> None:
    from specify_cli.coordination.workspace import CoordinationWorkspace

    repo = _status_mission(tmp_path, coordination=True)
    seen = _capture_preflight_destinations(monkeypatch)

    assert preflight.refuse_protected_status_target(repo, _PROBE_SLUG, _NO_LANES, excluded_canceled_wp_ids=frozenset(), retarget_to=retarget_to) is None
    assert seen == [CoordinationWorkspace.branch_name(_PROBE_SLUG, _MID8)]
