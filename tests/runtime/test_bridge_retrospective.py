"""Retrospective-seam tests for ``runtime_bridge_retrospective`` (#2531 WP04, FR-006).

Two independent concerns:

1. **Focused unit tests (FR-006)** against the cluster in isolation --
   stubbing ``specify_cli.retrospective.*`` at its source (never the real
   generator/writer/lifecycle_events), mirroring the stub-at-source scenario-
   builder pattern used across the bridge seam test family.

2. **Intra-module patch points** (#2561): the cluster's members call each
   other as plain module-level calls (``_run_retrospective_learning_capture``
   -> ``_build_retrospective_facilitator_callback``; the built facilitator ->
   ``_classify_and_emit_failure`` -> ``_classify_exc``/``_remediation_hint``),
   so ``runtime.next.runtime_bridge_retrospective`` is the one binding they
   look up. ``test_*_observes_patch_on_seam_for_*`` pin that by patching the
   callee on this module and asserting the (unpatched) caller sees it.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from runtime.next import runtime_bridge_retrospective as retro

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# 1a. RetrospectiveGateRefused / _gate_guard_failures
# ---------------------------------------------------------------------------


class _Blocked(Exception):
    """Stands in for ``MissionCompletionBlocked``: carries a ``decision``."""

    def __init__(self, decision: Any) -> None:
        super().__init__("blocked")
        self.decision = decision


def _reason(**fields: str) -> SimpleNamespace:
    return SimpleNamespace(reason=SimpleNamespace(**fields))


def test_gate_refusal_reads_code_and_detail_from_a_gate_decision() -> None:
    cause = _Blocked(_reason(code="no_record", detail="no retrospective record"))

    refusal = retro.RetrospectiveGateRefused(cause)

    assert refusal.cause is cause
    assert refusal.guard_failures == ["no_record: no retrospective record"]
    assert str(refusal) == "blocked"


@pytest.mark.parametrize("cause", [RuntimeError("no decision attribute"), _Blocked(_reason())])
def test_gate_refusal_without_a_gate_decision_has_no_guard_failures(cause: Exception) -> None:
    assert retro.RetrospectiveGateRefused(cause).guard_failures == []


def test_gate_refusal_with_a_gate_decision_missing_its_detail_keeps_the_code() -> None:
    assert retro.RetrospectiveGateRefused(_Blocked(_reason(code="no_record"))).guard_failures == ["no_record: "]


# ---------------------------------------------------------------------------
# 1b. _rich_hic_prompt
# ---------------------------------------------------------------------------


def test_rich_hic_prompt_returns_run_now(monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.prompt import Confirm

    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)
    assert retro._rich_hic_prompt() == (True, None)


def test_rich_hic_prompt_requires_non_empty_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.prompt import Confirm, Prompt

    answers = iter(["", "  needs operator review  "])
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: False)
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: next(answers))
    assert retro._rich_hic_prompt() == (False, "needs operator review")


# ---------------------------------------------------------------------------
# 1c. _resolve_mission_id_for_terminus
# ---------------------------------------------------------------------------


def test_resolve_mission_id_for_terminus_falls_back_on_missing_or_bad_meta(tmp_path: Path) -> None:
    feature_dir = tmp_path / "mission-slug"
    feature_dir.mkdir()

    assert retro._resolve_mission_id_for_terminus(feature_dir) == "mission-slug"

    (feature_dir / "meta.json").write_text("{not-json", encoding="utf-8")
    assert retro._resolve_mission_id_for_terminus(feature_dir) == "mission-slug"

    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": "  "}), encoding="utf-8")
    assert retro._resolve_mission_id_for_terminus(feature_dir) == "mission-slug"

    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": "01KQMISSION"}), encoding="utf-8")
    assert retro._resolve_mission_id_for_terminus(feature_dir) == "01KQMISSION"


# ---------------------------------------------------------------------------
# 1d. _resolve_retrospective_policy_for_runtime / _retrospective_blocks_completion
# ---------------------------------------------------------------------------


def test_resolve_retrospective_policy_for_runtime_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sentinel_policy = object()
    monkeypatch.setattr(
        "specify_cli.retrospective.policy.resolve_policy",
        lambda repo_root: (sentinel_policy, {"enabled": "charter"}),
    )
    policy, source_map, error = retro._resolve_retrospective_policy_for_runtime(tmp_path)
    assert policy is sentinel_policy
    assert source_map == {"enabled": "charter"}
    assert error is None


def test_resolve_retrospective_policy_for_runtime_falls_back_to_default_on_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from specify_cli.retrospective.policy import default_policy

    boom = RuntimeError("malformed policy")

    def _raise(repo_root: Path) -> Any:
        raise boom

    monkeypatch.setattr("specify_cli.retrospective.policy.resolve_policy", _raise)
    policy, source_map, error = retro._resolve_retrospective_policy_for_runtime(tmp_path)
    assert policy == default_policy()
    assert source_map == {
        "enabled": "<resolution_error>",
        "timing": "<resolution_error>",
        "failure_policy": "<resolution_error>",
    }
    assert error is boom


@pytest.mark.parametrize(
    "enabled,timing,failure_policy,expected",
    [
        (True, "before_completion", "block", True),
        (True, "before_completion", "warn", False),
        (True, "post_completion", "block", False),
        (False, "before_completion", "block", False),
    ],
)
def test_retrospective_blocks_completion_matrix(
    enabled: bool, timing: str, failure_policy: str, expected: bool
) -> None:
    class _Policy:
        pass

    policy = _Policy()
    policy.enabled = enabled  # type: ignore[attr-defined]
    policy.timing = timing  # type: ignore[attr-defined]
    policy.failure_policy = failure_policy  # type: ignore[attr-defined]
    assert retro._retrospective_blocks_completion(policy) is expected


# ---------------------------------------------------------------------------
# 1e. _classify_exc / _remediation_hint
# ---------------------------------------------------------------------------


def test_classify_exc_branches() -> None:
    from specify_cli.retrospective.writer import RecordExistsError

    assert retro._classify_exc(RecordExistsError("already there")) == "other"
    assert retro._classify_exc(FileNotFoundError("missing")) == "missing_artifacts"
    assert retro._classify_exc(IsADirectoryError("is a dir")) == "missing_artifacts"
    assert retro._classify_exc(RuntimeError("boom")) == "generator_exception"


def test_remediation_hint_branches() -> None:
    from specify_cli.retrospective.writer import RecordExistsError

    assert retro._remediation_hint(RecordExistsError("x"), {}) == "Re-run with --overwrite to replace the existing record."
    assert "normalize-lifecycle" in (retro._remediation_hint(FileNotFoundError("missing"), {}) or "")
    hint = retro._remediation_hint(RuntimeError("oops"), {"enabled": "charter.yaml", "timing": "config.yaml"})
    assert hint == "Check policy configuration at: charter.yaml, config.yaml"
    assert retro._remediation_hint(RuntimeError("oops"), {}) == "Check policy configuration at: unknown"


# ---------------------------------------------------------------------------
# 1f/2. _classify_and_emit_failure -- behavior + intra-module patch point
# ---------------------------------------------------------------------------


def test_classify_and_emit_failure_calls_emit_capture_failed_with_classified_fields(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def _fake_emit_capture_failed(**kwargs: Any) -> None:
        captured.update(kwargs)

    retro._classify_and_emit_failure(
        mission_id="mission-1",
        mission_slug="slug-1",
        repo_root=tmp_path,
        exc=FileNotFoundError("boom"),
        source_map={"enabled": "charter.yaml"},
        provenance_kind="runtime_post_completion",
        emit_capture_failed=_fake_emit_capture_failed,
    )

    assert captured["mission_id"] == "mission-1"
    assert captured["failure_category"] == "missing_artifacts"
    assert captured["remediation_hint"] == "Run `spec-kitty migrate normalize-lifecycle` to repair missing artifacts."
    assert captured["policy_source"] == {"enabled": "charter.yaml"}


def test_classify_and_emit_failure_swallows_emit_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    def _raising_emit(**_kwargs: Any) -> None:
        raise RuntimeError("emit backend down")

    # Must not raise -- the original exception (classified) already won; a
    # secondary emit failure is logged, never propagated.
    retro._classify_and_emit_failure(
        mission_id="mission-1",
        mission_slug="slug-1",
        repo_root=tmp_path,
        exc=RuntimeError("original"),
        source_map={},
        provenance_kind="runtime_post_completion",
        emit_capture_failed=_raising_emit,
    )


def test_classify_and_emit_failure_observes_patch_on_seam_for_classify_and_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``_classify_and_emit_failure`` calls ``_classify_exc`` /
    ``_remediation_hint`` as module-level names of this seam, so a patch on
    the seam is the one it observes."""
    calls: list[str] = []

    def _spy_classify(exc: Exception) -> str:
        calls.append("classify")
        return "generator_exception"

    def _spy_hint(exc: Exception, source_map: dict[str, str]) -> str:
        calls.append("hint")
        return "patched-hint"

    monkeypatch.setattr(retro, "_classify_exc", _spy_classify)
    monkeypatch.setattr(retro, "_remediation_hint", _spy_hint)

    captured: dict[str, Any] = {}
    retro._classify_and_emit_failure(
        mission_id="mission-1",
        mission_slug="slug-1",
        repo_root=tmp_path,
        exc=RuntimeError("boom"),
        source_map={},
        provenance_kind="runtime_post_completion",
        emit_capture_failed=lambda **kwargs: captured.update(kwargs),
    )

    assert calls == ["classify", "hint"]
    assert captured["failure_category"] == "generator_exception"
    assert captured["remediation_hint"] == "patched-hint"


