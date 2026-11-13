# Approach — mission-base-window-bound-01M78XB4

- **[2026-11-12][plan] Treat pre-Mission history like a verified declared dependency.** `window_base..mission_base` is empty whenever the target reaches the base, so every existing verdict is unchanged by construction; on a fork it names exactly the history the target lacks. Its commits leave the guard's spine walks; its shas/blobs/deletions join the #6771 exemption sets on the closed-world, squash and patch-id axes.
- **[2026-11-12][plan] Red first.** Both report shapes land as strict-xfail acceptance tests through `spec-kitty consolidate` before any behaviour change.
- **[2026-11-13][implement] Reviews earned their keep.** WP02 took three cycles (rename soundness, copy-detection regression on real repos) and WP04 two (speculative exemption). Each catch came from an adversarial probe against real repositories, not from the unit tests.
