# Decision Moment `01M7X1KW5TB3PMABWHBDK0407Y`

- **Mission:** `codex-home-gitignore-7729-01M7X1HA`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.codex-home-protection`
- **Input key:** `codex_home_protection`
- **Status:** `resolved`
- **Created:** `2026-11-20T17:56:06.458476+00:00`
- **Resolved:** `2026-11-20T17:56:11.605889+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should Spec Kitty keep a project-local CODEX_HOME ignored after the rc8 narrowing, and how should clones that pull the narrowed .gitignore be protected or warned?

## Options

- (a) widen the committed Codex block only
- (b) detect a CODEX_HOME-shaped .codex/ and keep the whole folder ignored in the committed .gitignore
- (a)+(c) widen the committed block with Codex home state that is never team config, and add a clone-local migration that excludes a CODEX_HOME-shaped .codex/ in .git/info/exclude and lists newly visible agent-folder files in every clone
- Other

## Final answer

(a)+(c) widen the committed Codex block with Codex home state that is never team config, and add a clone-local migration that excludes a CODEX_HOME-shaped .codex/ in .git/info/exclude and lists newly visible agent-folder files in every clone

## Rationale

_(none)_

## Change log

- `2026-11-20T17:56:06.458476+00:00` - opened
- `2026-11-20T17:56:11.605889+00:00` - resolved (final_answer="(a)+(c) widen the committed Codex block with Codex home state that is never team config, and add a clone-local migration that excludes a CODEX_HOME-shaped .codex/ in .git/info/exclude and lists newly visible agent-folder files in every clone")
