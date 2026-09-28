# JavaScript/TypeScript Supply-Chain Install Safety

Ecosystem-specific mechanics for the `supply-chain-install-safety` tactic's
checklist in an npm/pnpm/yarn project. The tactic states the
ecosystem-neutral checklist shape and evidence contract (registry
authenticity, freshness, install-time hook scripts, lockfile-driven
reproducibility, incident/IoC posture); this guide gives the exact commands
and file names for the JavaScript/TypeScript stack, plus the Node Active LTS
runtime-baseline check.

## Registry authenticity

Confirm the resolved package and version come from the approved official
registry (`registry.npmjs.org`, or an organization's approved private
registry/proxy) and not an unexpected mirror or namespace.

```bash
npm view <package> dist.tarball   # confirm the resolved tarball host
npm config get registry           # confirm the configured registry matches policy
```

## Freshness

Surface first-publish and latest-publish/update timestamps before accepting
a version.

```bash
npm view <package>@<version> time
npm view <package> time.modified
```

## Deny-by-default lifecycle scripts

`preinstall`/`install`/`postinstall` scripts are deny-by-default. Do not
globally disable script safety to unblock one dependency — that silently
re-enables automatic script execution for every dependency, not just the one
that needed it.

```bash
npm ci --ignore-scripts && npm run build        # verify the build still succeeds without scripts
pnpm install --ignore-scripts                   # skip dependency install scripts for this install
```

A pnpm config setting that toggles the project's own `pnpm run <script>`
pre/post hooks is NOT the deny-by-default control here — that governs the
project's own scripts, not the install-time lifecycle scripts of
dependencies. For dependency install scripts, use `--ignore-scripts` per
install, or scope an explicit allowlist in `pnpm-workspace.yaml`:

```yaml
# pnpm-workspace.yaml
onlyBuiltDependencies:
  - some-native-module   # explicit, scoped allowlist entry
```

For Yarn Berry (2+), disable dependency scripts globally and allowlist
per-package instead:

```yaml
# .yarnrc.yml
enableScripts: false
```

When a lifecycle script is genuinely required (a native module build), add
an explicit, scoped allowlist entry with the justification documented
alongside the change, rather than re-enabling scripts globally.

## Lockfile-driven reproducible installs

Commit and rely on the ecosystem lockfile — `package-lock.json`,
`yarn.lock`, or `pnpm-lock.yaml` — for a reproducible install, and use the
frozen/CI install mode in automation so an unreviewed dependency-tree change
cannot silently slip into a build.

```bash
npm ci                            # frozen install from package-lock.json, fails on drift
pnpm install --frozen-lockfile
yarn install --frozen-lockfile    # Yarn classic (1.x)
yarn install --immutable          # Yarn Berry (2+) — --frozen-lockfile is classic-only
```

Review lockfile diffs the same way manifest diffs are reviewed — a
lockfile-only change can still introduce a new transitive dependency or
resolve to a different version.

## Node Active LTS runtime baseline

Check the project's declared/runtime Node version against the current
Active LTS line. If the project intentionally runs a non-LTS or outdated
Node version, document the business rationale explicitly rather than
leaving the skew unacknowledged.

```bash
node --version
cat .nvmrc   # or the "engines.node" field in package.json
```

## Incident/IoC posture

Watch for class-level indicators of compromise from installed packages:
unexpected network calls from install scripts, credential/token
exfiltration attempts, or self-propagating (worm-style) install behavior.
Cite the CAS/vendor incident feed consulted; do not hardcode a specific
incident package/version list here.
