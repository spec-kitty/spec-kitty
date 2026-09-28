---
affected_files: []
cycle_number: 1
mission_slug: exit-zero-data-intact-01M3KDAS
reproduction_command:
reviewed_at: '2026-09-28T13:05:56Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback (reviewer-renata)

The production fix is correct. T032 (`ensure_skill_frontmatter`), T033 (render
normalisation plus `source_hash` on normalised bytes), T034 (`.gitattributes`)
and the T030 campsite (pyproject `follow_imports="normal"` overrides that follow
the #3719 precedent and add strictness rather than removing it) are all accepted
as written. This rejection is about the tests only: the FR-016 proof is vacuous,
and FR-017 coverage is incomplete. No production-code change is requested.

## 1. FR-016 test does not test the bug (blocking)

`tests/specify_cli/skills/test_crlf_skill_render_4998.py:72` (`_COMMAND_TEMPLATE`)
and `test_fr016_crlf_command_template_render_matches_lf_source` (:271).

The fixture `software-dev/specify/prompt.md` contains
`<!-- spdd:reasons-block:start -->` markers. For any template with those markers,
`charter.offering.spdd_reasons.template_renderer.apply_spdd_blocks_for_project`
runs `process_spdd_blocks`, and that already turns CRLF into LF. So on UNMODIFIED
base code the CRLF and LF renders of this template already have equal `body`,
`frontmatter` and description. I checked this on a `git archive` copy of base
1f4a914c.

The test is red on base, and red when only T033 is reverted, for one reason only:
the `source_hash` assertion. That value was redefined by the same change, so the
red proves nothing about the render. The body, frontmatter and description
assertions pass without T033. The T035 "half-by-half" claim for FR-016 is
therefore true only because of the hash.

On base, the bug really does show on templates WITHOUT SPDD markers, which is 7
of the 12 software-dev steps. With `accept/prompt.md` and `research/prompt.md` on
base, CRLF and LF renders differ in body, frontmatter and description, and the
body contains `\r`. On the lane they are identical. That is the case the test must
pin.

Required change:
- Switch the FR-016 fixture to a template with no SPDD markers, such as
  `software-dev/accept/prompt.md`. Optionally parametrise over one template with
  markers and one without.
- Assert `frontmatter["description"]` explicitly. The WP asks for "description
  extracted correctly".
- Assert that no `\r` survives in `body`.
- Guard the fixture choice: `assert "<!-- spdd:reasons-block:start -->" not in lf_text`.
  This stops a later marker addition from silently making the test vacuous again.
- Keep the `source_hash` equality check as an additional assertion. It must not
  be the only thing that goes red.
- Re-record the red-first result. With T033 alone reverted, the test must fail on
  body/frontmatter, not only on hash. Update the Activity Log accordingly.

## 2. FR-017 does not cover `spec-kitty upgrade` or command-skill repair (blocking)

FR-017 and T031 step 3 require restoration by `spec-kitty upgrade` AND by
`doctor tool-surfaces --kind doctrine-skill --fix`. For command skills
(Codex/Vibe/Pi/Letta) the required repair is `spec-kitty doctor skills --fix`.
The module covers only the doctrine-skill `doctor tool-surfaces` path
(`test_fr017_repair_converges_when_manifest_hash_matches_corrupted_disk`, :368).

Required change:
- Add convergence coverage for the upgrade path. The skill-pack migrations
  (`m_3_2_0rc35_spk_skill_pack` etc.) call `install_all_skills(...,
  archived_paths=...)`. A test that drives `install_all_skills` over the seeded
  corrupted install plus the matching manifest, with the CRLF registry
  monkeypatched, is acceptable if running the real `upgrade` CLI is impractical.
  Say why in the Activity Log.
- Add a command-skill convergence case. A command skill rendered pre-fix from a
  CRLF marker-free template, with the manifest recording that hash, must be
  restored by `doctor skills --fix` (or the provider repair it calls), and a
  second run must be a no-op. If this path cannot be corrupted in practice, show
  why in a test or in the Activity Log.

## 3. FR-018 assertion is weaker than the requirement (non-blocking, fix while here)

`test_fr018_drifted_user_edit_stays_consent_required` (:453):
`assert "managed-file-drift" in codes or payload["ok"] is False` passes on any
failure. FR-018 says the file stays `consent_required`. Assert that
classification, or the specific finding code or field that carries it, for that
skill's installed path.

## 4. Minor (non-blocking)

- The module docstring (:37) says "reverting T032 alone turns every other test
  in this module red". That is inaccurate. I verified that reverting T032 turns
  exactly FR-015 x2 and FR-017 red, while FR-016, FR-018 and FR-019 stay green.
  Correct the text.
- `_seed_corrupted_install` (:340-345): a local `import hashlib` plus two
  `# noqa: TID251`. Prefer the canonical hasher
  (`specify_cli.skills.manifest.compute_content_hash`, or its bytes-level
  equivalent) so the fixture hashes the way the manifest does and needs no
  suppression. Also move `import subprocess` (:464) to module scope.
- `_single_frontmatter_block` counts `^---$` across the WHOLE file. If a sampled
  skill ever gains a `---` horizontal rule, it will fail spuriously. Restrict the
  count to the leading block region, as the WP suggests.
