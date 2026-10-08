"""Versioned contract ledger for the ``charter context --json`` payload.

#2787 (E1, RFC #2497 endpoint): ``charter context --action <a> --json``
already ships and is canonical, but the **top-level** JSON payload built by
:func:`~charter.activation.context.build_charter_context_json` carried no schema
version of its own, so an external consumer that pins to its shape could
break silently on any offering-layer reshape. ``CONTEXT_SCHEMA_VERSION`` is
the single-authority stamp for that top-level shape; it is deliberately
named distinct from the *nested* ``org_charter.schema_version`` field
(``charter.activation.org_charter.OrgCharterPolicy.schema_version``),
which versions one imported org policy document, not the envelope that
carries it.

**This is an activation-scoped TRACKING contract, not yet a frozen one.**
The payload is *activation-scoped*: a restrictive org/project charter
legitimately *shrinks* the active directive/tactic/styleguide/toolguide set
for a given action, so a consumer pins the resolved *activation* contract
for their charter, not a static dump of every doctrine artifact that could
ever exist. Per #2787's own sequencing, stamping the version and recording
the top-level shape ships now; the harder half of the contract -- a hard
freeze plus a deprecation policy for removing/renaming a top-level key --
is deliberately deferred until the activation surface itself settles (the
#2519 freshness work + the S0-S4 DRG-node reshape). Do not read this module
as declaring a freeze; it declares a tracked, versioned shape.

**Maintenance rule:** whenever the top-level key set emitted by
``build_charter_context_json`` changes (a key is added, renamed, or
removed), ``CONTEXT_CONTRACT_TOP_LEVEL_KEYS`` MUST be updated in the same
change, and ``CONTEXT_SCHEMA_VERSION`` MUST be bumped so a pinned external
consumer can detect the shape moved instead of discovering it as a silent
``KeyError``/extra-key surprise.
"""

from __future__ import annotations

#: Single-authority stamp for the top-level ``charter context --json``
#: payload shape. Bump this whenever ``CONTEXT_CONTRACT_TOP_LEVEL_KEYS``
#: changes. Semantic-version string (``MAJOR.MINOR.PATCH``); not tied to
#: the package release version.
CONTEXT_SCHEMA_VERSION = "1.3.0"

#: The complete set of top-level keys the ``build_charter_context_json``
#: payload may carry, across both bootstrap (``mode == "bootstrap"``) and
#: non-bootstrap (``mode == "compact"``) actions. Derived from:
#:
#: * ``charter.activation.context.build_charter_context_json`` (the initial ``payload``
#:   dict literal plus the ``"mode"`` key set on both the early-return
#:   non-bootstrap branch and the bootstrap branch) -- the array-valued
#:   entries (``directives``/``tactics``/``styleguides``/``toolguides``/
#:   ``procedures``/``references``) are populated in place by
#:   ``charter.activation.progressive_disclosure.build_disclosure_payload``, which
#:   never introduces a *new* top-level key of its own.
#:
#: **Deliberate ``asset`` asymmetry (#3037, #3389).** ``procedure`` is a
#: first-class typed array here (bumped to 1.1.0), but ``asset`` is NOT:
#: there is intentionally no top-level ``assets`` array. An asset is
#: reference-only -- it has no resolution/install path -- so it is folded
#: into the flat ``references[]`` link set (via ``build_disclosure_payload``'s
#: ``extra_delivered``) and never promoted. Do not "fix" this by adding an
#: ``assets`` key: the omission is the contract.

#: **``directives_source`` provenance (#3728, FR-007, bumped to 1.2.0).** A
#: top-level string|null key naming which branch resolved the directive set
#: (``GovernanceResolution.metadata["directives_source"]``, e.g.
#: ``"catalog_fallback+project_local"``). It is *distinct* from the per-entry
#: ``all_directives[].source`` (artifact origin ``project``/``builtin``/``org``):
#: "which branch resolved the set" vs. "where did this one directive come from".
#: * ``tests/charter/test_context_bootstrap_markers.py`` --
#:   ``TestJsonEntryPointParity::test_json_entry_point_is_valid_bootstrap_payload``
#:   (the structural guard on a bootstrap-mode payload), which asserts the
#:   presence of the array-valued governance keys. (This replaced a frozen
#:   ``json_corpus.golden.txt`` byte-parity fixture retired in mission
#:   rehome-writing-comms-doctrine because it embedded the live directive
#:   catalog and red on every doctrine addition.)
#:
#: This is a superset guard, not a strict-equality contract: which of these
#: keys are actually present is conditional on the action (bootstrap vs.
#: non-bootstrap) and on charter/doctrine state (e.g. an org pack absent ->
#: ``org_charter`` still present but empty-shaped) -- callers must not
#: assert every key appears on every action, only that no undeclared key
#: escapes this ledger.
CONTEXT_CONTRACT_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "context_schema_version",
        "action",
        "mode",
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "procedures",
        "all_directives",
        "directives_source",
        "references",
        "project_charter",
        "org_charter",
        "governance_references",
    }
)

__all__ = ["CONTEXT_SCHEMA_VERSION"]
