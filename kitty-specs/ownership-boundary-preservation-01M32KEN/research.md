# Phase 0 Research: Ownership-Boundary Preservation

**Mission**: ownership-boundary-preservation-01M32KEN · Base: `main` @ `32cfc272ee`

## Decision 1 — One guard as a decision surface over per-signal provers (not one monolithic function)

- **Decision**: The shared guard is a thin *prove-or-preserve/archive* decision surface. Ownership is proven by one of three pluggable provers keyed to the reused `OwnershipProof.kind`: `manifest`, `managed_path`, `canonical_content`. The caller (each site) selects the prover matching its available signal.
- **Rationale**: The three headline sites carry *different* signals — #4859 has skills manifests (`manifest`); #4861's `.kittify/command-templates/` and #4862's `.kittify/charter/` governance files have **no manifest** (`managed_path` / `canonical_content`). A single function hard-wired to the skills-manifest predicate (`_replacement_is_owned`) cannot serve the manifest-less sites without dragging skills-only machinery across a context boundary (architect lens, post-spec squad).
- **Alternatives rejected**: (a) three per-site patches — recreates the #4759→#4861 residual drift and cannot be gated as one class; (b) forcing skills-manifest machinery onto manifest-less sites — a boundary leak (DIRECTIVE_001).
- **Evidence**: `OwnershipProof` (`src/specify_cli/tool_surface/operations.py:93`, kinds `manifest`/`managed_path`/`canonical_content`); `_replacement_is_owned` is `ManagedSkillManifest`-typed (`skills/installer.py:187`).

## Decision 2 — Model the `canonical_content` prover on the already-fixed charter-named hazard

- **Decision**: The `canonical_content` prover follows `m_3_1_2_globalize_commands._is_generated_file` (version-marker `<!-- spec-kitty-command-version:` ⇒ package-generated) and `m_2_0_7._matches_package_default` (byte-match). "No marker / no byte-match" ⇒ user-authored ⇒ preserve.
- **Rationale**: `m_3_1_2_globalize_commands` is the exact charter L478 hazard and is **already correctly guarded** — it is the canonical exemplar, not a fix target. Copying its proven pattern is DIRECTIVE_044 (reconcile to the canonical authority) rather than inventing a new predicate.
- **Evidence**: census (`scratchpad/census-classification.md`); charter Proof Trail L474–479.

## Decision 3 — Backup strategy: preserve in place, archive only when the parent is removed

