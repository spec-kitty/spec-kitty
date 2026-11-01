---
affected_files: []
cycle_number: 1
mission_slug: sdist-readme-anchor-01M6BRD9
reproduction_command:
reviewed_at: '2026-11-01T15:01:25Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review cycle 1 — changes requested (independent review, reviewer-renata lens)

Nothing blocking: red on base verified (732 members, config twin red), wheel byte-identical incl. wheel-from-sdist, packs/built-in and src unchanged. Fold before approval:

1. minor — pyproject.toml `[tool.hatch.build.targets.sdist.force-include]`: building an sdist from an unpacked sdist now fails (`FileNotFoundError: Forced include not found: …/docs/changelog/CHANGELOG.md`). No repo path does this (only wheel-from-sdist), but name it as a known limitation in the comment.
2. nit — pyproject.toml `packs/internal/**` and `packages/**` exclude comments still say the bare `README.md` include would ship their READMEs; the include is anchored now, so reword them as defense in depth. Leave the `services/**` / `contracts/**` comment alone (PR #7004 owns it).
3. nit — the archive check covers docs/, kitty-specs/, site/ only; the fix also removed stray tests/ and scripts/ members. Add `tests/` and `scripts/` to the forbidden trees so a future unanchored include cannot bring them back silently.
4. nit — the changelog fragment's "746" depends on what counts as stray (a worktree build also dropped `.github/CHANGELOG.md`); say "about 750".
