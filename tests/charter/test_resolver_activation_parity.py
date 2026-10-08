"""WP03 (FR-011/FR-012/FR-013) — directive-base + paradigm-base re-derivation
from ``activated_*``, mirroring ``PackContext``'s activation authority.

Before this fix, ``_resolve_directive_base`` returned ``doctrine.selected_directives``
VERBATIM the moment it was non-empty (``resolver.py``'s
``if doctrine.selected_directives: ... return list(doctrine.selected_directives),
"charter"``) — a silent FULL OVERRIDE that never consulted
``PackContext.activated_directives`` at all once the charter had ANY authored
selection. ``resolve_project_governance``'s paradigm assignment
(``selected_paradigms = list(doctrine.selected_paradigms)``) never read
``activated_paradigms`` in the first place — there was no activation-aware
paradigm base anywhere in this function.

This module pins the inverted priority: ``activated_*`` becomes the BASE,
``selected_*`` UNIONS onto it — never substitutes for it — mirroring the
existing, already-correct pattern ``_resolve_directives_selection`` uses for
project-local ``directives_cfg.directives``.

Marker discipline (SK-144/#3241): every resolver-concern file in
``tests/charter/`` (``test_resolver.py``, ``test_resolver_tier_axis_via_factory.py``,
``test_resolver_activation_gating.py``) carries ``pytest.mark.fast`` alone — no
``pytest.mark.doctrine``. This file follows the same live convention (plan.md's
table listing ``fast, doctrine`` for this file is stale; corrected here per this
WP's own Context section).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from charter.activation.resolver import resolve_project_governance

pytestmark = pytest.mark.fast

#: Deterministic, synthetic catalog for every test in this module — disjoint
#: IDs per concern so an assertion that a value came from ``activated_*``
#: (and not some other source) cannot pass by incidental overlap.
_CATALOG_DIRECTIVES = frozenset({"DIRECTIVE_001", "DIRECTIVE_010", "DIRECTIVE_038"})
_CATALOG_PARADIGMS = frozenset({"paradigm-a", "paradigm-b", "paradigm-agree"})


def _write_charter_files(
    root: Path,
    *,
    selected_directives: list[str] | None = None,
    selected_paradigms: list[str] | None = None,
) -> None:
    """Write ``governance.charter.selected_*`` into ``charter.yaml``.

    Mirrors ``tests/charter/test_resolve_project_governance_single_authority.py``'s
    ``_write_charter_files`` (itself mirroring ``test_resolver.py``'s helper):
    ``resolve_project_governance`` reads ``charter.activation.sync.load_governance_config``
    / ``load_directives_config``, which source ``charter.yaml``'s ``governance:``
    / ``directives:`` sections directly. Writes at the CANONICAL root, which the
    ``tests/charter/conftest.py`` autouse git-init fixture makes equal to
    ``root`` itself.
    """
    from charter.resolution import resolve_canonical_repo_root
    from ruamel.yaml import YAML

    yaml = YAML()
    root.mkdir(parents=True, exist_ok=True)
    canonical_root = resolve_canonical_repo_root(root)
    charter_dir = canonical_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)

    doctrine: dict[str, object] = {}
    if selected_directives is not None:
        doctrine["selected_directives"] = list(selected_directives)
    if selected_paradigms is not None:
        doctrine["selected_paradigms"] = list(selected_paradigms)

    document = {
        "governance": {"charter": doctrine},
        "directives": {"directives": []},
    }
    with (charter_dir / "charter.yaml").open("w", encoding="utf-8") as fh:
        yaml.dump(document, fh)


def _write_activation_config(
    root: Path,
    *,
    activated_directives: list[str] | None = None,
    activated_paradigms: list[str] | None = None,
) -> None:
    """Write ``.kittify/config.yaml`` with (or without) ``activated_*`` keys.

    Mirrors ``test_resolve_project_governance_single_authority.py``'s
    ``_write_activation_config``. No ``charter:`` pointer is written, so
    :meth:`PackContext.from_config` reads activation keys directly from this
    file. ``None`` for a given kind omits that key entirely (the three-state
    ``None`` case: absent -> catalog default); an empty list writes the key
    with an EXPLICIT empty sequence (the ``frozenset()`` opt-out case, never
    parsed as ``None`` by ruamel/pyyaml's bare-key form).
    """
    kittify_dir = root / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    # WP04 (C-A1): mission_type_activations is a hard construction
    # precondition for PackContext.from_config, orthogonal to the
    # activated_directives/activated_paradigms state under test here.
    lines = ["mission_type_activations:", "  - software-dev", "vcs:", "  type: git"]

    def _emit(key: str, values: list[str] | None) -> None:
        if values is None:
            return
        if values:
            lines.append(f"{key}:")
            lines.extend(f"  - {value}" for value in values)
        else:
            lines.append(f"{key}: []")

    _emit("activated_directives", activated_directives)
    _emit("activated_paradigms", activated_paradigms)
    (kittify_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix ``load_offering_catalog`` to the deterministic module-level catalog."""
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=_CATALOG_PARADIGMS,
            directives=_CATALOG_DIRECTIVES,
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset({"directives", "paradigms"}),
        ),
    )


# ---------------------------------------------------------------------------
# FR-012 — directive base: activated_* is the base, selected_* unions onto it
# (RED before T012: the old `if doctrine.selected_directives: ... return
# list(doctrine.selected_directives), "charter"` branch returns the charter
# selection VERBATIM and never consults activated_directives at all once the
# charter selection is non-empty.)
# ---------------------------------------------------------------------------


