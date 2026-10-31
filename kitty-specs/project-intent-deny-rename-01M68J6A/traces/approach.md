# Approach tracer — project-intent-deny-rename-01M68J6A

## Seed

- **[2026-10-31][specify] One authority, one new choice.** The fix extends the existing rename helper
  (`charter/activation/synthesizer/legacy_rename.py`) rather than adding a deny-side mapping: its
  token step already rewrites stem tokens in the activation write target, so the deny list joins that
  step and the write stays one call. A new `DenyListChoice.RENAME` is the sanctioned authority; the
  FR-014 gate pins its single origin. Issue #6565.

## Close

- **[2026-10-31][implement] The prediction held.** The deny rename landed as one predicate change
  and one choice in the existing token step (WP01 7af7c3054), with the gate pins in the same commit
  and the ADR wording following in WP02. Two review cycles were enough; no design change was needed
  after the spec.
