# Contracts: none

This Mission changes no API, wire format, JSON envelope or persisted shape. The only
contract it touches is the internal identity-resolution contract: `resolve_artifact_urn`,
`resolve_config_id` and `resolve_selected_id_to_stem` keep their names, parameters, return
types and exception types, and `charter activate`/`deactivate` keep their output and exit
codes for every token that already resolved.

What changes is which spellings reach the artifact: a `<kind>:<id>` URN, a normalised
directive id and a declared id now resolve on the cascade-source path exactly as the
runtime gate and the write path already resolved them. The pins for that contract live in
`tests/charter/activation/test_identity_facade_6433.py` and
`tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py`.
