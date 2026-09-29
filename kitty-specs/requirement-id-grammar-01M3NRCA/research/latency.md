# NFR-003 latency micro-benchmark (WP08 / T037)

## Method

- base SHA: `ddf114f06c54e5454bad5c3172e7049a95f7f862`
- head SHA: `fdf383f34a746104d15afe44cf97d9d9d7310749`
- command: `.venv/bin/python research/latency_bench.py --base-src <base-worktree>/src --head-src <head-tree>/src --base-sha <sha> --head-sha <sha> --out-dir <scratch>`
- rounds: 20 (ABBA-interleaved: round order alternates which side runs first)
- machine: Linux-6.8.0-136-generic-x86_64-with-glibc2.39
- CPU: AMD Ryzen 9 7950X3D 16-Core Processor (32 logical CPUs)
- Python: 3.11.15
- load average before=(1.2578125, 1.8408203125, 2.140625) after=(1.4765625, 1.81689453125, 2.11572265625)

## Fixture

- 30 work packages (WP01..WP30), each with `requirement_refs: [FR-0NN, NFR-00x]`
- spec.md declares FR-001..FR-030, 5 NFRs, 3 Cs, 4 SCs
- entry point: in-process `typer.testing.CliRunner` on `specify_cli.cli.commands.agent.mission.app`, `finalize-tasks --mission <slug> --json --validate-only`
- both sides reached the same pass verdict on the untimed pre-check (asserted by the driver before any round ran)
- every sample (warm-up and timed) asserted read-only: `git status --porcelain` empty after the call

## Phase metric (wrapped functions)

- `specify_cli.cli.commands.agent.mission_finalize._read_spec_requirement_ids`
- `specify_cli.cli.commands.agent.mission_finalize._validate_requirement_mapping`
- (both exist under the same name and module path at the merge-base; no head rename was needed)

## Results

- base phase (ms): median=0.2425 min=0.2280 max=0.2828
- head phase (ms): median=6.5809 min=6.2801 max=7.0101
- base total (ms): median=173.3594 min=168.2932 max=187.2758
- head total (ms): median=160.9636 min=154.6493 max=168.3604

### base samples

| # | phase (ms) | total (ms) |
| --- | --- | --- |
| 1 | 0.2473 | 171.4295 |
| 2 | 0.2344 | 168.3964 |
| 3 | 0.2433 | 174.0967 |
| 4 | 0.2404 | 178.2242 |
| 5 | 0.2331 | 170.6571 |
| 6 | 0.2662 | 175.0809 |
| 7 | 0.2828 | 173.0045 |
| 8 | 0.2280 | 170.9608 |
| 9 | 0.2792 | 183.4286 |
| 10 | 0.2434 | 175.1556 |
| 11 | 0.2282 | 168.2932 |
| 12 | 0.2349 | 168.7544 |
| 13 | 0.2432 | 171.9314 |
| 14 | 0.2311 | 173.7143 |
| 15 | 0.2417 | 179.5507 |
| 16 | 0.2647 | 185.0106 |
| 17 | 0.2524 | 182.9576 |
| 18 | 0.2583 | 187.2758 |
| 19 | 0.2389 | 169.7042 |
| 20 | 0.2299 | 171.9123 |

### head samples

| # | phase (ms) | total (ms) |
| --- | --- | --- |
| 1 | 6.6135 | 163.9982 |
| 2 | 6.4291 | 161.4216 |
| 3 | 6.4237 | 158.3449 |
| 4 | 6.7526 | 167.4419 |
| 5 | 7.0101 | 164.6227 |
| 6 | 6.4983 | 161.8510 |
| 7 | 6.6716 | 157.4159 |
| 8 | 6.6972 | 159.1744 |
| 9 | 6.2801 | 158.9739 |
| 10 | 6.4048 | 154.6493 |
| 11 | 6.5090 | 159.9511 |
| 12 | 6.9028 | 167.9393 |
| 13 | 6.5595 | 155.5119 |
| 14 | 6.6229 | 159.4595 |
| 15 | 6.4479 | 157.0516 |
| 16 | 6.5003 | 164.4718 |
| 17 | 6.6918 | 161.8870 |
| 18 | 6.5133 | 160.5056 |
| 19 | 6.6023 | 162.9983 |
| 20 | 6.9417 | 168.3604 |

## Verdict

**NFR-003: PASS (phase Δ = +6.3 ms <= 50 ms; total head = 161.0 ms < 2000 ms)**

- phase delta: +6.3384 ms (budget: <= 50 ms) -- PASS
- total delta (head - base): -12.3958 ms
- head total budget: < 2000 ms -- PASS

