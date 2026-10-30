# Design Decisions

> Record decisions that shaped the design and their rationale.

## Entries

- **[2026-10-30][planning] `OrgPackRegistryUnreadableError(ActiveCharterConfigError, ValueError)`**
  raised by `require_declared_org_roots`' registry-read failure arm only. The
  `ActiveCharterConfigError` base carries the `ACTIVE_CHARTER_CONFIG_INVALID` code and rides
  the CLI's existing `config_refusal` mapping (activate converges with zero CLI change);
  the `ValueError` base keeps every strict reader's `except ValueError` contract. The
  not-fetched arm keeps plain `ValueError` → `ACTIVATION_FAILED` with the fetch remedy
  (#4984 posture), per the issue's "keep the declared-pack-not-fetched case distinct".
- **[2026-10-30][planning] Lazy import across the offering→activation seam** (C-001): the
  helper imports `ActiveCharterConfigError` inside the function, mirroring
  `org_pack_discovery._strict_error`'s existing lazy import in the other direction.
- **[2026-10-30][planning] Converge the code, not the message prose.** The two verbs'
  messages name the same cause ("the org pack registry ... cannot be read") but differ in
  remediation prose (deactivate's carries the required-floor remediation line). The issue
  asks for code convergence; unifying prose would couple the two readers' messages for no
  tooling benefit.

## D4 — The typed error's home: `activation_ledger`, not `org_pack_config` (WP01 T002, revision of D3)

**Status:** decided 2026-10-30 (implementation)

**Decision.** `OrgPackRegistryUnreadableError(ActiveCharterConfigError, ValueError)` is
DEFINED in `src/charter/activation/activation_ledger.py`, next to its base, and RAISED
from `require_declared_org_roots` in `src/charter/offering/drg/org_pack_config.py` via a
lazily-importing `_refuse_unreadable_registry(cause)` helper. D3 placed the class
definition in `org_pack_config` itself; that placement is infeasible and was corrected
during implementation.

**Why.** Subclassing requires the base class at class- definition time — a lazy import
cannot feed a `class` statement's bases. And an EAGER module-level import of
`charter.activation.activation_ledger` from `org_pack_config` cycles the import graph:
verified at implementation time — importing `activation_ledger` transitively imports
`org_pack_config` (through `charter.offering.artifact_kinds` and friends), so the
offering module cannot hold the subclass definition. `activation_ledger` is the
documented "error home" of the `ActiveCharterConfigError` family, so the subclass lives
there and crosses the offering→activation seam only at raise time — the exact lazy shape
`org_pack_discovery._strict_error` already uses in the other direction (C-001 preserved).

**Why not re-parent onto `kernel.errors`.** The CLI's zero-change convergence depends on
the raised error being an `ActiveCharterConfigError` instance (activate.py's
`except ActiveCharterConfigError` arm precedes `except (ValueError, DRGLoadError)`), so
the activation base is required, not optional.

**Why not a plain `ActiveCharterConfigError` raise.** The strict org-chain readers
document `except ValueError` (`effective_set`, `preset_application`, `manifest_loader`);
raising a non-ValueError ActiveCharterConfigError from `require_declared_org_roots`
would silently change their refusal behaviour. The dual base is the contract; pinned by
`test_an_unreadable_registry_is_the_typed_refusal_on_both_bases`.

**Message fidelity.** `KittyInternalConsistencyError.__init__` sets `args=(code,)`, so
`str()` of the family is the code. `effective_set` interpolates `str(exc)` into its
refusal text, so the subclass overrides `__str__` to return `body` — the pre-fix
"the org pack registry cannot be read: …" message survives the `ValueError` view
unchanged. Pinned by the same seam test.

**Rejected extension.** Making `org_pack_discovery._strict_error`'s registry arm raise
the subclass too (so deactivate's error would be the same TYPE, not just the same
base+code) — the codes already converge via the base and the deactivate message carries
its own required-floor remediation; threading the distinction through `_strict_error`
is scope creep beyond the issue's contract (C-003).

**Consequence.** Zero CLI change: activate's existing `except ActiveCharterConfigError`
arm renders the typed error as a config refusal (`ACTIVE_CHARTER_CONFIG_INVALID`),
matching deactivate. Verified end-to-end: both verbs, text and `--json`, exit 1 with
`ACTIVE_CHARTER_CONFIG_INVALID`.
## Entries

- **[2026-10-30][planning] `OrgPackRegistryUnreadableError(ActiveCharterConfigError, ValueError)`**
  raised by `require_declared_org_roots`' registry-read failure arm only. The
  `ActiveCharterConfigError` base carries the `ACTIVE_CHARTER_CONFIG_INVALID` code and rides
  the CLI's existing `config_refusal` mapping (activate converges with zero CLI change);
  the `ValueError` base keeps every strict reader's `except ValueError` contract. The
  not-fetched arm keeps plain `ValueError` → `ACTIVATION_FAILED` with the fetch remedy
  (#4984 posture), per the issue's "keep the declared-pack-not-fetched case distinct".
- **[2026-10-30][planning] Lazy import across the offering→activation seam** (C-001): the
  helper imports `ActiveCharterConfigError` inside the function, mirroring
  `org_pack_discovery._strict_error`'s existing lazy import in the other direction.
- **[2026-10-30][planning] Converge the code, not the message prose.** The two verbs'
  messages name the same cause ("the org pack registry ... cannot be read") but differ in
  remediation prose (deactivate's carries the required-floor remediation line). The issue
  asks for code convergence; unifying prose would couple the two readers' messages for no
  tooling benefit.

## D5 — Development-assist test judgment (wrap-up, development-assist-test-cleanup)

**Status:** decided 2026-10-30 (wrap-up)

Tests the mission added, judged per DIRECTIVE_041's keep-vs-delete axis:

- `test_an_unreadable_registry_is_the_typed_refusal_on_both_bases` — **KEEP**. Pins
  the dual-base contract (ActiveCharterConfigError + ValueError), the code, the body
  lead, `str()==body` fidelity, and the chained cause. Deleting the ValueError base
  would change three strict readers; this test is the standing guard against exactly
  that. Not scaffolding.
- `test_a_declared_but_unfetched_pack_stays_a_plain_value_error` — **KEEP**. Pins the
  distinctness of the fetch-remedy refusal (FR-003); re-widening the typed arm would
  false-green the convergence test.
- `test_the_typed_error_crosses_the_seam_only_lazily` — **KEEP**. A subprocess probe
  pinning the import-graph invariant (C-001: no eager charter.activation import from
  org_pack_config at module load). Dev-assist flavored in mechanism (subprocess), but
  it guards a real, recurring regression class (someone "simplifying" the lazy import
  into an eager one would cycle the graph); the repo's own _strict_error seam has the
  same shape. Uses sys.executable and an absolute tempfile dir, so it is cwd-independent.
- `test_a_malformed_charter_packs_config_is_refused` — pre-existing (#6525), re-pinned
  (parametrize collapsed to the constant code, stale asymmetry comment replaced). Not
  mission-added; the re-pin IS the acceptance test.

No issue-named test files (test_issue_6772*, test_repro_*) were created, so there are
no fold-or-keep verdicts to record for those. No characterization/parity oracles, no
WP##/NFR-labeled test names to strip.

## D6 — Aggregate-review correction: the seam respects C-004 (revises D4)

**Status:** decided 2026-10-30 (wrap-up, from the independent aggregate review)

The independent adversarial review of the integrated diff returned **HOLD** with one
BLOCKER: D4's lazy `from charter.activation.activation_ledger import ...` inside
`org_pack_config._refuse_unreadable_registry` violates
`tests/architectural/test_charter_offering_does_not_import_activation.py` — the C-004
one-way boundary gate AST-walks all of `src/charter/offering/**` and forbids ANY
`charter.activation` import, at any scope, with no allowlist. The mission had never run
that gate (targeted-suites-only discipline missed it), and D4's own seam test pinned the
violation as "C-001". The review also flagged (minor) that D4's justification comment
cited `org_pack_discovery._strict_error` as precedent — a same-package lazy import that
crosses no seam, so it licenses nothing here.

**The inverted seam (lands as D6):**

- `charter.offering.drg.org_pack_config` raises an offering-owned
  `UnreadableOrgPackRegistry(ValueError)` from the registry-read arm of
  `require_declared_org_roots` — message and cause chain identical to D4's version;
  offering imports no activation code at any scope (gate now passes unchanged, no
  exemption entry needed).
- `charter.activation.layer_roots.resolve_pack_chain(strict=True)` — the chain
  authority every strict consumer (CLI activate, effective_set, preset_application)
  already goes through — catches `UnreadableOrgPackRegistry` and maps it onto
  `OrgPackRegistryUnreadableError` (`raise ... from cause`, body preserved). The
  lazy same-package import of the typed error lives in that mapping helper and is the
  shape `_strict_error` actually uses (the D4 analogy is now literally accurate):
  `activation_ledger` transitively imports `layer_roots`, so an eager import would
  cycle the same-package graph.
- The not-fetched arm still raises plain `ValueError` and the mapping does not touch
  it (pinned through both `require_declared_org_roots` and `resolve_pack_chain`), so
  activate's `ACTIVATION_FAILED` + fetch remedy is unchanged.

**Why map in `layer_roots` and not the CLI:** the mapping belongs at the one seam
every strict consumer already shares; effective_set and preset_application wrap with
`except ValueError` + `str(exc)`, and the dual base plus `__str__ == body` keeps their
interpolated text byte-identical either way. No CLI code changes.

**Tests re-pointed:** the dual-base pin now drives the refusal through
`resolve_pack_chain(strict=True)` (with the offering-side raise asserted as
`UnreadableOrgPackRegistry` first); the unfetched-distinctness pin asserts the mapping
does not swallow it; the seam probe now pins that the offering raise path leaves
`charter.activation.activation_ledger` unloaded (runtime complement of the static
C-004 gate). Review findings 3 (repr shows the code — family-consistent) and 4
(directive-only JSON coverage — same seam for all kinds) noted, no action.

## D7 — Aggregate review verdicts (wrap-up)

**Status:** recorded 2026-10-30

- **First pass (independent reviewer, kimi-k3, fresh session): HOLD** — one BLOCKER
  (the C-004 boundary-gate violation, fixed as D6), one MINOR (the misleading
  `_strict_error` analogy in D4's comment, fixed with D6), two NOTEs (repr shows the
  code — family-consistent, no action; directive-only JSON coverage — same seam for
  all kinds, no action). Checklist A-H otherwise PASS.
- **D6 delta verification (fresh reviewer session): LAND** — no BLOCKER/MAJOR/MINOR;
  runtime-verified body fidelity across the mapping, non-mapping of the not-fetched
  arm, offering activation-free at any scope, cycle safety at raise time, one-to-one
  caller analysis (layer_roots is the only src caller of require_declared_org_roots;
  all strict consumers receive the identical typed error). Cosmetic NOTE on the dead
  `from cause` sugar at the outer raise (harmless, mypy-friendly, left as-is).

Synthesized wrap-up verdict: **LAND**.
