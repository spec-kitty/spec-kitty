# Design Decisions — pack-level-declared-in-pack-yaml

Seeded at planning (Standing Order #3). Append rationale as the mission runs.

## Operator rulings (authoritative; do not re-open)

- **DR-1 — Reuse `kernel.pack_tiers.PackTier` Literal; no new enum.** `pack_level` is typed by the kernel Literal. `kernel.pack_tiers` stays the single spelling authority; `charter` imports it (kernel < charter). Chosen over a new `PackLevel` enum in `charter.offering.packs` (which would have tripped the existing empty-allowlist tier-token gate and duplicated naming authority). The ADR's Decision §2 prose is aligned to this.
- **DR-2 — Fold the ADR into this PR; close #6049.** The PR carries `docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md` (filename is `-2-`, not `-1-`). Decision §2 reworded to "kernel owns the tokens; the descriptor reuses the Literal; no second enum."
- **DR-3 — Fold #5992 (respell provenance).** The 3-tier artifact provenance/layer value is respelled `"builtin"` → `"built-in"` and unified onto `kernel.pack_tiers`. Scope-fenced (C-002): ONLY the 3-tier provenance vocabulary — not the `builtin|pack` skill-origin vocabulary nor the `"builtin:"` command-target prefix.
- **DR-4 — `packs/internal/` gets its own `pack.yaml`** (`pack_level: org`). `org-charter.yaml` is the pack's active-charter *content*, pointed to by `active_charter`; `drg/fragment.yaml` is pointed to by `pack_drg`. Pack layout is descriptor-declared, not located by hard-coded filename.
- **DR-5 — `active_charter` + `pack_drg` descriptor pointer fields.** Added so loaders/validator resolve the charter and DRG from the descriptor (fallback to per-level convention) through one seam.

## Architect (adversarial pre-spec) verdicts folded in

- **D1 → reuse Literal (DR-1).** The tier-token gate inspects only collection/`Literal` string-constant displays, not attribute refs; a derive-by-reference shape would have been gate-safe but still a naming duplication. Reusing the Literal is the strictest single-authority option.
- **D2 → defer was reconsidered; operator chose fold (DR-3).** The provenance value is persisted in serialized surfaces but **no read-back compares it to `"builtin"`** — so the respell needs no consumer data migration (NFR-001). The one persisted carrier (`.kittify/agent_profiles_manifest.json`) self-heals.
- **D3 → internal gets `pack.yaml` (DR-4).** `pack_version` becomes required only for built-in (FR-005); dual `pack_id` precedence = `pack.yaml` canonical + drift test (FR-012); loader gains a `pack.yaml` read on the org path; migration skips built-in/internal.
- **D4 → new clean-tree digest, enumerated-known-files / LF-normalized** (reuse `builtin_manifest`), NOT git-ls-files (fails on a `.git`-less export) nor rglob (noise). `snapshot_sha256` and its two remote-snapshot callers stay byte-unchanged (NFR-004).

## Known gate collisions to handle as deliverables (not regressions)

- `test_pack_manifest_no_author_edit` asserts the built-in `pack.yaml` key set is *exactly* `{pack_id, pack_version, parent_pack, name}` → must grow by `pack_level` (FR-018).
- `test_pack_tier_token_single_authority` + its docstring + `kernel/pack_tiers.py` doctrine comments explicitly *freeze* the `"builtin"` provenance spelling (NFR-003 carve-out) → must be extended to the unified spelling, carve-out dropped, empty allowlist kept (FR-019).

## Plan point-cut squad (architect + planner, 2026-10-11) — folded into plan.md

- **Decomposition**: 7 WPs across lanes A–G; IC-08 dissolved (gate FRs co-locate with their code: FR-018→WP04, FR-019→WP06, FR-020→WP01). Critical path WP01→WP02; WP06 (respell) is an independent second long pole from t0.
- **Seam (arch A)**: home = `charter/offering/packs/pack_layout.py` (not kernel); delegate convention to existing `kernel.charter_pack_paths`; `drg_path` return = file-or-dir (what `load_graph_or_dir` accepts) so built-in sharded fits the one seam.
- **MISMATCH position (arch B)**: real gap — `validate_pack(pack_dir)` has no position context. Add `check_pack_level(descriptor, expected_level)`; callers pass position; bare-path validate skips mismatch fail-closed but keeps MISSING+schema. WP02 org-path read touches `OrgPackConfig` (57 callers).
- **Digest (arch C)**: must be level-aware (builtin_manifest enumeration is built-in-only, misses org-charter/fragment); enumerate RECOGNISED_ARTIFACT_DIRS + seam's level files + pack.yaml, LF-normalized.
- **Lockstep (arch D)**: respell makes every sibling display a full-tier restatement → main gate reds. WP06 = one commit: respell + DERIVE each display from kernel.pack_tiers (keep empty allowlist, do NOT allowlist) + drop carve-out + rewrite NFR-003 docstrings. FR-016/017/019 are one WP.
- **WP06 scope fence**: explicit IN (3-tier provenance incl. `_TIER_RANK`) / OUT (`builtin|pack` skill-origin, `"builtin:"` prefix, `retrospective/reader.py::_provenance`) list in the brief before editing.

## Grounding references (CodeGraph passes, 2026-10-11)

- `PackDescriptor` / loader / `charter pack` CLI surface; `regenerate-graph` hardwires root at `_built_in_pack_root()` (`pack_tooling.py:36/110`).
- Tier vs provenance literal split; ~5 kernel consumers; the two single-authority gates and their empty allowlists.
- `snapshot_sha256` (full-tree rglob) callers: install-record `write_pack_manifest:342` + drift verifier `_snapshot_manifest_is_intact`; `builtin_manifest` enumerated/LF-normalized precedent.
- `packs/internal/` = org pack (ADR 2026-08-16-3) with `org-charter.yaml` + `drg/fragment.yaml`, no `pack.yaml` pre-mission.
