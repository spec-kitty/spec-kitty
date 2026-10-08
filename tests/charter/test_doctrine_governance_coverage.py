"""Focused coverage for Doctrine Governance Fidelity helper branches.

These pin the defensive / tolerant branches of the charter-gated org-profile
helpers that the behavioural tests don't naturally exercise — the best-effort
org-root fallbacks, the activation-map memoisation, and the FR-013 nested-layout
fallback — so the critical-path diff-coverage gate stays honest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation import context
from charter.activation.pack_manager import _resolve_kind, _resolve_org_layer_dir

pytestmark = pytest.mark.fast


def test_existing_org_roots_swallows_resolver_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """A raising ``resolve_org_roots`` yields ``[]`` (best-effort fast path)."""
    import charter.offering.drg.org_pack_config as cfg

    def _boom(_repo_root: Path) -> list[Path]:
        raise RuntimeError("config corrupt")

    monkeypatch.setattr(cfg, "resolve_org_roots", _boom)
    assert context._existing_org_roots(Path("/nonexistent-repo")) == []


def test_existing_org_roots_swallows_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing ``resolve_org_roots`` symbol (ImportError) yields ``[]``."""
    import charter.offering.drg.org_pack_config as cfg

    monkeypatch.delattr(cfg, "resolve_org_roots", raising=True)
    assert context._existing_org_roots(Path("/nonexistent-repo")) == []


def test_activation_aware_profile_map_returns_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second call for the same repo_root returns the memoised map (no rebuild)."""
    repo_root = Path("/some/repo")
    sentinel: dict = {}
    context._ACTIVATION_AWARE_PROFILE_MAPS[repo_root] = sentinel

    # If the cache branch were skipped, this would build a service; fail loudly if so.
    def _must_not_build(*_a: object, **_k: object) -> object:  # pragma: no cover - guard
        raise AssertionError("service was rebuilt despite a cached map")

    monkeypatch.setattr(context, "_build_activation_aware_doctrine_service", _must_not_build)
    try:
        assert context._activation_aware_profile_map(repo_root, []) is sentinel
    finally:
        context._ACTIVATION_AWARE_PROFILE_MAPS.pop(repo_root, None)


def test_resolve_org_layer_dir_is_the_flat_plural_dir(tmp_path: Path) -> None:
    """The org layer is the flat ``<pack>/<plural>/`` dir, whether or not it exists (FR-013)."""
    kind = _resolve_kind("agent-profile")
    assert kind is not None
    assert _resolve_org_layer_dir(tmp_path, kind) == tmp_path / kind.plural


def test_resolve_org_layer_dir_ignores_the_retired_nested_layout(tmp_path: Path) -> None:
    """A nested ``<pack>/doctrine/<plural>/org/`` dir is not read (FR-011)."""
    kind = _resolve_kind("agent-profile")
    assert kind is not None
    (tmp_path / "doctrine" / kind.plural / "org").mkdir(parents=True)
    assert _resolve_org_layer_dir(tmp_path, kind) == tmp_path / kind.plural
