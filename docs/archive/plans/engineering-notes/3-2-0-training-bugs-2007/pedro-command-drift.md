---
title: Command-Contract Drift — Ground Truth, Inventory, and Guard Design
description: "Python Pedro's research on #2007's command-contract drift: the ground truth, an inventory of skill/prompt/doc divergence, and a guard design."
doc_status: deprecated
updated: '2026-06-26'
---
# Command-Contract Drift — Ground Truth, Inventory, and Guard Design

**Author:** Python Pedro (research op, bounded)
**Scope:** Issue #2007 systemic problem (1) — *command-contract drift*: skills/prompts/docs
reference CLI surfaces/flags that do not exist or are internal-only.
**Method:** Live Typer introspection of `specify_cli.app` (the registered command tree,
not a copy), cross-referenced against SOURCE templates (`src/doctrine/missions/mission-steps/`),
SOURCE skills (`src/doctrine/skills/`), and `docs/`. Generated agent copies under `.claude/`,
`.amazonq/`, etc. are out of scope — they propagate from SOURCE on `spec-kitty upgrade`.

---

## 1. Ground-truth CLI surface (the commands #2007 implicates)

Produced by walking `typer.main.get_command(specify_cli.app)` and listing each leaf
command's click `Argument`s and `Option`s. This is authoritative as of `pr/tool-surface-contract-residuals`.

