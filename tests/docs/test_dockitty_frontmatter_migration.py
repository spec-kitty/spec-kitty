"""Unit tests for ``scripts/docs/dockitty_frontmatter_migration.py`` (#6929, FR-002/005/006/008/010)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs import dockitty_frontmatter_migration as mig
from scripts.docs._inventory import parse_frontmatter
from tests.docs.conftest import commit_all_changes, init_git_repo_with_base

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MAINTAINER = "docs/context/audience/internal/maintainer.md"


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A tiny repository: personas, published/draft/excluded pages, an ADR and a non-docs file."""
    _write(tmp_path, _MAINTAINER, "---\ntitle: 'Stakeholder Persona: Maintainer'\ndoc_status: active\n---\n")
    _write(tmp_path, "docs/guides/a.md", "---\ntitle: A\ndoc_status: active\n---\n")
    _write(tmp_path, "docs/guides/index.md", "---\ntitle: Guides\ndoc_status: active\n---\n")
    _write(tmp_path, "docs/plans/notes.md", "---\ntitle: Notes\ndoc_status: draft\n---\n")
    _write(tmp_path, "docs/archive/old.md", "---\ntitle: Old\ndoc_status: deprecated\n---\n")
    _write(tmp_path, "docs/adr/4.x/2026-01-01-1-x.md", "---\ntitle: X\nstatus: Proposed\ndate: '2026-01-01'\n---\nbody\n")
    _write(tmp_path, "pyproject.toml", "[project]\n")
    (tmp_path / "tests").mkdir()
    return tmp_path


def _corpus(repo: Path) -> mig.Corpus:
    return mig.Corpus.load(docs_root=repo / "docs", repo_root=repo)


def _migrate(repo: Path, rel: str, text: str) -> tuple[str, mig.MigrationReport]:
    report = mig.MigrationReport()
    return mig.migrate_text(rel, text, _corpus(repo), report), report


# --- audience ---------------------------------------------------------------


def test_audience_path_becomes_profile_with_persona_guidance(repo: Path) -> None:
    out, report = _migrate(repo, "guides/p.md", f"---\ntitle: P\naudience: {_MAINTAINER}\n---\nbody\n")
    assert parse_frontmatter(out)["audience"] == [{"profile": "internal/maintainer", "guidance_text": "Written for the Maintainer reader."}]
    assert "- profile: internal/maintainer\n  guidance_text:" in out
    assert out.endswith("---\nbody\n")
    assert report.audience_files == 1


def test_audience_list_and_free_text(repo: Path) -> None:
    text = f"---\ntitle: P\naudience:\n- {_MAINTAINER}\n- end-users\n---\n"
    out, _ = _migrate(repo, "guides/p.md", text)
    assert parse_frontmatter(out)["audience"][1] == {"profile": "end-users", "guidance_text": "Written for end-users."}


def test_audience_already_migrated_is_unchanged(repo: Path) -> None:
    text = "---\ntitle: P\naudience:\n- profile: internal/maintainer\n  guidance_text: Hand-written.\n---\n"
    assert _migrate(repo, "guides/p.md", text)[0] == text


@pytest.mark.parametrize("bad", ["audience: 3", "audience:\n- 3"])
def test_audience_of_an_unknown_shape_fails_closed(repo: Path, bad: str) -> None:
    with pytest.raises(mig.MigrationError):
        _migrate(repo, "guides/p.md", f"---\ntitle: P\n{bad}\n---\n")


# --- ADRs -------------------------------------------------------------------


@pytest.mark.parametrize(("status", "doc_status"), [("Accepted", "active"), ("Proposed", "active"), ("Superseded", "superseded")])
def test_adr_gains_doc_status_and_kind_after_status(repo: Path, status: str, doc_status: str) -> None:
    text = f"---\ntitle: X\nstatus: {status}\ndate: '2026-01-01'\nsuperseded_by: y\n---\nbody\n"
    out, report = _migrate(repo, "adr/4.x/2026-01-01-1-x.md", text)
    assert out == (f"---\ntitle: X\nstatus: {status}\ndoc_status: {doc_status}\nkind: ADR\ndate: '2026-01-01'\nsuperseded_by: y\n---\nbody\n")
    assert report.adr_files == 1


