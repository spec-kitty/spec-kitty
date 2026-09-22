# Quickstart: the ownership-mutation guard

Audience: a Spec Kitty maintainer adding or reviewing a mutating-flow cleanup.

## The rule (charter L463–479)

A mutating flow (`init`, `upgrade`, migrations) must NOT delete/rename/overwrite a path in a
user-visible command/skill/template/governance directory unless it can *prove* the package owns
that exact path. If it cannot prove ownership, it preserves the content and warns — it never
deletes-by-name.

## Adding a destructive cleanup step — do this

1. Pick the prover matching your ownership signal:
   - manifest-tracked skills/commands → `ManifestProver`
   - package-managed/regenerable-this-run path → `ManagedPathProver`
   - generated file with a version-marker / byte-matches the shipped canonical → `CanonicalContentProver`
2. Call the guard instead of a raw `rmtree`/`unlink`:

   ```python
   from specify_cli.asset_preservation import guard_destructive_removal, CanonicalContentProver

   verdict = guard_destructive_removal(path, project_path, prover=CanonicalContentProver(...))
   if verdict.owned:
       _safe_unlink(path)          # your existing delete + manifest prune
       changes.append(f"Removed {rel}")
   else:
       warnings.append(verdict.diagnostic)   # preserved / archived — content survives
   ```
3. Add a one-line comment documenting the ownership proof (charter L479).
4. Write a **red-first** test: seed a user-authored file that collides by name but is not
   package-owned; assert it survives (in place or backup) with a diagnostic AND that a genuinely
   package-owned target is still removed. It must be RED on the base commit, GREEN after your fix.

## If your op is genuinely safe (ephemeral scratch, worktree teardown, package-only)

Do NOT route it. Add it to the frozen allowlist in
`tests/architectural/test_mutation_ownership_routing.py` with a concrete one-line rationale
(what the path is, why no user content can be there). The allowlist is shrink-only.

## Don't

- Don't put the guard in `specify_cli/ownership/` (that's WP-scope manifests). It lives in `specify_cli/asset_preservation/`.
- Don't add a `--feature` CLI flag; don't put guard code in `specify_cli/__init__.py`.
- Don't add a raw `rmtree`/`unlink` of a user-visible dir — the gate will fail your PR.
- Don't signal preservation via a non-zero exit code; preservation exits success with a warning.

## Verify

```bash
PWHEADLESS=1 make test-fast
.venv/bin/python -m pytest tests/specify_cli/asset_preservation tests/architectural/test_mutation_ownership_routing.py -q
.venv/bin/python -m pytest tests/architectural -q     # new module + gate ⇒ run the arch suite
```
