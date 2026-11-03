# No external contracts changed in this mission

`#7128` fixes an internal preflight in the analysis report transaction. Nothing a caller can observe
through a contract changed:

- no CLI flag, option name or default (`--report-only` keeps its name and meaning),
- no JSON key, `error_code`, `commit_status` value or exit code,
- no report file format, no material-manifest schema, no pin file schema.

The only observable difference is that an invocation which used to be refused with
`DIRTY_ANALYSIS_INPUT` on a correctly set-up clone now records the report — the behaviour the
`--report-only` flag already promised. See `spec.md` FR-001..FR-006 and
`docs/development/analysis-report-transactions.md` for the behaviour that did change.