def test_adr_with_unknown_status_fails_closed(repo: Path) -> None:
    with pytest.raises(mig.MigrationError, match="no doc_status mapping"):
        _migrate(repo, "adr/4.x/2026-01-01-1-x.md", "---\ntitle: X\nstatus: Rejected\n---\n")


def test_adr_with_conflicting_doc_status_fails_closed(repo: Path) -> None:
    with pytest.raises(mig.MigrationError, match="doc_status"):
        _migrate(repo, "adr/4.x/2026-01-01-1-x.md", "---\ntitle: X\nstatus: Accepted\ndoc_status: draft\n---\n")


def test_adr_era_index_is_not_an_adr(repo: Path) -> None:
    text = "---\ntitle: ADRs\nstatus: whatever\n---\n"
    assert _migrate(repo, "adr/4.x/index.md", text)[0] == text


# --- related ----------------------------------------------------------------


def test_related_published_pages_become_slugs_and_the_rest_external(repo: Path) -> None:
    text = (
        "---\ntitle: P\ndoc_status: active\nrelated:\n- docs/guides/a.md\n- docs/guides/index.md\n"
        "- docs/adr/4.x/2026-01-01-1-x.md\n- docs/plans/notes.md\n- docs/archive/old.md\n- pyproject.toml\n"
        "- tests\n- docs/gone.md\n- guides/a\n- {ref: guides, note: n}\ndescription: d\n---\n"
    )
    out, report = _migrate(repo, "guides/p.md", text)
    data = parse_frontmatter(out)
    assert data["related"] == ["guides/a", "guides", "adr/4.x/2026-01-01-1-x", {"ref": "guides", "note": "n"}]
    assert list(data["related"][3]) == ["ref", "note"]
    base = "https://github.com/spec-kitty/spec-kitty"
    assert data["external_references"] == [
        {"url": f"{base}/blob/main/docs/plans/notes.md", "title": "Notes"},
        {"url": f"{base}/blob/main/docs/archive/old.md", "title": "Old"},
        {"url": f"{base}/blob/main/pyproject.toml", "title": "pyproject.toml"},
        {"url": f"{base}/tree/main/tests", "title": "tests"},
    ]
    assert data["description"] == "d"
    assert report.dropped_references == [{"from": "docs/guides/p.md", "to": "docs/gone.md"}]
    assert report.external_references == 4


def test_related_with_only_external_targets_drops_the_key(repo: Path) -> None:
    out, _ = _migrate(repo, "guides/p.md", "---\ntitle: P\ndoc_status: active\nrelated:\n- pyproject.toml\n---\n")
    data = parse_frontmatter(out)
    assert "related" not in data
    assert data["external_references"][0]["title"] == "pyproject.toml"


def test_related_with_only_missing_targets_drops_the_key(repo: Path) -> None:
    out, _ = _migrate(repo, "guides/p.md", "---\ntitle: P\ndoc_status: active\nrelated:\n- docs/gone.md\n---\n")
    assert "related" not in parse_frontmatter(out)
    assert "external_references" not in parse_frontmatter(out)


def test_an_excluded_source_keeps_slugs_to_unpublished_pages(repo: Path) -> None:
    out, _ = _migrate(repo, "archive/x.md", "---\ntitle: X\nrelated:\n- docs/archive/old.md\n- docs/plans/notes.md\n---\n")
    assert parse_frontmatter(out)["related"] == ["archive/old", "plans/notes"]


def test_a_draft_source_keeps_drafts_but_not_excluded_pages(repo: Path) -> None:
    text = "---\ntitle: X\ndoc_status: draft\nrelated:\n- docs/plans/notes.md\n- docs/archive/old.md\n---\n"
    data = parse_frontmatter(_migrate(repo, "plans/x.md", text)[0])
    assert data["related"] == ["plans/notes"]
    assert data["external_references"][0]["title"] == "Old"


def test_related_merges_into_existing_external_references_without_duplicates(repo: Path) -> None:
    existing = "external_references:\n- url: https://github.com/spec-kitty/spec-kitty/blob/main/pyproject.toml\n  title: pyproject.toml\n"
    text = f"---\ntitle: P\ndoc_status: active\n{existing}related:\n- pyproject.toml\n- docs/guides/a.md\n---\n"
    data = parse_frontmatter(_migrate(repo, "guides/p.md", text)[0])
    assert len(data["external_references"]) == 1
    assert data["related"] == ["guides/a"]


