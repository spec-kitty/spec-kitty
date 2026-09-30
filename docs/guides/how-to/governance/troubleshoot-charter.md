---
title: Troubleshooting Charter Failures
description: Diagnose and fix stale bundle, missing doctrine, compact-context, retrospective gate, and synthesizer rejection failures.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/external/tech-lead-evaluator.md
type: how-to
related:
- docs/context/charter-overview.md
- docs/guides/how-to/governance/setup-governance.md
- docs/guides/how-to/governance/extend-charter-for-unsupported-language.md
---
# Troubleshooting Charter Failures

This guide covers the most common Charter failure modes and how to fix them.

For background, see [How Charter Works](../../../context/charter-overview.md). If you haven't set up a
charter yet, or want the full interview-to-generation flow rather than a specific failure fix,
start at [How to Set Up Project Governance](setup-governance.md) instead.

---

## 1. Stale bundle

> **Model change**: this failure mode used to be described as `charter.md` drifting from a
> derived bundle, with `charter sync` as the fix. That model is retired. `.kittify/charter/charter.yaml`
> is the authoritative, resolving source; `charter.md` is a non-authoritative prose companion the
> runtime never parses, so it cannot cause drift. `charter sync` is now a confirmed no-op — it
> always reports `synced: False` and writes nothing. If you have this page bookmarked from an
> older run, use the symptoms and fix below instead. See [How Charter Works](../../../context/charter-overview.md)
> for the full authoritative-source model.

**Symptoms**:
- `uv run spec-kitty charter status --json` reports `synthesized_drg.state` as `"stale"`
- `spec-kitty next` injects governance context that does not reflect recent edits to
  `charter.yaml`'s `governance:` or `directives:` sections
- Agent behavior does not reflect recent changes you made to `charter.yaml`

**What is happening**: `charter.yaml` (the authoritative source) was edited after the last
`charter synthesize` run, so the synthesis manifest's stored content hash no longer matches a
freshly computed hash of `charter.yaml`. The synthesized doctrine graph (DRG) under
`.kittify/doctrine/` is stale relative to the charter that produced it. This is expected any time
you hand-edit `governance`, `directives`, or activation in `charter.yaml` — it self-heals on the
next successful synthesis run, which recomputes and re-stamps the hash.

**Fix**:

```bash
# 1. Check for graph-native decay
uv run spec-kitty charter lint

# 2. Re-run synthesis (recomputes and re-stamps the content hash)
uv run spec-kitty charter synthesize

# 3. Re-validate the bundle
uv run spec-kitty charter bundle validate

# 4. Confirm no drift
uv run spec-kitty charter status
```

There is no separate re-sync step: `charter sync` no longer extracts anything from `charter.md`,
so it is not part of this fix.

---

## 2. Missing doctrine

**Symptoms**:
- `uv run spec-kitty charter status` reports no bundle, an empty bundle, or missing `.kittify/doctrine/`
- `spec-kitty next` fails or warns that no governance context is available
- Agent prompts receive no Charter context

**What is happening**: The synthesis step has not been run, or the `.kittify/doctrine/` directory
is missing or empty.

**Fix**:

```bash
# 1. Run the full synthesis flow
uv run spec-kitty charter synthesize

# 2. Validate
uv run spec-kitty charter bundle validate

# 3. Confirm
uv run spec-kitty charter status
```

> **Model change**: this failure used to be framed as "`charter synthesize` fails because
> `charter.md` does not exist." That framing is stale. No failure branch in `charter synthesize`
> checks for `charter.md` — the actual gate is `.kittify/charter/charter.yaml` (the authoritative,
> resolving source), plus the interview answers it is compiled from. `charter.md` is a
> non-authoritative prose companion. See [How Charter Works](../../../context/charter-overview.md).

If `charter synthesize` fails because `charter.yaml` does not exist yet (or the interview
answers it is compiled from are missing):

