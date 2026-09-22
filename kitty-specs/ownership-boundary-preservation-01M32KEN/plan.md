# Implementation Plan: Ownership-Boundary Preservation for Mutating Flows

**Branch**: `fix/ownership-boundary-preservation` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/ownership-boundary-preservation-01M32KEN/spec.md`

## Summary

Close the charter class *Ownership Boundaries for Mutating Flows* (charter L463–479) by
construction. Introduce ONE shared ownership-mutation guard in `specify_cli` — a thin
*prove-ownership-or-preserve/archive-with-diagnostic* decision surface that dispatches to a
per-signal prover (`manifest` / `managed_path` / `canonical_content`) and delegates mechanical
write/backup to reused kernel/`template`/`skills` primitives. Route every same-root destructive
filesystem site in the mutating-flow module set (`cli/commands/init.py` + `upgrade/migrations/`)
through it (10 fix sites, incl. #4859/#4861/#4862; 4 borderline sites resolved by red-first
probe), leaving genuinely-safe ops in a frozen, rationalized, shrink-only allowlist. Prove the
class closed with a non-vacuous AST gate (census + positive-routing assertions + self-mutation).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib (`shutil`, `pathlib`, `hashlib`); reuse in-repo `kernel.atomic`, `specify_cli.tool_surface.operations.OwnershipProof`, `specify_cli.skills.installer` (`_replacement_is_owned`, `_archive_existing_path` core), `specify_cli.template.manager.back_up_operator_subtrees`, `specify_cli.skills.manifest` / `manifest_store`
**Storage**: filesystem only — `.kittify/` manifests (`skills-manifest.json`, `command-skills-manifest.json`) and timestamped backups (`.kittify/.backup-<ts>/`, `.kittify/.migration-backup/…`)
**Testing**: pytest (unit + integration), mypy --strict, ruff, ruff format; new arch gate under `tests/architectural/`
**Target Platform**: Linux / macOS / Windows 10+ (cross-platform; symlink + Windows mode caveats honored)
**Project Type**: single project (`src/specify_cli/…`)
**Performance Goals**: N/A — cleanup paths are one-shot; per-op ownership check is O(files) manifest lookup + a hash compare, negligible vs. the surrounding I/O
**Constraints**: ownership *judgement* stays in `specify_cli` (kernel stays zero-dep); no `--feature` CLI surface; no code in `specify_cli/__init__.py`; zero new blanket lint/type suppressions; fail-closed toward preservation
**Scale/Scope**: 1 new guard module/package + ~10 routed destructive sites across `init.py` and ~9 migration modules + 1 new arch gate; ~13 red-first repro suites

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter present (`.kittify/charter/charter.md`). Binding items and how this plan satisfies them:

- **Ownership Boundaries for Mutating Flows (L463–479)** — the mission's reason to exist. Every routed site proves ownership by manifest/managed-path/canonical-content, else preserves+warns (L472); name heuristics are never proof (L470); each site documents its ownership proof in code (L479 → NFR-006). ✅ central to the design.
- **Architectural gate discipline / DIRECTIVE_043 (Standing Order #5)** — non-vacuous gate: concrete call-site floor (census over the module set), self-mutation test (both directions), shrink-only allowlist, positive-routing assertions. ✅ WP for the gate.
- **ATDD-first / C-011 (Standing Order #4)** — each site's failing repro committed before its fix; reviewer verifies red-on-base→green. ✅ per-site red-first WPs; the #4859 bug-locking test is reworked.
- **Single canonical authority / DIRECTIVE_044** — ONE guard, not N per-site patches; reuse existing `OwnershipProof` vocabulary + backup primitives rather than inventing parallels. ✅ FR-007/C-002.
- **Architectural alignment / layer rules (DIRECTIVE_001)** — guard lives in `specify_cli`; only mechanical write/backup delegates down to `kernel`. ✅ NFR-003.
- **Locality of change / boy-scout / reconciler** — scope expanded deliberately (operator decision) to close the class; each migration touched only for the routing change + its rationale, no unrelated edits. ✅
- **Terminology canon** — internal `feature_dir`/`feature_slug` only; no new `--feature` flag; migration prose adds no retired `sync` tokens. ✅ C-004/C-005.
- **`__all__` / C-007** — new guard module declares `__all__`; no new `kernel` symbol required (backup/atomic already exist), so the symbol-level dead-code gate is not triggered. ✅

No violations requiring Complexity-Tracking justification. (Re-checked post-design: unchanged.)

## Project Structure

### Documentation (this mission)

```
kitty-specs/ownership-boundary-preservation-01M32KEN/
├── plan.md              # This file
├── research.md          # Phase 0 output (decisions, borderline resolution, adversarial evidence)
├── data-model.md        # Phase 1 output (guard model, prover contracts, census fix-list + allowlist)
├── quickstart.md        # Phase 1 output (how to add a new routed site / allowlist entry)
├── contracts/
│   └── ownership-guard-contract.md   # guard decision interface + gate invariant (the ATDD contract)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── asset_preservation/              # NEW — the shared guard (named distinctly; NOT specify_cli/ownership/ nor git/destructive_guard)
│   ├── __init__.py                  #   public API: guard_destructive_removal(...), OwnershipVerdict, provers, AnyProver; declares __all__
│   ├── guard.py                     #   decision surface: prove-or-preserve/archive + diagnostic
│   ├── provers.py                   #   ManifestProver(2 predicates) / ManagedPathProver / CanonicalContentProver(data-injected) / AnyProver
│   └── backup.py                    #   copy-only verbatim writer (extracted core) + dir-granular back_up_operator_subtrees delegation
├── cli/commands/init.py             # ROUTED: #4861 command-templates cleanup (managed_path)
└── upgrade/migrations/
    ├── m_3_2_0rc45_retire_standalone_skill_surface.py   # ROUTED: #4859 (manifest)
    ├── m_3_1_1_charter_rename.py                        # ROUTED: #4862 :195 (+ borderline :148/:161) (canonical_content/managed_path)
    ├── m_0_10_0_python_only.py                          # ROUTED: :175/:187 scripts (+ borderline :250) (canonical_content)
    ├── m_0_10_2_update_slash_commands.py                # ROUTED: :153 commands/*.toml (canonical_content/manifest)
    ├── m_2_0_11_remove_clarify_command.py               # ROUTED: :52 clarify (canonical_content)
    ├── m_2_1_2_remove_release_skill.py                  # ROUTED: :55 release skill (manifest)
    ├── m_2_2_0_profile_context_deployment.py            # ROUTED: :61 profile-context (canonical_content)
    ├── m_3_2_0rc43_retire_profile_context_command.py    # ROUTED: :48 profile-context (canonical_content)
    ├── m_0_6_7_ensure_missions.py                       # BORDERLINE B3: probe → route-or-allowlist
    └── m_unify_charter_activation_finalize.py           # BORDERLINE B4: probe → route-or-allowlist

