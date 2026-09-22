"""T017 (WP04, #2532) — non-trivial byte-parity baseline for ``charter.activation.context``.

Captured **after** WP01/WP02/WP03 land (Decision 10 / Decision 8 in
``research.md``): the corpus below traverses the three behaviour-bearing
cases the contract requires plus the empty-charter provenance proof:

* token-budget substitution (an over-budget action-critical section body
  gets swapped for the canonical fetch + when-doing stanza — NFR-001);
* catalog-miss fall-through (a profile-cited directive id absent from the
  catalog degrades to the structured miss stanza, not a crash);
* first-load state bookkeeping (a fresh repo's first render writes
  ``.kittify/charter/context-state.json``);
* the empty-charter / generic-agent fallback (WP01/WP03, #3064) — proves
  this golden was captured post-US1, not a stale pre-WP01 snapshot.

Each case asserts its own distinguishing behavioural marker: the token-budget
swap actually happened, the ghost reference degraded to the miss stanza, the
first-load state was persisted, and the empty-charter fallback did not leak the
directive canon.

RETIRED byte-parity goldens (mission rehome-writing-comms-doctrine)
-------------------------------------------------------------------
The four ``*.golden.txt`` byte-parity fixtures and the ``_assert_matches_golden``
helper were removed. The JSON corpus golden embedded the LIVE built-in directive
catalog, so it red on every legitimate doctrine addition with nothing wrong in
the renderer — concretely, shipping ``DIRECTIVE_049`` moved the catalog-miss
"did you mean" suggestion (``DIRECTIVE_998`` -> ``DIRECTIVE_049``) and broke the
frozen corpus. Render *determinism* is now covered permanently by
``tests/charter/test_context_noop_stability.py`` (render-twice idempotency), and
the behavioural contracts by the marker tests below, so the frozen corpus was a
redundant change-detector. The behaviour-bearing assertions are kept inline; only
the full-corpus byte-freeze is gone.

This module is import-safe before and after the WP04 extraction: every
private symbol it touches is only exercised indirectly through the three
public entry points (``build_charter_context``, ``build_charter_context_include``,
``build_charter_context_json``), so it never needs to import a moved
private symbol directly.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.context import (
    build_charter_context,
    build_charter_context_include,
    build_charter_context_json,
)
from charter.offering.agent_profiles import AgentProfile

pytestmark = [pytest.mark.fast]

# A unique needle embedded in the oversized "Terminology Canon" body so the
# token-budget test can assert the VERBATIM body is gone post-substitution
# (not just that *some* swap happened).
_LONG_BODY_NEEDLE = "PARITY-FIXTURE-LONG-BODY-MARKER-78321"
_LONG_BODY = f"Canonical term line reinforcing prose consistency ({_LONG_BODY_NEEDLE}).\n" * 700  # ~48,000 chars — comfortably over BUDGET_DEFAULT (40,000).

_GHOST_DIRECTIVE_CODE = "998"


# ---------------------------------------------------------------------------
# Fixture repo builders
# ---------------------------------------------------------------------------


def _write_common_charter_files(tmp_path: Path, charter_md: str) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    # No ``charter:`` pointer is written to config.yaml here, so PackContext
    # reads activation directly from config.yaml (legacy/un-migrated path).
    # ``mission_type_activations`` is provisioned so ``PackContext.from_config``
    # (WP04, C-A1: the provisioned charter is the sole activation authority),
    # unconditionally called by ``_resolve_action_bundle`` on every bootstrap
    # render, does not hard-fail on a genuinely absent key.
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    (charter_dir / "charter.md").write_text(charter_md, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(
        textwrap.dedent(
            """\
            doctrine:
              template_set: software-dev-default
              selected_paradigms: []
              selected_directives: []
              available_tools: []
            """
        ),
        encoding="utf-8",
    )
    (charter_dir / "references.yaml").write_text(
        textwrap.dedent(
            """\
            schema_version: "1.0.0"
            references: []
            """
        ),
        encoding="utf-8",
    )


def _bootstrap_corpus_charter_md() -> str:
    # Built via explicit concatenation (not ``textwrap.dedent`` over an
    # f-string) because ``_LONG_BODY``'s substituted lines carry no leading
    # whitespace, which would poison dedent's common-prefix calculation
    # across the whole template and leave the OTHER lines' indentation
    # un-stripped — silently breaking the ``## <heading>`` anchor match in
    # ``section_bodies._heading_pattern`` (line-start anchored, no leading
    # whitespace tolerance).
    header = textwrap.dedent(
        """\
        # Project Charter

        ## Policy Summary

        - Intent: deterministic parity fixture
        - Testing: pytest golden comparison

        ## Terminology Canon

        """
    )
    footer = textwrap.dedent(
        """\
        ## Code Review Checklist

        - Confirm the diff matches the reviewed scope.

        ## Regression Vigilance

        - Watch for silently reintroduced legacy terminology.
        """
    )
    return header + _LONG_BODY + footer


def _ghost_directive_profile() -> AgentProfile:
    """A synthetic profile citing a directive id absent from the catalog."""
    return AgentProfile.model_validate(
        {
            "profile-id": "parity-fixture-agent",
            "name": "Parity Fixture Agent",
            "roles": ["implementer"],
            "purpose": "test fixture for the WP04 byte-parity baseline",
            "specialization": {"primary-focus": "testing"},
            "directive-references": [
                {
                    "code": _GHOST_DIRECTIVE_CODE,
                    "name": "Ghost Directive",
                    "rationale": "force a catalog-miss fall-through",
                }
            ],
        }
    )


def _empty_doctrine_root(tmp_path: Path) -> Path:
    """An intentionally-empty doctrine root: every catalog lookup misses.

    Fully decouples the catalog-miss marker from the real, evolving
    built-in doctrine catalog (no risk of a future directive edit
    changing this golden for reasons unrelated to WP04).
    """
    root = tmp_path / "empty_doctrine_root"
    root.mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# Case 1 — build_charter_context: first-load + catalog-miss + token-budget
# ---------------------------------------------------------------------------


class TestBootstrapCorpusParity:
    """One render exercising all three non-trivial behaviour-bearing cases."""

    def _render(self, tmp_path: Path) -> tuple[str, Path]:
        _write_common_charter_files(tmp_path, _bootstrap_corpus_charter_md())
        doctrine_root = _empty_doctrine_root(tmp_path)
        profile = _ghost_directive_profile()

        from charter.activation.profile_resolution import _reset_agent_profile_cache

        _reset_agent_profile_cache()
        with (
            patch(
                "charter.activation.profile_resolution._activation_aware_profile_map",
                return_value={profile.profile_id: profile},
            ),
            patch(
                "charter.activation.catalog.resolve_doctrine_root",
                return_value=doctrine_root,
            ),
            # Post-relocation (mission relocate-builtin-doctrine-packs) the built-in
            # directive catalog is sourced through the ``built_in_dir(kind)`` seam,
            # NOT ``resolve_doctrine_root`` (which now only serves template sets under
            # src/doctrine). The profile-cited directive miss is diagnosed against the
            # ``DoctrineService.directives`` repo, which self-resolves via its OWN
            # built-in-dir seam. Patch both the charter-catalog seam and the directive
            # repository's seam to the SAME empty root so the miss stanza stays
            # decoupled from the live, evolving built-in canon — otherwise the fixture
            # leaks into the ambient dev-checkout ``packs/built-in`` and the golden
            # re-couples to real directive IDs (e.g. DIRECTIVE_039).
            #
            # Mission doctrine-built-in-seam-consolidation-01KYW3TX (WP01) routed the
            # directive repository's default through the ``built_in_dir(kind)``
            # authority in ``charter.offering.pack_paths`` (the join now lives there, not in
            # ``repository.py``), so the old ``...repository.resolve_pack_root`` patch
            # target no longer exists on this module. WP02 routed
            # ``charter.activation.catalog``'s own per-kind joins through the same
            # ``built_in_dir(kind)`` authority (removing its ``resolve_pack_root``
            # import entirely), so the old ``charter.activation.catalog.resolve_pack_root``
            # patch target no longer exists there either. Patching
            # ``charter.activation.catalog.built_in_dir`` (all kinds -> under the empty root)
            # and ``charter.offering.directives.repository.built_in_dir`` directly (rather
            # than ``charter.offering.pack_paths.resolve_pack_root``) reproduces the exact
            # same resolved paths scoped to only these two bindings, without
            # over-capturing every OTHER repository's built-in resolution in the same
            # render (paradigms/procedures/etc. still resolve their real built-in
            # content for this test).
            patch(
                "charter.activation.catalog.built_in_dir",
                side_effect=lambda kind: doctrine_root / kind.plural,
            ),
            patch(
                "charter.offering.directives.repository.built_in_dir",
                return_value=doctrine_root / "directives",
            ),
        ):
            result = build_charter_context(
                tmp_path,
                profile="parity-fixture-agent",
                action="implement",
                mark_loaded=True,
            )
        return result.text, tmp_path

    def test_first_load_marker(self, tmp_path: Path) -> None:
        """The fresh repo's first render must report first_load and persist state."""
        _write_common_charter_files(tmp_path, _bootstrap_corpus_charter_md())
        doctrine_root = _empty_doctrine_root(tmp_path)
        profile = _ghost_directive_profile()

        from charter.activation.profile_resolution import _reset_agent_profile_cache

        _reset_agent_profile_cache()
        state_path = tmp_path / ".kittify" / "charter" / "context-state.json"
        assert not state_path.exists(), "fixture must start with no prior state"

        with (
            patch(
                "charter.activation.profile_resolution._activation_aware_profile_map",
                return_value={profile.profile_id: profile},
            ),
            patch(
                "charter.activation.catalog.resolve_doctrine_root",
                return_value=doctrine_root,
            ),
        ):
            result = build_charter_context(
                tmp_path,
                profile="parity-fixture-agent",
                action="implement",
                mark_loaded=True,
            )

        assert result.first_load is True
        assert state_path.exists(), "first-load render must write context-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert "implement" in state.get("actions", {})

    def test_catalog_miss_marker(self, tmp_path: Path) -> None:
        """The ghost directive reference degrades to the structured miss stanza."""
        text, _ = self._render(tmp_path)
        assert f"directive:DIRECTIVE_{_GHOST_DIRECTIVE_CODE}" in text
        assert "Cause: missing_artifact" in text

    def test_token_budget_substitution_marker(self, tmp_path: Path) -> None:
        """The oversized critical-section body is swapped for a fetch stanza.

        The action-critical-sections block is now split per heading (each
        heading is its own swap candidate, competing on its own real size —
        see ``_split_critical_sections`` in ``token_budget.py``), so the
        swapped-out ``### Terminology Canon`` heading (the one carrying the
        oversized ``_LONG_BODY``) is replaced by its own heading-specific
        ``section:terminology-canon`` selector rather than the generic
        ``section:critical-implement`` bucket selector that covered the
        whole block before the split.
        """
        text, _ = self._render(tmp_path)
        assert _LONG_BODY_NEEDLE not in text, "the over-budget verbatim body must be swapped out, not inlined"
        assert "section:terminology-canon" in text
        assert "# Governance payload:" in text


