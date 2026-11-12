# Tracer: approach (#7578)

Seeded 2026-11-12. Append dated entries when the approach changes.

- 2026-11-12: a read-only squad (code grounding, evidence, issue discovery, then a second opinion) came before specify. Six design questions were escalated. The operator chose commands only (no inline diff) and widened the scope to stamp commit-to-target `single_branch`.

- 2026-11-12: integration reds between independently approved lanes surface only on the dependent lane (WP02's stamps turned WP03's derived-range pins red at WP05); per-lane review cannot catch them, so the dependent lane's implementer folds them and the PR names them.
- 2026-11-12: closeout ran accept and consolidate (merge strategy, branches kept), then rebuilt the history onto origin/main by replaying the 31 code commits in order plus one Mission-artifact commit; the rebuilt tree was checked equal to the consolidated content plus origin/main.
