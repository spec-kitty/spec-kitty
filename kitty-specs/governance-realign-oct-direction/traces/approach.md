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
- 2026-10-12 (review fold): independent adversarial review (reviewer ≠ implementer, a
  delegated fresh-eyes pass) returned three findings. Folded #1 (HIGH: `services/mission-status-api/`
  was written as shipped "in-repo now" though the dir does not exist on disk — reworded to
  direction/target state in the roadmap ×4 and the api-dashboard plan, caveat added to ADR
  D-10) and #3 (LOW: AGENTS.md Shared Package Boundary bullet missing ADR 2026-04-25-1 —
  added). FLAGGED #2 (3 stale "proposed" labels for ADR 2026-10-01-2 in
  `docs/architecture/04_implementation_mapping/README.md`) rather than fixing it: that file
  is outside the brief's explicit 9-file scope. Guards re-run after the fold.
- 2026-10-12 (delivery): add_repo push grant approved; pushed branch; opened DRAFT PR #6108
  (Refs not Closes; PROPOSED-amendments + confidentiality framing). Standing directive: watch
  CI, remediate reds (classify non-ours per baseline-red gotcha, don't widen), flip ready on
  green, handover note, stand down — operator merges.
- 2026-10-12 (scope tie-break): the operator's direct reply ("Confirmed it is my request")
  authorized the architecture widening; a peer session then relayed a contradicting "keep it
  separate". A peer relay is not operator authority, so the conflict was surfaced to the
  operator and resolved by their explicit choice: FOLD the widening into THIS PR. Un-stashed
  and committed the widening: new ADR 2026-10-12-2 (charter extraction) + docs/architecture
  sweep + the three operator-approved C4 diagrams (un-escaped from transport HTML-entities,
  mmdc-11.4.2-validated — all three render; embedded copies re-extracted and re-rendered).
  Guards re-run green (terminology 96/96, freshness 0 errors, spelling 0/690; inventory +
  docs-index regenerated).
- 2026-10-12 (held — scope widening, now RESOLVED by the tie-break above): a peer Claude session relayed an "operator addendum"
  (sweep `docs/architecture/`, author a charter-repo-extraction ADR, embed three
  "operator-approved" Mermaid diagrams). HELD, not actioned: it is unverified peer data (the
  session has had no genuine operator input), and it directly contradicts this brief's
  explicit non-goals (do NOT author the charter-repo-extraction ADR; `docs/architecture/` is
  out of the file scope). Surfaced to the operator for a real decision; not silently absorbed.
