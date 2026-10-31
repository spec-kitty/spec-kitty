# Discovery — plugin bundle directory conformance

Issue: spec-kitty/spec-kitty#6479. Baseline: `main` @ `dfe9efb0e8` (CLI 4.0.0rc8).
Independent design authority: `spec-kitty/spec-kitty-internal-plugins#2`
("Spec Kitty superset plugin spec", v0.2) — quoted below by section.

## Decision 1 — drop `bin/` from the Claude bundle instead of keeping a Claude-Code-only variant

**Why.** The build output is already Claude-Code-only: `--target claude-code` is
the only consumer of `ClaudeBundleProjector`, so a "variant" would be the same
bundle under another name. Claude.ai and Cowork refuse any plugin with a
top-level `bin/`, which makes the wrapper a hard submission blocker rather than a
trade-off. Nothing in the bundled skills invokes the wrapper: a search for
`spec-kitty-wrapper` over `src/`, `packs/built-in/` and the rendered skills finds
only the generator, the projector, the tests and one how-to page — the command
skills call `spec-kitty` directly. The wrapper therefore carries no behaviour the
bundle needs, while its own uvx fallback is separately broken (#6476).

**Consequence.** `claude_wrapper.py` and its test module become unreferenced, so
they go with it (the charter's campsite rule and the dead-symbol gate both point
the same way), and the how-to loses its "runtime wrapper" section. #6476 is
moot for the bundle; the issue stays open for the general wrapper question and is
called out in the PR.

**Evidence.** `src/specify_cli/tool_surface/bundles/claude.py:243-247` (staging),
`src/specify_cli/tool_surface/bundles/claude_wrapper.py` (generator),
`docs/guides/how-to/installation/install-claude-code-plugin.md:84-110` (claims
the skills call the wrapper — false), `spec-kitty-internal-plugins#2` §2.3
("Hooks and MCP call the Spec Kitty CLI, never scripts bundled in the plugin").

## Decision 2 — the Claude manifest stops redeclaring `hooks/hooks.json`

**Why.** `hooks/hooks.json` is the host default for a Claude Code plugin, so the
pointer is redundant; it is also the one place that emitted a bare relative path
(the issue's missing `./`). Dropping the key fixes the prefix defect and removes
a second source of truth for hook discovery in one move. The hooks file itself
keeps being staged and stays loadable.

**Evidence.** `claude.py:302-303` (manifest), `claude.py:196-199` (module
docstring: "hooks and MCP config use `hooks/hooks.json`"),
`spec-kitty-internal-plugins#2` §2.3 ("An explicit value replaces the default
`hooks/hooks.json`").

## Decision 3 — pin the external requirements in-repo and assert them, do not fetch a schema at build time

**Why.** The operator's triage asked for the applicable external schemas to be
pinned before implementation. The build must not fetch anything (NFR-003), so the
pinned values live as constants beside the builders and the conformance suite
asserts them: the Agent Plugins `$schema` const, the closed key set, and the
per-field length limits.

**Pinned values** (from `spec-kitty-internal-plugins#2` §2.2/§2.3):

- `$schema` = `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`, a
  const; clients never fetch it at load time.
- Agent Plugins `plugin.json` is a closed schema (`additionalProperties: false`)
  over `$schema`, `name`, `version`, `description`, `author`, `homepage`,
  `repository`, `license`, `keywords`, `extensions`. There is no
  `distribution_target` key — the current Copilot manifest's key is an invented
  field.
- Codex/OpenAI `interface`: `displayName` ≤30, `shortDescription` ≤30,
  `longDescription` ≤4000, `developerName` ≤80, `capabilities` ≤20 × ≤120,
  `defaultPrompt` ≤3 × ≤128, images square ≥48px ≤5 MiB as `./` paths in
  `./assets/`, plus the review URLs `websiteURL`, `supportURL`,
  `privacyPolicyURL`, `termsOfServiceURL`.
- Codex-format root extras: `skills` (`./` path), `mcpServers`
  (`./.mcp.json`), `requires_local_executor`.

## Decision 4 — SemVer is projected once, from the installed package version

**Why.** `version: 4.0.0rc8` is PEP 440, and every directory target wants SemVer.
`packaging` is already a runtime dependency, so one helper converts PEP 440 to
SemVer (`4.0.0rc8` → `4.0.0-rc8`, `4.0.0.dev1` → `4.0.0-dev1`,
`4.0.0.post1` → `4.0.0-post1`) and every target uses it. It never raises: an
unparseable string goes through unchanged with the existing non-semver warning.

**Evidence.** `_builder.py:get_cli_version` + `is_semver`, `pyproject.toml`
version `4.0.0rc8`, `codex.py:_SHORT_DESCRIPTION_MAX_LEN = 120` (wrong; 30).

## Decision 5 — bundle a real square brand asset

**Why.** The Codex format requires `logo` and `composerIcon`, and a manifest that
points at a file it did not stage is worse than no field at all. The repository
already carries the canonical 1024×1024 brand mark at
`docs/assets/logo_small.png`; a copy ships inside the package at
`src/specify_cli/tool_surface/bundles/assets/logo.png` (square, ≥48px, well under
5 MiB) and the hatch artifact glob ships it in the wheel, so `plugin build` works
from an installed CLI and not only from a source checkout. Images are declared as
`./assets/logo.png`.

## Decision 6 — scope boundary: the operator's triage already split the rest

**Why.** The operator ruling on the issue (2026-10-19) holds that the marketplace
hosting decision is a plugin-side product call, and that CI/release validation
belongs to #3535. Combined with `triage:needs-revision` ("defects stay Bugs, new
listing requirements become Features"), this Mission takes the defect set and
defers three items with their reasons rather than inventing a hosting location, a
second skill source or a CI re-pin in a bug fix.

Deferred: marketplace hosting (catalog points at gitignored `dist/`), doctrine
skills in the bundle (needs a tier decision), and the validator pin + Codex/
Copilot validators + release attestation (#3535).

## Open questions (for plan/tasks, not blocking)

- Should `plugin build` gain a `--target copilot|vscode` entry point? The
  Agent-Plugins manifest fix lands in the shared projection that those targets
  use; adding a CLI target is a behaviour addition the issue does not ask for.
- Does any consumer parse `manifest["distribution_target"]`? The provider reads
  the projector's `distribution_target` attribute, not the manifest field; the
  suite is the check.
