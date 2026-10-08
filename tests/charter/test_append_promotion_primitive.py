"""Unit tests for ``charter.activation.activation_engine.promote_activations`` (WP06, T022).

``promote_activations`` is the append-only promotion primitive shared by the
config-seeded migration + interview command (WP07) and the org-pack
``required_*`` union (WP04). It accepts an arbitrary ``{yaml_key: [ids]}`` set
(NOT roots-only — org packs can mandate non-root kinds such as tactics or
styleguides) and writes exclusively through :func:`commit_plan`.

Covers:

- T022(a): promoting a directive+paradigm+styleguide set appends exactly
  those IDs, is idempotent on a second call, and writes via ``commit_plan``
  only (no direct ``save``).
- T022(b) LAND-BLOCKER — first-run parity: promoting into a previously-absent
  key preserves everything effective (the caller-supplied ``EffectiveSet`` is
  materialized into the plan before the promoted IDs are appended) rather than
  writing a bare restrictive list; an absent key with no resolved set is left
  absent and reported (FR-015, #4400). Pinned against
  ``charter.activation.pack_context.PackContext.from_config``'s three-state absent-key
  contract so a ~19-built-in drop regression would fail this test.
- T022(c): this module carries no ``specify_cli`` import (layer rule,
  C-001) — a static AST guard, matching the style of the other layer-rule
  spot-checks in this package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.activation_engine import ActivationPlan, EffectiveSet, promote_activations
from charter.activation.pack_context import PackContext

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers / fixtures (mirrors tests/charter/test_activation_engine.py)
# ---------------------------------------------------------------------------


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _load(config_path: Path) -> tuple[dict[str, Any], YAML]:
    yaml = _yaml()
    data = yaml.load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    return (data or {}), yaml


def _save_with(yaml: YAML):
    """Return a single-write ``save`` callable bound to *yaml* (round-trip)."""

    def _save(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)

    return _save


def _write_config(tmp_path: Path, content: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    path = kittify / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# T022(a) — arbitrary multi-kind promotion, append-only, idempotent
# ---------------------------------------------------------------------------


def test_promote_arbitrary_kinds_appends_exactly_those_ids(tmp_path: Path) -> None:
    """Promoting a directive+paradigm+styleguide set appends exactly those."""
    config_path = _write_config(
        tmp_path,
        "activated_directives:\n  - 001-foo\nactivated_paradigms:\n  - ddd\n",
    )
    data, yaml = _load(config_path)
    save = _save_with(yaml)

    outcome = promote_activations(
        {
            "activated_directives": ["002-bar"],
            "activated_paradigms": ["tdd"],
            "activated_styleguides": ["py-style"],
        },
        config_path=config_path,
        config_data=data,
        save=save,
        effective_sets={"activated_styleguides": EffectiveSet(kind="styleguide", yaml_key="activated_styleguides", ids=frozenset({"kotlin-style"}))},
    )
    plans = outcome.committed

    assert [p.yaml_key for p in plans] == [
        "activated_directives",
        "activated_paradigms",
        "activated_styleguides",
    ]
    assert all(isinstance(p, ActivationPlan) for p in plans)
    assert outcome.left_absent == {}

    reloaded, _ = _load(config_path)
    assert list(reloaded["activated_directives"]) == ["001-foo", "002-bar"]
    assert list(reloaded["activated_paradigms"]) == ["ddd", "tdd"]
    # Absent-key kind (styleguides): the effective set first, then the promoted id.
    assert list(reloaded["activated_styleguides"]) == ["kotlin-style", "py-style"]


def test_promote_is_idempotent_on_repeated_calls(tmp_path: Path) -> None:
    """Promoting the same ids twice appends them exactly once (no duplicates)."""
    config_path = _write_config(tmp_path, "activated_directives:\n  - 001-foo\n")
    data, yaml = _load(config_path)
    save = _save_with(yaml)

    promote_activations(
        {"activated_directives": ["002-bar"]},
        config_path=config_path,
        config_data=data,
        save=save,
        effective_sets={},
    )
    # Re-load fresh config_data the way a real caller would on a second
    # invocation (e.g. re-interview run twice).
    data2, _ = _load(config_path)
    second_plans = promote_activations(
        {"activated_directives": ["002-bar"]},
        config_path=config_path,
        config_data=data2,
        save=save,
        effective_sets={},
    ).committed

    assert second_plans[0].activated == []
    assert any("already activated" in w for w in second_plans[0].warnings)
    reloaded, _ = _load(config_path)
    assert list(reloaded["activated_directives"]) == ["001-foo", "002-bar"]


# ---------------------------------------------------------------------------
# T022(b) LAND-BLOCKER — absent-key first-run parity (no built-in drop)
# ---------------------------------------------------------------------------


def test_promote_into_absent_key_preserves_all_builtins_active(tmp_path: Path) -> None:
    """Promoting into an absent key seeds the effective set first — never a bare list.

    Stands in for the real effective directive set with a small synthetic
    ``EffectiveSet`` so the test stays hermetic (no doctrine-tree scan). The
    key point pinned here: after the commit, none of the un-promoted
    "built-ins" (d1, d2, d3) are dropped — the promoted id (d4) is *added*,
    not substituted.
    """
    # ``mission_type_activations`` is preseeded here purely so the
    # ``PackContext.from_config`` round-trip below doesn't hard-fail
    # (WP04, C-A1) -- it is unrelated to the directive-promotion
    # absent-key behavior this test pins.
    config_path = _write_config(tmp_path, "vcs:\n  type: git\nmission_type_activations:\n  - software-dev\n")
    data, yaml = _load(config_path)
    save = _save_with(yaml)
    builtin_directives = ["d1", "d2", "d3"]

    plans = promote_activations(
        {"activated_directives": ["d4"]},
        config_path=config_path,
        config_data=data,
        save=save,
        effective_sets={"activated_directives": EffectiveSet(kind="directive", yaml_key="activated_directives", ids=frozenset(builtin_directives))},
    ).committed

    plan = plans[0]
    assert plan.new_list == ["d1", "d2", "d3", "d4"]
    assert plan.activated == ["d4"]
    assert any("no explicit activation set" in w for w in plan.warnings)

    reloaded, _ = _load(config_path)
    assert list(reloaded["activated_directives"]) == ["d1", "d2", "d3", "d4"]

    # PackContext.from_config resolution: none of the un-promoted built-ins
    # dropped out of the three-state activation set after the write.
    ctx = PackContext.from_config(tmp_path)
    assert ctx.activated_directives is not None
    for builtin_id in builtin_directives:
        assert builtin_id in ctx.activated_directives
    assert "d4" in ctx.activated_directives
    assert ctx.activated_directives == frozenset({"d1", "d2", "d3", "d4"})


def test_promote_into_present_key_ignores_effective_set(tmp_path: Path) -> None:
    """When the key is already present, the effective set must not be materialized."""
    config_path = _write_config(tmp_path, "activated_directives:\n  - 001-foo\n")
    data, yaml = _load(config_path)
    save = _save_with(yaml)

    plans = promote_activations(
        {"activated_directives": ["002-bar"]},
        config_path=config_path,
        config_data=data,
        save=save,
        effective_sets={"activated_directives": EffectiveSet(kind="directive", yaml_key="activated_directives", ids=frozenset({"999-should-not-appear"}))},
    ).committed

    reloaded, _ = _load(config_path)
    assert list(reloaded["activated_directives"]) == ["001-foo", "002-bar"]
    assert "999-should-not-appear" not in plans[0].new_list
