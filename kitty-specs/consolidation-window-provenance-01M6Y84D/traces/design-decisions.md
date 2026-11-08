# Design decisions — consolidation-window-provenance-01M6Y84D

Running log of design choices and rationale (procedure `mission-tracer-files`). The full record is in `research.md`; the binding record will be ADR `2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition`.

- **[2026-11-08][specify] The window lives on the status event, under one namespaced key.** `policy_metadata.wp_window` holds `open_sha` or a typed `gap`. There is no sidecar or second store, because the event log is the only authority (Decision Moments `window_source`, `window_writer`; ADR `2026-09-29-1-closed-world-refuse-on-mixed-lanes` Decision 2).
- **[2026-11-08][specify] A missing window falls back and is reported, never refused alone.** The approval-stamp bound applies (a degraded window from the claim base), so in-flight Missions keep their verdict. `APPROVAL_STAMP_MISSING` is unchanged (Decision Moment `missing_window_rule`).
- **[2026-11-08][plan] Write on every opening move, read the first.** The pure pipeline cannot know a move is the first without reading history, so it writes on each non-migration entry into `claimed`/`in_progress`, reusing the `lane_head` reading (0 extra git reads). The reader binds to the first such event, mirroring `approval_window_open_stamp`.
- **[2026-11-08][plan] Flat `reconciliation_<unit>.py` modules, not a subpackage.** A subpackage cannot share the facade's name, and a new `__init__.py` would trigger the version-bump rule. Ownership is by directory glob, so the CI module registry needs no edit.
- **[2026-11-08][plan] `ClaimInputs` keeps per-mode quirks in Phase 2.** The extraction is witnessed by the corpus with zero verdict change. Aligning the forecast's excluded set and freezing the resume anchors are separate red-first changes in Phase 4.
- **[2026-11-08][plan] The `blocked` opener asymmetry stays a named window variant.** Unifying it would change closed-world verdicts outside NFR-002, so the ADR maps it rather than removing it.
