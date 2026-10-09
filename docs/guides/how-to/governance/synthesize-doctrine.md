---
title: How to Synthesize and Maintain Doctrine
description: Run charter synthesize and charter resynthesize, validate the bundle, check provenance, and recover from stale state.
doc_status: active
updated: '2026-10-08'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/context/charter-overview.md
- docs/context/governance-files.md
---
# How to Synthesize and Maintain Doctrine

This guide covers the day-to-day synthesis workflow: checking status, linting, running synthesis,
validating the bundle, and recovering from stale or corrupted state.

For background on the synthesis model, see [How Charter Works](../../../context/charter-overview.md).

---

## 1. Check doctrine status

Before running synthesis, check what the current state is:

```bash
uv run spec-kitty charter status
```

The output reports:
- Whether the bundle is current or stale relative to `charter.md`
- The synthesis/operator state
- With `--provenance`: per-artifact provenance details

```bash
# Include provenance details
uv run spec-kitty charter status --provenance
```

If status reports the bundle as stale, it means `charter.md` has been edited since the last
synthesis. Run lint and synthesis to bring it current.

---

## 2. Lint your charter file

Before synthesizing, check for graph-native decay:

```bash
uv run spec-kitty charter lint
```

Lint detects:
- **Orphans**: artifacts referenced in the DRG but without a backing definition
- **Contradictions**: two directives with conflicting instructions for the same action
- **Staleness**: artifacts whose provenance references a deleted or superseded built-in directive

Filter by severity to focus on critical issues:

```bash
uv run spec-kitty charter lint --severity high
```

Scope to a specific mission:

```bash
uv run spec-kitty charter lint --mission my-feature-slug
```

Fix any issues reported by lint before proceeding to synthesis.

---

## 3. Synthesize doctrine (dry-run first)

Always preview the synthesis before applying:

```bash
uv run spec-kitty charter synthesize --dry-run
```

The `--dry-run` flag stages and validates artifacts but does not promote them to the live tree.
Review the output to confirm the synthesis plan is correct.

`charter synthesize` reads the charter interview answers, resolves synthesis targets from the DRG
and doctrine, and writes artifacts to `.kittify/charter-packs/`. On a fresh project where
`.kittify/charter/generated/` is missing or empty, it materializes the minimal artifact set: a
`.kittify/charter-packs/` directory and a `PROVENANCE.md` record.

---

## 4. Apply synthesis

When the dry-run output looks correct, apply:

```bash
uv run spec-kitty charter synthesize
```

On success, the artifacts are promoted to `.kittify/charter-packs/`. The runtime can now use the
updated doctrine for governed mission context injection.

Additional options:

```bash
# Use fixture adapter for offline testing
uv run spec-kitty charter synthesize --adapter fixture

# Skip code-reading evidence collection (faster, less thorough)
uv run spec-kitty charter synthesize --skip-code-evidence

# Skip best-practice corpus loading
uv run spec-kitty charter synthesize --skip-corpus

# Print evidence summary and exit without running synthesis
uv run spec-kitty charter synthesize --dry-run-evidence
```

---

## 5. Partial resynthesis with resynthesize

When only a specific directive or tactic has changed, use `charter resynthesize` to regenerate
just the affected artifacts without touching unrelated ones:

```bash
# Regenerate a specific tactic
uv run spec-kitty charter resynthesize --topic tactic:how-we-apply-directive-003

# Regenerate all artifacts referencing a built-in directive
uv run spec-kitty charter resynthesize --topic directive:DIRECTIVE_003

# Regenerate all artifacts from a specific interview section
uv run spec-kitty charter resynthesize --topic testing-philosophy

# List valid topic selectors
uv run spec-kitty charter resynthesize --list-topics
```

`charter resynthesize` uses a structured selector to identify the target set. Unrelated artifacts
are never modified.

---

## 6. Validate the bundle

After synthesis, validate the bundle schema:

```bash
uv run spec-kitty charter bundle validate
```

This validates the bundle against the CharterBundleManifest v1.0.0 schema. A clean validate
confirms the bundle is ready for runtime use. Check after every synthesis run.

---

## 7. Check provenance

To verify what synthesized the current doctrine artifacts:

```bash
uv run spec-kitty charter status --provenance
```

The `--provenance` flag includes per-artifact provenance details in the output, showing which
synthesis run created each artifact and from what source.

---

## 8. Understanding staging state

When `charter status` reports a staging state or pending synthesis, it means synthesis artifacts
have been staged (validated) but not yet promoted to the live tree. To promote:

```bash
# Run synthesize without --dry-run to complete the promotion
uv run spec-kitty charter synthesize
```

If synthesis was interrupted, re-run from the beginning. Synthesis is designed to be re-runnable
without side effects.

---

## 9. Recovery: stale or corrupted bundle

**Symptoms of a stale bundle**:
- `charter status` reports drift between `charter.md` and the bundle
- `spec-kitty next` injects outdated context into agent prompts
- `charter bundle validate` fails with schema errors

**Fix**:

1. Check current state: `uv run spec-kitty charter status`
2. Lint for decay: `uv run spec-kitty charter lint`
3. Re-sync if you have made manual edits to `charter.md`: `uv run spec-kitty charter sync`
4. Re-run synthesis: `uv run spec-kitty charter synthesize`
5. Re-validate: `uv run spec-kitty charter bundle validate`
6. Confirm: `uv run spec-kitty charter status`

If `charter status` still shows drift after these steps, check `.kittify/charter/generated/` for
any malformed agent-generated YAML that may be blocking promotion. The adapter reads those files
before synthesis.

---

## See Also

- [How Charter Works](../../../context/charter-overview.md)
- [Governance Files Reference](../../../context/governance-files.md)
- [Charter CLI Reference](../../../api/charter-commands.md)
- [Troubleshooting Charter Failures](troubleshoot-charter.md)
