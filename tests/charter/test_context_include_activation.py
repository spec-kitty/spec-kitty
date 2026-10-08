"""WP05 (FR-016) — ``charter context --include`` inherits the activation gate.

Pins the behaviour that ``charter context --include agent-profile:<id>``
resolves through an *activation-aware* doctrine service so the fetch path
inherits the charter activation gate: a profile that is **not** in the
project's ``activated_agent_profiles`` list is a structured miss (not
rendered), while an activated profile renders normally.

Crucially, this gate is scoped to **only** the ``agent-profile`` include
branch. The other include kinds (directive / tactic / paradigm / template /
section) and the five non-profile callers of ``_build_offering_service`` are
left on the unwrapped service and must keep their pre-#1636 behaviour.

The doctrine-service-backed kinds are exercised against stub doubles so the
test isolates the activation seam (mirroring ``test_context_include.py``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import charter.activation.context as context_module
from charter.activation.context import build_charter_context_include


pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Stub doubles
# ---------------------------------------------------------------------------


class _StubRepo:
    """Repository stub exposing both ``get`` and ``list_all``.

    The activation-aware wrapper (:class:`charter.activation.resolver.ActiveCharterService`)
    calls ``agent_profiles.list_all()`` to build its filtered dict, so the
    profile repo stub must provide ``list_all`` in addition to the ``get``
    used by the unwrapped render path.
    """

    def __init__(self, items: dict[str, Any] | None = None) -> None:
        self._items = items or {}

    def get(self, item_id: str) -> Any | None:  # noqa: ANN401 — duck-typed
        return self._items.get(item_id)

    def get_provenance(self, item_id: str) -> str | None:
        return None

    def list_all(self) -> list[Any]:
        return list(self._items.values())


class _StubService:
    """ActiveCharterService stand-in carrying the kinds WP05 routes."""

    def __init__(
        self,
        *,
        directives: _StubRepo | None = None,
        paradigms: _StubRepo | None = None,
        agent_profiles: _StubRepo | None = None,
    ) -> None:
        self.directives = directives or _StubRepo()
        self.paradigms = paradigms or _StubRepo()
        self.agent_profiles = agent_profiles or _StubRepo()


class _DummyAgentProfile:
    def __init__(self, *, profile_id: str, name: str) -> None:
        self.profile_id = profile_id
        self.name = name
        self.purpose = "p"
        self.roles = ["implementer"]


class _DummyParadigm:
    def __init__(self, *, paradigm_id: str, name: str) -> None:
        self.id = paradigm_id
        self.name = name


def _patch_service(monkeypatch: pytest.MonkeyPatch, service: _StubService) -> None:
    """Route ``_build_offering_service`` onto a stub doctrine service.

    Because ``_build_active_charter_service`` builds its inner
    service via ``_build_offering_service``, patching this single seam covers
    both the wrapped (agent-profile) and unwrapped (everything else) paths.
    """
    monkeypatch.setattr(
        context_module,
        "_build_offering_service",
        lambda repo_root, *, org_roots=None: service,
    )


def _write_activation_config(repo_root: Path, *, activated: list[str]) -> None:
    """Write ``.kittify/config.yaml`` with an ``activated_agent_profiles`` list.

    Also provisions ``mission_type_activations`` (WP04, C-A1: the provisioned
    charter is the sole activation authority for mission types) so
    ``PackContext.from_config`` -- which ``_build_active_charter_service``
    always calls for the agent-profile include branch -- does not hard-fail on
    a genuinely absent key. These tests are only exercising the
    ``activated_agent_profiles`` gate, so a generic mission type is fine.
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = ["mission_type_activations:", "  - software-dev", "activated_agent_profiles:"]
    if activated:
        lines.extend(f"  - {profile_id}" for profile_id in activated)
    else:
        lines[-1] = "activated_agent_profiles: []"
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# FR-016: agent-profile include inherits the activation gate
# ---------------------------------------------------------------------------


