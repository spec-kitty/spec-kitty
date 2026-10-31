# Plugin manifest directory requirements (pinned)

This is the mission's contract artifact: the external requirements the generated
plugin bundles must satisfy, where each is pinned, and where it is asserted. It
exists so the requirements have one home and the suite reads the same values.

Source: `spec-kitty/spec-kitty/spec-kitty-internal-plugins#2` v0.2 (§2.2 Agent
Plugins manifest, §2.3 `extensions["com.openai"]` / Codex format), recorded in
`../research.md` Decision 3.

## Agent Plugins 1.0.0 (Copilot / VS Code)

| Requirement | Pinned value | Asserted by |
| --- | --- | --- |
| `$schema` | `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` (const) | `test_manifest_declares_the_pinned_agent_plugins_schema` |
| Key set | closed: `$schema`, `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`, `extensions` | `test_manifest_carries_only_schema_defined_keys` |
| `version` | SemVer | `test_manifest_identity_and_links` |
| Links | `homepage`, `repository`, `license: MIT` | `test_manifest_identity_and_links` |

`distribution_target` is **not** a schema key; the projector keeps it as an
attribute only.

## Codex / OpenAI (`interface`)

| Field | Limit | Asserted by |
| --- | --- | --- |
| `displayName` | ≤30 | `test_codex_manifest_meets_the_pinned_directory_limits` |
| `shortDescription` | ≤30 | same |
| `longDescription` | ≤4000 | same |
| `developerName` | ≤80 | same |
| `capabilities` | ≤20 items, ≤120 each | same |
| `defaultPrompt` | 1–3 items, ≤128 each | same |
| `websiteURL`, `supportURL`, `privacyPolicyURL` | HTTPS | same |
| `logo`, `composerIcon` | `./assets/…`, square, ≥48px, ≤5 MiB | `test_codex_declared_images_exist_inside_the_bundle` |
| `skills` | `./`-prefixed path | `test_codex_manifest_meets_the_pinned_directory_limits` |

`termsOfServiceURL` has no published URL for this project; it is deliberately not
emitted. Root fields: `homepage`, `repository`, `license`,
`requires_local_executor` (the plugin shells out to the CLI).

## Claude Code

| Requirement | Asserted by |
| --- | --- |
| No top-level `bin/` in the bundle | `test_claude_bundle_has_no_top_level_bin_directory` |
| No `hooks` pointer (the host default is `hooks/hooks.json`) | `test_claude_manifest_does_not_redeclare_the_default_hooks_file` |
| `homepage`, `repository`, `license`, SemVer `version`, `./` component paths | `test_claude_manifest_carries_identity_links_and_semver` |

## Deferred by contract

Marketplace hosting (a committed or released catalog location) and the CI
validator pins are out of this mission's scope: the first is a plugin-side
product call, the second is owned by #3535.
