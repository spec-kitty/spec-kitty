# Design decisions

- Preserve PRIMARY report placement across caller topologies.
- Reuse Git path-scoped canonical commit; no alternate commit-tree or hook policy.
- Fail closed on dirty material inputs and unsupported state. Post-commit races return explicit recovery outcomes; no automatic reset.
- Existing capacity exception allows branch reuse only; no fourth checkout. Immutable qualified runtime keeps sibling work independent of mutable source.
- Dependency closure conservatively covers declared project governance and resolved pack roots rather than guessing an incomplete per-file selection. Explicitly exclude runtime/status/cache outputs so context loading does not invalidate its own report. Mutable external roots without qualified cleanliness are refused. Legacy/default freshness remains compatible.
- Read-only Aletheia config inspection confirms a local charter pointer and no declared org pack. Its charter catalog references generated local library files; those declarations belong in the manifest. Actual dirty authority still refuses until its owner reconciles it.
- Qualification is local and explicit: report frontmatter binds a random transaction identifier; its Git-directory receipt starts pending before the report is written and becomes qualified only after parent/tree/input/index/working-byte verification. Freshness rejects missing/pending receipts and requires the verified commit remain reachable. This prevents retained reports from unlocking a mission after HEAD/index-only races or process interruption. A copied report requires fresh analysis/recording in its destination checkout; receipts are not portable attestations.
- The transaction detects cooperative-writer races rather than claiming a filesystem-wide lock. Failed transactions preserve all concurrent state and report the observed commit when HEAD advanced. No reset or rollback is authorized.
- Bundled authority is content-pinned without machine-local paths. Canonical selected-template resolution rejects mutable global templates; project overrides and org roots must be inside the repository and committed. Aletheia's selected global spec/plan templates matched the bundled defaults byte-for-byte; hashes and supported mission-scoped override paths were sent to the owner for reconciliation, with no Aletheia mutation by this work package.

## Implementation log

### User experience findings

- Missing qualification receipts deliberately fail closed after copying an opt-in report to another clone. The command documents rerunning analysis/recording; no silent portable-success claim.
- Task directories can contain ordinary README files; only WP definition frontmatter receives runtime-field normalization.
- `agent action implement` lacks `--owned-checkout`; supported `next` plus `agent tasks move-task --owned-checkout` claimed this work package. The command shown in the initial task text was not accepted by the CLI.
- CI runs exposed shared per-worker global-template contamination in the new recorder fixtures. Each recorder fixture now isolates canonical template resolution to its own home; the explicit external-global refusal case still overrides that home and verifies refusal followed by committed project overrides.
- The deliberate `--report-only` addition also requires updating the frozen CLI flag contract. Its default remains false and has an explicit contract assertion; this is an intentional opt-in interface extension.
- Architecture CI identified direct charter implementation imports, duplicated charter paths, and two obsolete formatter exclusions. The correction uses existing canonical facades/constants, adds an identity-preserving exception export, and removes the obsolete exclusions without widening an allowlist.

### Known limitations

- Arbitrary external editors are not fenced; all pre/post race checks and failure outcomes are explicit.
- External mutable org/global authority is unsupported by this project-only transaction.
- Independent implementation review cleared the transaction at `5b8fc7dad` except its missing unchanged outcome. The root agent independently cleared that correction at `f5c35e71a`; repeated qualified analysis preserves report bytes, HEAD and unrelated staging. Canonical acceptance was recorded at `8dbc84f76` and source published as PR5017; updated CI remains pending. No Aletheia write by this agent, HA readiness, merge or deployment is implied.
- A real temporary-repository compatibility probe proved that lifecycle runtime `6d682dce3` accepts a retained new-format report without a qualification receipt, whereas the new reader rejects it. Therefore deployment requires one combined qualified runtime containing PR5009 lifecycle fixes and this complete recorder reader/writer; command-specific old/new runtime splitting is insufficient.

### Validation evidence

- Owning Git/recorder/report suites: 203 passed, 2 skipped. Additional malformed/external authority tests: 11 passed.
- Final CLI negative controls and unchanged semantics: 26 passed. Canonical commit/sole-resolver architecture checks: 22 passed.
- New-line diff coverage versus `18df07fc`: 92%; aggregate touched-module coverage: 93%.
- Configured strict mypy, scoped to all four touched source modules with `--follow-imports=skip`: zero issues. Ruff lint/diff checks pass; whole-tree format check reports 2,289 files already formatted.
- Required fast baseline: 2,043 passed, 5 skipped, 4 known baseline failures (retired cache path guard; three primary-only charter JSON tests under linked cwd). This is not full-green. Log: task-local `/tmp/spec-kitty-recorder-test-fast.log`.
- Read-only Aletheia closure after owner template pin `20af78ee`: 479 entries, no dirty or untracked material inputs. No Aletheia report command has been run by this agent.
- Separate integration source `4483ed812` preserves reviewed PR5009 lifecycle code and recorder implementation. Owned lifecycle/recorder qualification passed 136 tests; final recorder and corrected gate cases passed 30 tests. Independent review cleared the composition and controls. A separately installed, isolated wheel passed seven real-Git writer/gate checks outside the source checkout; eleven critical module hashes matched source. Qualification does not constitute an upstream release. Exact provenance is retained in the task-owned `spec-kitty-composite-4483ed812/qualification.json` runtime artifact.
- Architecture correction `529e18732`, independently reviewed, passes 263 focused architecture, authority, and recorder tests; one expected legacy-key warning remains. Strict mypy over five owning modules and scoped Ruff lint pass. The prior remote head's module, CLI, documentation, and quality gates passed; its architecture failure and downstream router failure are addressed by this correction and require fresh CI.
