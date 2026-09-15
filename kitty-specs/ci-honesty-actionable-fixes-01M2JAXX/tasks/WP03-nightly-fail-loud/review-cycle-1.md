---
affected_files: []
cycle_number: 1
mission_slug: ci-honesty-actionable-fixes-01M2JAXX
reproduction_command: spec-kitty agent tasks move-task WP03 --to approved --mission ci-honesty-actionable-fixes-01M2JAXX
reviewed_at: '2026-09-15T13:26:32Z'
reviewer_agent: reviewer-renata
wp_id: WP03
---

Approved by reviewer-renata: #4212: three suite steps capture exit into GITHUB_ENV; terminal if:always() fail-loud step per job exits 1 on any red; run-all (set +e/if:always/fail-fast:false) preserved; artefacts upload before failing. Guard test_nightly_suite_steps_are_fail_loud RED-on-base/GREEN-on-fix; 10 passed; ruff clean.
