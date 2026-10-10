# Mission Tracer — Design Decisions

Mission: charter-kind-tier-vocab-closeout-01M4H5RF. Appended during implementation (Standing Order #3).

## DD-1 — Scope decisions (recorded as Decision Moments)

The four material scope decisions were confirmed with the operator and recorded as resolved Decision Moments at specify time: retire `ArtifactKind.core`; widen the API-source 404 fallback to the 11 layered kinds; unify the pack-tier token on `"built-in"` under one kernel authority; delete the 13 dead standalone copies and leave `graph.yml`.

## DD-2 — Predicate choice when retiring `core` (WP03), for the 3 sites WP02 anchored on `core`

**Context.** #5823 (WP02) migrated three mirror sites to *derive* from the authority; the only authority predicate yielding their historical 8-kind value is `core`, which #5824 (WP03) deletes. "Preserve values" and "delete core" are therefore mutually exclusive for these three. The decision-moment CLI supports only planning flows, so this implementation decision is recorded here.

**Resolution.**
- `pack_manifest.RECOGNISED_ARTIFACT_DIRS` and `pack_assembler._ARTIFACT_DIRS_AND_GLOBS` → derive from **`has_built_in_content_dir`** (10 kinds). This is a **correctness fix**, not mere parity: the built-in pack ships `assets/`, `glossary_packs/`, `skills/` content dirs and has **no** `mission_step_contracts/` dir, so the 8-`core` value recognised a phantom dir and skipped three real ones. It is squarely #5824's defect class ("surfaces covering only the 8 core kinds skip glossary_pack/skill/asset"), which the operator pre-approved widening. These two sites genuinely gate pack scanning/assembly (`pack_manifest.py:350`, `snapshot.py:154/412`, `pack_assembler.py:182/568`), so the built-in pack manifest is regenerated and the packaging-safety + pack suites are run.
- `fetch_stanza._VALID_SELECTOR_KINDS` → derive from the **charter-activatable** kinds + `"section"`. This set is **behaviorally inert** (`format_selector`'s valid/invalid branches are identical), so the predicate choice carries no behavior change; activatable is the honest "kinds `charter context --include` accepts" set.
- #5824's four *named* surfaces (collision scan, org dir count, org-layer lint, API 404 fallback) → **`has_layered_repository`** (11 kinds), per the issue.

**Why this was not escalated as a blocker.** The direction (retire `core`; widen to cover glossary_pack/skill/asset) was operator-pre-approved; the pack-dir predicate is *dictated by the actual on-disk pack layout* (a correctness fix, not a product judgment). It is nonetheless a built-in-pack seam change, so it is flagged prominently in the PR handover for review, the manifest is regenerated, and the packaging-safety gate is run. If testing had surfaced an ambiguous consumer-contract ripple, the plan was to stop and escalate.

## DD-3 — Topology

`single_branch` chosen: WP01→WP02→WP03 converge on `artifact_kinds.py` and the facade table, so sequential execution in one checkout avoids self-inflicted lane-merge conflicts. WP04/WP05 are independent but share a few files with the chain, sequenced to keep gates green.

## DD-4 — #5825/#5961 resolved as PARTIAL (tier-token half) + follow-up #5992

WP04's T050 persistence audit established that the no-hyphen `"builtin"` value is the artifact **provenance/layer/rank** vocabulary (emitted by `BaseArtifactRepository._provenance`), which is **serialized into the charter context JSON** (`{"source": "builtin"}`), compared across ~12 modules, keyed by the rank maps, and pinned by ~30 tests. Respelling it is a breaking wire-contract change that NFR-003 and the operator's "verify no provenance string is persisted/compared before changing each" ruling protect against.

**Operator decision (2026-10-10): accept the partial.** WP04 unifies only the **tier-token** sites under the new `kernel.pack_tiers` authority (single `"built-in"` spelling) + an empty-allowlist gate; the `"builtin"` provenance vocabulary is left frozen and documented as a deliberately distinct fact. #5825/#5961 are recorded `deferred-with-followup`; the provenance-respelling (a separate breaking-wire-contract mission) is filed as follow-up **#5992**. The hand-off PR references #5825/#5961 as *partially addressed* (tier-token half) and does NOT claim to close them.
