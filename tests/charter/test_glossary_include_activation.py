"""R2 (M4 review) — ``charter context --include glossary-pack:<id>`` inherits the gate.

M4 gives ``GLOSSARY_PACK`` an activation-gated *delivery* slot and newly
advertises a ``--include glossary-pack:<id>`` *fetch* pointer (emitted by
``_format_inline_glossary_body``). A pre-merge security review found the
resolution side of that fetch pointer was UNgated: only ``agent-profile``
routed through the activation-aware service, so
``--include glossary-pack:<de-activated-id>`` returned the full term
definitions the charter withheld from delivery.

This module pins the fix: the glossary-pack include branch now resolves
through the *activation-aware* doctrine service, so a pack that is **not** in
the project's ``activated_glossary_packs`` list is a structured miss (never
rendered), while an activated pack renders its definitions exactly as before.

Mirrors ``test_context_include_activation.py`` (the agent-profile gate): the
doctrine service is a stub double patched onto the single
``_build_doctrine_service`` seam that both the wrapped and unwrapped paths
share, and activation state is written to ``.kittify/config.yaml``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import charter.activation.context as context_module
from charter.activation.context import build_charter_context_include


pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Stub doubles (mirroring test_context_include_activation.py)
# ---------------------------------------------------------------------------


class _StubRepo:
    """Repository stub exposing both ``get`` and ``list_all``.

    The activation-aware wrapper (:class:`charter.resolver.ActiveCharterService`)
    builds its filtered ``glossary_packs`` dict via ``list_all()``; the
    unwrapped render path reads through ``get()``. Provide both.
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
    """ActiveCharterService stand-in carrying the glossary_packs repo R2 routes."""

    def __init__(self, *, glossary_packs: _StubRepo | None = None) -> None:
        self.glossary_packs = glossary_packs or _StubRepo()


class _DummyTerm:
    def __init__(self, *, surface: str, definition: str) -> None:
        self.surface = surface
        self.definition = definition


class _DummyGlossaryPack:
    def __init__(self, *, pack_id: str, terms: list[_DummyTerm]) -> None:
        self.id = pack_id
        self.description = "Domain terminology"
        self.terms = terms


def _patch_service(monkeypatch: pytest.MonkeyPatch, service: _StubService) -> None:
    """Route ``_build_doctrine_service`` onto a stub doctrine service.

    ``_build_activation_aware_doctrine_service`` builds its inner service via
    ``_build_doctrine_service``, so patching this single seam covers both the
    wrapped (glossary) and unwrapped paths.
    """
    monkeypatch.setattr(
        context_module,
        "_build_doctrine_service",
        # Tolerant signature: the activation-aware builder forwards
        # ``org_roots`` AND ``agent_profile_overlay_dir`` to the inner build,
        # so absorb any keyword the real ``_build_doctrine_service`` accepts.
        lambda repo_root, **_kwargs: service,
    )


