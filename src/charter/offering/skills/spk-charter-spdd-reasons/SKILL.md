---
name: spk-charter-spdd-reasons
description: >-
  Drive REASONS Canvas authoring and review for Spec Kitty missions that
  opted in to Structured-Prompt-Driven Development (SPDD) via charter
  selection, and review structured prompt rationale.
  Triggers: "use SPDD", "use REASONS", "generate a REASONS canvas",
  "apply structured prompt driven development", "make this mission SPDD".
  Does NOT handle: enforcing SPDD on projects whose charter has not
  selected the SPDD/REASONS artifacts (escalate to charter workflow instead).
  Does NOT mirror code as prose; code remains the source of truth for
  current behavior.
---

# spk-charter-spdd-reasons

Use this skill when a mission opts into SPDD, REASONS Canvas work, or structured
prompt rationale review. The canvas is a thin, agent-curated reasoning layer
next to the spec, plan, and tasks, stored at
`kitty-specs/<mission>/reasons-canvas.md`.

## Flow

1. Confirm SPDD is selected by charter or mission context
   (`is_spdd_reasons_active` in `src/charter/offering/spdd_reasons/activation.py`).
2. Author or review the REASONS Canvas before downstream prompts depend on it,
   using its seven sections: Requirements, Entities, Approach, Structure,
   Operations, Norms, Safeguards.
3. Keep rationale tied to mission decisions, not generic process commentary.
4. In review, trace the diff against the canvas and classify divergences with
   the drift taxonomy.
5. Return approved rationale to specify, plan, or implementation steps.

## Boundaries

- Do not mirror the code as prose; reference source artifacts instead.
- Do not overwrite user-authored canvas content; merge by appending or
  refining.
- Do not silently enforce SPDD on a project that did not opt in through its
  charter; escalate to the charter workflow.
- The charter wins over the canvas; escalate glossary conflicts to
  `spk-charter-glossary`.

## References

- `references/reasons-canvas-workflow.md` -- Activation rules and detection,
  canvas authoring and review, charter precedence, glossary discipline, and
  reference paths.
