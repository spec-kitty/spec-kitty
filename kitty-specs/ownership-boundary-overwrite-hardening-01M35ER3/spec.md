# Mission Specification: Ownership-Boundary Overwrite Hardening

**Mission Branch**: `issue-4931-ownership-boundary-overwrite-hardening`
**Created**: 2026-09-22
**Status**: Draft
**Epic**: #4915 — User-data & customization preservation (mutating flows must never silently destroy user-authored files)
**In-scope issues**: #4931, #4926, #4921

## Intent Summary

**Primary actor**: an operator running ordinary Spec Kitty commands on a real project that contains their own hand-authored files.

**Trigger / problem**: three package-owned mutating flows destroy operator-authored bytes and report exit-0 success — `init` deletes a user-authored `.kittify/templates/` tree, `research` truncates a user-authored `research.md` (and fabricates 0-byte "ready" artifacts), and the mission-brief overwrite guard lives only in the CLI adapter so any future writer-layer caller silently clobbers a hand-authored brief.

**Desired outcome**: every package-owned mutating flow proves package ownership — by content or by this-invocation provenance, **never by path name alone** — before destroying user bytes, whether by removal or by overwrite/truncate; when ownership cannot be proven it preserves the file (or backs it up) and emits a clear diagnostic, and still exits success. This extends the already-landed `asset_preservation` **removal** chokepoint to the **overwrite/truncate** seam it does not yet cover.

**Load-bearing invariant** (charter §463-479, *User Customization Preservation*): *No mutating flow may overwrite, delete, rename, or chmod a user-owned customization unless the exact path is explicitly package-managed or manifest-tracked; name-based heuristics alone are not sufficient proof of package ownership; if ownership cannot be proven, preserve the file and emit a warning instead of deleting or rewriting it.*

**Assumptions**: (a) the canonical proof machinery is `src/specify_cli/asset_preservation/` (provers + `guard_destructive_removal`); this mission reuses it rather than inventing a parallel proof vocabulary. (b) "Preserve + warn, exit success" is the correct behaviour for unprovable ownership; a hard failure is acceptable only where no destruction is involved (e.g. `research` with no resolvable template may fail loudly rather than fabricate empty artifacts). (c) The three defects are independent code sites and may be fixed in parallel, sharing one proof surface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `init` preserves user-authored templates (Priority: P0 — release-blocking)

