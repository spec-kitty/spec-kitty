"""Self-test for the ``audience:`` frontmatter resolver (WP02 / IC-01 / FR-003).

The resolver validates doc-kitty's ``audience: [{profile, guidance_text}]``
shape (#6929): every catalog-shaped profile (``internal/...``/``external/...``)
must name a persona page under ``docs/context/audience/``, while free-text
profiles are examined but never dangle. This self-test is the real Definition
of Done: a ruler that cannot go RED is fake. We therefore prove that

* a deliberately-**dangling** profile is detected (and reds under ``--strict``);
* a clean tree of resolvable profiles reports **no** dangling refs;
* an old path string or an entry missing a field is reported as **malformed**;
* a walk that examines **zero** ``audience:`` entries reds on the non-vacuity
  floor rather than passing vacuously; and
* **free-text** profiles are examined but never dangle.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.docs.audience_resolver import (
    DanglingReference,
    MalformedAudience,
    main,
    resolve_audiences,
)
from tests.docs.conftest import commit_all_changes, init_git_repo_with_base

pytestmark = pytest.mark.architectural

_PERSONA_REL = "docs/context/audience/internal/maintainer.md"
_PERSONA = "internal/maintainer"
_MISSING = "internal/does-not-exist"


def _aud(*profiles: str) -> list[str]:
    """Frontmatter lines for an ``audience:`` list naming *profiles*."""
    lines = ["audience:"]
    for profile in profiles:
        lines += [f"  - profile: {profile}", f"    guidance_text: Written for {profile}."]
    return lines


def _write(path: Path, frontmatter: list[str], body: str = "x") -> None:
    """Write a markdown page with the given frontmatter lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", 'title: "page"', *frontmatter, "---", "", f"# {body}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _stage_catalog(repo: Path) -> None:
    """Create the persona file a valid ``audience:`` reference resolves to."""
    _write(repo / _PERSONA_REL, ["doc_status: active"], body="maintainer")


def _stage_repo(tmp_path: Path, *, audience: list[str], dangling: bool) -> Path:
    """Stage a repo-shaped tree; ``audience`` is the page's frontmatter block."""
    repo = tmp_path / "repo"
    _stage_catalog(repo)
    if dangling:
        # Reference a persona file that is never created.
        pass
    _write(repo / "docs" / "page.md", audience, body="page")
    return repo


def test_dangling_reference_is_detected(tmp_path: Path) -> None:
    """A ``.md`` ``audience:`` value with no catalog file surfaces as dangling."""
    repo = _stage_repo(
        tmp_path,
        audience=_aud(_MISSING),
        dangling=True,
    )

    report = resolve_audiences(docs_root=repo / "docs", repo_root=repo)

    assert report.checked_count > 0
    assert DanglingReference(from_path="docs/page.md", to_path=_MISSING) in report.dangling_references


def test_valid_profile_resolves(tmp_path: Path) -> None:
    """An ``audience:`` profile naming a catalog persona is clean."""
    repo = _stage_repo(
        tmp_path,
        audience=_aud(_PERSONA),
        dangling=False,
    )

    report = resolve_audiences(docs_root=repo / "docs", repo_root=repo)

    assert report.checked_count > 0
    assert report.dangling_references == []


def test_valid_profile_list_resolves(tmp_path: Path) -> None:
    """An ``audience:`` list whose profiles all resolve reports zero dangling."""
    repo = _stage_repo(
        tmp_path,
        audience=_aud(_PERSONA, _PERSONA),
        dangling=False,
    )

    report = resolve_audiences(docs_root=repo / "docs", repo_root=repo)

    assert report.checked_count > 0
    assert report.dangling_references == []


def test_free_text_value_is_examined_but_not_dangling(tmp_path: Path) -> None:
    """A free-text profile (no catalog prefix) counts but never dangles."""
    repo = _stage_repo(
        tmp_path,
        audience=_aud("end-users"),
        dangling=False,
    )

    report = resolve_audiences(docs_root=repo / "docs", repo_root=repo)

    assert report.checked_count == 1
    assert report.dangling_references == []


@pytest.mark.parametrize(
    ("lines", "detail"),
    [
        ([f"audience: {_PERSONA_REL}"], "not a list"),
        (["audience:", f"  - {_PERSONA_REL}"], "not a {profile, guidance_text} mapping"),
        (["audience:", f"  - profile: {_PERSONA}"], "missing guidance_text"),
        (["audience:", "  - guidance_text: x"], "missing profile"),
    ],
)
def test_old_or_incomplete_shape_is_malformed(tmp_path: Path, lines: list[str], detail: str) -> None:
    """The pre-#6929 path-string form and incomplete entries are reported, and red ``--strict``."""
    repo = _stage_repo(tmp_path, audience=lines, dangling=False)

    report = resolve_audiences(docs_root=repo / "docs", repo_root=repo)

    assert report.malformed_entries == [MalformedAudience(from_path="docs/page.md", detail=detail)]
    assert main(["--repo-root", str(repo), "--docs-root", str(repo / "docs"), "--strict"]) == 1


def test_profile_escaping_the_catalog_is_dangling(tmp_path: Path) -> None:
    """A catalog-shaped profile that climbs out of ``docs/context/audience/`` never resolves."""
    repo = _stage_repo(tmp_path, audience=_aud("internal/../../charter"), dangling=False)

    report = resolve_audiences(docs_root=repo / "docs", repo_root=repo)

    assert DanglingReference(from_path="docs/page.md", to_path="internal/../../charter") in report.dangling_references


