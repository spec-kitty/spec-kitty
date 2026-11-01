# Tooling friction — events-service cut-over

Tooling touched: `spec-kitty service vendor`, `scripts/sync_services.py`, the sync-services composite action, `gh` (release, attestation), the mission CLI (`agent mission create`, `decision`, `spec-commit`, `setup-plan`).

- **[2026-11-01][specify] `gh release view/download` refused.** The session proxy blocks GitHub GraphQL; `gh api .../releases/tags/<tag>` (REST) and plain `curl` of the release download URLs worked. Workaround.
- **[2026-11-01][specify] `gh attestation verify` cannot initialise Sigstore in the sandbox.** "no valid Sigstore verifiers could be initialized"; REST shows the attestation exists. Recorded as not verified here; candidate gap: `service vendor` does not verify attestations either (its documented follow-up, #6590).
- **[2026-11-01][specify] `spec-kitty spec-commit` writes its own message with no trailer option.** The required `Co-Authored-By` attribution had to be added with an amend. Candidate gap: a `--trailer` passthrough.
- **[2026-11-01][tasks] Tool-authored commits carry no attribution trailer.** `setup-plan`, `finalize-tasks` and the status-transition commits write their own messages; the required `Co-Authored-By` line is restored when the branch history is compacted at wrap-up. Candidate gap (same as the `spec-commit` one).
