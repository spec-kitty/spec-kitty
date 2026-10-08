## TACTIC_mirror_external_issue_numbering

When a mission spec references external trackers (GitHub issues, Linear
tickets, etc.) that already carry their own labeling for sub-items
(numbered hypotheses, lettered options, lettered milestones, etc.),
the mission spec SHOULD adopt that labeling verbatim. Inventing
parallel labels (e.g., abstracting `1./2./3.` to `H1/H2/H3`) creates
a translation tax with no benefit and increases drift risk if the
external tracker is later edited.

When the external numbering and the internal label both have a use
(e.g., distinguishing hypotheses across multiple missions whose
external trackers all use `1./2./3.`), the spec MAY introduce a
mission-local prefix (e.g., `1142.1`, `1142.2`) that preserves the
external numbering while disambiguating in cross-mission contexts.
Pure relabeling (`1.` → `H1`) is the anti-pattern this tactic
addresses.

Reference cases:
- spec-kitty PR #1160 — spec.md abstracted #1141 and #1142 issue
  bodies' numbered hypotheses to H1/H2/H3/H4; investigators
  correctly threaded the mapping but the abstraction added no
  value and required mental remapping at every reference.
