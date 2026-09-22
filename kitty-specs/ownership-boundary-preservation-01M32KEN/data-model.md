# Phase 1 Data Model & Design: Ownership-Boundary Preservation

> Post-plan squad folded (feasibility / decomposition / ATDD lenses). Guard package renamed
> `asset_preservation` (avoids the double "ownership" token vs `specify_cli/ownership/` and the
> "guard" token vs `git/destructive_guard.py`).

## Guard model (`src/specify_cli/asset_preservation/`)

### Value types

- **`OwnershipProof`** (REUSED — `specify_cli.tool_surface.operations`): `kind ∈ {manifest, managed_path, canonical_content}` + `reference: str`. The per-signal vocabulary; not re-declared.
- **`OwnershipVerdict`** (NEW, frozen): `owned: bool`, `proof: OwnershipProof | None`, `preserved_path: Path | None`, `backup_path: Path | None`, `reason: str`, `diagnostic: str`.

### Provers — a protocol with composition (resolves the dual-prover + fallback gaps)

```
class OwnershipProver(Protocol):
    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None: ...
```

- **`ManifestProver`** — signal `manifest`. **Two internal predicates** (the two manifest shapes are structurally different, confirmed by the feasibility lens):
  - *managed skills*: reuse `skills.installer._replacement_is_owned` (`ManagedSkillManifest`; `content_hash == "sha256:"+sha256(bytes)`, `delivery_mode == "copy"`, path derivation).
  - *command skills*: NEW predicate mirroring `manifest_store.fingerprint_file(path) == entry.content_hash` (bare 64-hex; `ManifestEntry` has `path`/`content_hash`/`agents` only — no `delivery_mode`/`installed_path`).
  - A directory is owned only if every tracked member matches and there are no untracked members.
- **`ManagedPathProver`** — signal `managed_path`. Constructed with an explicit package-managed / regenerable-this-run contract (path list + run-scope set). Owned iff the path is a package-managed regenerable location (e.g. `.kittify/templates/`, `.scratch`, `.resolved-*`) or was created by this run. The LEGACY tier `.kittify/command-templates/` is operator-authorable ⇒ never owned-by-name.
- **`CanonicalContentProver`** — signal `canonical_content`. **Canonical-source and marker-format are injected as DATA at construction, not branched at `prove()` time** (decomposition lens — otherwise the whack-a-mole moves into `provers.py`):
  - `marker`: the version marker `<!-- spec-kitty-command-version:` — the ONLY command marker syntax (verified: `template/asset_generator.py` injects it as an HTML comment into `.md` files AND into `.toml` prompt bodies inside `prompt = """…"""`; there is no `# …` command marker). Scan a configurable window; for `.toml` the marker sits inside the prompt string and may be past a 15-line head, so scan the whole file (or prefer the manifest — see WP06).
  - `canonical_bytes`: optional shipped-canonical bytes/digest to byte-match (`m_2_0_7._matches_package_default` model).
  - Owned iff the file carries the version marker OR byte-matches a supplied canonical. **No marker + no canonical ⇒ `None` (unprovable ⇒ preserve).**
