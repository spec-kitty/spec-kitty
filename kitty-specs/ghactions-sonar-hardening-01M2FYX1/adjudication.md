# Adjudication Dossier — GH-Actions Sonar Hardening (ghactions-sonar-hardening-01M2FYX1)

> **HOTSPOT-REVIEW / WON'T-FIX DOSSIER — NO CODE EDIT.**
> This document is the sole deliverable of WP05 (C-001, FR-005). It contains **zero workflow,
> action, or source edits** — every finding below is either (a) adjudicated safe-as-written and
> recommended for a "Won't Fix" / "Safe" hotspot-review resolution in the SonarCloud UI, (b)
> adjudicated a false positive and recommended for "False Positive" resolution, or (c) explicitly
> **not** adjudicated and flagged for a follow-up ticket. This dossier is **separate** from the
> code fixes landed in WP01 (S7630 env-indirection), WP02 (S7637 SHA-pinning + ci-windows
> perms/install), WP03 (S8264/S8233 permission relocation + ci-aggregate install pins), and WP04
> (3rd-party install pinning in ci-modules.yml / check-spec-kitty-events-alignment.yml /
> packs.yml). Findings that WP01–04 resolve with a code edit are **not** repeated here as
> won't-fix.

**Source of truth**: live SonarCloud API pull, `componentKeys=spec-kitty_spec-kitty`,
`languages=githubactions`, `resolved=false` — **99 open findings** at pull time.
```
curl -s "https://sonarcloud.io/api/issues/search?componentKeys=spec-kitty_spec-kitty&languages=githubactions&resolved=false&ps=200"
```
Pulled: 2026-09-14T13:04Z. Repo HEAD at pull time: `3b03047e934183c9f5099de9a8dbbb43e935cae7`
(branch `fix/ghactions-sonar-hardening`).

## Mission scope recap (spec.md)

- **In-scope (PR-CI-exercised) workflows**: `ci-quality.yml`, `ci-windows.yml`,
  `module-tests.yml`, `ci-aggregate.yml`, `ci-fleet-verdict.yml`, `ci-modules.yml`,
  `check-spec-kitty-events-alignment.yml`, `packs.yml` — plus the composite action they share,
  `.github/actions/warmup/action.yml`.
- **Release-critical, OUT of scope, deferred** (spec.md "Grounding"): `release.yml`,
  `release-readiness.yml`, `ci-nightly.yml` — not exercised by PR CI, so a hardening edit there
  cannot be validated before merge; deferred to a separate follow-up with a manual dry-run.
- **Excluded**: `docs-pages.yml` — under independent change in PR #4286; not touched or
  adjudicated by this mission.

Only findings inside the in-scope surface are adjudicated "safe" or "false positive" below. A
short **Section D** lists residual findings in the deferred/excluded files for transparency —
those are explicitly **not** adjudicated (see the "Honest gaps" note there).

---

## Section A — Safe-as-written (won't-fix) hotspots

### A1. S8541 `uv sync --frozen ...` self-install (~46 sites)

**Rule**: `githubactions:S8541` — *"Omitting `--no-build`/`--only-binary :all:` can lead to the
execution of setup scripts."*

**Rationale**: Every flagged site below installs `spec-kitty-cli` itself (this project, via its
own `pyproject.toml`) plus its declared dependency set. `spec-kitty-cli` ships a **hatchling
build backend** and is not a pure-wheel package — building it from source is the intended,
required install path; `--no-build` or `--only-binary :all:` would refuse to build the very
package the workflow exists to test and **break every job**. The rule's premise (an *untrusted*
sdist executing an attacker-controlled `setup.py`/build hook) does not apply: the sdist being
built is this repository's own first-party source tree, checked out by `actions/checkout` in the
same job, not a third-party artifact pulled from an index. Every one of these installs is also
`--frozen` against `uv.lock`, which pins **1420 `sha256` hashes** (`grep -c sha256 uv.lock`) — the
resolved dependency graph is locked and integrity-verified; nothing unpinned or untrusted is
built or resolved.

