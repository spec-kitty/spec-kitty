# Tracer: design decisions
- G1: the recorder answers `core.sshCommand` reads as unset instead of scripting them in every test: they are local config reads, not GitSource contacts, and the kernel tests from `dc4524a5` already pin their semantics.
- G2b: fake `run_origin_gate` in the harness (it is a collaborator like the rest) rather than adding `topology` to the stub; the owned test now asserts the fact reaches the gate.
- G3: parse `result.stdout` across the whole file (stdout is the `--json` contract); one test pins the note on stderr and in `advisories`.
