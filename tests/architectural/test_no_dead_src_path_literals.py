"""Architectural gate: live documentation must not name a dead ``src/`` path.

Sibling of the dead-path gate family (``test_dead_builtin_doc_paths.py`` Gate D,
``test_no_dead_doctrine_paths.py`` Gate C, ``test_no_stale_charter_path_literals.py``)
— filed as the closing gate of the post-convergence doc-alignment wave 2
(issue #3964). Gate D polices one *specific* retired path shape (the pre-move
built-in content home) via ``git grep``; this gate is the general form the wave
asked for: **any** ``src/...`` path literal in a live doc must resolve to a real
file or directory in the tree, so the next relocation cannot leave the same
debris behind (the convergence relocated ``src/doctrine/`` →
``src/charter/offering/`` + ``packs/built-in/`` on 2026-09-05 and eleven living
docs kept pointing at the deleted tree for a year-class of reader confusion
before anyone noticed).

What the gate flags
-------------------
A *dead* path literal is a ``src/<segment>/...`` string in a scanned markdown
file whose concrete prefix (see *normalization* below) does not exist under the
repository root. Both halves matter: the string must look like a repo-relative
source path (leading ``src/`` at a word/path boundary), and the tree must not
contain what it names.

Scope decisions (read before "why doesn't this catch X")
--------------------------------------------------------
* **Markdown only** (``docs/**/*.md``). The derived/generated non-prose
  artifacts — ``toc.yml``, ``docs/api/toc.yml``, ``llms.txt``, the docfx config
  — are regenerated, never hand-edited, and are out of scope for the same
  reason Gate D excludes the generated retrieval index.
* **Archived/frozen subtrees are excluded wholesale**, each for the same
  reason Gate D excludes ``docs/adr`` and ``docs/plans``: an ADR, a plan, a
  changelog entry, a test-sanitation report, a migration note, or a convergence
  porting record documents the world *as it was* — its old paths are the
  record, not a live pointer. ``docs/migrations`` and ``docs/convergence`` are
  move/porting records by construction; ``docs/assets`` holds generated HTML;
  ``docs/archive`` is the archive.
* **A file whose frontmatter carries a retired lifecycle ``doc_status``
  (``deprecated`` / ``superseded`` / ``closeout``) is skipped entirely** — a
  deprecated page documents a retired design the same way an ADR does, and its
  dead paths describe that design, not the current tree. The vocabulary is the
  ``DocStatus`` enum (directive 042); the three retired values are the ones
  whose pages are point-in-time records.
* **Correct-as-history mentions and illustrative examples are allowlisted
  explicitly** (:data:`_ALLOWED_DEAD_LITERALS`) — a live doc may *name* a dead
  path while saying it is dead ("the convergence retired the
  ``src/specify_cli/saas/`` package", "relocated from ``src/doctrine/``"), and
  a how-to guide may use an obviously hypothetical user-project path
  (``src/models/user.py``) in its example. Each allowlist entry carries its
  justification inline. The allowlist is keyed on (file, literal): adding a
  *new* dead literal to an already-allowlisted file still fails, so the list
  cannot silently grow to cover the next wave of debris.
* **No line numbers in the allowlist** — history prose moves inside a file as
  sections are edited; the (file, literal) key is the stable identity of a
  history mention.
* **Root-level ``AGENTS.md`` / ``CLAUDE.md`` / ``README.md`` are not
  scanned** — their remaining dead mentions are all explicit
  removed-in-<commit> history, and Gate D's docs-only scoping is the family
  precedent. Extending the scan there means curating that history allowlist
  first; it is a deliberate non-goal of this gate, not an oversight.

Normalization
-------------
A literal may carry placeholder or glob segments (``<type>``, ``*``, ``**``) or
a trailing slash. Existence is checked on the *concrete prefix*: everything
from the first placeholder/glob segment onward is dropped, and a trailing
slash is ignored — ``src/doctrine/missions/<type>/`` is judged on
``src/doctrine/missions`` (dead), while ``packs/built-in/missions/<type>/``
would be judged on ``packs/built-in/missions`` (alive). A literal that is
*entirely* concrete must name a real file or directory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_ROOT = _REPO_ROOT / "docs"

#: Immutable historical snapshots and move/porting records -- never scanned.
#: Prefixes are relative to the repo root and posix-separated.
ARCHIVE_PATH_PREFIXES: tuple[str, ...] = (
    "docs/adr/",
    "docs/plans/",
    "docs/reports/",
    "docs/changelog/",
    "docs/archive/",
    "docs/migrations/",
    "docs/convergence/",
    "docs/assets/",
)

#: Frontmatter ``doc_status`` values whose pages are point-in-time records of
#: retired designs (the retired half of the directive-042 ``DocStatus``
#: vocabulary: draft/active pages state the current tree; these three do
#: not). Scoped to the file's own LEADING ``---...---`` frontmatter block
#: (see :func:`_frontmatter_block`) -- a ``doc_status:``-shaped line
#: appearing later in the document body (prose, an illustrative example, a
#: nested fenced block) is not a lifecycle declaration and must not retire
#: the file.
_RETIRED_DOC_STATUS: frozenset[str] = frozenset({"deprecated", "superseded", "closeout"})
_DOC_STATUS_RE = re.compile(r"^doc_status:\s*([A-Za-z_]+)\s*$", re.MULTILINE)
#: The leading frontmatter block: opening ``---``, body, closing ``---``, all
#: at the very start of the file. Non-greedy so a body that itself contains a
#: ``---`` horizontal rule can't swallow the rest of the document.
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

#: One ``src/...`` path literal, with an optional trailing slash. Segments are
#: concrete (``[A-Za-z0-9_]`` first, then word/dot/hyphen chars -- a leading
#: hyphen is NOT a segment start, so prose like "the src/-only list" never
#: matches), a ``<placeholder>`` segment, or a bare glob (``*`` / ``**``). The
#: word-boundary lookbehind (``(?<!\w)``) keeps the match from starting
#: mid-identifier (``othersrc/...``) while still reaching the two shapes a
#: repo-relative path legitimately appears in: an inline-code mention
#: (``​`src/foo.py`​``) and a relative markdown link or GitHub blob URL
#: (``](../../src/foo.py)``, ``.../blob/main/src/foo.py``) -- a dead path
#: inside a public blob link is exactly the 404 shape wave 2 had to fix.
_PATH_LITERAL_RE = re.compile(
    r"(?<!\w)src/"
    r"(?:[A-Za-z0-9_][A-Za-z0-9_.-]*|<[^>/]+>|\*|\*\*)"
    r"(?:/(?:[A-Za-z0-9_][A-Za-z0-9_.-]*|<[^>/]+>|\*|\*\*))*"
    r"/?"
)

#: Dead literals that are correct as written: each entry names why the mention
#: is history or illustration, not a live pointer. Keyed (file, literal); a
#: *different* dead literal in the same file still fails.
_ALLOWED_DEAD_LITERALS: dict[str, dict[str, str]] = {
    "docs/api/batch-api-contract.md": {
        "src/specify_cli/sync/emitter.py": "wire-contract history: the doc says this module was deleted with the sync transport",
        "src/specify_cli/sync/batch.py": "wire-contract history: the doc says this module was deleted with the sync transport",
        "src/specify_cli/delivery/receivers.py": "wire-contract history: the doc says this module was removed with the delivery subsystem",
    },
    "docs/api/profile-invocation.md": {
        "src/auth/token.py": "hypothetical artifact ref inside a JSON event example",
    },
    "docs/architecture/00_landscape/README.md": {
        "src/doctrine/": "relocation history: 'absorbed the former src/doctrine/ package at src/charter/offering/'",
    },
    "docs/architecture/04_implementation_mapping/README.md": {
        "src/specify_cli/saas/": "retirement history: 'the convergence retired ... the src/specify_cli/saas/ package'",
        "src/specify_cli/next/": "shim-deletion history: names the commit that deleted the shim",
    },
    "docs/architecture/execution-lanes.md": {
        "src/foo.py": "illustrative example path in a lane-layout snippet",
    },
    "docs/architecture/feature-detection.md": {
        "src/specify_cli/core/feature_detection.py": "prior-design record: the References section states this module was removed in #347",
    },
    "docs/architecture/gap-analysis-connector-installation-model.md": {
        # Point-in-time draft gap analysis (2026-03-10) whose "Relevant code"
        # bullets cite the pre-Convergence sync tree the gap was measured
        # against; the sync transport has since been retired outright.
        "src/specify_cli/sync/git_metadata.py": "draft gap analysis citing the pre-Convergence sync tree",
        "src/specify_cli/sync/emitter.py": "draft gap analysis citing the pre-Convergence sync tree",
    },
    "docs/architecture/git-workflow.md": {
        "src/new-feature.py": "illustrative example path in a git-workflow snippet",
    },
    "docs/architecture/mission-type-resolution.md": {
        "src/doctrine/missions/<type>/": "relocation history: both mentions are phrased 'relocated from src/doctrine/missions/<type>/'",
    },
    "docs/architecture/spdd-reasons.md": {
        "src/foo/api.py": "illustrative example path in a structure sketch",
    },
    "docs/context/contextive-glossaries.md": {
        "src/specify_cli/my_new_package": "hypothetical path in an add-a-scope YAML example",
    },
    "docs/development/how-to/review-gates.md": {
        # The literal sits inside a grep *pattern* whose job is to catch
        # source-tree-prefix mentions in shipped pack content -- searching for
        # the dead spelling is the guard working, not a path reference.
        "src/doctrine/": "grep guard pattern, not a path reference: the command searches pack content for src/-prefixed mentions",
    },
    "docs/development/reference/known-friction-points.md": {
        "src/specify_cli/next/": "shim-removal history: 'src/specify_cli/next/ is a shim removed in 3.3.0'",
    },
    "docs/development/testing/testing-parallel.md": {
        "src/specify_cli/cli/commands/sync.py": "historical recipe: the section header note says the sync surface was retired with the transport",
    },
    "docs/guides/how-to/missions/use-wps-yaml-manifest.md": {
        "src/models/user.py": "user-project example path in a YAML manifest example",
        "src/views/auth.py": "user-project example path in a YAML manifest example",
    },
    "docs/guides/how-to/recovery/troubleshoot-merge.md": {
        "src/path/to/file.py": "obviously hypothetical placeholder path in a recovery example",
    },
    "docs/guides/how-to/scenarios/worktree-parallel-missions.md": {
        "src/auth/jwt.py": "user-project example path in a parallel-mission scenario",
        "src/utils/validation.py": "user-project example path in a parallel-mission scenario",
        "src/errors.py": "user-project example path inside a .worktrees diff example",
    },
}


@dataclass(frozen=True)
class DeadPath:
    """One flagged occurrence: *relpath* line *lineno* names dead *literal*."""

    relpath: str
    lineno: int
    literal: str


def concrete_prefix(literal: str) -> str:
    """The existence-checked prefix: everything before the first placeholder
    or glob segment, with a trailing slash ignored.

    ``src/foo/<type>/bar.py`` → ``src/foo``; ``src/foo.py`` → ``src/foo.py``
    (a fully concrete literal is checked whole, extension included).
    """
    parts: list[str] = []
    for segment in literal.split("/"):
        if segment.startswith("<") or segment in ("*", "**", "..."):
            break
        parts.append(segment)
    return "/".join(parts).rstrip("/")


def resolves_in_tree(literal: str, *, repo_root: Path) -> bool:
    prefix = concrete_prefix(literal)
    if not prefix:
        return True
    return (repo_root / prefix).exists()


def _frontmatter_block(text: str) -> str:
    """The leading ``---...---`` frontmatter block's body, or ``""`` if the
    file has none (no leading ``---`` fence, or the fence is never closed).
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return ""
    return match.group(1) or ""


