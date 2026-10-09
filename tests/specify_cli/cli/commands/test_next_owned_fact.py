"""Unit pins for how ``next_cmd`` carries the ``OwnedCheckout`` fact (WP19 T103-T105).

Fast, in-process seams only: the end-to-end rows (protected target, flagless
adoption, stale copy, validation count, branch flip) are proved through the real
command in ``tests/integration/test_owned_lifecycle_acceptance_next.py``. Here
each owned arm is pinned to read the fact directly -- ``get_main_repo_root``,
``placement_seam`` and ``mission_context_for`` are patched to RAISE -- and each
new branch/helper gets a focused test.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from mission_runtime import MissionTopology, OwnedCheckout
from specify_cli.cli.commands import next_cmd

pytestmark = pytest.mark.fast

_SLUG = "unit-owned-mission"


def _fact(tmp_path: Path) -> OwnedCheckout:
    """A fact over a real on-disk layout (a unit stand-in for the validator's output)."""
    repository_root = tmp_path / "repository-root"
    repository_root.mkdir()
    owned_root = tmp_path / "owned-checkout"
    mission_dir = owned_root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev", "mission_id": "01M3WP19000000000000000002"}), encoding="utf-8")
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="codex/owned",
    )


def _boom(name: str) -> Any:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"{name} must not be consulted on the owned arm")

    return _raise


def _ban_folds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_cmd, "placement_seam", _boom("placement_seam"))
    monkeypatch.setattr(next_cmd, "get_main_repo_root", _boom("get_main_repo_root"))
    monkeypatch.setattr("mission_runtime.mission_context_for", _boom("mission_context_for"))


# -- decide_next wrapper ---------------------------------------------------


def test_decide_next_wrapper_forwards_the_fact_only_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr("runtime.next.decision.decide_next", lambda *a, **k: calls.append((a, k)))
    fact = _fact(tmp_path)

    next_cmd.decide_next("claude", _SLUG, "success", tmp_path)
    next_cmd.decide_next("claude", _SLUG, "success", fact.repository_root, owned=fact)

    assert calls == [
        (("claude", _SLUG, "success", tmp_path), {}),
        (("claude", _SLUG, "success", fact.repository_root), {"owned": fact}),
    ]


# -- slug resolution ---------------------------------------------------------


def test_resolve_mission_slug_with_a_fact_returns_its_slug_without_any_resolver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ban_folds(monkeypatch)
    fact = _fact(tmp_path)

    assert next_cmd._resolve_mission_slug("any-raw-handle", fact.repository_root, owned=fact) == _SLUG
    assert next_cmd._resolve_mission_slug(None, fact.repository_root, owned=fact) == _SLUG


# -- charter preflight root --------------------------------------------------


class _StopAfterPreflight(Exception):
    pass


