# Discovery: the real-home guard on a shared host (#7026)

Mission: `acceptance-real-home-shared-host-01M6EJXK`. Findings gathered before the spec was
authored; the spec (`spec.md`) is authoritative for requirements.

## Evidence gathered

### The guard as it stands on `main`

`acceptance-jvm/src/test/java/kitty/acceptance/environment/ScenarioLifecycle.java` fingerprints
`Path.of(System.getProperty("user.home"), ".spec-kitty")` in a field initializer (so *before* the
scenario runs) and compares it in `assertObservedWriteInsideTempDir()`, the After hook. The
fingerprint is `files=<n>,newestMtime=<ms>,bytes=<n>` (or `absent`), computed by one `Files.walk`,
skipping files whose *name* ends in `.lock`. Any difference fails the scenario with
`The scenario changed the real <root> (before: ..., after: ...)`.

### Reproduction (current `main`, commit `9aed3a8012`)

Host with concurrent Missions. Entry point as documented (`gradle -p acceptance-jvm test --no-daemon`,
ad-hoc pass, 4 scenarios in parallel). Result: 13 of 14 executed scenarios failed, every one at
`ScenarioLifecycle.java:62`, e.g.

```
A project can start from a small curated baseline instead of everything
The scenario changed the real /home/<host>/.spec-kitty
 (before: files=1332,newestMtime=1793638337018,bytes=59194202,
  after:  files=1333,newestMtime=1793638358346,bytes=59251247)
```

Files that appeared in the real `~/.spec-kitty` during the windows were all under
`spec-kitty-prompts/<16-hex>/` — one per concurrent Mission's repo identity — never elsewhere. The
live tree on that host held 1330 files, 128 of them prompt-namespace directories, which is why the
failure is near-total in that environment. The issue's own report (run 1 and run 2 of
`tests/scenarios/status/event-traceability.feature`, from the #6260 binding mission) shows the same
single-file shape.

### Who writes the runtime state root

- `src/runtime/next/_tmp_namespace.py` — the single owner of `spec-kitty-prompts`: the leaf is
  `sha256(resolved repo path)[:16]`, so each checkout (each Mission, each lane worktree) has its own
  directory, and the session reaper sweeps it. Cross-mission collisions are impossible by
  construction.
- `src/specify_cli/review/pre_review_gate.py` — `gate-locks/<name>.lock`; the existing `.lock`
  suffix exclusion already covers those files, but the directory is the second racy surface named
  by the issue.
- `src/specify_cli/tracker/credentials.py` — `~/.spec-kitty/credentials`; per-user, holds secrets.
  A concurrent write there is *not* a per-mission content-addressed write, so it stays visible to
  the guard (C-002 in the spec).
- `kernel.paths.get_runtime_state_root` / `ensure_runtime_state_root` — resolves `SPEC_KITTY_HOME`
  else `~/.spec-kitty` (else `%LOCALAPPDATA%\spec-kitty` on Windows), which is why the guard reads
  `user.home` directly rather than the environment: it deliberately looks at the un-redirected root.

### Comparison with the shared-machine table in the operating brief

The brief names `~/.spec-kitty/spec-kitty-prompts/` and `~/.spec-kitty/gate-locks/` as *safe to
race* (per-mission, content-addressed / lock-scoped) while the installed CLI's global asset cache is
not. The narrowing therefore follows an already-recorded boundary rather than inventing one.

## Decisions

1. **Narrow by subtree, not by filename or time window.** A time-window heuristic ("ignore writes in
   the last N seconds") would excuse a real leak that lands late; `spec-kitty-prompts/` and
   `gate-locks/` are the two surfaces a *concurrent* Mission can legitimately own, and each is
   structurally per-mission. Filename matching (`spec-kitty-*.md`) would be fragile: it depends on
   prompt-naming and would silently stop excluding if a writer renames.
2. **Opt-in, not default.** The strict whole-tree comparison stays the default so a single-writer
   machine and CI keep today's force; the shared-host scope is selected by
   `SPEC_KITTY_ACCEPTANCE_SHARED_HOST` (truthy: `1`, `true`, `yes`, `on`).
3. **The switch is ignored on a CI runner.** When `GITHUB_ACTIONS` is truthy the guard runs strict
   regardless of the switch. This is the anti-drift measure: a flag exported into a workflow, or
   inherited from a developer's shell that some day defines it, cannot weaken the nightly gate.
4. **Non-vacuity is proved at runtime, in every scenario.** Rather than relying on a JVM unit-test
   harness that this subproject does not have (no JUnit Jupiter engine on the classpath; the
   `test` task is Cucumber-only and the suite is nightly-only), the guard carries its own negative
   control: it builds a synthetic tree under the scenario's temp root and asserts that (a) a planted
   file *outside* the excused subtrees changes the fingerprint in both scopes, (b) a planted file
   *inside* `spec-kitty-prompts/` changes it in strict scope and does not in shared-host scope. If
   any of those four expectations fails, the scenario fails with an error naming the vacuous
   expectation. This runs on every nightly leg on all three OSes, which a unit test in this
   subproject would not (there is no per-PR JVM lane).
5. **The failure message names the scope.** `scope=strict` / `scope=shared-host` is appended to the
   existing `before: ..., after: ...` message so a reader can tell a genuine leak from a mis-scoped
   run without opening the harness.
6. **Docs and changelog ride along.** The how-to page that already documents the isolation guard
   (`docs/development/testing/acceptance-scenarios.md`) gains the switch and the CI refusal; the
   changelog entry is a `.internal.md` fragment because this is developer tooling, not user-visible
   CLI behaviour.

## Rejected alternatives

- **Skip the guard when the machine looks busy** (e.g. `loadavg`, or "more than one prompt-namespace
  directory exists"). Auto-detection would make the guard's strength depend on ambient state that no
  test pins, and a genuinely single-writer machine that once ran a second Mission would silently
  relax forever.
- **Fingerprint only a named allowlist of "important" surfaces** (registry, config, credentials).
  That is a bigger behavioural change: it would stop noticing a leak that creates a *new* top-level
  entry, which is precisely what a redirection bug looks like. Subtracting two named subtrees keeps
  the guard's whole-tree reach.
- **Add a `junit-jupiter` dependency and unit-test the policy.** It needs a Gradle
  `verification-metadata.xml` regeneration and a new per-PR lane to have any effect, and it would
  not run where the guard actually runs (nightly, three OSes). The runtime negative control covers
  the same expectation at the point of use; see decision 4.

## Open questions

- Should `credentials` eventually get its own fingerprint slot (content hash) so that a concurrent
  credential refresh does not trip the guard without excusing a leak? Out of scope here (C-002);
  noted for a follow-up if a shared host ever reports it.