def is_retired_doc(text: str) -> bool:
    """True iff the file's LEADING frontmatter block carries a retired
    lifecycle ``doc_status`` -- a ``doc_status:`` line elsewhere in the body
    (prose, an example, a nested fenced block) does not count (#4105: this
    used to scan the whole file, vacuously retiring any doc that merely
    *mentioned* the string ``doc_status:`` outside its frontmatter).
    """
    frontmatter = _frontmatter_block(text)
    return any(match.group(1).lower() in _RETIRED_DOC_STATUS for match in _DOC_STATUS_RE.finditer(frontmatter))


def scan_markdown(text: str, *, relpath: str, repo_root: Path) -> list[DeadPath]:
    """Every dead ``src/`` literal in one markdown source.

    Fenced code, inline code, and prose are all scanned: a *runnable* grep
    example whose target path is dead (the wave-2 review-gates case) is a real
    defect, not an example, so fences get no wholesale exemption. The only
    exemptions are the (file, literal) history/example allowlist and the
    retired-``doc_status`` file-level skip, both applied by the caller.
    """
    allowed = _ALLOWED_DEAD_LITERALS.get(relpath, {})
    found: list[DeadPath] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _PATH_LITERAL_RE.finditer(line):
            literal = match.group(0)
            if literal in allowed:
                continue
            if resolves_in_tree(literal, repo_root=repo_root):
                continue
            found.append(DeadPath(relpath, lineno, literal))
    return found


