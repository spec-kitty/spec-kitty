# Research: Canonical doctrine artifact slug convention

Phase 0 output. Consolidates the research+design pass (design of record: comments on #4832, #4833, convergence note on #2519) **as revised by the post-plan brownfield adversarial point-cut** (3 profile-loaded lenses: architect-alphonso, debugger-debbie, reviewer-renata). No `[NEEDS CLARIFICATION]` markers remain. Scope decisions: durable fix (specify DM), migration **dropped** to go-forward-only (post-plan escalation).

## Decision 1 — Canonical slug convention: kebab-case, id/slug decoupled

- **Decision**: The on-disk filename/slug is `kebab(id)` for directives; the authored `id` (SCREAMING for directives) is preserved inside the file. `id` is canonical identity; slug is a derived handle.
- **Rationale**: The **decoupling** of a human slug from the authored id is the load-bearing precedent from shipped built-ins (`disciplined-refactoring.directive.yaml` ↔ `id: DISCIPLINED_REFACTORING`). *Correction from the squad*: `025-boy-scout-rule.directive.yaml ↔ id: DIRECTIVE_025` is NOT an example of `kebab(id)` (`kebab("DIRECTIVE_025")` = `directive-025`) — it shows a *descriptive* slug, which is a broader decoupling. Project authors use semantic SCREAMING ids (`LOVE_THY_ENEMY`) where mechanical `kebab(id)` is sensible; `NNN-`/descriptive built-in ids never reach the project registration path, so `slug_for` is not extended to them.
- **Alternatives**: `NNN-kebab` (no NNN source for project directives) and preserve-case (diverges from built-in filenames) — both rejected.

## Decision 2 — Single slug authority (`slug_for`) preserving the engine's URL-encoding

- **Decision**: One pure `slug_for(kind, identifier)` helper (home: `src/charter/offering/artifact_kinds.py`, beside `_PATTERNS`), used by the scaffolder and the engine. Definition extracted verbatim from `project_registration.py:187`:
  - directive → `quote(identifier.lower().replace("_", "-"), safe="")`
  - other kinds → `quote(identifier, safe="")`
- **Rationale (squad CRITICAL, 3-lens convergent)**: the engine already wraps its slug in `quote(…, safe="")` to collapse slash-bearing URN identities into one safe path component. Defining `slug_for` as unquoted "verbatim" (the pre-squad draft) would reintroduce a **provenance-directory path escape** for a namespaced id like `agent_profile:team/ops-responder` and regress the existing guard `tests/charter/test_project_registration.py:165-166`. `quote()` is a no-op on kebab/SCREAMING ids, so directives are unaffected. The id-grammar precondition (directives `^[A-Z][A-Z0-9_-]*$`; non-directives lowercase-kebab, URN-safe) is stated so a future reader does not "simplify" the quote away.

## Decision 3 — Validator kind table 3→5 behind one importable SSOT (the #4833 fix)

- **Decision**: Extend `_KIND_SUFFIX`/`_ALL_ARTIFACT_PATTERNS` to the five registration-writing kinds (`directive, tactic, styleguide, procedure, agent_profile`; `agent_profile → .agent.yaml`). Mint a **module-level `DIRECT_WRITE_KINDS`** constant in `artifact_kinds.py` (squad MEDIUM, 3-lens convergent — the kind list is a function-local tuple at `project_scan.py:193` today, not importable), referenced by `scan_project_artifacts`, the `ManifestArtifactEntry.kind` `Literal`, and the validator table. A parity test asserts all consumers agree.
- **Rationale**: `procedure` is a latent identical bug alongside `agent_profile`. Deriving from one constant closes the drift class by construction (DIRECTIVE_043). `glossary_pack`/`paradigm` are not scanned → no sidecar → out of scope.
- **Alternative rejected**: exempting engine-written kinds from the kind check would silently disable orphan detection.

## Decision 4 — Hybrid manifest-driven validation

- **Decision**: The validator resolves *registered* artifacts through the synthesis manifest's `(kind, slug, path, provenance_path)` (which the manifest **already records** for direct-write artifacts — confirmed at `manifest.py:47-61`, so no writer extension is needed). It **retains** the filesystem walk + filename parse for the orphan/legacy directions.
- **Rationale (squad MEDIUM, 3-lens convergent)**: a purely manifest-driven walk cannot see an on-disk artifact or sidecar that is absent from the manifest — the exact orphan/`ghost` corruption NFR-001 requires — and would regress the no-synthesis-state legacy path (NFR-003). Manifest for positive resolution of registered artifacts; disk sweep for orphans (comparing disk sidecars against the manifest `provenance_path` set, not re-parsing artifact filenames). The `<NNN>-` digit-strip test (`test_bundle_validate_extension.py:500`) is kept or retired deliberately with the parse it guards.

## Decision 5 — Migration DROPPED (go-forward only)

- **Decision**: No filename migration/self-heal. Existing SCREAMING-filename repos validate green via Decision 4 (manifest-driven resolution) with authored files untouched.
- **Rationale (squad HIGH, escalated + operator-confirmed)**: (a) the engine records the kebab slug in the manifest regardless of the on-disk filename, so WP03 alone fixes #4832 for existing repos — the rename is **cosmetic**; (b) a rename changes the file *stem*, which is the identity space `activated_directives` keys on (`kind_vocabulary.py:434`), so a hand-authored directive whose stem ≠ id would be **silently dropped from the activated set** (#3816 class); (c) the migration would also invert the registration module's "never mutate authored source" invariant and needs clobber/dirty-tree/crash-atomicity engineering with no mechanism in the real code today. Dropping it removes one HIGH dormant-mask and three migration-safety HIGHs for zero loss of the green-validate outcome.

## Decision 6 — #4834 kept as an independent correctness fix

- **Decision**: Keep the `_registration_records` path/provenance-drift re-write (early-`continue` at `project_registration.py:195`), no longer as a migration precondition but as a standalone latent-bug fix (operator-confirmed to keep). Cheap; guards the manifest against a stale path on unchanged content.

## Adversarial evidence (post-plan brownfield point-cut)

Per `contracts/adversarial-evidence-contract.md`. No contested finding silently dropped.

| Finding (lens) | Severity | Disposition |
|---|---|---|
| Unquoted `slug_for` → provenance path escape; regresses `test_project_registration.py:165-166` (debbie; renata; alphonso) | CRITICAL | **accepted** — Decision 2 preserves `quote(…, safe="")`. |
| WP05 rename is cosmetic; #4832 fixed by manifest-driven WP03 alone (debbie) | HIGH | **accepted** — Decision 5; migration dropped. |
| Rename changes stem → silent `activated_directives` drop for stem≠id directives (debbie) | HIGH | **accepted** — obviated by dropping the rename. |
| Migration inverts "no authored-source mutation" invariant; `PathGuard.rename`=os.rename clobbers; non-transactional; `previous.slug` reuse (renata) | HIGH×3 | **accepted (obviated)** — migration dropped; C-004 restates the invariant as preserved. |
| Manifest-driven resolution weakens orphan-*artifact* direction (alphonso; renata; debbie) | MEDIUM | **accepted** — Decision 4 keeps a hybrid disk sweep; NFR-001 now covers both directions. |
| NFR-002 SSOT is a non-importable function-local tuple (alphonso; renata; debbie) | MEDIUM | **accepted** — Decision 3 mints `DIRECT_WRITE_KINDS`. |
| Built-in precedent rationale unsound (`kebab("DIRECTIVE_025")`≠`025-boy-scout-rule`) (debbie) | MEDIUM | **accepted** — Decision 1 rationale corrected. |
| Fakeable DoDs: hand-written sidecars bypass the real slug path (renata; debbie) | MEDIUM | **accepted** — acceptance tests drive the real engine (`test_project_registration.py` seam); see `quickstart.md`. |
| Existing `<NNN>-` digit-strip parse test pins behavior the switch bypasses (debbie) | MEDIUM | **accepted** — Decision 4 keeps the parse for the orphan path; test kept/retired deliberately in the owning WP. |
| slug_for placement respects layer direction; manifest already carries fields; blast radius contained; #4834 at L195 (all lenses) | concessions | **accepted** — no change needed; recorded as validated. |
| `os.rename` not git-aware (renata) | LOW | **deferred_with_rationale** — moot; migration dropped. |

- **Supply-chain**: N/A — no dependency added/upgraded/removed (stdlib only). `051-supply-chain-install-safety` does not bind.

### Adversarial evidence (post-tasks anti-laziness point-cut)

2 lenses (reviewer-renata fakeable-DoD; paula-patterns decomposition/ownership). All findings `accepted` and folded into the WP prompts.

| Finding (lens) | Severity | Disposition |
|---|---|---|
| NFR-002 parity guard (T005) straddles the WP01/WP02 lane boundary — the `bundle._KIND_SUFFIX` assertion has no clean owner (paula; renata) | HIGH | **accepted** — WP01 T005 asserts scanner+manifest only; WP02 T006 owns the `bundle._KIND_SUFFIX` parity assertion in its own test file. |
| WP02 T009 "registered-clean" is fakeable by hand-fabricating artifact+sidecar+manifest; the 3-kind `_write_artifact` strawman invites extension (renata) | HIGH | **accepted** — T009 MUST drive the real engine (`author_guidance()`+`commit_project_registration()`+`validate_synthesis_state`); extending the strawman to 5 kinds is forbidden. |
| T007 understates scope — manifest must thread through `validate_synthesis_state` into BOTH `_check_artifacts_have_provenance` and `_check_provenance_have_artifacts`, not just the leaf helpers (renata) | MEDIUM | **accepted** — T007 now names all three functions. |
| T012 slug-reconciliation has no falsifying test (renata) | MEDIUM | **accepted** — T012 adds a non-canonical-`previous.slug` rewrite test. |
| T010 "byte-identical" is a post-refactor tautology via T014 convergence (renata) | MEDIUM | **accepted** — WP01 T004 adds a `slug_for == old-inline-expr` equivalence table (incl. digit-bearing directive); T014 reworded to a wiring check. |
| `artifact_kinds.py __all__` omits the two new authorities (paula) | MEDIUM | **accepted** — WP01 T002 adds them. |
| Parity guard itself fakeable if it hardcodes a set instead of introspecting live annotations (renata) | LOW | **accepted** — T005 introspects `typing.get_args` on the live Literal + live scanner tuple. |
| Manifest `Literal` SSOT is by-test not by-construction (renata) | LOW | **accepted (noted)** — a `Literal` can't consume a runtime tuple; the parity test is the guard, stated in T005. |
| plan.md dependency graph describes the stale 5-WP scheme (paula) | LOW | **accepted** — plan.md annotated that tasks.md's 4-WP graph supersedes it. |
| Third slug derivation quarantined for orphans in `bundle.py:482` (paula) | LOW | **accepted (by design)** — intended orphan behavior; contained to WP02-owned bundle.py; flagged for the WP02 reviewer. |
| No WP02↔WP03 ordering deadlock (engine already kebabs; T010 byte-identical); no source-file ownership leak; blast radius contained to named files; T015 real-engine seam exists and is non-fakeable; #4834 early-`continue` confirmed (paula; renata) | concessions | **accepted** — validated; no change. |

