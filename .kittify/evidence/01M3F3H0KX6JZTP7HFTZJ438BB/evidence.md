schema: review-verify/v1
complete: true
phase: op
mission: op-5000-fleet-verdict-import-fix
verified:
  - finding_id: op-rereview-001
    status: resolved
    evidence: >
      Loaded tests/ci/test_workflow_script_import_guard.py as a module and fed
      _has_module_level_scripts_import synthetic ASTs beyond the 10 cases already
      committed in test_has_module_level_scripts_import_filter: nested try inside
      an if (True), try/except* -- ast.TryStar (True), a from-import inside a
      class body (True), an import inside a function nested inside another
      function (False -- FunctionDef opacity is preserved at any nesting depth),
      bare "import scripts" (True), "from scripts import x" (True), "from
      scriptsx import y" (False -- confirms _is_scripts_module's exact-or-dotted
      match does not falsely widen to a same-prefix package name), a class nested
      inside another class with the import in the inner class body (True -- the
      "covered for free" claim in _nested_module_level_stmt_lists' docstring
      holds), a class body whose only import lives inside a method def (False --
      class-body inclusion does not leak into a def nested inside that class),
      and imports inside module-level for/while loops (both True). All 11 ran
      against the actual committed helper and matched expectation; combined with
      the 10 committed parametrized cases (if, try/except, try/else, try/finally,
      with, class-body, match, sync+async function-exclusion) this exercises
      every branch of _nested_module_level_stmt_lists (Try/TryStar, Match, If/
      For/AsyncFor/While, With/AsyncWith/ClassDef) plus the FunctionDef/
      AsyncFunctionDef opacity check and the exact-vs-prefix module-name match.
      The recursion now visits ast.Try, ast.TryStar, ast.Match, ast.For,
      ast.AsyncFor, ast.While, ast.With, ast.AsyncWith and ast.ClassDef (not just
      ast.If as before), while still skipping FunctionDef/AsyncFunctionDef
      bodies. Class-body inclusion is sound: it fires for a direct import, for a
      nested class's import (recursion naturally reaches it), and correctly does
      NOT fire for an import hidden inside a method defined in that class body,
      matching the documented rationale (a class body runs at import time; a
      method body does not, regardless of which class it lives in).
  - finding_id: op-rereview-002
    status: resolved
    evidence: >
      Built three synthetic workflow YAML files under a scratch dir outside the
      repo (never written into .github/) and called the module's own
      _workflow_run_blocks(path) / _BARE_SCRIPT_INVOCATION directly, since
      _workflow_run_blocks accepts an arbitrary Path. (1) A workflow whose only
      mention of a nonexistent scripts/ci/does_not_exist.py is inside a
      "#"-comment above a real `run: echo "hello world"` step: no exception, and
      the derived script set is empty (the comment is invisible to a real YAML
      parse, unlike the old raw-text regex) -- collection is not broken. (2) A
      workflow with a genuine `run: python3 scripts/ci/does_not_exist.py --flag`
      step: the path is correctly extracted into the candidate set, and re-running
      the same missing-path check test_workflow_invoked_scripts_resolve_to_real_files
      performs (script not on disk) yields a clean, named assertion candidate
      rather than a raised FileNotFoundError; separately called
      _imports_scripts_package() directly on that nonexistent path and confirmed
      it returns False rather than raising, which is what keeps the
      @pytest.mark.parametrize(...) call site at line 343 from crashing collection
      for this case. (3) A third synthetic workflow combined a job-level
      `defaults: run: shell: bash` block, a composite `uses: actions/checkout@v4`
      step (contributes no run text), a `run: |` (literal block scalar) step
      invoking scripts/ci/fleet_verdict.py, and a `run: >` (folded block scalar)
      step invoking scripts/ci/stale_running_sweep.py: exactly 2 run blocks were
      extracted (the uses: step correctly contributed none, and the defaults key
      did not interfere), and both script paths were correctly matched out of the
      block-scalar text regardless of style. Ran the real, hard-wired
      _workflow_invoked_scripts() / _scripts_exposed_to_bare_script_import_defect()
      against the actual .github/workflows directory (the helpers are hard-wired
      to _REPO_ROOT/.github/workflows via the _WORKFLOWS_DIR module constant, not
      parameterizable for that entry point -- acceptable, since this test's whole
      purpose is regression coverage of this repo's own live workflow set, not a
      general-purpose scanner): derived 24 scripts, filtered/executed 6
      (fleet_verdict, stale_running_sweep, wait_for_artifacts, glossary_linker,
      plantuml_render, seo_verify) -- unchanged from the commit message's claim.
      test_workflow_invoked_scripts_resolve_to_real_files and the 18-test file run
      both passed (`.venv/bin/python -m pytest tests/ci/test_workflow_script_import_guard.py -v`
      -> 18 passed).
