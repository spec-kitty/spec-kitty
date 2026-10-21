# Decision Moment `01M5DBXJ05DSF4322SXVPNPZZ1`

- **Mission:** `command-skill-names-and-antigravity-01M5DBWT`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.operator-rulings`
- **Input key:** `operator_rulings`
- **Status:** `resolved`
- **Created:** `2026-10-20T19:16:54.917142+00:00`
- **Resolved:** `2026-10-20T19:17:06.124084+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Confirm the mission scope and design rulings (naming, migration, Antigravity, frontmatter, open-packs, out-of-scope)?

## Options

_(none)_

## Final answer

Operator rulings (confirmed 2026-10-20): 1) name spec-kitty-<cmd>, one naming authority constant, uniqueness check vs built-in charter skills and RETIRED_CANONICAL_SKILL_NAMES, orphan detection keyed on manifest/explicit command set never the prefix. 2) Clean break: migration renames installed skills (install new, remove manifest-owned unmodified spec-kitty.<cmd>/, keep hand-edited with warning, rewrite manifest keys, idempotent, config-aware, never mkdir, order_manifest entry); release note + init/upgrade banner; doctor skills flags leftover dotted dirs; 13 command-agent slash-command files out of scope (#6471). 3) Antigravity: stop .agent/workflows project+global; migration removes owned spec-kitty.*.md from project .agent/workflows (never dir, never foreign); global writer stops writing ~/.agent/workflows, removes only owned files there on startup, stops fanning out to unconfigured agents. 4) Spec-conformant frontmatter per target, name<=64 description<=1024, skills-ref validator in CI. 5) open-packs PR replacing /spec-kitty.<cmd> and $spec-kitty. invocations, then pin bump. Red-first p0_repro tests; new ADR amending 2026-04-07-1; stop and ask on uncovered cases.

## Rationale

_(none)_

## Change log

- `2026-10-20T19:16:54.917142+00:00` — opened
- `2026-10-20T19:17:06.124084+00:00` — resolved (final_answer="Operator rulings (confirmed 2026-10-20): 1) name spec-kitty-<cmd>, one naming authority constant, uniqueness check vs built-in charter skills and RETIRED_CANONICAL_SKILL_NAMES, orphan detection keyed on manifest/explicit command set never the prefix. 2) Clean break: migration renames installed skills (install new, remove manifest-owned unmodified spec-kitty.<cmd>/, keep hand-edited with warning, rewrite manifest keys, idempotent, config-aware, never mkdir, order_manifest entry); release note + init/upgrade banner; doctor skills flags leftover dotted dirs; 13 command-agent slash-command files out of scope (#6471). 3) Antigravity: stop .agent/workflows project+global; migration removes owned spec-kitty.*.md from project .agent/workflows (never dir, never foreign); global writer stops writing ~/.agent/workflows, removes only owned files there on startup, stops fanning out to unconfigured agents. 4) Spec-conformant frontmatter per target, name<=64 description<=1024, skills-ref validator in CI. 5) open-packs PR replacing /spec-kitty.<cmd> and $spec-kitty. invocations, then pin bump. Red-first p0_repro tests; new ADR amending 2026-04-07-1; stop and ask on uncovered cases.")
