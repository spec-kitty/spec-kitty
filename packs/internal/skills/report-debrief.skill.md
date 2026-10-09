Goal: produce an executive debrief, a short branded report that says what happened over a time window or what is open in a milestone, label or query, for readers the requester names. The operator is the maintainer who invoked this skill. A debrief is for the maintainers' own use and never ships to consumers.

Input: the scope (parameter `scope`), and optionally the repositories, the readers and the layout. If the scope is missing, ask for it. If the readers are not named, ask who the debrief is for: the answer sets how plain the executive summary must be.

## Steps

Follow the `executive-debrief-generation` procedure. It carries the rules and the commands; this list is the order:

1. Fix the scope, the mode (a time window or a milestone/label scope), the repositories, the readers and the layout. Convert a local time to UTC. Open the work as a dispatch Op, not a Mission.
2. Collect the facts with the debrief collector asset. It owns every count and every `#ref`; you never count by hand.
3. Synthesize under the `executive-debrief` styleguide. Read only the collected files, and save any extra fact you need from `gh` or `git` to a file next to the collector output.
4. Render: the one-pager through the debrief renderer asset, the long form through the `spec-kitty-branded-pdf` asset. Never hand-build a cover or stylesheet.
5. Verify every page of the result, review it, and fix faults at the source, never in the PDF.
6. Place the output as the hand-off rule below says.

Find the asset paths with `spec-kitty charter pack asset path <id>` (ids: `debrief-collector`, `debrief-renderer`, `spec-kitty-branded-pdf`).

## The reference check (non-negotiable)

Every `#NNNN` in the debrief must appear in the collector output, or in a file you saved beside it and name in the appendix. Every number must come from one of those files. Before rendering, compare the references in your text with that set and remove or fix any that is not in it. You may cluster, narrate and label the collected facts; you may not add a number, an issue or a PR the collection does not contain. If a claim cannot be tied to a collected fact, cut it.

## Stop and ask the operator when

- the scope or the repositories are ambiguous after one question;
- a metric or query cannot be collected (record it as unavailable in the Method, do not estimate it);
- a request asks for the debrief to be committed or opened as a pull request (see the hand-off rule).

## Hand-off

A debrief is handed over, never committed. Send the PDF to the operator, and keep the collector output, the synthesis and any scratch script in the gitignored `work/` directory. Never commit a PDF, and never open a pull request into `spec-kitty` or any product repository for a debrief. If the operator wants the findings kept, write the short Markdown note the procedure describes in the planning repository. Close the Op with its real outcome.
