# Research: grounding #6549 on current `main`

**Question**: does the reported non-convergence still reproduce at `35318ef51c`?

**Method**: two fixtures driven through the real entry point
(`spec-kitty upgrade --project --yes`, and `MigrationRunner` for the isolated checks).

1. **Pre-ledger, fold-crossing (the issue's shape)** — `config.yaml` carries
   `activated_directives: [001-architectural-integrity-standard]`,
   `answers.selected_directives: [DIRECTIVE_001]`, version stamped `3.2.0rc30`.
   Pass 1 applies `consolidate_charter_bundle_fold`, `4.0.0rc8_activation_ledger` and
   `4.0.0rc8_promote_interview_selections`, and commits. Pass 2 and pass 3 create no
   commit and leave the tree clean. **The issue's symptom does not reproduce.**
2. **Bite fixture** (same project, `unify_charter_activation_promote_answers` removed
   from `SUPERSEDED_MIGRATIONS`) — pass 2 applies the shipped step and writes 38
   `activated_directives` into `config.yaml`. That is exactly the reported defect, and
   it is what the new module pins as its positive control.
3. **Residue probe** (a project already damaged by the pre-#6629 pass 2: 38 ids in
   `config.yaml`, 1 in the authority) — `upgrade` refuses at the activation-ledger move
   (`activated_directives differs between ...`), `doctor charter-packs` reports
   `LEGACY_KEYS_PRESENT` and names `migrate activation-ledger`, and that command also
   refuses a *differing* copy (it strips only a copy that already equals the ledger).
   The documented remedy is hand removal; stripping a tracked activation key
   automatically is a maintainer decision, so it is out of scope here and named in the
   PR's `## Deferred`.

**Conclusion**: the issue's defect is fixed by #6629 (supersession + write-target
resolution); the missing deliverable was the regression pin the issue itself asks for,
which this Mission adds — with a bite proof that keeps the pin from being vacuous.

**Superseded alternatives**:

- Fix the shipped class in place — rejected: DIRECTIVE_044 freezes its bytes, and
  #6629 already replaced it through `SUPERSEDED_MIGRATIONS`.
- Probe the residue case instead of the two-run convergence — rejected as the primary
  test: it asserts a refusal the maintainers chose deliberately (`#6496`), not the
  convergence #6549 reports.