# ---------------------------------------------------------------------------
# 1g/2. _run_retrospective_learning_capture -- behavior + intra-module patch point
# ---------------------------------------------------------------------------


def test_run_retrospective_learning_capture_observes_patch_on_seam_for_facilitator_builder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``_run_retrospective_learning_capture`` invokes
    ``_build_retrospective_facilitator_callback`` as a module-level name of
    this seam, so a patch on the seam is the one it observes."""
    build_calls: list[dict[str, Any]] = []
    facilitator_calls: list[dict[str, Any]] = []

    def _fake_builder(mission_slug: str, repo_root: Path, provenance_kind: str = "runtime_post_completion") -> Any:
        build_calls.append({"mission_slug": mission_slug, "provenance_kind": provenance_kind})

        def _facilitator(*, mission_id: str, feature_dir: Path, repo_root: Path, **_kw: Any) -> None:
            facilitator_calls.append({"mission_id": mission_id})

        return _facilitator

    monkeypatch.setattr(retro, "_build_retrospective_facilitator_callback", _fake_builder)

    retro._run_retrospective_learning_capture(
        mission_id="mission-9",
        mission_slug="slug-9",
        feature_dir=tmp_path,
        repo_root=tmp_path,
        block_on_failure=False,
    )

    assert build_calls == [{"mission_slug": "slug-9", "provenance_kind": "runtime_post_completion"}]
    assert facilitator_calls == [{"mission_id": "mission-9"}]


def test_run_retrospective_learning_capture_swallows_failure_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _raising_callback(*, mission_id: str, feature_dir: Path, repo_root: Path, **_kw: Any) -> None:
        raise RuntimeError("generator exploded")

    monkeypatch.setattr(retro, "_build_retrospective_facilitator_callback", lambda **_kw: _raising_callback)

    # Must not raise -- best-effort default (block_on_failure=False).
    retro._run_retrospective_learning_capture(
        mission_id="m",
        mission_slug="s",
        feature_dir=tmp_path,
        repo_root=tmp_path,
        block_on_failure=False,
    )


def test_run_retrospective_learning_capture_reraises_when_blocking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _raising_callback(*, mission_id: str, feature_dir: Path, repo_root: Path, **_kw: Any) -> None:
        raise RuntimeError("strict gate failure")

    monkeypatch.setattr(retro, "_build_retrospective_facilitator_callback", lambda **_kw: _raising_callback)

    with pytest.raises(RuntimeError, match="strict gate failure"):
        retro._run_retrospective_learning_capture(
            mission_id="m",
            mission_slug="s",
            feature_dir=tmp_path,
            repo_root=tmp_path,
            block_on_failure=True,
        )


@pytest.mark.parametrize(
    ("block_on_failure", "raises", "provenance"),
    [(False, False, "runtime_post_completion"), (True, True, "runtime_strict_gate")],
    ids=["best-effort", "blocking"],
)
def test_run_retrospective_learning_capture_treats_a_callback_build_failure_like_a_capture_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, block_on_failure: bool, raises: bool, provenance: str
) -> None:
    """A failure while building the capture (e.g. a broken late import) follows the policy (#2562 pre-PR squad).

    The best-effort capture runs after the run is already terminal; letting this
    raise turned a completed advance into a false ``blocked`` Decision. Like a
    failure inside the capture, it is also recorded as a ``RetrospectiveCaptureFailed``
    event, so the mission's event log shows the capture was attempted and failed.
    """
    from specify_cli.retrospective import lifecycle_events

    def _raising_builder(**_kw: Any) -> Any:
        raise ImportError("retrospective writer unavailable")

    emitted: list[dict[str, Any]] = []
    monkeypatch.setattr(retro, "_build_retrospective_facilitator_callback", _raising_builder)
    monkeypatch.setattr(lifecycle_events, "emit_capture_failed", lambda *args, **kwargs: emitted.append({"args": args, **kwargs}))

    def _capture() -> None:
        retro._run_retrospective_learning_capture(
            mission_id="m",
            mission_slug="s",
            feature_dir=tmp_path,
            repo_root=tmp_path,
            block_on_failure=block_on_failure,
        )

    if raises:
        with pytest.raises(ImportError, match="retrospective writer unavailable"):
            _capture()
    else:
        _capture()

    assert len(emitted) == 1
    assert emitted[0]["mission_id"] == "m"
    assert emitted[0]["mission_slug"] == "s"
    assert emitted[0]["failure_category"] == "generator_exception"
    assert emitted[0]["failure_message"] == "retrospective writer unavailable"
    assert emitted[0]["attempted_provenance_kind"] == provenance


# ---------------------------------------------------------------------------
# 1h/2. _build_retrospective_facilitator_callback / _facilitator -- behavior +
# intra-module patch point for _classify_and_emit_failure
# ---------------------------------------------------------------------------


def test_facilitator_short_circuits_when_policy_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _DisabledPolicy:
        enabled = False

    monkeypatch.setattr(
        "specify_cli.retrospective.policy.resolve_policy",
        lambda repo_root: (_DisabledPolicy(), {}),
    )
    callback = retro._build_retrospective_facilitator_callback("slug-1", tmp_path)
    result = callback(mission_id="mission-1", feature_dir=tmp_path, repo_root=tmp_path)
    assert result is None


def test_facilitator_happy_path_writes_and_emits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _EnabledPolicy:
        enabled = True

    sentinel_record = object()
    write_calls: list[Any] = []
    emit_calls: list[Any] = []

    monkeypatch.setattr(
        "specify_cli.retrospective.policy.resolve_policy",
        lambda repo_root: (_EnabledPolicy(), {}),
    )
    monkeypatch.setattr(
        "specify_cli.retrospective.generator.generate_retrospective",
        lambda *a, **k: sentinel_record,
    )
    monkeypatch.setattr(
        "specify_cli.retrospective.writer.write_gen_record",
        lambda record, **k: write_calls.append(record),
    )
    monkeypatch.setattr(
        "specify_cli.retrospective.lifecycle_events.emit_captured",
        lambda record, repo_root, **k: emit_calls.append(record),
    )

    callback = retro._build_retrospective_facilitator_callback("slug-1", tmp_path)
    result = callback(mission_id="mission-1", feature_dir=tmp_path, repo_root=tmp_path)

    assert result is sentinel_record
    assert write_calls == [sentinel_record]
    assert emit_calls == [sentinel_record]


def test_facilitator_observes_patch_on_seam_for_classify_and_emit_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ``_facilitator`` closure built by ``_build_retrospective_facilitator_callback``
    calls ``_classify_and_emit_failure`` as a module-level name of this seam
    when the generator raises, so a patch on the seam is the one it observes."""
    class _EnabledPolicy:
        enabled = True

    classify_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        "specify_cli.retrospective.policy.resolve_policy",
        lambda repo_root: (_EnabledPolicy(), {}),
    )

    def _raise_missing(*a: Any, **k: Any) -> Any:
        raise FileNotFoundError("forced for seam test")

    monkeypatch.setattr("specify_cli.retrospective.generator.generate_retrospective", _raise_missing)
    monkeypatch.setattr(
        retro,
        "_classify_and_emit_failure",
        lambda **kwargs: classify_calls.append(kwargs),
    )

    callback = retro._build_retrospective_facilitator_callback("slug-1", tmp_path)
    with pytest.raises(FileNotFoundError):
        callback(mission_id="mission-1", feature_dir=tmp_path, repo_root=tmp_path)

    assert len(classify_calls) == 1
    assert classify_calls[0]["mission_id"] == "mission-1"
    assert isinstance(classify_calls[0]["exc"], FileNotFoundError)


def test_facilitator_record_exists_is_non_fatal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.retrospective.writer import RecordExistsError

    class _EnabledPolicy:
        enabled = True

    sentinel_record = object()
    emit_calls: list[Any] = []

    monkeypatch.setattr(
        "specify_cli.retrospective.policy.resolve_policy",
        lambda repo_root: (_EnabledPolicy(), {}),
    )
    monkeypatch.setattr(
        "specify_cli.retrospective.generator.generate_retrospective",
        lambda *a, **k: sentinel_record,
    )

    def _raise_exists(record: Any, **k: Any) -> None:
        raise RecordExistsError("already written")

    monkeypatch.setattr("specify_cli.retrospective.writer.write_gen_record", _raise_exists)
    monkeypatch.setattr(
        "specify_cli.retrospective.lifecycle_events.emit_captured",
        lambda record, repo_root, **k: emit_calls.append(record),
    )

    callback = retro._build_retrospective_facilitator_callback("slug-1", tmp_path)
    result = callback(mission_id="mission-1", feature_dir=tmp_path, repo_root=tmp_path)

    # Non-fatal: RecordExistsError on write is swallowed and Captured is
    # still emitted with the existing record.
    assert result is sentinel_record
    assert emit_calls == [sentinel_record]