def _is_archived(relpath: str) -> bool:
    return any(relpath.startswith(prefix) for prefix in ARCHIVE_PATH_PREFIXES)


def collect_dead_paths(
    *,
    docs_root: Path = _DOCS_ROOT,
    repo_root: Path = _REPO_ROOT,
) -> list[DeadPath]:
    """The full gate: every live markdown file under *docs_root*."""
    found: list[DeadPath] = []
    if not docs_root.exists():
        return found
    for path in sorted(docs_root.rglob("*.md")):
        relpath = path.relative_to(repo_root).as_posix()
        if _is_archived(relpath):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if is_retired_doc(text):
            continue
        found.extend(scan_markdown(text, relpath=relpath, repo_root=repo_root))
    return found


def _format(findings: list[DeadPath]) -> str:
    return "\n".join(f"  {d.relpath}:{d.lineno} names dead path {d.literal!r}" for d in findings)


# ---------------------------------------------------------------------------
# The real gate.
# ---------------------------------------------------------------------------


def test_no_dead_src_path_literals_in_live_docs() -> None:
    """Zero dead ``src/`` path literals across live documentation.

    The closing guard of doc-alignment wave 2 (#3964): a live doc that sends a
    reader to a ``src/`` path which does not exist is exactly the debris the
    convergence relocation left in eleven docs. Repoint the literal (code →
    ``src/charter/offering/``, shipped content → ``packs/built-in/``, or the
    real successor), or — if the mention is history or an example — add it to
    ``_ALLOWED_DEAD_LITERALS`` with the justification inline.
    """
    findings = collect_dead_paths()
    assert not findings, (
        "live documentation names a src/ path that does not exist in the tree:\n"
        f"{_format(findings)}\n"
        "repoint it to the real successor, or allowlist it as history/example "
        "with a justification in _ALLOWED_DEAD_LITERALS"
    )