def _write_activation_config(repo_root: Path, *, activated: list[str] | None) -> None:
    """Write ``.kittify/config.yaml`` with an ``activated_glossary_packs`` list.

    ``activated`` = ``None`` omits the key entirely (three-state "admit all");
    ``[]`` writes an explicit empty list (opt-out); a populated list activates
    exactly those pack ids. ``mission_type_activations`` is always provisioned
    (WP04, C-A1) so ``PackContext.from_config`` has a valid mission-type block.
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = ["mission_type_activations:", "  - software-dev"]
    if activated is None:
        pass
    elif activated:
        lines.append("activated_glossary_packs:")
        lines.extend(f"  - {pack_id}" for pack_id in activated)
    else:
        lines.append("activated_glossary_packs: []")
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _domain_pack() -> _DummyGlossaryPack:
    return _DummyGlossaryPack(
        pack_id="domain-terms",
        terms=[
            _DummyTerm(surface="Mission", definition="The canonical unit of work."),
            _DummyTerm(surface="Lane", definition="A parallel execution branch."),
        ],
    )


# The definition text that must NEVER surface for a de-activated pack.
_LEAKY_DEFINITION = "The canonical unit of work."


# ---------------------------------------------------------------------------
# R2: glossary-pack include inherits the activation gate
# ---------------------------------------------------------------------------


class TestGlossaryPackActivationGate:
    def test_activated_pack_renders_definitions(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Parity: an ACTIVATED pack renders its term definitions via the
        # catalog renderer, exactly as it did on the unwrapped service.
        _write_activation_config(tmp_path, activated=["domain-terms"])
        _patch_service(
            monkeypatch,
            _StubService(glossary_packs=_StubRepo({"domain-terms": _domain_pack()})),
        )

        text = build_charter_context_include(tmp_path, "glossary-pack:domain-terms")

        assert "Glossary pack domain-terms: domain-terms" in text
        assert _LEAKY_DEFINITION in text
        assert "Lane: A parallel execution branch." in text

    def test_non_activated_pack_is_gated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # The pack exists in doctrine but is NOT in the activated list, so the
        # activation gate filters it out -> structured miss (ValueError), and
        # the withheld definitions never leak into the (empty) output.
        _write_activation_config(tmp_path, activated=["other-pack"])
        _patch_service(
            monkeypatch,
            _StubService(glossary_packs=_StubRepo({"domain-terms": _domain_pack()})),
        )

        with pytest.raises(ValueError, match="No glossary_pack found"):
            build_charter_context_include(tmp_path, "glossary-pack:domain-terms")

        try:
            text = build_charter_context_include(tmp_path, "glossary-pack:domain-terms")
        except ValueError:
            text = ""
        assert _LEAKY_DEFINITION not in text

    def test_empty_activation_list_gates_all_packs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Explicit empty list (opt-out) -> no pack is activated -> gated.
        _write_activation_config(tmp_path, activated=[])
        _patch_service(
            monkeypatch,
            _StubService(glossary_packs=_StubRepo({"domain-terms": _domain_pack()})),
        )

        with pytest.raises(ValueError, match="No glossary_pack found"):
            build_charter_context_include(tmp_path, "glossary-pack:domain-terms")

    def test_no_activation_key_renders_unrestricted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # No ``activated_glossary_packs`` key => resolves to None => the gate is
        # a no-op (admit all) => the pack renders (pre-R2 parity for projects
        # that never restrict glossary activation).
        _write_activation_config(tmp_path, activated=None)
        _patch_service(
            monkeypatch,
            _StubService(glossary_packs=_StubRepo({"domain-terms": _domain_pack()})),
        )

        text = build_charter_context_include(tmp_path, "glossary-pack:domain-terms")

        assert "Glossary pack domain-terms: domain-terms" in text
        assert _LEAKY_DEFINITION in text


# ---------------------------------------------------------------------------
# Regression: glossary routes the activation-aware service, agent-profile parity
# ---------------------------------------------------------------------------


class TestGlossaryRoutesActivationAwareService:
    def test_glossary_builds_activation_aware_service(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # R2 guard: the glossary include branch MUST build the activation-aware
        # service (the gate), not the plain one alone.
        _write_activation_config(tmp_path, activated=["domain-terms"])
        stub = _StubService(glossary_packs=_StubRepo({"domain-terms": _domain_pack()}))
        _patch_service(monkeypatch, stub)

        built: list[Path] = []
        real_builder = context_module._build_activation_aware_doctrine_service

        def _record(repo_root: Path, *, org_roots: Any = None) -> Any:
            built.append(repo_root)
            return real_builder(repo_root, org_roots=org_roots)

        monkeypatch.setattr(context_module, "_build_activation_aware_doctrine_service", _record)

        build_charter_context_include(tmp_path, "glossary-pack:domain-terms")

        assert built == [tmp_path]