def test_charter_preflight_runs_against_the_owned_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The charter ``next`` enforces is P's (T103 step 6); the runtime root stays R."""
    fact = _fact(tmp_path)
    seen: dict[str, Any] = {}

    def _capture_preflight(root: Path, **_kwargs: Any) -> None:
        seen["preflight_root"] = root
        raise _StopAfterPreflight

    monkeypatch.setattr(next_cmd, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(next_cmd, "_resolve_next_owned", lambda *_a, **_k: fact)
    monkeypatch.setattr(next_cmd, "_maybe_emit_runtime_notice", lambda *_: None)
    monkeypatch.setattr(next_cmd, "_run_charter_preflight_for_next", _capture_preflight)

    with pytest.raises(_StopAfterPreflight):
        next_cmd.next_step(mission=_SLUG, json_output=True, owned_checkout=fact.owned_root)

    assert seen["preflight_root"] == fact.owned_root


def test_charter_preflight_runs_against_the_ambient_root_when_not_owned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _capture_preflight(root: Path, **_kwargs: Any) -> None:
        seen["preflight_root"] = root
        raise _StopAfterPreflight

    monkeypatch.setattr(next_cmd, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(next_cmd, "_resolve_next_owned", lambda *_a, **_k: None)
    monkeypatch.setattr(next_cmd, "_maybe_emit_runtime_notice", lambda *_: None)
    monkeypatch.setattr(next_cmd, "_run_charter_preflight_for_next", _capture_preflight)

    with pytest.raises(_StopAfterPreflight):
        next_cmd.next_step(mission=_SLUG, json_output=True)

    assert seen["preflight_root"] == tmp_path


def test_next_step_without_a_project_root_exits_after_the_ownership_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_cmd, "locate_project_root", lambda: None)
    monkeypatch.setattr(next_cmd, "_resolve_next_owned", lambda *_a, **_k: None)

    with pytest.raises(typer.Exit) as excinfo:
        next_cmd.next_step(mission=_SLUG, json_output=True)

    assert excinfo.value.exit_code == 1


# -- _resolve_next_owned -----------------------------------------------------


def test_resolve_next_owned_without_a_root_and_without_the_flag_meets_the_legacy_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    guard_calls: list[str] = []
    monkeypatch.setattr(next_cmd, "_legacy_main_repo_guard", lambda: guard_calls.append("guard"))

    assert next_cmd._resolve_next_owned(None, _SLUG, None, False) is None
    assert guard_calls == ["guard"]


def test_resolve_next_owned_without_a_root_but_with_the_flag_skips_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_cmd, "_legacy_main_repo_guard", _boom("_legacy_main_repo_guard"))

    assert next_cmd._resolve_next_owned(tmp_path, _SLUG, None, False) is None


def test_resolve_next_owned_adopts_or_falls_through_to_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fact = _fact(tmp_path)
    guard_calls: list[str] = []
    monkeypatch.setattr(next_cmd, "_legacy_main_repo_guard", lambda: guard_calls.append("guard"))
    handles: list[Any] = []

    def _adopt(_root: Path, _checkout: Path | None, handle: str | None, **_kwargs: Any) -> OwnedCheckout | None:
        handles.append(handle)
        return fact

    monkeypatch.setattr(next_cmd, "resolve_owned_or_adopt", _adopt)
    assert next_cmd._resolve_next_owned(None, f"  {_SLUG}  ", fact.repository_root, False) is fact
    assert guard_calls == [] and handles == [_SLUG], "the handle is stripped and an adopted fact skips the guard"

    monkeypatch.setattr(next_cmd, "resolve_owned_or_adopt", lambda *_a, **_k: None)
    assert next_cmd._resolve_next_owned(None, _SLUG, fact.repository_root, False) is None
    assert guard_calls == ["guard"], "no adoption + no flag -> the unchanged legacy guard"

    guard_calls.clear()
    assert next_cmd._resolve_next_owned(fact.owned_root, _SLUG, fact.repository_root, False) is None
    assert guard_calls == [], "an explicit flag never meets the syntactic guard"


def test_resolve_next_owned_renders_a_refusal_in_nexts_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from mission_runtime import ActionContextError, OwnedRefusalCode

    def _refuse(*_a: Any, **_k: Any) -> None:
        raise ActionContextError(OwnedRefusalCode.OWNED_BRANCH_REFUSED, "no")

    monkeypatch.setattr(next_cmd, "resolve_owned_or_adopt", _refuse)

    with pytest.raises(typer.Exit) as excinfo:
        next_cmd._resolve_next_owned(tmp_path, _SLUG, tmp_path, True)

    assert excinfo.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"success": False, "error_code": OwnedRefusalCode.OWNED_BRANCH_REFUSED, "error": "no"}


# -- handle-less owned next ---------------------------------------------------


@pytest.mark.parametrize("listings", [[], [SimpleNamespace(mission_slug="a"), SimpleNamespace(mission_slug="b")]])
def test_resolve_next_owned_renders_the_minters_selection_signal_and_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, listings: list[Any]) -> None:
    from specify_cli.core.owned_mission import OwnedMissionSelectionRequired

    def _select(*_a: Any, **_k: Any) -> None:
        raise OwnedMissionSelectionRequired(listings)

    monkeypatch.setattr(next_cmd, "resolve_owned_or_adopt", _select)
    rendered: list[Any] = []
    monkeypatch.setattr(next_cmd, "_emit_missing_handle_discovery", lambda exc, _json: rendered.append(exc.listings))

    with pytest.raises(typer.Exit) as excinfo:
        next_cmd._resolve_next_owned(tmp_path, None, tmp_path, True)

    assert excinfo.value.exit_code == 1
    assert rendered == [listings]


