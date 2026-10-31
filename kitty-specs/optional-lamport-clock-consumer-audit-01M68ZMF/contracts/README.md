# Contracts

This mission introduces no new contract and changes no API surface. The one contract-shaped
value it does change is the on-disk `lamport_clock` sentinel the lifecycle-envelope upgrade
migration writes; that change and its rationale are recorded in
`docs/development/reference/optional-lamport-clock-consumers.md` and in the changelog entry
for #6414.
