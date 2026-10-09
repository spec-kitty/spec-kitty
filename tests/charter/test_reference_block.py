"""Reference-block delivery reachability tests (WP13, FR-013/FR-014, SC-006).

These pin the behaviour the mission's own thesis demands of the injected
"Reference Docs" block:

* every emitted pointer OPENS (resolves to a real doctrine document);
* the emitted set is DISTRIBUTED across kinds, not exhausted by the first
  kind in a fixed order;
* the composition VARIES by action; and
* a stated NON-VACUITY floor is met per action (SC-006), so "every pointer
  resolves" can never pass over an emitted set of zero.

The order-rigged ``[:10]`` window (user + 8 paradigms + ``DIRECTIVE_001``)
placed the first tactic at catalog index 34 -- unreachable -- and every
pointer was dead because ``.kittify/charter/_LIBRARY/`` is never materialised.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.context import (
    _ActionGovernanceBundle,
    _load_references,
    _render_bootstrap_text,
)
from charter.activation.context_renderers.reference_pointers import (
    _REFERENCE_POINTER_FLOOR,
    _REFERENCE_POINTER_LIMIT,
    _filter_references_for_action,
    _resolve_reference_source,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHARTER_DIR = _REPO_ROOT / ".kittify" / "charter"


class _NullRepo:
    """Resolves nothing -- the reference block does not need artifact bodies."""

    def get(self, _artifact_id: str) -> None:
        return None


class _NullService:
    directives = _NullRepo()
    tactics = _NullRepo()
    styleguides = _NullRepo()
    toolguides = _NullRepo()
    procedures = _NullRepo()


def _empty_bundle() -> _ActionGovernanceBundle:
    return _ActionGovernanceBundle(
        mission="software-dev",
        directive_ids=[],
        tactic_ids=[],
        styleguide_ids=[],
        toolguide_ids=[],
        procedure_ids=[],
        asset_ids=[],
        service=_NullService(),
    )


def _reference_docs_block(text: str) -> str:
    marker = "Reference Docs:"
    index = text.find(marker)
    assert index >= 0, "rendered bootstrap text is missing the Reference Docs block"
    return text[index:]


def _render_reference_block(action: str) -> str:
    """Render the live bootstrap text for *action* against the real catalog."""
    references = _load_references(_REPO_ROOT)
    text = _render_bootstrap_text(
        charter_path=_CHARTER_DIR / "charter.md",
        action=action,
        summary=[],
        governance_bundle=_empty_bundle(),
        references=references,
    )
    return _reference_docs_block(text)


def _emitted_pointer_paths(block: str) -> list[str]:
    """Extract the parenthesised pointer path from each emitted reference line."""
    paths: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        if stripped.endswith(")") and "(" in stripped:
            paths.append(stripped[stripped.rfind("(") + 1 : -1])
    return paths


def _pointer_opens(pointer: str) -> bool:
    """True when *pointer* resolves to an existing document under any root."""
    candidates = (
        Path(pointer),
        _REPO_ROOT / pointer,
        _CHARTER_DIR / pointer,
    )
    return any(candidate.is_file() for candidate in candidates)


def test_catalog_is_the_order_rigged_fixture() -> None:
    """Guard: the real catalog still exhibits the order that motivated WP13.

    If this drifts (e.g. the catalog shrinks below a tactic), the reachability
    tests below lose their teeth, so assert the pre-conditions explicitly.
    """
    references = _load_references(_REPO_ROOT)
    kinds = [ref.get("kind", "") for ref in references]
    assert "tactic" in kinds, "catalog must carry tactics for a reachability test"
    # The first tactic sits far behind a naive head window.
    first_tactic_index = kinds.index("tactic")
    assert first_tactic_index >= 10, (
        "expected the first tactic to sit behind the retired [:10] window; "
        f"found it at index {first_tactic_index}"
    )


def test_reference_block_reaches_later_kinds() -> None:
    """FR-013/F-2: distribution surfaces kinds beyond the fixed-order head.

    A tactic (catalog index 34) is unreachable under the retired ``[:10]``
    window; per-kind distribution must surface it.
    """
    block = _render_reference_block("implement")
    assert "TACTIC:" in block, (
        "the reference block must surface a tactic -- distribution across kinds, "
        "not a fixed-order head window"
    )


def test_render_bootstrap_dead_renderer_is_deleted() -> None:
    """F-4/F-5: the test-only ``_render_bootstrap`` render path is removed.

    ``_render_bootstrap`` carried a SECOND ``references[:10]`` cap yet was
    called from nowhere in ``src/`` -- only from the test suite. Keeping a
    render path reachable only from tests is an instance of this mission's own
    thesis, so it is deleted. The live renderer is ``_render_bootstrap_text``.
    """
    import charter.activation.context as context_module

    assert not hasattr(context_module, "_render_bootstrap"), (
        "_render_bootstrap is a test-only dead render path with a second "
        "order-rigged cap; it must be deleted (F-5)"
    )
    assert hasattr(context_module, "_render_bootstrap_text"), (
        "the live renderer _render_bootstrap_text must remain"
    )


def test_every_emitted_pointer_opens() -> None:
    """FR-013/F-1: every pointer the agent is handed resolves to a real doc.

    Today all emitted ``_LIBRARY/*.md`` pointers are dead --
    ``.kittify/charter/_LIBRARY/`` is never materialised. The block must
    construct pointers from resolvable locations so an agent that opens any
    emitted reference finds a document.
    """
    block = _render_reference_block("implement")
    pointers = _emitted_pointer_paths(block)
    assert pointers, "expected the reference block to emit at least one pointer"
    dead = [pointer for pointer in pointers if not _pointer_opens(pointer)]
    assert not dead, f"emitted pointers do not resolve to any document: {dead}"


# Canonical software-dev actions the reference block is rendered for.
_SOFTWARE_DEV_ACTIONS = ("specify", "plan", "implement", "review")


def test_non_vacuity_floor_per_action() -> None:
    """SC-006/F-6: a stated minimum number of pointers is emitted per action.

    Without a floor, "every emitted pointer resolves" passes vacuously over an
    emitted set of zero -- exactly the pre-WP13 state. Assert every canonical
    software-dev action emits at least ``_REFERENCE_POINTER_FLOOR`` pointers
    that open.
    """
    assert _REFERENCE_POINTER_FLOOR >= 1, "the floor must be non-vacuous"
    for action in _SOFTWARE_DEV_ACTIONS:
        block = _render_reference_block(action)
        pointers = _emitted_pointer_paths(block)
        opened = [pointer for pointer in pointers if _pointer_opens(pointer)]
        assert len(opened) >= _REFERENCE_POINTER_FLOOR, (
            f"action {action!r} emitted only {len(opened)} resolvable pointers; "
            f"the non-vacuity floor is {_REFERENCE_POINTER_FLOOR}"
        )


def test_emitted_sets_differ_across_actions() -> None:
    """FR-014/F-3: the block's composition varies by action.

    The retired renderer emitted the same fixed head for every action. Assert
    two distinct actions surface different pointer sets.
    """
    implement = set(_emitted_pointer_paths(_render_reference_block("implement")))
    specify = set(_emitted_pointer_paths(_render_reference_block("specify")))
    assert implement and specify
    assert implement != specify, (
        "the reference block emitted an identical set for 'implement' and "
        "'specify' -- composition must vary by action"
    )


def _emitted_kinds(action: str) -> set[str]:
    """Distinct catalog-id kind prefixes (e.g. ``TACTIC``) in the block."""
    block = _render_reference_block(action)
    kinds: set[str] = set()
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped:
            kinds.add(stripped[2:].split(":", 1)[0])
    return kinds


def test_distribution_is_pinned_against_mutation() -> None:
    """FR-013/T075: the distribution + cap are pinned, not silently mutable.

    Before WP13, mutating the window (``[:10] -> [:1]``) changed nothing --
    no test observed the cap. This pins two independently-mutable properties:

    * the emitted count equals ``_REFERENCE_POINTER_LIMIT`` (shrinking the cap
      reddens this); and
    * the emitted slice spans several kinds (collapsing distribution back to a
      fixed-order head window reddens this).

    Either mutation now fails a test.
    """
    block = _render_reference_block("implement")
    pointers = _emitted_pointer_paths(block)
    assert len(pointers) == _REFERENCE_POINTER_LIMIT, (
        f"expected exactly {_REFERENCE_POINTER_LIMIT} emitted pointers "
        f"(the stated cap); got {len(pointers)} -- the cap is unpinned or changed"
    )
    kinds = _emitted_kinds("implement")
    assert len(kinds) >= 5, (
        "distribution collapsed: the emitted slice spans "
        f"{len(kinds)} kind(s); a per-kind distribution must span several. "
        "A fixed-order head window would surface only the leading kinds."
    )


# ---------------------------------------------------------------------------
# Unit-level pipeline branches: the action-scope filter and the fallback
# resolution path, exercised directly rather than only through the assembled
# catalog (a fixture drift in ``.kittify/`` should not be the only way to
# reach these branches).
# ---------------------------------------------------------------------------


def test_filter_local_support_included_when_action_matches() -> None:
    """A local_support ref scoped ``(action: implement)`` survives for that action."""
    refs = [{"kind": "local_support", "summary": "worktree hygiene (action: implement)"}]
    assert _filter_references_for_action(refs, "implement") == refs


def test_filter_local_support_excluded_when_action_does_not_match() -> None:
    """The same scoped ref is dropped for a different action."""
    refs = [{"kind": "local_support", "summary": "worktree hygiene (action: implement)"}]
    assert _filter_references_for_action(refs, "plan") == []


def test_filter_local_support_included_when_no_action_scope_stated() -> None:
    """A local_support ref with no ``(action: ...)`` marker is global -- always included."""
    refs = [{"kind": "local_support", "summary": "always-relevant repo guidance"}]
    assert _filter_references_for_action(refs, "specify") == refs


def test_filter_non_local_support_always_included_regardless_of_action() -> None:
    """Non-``local_support`` kinds bypass the scope filter entirely."""
    refs = [{"kind": "tactic", "summary": "no action scoping applies to tactics"}]
    assert _filter_references_for_action(refs, "review") == refs


def test_resolve_reference_source_falls_back_to_local_path_slug() -> None:
    """When the catalog id misses, resolution falls back to the local-path slug.

    ``ref["id"]`` sometimes carries a catalog id the on-disk index does not
    recognise (e.g. a stale or renamed artifact), but the reference's own
    ``local_path`` (``_LIBRARY/<kind>-<slug>.md``) still names a resolvable
    doctrine document once the ``<kind>-`` prefix is stripped.
    """
    index = {"tactic": {"my-slug": Path("/doctrine/tactics/my-slug.yaml")}}
    ref = {
        "kind": "tactic",
        "id": "tactic:nonexistent-catalog-id",
        "local_path": "_LIBRARY/tactic-my-slug.md",
    }

    resolved = _resolve_reference_source(ref, index)

    assert resolved == Path("/doctrine/tactics/my-slug.yaml")


def test_resolve_reference_source_returns_none_when_neither_id_nor_slug_resolve() -> None:
    """Neither the catalog id nor the local-path slug resolve -- a clean miss."""
    index = {"tactic": {"my-slug": Path("/doctrine/tactics/my-slug.yaml")}}
    ref = {
        "kind": "tactic",
        "id": "tactic:nonexistent-catalog-id",
        "local_path": "_LIBRARY/tactic-also-missing.md",
    }

    assert _resolve_reference_source(ref, index) is None