class TestAgentProfileActivationGate:
    def test_activated_profile_renders(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_activation_config(tmp_path, activated=["python-pedro"])
        profile = _DummyAgentProfile(profile_id="python-pedro", name="Python Pedro")
        _patch_service(
            monkeypatch,
            _StubService(agent_profiles=_StubRepo({"python-pedro": profile})),
        )

        text = build_charter_context_include(tmp_path, "agent-profile:python-pedro")

        assert "Agent profile python-pedro: Python Pedro" in text

    def test_non_activated_profile_is_gated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The profile exists in doctrine but is NOT in the activated list, so
        # the activation gate filters it out -> structured miss (ValueError),
        # never silently rendered.
        _write_activation_config(tmp_path, activated=["reviewer-renata"])
        profile = _DummyAgentProfile(profile_id="python-pedro", name="Python Pedro")
        _patch_service(
            monkeypatch,
            _StubService(agent_profiles=_StubRepo({"python-pedro": profile})),
        )

        with pytest.raises(ValueError, match="No agent_profile found"):
            build_charter_context_include(tmp_path, "agent-profile:python-pedro")

        # And the gated render never leaks the profile's name into output.
        try:
            text = build_charter_context_include(
                tmp_path, "agent-profile:python-pedro"
            )
        except ValueError:
            text = ""
        assert "Python Pedro" not in text

    def test_empty_activation_list_gates_all_profiles(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Explicit empty list (opt-out) -> no profile is activated.
        _write_activation_config(tmp_path, activated=[])
        profile = _DummyAgentProfile(profile_id="python-pedro", name="Python Pedro")
        _patch_service(
            monkeypatch,
            _StubService(agent_profiles=_StubRepo({"python-pedro": profile})),
        )

        with pytest.raises(ValueError, match="No agent_profile found"):
            build_charter_context_include(tmp_path, "agent-profile:python-pedro")

    def test_no_activation_config_renders_unrestricted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No activated_agent_profiles key => it resolves to None => no
        # restriction => the gate is a no-op and the profile renders
        # (pre-#1636 parity). This is also the path the existing
        # ``test_context_include.py`` stubs hit (a profile repo without
        # ``list_all``), so the unwrapped fallback must be byte-identical to
        # the legacy fetch. ``mission_type_activations`` is still provisioned
        # (WP04, C-A1) since ``PackContext.from_config`` always needs it,
        # even when no agent-profile restriction is configured.
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        (kittify / "config.yaml").write_text(
            "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
        )
        profile = _DummyAgentProfile(profile_id="python-pedro", name="Python Pedro")
        _patch_service(
            monkeypatch,
            _StubService(agent_profiles=_StubRepo({"python-pedro": profile})),
        )

        text = build_charter_context_include(tmp_path, "agent-profile:python-pedro")

        assert "Agent profile python-pedro: Python Pedro" in text


# ---------------------------------------------------------------------------
# Regression: only the agent-profile branch routes through the wrapper
# ---------------------------------------------------------------------------


class TestScopedToAgentProfileOnly:
    def test_helper_always_returns_wrapped_service(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # R5 single builder contract: the helper ALWAYS returns the
        # activation-aware wrapper, whether or not a restriction is configured.
        # The unrestricted (``None``) case stays byte-identical in *behaviour*
        # because the wrapper's None branch admits every profile.
        from charter.activation.resolver import ActiveCharterService

        stub = _StubService(
            agent_profiles=_StubRepo(
                {"python-pedro": _DummyAgentProfile(profile_id="python-pedro", name="P")}
            )
        )
        _patch_service(monkeypatch, stub)

        # Restriction present -> wrapped (activation-aware) service.
        _write_activation_config(tmp_path, activated=["python-pedro"])
        wrapped = context_module._build_active_charter_service(tmp_path)
        assert isinstance(wrapped, ActiveCharterService)

        # No restriction -> STILL wrapped, and the None branch admits all so the
        # gated map carries the profile unchanged (single contract, R5).
        # ``mission_type_activations`` must stay provisioned even with the
        # ``activated_agent_profiles`` key gone (WP04, C-A1) -- otherwise
        # ``PackContext.from_config`` hard-fails on the now-fully-absent key.
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
        )
        unrestricted = context_module._build_active_charter_service(tmp_path)
        assert isinstance(unrestricted, ActiveCharterService)
        assert object.__getattribute__(unrestricted, "_inner") is stub
        assert "python-pedro" in unrestricted.agent_profiles

    def test_other_kinds_use_unwrapped_service(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Even with an agent-profile activation restriction in place, the
        # non-profile include branches (e.g. paradigm) must continue to use the
        # plain ``_build_offering_service`` and render without any activation
        # filtering — the gate must not bleed into other kinds.
        _write_activation_config(tmp_path, activated=["reviewer-renata"])
        paradigm = _DummyParadigm(paradigm_id="tdd", name="Test Driven Development")
        _patch_service(
            monkeypatch,
            _StubService(paradigms=_StubRepo({"tdd": paradigm})),
        )

        text = build_charter_context_include(tmp_path, "paradigm:tdd")

        assert "Paradigm tdd: Test Driven Development" in text

    def test_other_kinds_observe_build_doctrine_service_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression guard: the non-profile branches call the *unwrapped*
        # ``_build_offering_service`` exactly once and never construct an
        # activation-aware wrapper (the helper must not be invoked).
        _write_activation_config(tmp_path, activated=["reviewer-renata"])
        paradigm = _DummyParadigm(paradigm_id="tdd", name="Test Driven Development")
        stub = _StubService(paradigms=_StubRepo({"tdd": paradigm}))

        plain_calls: list[Path] = []

        def _record(repo_root: Path, *, org_roots: Any = None) -> _StubService:
            plain_calls.append(repo_root)
            return stub

        monkeypatch.setattr(context_module, "_build_offering_service", _record)

        def _explode(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError(
                "non-profile include must not build the activation-aware service"
            )

        monkeypatch.setattr(
            context_module, "_build_active_charter_service", _explode
        )

        build_charter_context_include(tmp_path, "paradigm:tdd")

        assert plain_calls == [tmp_path]