```bash
# Run the interview and generate charter.yaml first
uv run spec-kitty charter interview --profile minimal --defaults
uv run spec-kitty charter generate --from-interview

# Then synthesize
uv run spec-kitty charter synthesize
uv run spec-kitty charter bundle validate
```

**Symptom**: `spec-kitty dispatch` reports the request was "routed to the generic agent" instead
of a specialist, on a project with no charter configured yet.

**What is happening**: the generic-agent fallback (`is_charter_empty`) fires whenever
`.kittify/charter/charter.yaml` is absent, no org/project pack is registered, and no
`agent_profiles` activation is present. Plain `charter pack apply minimal` only writes activation
keys into `.kittify/config.yaml` — it does not compile `charter.yaml`, so the bundle stays absent
and the fallback still fires. Applying `minimal` alone does **not** resolve this symptom.

**Fix**: apply a starter pack and compile it into the bundle in the same step, so
`.kittify/charter/charter.yaml` actually exists:

```bash
uv run spec-kitty charter pack apply minimal --compile
```

`--compile` chains `spec-kitty charter generate --no-from-interview`, producing
`.kittify/charter/charter.yaml`. The fallback check only tests the bundle's *presence*, not its
contents, so once the file exists `spec-kitty dispatch` moves off the generic-agent short-circuit
and back to normal profile routing (verified directly: `empty_charter_fallback` flips from `true`
to `false`, and an unambiguous request routes to a real specialist profile).

