# Contract: single-authority architectural gate

File: `tests/architectural/test_owned_checkout_single_authority.py`. It is AST-based and reuses `tests/architectural/_ast_scan.parse_file`. Comments and docstrings never count as offenders.

| Gate | Rule | Allowlist | Floor on the planning base (non-vacuity) |
|---|---|---|---|
| G1 | `resolve_ownership_claim` is referenced only in `specify_cli/core/owned_mission.py` (plus its definition in `checkout_ownership.py`). Every reference form counts: `ast.alias.name` (including `import … as x`), `Attribute.attr`, `Name.id`, and string `Constant`s used with `getattr`/`importlib`. | empty | ≥ 1 offender: `next_cmd.py:170`, `mission_creation.py:848` |
| G2 | `resolve_owned_mission(` / `adopt_owned_checkout(` are called only from `specify_cli/cli/commands/_owned_checkout.py` and `owned_mission.py` | empty | ≥ 1 offender: `status_transition.py:917`, plus every CLI command calling it directly today |
| G3 | `OwnedCheckout._mint` is referenced only in `owned_mission.py` | empty | the symbol does not exist on the planning base; covered by self-mutation |
| G4 | The identifier `effective_root` does not appear anywhere in `src/` outside the org-pack module rule (below): not as a parameter, field, local annotation, keyword argument, TypedDict key or string dict key (`"effective_root"`). Annotation spelling is irrelevant, because the rule bans the identifier, not the annotation type. | empty | ≥ 1 offender (≈ 400 sites) |
| G5 | No parameter or field carries an owned root as a path under any name: `owned_root`, `owned_checkout`, `checkout_root` or `effective_root` annotated `Path`, `pathlib.Path`, `Path \| None`, `Optional[Path]`, `Union[Path, None]`, `os.PathLike` or the string form of any of these. Two named exemptions only, each pinned by a self-mutation test: (a) the fields of `mission_runtime.owned_checkout.OwnedCheckout` (by fully-qualified class name); (b) `CLI_CLAIM_INPUT_RULE`: a parameter annotated with the CLI claim-input alias `OwnedCheckoutOption` (`specify_cli/cli/commands/_owned_checkout.py`), or with its help-preserving form `Annotated[Path | None, owned_checkout_option(help=...)]` (the same alias with a custom help string), because it carries the raw, unvalidated `--owned-checkout` input to the minter and is never an owned root. The `checkout_root` name check additionally excludes `src/specify_cli/upgrade/migrations/**` by module rule (historical migrations, an unrelated sense). | empty | ≥ 1 offender (e.g. `tasks_mark_status.py:114`, `tasks_move_task.py:248`, `mission_creation.py:127`) |
| G6 | Positive signature pin: each consumer in `contracts/owned-checkout-carrier.md` §7 declares a parameter or field `owned: OwnedCheckout \| None`. The topology-agnostic review-base helper `claim_commit_for_wp(mission_dir: Path, wp_id: str)` is not a G6 consumer. | n/a | red on the planning base (no consumer has it) |

**Org-pack exclusion (`ORG_PACK_MODULE_RULE`).** `effective_root` is also the org-pack root method `OrgPackConfig.effective_root` (`src/charter/offering/drg/org_pack_config.py:374`), a different concept. It is excluded from G4/G5 by one module-scoped rule with a written reason, covering exactly:
- `src/charter/**`
- `src/specify_cli/doctrine/**`
- `src/specify_cli/cli/commands/_doctrine_collect.py`
- `src/specify_cli/analysis_inputs.py`

`src/specify_cli/charter_runtime/lint/checks/org_layer.py` is **not** exempted: its walrus local `(effective_root := pack.effective_root(repo_root))` is **renamed** (for example to `pack_root`) by WP18 T097, and the method call itself is exempt everywhere by the `OrgPackConfig.effective_root` call rule (a `Call` whose `func` is `Attribute(attr="effective_root")`; an uncalled attribute read is still flagged).

**Scan floor (exact).** The set of files G1/G2/G4/G5 scan equals `src/**/*.py` minus the named module-rule exemptions, compared as sets; an emptied or narrowed scan root fails. WP18 also runs the gate against a worktree of the planning base and records per-gate offender counts meeting the floors above.

**Self-mutation tests.** Synthetic sources must each be flagged:
- a stray claim call;
- `import resolve_ownership_claim as r`;
- `mod.resolve_ownership_claim` attribute access;
- `effective_root: "Path | None"`;
- `Optional[Path]`;
- a TypedDict key `effective_root`;
- a `**{"effective_root": x}` splat;
- a renamed `checkout_root: Path | None` parameter;
- a direct `OwnedCheckout._mint` reference outside the minter;
- a second class with an `owned_root: Path` field.
- a parameter annotated `OwnedCheckoutOption` is **not** flagged, while the same parameter annotated `Annotated[Path | None, typer.Option(...)]` **is** (pins `CLI_CLAIM_INPUT_RULE`);
- a `checkout_root: Path` parameter under `src/specify_cli/upgrade/migrations/` is not flagged, while the same source under any other path is.

A clean synthetic source passes.

**Scope boundary.** G2 enforces *where* validation may be called. It does not enforce "once per command"; NFR-002's CLI-level count carries that.

**Commit discipline:**
- The self-mutation and floor tests land green in the foundation WP.
- The G1–G6 assertions are committed red as the first commit of the closing WP and go green there.
- `_baselines.yaml` gains a section `test_owned_checkout_single_authority: {owned_root_bare_path_params: 0}`.
- Transitional surfaces are marked `# TRANSITIONAL(WP18): <reason>`; the closing WP deletes everything `grep -rn "TRANSITIONAL(WP18)" src tests` finds and asserts that grep is empty. It fails on any marker that no WP's DoD lists.
- `grep -rn "# bridging:" src` is empty at the mission tip, and `tests/architectural/test_no_dead_symbols.py` is green there (not per lane).
