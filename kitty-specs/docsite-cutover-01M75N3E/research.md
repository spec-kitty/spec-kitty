# Research: Docsite cutover to doc-kitty

## R-1: The canary result

- **Decision**: proceed with the cutover; the D-5 GitHub Pages leg is verified.
- **Evidence**: run [43027580608](https://github.com/spec-kitty/spec-kitty/actions/runs/43027580608) and the [report on #6938](https://github.com/spec-kitty/spec-kitty/issues/6938#issuecomment-6796965517): all 8 URL classes of `scripts/docs/site_live_probe.py` passed against `https://docs.spec-kitty.ai`, and DocFX was restored byte-identical.

## R-2: Where the smoketest runs (#2361 "Scope")

- **Decision**: a job in `docs-pages.yml` with `needs: deploy`, `main` only, the preferred option of #2361.
- **Rationale**: a failed smoketest reds the same run that shipped the site. A separate `workflow_run` plus schedule workflow decouples the probe from the deploy and adds a second fork-guarded workflow for no gain.
- **Alternatives**: separate scheduled workflow (rejected: second mechanism, staler signal).

## R-3: Alerting

- **Decision**: no auto-filed alert issue; a red run is the signal (operator decision). #2361's optional alert issue is not adopted.

## R-4: URL set

- **Decision**: reuse the probe unchanged. It already derives one URL per D-13 class from the committed ledgers (`site/url-baseline.txt`, `site/moves.yaml`, `site/legacy-redirects.json`), including the site root, `/llms.txt` and a retired URL that must answer 404, as #2361 asks. Its logic is covered by `tests/docs/test_site_live_probe.py`, and the shared build runs it over loopback on every pull request.

## R-5: Token permissions

- **Decision**: workflow default `contents: read`; `pages: read` for the probe-and-configure job; `pages: write` and `id-token: write` only on `deploy`.
- **Rationale**: `GET /repos/{owner}/{repo}/pages` needs the Pages read permission; `actions/configure-pages` without `enablement` only reads. The deploy is the only writer.
- **Risk**: if the read scope proved insufficient, the probe would answer 403, the job fails, and nothing deploys (DocFX stays live). The fix would be a one-line permission change. Flagged for the reviewer.

## R-6: Supply chain (DIRECTIVE_051)

- No new dependency. `actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346` (v5.0.1) and `actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8` (v5.0.0) are the SHAs the canary already used and this repository already pins. The shared build is first-party. No adversarial challenge needed: no dependency decision is made.