@pytest.mark.parametrize("bad", ["related: x", "related:\n- 3"])
def test_related_of_an_unknown_shape_fails_closed(repo: Path, bad: str) -> None:
    with pytest.raises(mig.MigrationError):
        _migrate(repo, "guides/p.md", f"---\ntitle: P\n{bad}\n---\n")


def test_root_page_is_the_empty_slug_and_stays_stable(repo: Path) -> None:
    _write(repo, "docs/index.md", "---\ntitle: Home\ndoc_status: active\n---\n")
    out, _ = _migrate(repo, "guides/p.md", "---\ntitle: P\ndoc_status: active\nrelated:\n- docs/index.md\n---\n")
    assert parse_frontmatter(out)["related"] == [""]
    assert _migrate(repo, "guides/p.md", out)[0] == out


def test_empty_slug_without_a_root_page_is_dropped(repo: Path) -> None:
    out, report = _migrate(repo, "guides/p.md", "---\ntitle: P\ndoc_status: active\nrelated:\n- ''\n---\n")
    assert "related" not in parse_frontmatter(out)
    assert report.dropped_references == [{"from": "docs/guides/p.md", "to": ""}]


def test_ref_note_entries_are_classified_by_their_ref(repo: Path) -> None:
    text = "---\ntitle: P\ndoc_status: active\nrelated:\n- ref: docs/guides/a.md\n  note: keep\n- ref: archive/old\n  note: moved\n---\n"
    data = parse_frontmatter(_migrate(repo, "guides/p.md", text)[0])
    assert data["related"] == [{"ref": "guides/a", "note": "keep"}]
    assert data["external_references"][0]["note"] == "moved"


def test_ref_note_entry_without_a_string_ref_fails_closed(repo: Path) -> None:
    with pytest.raises(mig.MigrationError, match="no string ref"):
        _migrate(repo, "guides/p.md", "---\ntitle: P\nrelated:\n- note: n\n---\n")


@pytest.mark.parametrize("bad", ["external_references:\n  url: u", "external_references:\n- u"])
def test_existing_external_references_of_an_unknown_shape_fail_closed(repo: Path, bad: str) -> None:
    with pytest.raises(mig.MigrationError, match="external_references"):
        _migrate(repo, "guides/p.md", f"---\ntitle: P\n{bad}\nrelated:\n- pyproject.toml\n---\n")


def test_a_comment_inside_an_edited_block_is_refused(repo: Path) -> None:
    with pytest.raises(mig.MigrationError, match="comment"):
        _migrate(repo, "guides/p.md", f"---\ntitle: P\naudience:\n  # keep me\n- {_MAINTAINER}\n---\n")


def test_mixed_line_endings_are_refused(repo: Path) -> None:
    with pytest.raises(mig.MigrationError, match="line endings"):
        _migrate(repo, "guides/p.md", f"---\r\ntitle: Q\naudience: {_MAINTAINER}\r\n---\r\n")


# --- editing, skipping, integrity ------------------------------------------


@pytest.mark.parametrize(
    "rel",
    ["adr/1.x/README.md", "architecture/README.md", "changelog/unreleased/1.fixed.md", "adr/4.x/index.md"],
)
def test_skipped_files_are_never_edited(repo: Path, rel: str) -> None:
    text = f"---\ntitle: S\naudience: {_MAINTAINER}\n---\n"
    assert _migrate(repo, rel, text)[0] == text


def test_text_without_frontmatter_is_unchanged(repo: Path) -> None:
    assert _migrate(repo, "guides/p.md", "# no frontmatter\n")[0] == "# no frontmatter\n"


def test_crlf_frontmatter_keeps_crlf(repo: Path) -> None:
    text = f"---\r\ntitle: P\r\naudience: {_MAINTAINER}\r\n---\r\nbody\r\n"
    out = _migrate(repo, "guides/p.md", text)[0]
    assert "\n" not in out.replace("\r\n", "")
    assert out.endswith("---\r\nbody\r\n")


