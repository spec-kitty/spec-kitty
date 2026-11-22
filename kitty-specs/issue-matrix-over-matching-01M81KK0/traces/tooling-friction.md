# Tooling friction

- **[2026-11-22][plan] The Mission's own artefacts trip the detector it is fixing.** Citing the bug's own examples (all-zero colours, a planted-break label, a closing keyword with a small number) in spec.md or plan.md would create phantom references, so the spec writes them with `#N` placeholders. Disposition: workaround; expected to disappear once the fix lands.
- **[2026-11-22][implement] First pytest run of a new file took about 100 s; reruns under 3 s.** The cost is a cold collection or import cache, not the tests themselves. Disposition: noted, no action.