| #2007 claim | Surface as documented/expected | Actually registered? | Ground truth |
|---|---|---|---|
| 1 | `spec-kitty doctrine list --kind <k>` / `doctrine show <id>` | **NO** | `doctrine` group only registers: `fetch`, `new <kind> <id>`, `regenerate-graph`, `validate <path>`, `mission-type list`, and subgroups `org` (`init`/`validate`), `pack` (`assemble`/`validate`). There is **no `list` and no `show`.** Canonical listing/inspection is the programmatic `from doctrine.service import DoctrineService` API (already documented later in the same skills) or reading the YAML under the doctrine packs. |
| 5 | `agent context resolve` — is `--action` required? | yes (exists) | `agent context resolve` ARGS=`[]` OPTS=`--action, --mission, --wp-id, --agent, --json`. `--action` **is required** (the command fails with a missing-`--action` error otherwise — confirmed by #2007 and by the prompts that already pass `--action plan|tasks|implement|review`). |
| 4 / 12 | `agent mission setup-plan` — is `--mission` required? | flags optional | `agent mission setup-plan` ARGS=`[]` OPTS=`--mission, --json`. The **snippet** `setup-plan --json` is syntactically valid (both flags optional). The drift is **behavioral**: with exactly one mission present the resolver returns `PLAN_CONTEXT_UNRESOLVED`/`FEATURE_CONTEXT_UNRESOLVED` and says "pass `--mission`" instead of auto-selecting. Not a snippet typo — a resolver contract gap. |
| 16 | `agent action implement` / `agent action review` — `--json`? | expected by callers | `agent action implement` ARGS=`[wp_id]` OPTS=`--mission, --agent, --allow-sparse-checkout, --acknowledge-not-bulk-edit` — **no `--json`.** `agent action review` ARGS=`[wp_id]` OPTS=`--mission, --agent` — **no `--json`.** Passing `--json` → Typer exit 2. |
| 16 | top-level `spec-kitty implement` vs `agent action implement` | both exist | Top-level `implement` ARGS=`[wp_id]` OPTS=`--mission, --auto-commit, --json, --recover, --base, --acknowledge-not-bulk-edit, --actor` — **has `--json`** and is the internal allocator. The canonical agent surface (`agent action implement`) does not. This is the split #2007 names: JSON lives on the internal surface, not the canonical one. (`--feature` hard-removed in #1060.) |
| 13 | `agent worktree repair` | **NO** | There is **no `agent worktree` group at all.** No `worktree repair` anywhere in the tree. |
| 13 | `doctor workspaces --fix` | yes (exists) | `doctor workspaces` ARGS=`[]` OPTS=`--fix, --json`. This is the real recovery surface that hints should point to. (`doctor coordination`, `doctor mission-state --fix`, `doctor sparse-checkout --fix` also exist.) |

Supporting surfaces relevant to the inventory below:

- `charter context` ARGS=`[]` OPTS=`--action, --include, --mark-loaded, --json`. The `--mark-loaded`
  bool auto-generates `--no-mark-loaded`, so `charter context --action specify --no-mark-loaded --json`
  is **valid** (false-positive trap — see guard design).
- `agent mission finalize-tasks` / `agent tasks finalize-tasks` both registered, OPTS include
  `--mission, --json, --validate-only`.

---

## 2. Drifted-reference inventory (SOURCE only)

Classification: **HARD** = the snippet would fail (nonexistent command/flag); **BEHAVIORAL** =
syntactically valid but contradicts the command's runtime contract; excluded = generated copies.

### HARD drift — nonexistent command surfaces

| File:line | Wrong surface | Correct surface |
|---|---|---|
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:113` | `spec-kitty doctrine list --kind directive` | No CLI. Use `DoctrineService` (documented at SKILL.md:621) or read pack YAML. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:114` | `spec-kitty doctrine show <a-directive-id>` | No CLI. Same as above. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:116` | `spec-kitty doctrine list --kind tactic` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:117` | `spec-kitty doctrine show <a-tactic-id>` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:119` | `spec-kitty doctrine list --kind styleguide` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:120` | `spec-kitty doctrine show <a-styleguide-id>` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:348` | `spec-kitty doctrine list --kind directive` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:439` | `spec-kitty doctrine list --kind directive` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:440` | `spec-kitty doctrine list --kind tactic` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:441` | `spec-kitty doctrine list --kind paradigm` | No CLI. |
| `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md:444` | `spec-kitty doctrine show DIRECTIVE_034` | No CLI. |
| `src/doctrine/skills/spec-kitty-mission-system/SKILL.md:320` | `spec-kitty doctrine list --kind procedure` | No CLI. |

**12 HARD-drift references** in SOURCE skills (#2007 item 1). Note the same skill file
(`spec-kitty-charter-doctrine`) correctly documents the `DoctrineService` programmatic API at
line 621 — the CLI snippets are vestigial and contradict the skill's own canonical guidance.

### BEHAVIORAL drift — valid snippet, wrong contract

| File:line | Snippet | Issue / correct guidance |
|---|---|---|
| `src/doctrine/missions/mission-steps/software-dev/plan/prompt.md:267` | `spec-kitty agent context resolve --mission <handle> --json` | **Missing required `--action`.** The other four prompts (tasks/tasks-outline/tasks-packages/implement/review) all pass `--action`; this plan-prompt line does not. Add `--action plan`. (#2007 item 5.) |
| `src/doctrine/missions/mission-steps/software-dev/plan/prompt.md:80` | `spec-kitty agent mission setup-plan --json` (no `--mission`) | Advertises no-flag operation; resolver returns `PLAN_CONTEXT_UNRESOLVED` even with one mission. (#2007 item 4.) Behavioral — resolve via auto-select-when-exactly-one OR require `--mission` in the prompt. |
| `src/doctrine/missions/mission-steps/software-dev/plan/prompt.md:241` | `spec-kitty agent mission setup-plan --json` once without `--mission` | Same as above — the prompt explicitly instructs a no-flag first attempt that the resolver rejects. (#2007 item 4/12.) |

### Worktree-repair references — already correctly absent from SOURCE prompts/skills

- `agent worktree repair` appears **only** in `docs/plans/engineering-notes/naming-identity-ssot-strangler/*`
  as tracker-sweep notes (#1890), explicitly flagged as "nonexistent command / follow-up". These are
  archaeology notes, **not** prescriptive snippets, so they are not active drift. The SOURCE
  setup-doctor skill's worktree-recovery section (`common-failure-signatures.md:150-180`) already uses
  the correct `git worktree prune` + `spec-kitty implement WP01` recovery — no `worktree repair`
  reference there. **#2007 item 13's drift is in the installed 3.2.0 build / generated code-paths, not in current SOURCE prompts.** The guard should still cover this to prevent reintroduction.

### Confirmed false-positives (do NOT flag)

- `charter context ... --no-mark-loaded` (charter/prompt.md:260; charter-doctrine SKILL.md:602;
  charter-command-map.md:230) — valid Typer auto-negation of `--mark-loaded`.
- `from specify_cli.* import ...` python snippets in `spec-kitty-bulk-edit-classification/SKILL.md`
  (lines 92, 99, 138, 154) — these are **real, in-venv** module paths (`specify_cli.mission_metadata`,
  `specify_cli.bulk_edit.occurrence_map`), not the bogus `specify_cli.core.templates`. #2007 item 9's
  bad import (`from specify_cli.core.templates import ...`) is **not present anywhere in SOURCE** —
  it was an ad-hoc command Robert typed, not a templated snippet. No SOURCE fix needed; the guard's
  scope is `spec-kitty …` CLI snippets, not arbitrary `python -c` lines.

### Drift tally (SOURCE, not generated copies)

- **HARD drift:** 12 references (all `doctrine list`/`doctrine show`).
- **BEHAVIORAL drift:** 3 references (1 missing-`--action`, 2 setup-plan no-flag).
- **Total actionable: 15** across 3 SOURCE files (2 skills + 1 mission-step prompt).
- Worst offender: `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md` — 11 of the 12 HARD hits.

---

## 3. CI command-snippet guard design

### 3.1 Precedent — this is a generalization, not a greenfield build

`tests/architectural/test_docs_cli_reference_parity.py` already ships:

- `scripts.docs._typer_walker.walk(app)` → `list[CommandPathEntry]` with `.path` (tuple of
  segments), `.hidden`, `.deprecated`. This is the **live registered surface** extractor.
- `test_skill_docs_profile_subcommands_are_registered` (FR-018) — already scans one SKILL.md for
  `spec-kitty agent profile <sub>` tokens via regex and asserts each `<sub>` is registered.

The #2007 guard is **that exact pattern, widened** from the single `agent profile` family to all
`spec-kitty …` snippets across all SOURCE skills/prompts/docs, with flag-level validation added.
That dramatically lowers risk: the hard part (live-surface introspection, the env-flag ordering at
import, the SaaS-gated path handling) is solved and battle-tested.

### 3.2 Extraction strategy

1. **Source set:** glob SOURCE only — `src/doctrine/skills/**/*.md`, `src/doctrine/skills/**/references/*.md`,
   `src/doctrine/missions/mission-steps/**/*.md`, and (a second, looser tier) `docs/**/*.md`.
   Exclude `docs/plans/engineering-notes/**` (archaeology/notes, not prescriptive) and all generated agent
   dirs (`.claude/`, `.amazonq/`, …).
2. **Snippet capture:** extract fenced ```` ```bash ```` blocks, then within them match lines
   beginning (after optional `uv run`, `$`, `#`-prefixed comments stripped) with `spec-kitty`.
   Tokenize the command path greedily over leading lower-case/hyphen words until the first token that
   is a flag (`-`/`--`), a placeholder, an argument value, or end-of-line.
3. **Path validation:** resolve the longest token-prefix that matches a registered `CommandPathEntry.path`
   (groups + leaf). If no registered command path is a prefix of the tokens → **HARD failure** with
   `file:line → spec-kitty <tokens>` and the nearest registered path as a suggestion.
4. **Flag validation (tier 2, opt-in per file):** for matched leaf commands, collect `--flag` tokens
   and check membership in that command's option set (read from the click command's `params`, including
   auto-negations of bool flags). Unknown `--flag` → failure. Keep this behind an allow-list initially
   because it has the most false-positive surface.

### 3.3 False-positive risks and mitigations

- **Placeholders:** `<handle>`, `<mission-slug>`, `<a-directive-id>`, `…`, `[OPTIONS]`. Mitigation:
  only validate the **command path** (lower-case/hyphen words); stop tokenizing at the first `<`, `[`,
  `…`, `$`, `{`, uppercase, or quote. Placeholders never appear in a command path position.
- **Bool-flag auto-negation:** `--no-mark-loaded`, `--no-auto-commit`, `--no-worktrees`. Mitigation:
  build the option set from click params and add the `--no-<name>` form for every `is_flag`/bool option.
- **Reference-table prose:** `docs/api/*.md` print `--mark-loaded --no-mark-loaded` as help text,
  not invocations. Mitigation: only scan inside ```` ```bash ```` fences; ignore tables / `Usage:` dumps.
- **Continuation lines & pipes:** `\`-continued commands and `| jq` tails. Mitigation: join `\`
  continuations; cut at the first `|`, `&&`, `;`, `>`.
- **`python -c` lines:** out of scope by construction (only `spec-kitty …` lines are validated).
- **Deprecated-but-present commands:** `walk()` already flags `.deprecated`; treat deprecated paths as
  valid-but-warn so the guard doesn't fight a separate deprecation banner test.

### 3.4 Allow-list placement

A module-level frozenset in the test file (mirroring `_SKILL_DOCS` in the existing parity test):
`_SNIPPET_DRIFT_ALLOWLIST: frozenset[tuple[str, tuple[str, ...]]]` keyed by
`(relative_file, command_path_tuple)`. Start **empty** (after the 15 SOURCE fixes land) so the guard
is a true ratchet. Any intentional pseudo-command in docs must be added explicitly with a comment — the
same discipline as the ratchet baselines in `tests/architectural/_baselines.yaml`.

### 3.5 Tractability and rough size — G3 DevEx enabler: YES

- **Tractable:** high confidence. All infrastructure (live walker, env-flag import ordering, regex
  token scan) exists; this is a widen + flag-check on a proven pattern.
- **Size:** ~120–180 LOC for the guard test + ~40–60 LOC of shared snippet-extraction helper
  (worth hoisting into `scripts/docs/` next to `_typer_walker.py` so the docs-lint job can reuse it).
  Path-level validation is the must-have (catches all 12 HARD hits); flag-level validation is a
  follow-on tier (catches the missing-`--action` class) and carries the false-positive budget.
- **Wiring:** runs in `tests/architectural/` (already collected by the docs-contract fail-on-drift
  gate per commit `04f2497ab`). No new CI job needed.
- **Caveat:** the guard catches *snippet* drift (HARD + missing-flag). It does **not** catch
  *behavioral* drift like setup-plan's no-flag contract (#2007 item 4) — that needs a resolver fix +
  regression test, not a snippet check. Be explicit about that boundary in the epic so the guard isn't
  oversold as covering all of problem (1).
