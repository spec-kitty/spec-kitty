# Research: Mission-State Repair Audit-Trail Durability (#4928)

## R1 — Where should the audit trail live?

**Decision**: `.kittify/mission-state-audit/` (repo-relative), replacing `MANIFEST_ROOT = .kittify/migrations/mission-state` for these artifacts.

**Rationale**:
- `git check-ignore` confirms `.kittify/mission-state-audit/…` is **not** ignored on the shipped `.gitignore`, whereas `.kittify/migrations/…` is ignored at `.gitignore:76`.
- Precedent: `.kittify/evidence/` is already a tracked home for durable per-run records; a sibling `mission-state-audit/` root is idiomatic.
- Keeps the artifacts under `.kittify/` (operator mental model: "spec-kitty's bookkeeping") rather than polluting `kitty-specs/`.

**Alternatives considered**:
- *Un-ignore the existing `.kittify/migrations/` tree* — rejected: that directory legitimately holds transient migration scratch that should stay ignored; un-ignoring it would start tracking unrelated churn. FR-007 reconciles only the audit artifacts, not the whole tree.
- *Write under `kitty-specs/<mission>/`* — rejected: the audit trail is repo-scoped (a repair run spans all missions), not owned by one mission dir.

## R2 — How many writers touch `MANIFEST_ROOT`?

**Finding**: two repair flows write under the gitignored root and both must relocate (FR-006):
1. **Mission-state repair** — manifest at `mission_state.py:713,752`; quarantine tree at `mission_state.py:1712-1715` (`MANIFEST_ROOT/quarantine/<run_id>/<slug>/status.events.jsonl`).
2. **Duplicate-key repair** — manifest at `mission_state.py:904-913` (`_DUP_KEY_MANIFEST_PREFIX`).

A single named audit-root constant consulted by both writers avoids re-introducing the split-brain the #4897 fix just closed for row classification.

## R3 — Git-safety and tracked-policy coherence

**Finding**: `_assert_git_safe` (`mission_state.py:526`) exists to stop the manifest/quarantine roots being written onto an *enclosing* real repo. The relocation must keep passing that guard for the new root (NFR-003). Separately, `_POLICY_TRACKED` (`mission_state.py:85-89`) **already** lists `.kittify/migrations/mission-state/*.json` as a tracked-policy pattern — directly contradicting `.gitignore:76`. FR-007 resolves the contradiction by pointing the policy pattern at the new tracked root and removing the gitignored home for these artifacts.

**Decision**: introduce `MISSION_STATE_AUDIT_ROOT` (name TBD at implement time), route all three write sites through it, update `_POLICY_TRACKED`, and reconcile `.gitignore`.

## R4 — Write-only guarantee

**Decision**: the relocation introduces **no** git mutation (NFR-001). `--fix` writes files to the tracked location and stops; the exit summary instructs the operator to commit. This matches today's behavior (repair already writes-without-committing) and keeps blast radius minimal. Confirmed against the C-002 Decision Moment (`write-only-operator-commits`).

## Adversarial evidence (post-plan brownfield point-cut)

Two profile-loaded opus lenses (architect-alphonso structure/split-brain + debugger-debbie live-evidence/coverage), read-only. Contested-finding dispositions:

- **No runtime reader of the old path** (architect) — *accepted*: the trail is write-only; all consumers only print `report.manifest_path`. No stale-reader split-brain. Confirms the relocation is safe from that class.
- **#2384: the gitignore is deliberate** (both) — *changed*: `state/contract.py:271-287` declares the surface `GitClass.IGNORED` with rationale "Ignored so a repair run does not dirty the tree or gate accept (#2384)", and `.gitignore` is *derived* from that contract. **Scope pivot decision `relocate-properly-full-scope`**: repoint the state surface to `TRACKED` and register the new root as self-bookkeeping churn (FR-007, FR-008) rather than hand-edit `.gitignore`. Reconciles #4928 durability with #2384's non-gating goal.
- **`_assert_git_safe` self-block once tracked** (architect) — *changed*: drop `MANIFEST_ROOT` from the checked path-set at `mission_state.py:716,908` (FR-009/NFR-003b), else a second `--fix` refuses on its own output.
- **Guard citation conflated** (architect) — *changed*: `_assert_git_safe` is `:2611` (dirty-path refusal); `:526` is `_anchor_repair_root` (repo-boundary). NFR-003 split into 003a/003b.
- **3 architectural archive ratchets pin the old quarantine root** (both) — *accepted*: repoint them (FR-010); record that the relocated, operator-committed trail is reviewable, NOT DM-immutable (default).
- **Back-compat: keep the legacy ignore** (architect) — *accepted*: legacy projects retain old ignored trails; add the tracked root, do not un-ignore the old tree (C-005).
- **dup-key manifest is conditional, not every-run** (debugger) — *accepted*: the "manifest every run" invariant (M-1) holds for the mission-state repair only; the contract notes the dup-key manifest is conditional on `file_changes`.

No contested finding was silently dropped. No security-impacting dependency decision (no dep added/changed).

## Supply chain

N/A — no dependency added, upgraded, or removed.