new_findings:
  - id: op-verify-001
    lens: test-side-effect-hazard
    severity: 2
    title: "_workflow_run_blocks trades a never-raising raw-text regex for an unguarded yaml.safe_load call still made directly inside @pytest.mark.parametrize(...), reopening the same collection-crash failure MODE op-rereview-002 targeted, via a different trigger"
    evidence:
      - code: "tests/ci/test_workflow_script_import_guard.py:168-183"
      - code: "tests/ci/test_workflow_script_import_guard.py:343"
    claim: >
      op-rereview-002's fix correctly closes the FileNotFoundError collection
      crash by having _imports_scripts_package return False for a missing path
      instead of raising, and moves the "does this path exist" assertion to
      ordinary test-execution time in test_workflow_invoked_scripts_resolve_to_real_files.
      But _workflow_run_blocks (lines 168-183), which is still called directly
      inside the @pytest.mark.parametrize(...) decorator at line 343 via
      _scripts_exposed_to_bare_script_import_defect() -> _workflow_invoked_scripts(),
      does a bare `yaml.safe_load(workflow_path.read_text(...))` with no
      try/except, and then unconditionally calls `.get("jobs")` / `.values()` /
      `job.get("steps")` on whatever that returns. I constructed a synthetic
      workflow YAML with a tab-indented line (a common real-world YAML mistake,
      since GitHub Actions YAML forbids tabs) and confirmed
      `_workflow_run_blocks` raises an uncaught `yaml.scanner.ScannerError`
      rather than returning cleanly or raising a targeted, informative error --
      the same "whole test file fails to collect with a confusing traceback"
      failure mode the finding's own remediation text was written to eliminate,
      just triggered by a YAML syntax/shape defect instead of a missing file.
      This is not live today (all 24 real `.github/workflows/*.yml` files parse
      cleanly, confirmed above) and many sibling test files in tests/ci and
      tests/architectural already `yaml.safe_load` these same workflow files
      unguarded at collection or test time, so a genuinely malformed workflow
      YAML would already break several other files' collection simultaneously --
      this is a shared, pre-existing risk class across the workflow-yaml-parsing
      test surface, not a regression this commit introduced from nothing. But
      the commit's own docstring and commit message frame op-rereview-002 as
      fully closed ("no uncaught FileNotFoundError... instead of letting
      parametrize-time collection fail opaquely"), without noting that the fix
      narrows the guard to exactly one exception type/failure shape
      (FileNotFoundError from a missing script path) while leaving the new
      YAML-parse call site at the same collection-time position exposed to a
      different one (YAMLError / AttributeError from malformed or
      unexpectedly-shaped workflow YAML).
    remediation: >
      Either wrap _workflow_run_blocks's body (or its call site inside
      _workflow_invoked_scripts) in a narrow try/except (yaml.YAMLError,
      AttributeError) that surfaces a clear, workflow-path-naming failure rather
      than letting parametrize-time collection fail opaquely -- mirroring the
      fix already applied for the missing-script-path case -- or explicitly scope
      the docstring/commit message's "closes op-rereview-002" claim to "a missing
      script path no longer crashes collection" rather than "collection cannot be
      crashed by workflow-scan input," since the latter is not true of malformed
      YAML.
