---
affected_files: []
cycle_number: 2
mission_slug: exit-zero-data-intact-01M3KDAS
reproduction_command:
reviewed_at: '2026-09-28T13:45:15Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback, cycle 2 (reviewer-renata)

Production code is still accepted as written: T030, T032, T033 and T034. Rework
cycle 1 fixed the FR-016 vacuity. It now fails on base and with T033 alone
reverted, on `'\r' in body`, not on the hash. The FR-018 exact-`skipped`
assertion, the docstring fixes and the canonical hasher are also good. Two items
remain, and both concern tests only.

## 1. FR-017 via `spec-kitty upgrade`: the stated blocker does not reproduce, and the stand-in is the wrong function (blocking)

`tests/specify_cli/skills/test_crlf_skill_render_4998.py`: module docstring
(~:30-44) and `test_fr017b_doctrine_skill_repair_converges_via_install_all_skills`
(:519).

The docstring says the real `spec-kitty upgrade` CLI cannot be driven because
it hits an "Owner effect conflict" (`tool_surface/operations.py::coalesce_effects`).
That comes from the hand-built `_make_project` fixture, not from upgrade. I
checked this on a REAL project, with the lane code and HOME, XDG and
SPEC_KITTY_HOME all isolated to a scratch directory:

- `spec-kitty init --ai codex --non-interactive`, then `spec-kitty upgrade --yes`,
  with the uncorrupted LF registry: exit 0, no conflict.
- Seeded a doubled-frontmatter doctrine skill (bogus LF block plus the real
  CRLF bytes) and made the doctrine manifest record that hash. Then ran
  `spec-kitty upgrade --yes` with `SkillRegistry.from_package` patched to CRLF
  copies of the package skills:
  - **lane:** the file is restored byte-equal to the LF source, and a second
    upgrade leaves it unchanged;
  - **base (1f4a914c):** the file stays doubled after both runs.

  So the real upgrade CLI is testable and red-first.
- In-process with `CliRunner`, init plus upgrade takes about 16 s.

The docstring also calls `install_all_skills` "the function the upgrade CLI
calls". On a project that is already current, that is wrong. Upgrade repairs
doctrine skills through `upgrade.assessment.prepare_upgrade_repairs` and
`apply_upgrade_repairs` (the ManagedSkillsProvider with
`kinds=(DOCTRINE_SKILL,)`). In my runs the migrations did not execute ("Project
is already up to date!"), yet the repair still happened. `install_all_skills`
runs only inside the one-shot skill-pack migrations. FR-017b therefore tests the
migration path, which is fine to keep, but not `spec-kitty upgrade`.

Required change:
- Add a test that drives the real `upgrade` CLI:
  1. Build the project with `CliRunner().invoke(specify_cli.app, ["init", "--ai", "codex", "--non-interactive"])`
     inside `tmp_path`, using the existing `_isolated_home` fixture.
  2. Seed the corruption into one installed doctrine `SKILL.md`. Use the real
     CRLF bytes (see item 3) and rewrite that entry's `content_hash` in the
     existing manifest with `compute_content_hash`.
  3. Patch `SkillRegistry.from_package` to the CRLF registry and invoke
     `["upgrade", "--yes"]`.
  4. Assert the file is byte-equal to the LF source, and that a second
     `upgrade --yes` leaves the bytes unchanged.
  5. Confirm it is red on base, and record that in the Activity Log.
- The test is about 16 s, so give it a non-`fast` marker (or whatever marker the
  repo uses for CLI-integration tests) rather than module-level `fast`.
- Correct the module docstring and the FR-017b docstring. Remove the "Owner
  effect conflict" justification, and describe FR-017b as the migration path.

## 2. `doctor skills --fix` negative pin: use a strict xfail, not a passing assertion of the defect (blocking, small)

`test_fr017c_doctor_skills_fix_leaves_self_consistent_drift_untouched` (:652).

I confirmed the gap is pre-existing. On a real init'd project, a self-consistent
CRLF-corrupted `spec-kitty.accept` command skill is left unrepaired by
`doctor skills --fix`, identically on base and on lane. The real
`spec-kitty upgrade --yes` repairs it on both. So fixing it is outside WP06's
owned files and is correctly a follow-up. The coordinator is filing it.

As written, though, the test is green only while the defect exists: it asserts
the wrong behaviour as expected. Required change:
- Assert the DESIRED behaviour: the file is restored and a second run is a no-op.
- Mark it `@pytest.mark.xfail(strict=True, reason="<follow-up issue>: command_installer.verify() only compares to the manifest-recorded hash")`,
  so the fix flips it to XPASS and forces removal of the marker.
- Keep the explanatory docstring.

## 3. Non-blocking (fix while here)

- `_seed_corrupted_install` (~:417) and FR-017b (~:543) build the "CRLF
  original" with `skill.skill_md.read_text(encoding="utf-8")`. That is universal
  newlines, so the CRLF becomes LF. The seeded corruption is really "bogus block
  + LF original", not the historical "bogus LF block + CRLF original". Use
  `skill.skill_md.read_bytes().decode("utf-8")`. I checked that the real
  CRLF-bytes shape still converges on the lane.
- `_copy_skill_tree` (~:190): the comment says the lone-CR line is injected
  "right after the frontmatter's closing delimiter". `replace("---\r\n", ..., 1)`
  hits the OPENING delimiter, so the marker lands inside the frontmatter. Either
  inject it after the closing delimiter or fix the comment.
- `_single_frontmatter_block` (:210) is correct for the real historical shape. I
  checked that it returns False on actual old-code output for a CRLF source, and
  on a tripled block. It returns True for an LF or CRLF single block and for a
  `---` rule later in the body. Its one blind spot: a doubled block separated by
  a blank line reports True. That is not the historical shape, and it is
  harmless wherever byte-equality is also asserted. `test_fr015_..._via_real_cli`
  relies on it alone, so add a byte-equality check against the LF source there
  as well (normalise the mixed-variant skill, or exclude it).
