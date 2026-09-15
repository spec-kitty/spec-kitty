"""WP18 — contract tests for the relative-link integrity fixer.

Mission B (*Common Docs Structural Move*, ``01KW3SBK``).  These tests drive the
real fixer (:mod:`scripts.docs.relative_link_fixer`) against synthetic repos so
the load-bearing invariants are pinned to observable behaviour:

#. a move-broken bare-relative body link **is** resolved to the correct new path
   through the ``moves:`` spine;
#. a coarse-spine-miss with a unique on-disk landing **is** healed by the
   unique-basename fallback (deterministic, not a guess);
#. an already-resolving link is **untouched** (idempotency);
#. a *frontmatter* link is **never** touched (WP12 territory);
#. an external / anchor-only / absolute link is **skipped**;
#. an unresolvable link is **reported, never guessed**;
#. the body-link-resolution gate goes **RED** on a planted broken link and
   **GREEN** on the clean tree.

A final real-tree gate (:class:`TestLiveTreeGate`) pins the assembled ``docs/``
to *zero* dead bare-relative body links bar the documented nav-stub gaps.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs._guards import GitDiffError  # noqa: E402  (sys.path bootstrap above)
from scripts.docs.relative_link_fixer import (  # noqa: E402  (sys.path bootstrap above)
    _LINK,
    LinkTarget,
    Resolver,
    Unresolvable,
    check_dead_body_links,
    check_dead_body_links_diff_scoped,
    is_bare_relative,
    main,
    parse_link_payload,
    rewrite_body,
    run,
)
from tests.docs.conftest import (  # noqa: E402  (sys.path bootstrap above)
    commit_all_changes,
    init_git_repo_with_base,
)

pytestmark = pytest.mark.fast


# --------------------------------------------------------------------------- #
# Synthetic-repo builder                                                       #
# --------------------------------------------------------------------------- #

# Mirrors the real restructure: ``how-to`` → ``guides``, ``reference`` → ``api``.
_OCCURRENCE_MAP: Final[str] = """\
target:
  term: "docs/"
  replacement: "docs/"
moves:
  - from: ["docs/how-to"]
    to: docs/guides
    reason: "How-to pages -> guides."
  - from: ["docs/reference"]
    to: docs/api
    reason: "Reference pages -> api."