**In-scope sites (45 lines, first-party self-install `uv sync --frozen [...]` and the paired
`uv run --frozen <tool>` invocation in the same step — see A2):**

| File | Lines |
|---|---|
| `.github/actions/warmup/action.yml` | 134 (`uv sync --frozen --all-extras`, pr/default mode) |
| `.github/workflows/ci-quality.yml` | 28, 176 (`uv sync --frozen --all-extras`) |
| `.github/workflows/ci-aggregate.yml` | 357 (`uv sync --frozen --all-extras`) |
| `.github/workflows/ci-router.yml` | 210, 255 (`uv sync --frozen --extra lint`); 268, 287, 300, 344, 372, 387, 405, 425, 447, 476 (`uv sync --frozen --all-extras`) |
| `.github/workflows/packs.yml` | 112, 131, 150, 174, 197, 224, 239 (`uv sync --frozen --all-extras`) |

(Line 357 in `ci-aggregate.yml` is the only `uv sync --frozen` site left un-touched there; the
other two S8541 hits in that file — line 179 `pip install pyyaml==6.0.2` and line 367
`uv pip install diff-cover/defusedxml` — are WP03 code-fix targets, not won't-fix, and are
excluded from this count. Likewise `ci-modules.yml:63` is a WP04 code-fix target, excluded.)

**Recommended SonarCloud resolution**: **Won't Fix** ("Safe" hotspot status), with the rationale
above attached per-issue or at minimum linked to this dossier.

### A2. S8541/S8544 on `uv run --frozen <tool> ...` (test/lint invocations, not installs)

The paired lines directly below each `uv sync --frozen` call in the table above are also
flagged — these are `uv run --frozen ruff check`, `uv run --frozen ruff format --check`,
`uv run --frozen spec-kitty regen --check`, and `uv run --frozen pytest <path>` invocations.

**Rationale**: `uv run` performs an implicit sync-check before executing, which is what trips the
installer heuristic — but by construction every flagged `uv run --frozen ...` line is preceded,
in the **same shell step**, by an explicit `uv sync --frozen --all-extras` (or `--extra lint`)
that has already built the venv (adjudicated in A1). The `uv run --frozen` call that follows is a
no-op resync against the identical frozen lockfile plus the actual test/lint/regen invocation —
it builds nothing new and installs nothing beyond what A1 already covers. `--frozen` on `uv run`
additionally refuses to touch the lockfile if it were ever out of date, so there is no drift
surface here either.

Exact paired lines (file → `uv sync` line / `uv run` line):
- `ci-quality.yml`: 28 / 31, 32
- `ci-router.yml`: 210/211,212 · 255/256 · 268/269 · 287/288 · 300/301 · 344/349 · 372/373 ·
  387/388 · 405/406 · 425/426 · 447/458 · 476/477
- `packs.yml`: 112/113 · 131/132 · 150/151 · 174/180 · 197/198 · 224/225 · 239/240

**Recommended SonarCloud resolution**: **Won't Fix**, same rationale as A1 (these ARE the ~46
count together with A1 — Sonar reports one issue per flagged line, so the `uv sync` line and its
paired `uv run` line are two issues sharing one root cause).

### A3. S8544 warmup drift resolution — `uv sync --all-extras --upgrade-package` (nightly full mode)

