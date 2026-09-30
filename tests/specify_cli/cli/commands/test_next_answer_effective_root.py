"""Unit tests threading the ``OwnedCheckout`` fact through the ``next --answer`` sub-path.

(The filename is pinned from the era of the bare ``effective_root`` keyword;
the contract is now the validated ownership fact.)

Every OTHER owned-``next`` call site in ``next_cmd`` (``_pair_previous_
lifecycle_record``, ``_write_issuance_lifecycle_record``,
``_emit_mission_next_invoked``, ``_resolve_mission_slug``) branches on
``owned`` and reads the fact directly instead of the primary-folding
``placement_seam(...).read_dir(...)``. ``_handle_answer`` (the ``next
--answer`` sub-path) used to be the one holdout: it always called
``placement_seam(...)``, which folds a linked-worktree root back to the
primary checkout (``get_main_repo_root``) -- the "old way" the ADR forbids for
opted-in owned layers.

These tests assert ``_handle_answer`` takes the same fork as its siblings:
with a fact it reads ``owned.mission_dir`` and hands the fact (not a bare path)
on to the runtime, WITHOUT consulting ``placement_seam``,
``mission_context_for`` or ``get_main_repo_root`` (each patched to raise); and
without one it makes the historical ``placement_seam(...)`` call unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionTopology, OwnedCheckout
from specify_cli.cli.commands import next_cmd

pytestmark = pytest.mark.fast

_SLUG = "owned-mission"


class _FakeRunRef:
    def __init__(self, run_dir: str) -> None:
        self.run_dir = run_dir


class _FakeRuntimeBridge:
    """Stand-in for ``_runtime_bridge_module()`` that records the root and fact it saw."""

    def __init__(self, run_dir: str) -> None:
        self._run_dir = run_dir
        self.get_or_start_run_calls: list[tuple[str, object, str, object]] = []
        self.answer_calls: list[tuple[str, str, str, str, object, object]] = []

    def get_or_start_run(self, mission_slug, repo_root, mission_type, *, owned=None):
        self.get_or_start_run_calls.append((mission_slug, repo_root, mission_type, owned))
        return _FakeRunRef(self._run_dir)

    def answer_decision_via_runtime(self, mission_slug, decision_id, answer, agent, repo_root, *, owned=None):
        self.answer_calls.append((mission_slug, decision_id, answer, agent, repo_root, owned))


def _fact(tmp_path: Path) -> OwnedCheckout:
    """A fact over a real on-disk layout (a unit stand-in for the validator's output)."""
    repository_root = tmp_path / "repository-root"
    repository_root.mkdir()
    owned_root = tmp_path / "owned-checkout"
    mission_dir = owned_root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev"}), encoding="utf-8")
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="codex/owned",
    )


def _patch_common(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, seen_feature_dirs: list[Path]) -> _FakeRuntimeBridge:
    fake_bridge = _FakeRuntimeBridge(run_dir=str(tmp_path / "run-dir"))
    monkeypatch.setattr(next_cmd, "_runtime_bridge_module", lambda: fake_bridge)
    monkeypatch.setattr(
        "specify_cli.mission.get_mission_type",
        lambda feature_dir: (seen_feature_dirs.append(feature_dir), "software-dev")[1],
    )
    return fake_bridge


def _boom(name: str):
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"{name} must not be consulted on the owned arm")

    return _raise


def test_handle_answer_without_fact_uses_placement_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Historical behavior: no fact -> the primary-folding seam."""
    primary_marker = tmp_path / "primary-marker"
    seen_feature_dirs: list[Path] = []
    fake_bridge = _patch_common(monkeypatch, tmp_path, seen_feature_dirs)

    seam_calls: list[tuple[object, str]] = []

    class _FakeSeamReader:
        def read_dir(self, kind):
            return primary_marker

    def _fake_placement_seam(repo_root, mission_slug):
        seam_calls.append((repo_root, mission_slug))
        return _FakeSeamReader()

    monkeypatch.setattr(next_cmd, "placement_seam", _fake_placement_seam)
    monkeypatch.setattr("mission_runtime.mission_context_for", _boom("mission_context_for"))

    result = next_cmd._handle_answer("claude", "some-mission", "yes", "input:review", tmp_path)

    assert result == "input:review"
    assert seam_calls == [(tmp_path, "some-mission")]
    assert seen_feature_dirs == [primary_marker]
    assert fake_bridge.get_or_start_run_calls == [("some-mission", tmp_path, "software-dev", None)]
    assert fake_bridge.answer_calls == [("some-mission", "input:review", "yes", "claude", tmp_path, None)]


def test_handle_answer_with_fact_reads_the_fact_and_hands_it_to_the_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owned path: the fact's mission dir is read; the fact reaches the runtime; nothing folds to R."""
    fact = _fact(tmp_path)
    seen_feature_dirs: list[Path] = []
    fake_bridge = _patch_common(monkeypatch, tmp_path, seen_feature_dirs)
    monkeypatch.setattr(next_cmd, "placement_seam", _boom("placement_seam"))
    monkeypatch.setattr("mission_runtime.mission_context_for", _boom("mission_context_for"))
    monkeypatch.setattr(next_cmd, "get_main_repo_root", _boom("get_main_repo_root"))

    result = next_cmd._handle_answer("claude", _SLUG, "yes", "input:review", fact.repository_root, owned=fact)

    assert result == "input:review"
    assert seen_feature_dirs == [fact.mission_dir]
    assert fake_bridge.get_or_start_run_calls == [(_SLUG, fact.repository_root, "software-dev", fact)]
    assert fake_bridge.answer_calls == [(_SLUG, "input:review", "yes", "claude", fact.repository_root, fact)]


def test_maybe_handle_answer_threads_the_fact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The call-site wrapper (``_maybe_handle_answer``) forwards the fact to
    ``_handle_answer`` unchanged -- this is what closes the owned ``--answer``
    gap at the ``next_step`` call site."""
    captured: dict[str, object] = {}

    def _fake_handle_answer(agent, mission_slug, answer, decision_id, repo_root, *, owned=None):
        captured["owned"] = owned
        return "resolved-id"

    monkeypatch.setattr(next_cmd, "_handle_answer", _fake_handle_answer)
    fact = _fact(tmp_path)

    result = next_cmd._maybe_handle_answer("claude", _SLUG, "yes", None, fact.repository_root, False, owned=fact)

    assert result == "resolved-id"
    assert captured["owned"] is fact
