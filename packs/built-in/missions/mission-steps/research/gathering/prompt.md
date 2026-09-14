---
description: Register sources and extract evidence into an auditable, citation-clean gathering trail
---
# Source Gathering — Build the Evidence Base

**Mission type**: `research` | **Step**: `gathering` (sequence index 2, depends on `methodology`) | **Agent profile**: `researcher-robbie`

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/research/source-register.csv`). Never refer to a file by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.**

## User Input

```text
$ARGUMENTS
```

Treat `$ARGUMENTS` as candidate leads (a source, a database, a search hint), not a substitute for the search strategy locked in `plan.md`.

## Bootstrap

```bash
spec-kitty charter context --action gathering --json
```

## What This Step Produces

- `kitty-specs/<mission>/research/source-register.csv` — every reviewed source, kept or excluded.
- `kitty-specs/<mission>/research/evidence-log.csv` — every extracted finding, with confidence.
- A `source_documented` event per accepted source, observed by the run engine.

The gate on `gathering -> synthesis` is `event_count("source_documented", 3)` (`mission.yaml`) — **events**, not file rows. Editing the CSV without the run engine observing the corresponding event does not advance the mission; follow your harness's event-emission mechanism for each accepted source, not just the file write.

## Read the Locked Methodology First

- Read `kitty-specs/<mission>/plan.md`. The search strategy, inclusion/exclusion criteria, and data sources were locked at methodology — gathering executes that plan, it does not redesign it.
- If methodology turns out to be infeasible mid-search (a named database is inaccessible, keywords yield nothing), that is a methodology gap to flag, not license to silently substitute an unplanned strategy.

## Source Registration Discipline

- Document **every** reviewed source in `research/source-register.csv`. A source that is read but not registered is invisible to downstream review.
- Capture each source with citation, URL or DOI, relevance assessment, and status (reviewed / pending / excluded).
- Sources excluded by inclusion/exclusion criteria are still registered — with the exclusion reason. Reviewers need to see the search yield, not just the kept set.
- Capture each key finding extracted from a source in `research/evidence-log.csv`, with confidence level (high / medium / low) and contextual notes.

## Citation Standards (research-citation-discipline)

Apply the `research-citation-discipline` styleguide throughout:

- Use **BibTeX** or **APA** format consistently — pick one at methodology time and hold it across the register.
- Include a **DOI** when available; otherwise a stable **URL**.
- Track **access dates** for all online sources — web sources drift, and an access date is what makes a citation re-verifiable.
- **Tier the evidence**: primary/reproducible (direct measurement, source code, an official spec) over secondary (documentation, third-party analysis) over anecdotal (a single unverified report). Name the tier when it is material to a later conclusion.
- **Record retrieval context** (date, version, query, commit) — a citation without it cannot be re-verified.
- **Report contradicting sources.** If two sources disagree, register both and note the disagreement; do not quietly keep only the one that supports an emerging hypothesis.

## Forensic-Style Source Investigation

Where the research question concerns a codebase, repository, or engineering artifact rather than published literature, the `forensic-repository-audit` tactic's discipline applies to gathering directly: scope the investigation window explicitly, exclude vanity noise (generated files, lockfiles, vendored code) before drawing conclusions from commit or ownership history, and register the exclusion list in the source register so a later reviewer can reproduce the search.

## Minimum-Source Threshold

- `mission.yaml`'s `event_count("source_documented", 3)` guard is a **floor**, not a target — most missions need substantially more. Use the target set in `plan.md` (driven by scoping's success criteria) to know when gathering is actually done.
- Document the source count as it grows; do not delay registration to the end of the phase.

## What This Phase Does NOT Cover

Gathering produces a clean evidence base. It does **not**:

- Re-scope the research question or change inclusion criteria after gathering starts (a methodology-discipline violation — flag it instead).
- Synthesize findings or draw cross-source conclusions (`synthesis` step's job).
- Produce publication output (`output` step's job).

Notes that begin to weave findings together belong in synthesis, not in the source register.

## What To Do

1. Read `kitty-specs/<mission>/plan.md` for the locked search strategy.
2. For each candidate source: assess against inclusion/exclusion criteria, register it in `research/source-register.csv` (kept or excluded, with reason), and — if kept — extract the key finding into `research/evidence-log.csv` with a confidence level.
3. Emit (or let your harness emit) a `source_documented` event for each accepted source; do not rely on the CSV row alone.
4. Continue until the plan's target source count is met and the `event_count("source_documented", 3)` floor is cleared.
5. Commit `research/source-register.csv` and `research/evidence-log.csv` per the `029-agent-commit-signing-policy` / `033-targeted-staging-policy` directives.

## Quality Gates

- Source register is complete: every reviewed source has a row.
- Citation format is consistent across the register.
- Every online source has an access date.
- Confidence levels are assigned and justified.
- The minimum-source threshold from the step contract is met, with real `source_documented` events, not just CSV rows.
- Evidence rows are stable enough that later phases can cite them by ID.