def test_gate_is_not_vacuous_on_the_real_tree() -> None:
    """Non-vacuity: the scan actually reaches a substantial live-doc corpus."""
    scanned = 0
    for path in _DOCS_ROOT.rglob("*.md"):
        relpath = path.relative_to(_REPO_ROOT).as_posix()
        if _is_archived(relpath):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if is_retired_doc(text):
            continue
        if "src/" in text:
            scanned += 1
    assert scanned > 50, (
        f"only {scanned} live docs carry a src/ literal -- either the docs "
        "tree moved or this gate's discovery logic is broken; either way it "
        "would be silently vacuous above"
    )


def test_every_allowlist_entry_names_a_real_file_and_a_dead_literal() -> None:
    """The allowlist cannot rot: each entry's file must exist, and its literal
    must still be dead (an allowlisted literal that starts resolving means the
    entry is stale and should be removed) and must not resolve via a
    placeholder-empty prefix.
    """
    for relpath, literals in _ALLOWED_DEAD_LITERALS.items():
        assert (_REPO_ROOT / relpath).exists(), f"allowlist names missing file {relpath}"
        text = (_REPO_ROOT / relpath).read_text(encoding="utf-8")
        for literal, reason in literals.items():
            assert reason.strip(), f"{relpath}: allowlist entry {literal!r} carries no justification"
            assert not resolves_in_tree(literal, repo_root=_REPO_ROOT), (
                f"{relpath}: allowlisted literal {literal!r} now resolves in the tree -- the entry is stale, remove it"
            )
            assert literal in text, f"{relpath}: allowlisted literal {literal!r} no longer appears in the file -- the entry is stale, remove it"


# ---------------------------------------------------------------------------
# Scanner unit tests (synthetic trees -- no repo fixture needed).
# ---------------------------------------------------------------------------


def test_concrete_prefix_cuts_at_placeholder_and_glob() -> None:
    assert concrete_prefix("src/foo/<type>/bar.py") == "src/foo"
    assert concrete_prefix("src/foo/*/built-in") == "src/foo"
    assert concrete_prefix("src/foo.py") == "src/foo.py"
    assert concrete_prefix("src/foo/") == "src/foo"


