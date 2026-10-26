# Quickstart: verify the fix

```bash
uv run --frozen pytest tests/charter/synthesizer/test_reach_only_delivery.py tests/charter/synthesizer/test_styleguide_reach_only.py -q
```

Manual check in a project with synthesized tactics: corrupt
`.kittify/charter/synthesis-manifest.yaml`, deactivate the owning directive, run
`spec-kitty charter context --action implement`; the synthesized tactic is absent and a warning
names the unreadable manifest.