# ---------------------------------------------------------------------------
# Case 2 — build_charter_context_include
# ---------------------------------------------------------------------------


_INCLUDE_CHARTER_MD = textwrap.dedent(
    """\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic parity fixture

    ## Terminology Canon

    - Canonical product term is "Mission"; "Feature" is prohibited.
    - "primary" and "merge" are overloaded — always name the sense.

    ## Code Review Checklist

    - Confirm the diff matches the reviewed scope.

    ## Regression Vigilance

    - Watch for silently reintroduced legacy terminology.
    """
)


class TestIncludeEntryPointParity:
    def test_include_returns_the_requested_section_body(self, tmp_path: Path) -> None:
        """The section-fetch entry point returns the requested section's body.

        Behavioural marker only (the frozen ``include_corpus`` byte-golden was
        retired — see the module docstring): the render is a section fetch, so it
        must carry that section's canonical-term line.
        """
        _write_common_charter_files(tmp_path, _INCLUDE_CHARTER_MD)

        text = build_charter_context_include(
            tmp_path,
            "section:terminology-canon",
            action="implement",
        )

        assert "Canonical product term is" in text


# ---------------------------------------------------------------------------
# Case 3 — build_charter_context_json
# ---------------------------------------------------------------------------


class TestJsonEntryPointParity:
    def test_json_entry_point_is_valid_bootstrap_payload(self, tmp_path: Path) -> None:
        """The JSON entry point returns a valid, well-shaped bootstrap payload.

        Lightweight structural assertion (the frozen ``json_corpus`` byte-golden
        was retired — see the module docstring — because it embedded the LIVE
        directive catalog and red on every doctrine addition). This pins the
        contract that survives catalog growth: the payload is JSON-serialisable,
        reports the ``bootstrap`` mode for the requested action, and carries the
        governance-payload structure — without freezing the full corpus.
        """
        _write_common_charter_files(tmp_path, _INCLUDE_CHARTER_MD)

        payload = build_charter_context_json(tmp_path, action="implement")

        assert payload["mode"] == "bootstrap"
        assert payload["action"] == "implement"

        # Valid JSON: round-trips byte-for-byte through a serialise/parse cycle.
        rendered = json.dumps(payload, indent=2, sort_keys=True)
        assert json.loads(rendered) == payload

        # Well-shaped governance payload (keys, not frozen catalog contents).
        # ``procedures`` is a first-class typed array (#3389); ``assets`` is
        # deliberately NOT a top-level array (asset stays reference-only, #3037).
        for key in ("directives", "tactics", "styleguides", "toolguides", "procedures"):
            assert key in payload, f"bootstrap payload missing '{key}' key"
        assert "assets" not in payload, "asset stays reference-only — no top-level array"