- **`AnyProver([p1, p2, …])`** — NEW ordered composite. Returns the first non-`None` proof; used by dual-signal sites (#4 `manifest`→`canonical_content`, #9 `canonical_content`→`managed_path`) so the fallback is guard-owned data, not call-site branching.

Fail-closed: any prover error, unreadable/corrupt manifest, symlink, or mixed (tracked+untracked) directory ⇒ **unprovable** ⇒ preserve.

### Decision surface + backup

```
guard_destructive_removal(path, project_path, *, prover, is_tree=False, backup_parent=None, dry_run=False) -> OwnershipVerdict
```

`is_tree` selects the removal the guard performs on `owned` (`shutil.rmtree` vs `unlink`). A site
that must remove a now-empty/package-only directory after preserving user members uses either a
guard call with a proving `ManagedPathProver` or the allowlisted empty-only `rmdir` category —
never a fresh raw `rmtree` literal at the site.

- Runs `prover.prove`. **owned** ⇒ the guard **PERFORMS the removal itself** (`rmtree` when `is_tree`, else `unlink`) and returns `owned=True`; the caller then prunes manifest entries as before. **unprovable** ⇒ preserve in place when the parent survives, else archive verbatim, and return `owned=False` + diagnostic (no removal).
- **The guard performs the delete (chokepoint), it does not defer to the caller.** This is deliberate and load-bearing for the gate's non-vacuity (post-tasks review): a routed site replaces its raw `shutil.rmtree`/`unlink` with a `guard_destructive_removal(...)` call and therefore carries **NO raw destructive literal** — exactly like `git/destructive_guard.py::guarded_worktree_remove`. The ONLY raw `rmtree`/`unlink` literals that remain are (a) inside the guard's own implementation (allowlisted as the chokepoint, like `destructive_guard.py:229`) and (b) genuinely-safe allowlisted ops. A caller-deletes design would leave the literal at every routed site, collapsing "routed" and "un-routed" into one indistinguishable census bucket and making the gate fakeable — so it is rejected.
- **`backup_parent` is mandatory for archive-when-parent-removed sites** (#4859 dir removal, #4862 `rmtree(constitution_dir)`): it must point outside the doomed tree (e.g. `.kittify/.backup-<ts>/`) so the backup survives the caller's `rmtree` (feasibility lens; `back_up_operator_subtrees` docstring).
- **`backup.py`** extracts a **copy-ONLY** verbatim writer (~13 lines: symlink-or-`O_EXCL` write + `chmod_fd` + `os.utime`, depending only on `FileState`/`chmod_fd`/stdlib) out of `skills.installer._archive_existing_path`; the **trailing `_safe_unlink(dest)` is excluded** (redundant when the parent is being removed; wrong for in-place preserve). The skills wrapper **delegates** to the extracted core (single authority — no duplicate). Dir-granular archiving reuses `template.manager.back_up_operator_subtrees` (+ `_allocate_backup_dir`).
- Layering: `asset_preservation` imports `kernel.atomic` (down) + reuses `template`/`skills`/`tool_surface`/`manifest_store` peers; nothing in `kernel`/`charter` imports it.

## Census: routed fix-list (SAME-ROOT) → prover

| # | Site | Prover | Note |
|---|------|--------|------|
| 1 | `cli/commands/init.py:1568` (#4861) | `ManagedPathProver` | **ONE** `rmtree` literal in a 3-name loop; the guard decides per name — preserve `command-templates` (operator tier), still delete `templates`/`.scratch` (managed). **Routed, NOT allowlisted.** |
| 2 | `m_0_10_0_python_only.py:175` (bash `*.sh`) | `CanonicalContentProver` → **preserve-all** | `.sh` carry no marker and the package no longer ships a canonical ⇒ prover returns `None` ⇒ preserve+warn. Migration expectations rewritten from "removed N" to "preserved M unprovable". |
| 3 | `m_0_10_0_python_only.py:187` (ps `*.ps1`) | `CanonicalContentProver` → **preserve-all** | same as #2 |
| 4 | `m_0_10_2_update_slash_commands.py:153` (`commands/*.toml`) | `AnyProver([ManifestProver(command), CanonicalContentProver(toml marker)])` | prove via command-skills manifest first; `#`-syntax marker fallback. |
| 5 | `m_2_0_11_remove_clarify_command.py:52` | `CanonicalContentProver` (both marker syntaxes) | broad `spec-kitty.clarify*`; confirm target files carry a marker, else reclassify to manifest. |
| 6 | `m_2_1_2_remove_release_skill.py:55` | `ManifestProver` | `.claude/skills/release` |
| 7 | `m_2_2_0_profile_context_deployment.py:61` | `CanonicalContentProver` | `spec-kitty.profile-context.md` (`<!-- -->` marker) |
| 8 | `m_3_2_0rc43_retire_profile_context_command.py:48` | `CanonicalContentProver` | `spec-kitty.profile-context.md` |
| 9 | `m_3_1_1_charter_rename.py:~196` (#4862) | `AnyProver([CanonicalContentProver, ManagedPathProver])` → effectively **preserve-always** | governance files carry no marker/canonical ⇒ preserve the "Skipped" file; empty residual dir still `rmtree`s fine. |
| 10 | `m_3_2_0rc45_retire_standalone_skill_surface.py:196 & :198` (#4859) | `ManifestProver` (managed **and** command manifests, per-path) | name-only retired-skill delete |

## Census: borderline (resolve by red-first probe → route or allowlist)

| B | Site | Resolution |
|---|------|-----------|
| B1 | `m_3_1_1:~148` rmtree `missions/<m>/constitution/`; `~161` unlink stale `memory/constitution.md` | route via `CanonicalContentProver`→preserve (governance). |
| B2 | `m_0_10_0:~250` rmtree `scripts/tasks/` | route → preserve-all (same as #2/#3). |
| B3 | `m_0_6_7:~119` rmtree incomplete `REQUIRED_MISSION` then `copytree` | **archive-then-recopy**: `copytree(dirs_exist_ok=False)` needs the dest absent, so preserve = archive user members OUT to `backup_parent`, THEN the legitimate `rmtree`+`copytree` proceeds. Red-first asserts the user member lands in the backup (in-place preserve is structurally impossible here). |
| B4 | `m_unify_charter_activation_finalize:~439` unlink compiled bundle | probe: if the bundle can diverge from `charter.yaml` → fold-then-delete/canonical check; else allowlist as compiled artifact. |

## Census: op vocabulary + SAFE allowlist

**Op vocabulary the gate scans** (live AST census confirms counts over `init.py` + `migrations/*.py`): `shutil.rmtree` (18), `Path.unlink` (34), `shutil.move` (10), `Path.rmdir` (10), `os.unlink`/`os.remove` (1), plus the `_safe_rmtree`/`_safe_unlink` wrappers. **`rmdir`/`os.rmdir` are a category-rationalized allowlist class**: they raise on a non-empty directory, so they cannot silently lose content (10 sites: `m_0_10_0:194/197/231`, `m_0_10_2:161`, `m_0_9_1:431`, `m_2_0_6:421`, `m_2_0_7:135/139`, `m_3_1_2:171`, `m_3_2_0rc35:234`).

**The allowlist is computed against the LIVE census in WP02** (line numbers below are illustrative and self-correct):

- **Ephemeral scratch/tmp**: `init.py` resolver-scratch removals, `m_3_2_8` tmp, `m_3_3_0` tmp.
- **Worktree teardown (`.worktrees/*`)**: `m_0_6_5`, `m_0_7_2`, `m_0_9_1`, `m_2_0_6`, `m_0_8_0_worktree_agents_symlink`, `m_0_10_8` (wt symlinks) — package-generated command dirs/symlinks only. **NOT `m_0_10_0:229`** (`_cleanup_worktree_bash_scripts` deletes `.worktrees/*/.kittify/scripts/bash/*.sh` — user-authorable scripts, same hazard class as `:175`; it is ROUTED in WP05, never allowlisted as teardown).
- **Broken-symlink / package-state markers**: `m_0_10_8` (memory/AGENTS symlinks), `m_0_8_0_remove_active_mission`, `init.py` pending-marker.
- **Relocation/rename (overwrite-guarded)**: `m_0_2_0`, `m_0_6_5`, `m_0_9_0` (source-after-move), `m_0_9_1` (source-after-move), `m_0_10_8`, `m_3_1_1` non-collision moves (`:172/188/205/219/322/347`).
- **`shutil.rmtree` lane-teardown (emptiness-checked in code)**: `m_0_9_0:272`, `m_0_9_1:324` — *these are `rmtree`, corrected from the earlier mislabel; kept as lane-teardown rationale, not "rmdir".*
- **`rmdir` category (empty-only, raises on non-empty)**: the 10 sites above.
- **Already ownership/content/backup-guarded (exemplars — do NOT change)**: `m_2_0_0:127`, `m_2_0_7:93`, `m_2_1_3:350`, `m_3_1_2:158`, `m_3_2_0rc35:208`, `init.py` `_discard_failed_project_scaffold` (routes `back_up_operator_subtrees`).
- **Non-user surface**: `m_3_3_0` machine `kitty-ops/*.jsonl`.
- **Wrapper primitives (decision at call site)**: `m_3_2_0rc45:31/34/38`.

## Non-vacuous gate (`tests/architectural/test_mutation_ownership_routing.py`)

- **Reuse, don't duplicate**: extract the shared AST census/allowlist/self-mutation plumbing (`_iter_py_files`, `_parse`, `_module_string_constants`, `_diff_against_allowlist`, planted-op + drop-one-entry self-mutation) from `tests/architectural/test_destructive_op_routing.py` into a common helper both gates consume (DIRECTIVE_044). The existing gate scans **git argv literals**; this new one scans **Python FS `ast.Call`s** — complementary, shared machinery.
- LIVE AST census over `cli/commands/init.py` + `upgrade/migrations/*.py` of the op vocabulary above. Because the guard **performs** the removal, a routed site carries **no raw `rmtree`/`unlink` literal** — so each discovered literal must be ∈ {inside `asset_preservation`'s own guard implementation — the chokepoint} ∪ {frozen rationalized allowlist (safe ops + the `rmdir` empty-only category)}. A NEW raw destructive literal at any migration/init site is neither — it FAILS the gate by construction (this is the non-vacuity the caller-deletes design could not deliver).
- **Op-vocabulary exhaustiveness self-test**: assert the scanned attr set covers every `shutil`/`os`/`pathlib` destructive method appearing in the module set (completeness control), so a future `os.remove` cannot evade the census.
- **Positive routing, pinned + completeness-checked**: assert each routed fix-site module calls into `asset_preservation` AND carries no raw destructive literal. The required routed-module set is **pinned** to the WP02–WP08 `authoritative_surface` set — `cli/commands/init.py`, `m_3_2_0rc45_retire_standalone_skill_surface.py`, `m_3_1_1_charter_rename.py`, `m_0_10_0_python_only.py`, `m_0_10_2_update_slash_commands.py`, `m_2_0_11_remove_clarify_command.py`, `m_2_1_2_remove_release_skill.py`, `m_2_2_0_profile_context_deployment.py`, `m_3_2_0rc43_retire_profile_context_command.py`, `m_0_6_7_ensure_missions.py` (+ `m_unify_charter_activation_finalize.py` iff B4 routed) — and the assertion is **completeness-checked** (a module silently dropped from that set fails the gate), so an implementer cannot green the gate by omitting a module and allowlisting its target op.
- **Self-mutation both directions**: planted un-routed op ⇒ detected; drop one allowlist entry ⇒ reproduces the gate failure. **Shrink-only**, baseline-governed (charter Burn-down Policy). WP09 must **reject any un-rationalized user-content op** rather than silently absorbing a still-raw site (e.g. a leftover `m_0_10_0:229`) into the allowlist.

## Non-vacuity of the runtime guard (owned=True must not be vacuous)

The arch gate proves *routing*, never that the guard *deletes when it should*. Therefore the ATDD
suites MUST include, per manifest/canonical site, a **positive owned-DELETE** test: a genuinely
package-owned target (manifest entry with `content_hash == sha256(current bytes)` + `copy`
delivery on disk, or a marker-bearing/canonical-matching file) IS removed + its entry pruned.
For #4859 this is a NEW test paired with the flipped bug-locking test — without it a
preserve-everything guard would pass all #4859 acceptance.

**ATDD labelling (honest RED/GREEN, DIRECTIVE_041).** On the base commit the buggy code deletes
targets *by name unconditionally*, so a genuinely-owned target is ALSO deleted on base — the
owned-delete test is therefore a **GREEN-on-base → GREEN-on-fix non-vacuity anchor**, NOT a
RED-on-base repro. The **preserve** direction (unprovable collision survives) is the
**RED-on-base → GREEN-on-fix** repro that carries the C-011 evidence. WP prompts must label the
two directions accordingly and not have an implementer hunt for a RED-on-base owned-delete that
cannot exist.

## Entities recap

`OwnershipProof` (reused vocabulary) · `OwnershipVerdict` (guard output) · `OwnershipProver` protocol (`ManifestProver` [2 predicates] / `ManagedPathProver` / `CanonicalContentProver` [data-injected] / `AnyProver` composite) · Backup location (timestamped, parent-surviving) · Routed site vs. Allowlisted op (the gate's two buckets).