An operator has hand-authored `.kittify/templates/spec-template.md` (an active resolver LEGACY tier the product itself serves) on a project that has never been initialized, or whose `.kittify/config.yaml` was removed by a prior recovery. They run `spec-kitty init --ai claude --non-interactive`. Today the command recursively deletes that tree, makes no backup, prints `Project ready.`, and exits 0 — the file exists nowhere afterward, including `.kittify/.backup-*`. (#4931)

**Why this priority**: highest — silent, unrecoverable destruction of operator content that the product itself resolves, triggered by the first command every user runs, with a success message. #4931 carries the tracker label **`priority:P0`** (release-blocking under ADR 2026-07-17-1); the sibling #4861 was also P0.

**Independent Test**: seed a unique-content `.kittify/templates/spec-template.md`, confirm the resolver serves it at `tier=LEGACY`, run `init`; assert the file (or a recoverable backup) still exists and that the run emitted a "not package-owned — left in place" diagnostic. Verifiable without the other two stories.

**Acceptance Scenarios**:

1. **Given** a pre-existing user-authored `.kittify/templates/<file>` that this `init` invocation did not create, **and** no `.kittify/config.yaml`, **When** `init --non-interactive` runs, **Then** the file is preserved in place (or backed up under `.kittify/.backup-*`) and a diagnostic states it was left because ownership is not proven, **and** exit code is 0.
2. **Given** the same file but reached through EITHER full-copy template path — `copy_specify_base_from_local` (`--local` checkout) OR `copy_specify_base_from_package` (**the pip-installed default `init`**) — **When** `init` runs, **Then** the file is preserved/backed up in **both** paths: `templates/` is the only subtree left unprotected while `memory/`/`missions/` already back up, so the fix must cover the package default path too, not only the local one.
3. **Given** a `.kittify/templates/` tree that this `init` invocation genuinely created, **When** cleanup runs, **Then** it is removed as before (a legitimate package-created path is still cleaned — no regression).

### User Story 2 - `research` never fabricates or truncates artifacts (Priority: P2)

An operator runs `spec-kitty research --mission <slug>` on a `software-dev` mission for which no research template resolves. Today the command `touch`es **four** 0-byte files (`research.md`, `data-model.md`, `research/evidence-log.csv`, `research/source-register.csv`), renders a green "ready" panel, and exits 0; with `--force` over any existing user-authored one of those files it `unlink`s then `touch`es, truncating the file to zero bytes. All four share the same `_copy_asset` / CSV-loop destroyer. (#4926)

**Why this priority**: P2 — the truncation needs explicit `--force` and committed content is git-recoverable, but it is still a data-destroying path reporting success, plus a false-success on the default mission type.

**Independent Test**: on a fresh software-dev mission, run `research`; assert it does **not** create 0-byte "ready" artifacts for **any** of the four assets. Then write non-empty content into each of the four (in turn), run `research --force`; assert none is truncated to empty. Verifiable in isolation.

**Acceptance Scenarios** (each applies to **all four** research assets, not only `research.md`):

1. **Given** a mission type for which no research template resolves, **When** `research` runs, **Then** it does not create empty artifacts for any of the four assets and does not report them "ready" — it reports a clear "no research template for mission type X" outcome and does not claim false success.
2. **Given** an existing user-authored research asset with real content and **no** resolvable template, **When** `research --force` runs, **Then** the user's file is preserved (not truncated to 0 bytes). The decision to skip is taken **before** any `unlink` — the command never removes user bytes first and "fabricates" second.
3. **Given** an existing user-authored research asset, **When** `research` runs **without** `--force`, **Then** the file is preserved unchanged (existing control — no regression).
4. **Given** a mission type for which the template **does** resolve (e.g. the `research` mission type ships these assets), **When** `research` runs, **Then** the real template content is copied as before (no regression to the legitimate path).

### User Story 3 - the mission-brief overwrite guard is unforgeable at the chokepoint (Priority: P2)

An operator (or any future internal caller) writes a mission brief through the exported `write_mission_brief` writer. Today the "refuse to overwrite an existing complete brief without authorization" invariant lives only in the `intake` CLI adapter (duplicated across two gate sites); the writer itself overwrites unconditionally. Any future caller that forgets to gate silently clobbers a hand-authored brief — the exact #4910 failure mode, one layer down. (#4921)

**Why this priority**: P2 — architectural / latent-recurrence hardening; no active user-facing loss today, but it is the durable fix that retires the #4910 bug class instead of guarding one entry point at a time.

**Independent Test**: call the writer directly with a present complete brief and no overwrite authorization; assert it refuses with a typed error rather than replacing. Assert the two CLI gates translate that one error to the existing `--force` message. Verifiable at the writer layer without the CLI.

**Acceptance Scenarios** (the chokepoint refuses on brief **existence alone**, matching the #4910 gate — a present brief with an ABSENT provenance sidecar is unknown-provenance and must still refuse; the refusal is evaluated **before** any partial-state cleanup can unlink a brief-only file):

1. **Given** a present `.kittify/mission-brief.md` (whether or not `brief-source.yaml` is present), **When** `write_mission_brief` is called without overwrite authorization, **Then** it raises a typed refusal and leaves the existing brief bytes untouched — including the brief-present/sidecar-absent case, which today's CLI gate refuses on existence and which the chokepoint must NOT weaken.
2. **Given** the same, **When** overwrite is explicitly authorized, **Then** the brief is replaced (the `intake --force` path still works).
3. **Given** an orphaned partial-state sidecar (`brief-source.yaml` present, brief **absent** — the existing XOR recovery case), **When** the writer runs, **Then** the existing recovery behaviour is unchanged: no brief exists, so no refusal fires, and the orphan is cleaned and a fresh brief written (no regression).

### Edge Cases

- `init` where `.kittify/templates/` contains a **mix** of package-created and user-authored files: user-authored entries are preserved; only proven package-created entries are removed.
- `research` where the template resolves normally: unchanged behaviour (real content copied).
- Brief writer where neither brief nor sidecar exists: normal first-write path, no refusal.
- Ownership genuinely ambiguous (corrupt/absent manifest): fail toward preservation, never toward destruction.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | `init` preserves unprovable `.kittify/templates/` via TWO distinct mechanisms | As an operator, I want `init` to keep my hand-authored `.kittify/templates/` (or back it up with a diagnostic) unless this invocation created it, so my resolver-served templates are never silently deleted. **(a) Removal seam** (`init.py` cleanup guard): stop proving `.kittify/templates` package-owned by path name; prove it owned only by this-invocation `run_created` provenance. **(b) Overwrite seam** (`template/manager.py` — BOTH full-copy paths): back up pre-existing `templates/` first, reusing the in-file `back_up_operator_subtrees` / `preserve_existing=True` precedent (already used for `memory/`+`missions/`, #4759) — NOT forced through the removal chokepoint. Must cover `copy_specify_base_from_local` (raw `rmtree` at :117-120) AND `copy_specify_base_from_package` (`copy_package_tree(..., preserve_existing=False)` at :193, **the pip-installed default path**). (Source: #4931, tracker P0) | High | Open |
| FR-002 | `research` refuses instead of fabricating; never `--force`-truncates — for all four assets | As an operator, I want `research` to stop creating 0-byte "ready" artifacts when no template resolves and to never let `--force` truncate an existing user-authored artifact to empty, for **all four** research assets (`research.md`, `data-model.md`, and both CSVs), deciding to skip **before** any `unlink`, so a success message never coincides with data loss. (Source: #4926) | Medium | Open |
| FR-003 | Brief overwrite invariant enforced at the `write_mission_brief` chokepoint | As a maintainer, I want the "refuse to overwrite an EXISTING brief (existence alone — brief present with sidecar present OR absent) without authorization" invariant enforced inside the exported writer, **evaluated before the partial-state XOR cleanup** so a brief-only file is never unlinked-then-rewritten, with the duplicated CLI-adapter gates delegating to it, so no future caller can silently clobber a hand-authored brief and the #4910 brief-only case is not weakened. (Source: #4921) | Medium | Open |
| FR-004 | Extend the removal-routing arch gate to `research.py`'s removal literals (what the census *can* police) | As a maintainer, I want `test_mutation_ownership_routing` to add `research.py` to its scanned module set so its `unlink` literals must be **routed away** (the census refuses to allowlist a raw user-content op), catching a re-introduced raw `unlink` there. This is a *partial* guard — it does NOT and cannot police the overwrite/truncate op class, `template/manager.py`, or the mis-configured-but-routed prover that is #4931's root cause; those ride on FR-005 behavioral tests. (Source: #4926 coverage-gap finding) | Medium | Open |
| FR-005 | Behavioral regression tests are the durable protection for the overwrite seam and #4931's root cause | As a maintainer, I want each of #4931 (both destroyers), #4926 (all four assets), and #4921 to carry an issue-pinned behavioral regression test through the pre-existing CLI/writer entry point (per C-004), because a census/routing arch gate structurally cannot catch a mis-configured prover, an out-of-scanned-set module (`manager.py`), or an overwrite-shaped destroyer. These behavioral tests, not the arch gate, are what SC-001/SC-003 rest on. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero silent destruction | Across the three issues' reproduction scripts — #4926 exercised over **all four** research assets — 0 flows lose user-authored bytes while reporting success; each either preserves the bytes (intact, with a diagnostic/backup) or refuses with a clear message. | Reliability | High | Open |
| NFR-002 | No regression on legitimate paths | 100% of the pre-existing control arms remain green: `command-templates` preserved, `config.yaml`-present "Already Initialized", plain `research` re-run preserves, `research` on a type whose template resolves still copies real content, brief `--force` overwrites, orphan-sidecar XOR recovery unchanged, genuinely package-created `templates/` still cleaned. | Compatibility | High | Open |
| NFR-003 | Chokepoint-enforced overwrite invariant, one authority — without conflating seams | The overwrite/truncate invariant is enforced at the write chokepoint (not only in adapters); 0 adapter-only gates remain as the sole protection for the brief writer; no second proof vocabulary is introduced (reuses `asset_preservation`). This does NOT mean forcing every destroyer through the *removal* chokepoint: `template/manager.py`'s copy-over-existing uses backup-before-overwrite (`back_up_operator_subtrees`), which is the correct mechanism for an overwrite, not a removal. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the canonical proof authority | Reuse `src/specify_cli/asset_preservation/` provers / `OwnershipProof`; do not add a parallel ownership-proof authority (charter single-canonical-authority). | Technical | High | Open |
| C-002 | Name is not ownership proof | Ownership must be proven by content or by this-invocation provenance (`run_created`), never by path name alone (charter §470). | Technical | High | Open |
| C-003 | Preserve-on-unprovable, exit success | When ownership cannot be proven, preserve + warn and exit success; fail-closed only where no destruction is involved (charter §472). | Technical | High | Open |
| C-004 | ATDD / red-first | Each defect lands an issue-pinned failing `@pytest.mark.regression` repro through the pre-existing CLI entry point, RED before the fix, per ADR 2026-07-17-1; transitional repros become focused unit/functional tests after green. | Process | High | Open |
| C-005 | Scope boundary | Out of scope: the merge/`meta.json` dirty-tree seam (#4933, merge subsystem, owned by `merge-destructive-op-safety-01M2XQF8`), `agent config remove` rmtree (#4907, claimed — same removal seam as #4931, coordinate on prover wiring), git-hook overwrite in `implement` (#4895, claimed). The FR-001 audit-sweep task must NOT silently absorb #4907's `agent/config.py` `.claude/commands/` rmtree — surface it, do not fix it here. The orphan scaffold `kitty-specs/silent-destructive-write-hardening-01M355VK/` (no meta.json on `main`) is superseded by this mission and owns no work. | Scope | High | Open |

### Key Entities

- **User-authored asset**: operator-owned content a mutating flow might touch — `.kittify/templates/*`, `.kittify/mission-brief.md`, a mission's `research.md`. Preserved by default.
- **Ownership proof**: evidence that a path is package-owned — manifest membership, package-shipped content match, or this-invocation `run_created` provenance. Name membership alone is NOT proof.
- **Write chokepoint**: the single function through which a mutating flow commits bytes (`write_mission_brief`, the `research` copy helper, the `init` cleanup guard). The invariant lives here, not in callers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Re-running the #4931 (both destroyers), #4926 (all four assets), and #4921 reproduction scripts on the fixed build yields 0 silent-loss outcomes — 100% preserved-with-diagnostic or clearly-refused.
- **SC-002**: 100% of the pre-existing control arms across the three flows remain green (no legitimate refresh/overwrite/cleanup path regresses).
- **SC-003**: A caller that invokes the brief writer without overwrite authorization on a present complete brief cannot destroy it — the chokepoint refuses by construction (proven by a writer-layer test with no CLI involvement).
- **SC-004**: Each in-scope defect carries an issue-pinned **behavioral** regression test through its real entry point (#4931 ×2 destroyers, #4926 ×4 assets, #4921) that is RED before the fix and GREEN after — this is the durable CI protection, because a census/routing gate cannot catch a mis-configured prover or an overwrite-shaped destroyer.
- **SC-005**: The removal-routing arch gate (`test_mutation_ownership_routing`) additionally scans `research.py`, so a re-introduced raw `unlink` there fails CI. This is explicitly a *partial* guard layered on top of SC-004; it makes no claim over the overwrite op class, `template/manager.py`, or the prover-configuration root cause.