def test_fr012_directive_base_is_activated_not_charter_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-empty, DISJOINT ``governance.charter.selected_directives`` must
    NOT silently override an also-non-empty ``activated_directives`` — the
    resolved directive set must include the activated-only member.

    Why RED on the pre-fix ``resolver.py``: ``_resolve_directive_base``'s
    ``if doctrine.selected_directives:`` branch fires first and returns
    ``["DIRECTIVE_010"]`` verbatim — ``activated_directives`` is never read
    because that branch already returned. ``DIRECTIVE_038`` is absent from
    the pre-fix result.
    """
    _patch_catalog(monkeypatch)
    _write_charter_files(tmp_path, selected_directives=["DIRECTIVE_010"])
    _write_activation_config(tmp_path, activated_directives=["DIRECTIVE_038"])

    result = resolve_project_governance(tmp_path)

    assert "DIRECTIVE_038" in result.directives, "activated_directives must contribute to the base even when charter selected_directives is non-empty and disjoint"
    assert "DIRECTIVE_010" in result.directives, "charter selected_directives must still union onto the activated base (never dropped)"


# ---------------------------------------------------------------------------
# FR-013 — paradigm base: activated_paradigms is the base, selected_paradigms
# unions onto it (RED before T012: resolve_project_governance's
# `selected_paradigms = list(doctrine.selected_paradigms)` is unconditional —
# there is NO activated_paradigms read anywhere in this function pre-fix.)
# ---------------------------------------------------------------------------


def test_fr013_paradigm_base_is_activated_not_charter_passthrough(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-empty, DISJOINT ``governance.charter.selected_paradigms`` must
    NOT be returned as an unconditional passthrough — the resolved paradigm
    list must include the activated-only member.

    Why RED on the pre-fix ``resolver.py``: ``resolve_project_governance``'s
    ``selected_paradigms = list(doctrine.selected_paradigms)`` is unconditional
    and reads no ``activated_*`` state at all. The resolved ``paradigms`` list
    on the pre-fix code is always exactly ``["paradigm-b"]``, regardless of
    ``activated_paradigms``.
    """
    _patch_catalog(monkeypatch)
    _write_charter_files(tmp_path, selected_paradigms=["paradigm-b"])
    _write_activation_config(tmp_path, activated_paradigms=["paradigm-a"])

    result = resolve_project_governance(tmp_path)

    assert "paradigm-a" in result.paradigms, "activated_paradigms must contribute to the base even when charter selected_paradigms is non-empty and disjoint"
    assert "paradigm-b" in result.paradigms, "charter selected_paradigms must still union onto the activated base (never dropped)"


# ---------------------------------------------------------------------------
# Step 5 — agreement case: when selected_* and activated_* already agree,
# the resolved value is UNCHANGED from what main already produces. This case
# is expected GREEN on main already (a regression guard against the fix
# over-correcting), NOT a red-first case — do not force it red.
# ---------------------------------------------------------------------------


def test_agreement_case_directives_and_paradigms_unchanged_from_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``selected_*`` and ``activated_*`` select the identical set, the
    resolved value is exactly that set for both directives and paradigms —
    this mission does not flip a project whose two sources already agree.

    This case is ALREADY GREEN on the pre-fix ``resolver.py`` (the charter
    branch returns ``selected_directives`` verbatim, which here happens to
    equal what the activated base would also produce; the unconditional
    ``selected_paradigms`` passthrough likewise already equals the activated
    set). It is committed as a regression guard, not forced red.
    """
    _patch_catalog(monkeypatch)
    _write_charter_files(
        tmp_path,
        selected_directives=["DIRECTIVE_010"],
        selected_paradigms=["paradigm-agree"],
    )
    _write_activation_config(
        tmp_path,
        activated_directives=["DIRECTIVE_010"],
        activated_paradigms=["paradigm-agree"],
    )

    result = resolve_project_governance(tmp_path)

    assert result.directives == ["DIRECTIVE_010"]
    assert result.paradigms == ["paradigm-agree"]


# ---------------------------------------------------------------------------
# Step 6 — stem-form activated_directives normalization (found during the
# tasks-phase R4 boundary audit; Union/Exclusion Boundary Audit boundary 1).
# RED before T012: the pre-fix activation branch (`return
# sorted(activated_directives), "activation"`) returns PackContext's entries
# VERBATIM, un-normalized — the resolved directives list on main contains the
# literal stem string, not the canonical DIRECTIVE_001 form.
# ---------------------------------------------------------------------------


def test_stem_form_activated_directive_normalized_before_promotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stem-form ``activated_directives`` entry (e.g.
    ``001-architectural-integrity-standard``, the same id
    ``TestOrgRequiredIdFormNormalizedBeforePromotion`` proves is a legitimate
    authoring shape) must be normalized to its canonical ``DIRECTIVE_NNN``
    form before it becomes part of the resolved base — never leaked verbatim.

    ``doctrine.selected_directives`` is left EMPTY so ``_resolve_directive_base``'s
    activation branch (not the charter branch) is the one that fires.
    """
    _patch_catalog(monkeypatch)
    _write_charter_files(tmp_path)  # selected_directives / selected_paradigms both empty
    _write_activation_config(tmp_path, activated_directives=["001-architectural-integrity-standard"])

    result = resolve_project_governance(tmp_path)

    assert "DIRECTIVE_001" in result.directives, "a stem-form activated_directives entry must be normalized to its canonical form before entering the resolved base"
    assert "001-architectural-integrity-standard" not in result.directives, "the raw, un-normalized stem string must never leak into the resolved directives list"
