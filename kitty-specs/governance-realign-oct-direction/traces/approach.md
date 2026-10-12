# Approach

- 2026-10-12 (plan): Governance-docs realignment to six operator-ratified decisions.
  Delivered on one topic branch `governance-realign-oct-direction` as a draft PR, not as a
  lane-based code mission (no code lanes/worktrees); the canonical loop runs as artifacts
  over one branch because the change is prose on a single branch. Order of edits: ADRs
  (Divio-exempt tree) → charter (authority) → AGENTS.md (mirror) → roadmap → exec-overview
  → three domain plans → guards → review → PR.
- 2026-10-12 (plan): Charter wins over AGENTS.md on conflict. Each concept stated in both is
  edited in both, charter phrased as authority.
- 2026-10-12 (plan): Terminology-guard footguns to avoid in scanned `docs/`: `ceremony`,
  `status-writing`, the lane-consolidation phrases ("lane merge" / "merging lanes" / ...),
  and bare "spec-kitty merge". The ADRs sit under the guard-exempt `docs/adr/` tree, but the
  same canon is used there anyway.
