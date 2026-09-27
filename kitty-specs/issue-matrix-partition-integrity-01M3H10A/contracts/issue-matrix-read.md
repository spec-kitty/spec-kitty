# Contract: Coordination-aware issue-matrix read

Behavioral contract (not HTTP) for the read authority that every issue-matrix consumer routes
through. Backed by ATDD tests; each MUST-clause names its witnessing scenario.

## Inputs

- `repo_root`, `mission_slug`
- `kind = MissionArtifactKind.ISSUE_MATRIX`
- topology (from `meta.json`), coordination branch name (when applicable)

## Guarantees

1. **Discovery/verdict partition split** — reference discovery reads the PRIMARY partition (always a
   directory); matrix verdicts read the matrix's owning partition, which on coord topology is a
   different source. That source is a **directory** when the coordination worktree is materialized and
   **branch-ref content** (`git show <ref>:<path>`, no on-disk dir) when it is unmaterialized-but-retained
   — so the read authority yields matrix *content*, not only a `Path`. Readers accept a content source
   (IC-01b), not only a directory. *(FR-001, FR-003, FR-004, FR-005; witnessed: US1.1/1.3, US2.1/2.2/2.3/2.4, US4.1/4.2)*
2. **Branch-flat unchanged** — on single_branch/lanes the matrix resolves to PRIMARY; behavior is
   byte-for-byte identical to today. *(US1.3, US2.4 parity)*
3. **Post-consolidation read via the write's phase authority** — when the artifact has no on-disk
   worktree, the read surface is chosen by the SAME lifecycle-phase authority the write uses
   (`resolve_lifecycle_phase`): PUBLISHED ⇒ consolidated-primary ref; CONSOLIDATED/PRE_CONSOLIDATION on
   coord topology ⇒ coordination branch ref. Content is read from the resolved ref (`git show <ref>:<path>`,
   existence via `git rev-parse --verify`). The read never hardcodes a surface, so it cannot diverge
   from where the write landed. *(FR-005; witnessed: US4.1, US4.2)*
4. **Fail closed** — the read REFUSES (raises / returns a typed refusal), never falling back to
   PRIMARY residue or passing vacuously, when:
   - the coordination ref is absent (deleted) — *US4.3*;
   - the content probe errors — *US4.5 negative*;
   - the authored set is empty while gating references exist — *US4.4 negative*.
   *(FR-007, NFR-002)*
5. **Positive controls** — for each refusal clause a same-fixture positive assertion proves the read
   returns the verdict when present (non-empty set → resolves; probe ok → reads `fixed`). *(US4.4/4.5)*
6. **Performance** — resolution completes within the CLI <2s bar on the NFR-003 fixture (10 issues /
   25 rows); the branch-ref read adds no measurable overhead vs the worktree read. *(NFR-003)*

## Non-goals

- No second resolver authority; extends the existing seam in `src/mission_runtime/resolution.py`.
- No change to verdict semantics or the canonical verdict vocabulary.
