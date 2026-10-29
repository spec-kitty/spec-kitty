# Approach

## 2026-10-27 — plan
- Tidy-first: extract a report value from the print-as-you-go activate/deactivate cascade code (golden text pins byte-identical output), then serialize it for `--json`.
- Status: reuse the #6555 soundness gate before the bundle check; route all errors through `render_coded_error`.
- Activation block reads through `charter.activation.api` only.