def test_zero_examined_walk_raises(tmp_path: Path) -> None:
    """A walk that examines no ``audience:`` values reds instead of passing vacuously.

    Mirrors the ``related_validator`` floor (FR-008): a scope-narrowing
    regression — an ``audience:``-free or markdown-free tree — must go RED, not
    report "0 dangling" over 0 checked.
    """
    repo = tmp_path / "repo"
    docs = repo / "docs"
    _write(docs / "no-audience.md", ["doc_status: active"], body="untagged")

    with pytest.raises(RuntimeError, match="expected at least"):
        resolve_audiences(docs_root=docs, repo_root=repo)


def test_missing_docs_root_raises(tmp_path: Path) -> None:
    """A non-existent docs tree trips the same non-vacuity floor."""
    with pytest.raises(RuntimeError, match="expected at least"):
        resolve_audiences(docs_root=tmp_path / "absent", repo_root=tmp_path)


def test_strict_flag_reds_on_dangling(tmp_path: Path) -> None:
    """The wired ``--strict`` flag turns a dangling reference into a non-zero exit."""
    repo = _stage_repo(
        tmp_path,
        audience=_aud(_MISSING),
        dangling=True,
    )

    exit_code = main(["--repo-root", str(repo), "--docs-root", str(repo / "docs"), "--strict"])

    assert exit_code != 0


def test_strict_flag_stays_green_on_clean_tree(tmp_path: Path) -> None:
    """``--strict`` does not red a tree whose references all resolve."""
    repo = _stage_repo(
        tmp_path,
        audience=_aud(_PERSONA),
        dangling=False,
    )

    exit_code = main(["--repo-root", str(repo), "--docs-root", str(repo / "docs"), "--strict"])

    assert exit_code == 0


def test_report_only_exit_zero_even_when_dangling(tmp_path: Path) -> None:
    """Default invocation is report-only: dangling references still exit 0."""
    repo = _stage_repo(
        tmp_path,
        audience=_aud(_MISSING),
        dangling=True,
    )

    exit_code = main(["--repo-root", str(repo), "--docs-root", str(repo / "docs")])

    assert exit_code == 0


class TestDiffScopeAudienceCLI:
    """``--changed-from`` behavior through :func:`main` over real git repos."""

    def test_changed_dangling_reference_reds(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _stage_catalog(repo)
        base_sha = init_git_repo_with_base(repo)
        _write(
            repo / "docs" / "changed.md",
            _aud(_MISSING),
            body="changed",
        )
        commit_all_changes(repo, "add dangling audience reference")

        exit_code = main(
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

        assert exit_code == 1

    def test_changed_unicode_path_dangling_reference_reds(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _stage_catalog(repo)
        base_sha = init_git_repo_with_base(repo)
        _write(
            repo / "docs" / "café.md",
            _aud(_MISSING),
            body="changed",
        )
        commit_all_changes(repo, "add Unicode dangling audience reference")

        exit_code = main(
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

        assert exit_code == 1

    def test_unchanged_preexisting_dangling_reference_passes(self, tmp_path: Path) -> None:
        repo = _stage_repo(
            tmp_path,
            audience=_aud(_MISSING),
            dangling=True,
        )
        base_sha = init_git_repo_with_base(repo)
        _write(
            repo / "docs" / "changed.md",
            _aud(_PERSONA),
            body="changed",
        )
        commit_all_changes(repo, "add clean audience reference")

        exit_code = main(
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

        assert exit_code == 0

    def test_resolved_zero_docs_passes(self, tmp_path: Path) -> None:
        repo = _stage_repo(
            tmp_path,
            audience=_aud(_MISSING),
            dangling=True,
        )
        base_sha = init_git_repo_with_base(repo)
        (repo / "README.md").write_text("# changed\n", encoding="utf-8")
        commit_all_changes(repo, "change non-docs file")

        exit_code = main(
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

        assert exit_code == 0

    def test_unresolvable_base_errors(self, tmp_path: Path) -> None:
        repo = _stage_repo(
            tmp_path,
            audience=_aud(_PERSONA),
            dangling=False,
        )
        init_git_repo_with_base(repo)

        exit_code = main(
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

        assert exit_code == 2


def test_json_report_carries_dangling_and_malformed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--json`` emits both lists in the contract shape."""
    repo = _stage_repo(tmp_path, audience=_aud(_MISSING), dangling=True)
    _write(repo / "docs" / "old.md", [f"audience: {_PERSONA_REL}"], body="old")

    main(["--repo-root", str(repo), "--docs-root", str(repo / "docs"), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["dangling_references"] == [{"from": "docs/page.md", "to": _MISSING}]
    assert payload["malformed_entries"] == [{"from": "docs/old.md", "detail": "not a list"}]


def test_human_report_names_malformed_entries(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _stage_repo(tmp_path, audience=[f"audience: {_PERSONA_REL}"], dangling=False)

    main(["--repo-root", str(repo), "--docs-root", str(repo / "docs")])

    assert "MALFORMED docs/page.md: not a list" in capsys.readouterr().out


def test_unreadable_page_is_skipped(tmp_path: Path) -> None:
    """A ``*.md`` path that cannot be read (here a directory) is skipped, not crashed on."""
    repo = _stage_repo(tmp_path, audience=_aud(_PERSONA), dangling=False)
    (repo / "docs" / "folder.md").mkdir()

    report = resolve_audiences(docs_root=repo / "docs", repo_root=repo)

    assert report.checked_count == 1
    assert not report.failed