**File/line**: `.github/actions/warmup/action.yml:132`
```yaml
if [ "$mode" = "full" ]; then
  uv sync --all-extras --upgrade-package "spec-kitty-events==${{ steps.resolve-rev.outputs.resolved-events-rev }}"
else
  uv sync --frozen --all-extras
fi
```
**Rationale**: This branch is intentionally **not** locked. `mode == "full"` is the nightly
drift-detection path (research decision D2 in this mission's `research/`): it deliberately
re-resolves `spec-kitty-events` to whatever version `resolve-rev` picked up from
`https://pypi.org/pypi/spec-kitty-events/json` (the *latest published* mainline release — see
A4/B1), to catch upstream drift before it reaches a PR. `mode == "pr"` — the path every actual PR
exercises — takes the `else` branch, which is the same `uv sync --frozen --all-extras` adjudicated
safe in A1. The unlocked resolution never runs in PR CI.

**Recommended SonarCloud resolution**: **Won't Fix** — by design, non-PR path, PR path is frozen.

### A4. S8544 `ci-windows.yml:86` self-bootstrap `pip`/`pipx`

**File/line**: `.github/workflows/ci-windows.yml:86`
```yaml
- name: Install pipx
  run: |
    python -m pip install --upgrade pip pipx
    python -m pipx ensurepath
```
**Rationale** (per WP02's T004 adjudication note — WP02 pinned this file's S7637 action refs and
relocated its S8264 permissions but intentionally left this line unedited): this is the runner's
own `pip` upgrading itself plus installing `pipx`, the tool used two steps later to bootstrap
`spec-kitty-cli` in an isolated environment on the Windows runner. `pip` and `pipx` have no
meaningful "lock" surface for a bootstrap step run once per job on a stock GitHub-hosted runner
image — pinning them buys no security benefit and risks drifting out of sync with the runner
image's bundled Python. This is the same self-bootstrap pattern as A3, applied to `pip`/`pipx`
rather than `uv`.

**Recommended SonarCloud resolution**: **Won't Fix**.

---

## Section B — False positives

### B1. S6506 + S8482 on `.github/actions/warmup/action.yml:73`

**Rules**: `githubactions:S6506` — *"Not enforcing HTTPS here might allow for redirections to
insecure websites."* / `githubactions:S8482` — *"Avoid executing downloaded artifacts directly
without verification."*

**Line**:
```yaml
rev="$(curl -fsSL https://pypi.org/pypi/spec-kitty-events/json \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["info"]["version"])')"
```
**Rationale — both rules are false positives against the actual code**:
- **S6506 (HTTPS)**: the URL is already `https://pypi.org/...` — the scheme is HTTPS, hard-coded,
  with no `http://` fallback or redirect-following flag that could downgrade it. There is no
  insecure-redirect surface to enforce against; the rule appears to be pattern-matching on `curl`
  usage rather than the literal URL string.
- **S8482 (downloaded artifact executed without verification)**: nothing downloaded here is
  *executed*. The `curl` response is piped into `python3 -c` as **JSON text on stdin**; the
  Python one-liner parses it with `json.load` and prints a single field (`info.version`) — a
  version string, not code. No shell/`eval`/subprocess execution of the fetched content occurs,
  and the extracted string is used later purely as a `uv sync --upgrade-package` version pin
  (A3), not interpolated into a command.

**Recommended SonarCloud resolution**: **False Positive** for both `S6506` and `S8482` on this
line.

### B2. S6505 on third-party CLI installs needing lifecycle scripts

**Rule**: `githubactions:S6505` — *"`npx`/`npm install` can install packages on-demand and run
their lifecycle scripts."*

**Sites**:
1. `.github/workflows/packs.yml:194` — `npm install -g @anthropic-ai/claude-code`. This tool's
   published npm package relies on its install lifecycle scripts (postinstall) to place its CLI
   binary and complete setup; `--ignore-scripts` breaks the installed tool. WP04 pins this
   install to an **exact version** (closing the companion `S8543` "unlocked dependency" finding
   on the same line) but explicitly does **not** add `--ignore-scripts` — see WP04's task note:
   *"do not add `--ignore-scripts` (it needs its lifecycle scripts, S6505 → adjudicate in
   WP05, no edit)"*. After WP04 lands, this line is version-pinned; the S6505 finding on it
   remains open by design and is won't-fix here.
