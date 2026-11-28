---
doc_status: draft
updated: '2026-11-28'
---

# Prediction packet for the outside observer

This packet asks the outside observer for predictions before any measured outcome is disclosed. It contains measurement definitions, scope, criteria and historical measurement points. It contains no outcome.

## What the observer receives

- This file.
- [01-pre-registration.md](01-pre-registration.md), which defines every measure (M01a to M08), the experiment PX-01, the thresholds, the samples and the measurement points P0 to P7.

The observer does not receive `00-rulings-and-deviations.md`, the grounding notes, or any finding. Those contain or hint at outcomes.

## Scope in brief

- Five repositories at the head revisions listed in the pre-registration, plus the revisions and released artefacts that core integrates.
- Core Python history from 2026-01 to 2026-11-28, with two parallel lines between 2026-08-19 and 2026-09-05 that were joined by a convergence merge. No trend is drawn across that merge.
- The maintenance window of H01 is supplied separately by the human architect and is not known to the investigators when the series is computed.
- Verdicts are supported, contradicted, inconclusive, or not assessable, by the criteria in section 6 of the pre-registration.

## What is asked

For each row, before seeing any result:

1. the verdict you expect;
2. your probability for each of the four verdicts (summing to 1);
3. the direction and rough size you expect for the named measure;
4. one result that would surprise you most.

| Item | Measure to predict |
|---|---|
| H01 | Change in M01a, M01b (load-time variant) and M01d between the start and end of a one-to-two-month window in mid-2026; and the same for the months after the convergence |
| H01, cause | Whether M01f differs between corrective maintenance and capability growth, and in which direction |
| H02 | Share of the 30 sampled cross-component fixes stopped by an automated gate before `main`; share that passed Mission acceptance first |
| H03 | Number of unrecorded violations of the enforced tier; number of recorded exceptions; M03b |
| H04 | For each of the twelve capabilities and five dimensions in M04: established, partly, not established, or not claimed |
| H05 | Share of ledgers flat or shrinking; share of entries with a reference or retirement condition |
| H06 | How many of the twenty questions are answered from one authoritative source and are correct; the change when agent-guidance files are added |
| H07 | Verified share of the fifteen execution responsibilities against the coordination comparator; how many are delegated or out of scope by recorded intent |
| H08 | For how many of the six invariants the contract-only check can be written and agrees |
| PX-01 | Which of the four outcomes |
| Replication | For which measures the blind replication of workstream C will differ by more than 10% |
| Mutations | Of 24 controlled mutations in four classes, how many the existing gates detect, per class |

Free text is welcome: which hypothesis you consider weakest, and which measure you think is poorly chosen.

## Recording

The predictions are stored unchanged in this folder as `predictions-outside-observer.md`, with the time received and the commit of the pre-registration they refer to, before any finding is shared.
