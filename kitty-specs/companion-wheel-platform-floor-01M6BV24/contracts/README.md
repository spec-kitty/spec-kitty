# Contracts

This Mission defines no external contract, so this directory holds no contract artifact.

The change is build-time only: it reads an OS floor out of the pinned service binaries and refuses
a companion wheel whose tag would understate it (`plan.md`, "Documentation (this mission)"). The two
new refusals, `SERVICE_PLATFORM_FLOOR_EXCEEDED` and `SERVICE_PLATFORM_FLOOR_UNREADABLE`, extend the
existing internal `SERVICE_*`/`COMPANION_*` refusal set of `scripts/build_services_wheel.py`; they
are consumed by the release workflow and documented in the script's docstring and the changelog, and
no other repository, service or consumer speaks them (spec.md, "Out of Scope").
