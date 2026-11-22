# Tooling friction

- **[2026-11-22][plan] The Mission's own artefacts trip the detector it is fixing.** Citing the bug's own examples (all-zero colours, a planted-break label, a closing keyword with a small number) in spec.md or plan.md would create phantom references, so the spec writes them with `#N` placeholders. Disposition: workaround; expected to disappear once the fix lands.