Note: `minimal` activates a curated set of directives and tactics only — it declares no
`agent_profiles` key (see `src/charter/activation/packs/minimal.yaml`'s own header), so this fix does not by
itself narrow which specialist gets picked. With no explicit `agent_profiles` activation, the
router still considers every built-in profile (three-state "admit all" semantics) and may report
`ROUTER_AMBIGUOUS` for underspecified requests — pass `--profile <profile-id>` to disambiguate
when that happens.

See [Quick baseline via a starter pack](setup-governance.md#quick-baseline-via-a-starter-pack) for
the additive-merge caveat.

---

## 3. Compact-context limitation

**Symptoms**:
- Governed mission actions receive incomplete Charter context
- Large project governance appears to be truncated in agent prompts
- Agents reference only a subset of your directives

**What is happening**: When the DRG context payload for an action is too large to include in full,
the runtime falls back to **compact-context mode** — a summarized view that includes resolved
paradigms, directives, and tool list but omits full doctrine library text.

This is a known limitation (see issue #787 in the project issue tracker; check that issue for
current resolution status).

**Workarounds**:
- Reduce the scope of `charter.yaml`'s `directives:` section by removing directives that are not
  relevant to the current project phase or that overlap significantly with other directives.
  (`charter.md` is a non-authoritative prose companion the runtime never parses — editing it has
  no effect on the DRG context payload.)
- Break a very large project governance layer into smaller, focused governance domains, each with
  its own charter.
- Use `charter resynthesize --topic <selector>` to regenerate only the high-priority directives
  and ensure they are correctly represented in the DRG.

---

## 4. Retrospective gate failure

**Symptoms**:
- `spec-kitty next` blocks at mission terminus with a retrospective gate error
- Mission cannot transition to `done`
- You see a message like "Charter does not authorize operator-skip in autonomous mode"

**What is happening**: The retrospective learning loop gate is blocking mission completion. In
autonomous mode, the retrospective is mandatory and cannot be skipped. In HiC mode, the gate
offered a retrospective and requires either running it or explicitly skipping it.

**Fix for HiC mode**:

```bash
# 1. View pending retrospective (summary)
uv run spec-kitty retrospect summary

# 2. Preview proposals for the blocked mission
uv run spec-kitty agent retrospect synthesize --mission my-feature-slug

# 3. Apply proposals (or skip in HiC mode by responding 'n' with a reason at the terminus prompt)
uv run spec-kitty agent retrospect synthesize --mission my-feature-slug --apply
```

**Fix for autonomous mode**: The retrospective cannot be skipped. If the facilitator failed:

```bash
# Check the retrospective record
# .kittify/missions/<mission_id>/retrospective.yaml

# View the summary for diagnostics
uv run spec-kitty retrospect summary

# Check for facilitator errors in the event log
# kitty-specs/<slug>/status.events.jsonl (filter by event_name prefix "retrospective.")
```

If the facilitator itself errored (exit code 2 with "Retrospective facilitator failed"), check
the retrospective YAML for schema errors and the status events file for the error event. Once
the underlying data issue is fixed, re-run `spec-kitty next` to retry the gate.

---

## 5. Synthesizer rejection

**Symptoms**:
- `uv run spec-kitty agent retrospect synthesize --mission <slug> --apply` exits with non-zero code
- Proposals are not applied
- The output shows "Conflict detection is fail-closed: no proposals applied"

**What is happening**: Two or more proposals conflict with each other (e.g., both try to add the
same glossary term with different definitions). The synthesizer fails closed and applies nothing.

**Fix**:

```bash
# 1. Run dry-run to see the conflict details
uv run spec-kitty agent retrospect synthesize --mission my-feature-slug

# 2. Read the conflict report — it names the conflicting proposals and the conflicting field

# 3. Apply only the non-conflicting proposals, or edit the durable target surface manually
uv run spec-kitty agent retrospect synthesize --mission my-feature-slug --proposal-id P1 --apply

# 4. If you changed charter-derived state manually, re-run synthesis/validation as needed
uv run spec-kitty charter synthesize
uv run spec-kitty charter bundle validate

# 5. Re-run retrospect synthesize for the surviving proposal set
uv run spec-kitty agent retrospect synthesize --mission my-feature-slug --proposal-id P1 --apply
```

---

## 6. Context says `Languages: python` (or `unknown`) for a non-Python project

**Symptom**: `spec-kitty charter context` prints `Languages: python` for a project that is not
written in Python, or prints `Languages: unknown` together with an advisory.

**Cause**: when the languages/frameworks answer (`languages_frameworks`) is a real declaration, the
languages are derived from that answer alone (built-in detector plus doctrine-scoped words), and
`unknown` means it named nothing recognized. Only when that answer is absent, the shipped default or
a placeholder are the other answers scanned for a built-in language or well-known tool word (for
example `pytest`, `mypy`, `ruff`, `npm` or `cargo`), such as a testing answer. The advisory appears
whenever no installed doctrine is scoped to the resolved languages, so a recognized language without
shipped guidance (for example `Languages: rust`) shows it too. A language token after `word-`, as in
`React-TypeScript`, does not count.

**Fix**: in `.kittify/charter/interview/answers.yaml`, state your languages in `languages_frameworks`
(if it is a placeholder, stray language or tool words in other answers decide instead), then
regenerate. `spec-kitty charter generate --force` reads the interview by default and re-derives the
languages; it replaces any hand edit of `catalog.languages` (as does `charter activate --resynthesize`). For the
advisory, follow
[Extend your charter for an unsupported language](extend-charter-for-unsupported-language.md).

---

## Diagnostic Quick Reference

| Question | Command |
|---|---|
| Is the bundle current? | `uv run spec-kitty charter status` |
| Are there graph decay issues? | `uv run spec-kitty charter lint` |
| Is the bundle schema valid? | `uv run spec-kitty charter bundle validate` |
| What retrospectives are pending? | `uv run spec-kitty retrospect summary` |
| What proposals exist for a mission? | `uv run spec-kitty agent retrospect synthesize --mission <slug>` |

---

## See Also

- [How to Set Up Project Governance](setup-governance.md) — the complete interview-to-generation flow
- [How to Synthesize and Maintain Doctrine](synthesize-doctrine.md)
- [Extend your charter for an unsupported language](extend-charter-for-unsupported-language.md)
- [How to Use the Retrospective Learning Loop](use-retrospective-learning.md)
- [Retrospective Schema Reference](../../../api/retrospective-schema.md)
- [How Charter Works](../../../context/charter-overview.md)
