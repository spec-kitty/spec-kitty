# Validate Action — Governance Guidelines

These guidelines govern the quality-gate standards for the **validate** phase of a documentation mission. The deliverable is `audit-report.md` — the canonical evidence artifact recording which gates passed, which failed, what risks remain, and whether the documentation is fit to publish. Validate is the last checkpoint before content meets readers.

---

## Core Authorship Focus

- Treat validation as a **set of explicit gates**, not an impressionistic skim. Each gate has an objective check, an evidence trail, and a pass/fail outcome.
- Verify **Divio-type adherence** for every page produced in generate. A page tagged `tutorial` that reads like reference fails the type contract regardless of how good the content is.
- Verify **completeness** against the design: every required cell either filled or deferred-with-reason; no orphaned drafts; no unresolved placeholders.
- Verify **accessibility** appropriate to the publication target — heading hierarchy, alt text, color-contrast, link text quality. Accessibility failures discovered post-publish are user-visible.
- Run a **pre-mortem** against publication: what fails after readers arrive? Stale screenshots, broken commands, contradictory pages, missing prerequisites. Surface those risks now.

---

## Quality Gates To Enforce

- **Type adherence** — each page matches its declared Divio type.
- **Completeness** — coverage matches the design plan; deferrals are explicit and justified.
- **Accessibility** — appropriate heading levels, alt text on images, descriptive link text, contrast on themed elements.
- **Source-of-truth alignment** — reference matches code; tutorials and how-tos run verbatim; explanations cite the architecture they describe.
- **Cross-link integrity** — every internal link resolves; the link graph matches the design's plan.
- **Generator reproducibility** — a clean rerun of the documented generator commands reproduces the published artifacts.

---

## Risk Review Discipline

- Pre-publication risks include drift (code moved, docs did not), unstable examples (the API changes after publish), and audience mismatches (the page targets a reader the discover spec did not promise).
- Each surfaced risk gets a disposition: accept (with a rationale), mitigate (with the action), or block-publish. This vocabulary maps onto the `adversarial-squad-deployment` procedure's findings-disposition contract: accept -> `accepted`, mitigate -> `changed` (the action taken), block-publish -> `deferred_with_rationale` (deferred back to generate or design with the blocking rationale recorded).
- Risks that block publish go back to generate or design as appropriate. Validate does not silently downgrade a blocking risk to a warning.

---

## audit-report.md as Canonical Evidence

- `audit-report.md` is the **canonical evidence artifact** for this phase. It captures every gate, every finding, every disposition.
- The report cites concrete page paths, concrete failures, and concrete fixes. "Some pages have issues" is not validation; it is a note-to-self.
- The report's verdict — `ready-to-publish`, `needs-rework`, or `blocked` — gates the publish action. Publish reads this verdict; do not bypass it.
- Future validate cycles compare against the previous `audit-report.md`. Trends matter: a metric that worsened across cycles is itself a finding.

---

## What This Phase Does NOT Cover

The validate action gates the produced content against quality criteria. It does **not**:

- Reopen scope, audience, or iteration mode (discover decisions).
- Reopen the gap analysis (audit decisions).
- Reopen the architecture or generator selection (design decisions).
- Author new content beyond the fix-it loops needed to clear gates (that is generate's job).
- Publish the result (that is the publish action's job).

A validate report that proposes new sections or new architecture is overstepping. Surface the need, send it back to the appropriate phase.

---

## Quality Gates (Meta)

- `audit-report.md` exists, is complete, and carries an explicit verdict.
- Every claimed gate has cited evidence (page path, command output, screenshot, or diff).
- Risks marked `block-publish` are addressed before the verdict flips to `ready-to-publish`.
- The report is reproducible: rerunning the gates produces the same outcome on the same content.
