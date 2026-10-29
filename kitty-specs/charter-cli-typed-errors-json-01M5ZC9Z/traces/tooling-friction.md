# Tooling friction

## 2026-10-27 — plan
- `spec-kitty mission list --json` returned entries with no `key`/`name` field readable by a naive parser; type confirmed as software-dev from the prompt instead.
- `spec-kitty upgrade --agent-check --json` exits 2 under `SPEC_KITTY_NO_NAG` (reason `nag_disabled`); harmless but noisy.
- #6525 names `CascadeActivationResult.to_report`, which does not exist; the serializer is new work.
