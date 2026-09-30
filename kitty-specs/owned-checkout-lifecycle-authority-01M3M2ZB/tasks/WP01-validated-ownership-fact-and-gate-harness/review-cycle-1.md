---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T17:37:54Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback, cycle 1 (reviewer-renata)

Verdict: **changes requested**. The carrier, surface pin, `OwnedRefusalCode` registry (15 members, matching the data-model table), layer ledger, ci-windows filter and red-first commit order are all good. The blocking items are vacuous tests, scanner gaps against `contracts/architectural-gate.md`, and DoD deviations. Each item below was reproduced with a probe script against lane-a HEAD `3c2ddf790`.

## Blocking

**1. The NFR-006 case-variant test is vacuous, and `_same_path`'s normcase branch is never executed.** (`tests/mission_runtime/test_owned_checkout.py:266-275`)
- (a) It is marked `windows_ci`, so `tests/conftest.py:335` skips it on Linux. The Linux run never executes it: `-m windows_ci` gives "1 skipped".
- (b) It monkeypatches `kernel.paths.is_windows`, but `owned_checkout.py` does `from kernel.paths import is_windows`, so the local binding is not patched. The probe shows `mission_runtime.owned_checkout.is_windows()` is still False after the patch.
- (c) The `ValueError` it catches comes from the *mission_dir* invariant ("mission_dir must be inside owned_root/kitty-specs"), not from the same-checkout invariant. `owned_root=swapcase(repo)` does not contain `mission`. The test would pass even if `_same_path` ignored case entirely, on Windows too.

Fix, per T003 step 4:
- Add an **unmarked** Linux test that patches `mission_runtime.owned_checkout.is_windows`, or `kernel.paths.is_windows` and then reads it through the module attribute.
- In that test, build a layout where only the case differs, so the only invariant that can fire is the same-checkout one. For example, call `_same_path` / `_is_within` directly, or mint with `owned_root` equal to a case-variant of `repository_root` where the mission dir sits under the variant.
- Assert the error message (`match="must not be the repository root checkout"`).
- Keep a separate `windows_ci` test that runs natively.
- Also cover `_is_within`'s Windows branch.

**2. The G4 docstring skip does not work, and its negative control does not discriminate.** (`_owned_checkout_scan.py:142-153`)
- `_iter_non_docstring_bodies` skips the docstring `Expr` node but still yields its child `Constant` (the scan uses `ast.walk` over the whole tree).
- Result 1: a docstring that is exactly `"""effective_root"""` **is** flagged (`string "effective_root"`).
- Result 2: removing the skip leaves `test_g4_negative_docstring_mention_is_not_flagged` green. The mutation-sanity item in the T005 checklist fails, because a prose docstring never `==` `"effective_root"`.

Fix: exclude the docstring's `Constant` too, for example by collecting `id(body[0].value)`. Then add a control whose docstring would be flagged without the skip: the exact-string docstring, on module, class and function.

**3. `ORG_PACK_MODULE_RULE` is not applied to G5.** The contract says the rule "takes them out of G4/G5 scope". `bare_owned_root_paths(parse("def f(effective_root: Path | None = None): ..."), "src/charter/offering/drg/org_pack_config.py")` returns a G5 offender. The four-path negative control only exercises G4.

Fix: apply the rule in `bare_owned_root_paths`, and extend the parametrised org-pack control to assert both G4 and G5 are empty.

Also fix the `effective_root_identifiers` docstring. It says "ORG_PACK_MODULE_RULE is the caller's decision … this visitor reports every occurrence", but the code applies the rule itself at `:244`. Pick one and make the code and docstring agree.

**4. Reference forms that G2 and G3 miss.** The WP asks for coverage "in any reference form" and "including via an alias".
- G3 misses `import mission_runtime; mission_runtime.OwnedCheckout._mint(...)`. This is the natural package-root spelling, because MR-1/MR-2 force root imports. It also misses `getattr(OwnedCheckout, "_mint")`. The probe returns `[]` for both.
- G2 misses the alias form `from specify_cli.core.owned_mission import resolve_owned_mission as rom; rom(...)`. The probe returns `[]`. G1 already handles aliases through `ast.alias`; G2 should resolve import-as aliases the same way, and dynamic `getattr` lookups as well.

Add a self-mutation case for each form.

**5. G6's docstring and code disagree.** The docstring (`:399-402`) says "A required name absent from `tree` … is an offender". The code at `:408-409` does `continue`, and `test_g6_negative_absent_name_is_not_reported` pins the skip. As written, a renamed or deleted consumer passes G6 without a report.

Fix: choose the semantics and make the docstring, code and test agree. If absence stays per-file-silent, document that WP18 must assert every §7 consumer is found somewhere, and put that in the WP18 hand-off note.

**6. The TRANSITIONAL(WP18) marker count does not match the DoD.** The DoD requires `grep -c "TRANSITIONAL(WP18)" src/mission_runtime/owned_checkout.py` to be **5**; it is **6**. The section-header comment at `owned_checkout.py:205` (`# -- Transitional legacy properties (TRANSITIONAL(WP18)) ---`) also matches, and WP18 T096 counts markers against the DoD lists.

Fix: reword the header so it does not contain the marker token. The test file is correct at 1.

**7. The mypy `--strict` and no-suppression rules are not met.**
- `mypy --strict tests/architectural/test_owned_checkout_gate_selftest.py` fails at `:29`: `_parse` has no return annotation (`-> ast.Module`).
- There are two `# type: ignore` comments with no rationale. Both are avoidable, and CLAUDE.md requires a fix or an inline justification:
  - `tests/mission_runtime/test_owned_checkout.py:48` (`_mint(**kwargs)`): type the kwargs with a TypedDict, or pass the fields explicitly with overrides.
  - `tests/architectural/_owned_checkout_scan.py:418`: narrow with `isinstance` inside the comprehension, or build the list of `(name, annotation)` pairs first.

## Should fix (same cycle)

- T005 lists `def f(effective_root: "Path | None" = None)` and `Optional[Path]` as "G4 **and** G5". The tests assert G4 only. Add the G5 assertion.
- The Test Strategy asks each positive case to assert the specific rule id **and line number**. No self-test asserts `lineno`. Add it at least to the multi-line cases (G3 alias, the TypedDict key, the walrus).
- `CLI_CLAIM_INPUT_ALIAS_NAMES` contains `"_owned_checkout.OwnedCheckoutOption"`, but `_annotation_name` returns only `.attr`, so that entry can never match. It is dead: remove it, or match the dotted form properly. Also, matching on the attr name alone exempts `anything.OwnedCheckoutOption`. Consider requiring `Name` or the `_owned_checkout.` qualifier.

## Non-blocking notes

- Inside the scanner, `assert isinstance(parsed, ast.Expr)` is stripped under `-O`. Prefer an explicit check that raises. Also, an empty string annotation raises `IndexError` on `.body[0]`.
- `test_mission_runtime_surface.py` picked up unrelated whole-file reformatting. It is harmless, but it inflates the diff of a file other WPs may touch.
- `test_no_dead_symbols` flags only `mission_runtime.owned_checkout::OwnedCheckoutPathRefused`. This is the expected, accepted transient, judged at the mission tip. Do not allowlist it.