def test_integrity_check_catches_a_changed_neighbour_key() -> None:
    with pytest.raises(mig.MigrationIntegrityError, match="title"):
        mig._check_integrity("p.md", {"title": "a"}, {"title": "b"}, {})


def test_integrity_check_catches_an_unintended_value() -> None:
    with pytest.raises(mig.MigrationIntegrityError, match="audience"):
        mig._check_integrity("p.md", {"audience": "x"}, {"audience": "y"}, {"audience": "z"})


def test_body_guard_refuses_a_rewrite_whose_body_differs(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mig, "body_of", lambda text: "tampered")
    with pytest.raises(mig.MigrationIntegrityError, match="body changed"):
        _migrate(repo, "guides/p.md", f"---\ntitle: P\naudience: {_MAINTAINER}\n---\nbody\n")


# --- tree, CLI, verify ------------------------------------------------------


def test_migrate_tree_is_idempotent_and_cli_check_reports(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "docs/guides/p.md", f"---\ntitle: P\ndoc_status: active\naudience: {_MAINTAINER}\nrelated:\n- docs/gone.md\n---\nbody\n")
    args = ["--docs-root", str(repo / "docs"), "--repo-root", str(repo)]
    assert mig.main([*args, "--check"]) == 1
    assert "DROPPED docs/guides/p.md -> docs/gone.md" in capsys.readouterr().out
    assert mig.main([*args, "--apply", "--json"]) == 0
    assert '"changed_files": 2' in capsys.readouterr().out
    assert mig.main([*args, "--check"]) == 0
    second = mig.migrate_tree(docs_root=repo / "docs", repo_root=repo, write=False)
    assert second.changed_files == []


def test_apply_writes_nothing_when_any_page_fails(repo: Path) -> None:
    good = _write(repo, "docs/guides/p.md", f"---\ntitle: P\naudience: {_MAINTAINER}\n---\n")
    _write(repo, "docs/adr/4.x/2026-02-02-1-y.md", "---\ntitle: Y\nstatus: Rejected\n---\n")
    before = good.read_text(encoding="utf-8")
    with pytest.raises(mig.MigrationError):
        mig.migrate_tree(docs_root=repo / "docs", repo_root=repo, write=True)
    assert good.read_text(encoding="utf-8") == before


def test_cli_reports_a_migration_error(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "docs/adr/4.x/2026-02-02-1-y.md", "---\ntitle: Y\nstatus: Rejected\n---\n")
    assert mig.main(["--docs-root", str(repo / "docs"), "--repo-root", str(repo), "--check"]) == 2
    assert "no doc_status mapping" in capsys.readouterr().err


def test_verify_against_flags_a_body_change_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path
    _write(repo, "docs/a.md", "---\ntitle: A\n---\nbody\n")
    _write(repo, "docs/b.md", "---\ntitle: B\n---\nbody\n")
    base = init_git_repo_with_base(repo)
    _write(repo, "docs/a.md", "---\ntitle: A\nkind: ADR\n---\nbody\n")
    _write(repo, "docs/b.md", "---\ntitle: B\n---\nbody changed\n")
    _write(repo, "docs/new.md", "---\ntitle: N\n---\nnew\n")
    commit_all_changes(repo, "change")
    (repo / "docs" / "b.md").rename(repo / "docs" / "c.md")
    commit_all_changes(repo, "rename")
    assert mig.verify_against(repo_root=repo, ref=base) == ["docs/c.md"]
    assert mig.main(["--repo-root", str(repo), "--verify-against", base]) == 1
    assert "docs/c.md" in capsys.readouterr().out


@pytest.mark.slow
def test_real_corpus_apply_then_check_is_a_fixed_point(tmp_path: Path) -> None:
    """Idempotency on the real ``docs/`` tree: after ``--apply``, a second run changes nothing."""
    import shutil

    repo_root = Path(__file__).resolve().parents[2]
    docs = tmp_path / "docs"
    shutil.copytree(repo_root / "docs", docs)
    first = mig.migrate_tree(docs_root=docs, repo_root=repo_root, write=True)
    second = mig.migrate_tree(docs_root=docs, repo_root=repo_root, write=False)
    assert first.changed_files or second.changed_files == []
    assert second.changed_files == []
