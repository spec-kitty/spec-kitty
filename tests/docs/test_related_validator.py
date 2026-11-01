"""Self-test for the ``related:`` frontmatter validator (WP03 / IC-03 / FR-005).

The validator is *report-only* (exit 0) in Mission A; Mission B flips the
``--strict`` default on to make it blocking. This self-test is the real
Definition of Done: a ruler that cannot go RED is fake. We therefore prove
that

* a deliberately-**dangling** ``related:`` edge is detected (and reds under
  ``--strict``);
* a clean tree reports **no** dangling edges; and
* ``checked_count > 0`` so "0 broken" can never silently mean "0 checked".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs._guards import GitDiffError
from scripts.docs.related_validator import (
    DanglingEdge,
    main,
    validate_related,
    validate_related_diff_scoped,
)
from tests.docs.conftest import commit_all_changes, init_git_repo_with_base

pytestmark = pytest.mark.architectural


def _write(path: Path, frontmatter_related: list[str] | None, body: str = "x") -> None:
    """Write a markdown page with an optional ``related:`` frontmatter list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", 'title: "page"']
    if frontmatter_related is not None:
        lines.append("related:")
        lines.extend(f"  - {entry}" for entry in frontmatter_related)
    lines += ["---", "", f"# {body}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _stage_repo(tmp_path: Path, *, dangling: bool) -> Path:
    """Stage a repo-shaped tree under ``tmp_path`` and return the repo root.

    The source page names the slug ``target`` (``docs/target.md`` always exists)
    and, when ``dangling`` is true, also ``missing`` (which never does).
    """
    repo = tmp_path / "repo"
    docs = repo / "docs"
    _write(docs / "target.md", None, body="target")
    related = ["target"]
    if dangling:
        related.append("missing")
    _write(docs / "source.md", related, body="source")
    return repo


def test_dangling_edge_is_detected(tmp_path: Path) -> None:
    """A non-resolving ``related:`` entry surfaces as a dangling edge."""
    repo = _stage_repo(tmp_path, dangling=True)

    report = validate_related(docs_root=repo / "docs", repo_root=repo)

    assert report.checked_count > 0
    assert DanglingEdge(from_path="docs/source.md", to_path="missing") in report.dangling_edges


def test_clean_tree_has_no_dangling_edges(tmp_path: Path) -> None:
    """A tree whose ``related:`` edges all resolve reports zero dangling."""
    repo = _stage_repo(tmp_path, dangling=False)

    report = validate_related(docs_root=repo / "docs", repo_root=repo)

    assert report.checked_count > 0
    assert report.dangling_edges == []


def test_report_only_exit_zero_even_when_dangling(tmp_path: Path) -> None:
    """Default invocation is report-only: dangling edges still exit 0 (C-002)."""
    repo = _stage_repo(tmp_path, dangling=True)

    exit_code = main(["--repo-root", str(repo), "--docs-root", str(repo / "docs")])

    assert exit_code == 0


def test_strict_flag_reds_on_dangling(tmp_path: Path) -> None:
    """The wired ``--strict`` flag turns a dangling edge into a non-zero exit."""
    repo = _stage_repo(tmp_path, dangling=True)

    exit_code = main(["--repo-root", str(repo), "--docs-root", str(repo / "docs"), "--strict"])

    assert exit_code != 0


def test_strict_flag_stays_green_on_clean_tree(tmp_path: Path) -> None:
    """``--strict`` does not red a tree whose edges all resolve."""
    repo = _stage_repo(tmp_path, dangling=False)

    exit_code = main(["--repo-root", str(repo), "--docs-root", str(repo / "docs"), "--strict"])

    assert exit_code == 0


def test_zero_edge_walk_raises(tmp_path: Path) -> None:
    """A walk that examines no ``related:`` edges reds instead of passing vacuously.

    Mirrors ``relative_link_fixer.check_dead_body_links``' floor (#3264 / FR-008):
    a scope-narrowing regression that walks an empty or markdown-free tree must go
    RED, not report "0 dangling" over 0 checked.
    """
    empty_tree = tmp_path / "docs"
    empty_tree.mkdir()

    with pytest.raises(RuntimeError, match="expected at least"):
        validate_related(docs_root=empty_tree, repo_root=tmp_path)


def test_missing_docs_root_raises(tmp_path: Path) -> None:
    """A non-existent docs tree trips the same non-vacuity floor rather than returning empty."""
    with pytest.raises(RuntimeError, match="expected at least"):
        validate_related(docs_root=tmp_path / "absent", repo_root=tmp_path)


# --------------------------------------------------------------------------- #
# T009 — Diff-scope mode (#3147, B-WP02)                                      #
# --------------------------------------------------------------------------- #


class TestDiffScopeValidatorPureFunction:
    """:func:`validate_related_diff_scoped` unit tests (no git involved)."""

    def test_in_scope_dangling_edge_is_reported(self, tmp_path: Path) -> None:
        repo = _stage_repo(tmp_path, dangling=True)
        report = validate_related_diff_scoped(docs_root=repo / "docs", repo_root=repo, changed_files=["docs/source.md"])
        assert DanglingEdge(from_path="docs/source.md", to_path="missing") in report.dangling_edges

    def test_out_of_scope_dangling_edge_is_not_reported(self, tmp_path: Path) -> None:
        # source.md carries the dangling edge but is NOT in the changed set —
        # diff-scope must not surface it.
        repo = _stage_repo(tmp_path, dangling=True)
        report = validate_related_diff_scoped(docs_root=repo / "docs", repo_root=repo, changed_files=["target"])
        assert report.dangling_edges == []
        assert report.checked_count == 0

    def test_resolved_zero_in_scope_docs_returns_empty_not_raise(self, tmp_path: Path) -> None:
        # B-WP02: a changed set with no docs_root files (e.g. a
        # src/specify_cli/**-only PR) must be a clean pass, never RuntimeError.
        repo = _stage_repo(tmp_path, dangling=True)
        report = validate_related_diff_scoped(
            docs_root=repo / "docs",
            repo_root=repo,
            changed_files=["src/specify_cli/foo.py"],
        )
        assert report.checked_count == 0
        assert report.dangling_edges == []

    def test_empty_changed_set_returns_empty_not_raise(self, tmp_path: Path) -> None:
        repo = _stage_repo(tmp_path, dangling=True)
        report = validate_related_diff_scoped(docs_root=repo / "docs", repo_root=repo, changed_files=[])
        assert report.checked_count == 0
        assert report.dangling_edges == []

    def test_deleted_changed_file_is_skipped(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "docs").mkdir(parents=True)
        report = validate_related_diff_scoped(
            docs_root=repo / "docs",
            repo_root=repo,
            changed_files=["docs/gone-now.md"],
        )
        assert report.checked_count == 0
        assert report.dangling_edges == []


class TestDiffScopeValidatorCLI:
    """``--changed-from`` end-to-end through :func:`main`, over real git repos."""

    def test_in_scope_dangling_edge_reds(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs" / "target.md", None, body="target")
        base_sha = init_git_repo_with_base(repo)
        _write(repo / "docs" / "source.md", ["missing"], body="source")
        commit_all_changes(repo, "add dangling related edge")

        rc = main(
            [
                "--repo-root",
                str(repo),
                "--docs-root",
                str(repo / "docs"),
                "--strict",
                "--changed-from",
                base_sha,
            ]
        )

        assert rc == 1

    def test_out_of_scope_preexisting_dangling_edge_passes(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        # Pre-existing dangling edge, committed as part of the base state.
        _write(repo / "docs" / "source.md", ["missing"], body="source")
        base_sha = init_git_repo_with_base(repo)
        _write(repo / "docs" / "other.md", None, body="other")
        commit_all_changes(repo, "add unrelated doc")

        rc = main(
            [
                "--repo-root",
                str(repo),
                "--docs-root",
                str(repo / "docs"),
                "--strict",
                "--changed-from",
                base_sha,
            ]
        )

        assert rc == 0

    def test_resolved_zero_docs_passes(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs" / "target.md", None, body="target")
        base_sha = init_git_repo_with_base(repo)
        (repo / "README.md").write_text("# readme change\n", encoding="utf-8")
        commit_all_changes(repo, "non-docs change")

        rc = main(
            [
                "--repo-root",
                str(repo),
                "--docs-root",
                str(repo / "docs"),
                "--strict",
                "--changed-from",
                base_sha,
            ]
        )

        assert rc == 0

    def test_base_unresolvable_errors_non_zero(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs" / "target.md", None, body="target")
        init_git_repo_with_base(repo)

        rc = main(
            [
                "--repo-root",
                str(repo),
                "--docs-root",
                str(repo / "docs"),
                "--strict",
                "--changed-from",
                "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            ]
        )

        assert rc not in (0, 1)

    def test_base_unresolvable_does_not_raise_out_of_main(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        _write(repo / "docs" / "target.md", None, body="target")
        init_git_repo_with_base(repo)

        def _boom(*_args: object, **_kwargs: object) -> list[str]:
            raise GitDiffError("synthetic failure")

        monkeypatch.setattr("scripts.docs.related_validator.resolve_changed_files", _boom)
        rc = main(
            [
                "--repo-root",
                str(repo),
                "--docs-root",
                str(repo / "docs"),
                "--strict",
                "--changed-from",
                "whatever",
            ]
        )
        assert rc not in (0, 1)


# --------------------------------------------------------------------------- #
# doc-kitty slugs and publication (#6929)
# --------------------------------------------------------------------------- #


def _page(path: Path, frontmatter: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: t\n{frontmatter}---\n# t\n", encoding="utf-8")


def _publication_repo(tmp_path: Path, source_status: str, related: list[str]) -> Path:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    _page(docs / "index.md", "doc_status: active\n")
    _page(docs / "guides" / "index.md", "doc_status: active\n")
    _page(docs / "notes.md", "doc_status: draft\n")
    _page(docs / "archive" / "old.md", "doc_status: active\n")
    lines = "".join(f"- {entry!r}\n" for entry in related)
    _page(docs / "source.md", f"doc_status: {source_status}\nrelated:\n{lines}")
    return repo


def test_slugs_resolve_to_files_and_folder_indexes(tmp_path: Path) -> None:
    repo = _publication_repo(tmp_path, "active", ["guides", "", "guides/"])
    report = validate_related(docs_root=repo / "docs", repo_root=repo)
    assert report.dangling_edges == []
    assert report.unpublished_edges == []


def test_a_repository_path_is_no_longer_a_slug(tmp_path: Path) -> None:
    repo = _publication_repo(tmp_path, "active", ["docs/guides/index.md"])
    report = validate_related(docs_root=repo / "docs", repo_root=repo)
    assert report.dangling_edges == [DanglingEdge(from_path="docs/source.md", to_path="docs/guides/index.md")]


@pytest.mark.parametrize(
    ("source_status", "target", "flagged"),
    [
        ("active", "notes", True),
        ("active", "archive/old", True),
        ("draft", "notes", False),
        ("draft", "archive/old", True),
    ],
)
def test_published_and_draft_pages_name_only_what_doc_kitty_builds(tmp_path: Path, source_status: str, target: str, flagged: bool) -> None:
    repo = _publication_repo(tmp_path, source_status, [target])
    report = validate_related(docs_root=repo / "docs", repo_root=repo)
    assert (report.unpublished_edges == [DanglingEdge(from_path="docs/source.md", to_path=target)]) is flagged
    assert related_main_strict(repo) == (1 if flagged else 0)


def test_pages_in_excluded_folders_are_not_checked(tmp_path: Path) -> None:
    """doc-kitty never builds them, so their related list (old shape included) is never resolved."""
    repo = _publication_repo(tmp_path, "active", ["guides"])
    _page(repo / "docs" / "archive" / "x.md", "related:\n- docs/gone.md\n- archive/old\n")
    report = validate_related(docs_root=repo / "docs", repo_root=repo)
    assert report.dangling_edges == []
    assert report.unpublished_edges == []


def test_ref_note_entries_are_checked_by_their_ref(tmp_path: Path) -> None:
    repo = _publication_repo(tmp_path, "active", ["guides"])
    _page(repo / "docs" / "other.md", "doc_status: active\nrelated:\n- ref: gone\n  note: n\n")
    report = validate_related(docs_root=repo / "docs", repo_root=repo)
    assert DanglingEdge(from_path="docs/other.md", to_path="gone") in report.dangling_edges


def test_json_report_lists_unpublished_edges(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _publication_repo(tmp_path, "active", ["notes"])
    main(["--docs-root", str(repo / "docs"), "--repo-root", str(repo), "--json"])
    assert '"unpublished_edges"' in capsys.readouterr().out


def test_unreadable_page_is_skipped(tmp_path: Path) -> None:
    """A ``*.md`` path that cannot be read (here a directory) contributes no edges."""
    repo = _publication_repo(tmp_path, "active", ["guides"])
    (repo / "docs" / "folder.md").mkdir()
    report = validate_related(docs_root=repo / "docs", repo_root=repo)
    assert report.checked_count == 1
    assert not report.failed


def related_main_strict(repo: Path) -> int:
    return main(["--docs-root", str(repo / "docs"), "--repo-root", str(repo), "--strict"])
