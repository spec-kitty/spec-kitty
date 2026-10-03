# Contract: command-skill drift and consent

Applies the drift policy of `kitty-specs/agent-profile-projection-plugin-production-01KV3NGS/contracts/drift-policy.md` to `.agents/skills/spec-kitty.<command>/SKILL.md`.

## Invariants

1. **Canonical is fresh.** If the on-disk bytes equal today's canonical rendering, the file is not drifted, whatever the recorded hash. The adoption pass that runs during `spec-kitty upgrade` records the canonical digest.
2. **Edits survive unattended runs.** `spec-kitty upgrade --yes` (and any run without an explicit repair) never rewrites a file whose bytes differ from both the recorded and the canonical hash. It reports the path in `drifted_reported` and exits non-zero.
3. **Explicit repair overwrites.** `spec-kitty doctor tool-surfaces --fix` replaces a drifted command skill with the canonical rendering and records its digest, exactly as it does for agent profiles. The same holds for an interactive upgrade where the operator answers yes.
4. **Guidance is actionable.** The drift finding for a command skill names `spec-kitty doctor tool-surfaces --fix`.
5. **No new public flag.** Consent travels only through `ApplyConsent.overwrite_paths`.

## Observable checks

| Scenario | Command | Expected |
|----------|---------|----------|
| Canonical bytes, old recorded hash | `spec-kitty upgrade --yes` | exit 0; no drift reported; manifest hash equals canonical |
| Real edit | `spec-kitty upgrade --yes` | non-zero exit; file bytes identical before/after |
| Real edit | `spec-kitty doctor tool-surfaces --fix` | file equals canonical; a following `doctor tool-surfaces` reports no drift for it |
