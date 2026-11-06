# Approach — lane-worktree-model-hardening-01M6QY1M

- **[2026-11-06][discovery] Six read-only discovery lenses (status surface, lane lifecycle, topology, single_branch bound, cleanup, doctrine+write-service ADRs) mapped call sites, overlaps and risks.** Their briefs drive the spec; full files kept in the session scratchpad.
- **[2026-11-06][discovery] Four findings were escalated to the operator in one batch (ruling 3 unworkable as worded; S8 back-compat; S7 on protected targets; S5 vs the S4 ADR scope).** All four answered the same day; recorded as Decision Moments.
- **[2026-11-06][specify] One Mission, explicit `lanes` topology, consolidating into the topic branch issue-7276-lane-worktree-hardening.** ADR work packages first where they govern code; S2 before S3; S8 before S7; S1 and S6 early.
- **[2026-11-06][specify] Out-of-repo deliverables:** S9's spec-kitty-events ADRs (0007/0008) and S11's open-packs doctrine are drafted as patches/files (read-only access to events; open-packs push denied) for the operator to land.