tests/
├── architectural/
│   └── test_mutation_ownership_routing.py   # NEW non-vacuous gate (census + positive-routing + self-mutation)
├── specify_cli/upgrade/migrations/          # red-first repros per migration (preserve + owned-delete both directions)
├── init/  ·  tests/cli/                      # #4861 init repros (config.yaml present AND absent)
└── specify_cli/asset_preservation/          # NEW guard + prover unit tests (single home; avoids overlap with WP03 skills tests)
```

**Structure Decision**: single-project layout. The guard is a **new distinctly-named package**
`src/specify_cli/asset_preservation/` (C-003 — never `specify_cli/ownership/`, which is WP-scope
manifests; the name also avoids the `git/destructive_guard.py` "guard" token and the "ownership"
token — its job is *preservation on unproven ownership*). It owns the ownership *judgement* +
preserve/archive orchestration; it imports down to `kernel.atomic` and reuses
`template.manager`/`skills`/`manifest_store` primitives, never the reverse. The tests reuse the
existing `test_destructive_op_routing.py` AST-census/self-mutation plumbing via a shared helper
(DIRECTIVE_044) rather than copying it.

## Complexity Tracking

*No Charter/Constitution violations to justify.* The scope is deliberately broad (whole-class
closure, operator decision) but each unit is small: one guard package + one routing edit per
site + one gate. Function-complexity ceiling (≤15) is respected by splitting guard/provers/backup
into separate small functions.

## Parallel Work Analysis

### Dependency Graph

```
WP01 asset_preservation guard + provers + backup + unit tests (FOUNDATION — blocks all routing)
        │
        ├── WP03 #4859 skill-retirement (rework bug-locking test)      ┐
        ├── WP04 #4861 init command-templates                          │
        ├── WP05 #4862 charter-rename :195 (+ B1 :148/:161)            │  Wave 1 (parallel;
        ├── WP06 scripts m_0_10_0 :175/:187 (+ B2 :250)                │  disjoint files —
        ├── WP07 m_0_10_2 commands/*.toml                              │  no overlap)
        ├── WP08 command retirements (clarify/release/profile-context) │
        └── WP09 borderlines B3 (m_0_6_7) + B4 (m_unify) probe+decide  ┘
                          │
                          └── WP02 non-vacuous gate + CHANGELOG + docs (INTEGRATION — after all routing)
```

### Work Distribution

- **Sequential (foundation)**: WP01 (the guard) must land first — every routing WP imports it. WP02 (the gate) must land last — its positive-routing + census assertions go green only once all sites are routed.
- **Parallel streams**: WP03–WP09 each own a disjoint file set (one migration module or `init.py`), so they run in parallel lanes with no file overlap (charter ownership-map leeway: no-overlap is the real guard).
- **Agent assignments**: python-pedro for the guard + migration routing; reviewer-renata for review; each WP is a lane.

### Coordination Points

- **Integration schedule**: routing WPs merge after WP01; the gate WP (WP02) merges last and is the class-closure proof.
- **Integration tests**: `make test-fast` + the touched migration/init/skills suites + the new `tests/architectural/test_mutation_ownership_routing.py` + full `tests/architectural/` (new module + gate ⇒ cross-cutting).
- **Borderline resolution (WP09)**: each borderline gets a red-first probe; if it proves user-content loss is possible → route through guard; else → allowlist with a documented rationale. NOTE B3 (`m_0_6_7`) must still permit removal-for-recopy (the guard preserves only untracked/user members, then the legitimate recopy proceeds).
