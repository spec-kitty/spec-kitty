# Tooling friction — decision-significance adoption

Context: Spec Kitty 4.0.0rc8 CLI from the checkout; cloud session; spec-kitty-events consumed from PyPI.

- 2026-10-27 — `spec-kitty-events` 11.1.0–11.2.1 never reached PyPI: the publish run failed on a version-guard test that cannot pass on a tag build. Fixed upstream (spec-kitty-events#143/#144); 11.3.0 published. Cost: one blocked round trip with the operator.
- 2026-10-27 — `mission create` on a topic branch in a checkout without `origin/HEAD` resolved `topology: coord` (the documented caveat), not `lanes`.

2026-10-27 · claude · tests/upgrade/test_mission_corpus_recovery.py goes 9/9 red in a shallow cloud clone: 8 need pinned history commits (git archive/show of c0054153, 2ff2f1de; pass after a --depth=20000 fetch) and 1 exceeds its 240s pytest-timeout budget (246s with events 11.0.0, 247s with 11.3.0 — not a lock regression). Environment, not this mission.
