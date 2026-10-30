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
