---
affected_files: []
cycle_number: 1
mission_slug: charter-epic-golden-path-nfr-budget-01M35H35
reproduction_command:
reviewed_at: '2026-09-23T12:16:37Z'
reviewer_agent: reviewer-renata
wp_id: WP04
---

# wp-verdict/v1 — canonical format for per-WP review verdicts.
schema: wp-verdict/v1
complete: true
wp: WP04
cycle: 1
mission: charter-epic-golden-path-nfr-budget-01M35H35
verdict: rejected
gates_observed:
  tsc: pass          # mypy --strict src/specify_cli/runtime/agent_commands.py: Success, no issues
  tests: pass         # 24/24 in tests/specify_cli/runtime/test_agent_commands.py; blast-radius subset also green
  coverage: "89.6%"   # diff-cover vs parent commit 9791b3923 on src/specify_cli/runtime/agent_commands.py; CI gate is >=90%
feedback:
  - id: WP04-C1-001
    severity: 4
    claim: >
      Ruling 6 requires a red-first test that fails if the pre-check wrongly skips when the
      spec-kitty version changes. Mutation testing (in the lane worktree, reverted after each
      run) shows this is not actually proven: mutating `_freshness_stamp_matches`
      (agent_commands.py:430-439) to drop the `cli_version` comparison entirely leaves ALL 24
      tests in tests/specify_cli/runtime/test_agent_commands.py green, including
      `TestFreshnessPrecheck::test_cli_version_change_forces_rerender`
      (test_agent_commands.py:493-501). The test still passes under this mutation only because
      `_all_global_agent_commands_healthy()` (agent_commands.py:296-305) independently
      re-verifies the CLI-version marker embedded in each rendered destination file, and the
      test's bootstrapped files still carry the OLD marker after `_get_cli_version` is
      monkeypatched — so the destination-health check (condition 4) masks a broken
      cli_version comparison (condition 1) and forces the fall-through for an unrelated
      reason. The test therefore does not isolate or actually red-first-prove the stamp's
      cli_version field, which is exactly what Ruling 6's binding condition requires ("tests
      that fail if the check wrongly skips ... when the spec-kitty version changes"). A
      killed-by-nothing mutation on the three Ruling-6-named conditions is a Ruling 6
      violation per this review's dispatch.
    remediation: >
      Add (or modify) a test that isolates the stamp's cli_version comparison from the
      destination-health redundancy — e.g. monkeypatch `_all_global_agent_commands_healthy`
      to always return True for this one test, then assert a cli_version-only mismatch still
      forces a re-render. This proves `_freshness_stamp_matches` itself checks cli_version,
      independent of the marker-based safety net that currently masks a regression there.
  - id: WP04-C1-002
    severity: 3
    claim: >
      `diff-cover` against the parent commit (9791b3923) on
      src/specify_cli/runtime/agent_commands.py reports 89.6% (60/67 changed lines covered,
      7 missing: lines 419, 424, 426, 472-473, 479-480) — below the repo's CI-enforced
      diff-cover >=90% gate (ci-aggregate.yml, per CLAUDE.md). As committed, this WP's diff
      would fail that gate. The uncovered lines are all in new code: the
      `_read_freshness_stamp` malformed-payload branches (payload not a dict; cli_version or
      template_source_signature not a string; agent_keys not a list of strings) and the two
      `except OSError: return None` fallback branches in `_freshness_short_circuit` (an
      unreadable template-source tree during signature computation; an unreadable destination
      during the health check).
    remediation: >
      Add narrow unit tests for each uncovered branch: a stamp file that is valid JSON but not
      an object (e.g. "[]"); a stamp with non-string cli_version/template_source_signature; a
      stamp whose agent_keys is not a list of strings; an unreadable/inaccessible
      command-templates source directory (forces the _template_source_signature OSError
      catch); and an unreadable destination command directory during the health check (forces
      the second OSError catch in _freshness_short_circuit).
  - id: WP04-C1-003
    severity: 3
    claim: >
      T013 and the inline code comment at agent_commands.py:589-597 assert the freshness
      stamp is "written into the SAME AssetPreparation batch as the rendered command files
      above, staged, locked and applied atomically together" and specifically that "a
      partial/failed run never reaches here with a different set of effects than what
      actually gets applied." Mutation testing this property directly (moving the stamp's
      `prepared._effect()` staging call to immediately after `AssetPreparation` construction,
      before the per-agent render loop, in the lane worktree, then reverted) shows this
      ordering property is killed by NOTHING: all 24 tests still pass. No test in this WP
      exercises a genuinely partial/failed render-and-apply cycle and then asserts the
      freshness stamp was NOT written. The "write only after a full, successful
      render-and-apply cycle completes" contract (data-model.md) is currently enforced only by
      code-comment discipline and correct-by-construction line ordering, not by any test that
      would catch a regression to it.
    remediation: >
      Add a test that forces a per-agent render or apply step to fail partway through the
      full-fleet batch (e.g. monkeypatch `_render_agent_commands` to raise on the Nth agent
      key, or induce a write failure partway through `_apply_command_assessment`), then assert
      the freshness stamp file does not exist (or is unchanged from its prior state)
      afterward.
  - id: WP04-C1-004
    severity: 2
    claim: >
      `_template_source_signature` (agent_commands.py:379-393) hashes only the command
      -templates SOURCE tree returned by `_get_command_templates_dir()`. It does not cover
      the rendering pipeline's own code (`_render_agent_commands`,
      `render_command_template`/`render_template_text` in the template/asset_generator
      module). `_get_cli_version()` (runtime/bootstrap.py:28-40) returns the static
      `pyproject.toml` version string, not a build/commit-scoped value, so on an editable/dev
      install — the exact install shape this mission's own WP agents and reviewers run under
      — a contributor changing the rendering code without touching template content and
      without bumping pyproject.toml's version would go completely undetected by both the
      stamp comparison and (unlike the version-change case in finding 001) the
      destination-health marker check, since the marker only encodes cli_version, which is
      unchanged. This is a genuine silent-staleness vector, though it is not one of Ruling
      6's three named conditions and is inherent to data-model.md's three-field stamp
      contract rather than something T012-T016 could fix unilaterally. Confirmed separately:
      this global render never reads `.kittify/overrides` or any project-local/org-pack
      source (`_get_command_templates_dir` and `_render_agent_commands` reference only the
      installed `charter.offering` package's own `mission-steps` tree), so there is no
      staleness hole from project overrides or org packs — the signature already covers the
      render's entire actual input universe for that concern.
    remediation: >
      Advisory / mission-level: if this class of dev-install staleness matters to the
      project, extend the stamp's signature to also hash the rendering pipeline's own module
      source(s), or document the gap explicitly as an accepted limitation of the three-field
      contract for editable installs. Not a blocking requirement for this WP given data-model.md's
      contract is fixed at three fields, but worth a tracer/ledger entry.