2. `.github/workflows/ci-router.yml:230` — `npx --yes markdownlint-cli2 "**/*.md" || true`. This
   is a **non-blocking** documentation linter: `|| true` means the step can never fail the job
   regardless of what `npx` resolves or runs, and `markdownlint-cli2` is a dev-only linting tool
   with no lifecycle-script attack surface relevant to a job whose worst case is "the lint step
   silently no-ops."

**Recommended SonarCloud resolution**: **Won't Fix** for both — the first because the tool
requires its lifecycle scripts to function (functionally equivalent to `--ignore-scripts`
breaking the CLI), the second because the invocation is best-effort/non-blocking with no
consequential blast radius.

---

## Section C — Summary counts (in-scope, adjudicated here)

| Rule | In-scope findings adjudicated | Disposition |
|---|---|---|
| S8541 | 45 (A1) | Won't Fix |
| S8544 | 2 (A3 warmup:132, A4 ci-windows:86) | Won't Fix |
| S6506 | 1 (B1 warmup:73) | False Positive |
| S8482 | 1 (B1 warmup:73) | False Positive |
| S6505 | 2 (B2 packs.yml:194, ci-router.yml:230) | Won't Fix |
| **Total** | **51** | — |

These 51 are drawn from the 99 total open `githubactions` findings; the remaining 48 are either
WP01–04 code-fix targets (S7630, S7637, S8264, S8233, the bare-install S8541/S8544/S8543 sites
WP03/WP04 pin) or fall in the deferred/excluded surface covered in Section D below, not in this
dossier's "safe/false-positive" adjudication.

---

## Section D — Deferred / excluded surface (honest gaps, NOT adjudicated safe)

