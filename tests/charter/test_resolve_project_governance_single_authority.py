"""WP04 (FR-007) — single directive authority: retire the catalog-fallback.

Before this fix, ``resolve_project_governance`` was a SECOND, divergent
directive authority: when the authored charter selection was empty (as it is
right after apply+compile), ``_resolve_directives_selection`` catalog-fell-back
to the FULL built-in catalog instead of the operator's config-activated set —
the same set the doctrine-layer ``DoctrineService`` wrapper filters
``paradigms``/``procedures``/``agent_profiles`` by via
:class:`~charter.activation.pack_context.PackContext`.

This module pins the three-state contract (``pack_context.py:144``) for the
empty-selection branch of ``_resolve_directives_selection``/
``resolve_project_governance``:

* ``activated_directives is None`` (no ``.kittify/config.yaml`` at all — a
  bare, never-activated project) → the EXISTING catalog default is preserved
  (``directives_source`` stays ``"catalog_fallback"``). See
  :func:`test_bare_project_with_no_activation_key_keeps_catalog_default`.
* ``activated_directives == frozenset()`` (key present but explicitly empty —
  an opt-out) → ``directives == []``, ``directives_source == "activation"``.
  This is the state that catches a truthiness-collapse regression
  (``activated_directives or frozenset()`` / ``if activated_directives:``)
  because ``frozenset()`` is falsy just like ``None`` — the bare-project test
  alone would NOT catch it. See
  :func:`test_activated_directives_explicit_empty_list_opts_out_not_catalog_default`.
* ``activated_directives == {ids}`` → ``directives == sorted(ids)``,
  ``directives_source == "activation"``. This is journey 6: apply 5
  directives + compile, then resolve — the resolved directives must be
  exactly the 5 activated, never the full catalog. See
  :func:`test_journey_six_apply_five_activated_directives_sources_from_activation`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from charter.activation.resolver import resolve_project_governance

pytestmark = pytest.mark.fast

#: A catalog default deliberately DISJOINT from every activated-set fixture
#: below, so an assertion that ``result.directives`` equals the activated set
#: (and not the catalog) cannot pass by incidental overlap.
_CATALOG_DEFAULT_DIRECTIVES = frozenset({"DIRECTIVE_003", "DIRECTIVE_010"})


def _write_charter_files(
    root: Path,
    *,
    governance: str = "charter: {}\n",
    directives: str = "directives: []\n",
) -> None:
    """Write governance/directives bodies into ``charter.yaml``'s sections.

    Mirrors ``tests/charter/test_resolver.py``'s ``_write_charter_files``:
    ``resolve_project_governance`` reads ``charter.activation.sync.load_governance_config``
    / ``load_directives_config``, which source ``charter.yaml``'s
    ``governance:`` / ``directives:`` sections directly. Writes at the
    CANONICAL root (``charter.resolution.resolve_canonical_repo_root(root)``),
    which the ``tests/charter/conftest.py`` autouse git-init fixture makes
    equal to ``root`` itself.
    """
    from charter.resolution import resolve_canonical_repo_root
    from ruamel.yaml import YAML

    yaml = YAML()
    root.mkdir(parents=True, exist_ok=True)
    canonical_root = resolve_canonical_repo_root(root)
    charter_dir = canonical_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    document = {
        "governance": yaml.load(governance),
        "directives": yaml.load(directives),
    }
    with (charter_dir / "charter.yaml").open("w", encoding="utf-8") as fh:
        yaml.dump(document, fh)


def _write_activation_config(root: Path, *, activated_directives: list[str] | None) -> None:
    """Write ``.kittify/config.yaml`` with (or without) an ``activated_directives`` key.

    No ``charter:`` pointer is written, so :meth:`PackContext.from_config`
    reads activation keys directly from this file (the legacy/un-migrated
    path) — the resolution path ``resolve_project_governance`` does NOT
    otherwise touch (it always reads ``governance``/``directives`` straight
    off ``charter.yaml``, independent of any ``charter:`` pointer).

    ``activated_directives=None`` omits the key entirely (the bare-project /
    three-state ``None`` case); an empty list writes the key with an empty
    YAML sequence (the three-state ``frozenset()`` opt-out case).
    """
    kittify_dir = root / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    # ``mission_type_activations`` is unrelated to the ``activated_directives``
    # three-state contract this module pins, but WP04 (C-A1) made it a hard
    # construction precondition for ``PackContext.from_config`` -- a genuinely
    # absent key now raises rather than defaulting. Provision it here so every
    # activation-config fixture in this module can construct.
    lines = ["mission_type_activations:", "  - software-dev", "vcs:", "  type: git"]
    if activated_directives is not None:
        lines.append("activated_directives:")
        if activated_directives:
            lines.extend(f"  - {directive_id}" for directive_id in activated_directives)
        # else: key present with an explicit empty sequence, expressed as a
        # bare key with no children — ruamel/pyyaml parse this as `None`,
        # NOT `[]`, so write the empty-flow form explicitly instead.
        else:
            lines[-1] = "activated_directives: []"
    (kittify_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix ``load_doctrine_catalog`` to a small, deterministic catalog.

    The catalog's directive set (:data:`_CATALOG_DEFAULT_DIRECTIVES`) is
    disjoint from every activated-set fixture in this module so tests can
    assert "resolved to the activated set, not the catalog" unambiguously.
    """
    monkeypatch.setattr(
        "charter.activation.resolver.load_doctrine_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=_CATALOG_DEFAULT_DIRECTIVES,
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )


# ---------------------------------------------------------------------------
# Journey 6 — apply 5 + compile: resolves to the activated 5, not the catalog
# (RED before FR-007; the ``sorted(doctrine_catalog.directives)`` fallback at
# the old resolver.py:258-260 made this assert the full catalog instead.)
# ---------------------------------------------------------------------------


def test_journey_six_apply_five_activated_directives_sources_from_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After apply-5 + compile, ``resolve_project_governance`` resolves exactly
    the 5 activated directives, with ``directives_source`` naming the
    activation source — NOT the retired catalog-fallback."""
    _patch_catalog(monkeypatch)
    _write_charter_files(tmp_path)  # empty selected_directives, empty local directives
    activated = ["ACTIVATED_1", "ACTIVATED_2", "ACTIVATED_3", "ACTIVATED_4", "ACTIVATED_5"]
    _write_activation_config(tmp_path, activated_directives=activated)

    result = resolve_project_governance(tmp_path)

    assert result.directives == sorted(activated)
    assert result.metadata["directives_source"] == "activation"
    assert result.metadata["directives_source"] != "catalog_fallback"
    # Negative-shape guard: the old catalog-fallback canon must not leak in.
    assert not (_CATALOG_DEFAULT_DIRECTIVES & set(result.directives))


# ---------------------------------------------------------------------------
# Bare-project regression — activated_directives is None (no config.yaml at
# all): the EXISTING catalog default is preserved, not 0/empty.
# ---------------------------------------------------------------------------


def test_bare_project_with_no_activation_key_keeps_catalog_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project with no ``.kittify/config.yaml`` at all (``activated_directives``
    is ``None``, three-state) must still see the built-in catalog default —
    NOT an empty list. A naive ``sorted(activated or frozenset())`` /
    ``if activated_directives:`` collapse would not break this particular
    case (``None`` is falsy either way), but pinning it guards the documented
    "bare projects still see built-ins" contract explicitly."""
    _patch_catalog(monkeypatch)
    _write_charter_files(tmp_path)  # empty selected_directives, empty local directives
    # Deliberately do NOT call _write_activation_config: no ``activated_directives``
    # key at all -> PackContext.from_config's activated_directives is None (the
    # three-state contract this test pins). A bare ``mission_type_activations``
    # key IS still provisioned here (WP04, C-A1: an absent key is a hard
    # construction precondition, orthogonal to the activated_directives state
    # under test) -- this is the minimal config that keeps the project
    # "bare" with respect to directive activation.
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    result = resolve_project_governance(tmp_path)

    assert result.directives == sorted(_CATALOG_DEFAULT_DIRECTIVES)
    assert result.directives != []
    assert result.metadata["directives_source"] == "catalog_fallback"


# ---------------------------------------------------------------------------
# frozenset() opt-out pin (MANDATORY) — activated_directives key present but
# explicitly empty. The ONLY case that catches a truthiness collapse: under
# `if activated_directives:` / `activated_directives or frozenset()`, an
# empty frozenset is falsy just like None and would wrongly fall back to the
# catalog default; the bare-project (None) test above does NOT catch this
# because None is falsy too and still (correctly) routes to the catalog.
# ---------------------------------------------------------------------------


def test_activated_directives_explicit_empty_list_opts_out_not_catalog_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``activated_directives: []`` (key present, explicitly empty) is a
    deliberate opt-out: resolved directives must be ``[]``, sourced from
    the activation state — NEVER the catalog default."""
    _patch_catalog(monkeypatch)
    _write_charter_files(tmp_path)  # empty selected_directives, empty local directives
    _write_activation_config(tmp_path, activated_directives=[])

    result = resolve_project_governance(tmp_path)

    assert result.directives == []
    assert result.metadata["directives_source"] == "activation"
    assert result.metadata["directives_source"] != "catalog_fallback"
