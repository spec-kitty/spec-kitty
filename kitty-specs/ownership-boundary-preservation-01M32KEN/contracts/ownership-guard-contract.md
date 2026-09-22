# Contract: Asset-Preservation Guard + Non-Vacuous Gate

The executable contract the ATDD tests pin. Two surfaces: the runtime guard
(`specify_cli.asset_preservation`), and the arch gate.

## C1 — Guard decision surface (`specify_cli.asset_preservation`)

```
guard_destructive_removal(
    path: Path,
    project_path: Path,
    *,
    prover: OwnershipProver,     # ManifestProver | ManagedPathProver | CanonicalContentProver | AnyProver([...])
    is_tree: bool = False,       # rmtree vs unlink for the removal the guard performs on `owned`
    backup_parent: Path | None = None,
    dry_run: bool = False,
) -> OwnershipVerdict
```

**Invariants:**

0. **The guard performs the removal; the site does not.** On `owned`, the guard executes the removal itself (`shutil.rmtree` when `is_tree`, else `unlink`); the raw destructive literal lives ONLY inside the guard (the chokepoint) and inside genuinely-safe allowlisted ops. A routed site replaces its raw `rmtree`/`unlink` with a `guard_destructive_removal(...)` call and carries no raw destructive literal — this is what makes the WP09 census non-vacuous by construction (post-tasks review; mirrors `git/destructive_guard.py::guarded_worktree_remove`). A caller-deletes design is rejected.
1. **No delete without proof.** If `prover.prove(path, project_path)` returns `None`, the guard MUST NOT delete/rename/overwrite `path`; it preserves in place (parent survives) or archives verbatim (parent being removed) and returns `owned=False`.
2. **Proof is content-based, never name-based.** `owned=True` requires a concrete `OwnershipProof` (manifest entry + matching `content_hash` + copy delivery; OR a package-managed/regenerable contract; OR a version-marker/canonical-byte match). Basename/dirname equality alone never yields `owned=True`.
3. **Fail closed.** Any prover exception, unreadable/corrupt manifest, symlink target, or mixed (tracked+untracked) directory ⇒ `owned=False` (preserve).
4. **Byte-exactness on archive.** An archived file is byte-identical (mode + mtime preserved where the platform allows). **`backup_parent` is mandatory when the caller is about to remove the path's parent** — it must resolve outside the doomed tree so the backup survives the caller's `rmtree`.
5. **Copy-only archive core.** The extracted verbatim writer copies; it does NOT unlink the original (in-place preserve must not delete; parent-removal deletes via the caller's own `rmtree`). The `skills.installer` wrapper delegates to this one core (single authority).
6. **Success-preserving.** Preservation returns a verdict the caller renders as a warning; it never forces a non-zero exit (FR-008).
7. **Diagnostic completeness.** A preserving verdict names the path, the reason, and the backup location when archived (FR-009).
8. **Idempotent.** A second run over an already-preserved/already-owned tree produces the same verdict and no additional mutation.

**Prover composition.** `AnyProver([p1, p2, …]).prove` returns the first non-`None` proof, so
dual-signal sites express their fallback as guard-owned data, not call-site branching.
`CanonicalContentProver` receives the version marker (`<!-- spec-kitty-command-version:` — the one
command marker syntax, used in `.md` and inside `.toml` prompt bodies alike) and any canonical
bytes as constructor DATA and proves through one code path. For `.toml` the marker can sit past a
15-line head, so scan the whole file or prefer the manifest.
`ManifestProver` checks both the managed-skills and command-skills manifests (their entry shapes
and hash formats differ).

## C2 — Per-site routing contract

Each routed site selects the prover matching its signal (`AnyProver` when two apply), calls
`guard_destructive_removal(...)`, deletes/prunes only on `verdict.owned`, appends
`verdict.diagnostic` on preservation, and carries an in-code comment documenting its ownership
proof (charter L479 / NFR-006).

## C3 — Non-vacuous gate invariant (`tests/architectural/test_mutation_ownership_routing.py`)

1. **Census (live, AST).** Every `shutil.rmtree` / `Path.unlink` / `os.unlink` / `os.remove` / `shutil.move` / `Path.rmdir` / `_safe_rmtree` / `_safe_unlink` call in `cli/commands/init.py` + `upgrade/migrations/*.py` is discovered by walking the AST (resolving module-level string-constant path indirections). Shared plumbing is extracted from the existing `test_destructive_op_routing.py` and reused (single authority).
2. **Op-vocabulary exhaustiveness self-test.** Assert the scanned attribute set covers every `shutil`/`os`/`pathlib` destructive method present in the module set, so a future `os.remove`/`rmdir` cannot silently evade the census.
3. **Routed sites are literal-free (guard performs the delete).** Every discovered raw destructive literal is EITHER inside `asset_preservation`'s own guard implementation (the chokepoint) OR a member of the frozen, individually-rationalized, shrink-only allowlist (safe ops + the `rmdir` empty-only category). A routed site has no raw literal at all. A NEW raw destructive literal at any migration/init site is neither ⇒ it FAILS the gate by construction.
4. **Positive routing — pinned + completeness-checked.** Assert each routed fix-site module both (a) calls into `asset_preservation` and (b) carries no raw destructive literal. The required routed-module set is PINNED to the WP02–WP08 `authoritative_surface` set (init.py + the nine migration modules, +`m_unify` iff B4 routed) and the assertion is completeness-checked, so dropping a module from the set fails the gate — the gate cannot be greened by omitting a module and allowlisting its target op. WP09 must reject any un-rationalized user-content op rather than absorbing a still-raw site (e.g. a leftover `m_0_10_0:229`) into the allowlist. Per-path guarantees (e.g. `command-templates` preserved while `templates`/`.scratch` are removed) are additionally carried by the C4 behavioural tests.
5. **Self-mutation, both directions.** A planted un-routed op is detected; dropping one real allowlist entry reproduces the exact gate failure. Shrink-only (a vanished site warns; growth fails — charter Burn-down Policy).

## C4 — Behavioural acceptance (per spec User Stories) — BOTH directions

For every routed manifest/canonical site, the ATDD suite pins BOTH directions, with honest RED/GREEN labels:
- **preserve** (RED-on-base → GREEN-on-fix) — an unmanifested/marker-less/byte-differing collision survives (in place or backup) + diagnostic. This is the C-011 repro.
- **owned-delete (GREEN-on-base → GREEN-on-fix non-vacuity anchor)** — a genuinely package-owned target (manifest entry with `content_hash == sha256(current bytes)` + `copy` delivery on disk, or a marker-bearing/canonical-matching file) IS removed + its entry pruned. On base the buggy code already deletes it by name, so this test is green-on-base; it exists to stop a preserve-everything guard passing, NOT as a RED repro. Do not hunt for a RED-on-base owned-delete.

Site specifics:
- US1 (#4859): flip `test_apply_removes_retired_skill_surface_from_all_known_project_roots` to preserve-direction AND add the NEW manifest-owned-delete test (without it, a preserve-everything guard passes all #4859 acceptance). `test_apply_prunes_managed_and_command_manifests` stays green.
- US2 (#4861): **Case A (config.yaml ABSENT)** is the RED-on-base repro — init falls through to the `:1564` cleanup and `rmtree`s `command-templates`; after the fix it survives + exit 0. **Case B (config.yaml PRESENT)** is a GREEN-on-base wiring/invariant guard, NOT a RED repro: init's unconditional `Exit(0)` at `:900-928` means the delete site is never reached with config present, so the file survives trivially on base — the test asserts the invariant holds after the fix, it does not claim red-on-base. Never-seeded project still ends with no `command-templates/`; `templates`/`.scratch` still removed.
- US3 (#4862): the "Skipped" governance file survives; no-collision residual dir still removed.
- US4 (class): each routed retirement migration preserves an unprovable collision AND still removes a proven-owned target. For the script sites (`m_0_10_0`), "owned-delete" is N/A (no signal) → the migration is preserve-all; its expectations are rewritten accordingly and a red-first test asserts a user `.sh`/`.ps1` survives.
- All: the **preserve** direction is RED on base `32cfc272ee` and GREEN on the site's final commit (C-001 ATDD); owned-delete and config-present-invariant tests are green-on-base anchors. Capture the actual RED-on-base run output per DIRECTIVE_030.