- **Decision**: When ownership is unprovable, preserve the file **in place** if its parent directory survives; **archive** (verbatim, timestamped, collision-safe) only when the parent directory is itself being removed (e.g. #4862's `rmtree(constitution_dir)`, #4859's dir removal). Reuse `template.manager.back_up_operator_subtrees` (dir-granular) and the extracted mechanical file-archive core of `skills.installer._archive_existing_path`; route rewrites through `kernel.atomic.atomic_write`.
- **Rationale**: charter L472 says "preserve the file and emit a warning" (in place) and L469 forbids gratuitous rename/move; archiving is a *move*, so it is used only where in-place preservation is impossible because the parent is being deleted (reviewer lens). Reusing the #4759 backup helper is DIRECTIVE_044.
- **Alternatives rejected**: always-archive (needless relocation for in-place-feasible sites); hand-rolled backup (duplicate authority).

## Decision 4 — Non-vacuous gate reuses the AST-census PATTERN, in a NEW filesystem-op gate

- **Decision**: A new `tests/architectural/test_mutation_ownership_routing.py` performs a LIVE AST census of destructive FS ops (`shutil.rmtree`, `Path.unlink`/`os.unlink`, `shutil.move`, `_safe_rmtree`/`_safe_unlink`) over the module set `cli/commands/init.py` + `upgrade/migrations/*.py`. Each op must be (a) inside the guard's own implementation, (b) reached only via the guard chokepoint (carries no raw destructive literal), or (c) a frozen, individually-rationalized, shrink-only allowlist member. Plus: a **positive-routing assertion** per fixed site (mirroring `test_live_worktree_removal_sites_route_through_the_guard`), and self-mutation tests both directions (planted un-routed op ⇒ fail; dropped allowlist entry ⇒ fail).
- **Rationale**: The existing `tests/architectural/test_destructive_op_routing.py` gates **git** commands, not FS ops — so this is a NEW gate reusing its proven *methodology*, not an extension of it (planner lens). The positive-routing assertion prevents the gate being faked by allowlisting a target op (reviewer lens).
- **Baseline governance**: the shrink-only allowlist is registered per charter Burn-down Policy (`tests/architectural/_baselines.yaml`) or as an in-file frozen `_ALLOWLIST` mirroring the existing gate; finalized in tasks. Growth fails CI; shrinkage warns.

## Decision 5 — Borderline sites resolved objectively by red-first probe

For each of the 4 borderline ops, write a red-first test that attempts to lose user-authored
content through the real entry point:

| Borderline | Op | Resolution rule |
|-----------|-----|-----------------|
| B1 | `m_3_1_1:148` rmtree `missions/<m>/constitution/`; `:161` unlink stale `memory/constitution.md` | Governance content — route through guard (preserve/archive unless canonical-content-proven). |
| B2 | `m_0_10_0:250` rmtree `.kittify/scripts/tasks/` | Same cavalier flow as the :175 sweep — route through guard. |
| B3 | `m_0_6_7:119` rmtree incomplete `REQUIRED_MISSION` dir then `copytree` | **archive-then-recopy** (in-place preserve is impossible — `copytree(dirs_exist_ok=False)` needs the dest absent): archive any user/untracked member OUT to `backup_parent`, then the legitimate `rmtree`+`copytree` proceeds. Red-first asserts the user member lands in the backup. |
| B4 | `m_unify_charter_activation_finalize:439` unlink compiled doctrine bundle | If the bundle can diverge from `charter.yaml` (content-loss path noted in census), route with a fold-then-delete/canonical-content check; else allowlist as compiled-artifact. |

Rule: route iff a red-first test proves user-content loss is possible; else allowlist with a documented rationale (NFR-006). No borderline is silently dropped.

## Supply-Chain Security (051-supply-chain-install-safety)

**N/A — no dependency added, upgraded, or removed.** The mission uses only Python stdlib and
in-repo modules; no `pyproject.toml`/lockfile dependency change, no install lifecycle scripts.
Recorded per the advisory posture: examined and found not applicable (not silently skipped).

## Adversarial Evidence (post-spec squad, contracts/adversarial-evidence-contract.md)

Post-spec squad (planner-priti / reviewer-renata / architect-alphonso), profile-loaded,
read-only. Contested findings and dispositions:

| Finding (lens) | Severity | Disposition |
|----------------|----------|-------------|
| Gate census boundary undefined + unscoped same-root sibling sites (planner) | HIGH | **changed** — scope expanded (operator) to close the whole class; module set enumerated; census produced the fix-list + allowlist. |
| Gate fakeable without a positive-routing assertion (reviewer) | MEDIUM | **accepted/changed** — NFR-002/SC-003 now require positive-routing assertions per fixed site. |
| C-002 over-claims uniform primitive reuse (architect) | MEDIUM | **accepted/changed** — guard reframed as decision surface + per-`OwnershipProof.kind` provers; skills primitives scoped to the manifest family. |
| #4861 command-templates ownership-proof underspecified (reviewer) | MEDIUM | **accepted/changed** — `managed_path` prover specified for the manifest-less command-templates site; FR-001 reconciled. |
| #4861 fix covers only 1 of 3 rmtrees in the loop (planner) | MEDIUM | **corrected** — `init.py:1568` is ONE `rmtree` literal in a 3-name loop, so it is **routed** through the guard (the `ManagedPathProver` preserves `command-templates`, still deletes `templates`/`.scratch`), NOT allowlisted (allowlisting a target op would defeat positive-routing non-vacuity). |
| "extends test_destructive_op_routing.py" misleads (planner) | LOW | **accepted** — reworded to "reuses the PATTERN in a NEW FS-op gate". |
| US priority-header scale confusion / US3 P2 vs #4862 P1 (planner) | LOW | **accepted** — stories relabeled to a delivery-slice scale; issue priority shown separately. |
| "no config.yaml" not load-bearing (reviewer) | LOW | **accepted** — US2 adds a config.yaml-present preservation scenario. |
| archive-vs-in-place tension with L469/L472 (reviewer) | LOW | **accepted** — FR-002 prefers in-place; archive only when parent removed. |
| SC-004 coord-layout clause vacuous (reviewer) | LOW | **accepted** — dropped. |
| L479 "document ownership proof" only implicit (reviewer) | INFO | **accepted** — NFR-006 requires an in-code rationale per routed site + allowlist entry. |

No contested finding was silently dropped.

## Decision 6 — Script sites (`m_0_10_0` `.sh`/`.ps1`): preserve-all (charter-mandated)

- **Decision**: `.kittify/scripts/bash/*.sh` and `powershell/*.ps1` carry no version marker (marker is markdown/`#`-comment for command files, never injected into scripts) and the package no longer ships a canonical to byte-match (the migration exists *because* it went python-only). No content signal exists ⇒ `CanonicalContentProver.prove()` returns `None` ⇒ **preserve-all**. The migration's expectations are rewritten from "Total scripts removed: N" to "preserved M unprovable script(s) + warning"; it no longer deletes scripts by glob.
- **Rationale**: Charter L472 is explicit — when ownership cannot be proven, preserve + warn. With no signal, the charter-correct outcome is preserve-all. This DOES close the class (zero user bytes lost); the retired package scripts are inert and simply linger (an operator may remove them manually).
- **Alternatives rejected**: (a) vendored per-version digest set of historically-shipped script bytes — a valid `canonical_content` signal but high-effort/low-value for an old migration; revisit only if precise delete-owned is later required. (b) allowlisting the script deletes — **unsafe/dishonest**: the current code deletes *custom* scripts, so "no signal" is not a safe rationale.
- **Same rule** applies to borderline B2 (`m_0_10_0:250` `scripts/tasks/`).

## Post-plan adversarial evidence (feasibility / decomposition / ATDD lenses)

| Finding (lens) | Severity | Disposition |
|----------------|----------|-------------|
| `canonical_content` has no signal for `.sh`/`.ps1` scripts (pedro) | HIGH | **changed** — Decision 6: preserve-all + rewrite migration expectations. |
| Prover re-fragmentation: caller-selected prover + per-site canonical source/marker (paula) | HIGH | **changed** — canonical-source + marker-syntaxes injected as constructor DATA; one `prove()` code path; ATDD covers `.sh` + `.md`/`.toml` markers. |
| Dual-prover sites (#4, #9) have no composition; guard takes one prover (paula) | HIGH | **changed** — first-class ordered `AnyProver([...])` composite. |
| Manifest-owned-DELETE direction untested ⇒ preserve-everything guard passes #4859 (renata) | HIGH | **changed** — C4 requires a NEW owned-delete test per manifest/canonical site; #4859 flip is paired with it. |
| ManifestProver needs two predicates (managed vs command manifest shapes) (pedro) | MEDIUM | **accepted** — split predicates; `_replacement_is_owned` covers managed only. |
| B3 `m_0_6_7` preserve-in-place breaks `copytree` (pedro/renata) | MEDIUM | **changed** — archive-then-recopy (Decision 5/B3). |
| route-vs-allowlist contradiction for `init.py:1568` (renata) | MEDIUM | **corrected** — routed via `ManagedPathProver`, not allowlisted. |
| `rmdir` (×10) + `os.remove` (×1) omitted from op vocabulary; two allowlist rows mislabeled (paula) | MEDIUM | **accepted** — op vocabulary adds `rmdir`/`os.remove`; `rmdir` is an empty-only category rationale; mislabeled rows corrected; WP02 census is live. |
| retired-command canonical sites may over-preserve if no marker (renata) | MEDIUM | **accepted** — confirm each target carries a marker (both syntaxes) or reclassify to `manifest`. |
| Extract shared gate plumbing from `test_destructive_op_routing.py` (paula, DIRECTIVE_044) | MEDIUM | **accepted** — shared AST census/self-mutation helper; both gates consume it. |
| Naming: two "ownership", two "guard" tokens (paula) | MEDIUM | **accepted** — package renamed `asset_preservation`. |
| archive core is copy-only; wrapper delegates (renata/pedro) | LOW | **accepted** — copy-only core, single authority. |
| external `backup_parent` for parent-removed sites (pedro) | LOW | **accepted** — mandatory param (contract C1.4). |
| `m_0_10_2` `.toml` marker past 15-line head (pedro/renata) | LOW | **accepted** — prove via command-skills manifest first (`AnyProver`). |
| positive-routing is module-coarse; per-path via ATDD (paula) | LOW | **accepted** — documented in contract C3.4. |
| op-vocabulary exhaustiveness self-test (renata) | LOW | **accepted** — added (contract C3.2). |

No contested finding was silently dropped.