def test_regex_requires_a_real_segment_start() -> None:
    """Prose like "the src/-only list" (wave-2 false positive) never matches."""
    line = "Top-19 of the full-corpus table is identical to the src/-only list."
    assert _PATH_LITERAL_RE.search(line) is None


def test_regex_matches_relative_link_and_inline_code_targets() -> None:
    link_match = _PATH_LITERAL_RE.search("see [x](../../src/foo.py)")
    assert link_match is not None and link_match.group(0) == "src/foo.py"
    code_match = _PATH_LITERAL_RE.search("edit `src/foo.py`")
    assert code_match is not None and code_match.group(0) == "src/foo.py"


def test_scan_flags_a_dead_literal_and_passes_a_live_one(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")
    text = "Live: `src/foo.py`. Dead: `src/bar.py` and `src/baz/<type>/`.\n"
    findings = scan_markdown(text, relpath="docs/fake.md", repo_root=tmp_path)
    assert [(d.lineno, d.literal) for d in findings] == [(1, "src/bar.py"), (1, "src/baz/<type>/")]


def test_allowlist_entry_does_not_excuse_a_different_literal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(_ALLOWED_DEAD_LITERALS, "docs/fake.md", {"src/foo.py": "history"})
    text = "History: `src/foo.py`. New debris: `src/bar.py`.\n"
    findings = scan_markdown(text, relpath="docs/fake.md", repo_root=tmp_path)
    assert [d.literal for d in findings] == ["src/bar.py"]


def test_retired_doc_status_skips_the_file(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    retired = docs / "retired.md"
    retired.write_text("---\ndoc_status: deprecated\n---\nDead: `src/gone.py`\n", encoding="utf-8")
    active = docs / "active.md"
    active.write_text("Dead: `src/gone.py`\n", encoding="utf-8")
    findings = collect_dead_paths(docs_root=docs, repo_root=tmp_path)
    assert [d.relpath for d in findings] == ["docs/active.md"]


def test_archive_prefixes_are_not_scanned(tmp_path: Path) -> None:
    findings = collect_dead_paths(docs_root=tmp_path / "does-not-exist", repo_root=tmp_path)
    assert findings == []


# ---------------------------------------------------------------------------
# spec-kitty#4105: ``is_retired_doc`` non-vacuity. Before the fix,
# ``_DOC_STATUS_RE`` was applied to the WHOLE file text via ``finditer``, so a
# ``doc_status:`` line anywhere in the document -- including deep in body
# prose, nowhere near the leading frontmatter block -- vacuously retired the
# file and let a genuinely dead ``src/`` literal in it pass uncaught. These
# are the guard's permanent non-vacuity tests, not transitional scaffolding.
# ---------------------------------------------------------------------------


def test_is_retired_doc_scopes_to_frontmatter_only_4105() -> None:
    """A ``doc_status:``-shaped line in the file BODY must not retire the
    file; only a ``doc_status:`` line inside the leading ``---...---``
    frontmatter block may.
    """
    body_only = "# Title\n\nSome prose.\n\ndoc_status: superseded\n\nMore prose.\n"
    assert is_retired_doc(body_only) is False

    frontmatter = "---\ndoc_status: superseded\n---\n\nBody text.\n"
    assert is_retired_doc(frontmatter) is True

    no_frontmatter_at_all = "Body text with no frontmatter at all.\n"
    assert is_retired_doc(no_frontmatter_at_all) is False


def test_body_doc_status_does_not_skip_a_dead_path_4105(tmp_path: Path) -> None:
    """Integration-level non-vacuity demo: a doc whose BODY (not frontmatter)
    carries a ``doc_status:`` line must still be scanned for dead ``src/``
    literals; a genuinely frontmatter-retired page must still skip.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    body_status = docs / "body-status.md"
    body_status.write_text(
        "# Some Doc\n\ndoc_status: superseded\n\nDead: `src/nonexistent_xyz.py`\n",
        encoding="utf-8",
    )
    frontmatter_status = docs / "frontmatter-status.md"
    frontmatter_status.write_text(
        "---\ndoc_status: superseded\n---\n\nDead: `src/nonexistent_xyz.py`\n",
        encoding="utf-8",
    )
    findings = collect_dead_paths(docs_root=docs, repo_root=tmp_path)
    assert [d.relpath for d in findings] == ["docs/body-status.md"]
    assert findings[0].literal == "src/nonexistent_xyz.py"
