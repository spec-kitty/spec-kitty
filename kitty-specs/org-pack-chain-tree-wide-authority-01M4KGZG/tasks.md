# Tasks: Tree-wide org-pack chain authority

**Mission**: org-pack-chain-tree-wide-authority-01M4KGZG
**Branch**: `feat/org-pack-chain-tree-wide-authority`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

Exact per-caller replacements are in [research.md](./research.md) Decision 2. Posture is preserved everywhere except the three #4984 decision surfaces (WP03), which move existing-filtered → `strict=True`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Migrate `runtime_bridge_io.py:465` → `resolve_pack_chain(strict=False)` (keep lazy import; refresh DEC-004/005 comment) | WP01 | |
| T002 | Migrate `runtime/resolver.py:356` and `:818` → `resolve_pack_chain(strict=False)` | WP01 | |
| T003 | Migrate `mission_loader/command.py:235` → `resolve_pack_chain(strict=False)` | WP01 | |
| T004 | Refresh `_internal_runtime/discovery.py:82` docstring (org_roots now via `resolve_pack_chain`) | WP01 | |
| T005 | Migrate `skills/catalog.py:154` → `resolve_pack_chain(strict=False)` | WP02 | [P] |
| T006 | Migrate `invocation/org_profiles.py:67` → `resolve_pack_chain(strict=False)` (keep `try/except → []`) | WP02 | [P] |
| T007 | Migrate `cli/commands/profiles_cmd.py:109` → `resolve_pack_chain(strict=False)` | WP02 | [P] |
| T008 | Migrate `cli/commands/_charter_pack_collect.py:258/365/609/1213` → `resolve_pack_chain(strict=False)`; verify `CharterOfferingService` no-ops absent roots | WP02 | |
| T009 | Red-first regression: `gate_bindings` unfetched pack ⇒ raises (names pack + `spec-kitty charter fetch`) | WP03 | |
| T010 | Migrate `review/gate_bindings.py:286` → `resolve_pack_chain(strict=True)` [#4984] | WP03 | |
| T011 | Red-first regression: `executor` unfetched pack ⇒ raises | WP03 | |
| T012 | Migrate `mission_step_contracts/executor.py:194` → `resolve_pack_chain(strict=True)` [#4984] | WP03 | |
| T013 | Migrate `tool_surface/providers/agent_profiles.py:574` → `resolve_pack_chain(strict=True)`; canonical message; update old-message test | WP03 | |
| T014 | Migrate `upgrade/migrations/_retired_activation.py:353` → `resolve_pack_chain(strict=False)` (keep retired-key splice) | WP04 | |
| T015 | Confirm `charter.drg` stays frozen; callers import `resolve_pack_chain` directly from `charter.activation.layer_roots` | WP04 | |
| T016 | Widen `_SCOPE_DIRS` → `src/`; add `src/charter/offering/**` scan-exclusion rule | WP05 | |
| T017 | Raise `_SCANNED_FILE_FLOOR`; extend module docstring (name-paired readers rely on existing rule semantics) | WP05 | |
| T018 | Confirm gate green tree-wide, allowlist empty; positive control — a reintroduced direct call trips the gate | WP05 | |

## Work Packages

### WP01 — Runtime-tier lenient hot-path migration
- **Goal**: route the runtime/next template-discovery + resolution hot paths onto `resolve_pack_chain(strict=False)` with no behaviour change.
- **Priority**: P1 · **Independent test**: two-pack project resolves identical ordered chain through each migrated caller; existing runtime tests green.
- **Subtasks**: T001, T002, T003, T004
- **Dependencies**: none
- **Risks**: keep lazy imports lazy; raw→`strict=False` adds an existence filter (harmless in template search).
- **Prompt**: [tasks/WP01-runtime-hot-paths.md](./tasks/WP01-runtime-hot-paths.md)

### WP02 — specify_cli lenient callers
- **Goal**: migrate the best-effort / diagnostic / read-only specify_cli callers to `strict=False`.
- **Priority**: P1 · **Independent test**: `doctor charter-packs`, profile view, skills prefilter behave identically; existing tests green.
- **Subtasks**: T005, T006, T007, T008
- **Dependencies**: none
- **Risks**: verify `CharterOfferingService` no-ops absent roots before the `_charter_pack_collect` raw→filtered swap.
- **Prompt**: [tasks/WP02-specify-cli-lenient.md](./tasks/WP02-specify-cli-lenient.md)

### WP03 — #4984 fail-closed decision surfaces
- **Goal**: move the three governed decision surfaces to `strict=True` so a declared-but-missing pack fails closed (completes #4984).
- **Priority**: P1 · **Independent test**: unfetched pack ⇒ each surface raises naming the pack + remedy; configured chain unchanged.
- **Subtasks**: T009, T010, T011, T012, T013
- **Dependencies**: none
- **Risks**: real behaviour change (refuse vs degrade) — red-first per surface + CHANGELOG at closeout; update tests asserting the old `agent_profiles` message / monkeypatching old primitives.
- **Prompt**: [tasks/WP03-4984-fail-closed.md](./tasks/WP03-4984-fail-closed.md)

### WP04 — migration-tier caller + drg.py decision
- **Goal**: migrate `_retired_activation.py:353`; confirm `charter.drg` stays a frozen compat surface.
- **Priority**: P2 · **Independent test**: retired-activation migration path resolves the same roots; `charter.drg` re-exports unchanged.
- **Subtasks**: T014, T015
- **Dependencies**: none
- **Risks**: `_retired_activation` is frozen — keep byte-identical; its `_retired_key_org_roots` is not a census hit.
- **Prompt**: [tasks/WP04-retired-activation-and-drg.md](./tasks/WP04-retired-activation-and-drg.md)

### WP05 — widen the census gate tree-wide (LANDS LAST)
- **Goal**: widen the FR-006 census to all of `src/` with the allowlist empty and rule-based exemptions.
- **Priority**: P1 · **Independent test**: gate green tree-wide after WP01–04; red when a direct call is reintroduced on a non-exempt surface.
- **Subtasks**: T016, T017, T018
- **Dependencies**: WP01, WP02, WP03, WP04
- **Risks**: offering exclusion must be a documented rule, not an allowlist entry; file floor must track the tree-wide count.
- **Prompt**: [tasks/WP05-widen-census-gate.md](./tasks/WP05-widen-census-gate.md)

## MVP / sequencing

WP01–WP04 are mutually independent (parallelizable across lanes); WP05 depends on all four and must land last (widening before the callers migrate turns the gate red).