status: applied
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Stage a post-move synthetic ``docs/`` tree + occurrence map.

    Returns ``(repo_root, occurrence_map_path)``.  The links in the staged files
    are authored against the *pre-move* layout, so the cross-directory ones are
    broken on this post-move tree exactly as the real restructure left them.
    """

    repo = tmp_path / "repo"
    occ = repo / "occurrence_map.yaml"
    _write(occ, _OCCURRENCE_MAP)

    # Moved target lives at its new home; the link in ``install.md`` still points
    # at the pre-move ``../reference/cli.md`` and is therefore broken.
    _write(repo / "docs/api/cli.md", "# CLI\n")
    _write(
        repo / "docs/guides/install.md",
        "---\nrelated:\n  - ../reference/cli.md\n---\n"
        "# Install\n\nSee the [CLI reference](../reference/cli.md) and the\n"
        "[install guide](install.md) and an [external](https://example.com/x.md)\n"
        "and an [anchor](#section) and an [absolute](/docs/api/cli.md).\n",
    )
    return repo, occ


# --------------------------------------------------------------------------- #
# Link payload parsing (pure units)                                            #
# --------------------------------------------------------------------------- #


class TestLinkParsing:
    def test_plain_target(self) -> None:
        parsed = parse_link_payload("../a/b.md")
        assert parsed == LinkTarget(lead="", angle=False, path="../a/b.md", anchor="", tail="")

    def test_anchor_preserved(self) -> None:
        parsed = parse_link_payload("../a/b.md#sec")
        assert parsed is not None
        assert parsed.path == "../a/b.md"
        assert parsed.anchor == "#sec"
        assert parsed.render("../x/b.md") == "../x/b.md#sec"

    def test_title_preserved(self) -> None:
        parsed = parse_link_payload('../a/b.md "Title here"')
        assert parsed is not None
        assert parsed.path == "../a/b.md"
        assert parsed.render("c.md") == 'c.md "Title here"'

    def test_angle_wrapped(self) -> None:
        parsed = parse_link_payload("<../a/b.md>")
        assert parsed is not None
        assert parsed.path == "../a/b.md"
        assert parsed.render("c.md") == "<c.md>"

    def test_empty_payload(self) -> None:
        assert parse_link_payload("") is None
        assert parse_link_payload("   ") is None

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("../a.md", True),
            ("a/b.md", True),
            ("https://x/a.md", False),
            ("http://x/a.md", False),
            ("mailto:x@y.z", False),
            ("#anchor", False),
            ("/abs/a.md", False),
            ("", False),
        ],
    )
    def test_is_bare_relative(self, path: str, expected: bool) -> None:
        assert is_bare_relative(path) is expected


# --------------------------------------------------------------------------- #
# C-006 narrowness: link-shape coverage                                        #
# --------------------------------------------------------------------------- #


class TestLinkShapeCoverage:
    """C-006: reference-style and raw-HTML links are out-of-scope; inline ](
    links are in scope.  These tests pin the exemption boundary so a future
    broadening is visible in the diff (FR-003 narrowness guard).
    """

    def test_reference_style_not_matched_by_link_regex(self) -> None:
        # Reference-style links [text][ref] are intentionally out of scope.
        assert _LINK.search("[text][ref]") is None

    def test_raw_html_href_not_matched_by_link_regex(self) -> None:
        # Raw-HTML <a href="..."> is intentionally out of scope.
        assert _LINK.search('<a href="../foo.md">') is None

    def test_inline_link_is_matched_by_link_regex(self) -> None:
        # Non-vacuity: inline ]( links ARE matched by _LINK.
        m = _LINK.search("[text](../foo.md)")
        assert m is not None
        assert m.group(1) == "../foo.md"

    def test_is_bare_relative_does_not_over_exclude(self) -> None:
        # C-006: the prefix check is exact — a path whose initial characters
        # resemble a skipped scheme but lack the colon/slash separator is still
        # treated as bare-relative (no over-broad prefix matching).
        assert is_bare_relative("mailto-archive.md") is True  # "mailto-" ≠ "mailto:"
        assert is_bare_relative("https-guide.md") is True  # "https-" ≠ "https://"
        assert is_bare_relative("mailto:foo@bar.com") is False
        assert is_bare_relative("https://example.com") is False


# --------------------------------------------------------------------------- #
# Resolution + rewrite behaviour                                              #
# --------------------------------------------------------------------------- #


class TestSpineResolution:
    def test_broken_link_resolved_to_new_path_via_moves(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        report = run(repo, occ)

        body = (repo / "docs/guides/install.md").read_text(encoding="utf-8")
        # The broken ``../reference/cli.md`` is rewritten to the real landing.
        assert "(../api/cli.md)" in body
        assert "../reference/cli.md" not in _strip_frontmatter(body)
        rewrites = {(r.old_link, r.new_link, r.tier) for r in report.rewrites}
        assert ("../reference/cli.md", "../api/cli.md", "spine") in rewrites

    def test_already_resolving_link_untouched(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        run(repo, occ)
        body = (repo / "docs/guides/install.md").read_text(encoding="utf-8")
        # ``install.md`` is a same-dir sibling that already resolves — verbatim.
        assert "[install guide](install.md)" in body

    def test_external_anchor_absolute_skipped(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        run(repo, occ)
        body = (repo / "docs/guides/install.md").read_text(encoding="utf-8")
        assert "(https://example.com/x.md)" in body
        assert "(#section)" in body
        assert "(/docs/api/cli.md)" in body

    def test_frontmatter_link_never_touched(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        run(repo, occ)
        text = (repo / "docs/guides/install.md").read_text(encoding="utf-8")
        front = text.split("---\n", 2)[1]
        # The frontmatter ``related:`` edge (WP12's category) is left as-authored.
        assert "../reference/cli.md" in front

    def test_idempotent_second_run_is_noop(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        run(repo, occ)
        after_first = (repo / "docs/guides/install.md").read_text(encoding="utf-8")
        second = run(repo, occ)
        after_second = (repo / "docs/guides/install.md").read_text(encoding="utf-8")
        assert second.total_rewrites == 0
        assert after_first == after_second


class TestOnDiskFallback:
    def test_unique_basename_landing_healed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "occurrence_map.yaml", _OCCURRENCE_MAP)
        # ``a.md`` never moved; its sibling link to ``b.md`` is broken because
        # ``b.md`` actually landed under a different, unique directory.
        _write(repo / "docs/notes/a.md", "# A\n\nSee [B](b.md).\n")
        _write(repo / "docs/elsewhere/b.md", "# B\n")
        report = run(repo, repo / "occurrence_map.yaml")
        body = (repo / "docs/notes/a.md").read_text(encoding="utf-8")
        assert "(../elsewhere/b.md)" in body
        assert {r.tier for r in report.rewrites} == {"on-disk"}

    def test_ambiguous_basename_reported_not_guessed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "occurrence_map.yaml", _OCCURRENCE_MAP)
        _write(repo / "docs/notes/a.md", "# A\n\nSee [dup](dup.md).\n")
        _write(repo / "docs/one/dup.md", "# one\n")
        _write(repo / "docs/two/dup.md", "# two\n")
        report = run(repo, repo / "occurrence_map.yaml")
        # Two ``dup.md`` candidates -> no deterministic target -> reported.
        assert report.total_rewrites == 0
        assert [(u.file, u.link) for u in report.unresolvable] == [("docs/notes/a.md", "dup.md")]


class TestReportNeverGuess:
    def test_unresolvable_link_reported(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "occurrence_map.yaml", _OCCURRENCE_MAP)
        _write(repo / "docs/notes/a.md", "# A\n\nSee [ghost](ghost.md).\n")
        report = run(repo, repo / "occurrence_map.yaml")
        body = (repo / "docs/notes/a.md").read_text(encoding="utf-8")
        # No target exists anywhere -> left verbatim, surfaced for the reviewer.
        assert "(ghost.md)" in body
        assert report.total_rewrites == 0
        assert [(u.file, u.link) for u in report.unresolvable] == [("docs/notes/a.md", "ghost.md")]


# --------------------------------------------------------------------------- #
# Body-link-resolution gate (T101)                                            #
# --------------------------------------------------------------------------- #


class TestGate:
    def test_gate_green_on_clean_tree(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        run(repo, occ)  # heal the move-broken link
        assert check_dead_body_links(repo) == []

    def test_gate_red_on_planted_broken_link(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        run(repo, occ)
        _write(
            repo / "docs/guides/planted.md",
            "# Planted\n\nA [dead](../does/not/exist.md) link.\n",
        )
        dead = check_dead_body_links(repo)
        assert [(u.file, u.link) for u in dead] == [("docs/guides/planted.md", "../does/not/exist.md")]

    def test_gate_covers_adr_subtree(self, tmp_path: Path) -> None:
        # WP02/T026: EXCLUDE_PREFIXES=() — docs/adr/ is now inside gate scope.
        # A dead link inside docs/adr/ MUST trip the gate (no longer excluded).
        repo, occ = _build_repo(tmp_path)
        run(repo, occ)
        _write(
            repo / "docs/adr/3.x/x.md",
            "# ADR\n\nA [dead](../does/not/exist.md) link.\n",
        )
        dead = check_dead_body_links(repo)
        assert any(u.file == "docs/adr/3.x/x.md" for u in dead), "docs/adr/ must be inside gate scope after EXCLUDE_PREFIXES=() flip (T026/FR-002)"


class TestRewriteBodyHelper:
    def test_rewrite_body_skips_frontmatter_region(self, tmp_path: Path) -> None:
        repo, occ = _build_repo(tmp_path)
        resolver = Resolver.build(repo, occ)
        body = "See [cli](../reference/cli.md).\n"
        new_body, rewrites, unresolved = rewrite_body(body, "docs/guides/install.md", resolver)
        assert "(../api/cli.md)" in new_body
        assert frozenset((r.old_link, r.new_link) for r in rewrites) == frozenset({("../reference/cli.md", "../api/cli.md")})
        assert unresolved == []


# --------------------------------------------------------------------------- #
# T002 — Non-vacuity guard (FR-004)                                           #
# --------------------------------------------------------------------------- #


class TestNonVacuityGuard:
    def test_guard_raises_on_zero_files(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        # Empty docs/ tree — no markdown files at all.
        (repo / "docs").mkdir(parents=True)
        with pytest.raises(RuntimeError, match="non-vacuity guard"):
            check_dead_body_links(repo)

    def test_guard_raises_on_zero_links(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        # One file, no bare-relative links — misconfigured or empty content.
        _write(repo / "docs/empty.md", "# No links here.\n")
        with pytest.raises(RuntimeError, match="non-vacuity guard"):
            check_dead_body_links(repo, min_links=1)

    def test_guard_passes_when_thresholds_met(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs/a.md", "# A\n")
        _write(repo / "docs/b.md", "# B\n\nSee [A](a.md).\n")
        # One file with one link — default min_files=1, min_links=1 should pass.
        result = check_dead_body_links(repo)
        assert result == []  # b.md's link to a.md resolves


# --------------------------------------------------------------------------- #
# T003 — Escape guard (D-1)                                                   #
# --------------------------------------------------------------------------- #


class TestEscapeGuard:
    def test_escape_guard_reports_link_escaping_docs_root(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        # Three ``..`` from ``docs/sub/page.md`` (file_dir = ``docs/sub``,
        # 2 components) goes above the repo root: the POSIX-normalised result
        # starts with ``..`` → genuine repo-root escape.  We do NOT create the
        # target because it is outside the repo; the escape-guard fires on the
        # normalised path alone (D-1), regardless of on-disk existence.
        _write(
            repo / "docs/sub/page.md",
            "# Sub\n\nSee [outside](../../../outside.md) for details.\n",
        )
        dead = check_dead_body_links(repo)
        assert any(u.link == "../../../outside.md" for u in dead), (
            "Escape guard must report a link whose POSIX-normalised target starts with '..' (genuine repo-root escape, D-1 true F5 invariant)"
        )

    def test_escape_guard_does_not_flag_intra_docs_traversal(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        # Both files exist; the link traverses up one level but stays inside docs/.
        _write(repo / "docs/other.md", "# Other\n")
        _write(
            repo / "docs/sub/page.md",
            "# Sub\n\nSee [other](../other.md) for details.\n",
        )
        dead = check_dead_body_links(repo)
        assert not any(u.link == "../other.md" for u in dead), (
            "Intra-docs traversal (docs/sub/../other.md → docs/other.md) must NOT be flagged as an escape — over-reporting guard (D-1)"
        )


# --------------------------------------------------------------------------- #
# T004 — --no-exclude flag (D-3)                                              #
# --------------------------------------------------------------------------- #


class TestNoExcludeFlag:
    def test_no_exclude_covers_excluded_subtree(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        # Dead link under docs/adr/ — normally excluded by EXCLUDE_PREFIXES.
        _write(
            repo / "docs/adr/3.x/page.md",
            "# ADR\n\nSee [dead](../ghost/missing.md).\n",
        )
        # With exclude_prefixes=() the file is in scope; the dead link is reported.
        dead = check_dead_body_links(repo, exclude_prefixes=())
        assert any(u.link == "../ghost/missing.md" for u in dead), "exclude_prefixes=() must cover docs/adr/ — link not found in dead list"

    def test_no_exclude_flag_plumbs_through_main(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # D-3 end-to-end: verify --no-exclude actually passes exclude_prefixes=()
        # to check_dead_body_links via main(), not merely to the internal API.
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Hello\n")

        captured: list[tuple[str, ...] | None] = []

        def spy(
            root: Path,
            *,
            exclude_prefixes: tuple[str, ...] | None = None,
            min_files: int = 1,
            min_links: int = 1,
        ) -> list[Unresolvable]:
            captured.append(exclude_prefixes)
            return []  # spy returns no dead links; we only care about the argument

        monkeypatch.setattr("scripts.docs.relative_link_fixer.check_dead_body_links", spy)
        main(["--check", "--no-exclude", "--repo-root", str(repo)])
        assert len(captured) == 1, (  # (call-count spy)
            f"Expected spy called once, got {len(captured)}"
        )
        assert captured[0] == (), f"--no-exclude must pass exclude_prefixes=() to check_dead_body_links, got {captured[0]!r}"


# --------------------------------------------------------------------------- #
# T006 — _KNOWN_GAPS 2-tuple projection (D-2)                                 #
# --------------------------------------------------------------------------- #


class TestKnownGapsProjection:
    def test_known_gaps_projection_is_2_tuple(self) -> None:
        # D-2: _KNOWN_GAPS is keyed on (file, link); the `line` field is
        # display-only and must NOT participate in gap-matching.
        # Two Unresolvable instances with the same (file, link) but different
        # line numbers must map to the SAME 2-tuple in the set comprehension.
        a = Unresolvable(file="docs/a.md", link="x.md", line=3)
        b = Unresolvable(file="docs/a.md", link="x.md", line=7)
        projected = {(u.file, u.link) for u in [a, b]}
        assert projected == {("docs/a.md", "x.md")}, (
            "Different line numbers for the same (file, link) must collapse to a single 2-tuple — line is display-only (D-2)"
        )


# --------------------------------------------------------------------------- #
# Live assembled-tree gate                                                     #
# --------------------------------------------------------------------------- #


class TestLiveTreeGate:
    """Pin the real ``docs/`` to **zero** unexpected dead bare-relative body links.

    WP14 created the three section landing pages the ``docs/index.md`` cards
    pointed at (``adr/index.md``, ``integrations/index.md``, ``security/index.md``)
    as part of flipping the body-link gate to blocking, so the former nav-stub
    gaps are now resolved.

    The D-1 escape guard (WP01/WP02, gate-hardening) flags only genuine
    repo-root escapes (normalised path starting with ``..``) and non-resolving
    targets.  In-repo cross-tree references (``docs/`` → ``src/``, ``tests/``,
    ``kitty-specs/``, etc.) that resolve on disk are **accepted** — they are
    not dead links and do not need allowlist entries.  As a result, the
    ``_KNOWN_GAPS`` set is empty: the production gate and these tests agree on
    zero dead links in the real ``docs/`` tree.
    """

    # (file, link) — line is display-only (D-2).
    # Empty: with the D-1 escape guard re-scoped to repo-root (WP02, cycle 1),
    # all in-repo cross-tree refs that resolve on disk are accepted by the gate.
    # Add entries ONLY for genuinely unfixable repo-root escapes or permanently
    # non-resolving links, with an inline justification per entry.
    #
    # Deliberately NOT used for the three files mission charter-code-topology-01M152G1
    # permanently deleted (src/doctrine/pyproject.toml, src/doctrine/hatch_build.py,
    # tests/architectural/test_doctrine_wheel_closure.py): the production `--check`
    # CLI invoked directly in CI (docs-freshness.yml, docs-build-pr.yml) has no
    # _KNOWN_GAPS mechanism of its own, so an entry here would silence only this
    # pytest copy of the gate while the real CI gate stayed red. The ADR that cited
    # those paths (2026-08-02-1-charter-wheel-assessment.md) was instead rewritten
    # to name them as plain code spans (no markdown link), which preserves the
    # historical record without producing a dead link.
    _KNOWN_GAPS: Final[frozenset[tuple[str, str]]] = frozenset()

    def test_assembled_tree_has_no_unexpected_dead_links(self) -> None:
        dead = {(u.file, u.link) for u in check_dead_body_links(_REPO_ROOT)}
        unexpected = dead - self._KNOWN_GAPS
        assert unexpected == set(), (
            "Run `python -m scripts.docs.relative_link_fixer --repo-root .` to "
            "rewrite each resolvable link via the moves:/on-disk-basename spine, "
            "or -- for a genuinely unfixable repo-root escape or permanently "
            "non-resolving target -- add a justified entry to _KNOWN_GAPS. "
            f"Unexpected dead bare-relative body links: {sorted(unexpected)}"
        )

    def test_full_tree_no_exclude_is_green(self) -> None:
        """C-007: the full docs/ scope with exclude_prefixes=() has no unexpected dead links.

        After EXCLUDE_PREFIXES=() gate-flip (WP02/T026, FR-002), the explicit
        full-scope invocation must be green — no dead bare-relative links beyond
        the documented known cross-tree references in _KNOWN_GAPS.  This is the
        C-007 gate-unmask verification: calling with exclude_prefixes=() and with
        the default (None) are now equivalent because EXCLUDE_PREFIXES is empty.
        """
        dead = {(u.file, u.link) for u in check_dead_body_links(_REPO_ROOT, exclude_prefixes=())}
        unexpected = dead - self._KNOWN_GAPS
        assert unexpected == set(), (
            "C-007 full-scope gate (exclude_prefixes=()). Run "
            "`python -m scripts.docs.relative_link_fixer --repo-root .` to "
            "rewrite each resolvable link (the fixer's write mode already covers "
            "the full tree -- exclude_prefixes only narrows the --check scan), or "
            "-- for a genuinely unfixable repo-root escape or permanently "
            "non-resolving target -- add a justified entry to _KNOWN_GAPS. "
            f"Unexpected dead bare-relative body links: {sorted(unexpected)}"
        )

    def test_live_tree_links_examined_meets_non_vacuity_floor(self) -> None:
        # FR-004: ensure the scan is not vacuously narrow on the real docs/ tree.
        # Floor is set at ≥ 1000 bare-relative inline links (observed: ~1360 as of
        # 2026-06-30; floor is ≈73 % to allow organic growth without the ratchet
        # becoming trivially defeatable).  Adjust the floor UPWARD as docs grow;
        # never downward without a documented scope-change explanation.
        # If this raises RuntimeError, a scope-narrowing regression is the cause:
        # broken iter_doc_files, over-broad exclude_prefixes, or a regex change
        # that stops matching links.
        check_dead_body_links(_REPO_ROOT, min_links=1000)


# --------------------------------------------------------------------------- #
# T008 — Diff-scope mode (#3147, B-WP02)                                      #
# --------------------------------------------------------------------------- #


class TestDiffScopeGatePureFunction:
    """:func:`check_dead_body_links_diff_scoped` unit tests (no git involved).

    ``changed_files`` is passed directly, exercising the file-scoping predicate
    in isolation from :func:`scripts.docs._guards.resolve_changed_files`.
    """

    def test_in_scope_violation_is_reported(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Home\n")
        _write(repo / "docs/page.md", "See [gone](../missing/none.md).\n")
        dead = check_dead_body_links_diff_scoped(repo, ["docs/page.md"])
        assert [(u.file, u.link) for u in dead] == [("docs/page.md", "../missing/none.md")]

    def test_out_of_scope_violation_is_not_reported(self, tmp_path: Path) -> None:
        # The broken link lives in a file NOT in the changed set — diff-scope
        # must not see it (B-WP02: the check_dead_body_links_diff_scoped scope
        # discipline is FILE-based, driven entirely by `changed_files`).
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Home\n")
        _write(repo / "docs/broken.md", "See [gone](../missing/none.md).\n")
        dead = check_dead_body_links_diff_scoped(repo, ["docs/index.md"])
        assert dead == []

    def test_resolved_zero_in_scope_docs_returns_empty_not_error(self, tmp_path: Path) -> None:
        # B-WP02: a non-empty changed set that contains no docs/**/*.md files
        # (e.g. a src/specify_cli/**-only PR) must be a clean pass, not raise.
        repo = tmp_path / "repo"
        _write(repo / "docs/broken.md", "See [gone](../missing/none.md).\n")
        dead = check_dead_body_links_diff_scoped(repo, ["src/specify_cli/foo.py"])
        assert dead == []

    def test_empty_changed_set_returns_empty_not_error(self, tmp_path: Path) -> None:
        # B-WP02's central assertion at its most literal: an empty changed set
        # (a resolved diff with genuinely zero changes) must NOT raise, unlike
        # the whole-tree gate's min_files=1 floor.
        repo = tmp_path / "repo"
        _write(repo / "docs/broken.md", "See [gone](../missing/none.md).\n")
        dead = check_dead_body_links_diff_scoped(repo, [])
        assert dead == []

    def test_deleted_changed_file_is_skipped(self, tmp_path: Path) -> None:
        # A changed path that no longer exists on disk (deleted in the diff)
        # must not crash the scan — there is nothing left to check.
        repo = tmp_path / "repo"
        repo.mkdir()
        dead = check_dead_body_links_diff_scoped(repo, ["docs/gone-now.md"])
        assert dead == []

    def test_non_docs_md_changed_file_is_ignored(self, tmp_path: Path) -> None:
        # A changed file outside docs/**/*.md (e.g. a non-md docs asset) is not
        # in scope for the bare-relative body-link gate.
        repo = tmp_path / "repo"
        _write(repo / "docs/image.png", "not really an image")
        dead = check_dead_body_links_diff_scoped(repo, ["docs/image.png"])
        assert dead == []

    def test_exclude_prefixes_still_apply_in_diff_scope(self, tmp_path: Path) -> None:
        # exclude_prefixes narrows diff-scope the same way it narrows the
        # whole-tree gate.
        repo = tmp_path / "repo"
        _write(repo / "docs/adr/3.x/x.md", "See [gone](../missing/none.md).\n")
        dead = check_dead_body_links_diff_scoped(repo, ["docs/adr/3.x/x.md"], exclude_prefixes=("docs/adr",))
        assert dead == []


class TestDiffScopeGateCLI:
    """``--changed-from`` end-to-end through :func:`main`, over real git repos.

    Mirrors the T012 three-case RED-proof in ``test_rulers_blocking.py`` at the
    unit level, plus the resolved-zero-docs pass case (B-WP02).
    """

    def test_in_scope_violation_reds(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Home\n")
        base_sha = init_git_repo_with_base(repo)
        _write(repo / "docs/page.md", "See [gone](../missing/none.md).\n")
        commit_all_changes(repo, "add broken link")

        rc = main(["--check", "--repo-root", str(repo), "--changed-from", base_sha])

        assert rc == 1

    def test_out_of_scope_preexisting_violation_passes(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Home\n")
        # Broken link committed as part of the BASE state — pre-existing.
        _write(repo / "docs/broken.md", "See [gone](../missing/none.md).\n")
        base_sha = init_git_repo_with_base(repo)
        # The PR itself only touches an unrelated file.
        _write(repo / "docs/other.md", "# Other\n")
        commit_all_changes(repo, "add unrelated doc")

        rc = main(["--check", "--repo-root", str(repo), "--changed-from", base_sha])

        assert rc == 0

    def test_resolved_zero_docs_passes(self, tmp_path: Path) -> None:
        # A non-docs-md PR (e.g. touching only a top-level file) must PASS —
        # its diff resolves fine and yields zero in-scope docs (B-WP02).
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Home\n")
        base_sha = init_git_repo_with_base(repo)
        (repo / "README.md").write_text("# readme change\n", encoding="utf-8")
        commit_all_changes(repo, "non-docs change")

        rc = main(["--check", "--repo-root", str(repo), "--changed-from", base_sha])

        assert rc == 0

    def test_base_unresolvable_errors_non_zero(self, tmp_path: Path) -> None:
        # B-WP02's third, load-bearing case: distinct from BOTH the in-scope
        # RED (1) and the out-of-scope/zero-docs PASS (0).
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Home\n")
        init_git_repo_with_base(repo)

        rc = main(
            [
                "--check",
                "--repo-root",
                str(repo),
                "--changed-from",
                "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            ]
        )

        assert rc not in (0, 1)
        assert rc != 0

    def test_base_unresolvable_does_not_raise_out_of_main(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # main() must translate GitDiffError into an exit code, not propagate it
        # (a CLI entry point that raises produces a traceback, not a clean gate).
        repo = tmp_path / "repo"
        _write(repo / "docs/index.md", "# Home\n")
        init_git_repo_with_base(repo)

        def _boom(*_args: object, **_kwargs: object) -> list[str]:
            raise GitDiffError("synthetic failure")

        monkeypatch.setattr("scripts.docs.relative_link_fixer.resolve_changed_files", _boom)
        rc = main(["--check", "--repo-root", str(repo), "--changed-from", "whatever"])
        assert rc not in (0, 1)


# --------------------------------------------------------------------------- #
# T007 — Performance regression guard (NFR-001)                               #
# --------------------------------------------------------------------------- #


class TestGatePerformance:
    @pytest.mark.performance
    def test_full_docs_scan_under_5_seconds(self) -> None:
        # NFR-001: full docs/ scan must complete in < 5 s.
        # The current live-tree scan takes ≈0.1–0.3 s; the 5 s threshold gives
        # ~15–50× headroom for organic growth and slow CI machines.
        # If this is persistently flaky on slow machines, raise to 10 s and
        # document the adjustment inline — the real constraint is "not materially
        # slow", not the exact 5 s figure.
        start = time.monotonic()
        check_dead_body_links(_REPO_ROOT)
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Gate scan took {elapsed:.2f}s — exceeds the 5 s NFR-001 budget"


# --------------------------------------------------------------------------- #
# T008 — Deliberate-breakage test (NFR-003, SC-002)                          #
# --------------------------------------------------------------------------- #


class TestDeliberateBreakage:
    def test_all_dead_links_reported_with_line_numbers(self, tmp_path: Path) -> None:
        # SC-002: all offenders reported, each with a correct line number.
        # File has NO frontmatter so body-relative == file-absolute line numbers.
        repo = tmp_path / "repo"
        _write(
            repo / "docs/section/a.md",
            "# Title\n"  # line 1
            "\n"  # line 2
            "See [first broken](../ghost/one.md) here.\n"  # line 3
            "Some prose.\n"  # line 4
            "See [second broken](../ghost/two.md) here.\n",  # line 5
        )
        dead = check_dead_body_links(repo)
        findings = {(u.file, u.line, u.link) for u in dead}
        assert findings == {
            ("docs/section/a.md", 3, "../ghost/one.md"),
            ("docs/section/a.md", 5, "../ghost/two.md"),
        }, f"Expected exactly these 2 dead links, got: {findings}"
        assert ("docs/section/a.md", 3, "../ghost/one.md") in findings, f"Expected line 3 for first broken link; findings: {findings}"
        assert ("docs/section/a.md", 5, "../ghost/two.md") in findings, f"Expected line 5 for second broken link; findings: {findings}"

    def test_dead_link_line_reported_correctly_with_frontmatter(self, tmp_path: Path) -> None:
        # SC-002 frontmatter case: line number must account for the frontmatter
        # offset so the reported line matches what an editor displays.
        # This pins the correctness of the fm_lines offset calculation.
        repo = tmp_path / "repo"
        _write(
            repo / "docs/adr/3.x/example.md",
            "---\n"  # line 1
            "title: Example ADR\n"  # line 2
            "status: accepted\n"  # line 3
            "---\n"  # line 4
            "\n"  # line 5
            "See [dead](../ghost/missing.md) here.\n",  # line 6 — offending link
        )
        # Use exclude_prefixes=() so docs/adr/ is in scope for this test.
        dead = check_dead_body_links(repo, exclude_prefixes=())
        assert frozenset((u.file, u.line, u.link) for u in dead) == frozenset({("docs/adr/3.x/example.md", 6, "../ghost/missing.md")})
        assert dead[0].line == 6, (
            f"Expected line 6 (editor-absolute, accounting for 4-line frontmatter), got {dead[0].line} — frontmatter offset not applied correctly"
        )


# --------------------------------------------------------------------------- #
# T029 — SC-005 hand-rolled dead-link loop sentinel                           #
# --------------------------------------------------------------------------- #


class TestSC005HandrolledLoopSentinel:
    """SC-005: no new hand-rolled dead-link scanning loops in tests/docs/.

    The canonical gate is :func:`check_dead_body_links` (exposed via
    ``scripts/docs/relative_link_fixer.py --check``).  Adding parallel
    checkers in ``tests/docs/`` fragments the unified gate surface and creates
    competing, unsynchronised rule sets.  This test pins the boundary.

    Allowlisted files that define their own link-checking infrastructure are
    excluded.  The allowlist must be grown intentionally — adding to it is a
    documented, reviewable act.
    """

    _TESTS_DOCS: Final[Path] = _REPO_ROOT / "tests" / "docs"

    # Files in tests/docs/ permitted to contain link-resolution infrastructure
    # (LINK_RE or _iter_local_links patterns).  Only the canonical gate file
    # belongs here — any future addition requires a documented rationale.
    _SC005_ALLOWED: Final[frozenset[str]] = frozenset(
        {
            "test_relative_link_fixer.py",  # the canonical gate itself
        }
    )

    _LINK_INFRA_PAT: Final[re.Pattern[str]] = re.compile(r"\bLINK_RE\b|\b_iter_local_links\b")

    def test_no_hand_rolled_link_loop_outside_allowlist(self) -> None:
        """SC-005: no file under tests/docs/ defines LINK_RE or _iter_local_links
        unless it is in _SC005_ALLOWED.
        """
        offenders: list[str] = []
        for py_file in sorted(self._TESTS_DOCS.rglob("*.py")):
            if py_file.name in self._SC005_ALLOWED:
                continue
            if self._LINK_INFRA_PAT.search(py_file.read_text(encoding="utf-8")):
                offenders.append(str(py_file.relative_to(_REPO_ROOT)))
        assert not offenders, (
            "SC-005: these test files define link-checking infrastructure outside "
            "the canonical gate — retire the checker or add it to _SC005_ALLOWED "
            f"with a documented rationale: {offenders}"
        )


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        return text.split("---\n", 2)[-1]
    return text
