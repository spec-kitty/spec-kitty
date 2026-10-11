# Research — Tree-wide org-pack chain authority

Phase 0 findings. Source: brownfield scout over current `main` (post-#6006). Read-only; file:line verified against the tree.

## Decision 1 — The forbidden-primitive set is exactly four, and the issue's caller list needed correction

- **Decision**: the census gate forbids `{resolve_org_roots, resolve_existing_org_roots, require_declared_org_roots, resolve_org_root_chain}`. `resolve_org_dirs` is **not** forbidden (it returns subdir-joined dirs + a per-dropped-root WARNING — a different primitive), and `resolve_org_root_chain` does not exist (named defensively).
- **Consequence**: `gate_bindings.py:176`, `mission_loader/command.py:275`, `executor.py:173` (all `resolve_org_dirs`) are **out of scope**. `discovery.py:82` is a docstring, not a call. One caller **missing** from the issue list must be added: `_retired_activation.py:353`.
- **Rationale**: a tree-wide call census (forbidden-primitive calls under `src/`, excluding `charter/offering/**`, tests, and the owner) returns exactly the 13 call sites the plan migrates.
- **Alternatives considered**: migrating `resolve_org_dirs` too — rejected: it would drop the NFR-002 per-dropped-root WARNING; it is a legitimately distinct primitive.

## Decision 2 — Per-caller posture classification (decision surface vs lenient hot path)

| Caller (file:line) | Today | Posture | Class | Replacement |
|---|---|---|---|---|
| runtime_bridge_io.py:465 | `resolve_org_roots(repo_root, quiet=True)` | raw | hot path | `resolve_pack_chain(repo_root, strict=False)` |
| runtime/resolver.py:356,818 | `resolve_org_roots(project_dir, quiet=True)` | raw | hot path | `resolve_pack_chain(project_dir, strict=False)` |
| mission_loader/command.py:235 | `resolve_org_roots(repo_root, quiet=True)` | raw | hot path | `resolve_pack_chain(repo_root, strict=False)` |
| skills/catalog.py:154 | `resolve_existing_org_roots(project_root)` | existing-filtered | hot path (prefilter) | `resolve_pack_chain(project_root, strict=False)` |
| invocation/org_profiles.py:67 | `[r for r in resolve_org_roots(repo_root) if r.exists()]` | existing-filtered | hot path | `resolve_pack_chain(repo_root, strict=False)` (keep try/except→[]) |
| cli/commands/profiles_cmd.py:109 | `[r for r in resolve_org_roots(repo_root) if r.exists()]` | existing-filtered | hot path (view) | `resolve_pack_chain(repo_root, strict=False)` |
| cli/commands/_charter_pack_collect.py:258,365,609,1213 | `resolve_org_roots(repo_root)` | raw | hot path (diagnostic) | `resolve_pack_chain(repo_root, strict=False)` |
| upgrade/migrations/_retired_activation.py:353 | `resolve_existing_org_roots(project_path)` | existing-filtered | hot path (frozen migration) | `resolve_pack_chain(project_path, strict=False)` (keep retired-key splice) |
| review/gate_bindings.py:286 | `resolve_existing_org_roots(repo_root)` | existing-filtered | **DECISION surface** | `resolve_pack_chain(repo_root, strict=True)` **[#4984]** |
| mission_step_contracts/executor.py:194 | `resolve_existing_org_roots(context.repo_root)` | existing-filtered | **DECISION surface** | `resolve_pack_chain(context.repo_root, strict=True)` **[#4984]** |
| tool_surface/providers/agent_profiles.py:574 | `resolve_org_roots(root)` + manual is-dir raise | manual fail-close | **DECISION surface** | `resolve_pack_chain(root, strict=True)` **[#4984 — canonical message]** |

- **Rationale**: a decision surface is one where acting on a silently-shortened chain is an integrity hole — review-gate bindings (`gate_bindings`), step-contract execution/delegation (`executor`), and required-profile projection (`agent_profiles`, which already refuses on an absent root). Everything else is discovery/projection/best-effort/diagnostic where silent-degrade is deliberate.
- **Note**: `strict=False` is byte-identical to `resolve_existing_org_roots`. For the raw `resolve_org_roots` sites this *adds* an existence filter — harmless (absent roots are no-ops in template search and in `CharterOfferingService`), noted in WP notes, no behaviour-change test.

## Decision 3 — #4984 fail-closed is a real behaviour change (crash-vs-degrade), accepted

- **Decision**: the three decision surfaces move existing-filtered → `strict=True`; a declared-but-unfetched pack raises (naming the pack + `spec-kitty charter fetch` remedy). This is the explicit intent of #6012/#4984.
- **Consequence**: `review` and step-contract execution will refuse rather than silently proceed on an unfetched pack. Each gets a red-first regression (unfetched pack ⇒ raises) and a CHANGELOG entry. `agent_profiles` already manual-raises → only the message becomes canonical; update any test asserting its old `"Required org profile root unavailable"` string.

## Decision 4 — `charter.drg` stays a frozen compat surface; callers import the authority directly

- **Decision**: leave `charter.drg`'s primitive re-exports (`resolve_existing_org_roots`, `resolve_org_dirs`, `resolve_org_roots`, `load_pack_registry`) in place — tests and `resolve_org_dirs` facade users depend on them. Migrated callers import `resolve_pack_chain` **directly from `charter.activation.layer_roots`**, matching all 16 existing importers.
- **Rationale**: scout verified runtime/next already imports `charter.activation.*` directly (prompt_builder, decision, runtime_bridge_composition) and no `charter/offering/**` module imports `charter.drg` at runtime, so this introduces no layering inversion. Optionally adding `resolve_pack_chain` to `charter.drg` is safe but unnecessary.
- **Alternatives considered**: forcing runtime/next through a `charter.drg` facade re-export (DEC-004 literal reading) — not required; direct import is the established convention.

## Decision 5 — Census widen (FR-003/FR-004), allowlist stays empty

- **Decision**: in `tests/architectural/test_org_pack_chain_single_authority.py`: set `_SCOPE_DIRS = (_REPO_ROOT / "src",)`; add a **scan-exclusion rule** skipping files under `src/charter/offering/**` (the tier defines + cross-calls the primitives and cannot import the activation authority); raise `_SCANNED_FILE_FLOOR` from 100 to track the tree-wide count; keep `_ALLOWED = frozenset()`; extend the module docstring to note the two name-paired tree-wide readers rely on existing rule semantics.
- **Name-paired exemption needs no code**: `_enumerate_org_pack_paths[_strict]` (`org_pack_discovery.py:70,93`) and `pack_context._read_org_packs` (`pack_context.py:747`) call `load_pack_registry()` (not a forbidden primitive) and return name-paired tuples / capture `pack.name`, so Rule 1 misses them and Rule 2 (`_is_bare_root`/`captures_name`) exempts them already. `_retired_activation._retired_key_org_roots` iterates retired-key entries, not `registry.packs`, so it is not a Rule-2 hit either.
- **Rationale**: ADR 2026-09-30-1 forbids ever adding to the allowlist; legitimate exemptions are rules, not entries (C-003).

## Risks (whack-a-field / parallel-authority)

- `resolve_org_dirs` siblings must NOT be "helpfully" migrated (drops the per-dropped-root WARNING — NFR-002 trap).
- `_charter_pack_collect` raw→filtered is safe only if `CharterOfferingService` no-ops absent roots (verify in WP02); per-pack health comes from separate `registry.packs` loops.
- Tests monkeypatching the old primitive *on a migrated module*, or asserting `agent_profiles`' old message, must move their patch target / assertion to `resolve_pack_chain`.
- Keep the lazy imports lazy on migration; update the DEC-004/005 comment blocks that still name `resolve_org_roots`.

## Supply chain

No dependency added/upgraded/removed — DIRECTIVE_051 / supply-chain-install-safety not triggered.
