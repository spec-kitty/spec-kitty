# Research: command skill names + Antigravity

## R-1 Agent Skills naming and frontmatter rules

- **Decision**: name `spec-kitty-<cmd>`; frontmatter keys limited to `name`, `description`,
  `license`, `compatibility`, `metadata`, `allowed-tools` in the shared root.
- **Rationale**: `skills-ref` 0.1.1 `validator.py` (anthropics/agentskills, Apache-2.0) enforces
  `ALLOWED_FIELDS`, lowercase name, alnum-or-hyphen only, no leading/trailing/double hyphen, name
  ≤64 equal to the directory name (NFKC), description ≤1024, compatibility ≤500. Source read from
  the PyPI sdist on 2026-10-20. Issue #6475 cites VS Code, OpenCode and Cursor documentation for
  the same rule.
- **Alternatives**: keep dots and add an alias folder — rejected by C-005 (clean break).

## R-2 Antigravity skills surface

- **Decision**: deliver through the shared `.agents/skills/` root.
- **Rationale**: Spec Kitty's `AGENT_SKILL_CONFIG["antigravity"]` already declares
  `.agents/skills/` and `.agent/skills/`; #6470 cites the Antigravity migration guide saying
  workflows stop on 2026-10-19 and skills replace them. The guide host (`antigravity.google`) did
  not resolve from the build container on 2026-10-20 (DNS failure), so dotted-name behaviour is
  unverified; the hyphenated name is spec-valid either way. Labelled hypothesis: Antigravity reads
  `.agents/skills/` at project scope (per Spec Kitty's existing config, not re-verified).

## R-3 Ownership proofs available

- Project command skills: `.kittify/command-skills-manifest.json` (path → sha256, agents) via
  `asset_preservation.ManifestProver`.
- Project `.agent/workflows`: written by older releases with the
  `<!-- spec-kitty-command-version: X -->` marker (m_3_1_2 convention); no manifest. Proof = marker
  line present in the first 20 lines AND file name in the canonical command set. Edited files that
  keep the marker are indistinguishable from generated ones only when the body differs from a
  known render; to honour NFR-001 the migration removes a marked file only when its body (after the
  marker) equals the render of the same command for the marker's version **or** the current render;
  otherwise it keeps the file with a warning. (Implementation may simplify to: current render
  equality OR marker naming a different version with an unmodified-since-generation check is not
  available → keep. Choose the conservative path; record in design-decisions.)
- Home folder: `~/.kittify/cache/slash_commands-assets.json` inventory (path, sha256) — exact proof;
  marker fallback per `_is_canonical_predecessor` (#4609).

## R-4 Validator distribution

- **Decision**: CI runs `uvx --from skills-ref==0.1.1 agentskills validate <dir>` per skill dir via
  `scripts/ci/validate_agent_skills.py`; no runtime dependency added.
- **Supply chain (DIRECTIVE_051)**: single pinned version, publisher anthropics (author
  klazuka@anthropic.com), deps `click`, `strictyaml`; CI-only, not shipped in the wheel; npm
  `skills-ref` is a third-party port and is not used. No adversarial-squad challenge is required
  beyond this note because nothing ships to consumers; recorded here per the plan prompt.
