# Tracer — tooling friction

Mission: `nightly-census-and-timeout-headroom-01M3PM2S`

- `spec-kitty doctrine regenerate-graph --check` reports "stale" on any pack YAML edit, even one that
  changes no edge, because `pack-manifest.yaml` carries content hashes; regenerate to see whether any
  `*.graph.yaml` actually moved.
- Nightly job logs run pytest with `-q -n auto`, so no "collected N" line is printed; test counts had to
  be summed from the final summary line.