Per spec.md, `release.yml`, `release-readiness.yml`, and `ci-nightly.yml` are release-critical and
not exercised by PR CI, so hardening edits there cannot be validated before merge — the mission
explicitly **defers** them to a follow-up with a manual dry-run, rather than editing or
adjudicating them now. `docs-pages.yml` is excluded outright (under independent change in PR
#4286). Listing what's open there for continuity — **none of the following is claimed
safe-as-written by this dossier**; they need their own review when that follow-up work happens:

- **`release-readiness.yml:202-206`** — `uv export --frozen --no-dev --no-hashes ... | pip
  install -r .cutover-requirements.lock.txt` (S8544). This is the one release-readiness site the
  WP05 task brief asked to be captured here even though it's out of code-fix scope: the installed
  requirements file is generated by `uv export --frozen` from the same `uv.lock` adjudicated safe
  in A1 — every version is resolved and pinned, though `--no-hashes` means this particular export
  drops the sha256 hash pins A1 relies on for its "integrity-verified" claim. **This is a weaker
  guarantee than A1**, not an equivalent one; flagging it here for the follow-up reviewer rather
  than asserting it's equally safe.
- **`release-readiness.yml:58-59`** — `pip install pyyaml` (no version, no `--only-binary`;
  S8541 + S8544). This is a genuinely **unpinned** third-party install with no defensible
  won't-fix rationale — it should be pinned in the deferred follow-up, not waved off.
- **`release.yml:42`** — `uv sync --python "$(which python)" --extra test --extra lint` (S8544).
  Unlike every A1 site, this `uv sync` call is **not** `--frozen` — a real gap, not the same
  pattern as A1; needs its own fix in the deferred follow-up.
- **`ci-nightly.yml:90,97,105`** (S8541) and **`:97,105,154`** (S8544) — same
  `uv sync --frozen --all-extras` / `uv run pytest -m ...` shape as A1/A2 (note: the `uv run
  pytest` calls here omit `--frozen`, unlike the in-scope A2 sites). Almost certainly the same
  rationale would apply, but this file is out of this mission's edit/adjudication scope by
  NFR-002 — left for the deferred follow-up to formally adjudicate or fix.
- **`docs-pages.yml:52`** — S6506 (HTTPS). Not reviewed here; PR #4286 owns this file.
- Residual `S7637` (full-SHA action pinning) on `release.yml` (3 sites) and `release-readiness.yml`
  (2 sites) — out of scope for the same reason; not part of WP02's SHA-pinning surface.

---

## Reviewer checklist (per WP05's own risk note)

- [ ] Confirm `git diff` for this commit touches **only**
      `kitty-specs/ghactions-sonar-hardening-01M2FYX1/adjudication.md` — zero workflow/action
      edits (C-001).
- [ ] Spot-check the hatchling self-install claim (A1): `spec-kitty-cli`'s `pyproject.toml` build
      backend and the `uv.lock` hash count (`grep -c sha256 uv.lock` → 1420).
- [ ] Spot-check A2's pairing claim: each flagged `uv run --frozen` line is preceded in the same
      step by the `uv sync --frozen` line adjudicated in A1 (see the line tables above).
- [ ] Confirm Section D makes no safety claim about `release.yml` / `release-readiness.yml:58-59`
      / `ci-nightly.yml` — those are flagged as open gaps for a follow-up, not adjudicated here.


---

## Section E — Deferred-surface resolution (follow-up mission, issue #4352)

> Added by the follow-up mission that Section D deferred (issue #4352, milestone 4.0.0, epic
> #1928). This section supersedes Section D's "honest gaps" for the three release-critical files:
> the genuine findings are now **code-fixed**, and the residual first-party self-install /
> frozen-lock findings are adjudicated won't-fix here, extending the A1/A2/A4 rationale. Source of
> truth: a fresh live SonarCloud pull (`componentKeys=spec-kitty_spec-kitty&languages=githubactions&resolved=false`)
> filtered to the three files — 5 findings on `release.yml`, 11 on `release-readiness.yml`, 6 on
> `ci-nightly.yml`. **Validation constraint:** these workflows are not exercised by PR CI, so the
> code fixes were validated by a manual dry-run (release-readiness `workflow_dispatch` in tag mode)
> plus a local exercise of the changed install commands — see the PR's Tests-run section.

### E1 — Code fixes landed (finding → fix)

**`release.yml` (5 open findings, all fixed):**

| Line | Rule | Fix |
|---|---|---|
| 15 | S8233 | Removed workflow-level `permissions: contents: write`; relocated to job scope — `build-release` and `verify-pypi-installability` get `contents: read`, `publish-pypi` keeps its own `contents: write` + `id-token: write`. |
| 38 | S7637 | `astral-sh/setup-uv@v8.1.0` → `@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0`. |
| 42 | S8544 | `uv sync ... --extra test --extra lint` gained `--frozen` (lock-verified self-install). |
| 274 | S7637 | `softprops/action-gh-release@v3.0.0` → `@b4309332981a82ec1c5618f44dd2e27cc8bfbfda # v3.0.0`. |
| 287 | S7637 | `pypa/gh-action-pypi-publish@release/v1` → `@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2 (release/v1 tip)`. **OIDC preserved**: the SHA is simultaneously the `release/v1` branch tip and official tag `v1.14.2`; OIDC minting keys on the job's `id-token: write` + `environment: pypi`, never on the action ref form. |

Also exact-pinned `twine==6.*`→`6.2.0` and `tomli==2.*`→`2.4.1` on release.yml:44 (issue-requested S8544 hardening; behavior-identical — those are the latest releases satisfying the prior `6.*`/`2.*` constraints today).

**`release-readiness.yml` (11 open findings; 6 fixed, 5 adjudicated in E2):**

| Line | Rule | Fix |
|---|---|---|
| 38 | S8233 | Removed workflow-level `pull-requests: write`; relocated to job scope — `check-readiness` keeps `contents: read` + `pull-requests: write` (retained for the PR-facing readiness-report surface), `cutover-guard` gets `contents: read`. |
| 59 | S8544 + S8541 | `pip install pyyaml` → `pip install pyyaml==6.0.3 --only-binary=:all:`. |
| 64 | S7637 | `dorny/paths-filter@v4` → `@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d # v4.0.3`. |
| 86, 87, 89 | S7630 | The three `${{ inputs.tag }}` interpolations in the Validate step's `run:` body were moved to a step-level `env: TAG: ${{ inputs.tag }}` binding; the script now reads `"$TAG"`. Removes the script-injection surface; behavior-identical. |
| 198 | S7637 | `astral-sh/setup-uv@v8.1.0` → `@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0`. |

**`ci-nightly.yml` (6 open findings; the frozen-lock half fixed, self-install half adjudicated in E2):**
Actions were already SHA-pinned (no S7637) and the top-level `permissions: contents: read` needs no relocation (S8233 flags only write scopes). The real gap was the three `uv run pytest` calls omitting `--frozen`; lines 97, 105, 154 gained `--frozen`, closing the S8544 drift finding on each and bringing them in line with the adjudicated-safe A2 pattern (frozen no-op resync + test invocation, preceded in-step by `uv sync --frozen --all-extras`).

### E2 — Residual won't-fix (extends A1/A2/A4)

These remain open by design after E1 — the same first-party self-install / lock-export rationale as A1/A2/A4:

- **`release-readiness.yml:58` S8544** — `python -m pip install --upgrade pip`. Runner's own `pip` upgrading itself before the pinned `pyyaml` install; no meaningful lock surface. Same rationale as **A4** (pinning the bootstrap `pip`/`pipx` buys no security benefit and risks drift from the runner image's bundled Python). **Won't Fix.**
- **`release-readiness.yml:202` S8544** — `uv export --frozen --no-dev --no-hashes ... --output-file .cutover-requirements.lock.txt`. Versions are locked (`--frozen` against `uv.lock`), so the resolved set is deterministic. Honest caveat carried forward from Section D: `--no-hashes` drops the sha256 pins that A1 relies on for its integrity claim, so this is a **weaker** guarantee than A1, not equivalent. A candidate future hardening (out of this behavior-identical mission's scope) is to drop `--no-hashes` and install with `pip --require-hashes`; the structural test `test_release_readiness_cutover_guard_uses_public_lock_dependencies` pins the `uv export --frozen --no-dev` shape, so any such change must update that test. **Won't Fix (with noted caveat).**
- **`release-readiness.yml:206` S8544** — `python -m pip install -r .cutover-requirements.lock.txt`. Installs the frozen-exported, version-pinned lock file produced on line 202; no unpinned resolution. **Won't Fix** (inherits the :202 caveat).
- **`ci-nightly.yml:90` S8541** — `uv sync --frozen --all-extras` (self-install). Same as **A1**: `spec-kitty-cli` is a hatchling-built first-party package; `--no-build`/`--only-binary :all:` would refuse to build the very package under test and break the job. **Won't Fix.**
- **`ci-nightly.yml:97,105,154` S8541** — after E1 these are `uv run --frozen pytest -m ...`. The `--no-build`/`--only-binary` half (S8541) remains and is the same **A2** no-op-frozen-resync-plus-invocation pattern: nothing new is built or resolved beyond the A1-covered self-install in the preceding `uv sync --frozen` step. **Won't Fix.**

> Note: after E1 adds `--frozen` to `release.yml:42`, a subsequent SonarCloud re-scan may raise a
> **new** S8541 (`--no-build`) on that now-frozen `uv sync` — the same A1 first-party hatchling
> self-install pattern. If it appears, it is **Won't Fix** on the A1 rationale.

### E3 — Follow-up noted (not ticketed; PR body)

The five `# vX.Y.Z`-commented SHA pins are now immutable — a supply-chain win, but a future
critical patch on any pinned action is frozen out until the SHA is bumped. Recommend a
`github-actions` Dependabot/Renovate config so those pins receive automated bump PRs. Out of this
mission's three-file scope; carried in the PR body rather than ticketed.

