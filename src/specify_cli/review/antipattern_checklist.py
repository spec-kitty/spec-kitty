"""WP-level review anti-pattern checklist rendering."""

from __future__ import annotations


def render_wp_review_antipattern_checklist() -> str:
    """Return the required anti-pattern checklist for WP review prompts."""
    return """## Anti-pattern checklist (WP-level cheap version of mission-review)

For each item below, state PASS / FAIL / N/A in your verdict. A FAIL on any
item blocks approval.

1. **Dead code**: every new public function, class, or module created by this
   WP has at least one live caller from production code, excluding tests. For
   each new module, run targeted import/call-site greps, for example
   `grep -r -e "from <new_module> import" -e "import <new_module>" src/ --include="*.<ext>"`.
   Zero production hits means dead code.

2. **Synthetic-fixture test**: every test marked as covering an FR listed in
   this WP's frontmatter actually invokes the production code path that would
   produce the asserted shape. A test that constructs a literal dict matching
   the assertion is a synthetic fixture. Ask: if I delete the implementation
   code, does this test still pass? If yes, the FR is untested.

3. **Silent empty return**: search every new code path for `except ...:
   return ""`, `return None`, `return []`, `return {}`, or `pass`. Each hit
   must have a documented reason; absent that, it is a silent failure
   candidate.

4. **FR coverage**: every functional requirement in `requirement_refs`
   (`FR-###`, including a letter-suffixed `FR-###a`) has at least one test
   assertion that references the behavior it names, not just a comment or
   frontmatter entry. `SC-###` refs are tracked, not gated, and a
   `<mission-slug>#<ID>` ref cites another mission, so neither needs a test
   here.

5. **Frozen surface**: no commit in this WP modifies a file the spec,
   contract, or WP prompt marks as frozen or untouchable. For each frozen file,
   `git log --oneline <base>..HEAD -- <frozen-file>` must be empty.

6. **Locked decision**: no new code path contradicts a `MUST NOT` clause in
   `spec.md`, `plan.md`, or `contracts/`. Grep the diff for forbidden patterns
   named by those clauses.

7. **Shared-file ownership**: any file modified by this WP that is also
   modified by another WP, visible in `lanes.json`, shared lane metadata, or
   the same mission merge, has an explicit coordination note in the move-task
   reason or review feedback.

8. **Production fragility**: any new `raise` in a production code path has a
   documented fail-loud rationale. A bare `raise` in a request handler, worker,
   or CLI path that can fire on a transient race is a fragility risk.
"""
