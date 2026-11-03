# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · Fixed the two BLOCKER false positives at source instead of a SonarCloud UI waiver: the events default kind is resolved by registry NAME rather than by value lookup, and the charter builder's function-local import precedes the annotation that names it. Both are behaviour-identical, and neither adds a suppression marker or analyzer config, so the gate recovers without an invisible web-UI action.

2026-11-03 · python-pedro · Scoped out the fourth new-code finding (java:S5960 on acceptance-jvm step definitions) rather than reversing sonar.yml's documented decision to scan that tree as MAIN code for the full Java rule set. Consequence stated plainly: the rating moves E->C, not to A, and the choice is left to the maintainer as a named decision in the PR.