def test_resolve_next_owned_asks_the_minter_to_discover_the_sole_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _mint(_root: Path, _checkout: Path | None, handle: str | None, **kwargs: Any) -> None:
        seen.update(handle=handle, **kwargs)

    monkeypatch.setattr(next_cmd, "resolve_owned_or_adopt", _mint)
    monkeypatch.setattr(next_cmd, "_legacy_main_repo_guard", lambda: None)

    next_cmd._resolve_next_owned(tmp_path, None, tmp_path, False)

    assert seen["handle"] is None and seen["discover_sole"] is True


def test_minter_discovers_the_sole_mission_only_inside_the_claimed_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``discover_sole`` runs strictly AFTER the single claim check, against the claimed checkout."""
    from specify_cli.core import owned_mission

    fact = _fact(tmp_path)
    order: list[str] = []

    def _claim(_root: Path, _checkout: Path) -> Any:
        order.append("claim")
        return SimpleNamespace(claimed_checkout=fact.owned_root)

    def _list(root: Path) -> list[Any]:
        order.append("list")
        assert root == fact.owned_root
        return [SimpleNamespace(mission_slug=_SLUG)]

    class _Stop(Exception):
        pass

    def _stop(root: Path, handle: str | None) -> Any:
        order.append(f"directory:{handle}")
        raise _Stop

    monkeypatch.setattr(owned_mission, "_require_owned_claim", _claim)
    monkeypatch.setattr(owned_mission, "_require_not_mission_worktree", lambda *_a: None)
    monkeypatch.setattr(owned_mission, "_resolve_mission_dir_best_effort", lambda *_a: None)
    monkeypatch.setattr(owned_mission, "_resolve_owned_directory", _stop)
    monkeypatch.setattr("specify_cli.context.mission_resolver.list_missions_for_selection", _list)

    with pytest.raises(_Stop):
        owned_mission.resolve_owned_mission(fact.repository_root, fact.owned_root, None, discover_sole=True)

    assert order == ["claim", "list", f"directory:{_SLUG}"]


@pytest.mark.parametrize("count", [0, 2])
def test_discover_sole_handle_signals_zero_or_several(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    from specify_cli.core.owned_mission import OwnedMissionSelectionRequired, _discover_sole_handle

    listings = [SimpleNamespace(mission_slug=f"m{i}") for i in range(count)]
    monkeypatch.setattr("specify_cli.context.mission_resolver.list_missions_for_selection", lambda _r: listings)

    with pytest.raises(OwnedMissionSelectionRequired) as excinfo:
        _discover_sole_handle(tmp_path)

    assert excinfo.value.listings == listings


# -- the legacy guard ---------------------------------------------------------


@pytest.mark.real_worktree_detection
def test_legacy_guard_refuses_inside_a_literal_worktree_and_passes_outside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".git").mkdir()
    lane = tmp_path / ".worktrees" / "some-lane"
    lane.mkdir(parents=True)
    monkeypatch.chdir(lane)
    with pytest.raises(typer.Exit) as excinfo:
        next_cmd._legacy_main_repo_guard()
    assert excinfo.value.exit_code == 1

    monkeypatch.chdir(tmp_path)
    next_cmd._legacy_main_repo_guard()


# -- decision output ----------------------------------------------------------


class _Decision:
    def to_dict(self) -> dict[str, Any]:
        return {"kind": "query"}


def test_print_decision_json_adds_the_stale_copy_key_only_for_owned_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fact = _fact(tmp_path)
    monkeypatch.setattr(next_cmd, "stale_copy_payload", lambda owned: {"stale_repository_root_copy": {"path": str(owned.repository_root), "mission_id": "m"}})

    next_cmd._print_decision(_Decision(), True, None, None)
    non_owned = json.loads(capsys.readouterr().out)
    next_cmd._print_decision(_Decision(), True, "input:x", "yes", owned=fact)
    owned = json.loads(capsys.readouterr().out)

    assert non_owned == {"kind": "query"}, "a non-owned payload is byte-identical: no stale_repository_root_copy key"
    assert owned["stale_repository_root_copy"] == {"path": str(fact.repository_root), "mission_id": "m"}
    assert (owned["answered"], owned["answer"]) == ("input:x", "yes")


def test_print_decision_json_includes_commit_warning_without_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    next_cmd._print_decision(_Decision(), True, "input:x", "yes", commit_warnings=["Decision log commit failed; events may be uncommitted."])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "kind": "query",
        "answered": "input:x",
        "answer": "yes",
        "warnings": ["Decision log commit failed; events may be uncommitted."],
    }


def test_print_decision_human_warns_on_stderr_only_for_owned_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fact = _fact(tmp_path)
    warned: list[OwnedCheckout] = []
    monkeypatch.setattr(next_cmd, "_print_human", lambda _decision: None)
    monkeypatch.setattr(next_cmd, "echo_stale_copy_warning", warned.append)

    next_cmd._print_decision(_Decision(), False, None, None)
    assert warned == []
    next_cmd._print_decision(_Decision(), False, None, None, owned=fact)
    assert warned == [fact]


# -- backfill nudge / query / lifecycle wrappers -------------------------------


def test_backfill_nudge_lists_the_owned_checkout_not_the_repository_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fact = _fact(tmp_path)
    monkeypatch.setattr(next_cmd, "get_main_repo_root", _boom("get_main_repo_root"))
    roots: list[Path] = []

    def _list(root: Path) -> list[Any]:
        roots.append(root)
        return [SimpleNamespace(mission_slug=_SLUG, mid8=None)]

    monkeypatch.setattr("specify_cli.context.mission_resolver.list_missions_for_selection", _list)

    next_cmd._maybe_emit_backfill_nudge(_SLUG, fact.repository_root, owned=fact)

    assert roots == [fact.owned_root]
    assert "migrate backfill-identity" in capsys.readouterr().err


def test_run_query_mode_hands_the_fact_to_the_runtime_only_when_owned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fact = _fact(tmp_path)
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    bridge = SimpleNamespace(
        QueryModeValidationError=RuntimeError,
        query_current_state=lambda *a, **k: (calls.append((a, k)), SimpleNamespace(to_dict=lambda: {}))[1],
    )
    monkeypatch.setattr(next_cmd, "_runtime_bridge_module", lambda: bridge)
    monkeypatch.setattr(next_cmd, "_print_decision", lambda *_a, **_k: None)

    next_cmd._run_query_mode("claude", _SLUG, tmp_path, True, None, None)
    next_cmd._run_query_mode("claude", _SLUG, fact.repository_root, True, None, None, owned=fact)

    assert calls == [
        (("claude", _SLUG, tmp_path), {}),
        (("claude", _SLUG, fact.repository_root), {"owned": fact}),
    ]


@pytest.mark.parametrize(
    ("wrapper", "seam", "args"),
    [
        ("_pair_previous_lifecycle_record", "pair_previous_lifecycle_record", ("claude", _SLUG, "success", None)),
        ("_write_issuance_lifecycle_record", "write_issuance_lifecycle_record", ("claude", _SLUG, None, object())),
        ("_emit_mission_next_invoked", "emit_mission_next_invoked", ("claude", "success", _SLUG, None, object())),
    ],
)
def test_lifecycle_wrappers_pass_the_fact_never_a_bare_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrapper: str, seam: str, args: tuple[Any, ...]
) -> None:
    fact = _fact(tmp_path)
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(f"runtime.next.next_invocation_lifecycle.{seam}", lambda *_a, **k: seen.append(k))

    getattr(next_cmd, wrapper)(*args, owned=fact)

    assert seen == [{"owned": fact}]