# ---------------------------------------------------------------------------
# Case 4 — empty-charter provenance (Decision 10): proves the golden is
# post-WP01/WP03, not a stale pre-US1 snapshot.
# ---------------------------------------------------------------------------


class TestEmptyCharterProvenance:
    def test_empty_charter_fallback_does_not_leak_directive_canon(self, tmp_path: Path) -> None:
        """The empty-charter generic fallback must not leak the directive canon.

        Behavioural marker only (the frozen ``empty_charter_corpus`` byte-golden
        was retired — see the module docstring). The provenance proof (Decision
        10) is unchanged: the WP01/WP03 suppression is in effect, so the full
        built-in directive canon must NOT leak into the generic-agent render.
        """
        from specify_cli.invocation.empty_charter import resolve_generic_fallback

        # Wholly-empty repo: no charter, no interview transcript, no
        # activations (the maximally-empty charter state — mirrors
        # tests/charter/test_empty_charter_governance_agreement.py).
        # ``PackContext.from_config`` (WP04, C-A1) fail-closes when
        # ``mission_type_activations`` is absent from ``.kittify/config.yaml``
        # -- unconditionally read by ``is_charter_empty`` -- so a minimal
        # config carrying ONLY that key is provisioned here; this test's own
        # subject (empty-charter provenance / no-directive-leak) is unrelated
        # to mission-type activation, and no other activation key is written.
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        (kittify / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")

        decision = resolve_generic_fallback(tmp_path, "please help me tidy this up")
        assert decision is not None
        assert decision.profile_id == "generic-agent"

        result = build_charter_context(
            tmp_path,
            profile=decision.profile_id,
            action=decision.action,
            mark_loaded=False,
            suppress_project_resolver=decision is not None,
        )

        # Provenance proof (Decision 10): the WP01/WP03 suppression must be
        # in effect — the full built-in directive canon must NOT leak.
        assert "Directive IDs:" in result.text or result.mode == "compact"
