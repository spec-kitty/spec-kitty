---
description: Validate generated documentation against explicit quality gates and record the verdict
---
# /spec-kitty.validate - Validate Documentation Quality

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/audit-report.md`). Never refer to a folder by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Location Pre-flight Check

**BEFORE PROCEEDING:** Verify you are working in the repository root checkout.

```bash
pwd
git branch --show-current
```

## What This Step Produces

- **`kitty-specs/<mission>/audit-report.md`** — the canonical evidence artifact recording which gates passed, which failed, what risks remain, and whether the documentation is fit to publish.

This is the last checkpoint before content meets readers.

## Goal

Gate the content produced in `generate` against explicit quality criteria and record a reproducible, evidence-backed verdict.

## What to Do

1. **Treat validation as a set of explicit gates, not an impressionistic skim.** Each gate needs an objective check, an evidence trail, and a pass/fail outcome.

2. **Verify Divio-type adherence** for every page produced in `generate`. A page tagged `tutorial` that reads like reference fails the type contract regardless of how good the content is.

3. **Verify completeness against `plan.md`**: every required cell is either filled or deferred-with-reason; no orphaned drafts; no unresolved placeholders.

4. **Verify accessibility** appropriate to the publication target: heading hierarchy (H1 → H2 → H3, no skipping levels), alt text on images, descriptive link text, sufficient color contrast on themed elements. Accessibility failures discovered post-publish are user-visible — catch them here.

5. **Verify source-of-truth alignment**: reference matches code; tutorials and how-tos run verbatim as written; explanations cite the architecture they describe.

6. **Verify cross-link integrity**: every internal link resolves; the link graph matches `plan.md`.

7. **Verify generator reproducibility**: rerun the documented generator commands in a clean environment and confirm they reproduce the published artifacts.

8. **Run a pre-mortem against publication.** What fails after readers arrive? Stale screenshots, broken commands, contradictory pages, missing prerequisites. Surface each such risk now, not after publish.

9. **Give every surfaced risk a disposition**: accept (with a rationale), mitigate (with the action), or block-publish. This vocabulary maps onto the `adversarial-squad-deployment` procedure's findings-disposition contract (load it with `spec-kitty charter context --include procedure:adversarial-squad-deployment`): accept -> `deferred_with_rationale` (the risk stands and the page publishes unchanged; record the rationale and where it is tracked), mitigate -> `accepted` (the page changed accordingly; record where the action landed, or use `changed` when the concern is resolved another way), block-publish -> `deferred_with_rationale` while the rework is pending (deferred back to `generate` or `design` with the blocking rationale recorded), then replaced by `accepted` once the rework lands (each finding carries exactly one disposition at a time; record where the rework landed). Risks that block publish go back to `generate` or `design` as appropriate — do not silently downgrade a blocking risk to a warning.

10. **Write `audit-report.md` as the canonical evidence artifact.** Cite concrete page paths, concrete failures, concrete fixes — "some pages have issues" is a note-to-self, not a validation. Assign a verdict: `ready-to-publish`, `needs-rework`, or `blocked`. The `publish` step reads this verdict and does not bypass it. If a previous `audit-report.md` exists, compare trends — a metric that worsened across cycles is itself a finding.

## Success Criteria

- `audit-report.md` exists, is complete, and carries an explicit verdict.
- Every claimed gate has cited evidence (page path, command output, screenshot, or diff).
- Risks marked `block-publish` are addressed before the verdict flips to `ready-to-publish`.
- The report is reproducible: rerunning the gates produces the same outcome on the same content.

## Handoff

This step gates content against quality criteria only. It does **not** reopen scope, audience, or iteration mode (`discover` decisions), reopen the gap analysis (`audit` decisions), reopen the architecture or generator selection (`design` decisions), author new content beyond the fix-it loops needed to clear gates (`generate`'s job), or publish the result (`publish`'s job). A validate report that proposes new sections or new architecture is overstepping — surface the need and send it back to the appropriate step.
