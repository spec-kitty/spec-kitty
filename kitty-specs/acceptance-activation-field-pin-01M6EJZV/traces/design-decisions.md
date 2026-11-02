# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · claude · The model is right and the test is stale: #6556 intentionally grew CharterYaml to the 13-key ACTIVATION_YAML_KEYS authority to stop a legitimate charter failing extra_forbidden, and the model/authority parity gate is green. Bumping 10 to 13 would restate the vocabulary a second time, so WP01 reads the key list from the authority instead and leaves set-equality to the parity gate.
