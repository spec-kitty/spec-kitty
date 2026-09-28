# Python Supply-Chain Install Safety

Ecosystem-specific mechanics for the `supply-chain-install-safety` tactic's
checklist in a pip/uv/poetry project. The tactic states the ecosystem-neutral
checklist shape and evidence contract (registry authenticity, freshness,
install-time hook scripts, lockfile-driven reproducibility, incident/IoC
posture); this guide gives the exact commands and file names for the Python
stack.

## Registry authenticity and index pinning

Confirm the resolved package and version come from the approved official
index (PyPI, or an organization's approved private index/proxy) and not an
unexpected mirror. Pin the index explicitly rather than letting resolution
fall through to an unreviewed default.

```bash
pip config list                          # confirm the configured index-url matches policy
pip download --no-deps -v <package>       # verbose output shows the URL actually used to resolve
```

The main hazard for index pinning is dependency confusion through
`--extra-index-url` or multiple configured indexes: a private package name
can resolve from a public index instead of your organization's private one.
Avoid `--extra-index-url` for private package names. With uv, scope a
private index to only the packages it should serve:

```toml
# pyproject.toml
[[tool.uv.index]]
name = "internal"
url = "https://pkg.internal.example.com/simple"
explicit = true   # only packages that opt in via [tool.uv.sources] resolve here
```

Keep uv's default `first-index` resolution strategy (the first index that
has the package wins) rather than switching to a strategy that searches
every configured index for the best match, which reopens the same
dependency-confusion window `explicit = true` closes.

## Freshness

Surface first-publish and latest-publish/update timestamps before accepting
a version.

```bash
curl -s https://pypi.org/pypi/<package>/json | jq '.releases["<version>"][0].upload_time'
```

## Install-time hook scripts

Most pure-Python wheels have no install-time hook script surface, but a
package with a native/source build (`setup.py`) can run arbitrary code at
build time. Treat a package that requires a source build over a prebuilt
wheel as elevated risk and confirm the build step is expected before
accepting it.

```bash
pip install --only-binary=:all: <package>   # refuse a source build entirely
```

## Lockfile-driven reproducible installs

Commit and rely on the ecosystem lockfile — `uv.lock` or `poetry.lock` — for
a reproducible install, and use the CI/drift-gate install mode in automation
so an unreviewed dependency-tree change cannot silently slip into a build.

```bash
uv sync --locked                      # fails the build if uv.lock is out of date with pyproject.toml
uv lock --check                       # check-only: fails if uv.lock is out of date, without installing
uv lock                               # separate developer step: refreshes uv.lock — do not run before the gate above
uv sync --frozen                      # installs from uv.lock as-is, WITHOUT checking staleness — not a drift gate
poetry check --lock                   # check-only: fails if poetry.lock is out of date, without rewriting it
poetry sync                           # `poetry install --sync` is deprecated in Poetry 2; `poetry sync` replaces it
pip install --require-hashes -r requirements.txt
```

Use `uv sync --locked` (or `uv lock --check`) alone as the CI drift gate —
these are the modes that fail when the lockfile does not match
`pyproject.toml`. Do **not** chain `uv lock` immediately before `uv sync --locked` in the
same gate step (`uv lock`, then `&&`, then `uv sync --locked`): `uv lock`
rewrites a stale lock in place first, so the `--locked` check that runs
after it always passes even when the lock was stale — it defeats the
check it is meant to run. Keep `uv lock` as a separate developer step
that refreshes the lock, run outside the gate.
The same applies to Poetry: `poetry lock` rewrites the lock, so
`poetry lock && poetry sync` is not a gate either — use `poetry check
--lock` for the check, and keep `poetry lock` as the separate refresh
step. `--frozen`
(uv) installs exactly what is already in `uv.lock` without checking
whether that lock is current; it is useful for "install exactly the
lock, fast" but does not catch drift.

Review lockfile diffs the same way manifest diffs are reviewed — a
lockfile-only change can still introduce a new transitive dependency or
resolve to a different version.

## Hash pinning

Hashes make an install fail closed if a resolved artifact's bytes do not
match what was locked, defending against a compromised or substituted
package even when the version number is correct. `uv.lock` and
`poetry.lock` already record hashes for every resolved package as part of
normal locking — no extra step is needed there. For a plain
`requirements.txt` workflow, generate hashes explicitly and enforce them on
install:

```bash
uv pip compile requirements.in --generate-hashes -o requirements.txt
# or: pip-compile --generate-hashes requirements.in
pip install --require-hashes -r requirements.txt
```

`pip install --require-hashes` refuses to install any requirement that
lacks a hash, so a requirements file must have every dependency pinned with
hashes, not just the top-level ones.

## Incident/IoC posture

Watch for class-level indicators of compromise from installed packages:
unexpected network calls from a build step, credential/token exfiltration
attempts, or self-propagating (worm-style) install behavior. Cite the
CAS/vendor incident feed consulted; do not hardcode a specific incident
package/version list here.
