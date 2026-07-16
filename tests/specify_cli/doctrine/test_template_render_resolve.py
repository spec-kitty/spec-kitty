"""Unit tests for TEMPLATE parse / resolve (WP01 T003/T004)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from specify_cli.doctrine.sources.protocol import FetchResult
from specify_cli.doctrine.template_render.resolve import (
    RULE_BRANCH_CONFLICT,
    RULE_TEMPLATE_GIT_FETCH,
    RULE_TEMPLATE_MISSING,
    merge_branch_refs,
    parse_template_ref,
    resolve_template_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_parse_local_path() -> None:
    parsed = parse_template_ref("~/projects/doctrine-template")
    assert parsed.kind == "local"
    assert parsed.location == "~/projects/doctrine-template"
    assert parsed.encoded_ref is None


def test_parse_https_with_fragment() -> None:
    parsed = parse_template_ref("https://github.com/org/repo.git#main")
    assert parsed.kind == "git"
    assert parsed.location == "https://github.com/org/repo.git"
    assert parsed.encoded_ref == "main"


def test_parse_https_with_at_ref() -> None:
    parsed = parse_template_ref("https://github.com/org/repo.git@develop")
    assert parsed.kind == "git"
    assert parsed.location == "https://github.com/org/repo.git"
    assert parsed.encoded_ref == "develop"


def test_parse_ssh_url_with_fragment() -> None:
    parsed = parse_template_ref("ssh://git@github.com/org/repo.git#main")
    assert parsed.kind == "git"
    assert parsed.location == "ssh://git@github.com/org/repo.git"
    assert parsed.encoded_ref == "main"


def test_parse_ssh_url_at_ref_preserves_git_userinfo_and_slash_branch() -> None:
    """ssh:// with git@ userinfo and feat/... branch via @ref."""
    template = (
        "ssh://git@git.example.com:7999/org/doctrine-template.git"
        "@feat/make-embeddable-template"
    )
    parsed = parse_template_ref(template)
    assert parsed.kind == "git"
    assert parsed.location == (
        "ssh://git@git.example.com:7999/org/doctrine-template.git"
    )
    assert parsed.encoded_ref == "feat/make-embeddable-template"


def test_parse_https_at_ref_allows_slash_in_branch() -> None:
    parsed = parse_template_ref(
        "https://github.com/org/repo.git@feat/make-embeddable-template"
    )
    assert parsed.kind == "git"
    assert parsed.location == "https://github.com/org/repo.git"
    assert parsed.encoded_ref == "feat/make-embeddable-template"


def test_parse_scp_git_at_does_not_eat_userinfo() -> None:
    parsed = parse_template_ref("git@github.com:org/repo.git")
    assert parsed.kind == "git"
    assert parsed.location == "git@github.com:org/repo.git"
    assert parsed.encoded_ref is None


def test_merge_branch_conflict() -> None:
    ref, err = merge_branch_refs("main", "develop")
    assert ref is None
    assert err is not None
    assert err.rule_id == RULE_BRANCH_CONFLICT
    assert "main" in err.message
    assert "develop" in err.message


def test_merge_branch_equal_dual_ok() -> None:
    ref, err = merge_branch_refs("main", "main")
    assert err is None
    assert ref == "main"


def test_merge_branch_option_only() -> None:
    ref, err = merge_branch_refs(None, "feature")
    assert err is None
    assert ref == "feature"


def test_resolve_local_ok(tmp_path: Path) -> None:
    root = tmp_path / "tpl"
    root.mkdir()
    source, err = resolve_template_source(str(root))
    assert err is None
    assert source is not None
    assert source.kind == "local"
    assert source.root == root.resolve()
    assert source.cleanup is False


def test_resolve_local_folder_template_tree(tmp_path: Path) -> None:
    """Local TEMPLATE is a real directory tree (operator local-folder path)."""
    root = tmp_path / "doctrine-template"
    (root / "pack").mkdir(parents=True)
    (root / "pack" / "org-charter.yaml").write_text(
        'org_name: "{{ORG_NAME}}"\n', encoding="utf-8"
    )
    (root / ".templateignore").write_text(".git/\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")

    source, err = resolve_template_source(str(root))
    assert err is None
    assert source is not None
    assert source.kind == "local"
    assert source.root == root.resolve()
    assert (source.root / "pack" / "org-charter.yaml").is_file()
    assert source.cleanup is False


def test_resolve_local_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    source, err = resolve_template_source(str(missing))
    assert source is None
    assert err is not None
    assert err.rule_id == RULE_TEMPLATE_MISSING


def test_resolve_git_uses_factory(tmp_path: Path) -> None:
    calls: dict[str, Any] = {}

    class FakeGitSource:
        def __init__(self, url: str, ref: str | None = None) -> None:
            calls["url"] = url
            calls["ref"] = ref

        def fetch(self, target_dir: Path) -> FetchResult:
            calls["target"] = target_dir
            (target_dir / "pack").mkdir()
            return FetchResult(ok=True, artifacts_written=1, pack_version="abc", errors=[])

    source, err = resolve_template_source(
        "https://example.com/org/repo.git#main",
        branch=None,
        git_source_factory=FakeGitSource,
    )
    assert err is None
    assert source is not None
    assert source.kind == "git"
    assert source.cleanup is True
    assert source.ref == "main"
    assert calls["url"] == "https://example.com/org/repo.git"
    assert calls["ref"] == "main"
    assert source.root.exists()


def test_resolve_ssh_url_at_ref_branch(tmp_path: Path) -> None:
    """ssh://git@…@feat/… splits URL vs ref and passes both to GitSource."""
    calls: dict[str, Any] = {}
    template = (
        "ssh://git@git.example.com:7999/org/doctrine-template.git"
        "@feat/make-embeddable-template"
    )

    class FakeGitSource:
        def __init__(self, url: str, ref: str | None = None) -> None:
            calls["url"] = url
            calls["ref"] = ref

        def fetch(self, target_dir: Path) -> FetchResult:
            (target_dir / "pack").mkdir()
            (target_dir / "pack" / "org-charter.yaml").write_text(
                'org_name: "{{ORG_NAME}}"\nlocal: "{{LOCAL_PATH}}"\n',
                encoding="utf-8",
            )
            return FetchResult(ok=True, artifacts_written=1, pack_version="abc", errors=[])

    source, err = resolve_template_source(
        template,
        branch=None,
        git_source_factory=FakeGitSource,
    )
    assert err is None
    assert source is not None
    assert source.kind == "git"
    assert source.ref == "feat/make-embeddable-template"
    assert calls["url"] == (
        "ssh://git@git.example.com:7999/org/doctrine-template.git"
    )
    assert calls["ref"] == "feat/make-embeddable-template"
    assert (source.root / "pack" / "org-charter.yaml").is_file()
    shutil.rmtree(source.root, ignore_errors=True)


def test_resolve_git_fetch_failure() -> None:
    class FailingGitSource:
        def __init__(self, url: str, ref: str | None = None) -> None:
            pass

        def fetch(self, target_dir: Path) -> FetchResult:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=["clone exploded"],
            )

    source, err = resolve_template_source(
        "https://example.com/org/repo.git",
        branch="main",
        git_source_factory=FailingGitSource,
    )
    assert source is None
    assert err is not None
    assert err.rule_id == RULE_TEMPLATE_GIT_FETCH
    assert "clone exploded" in err.message


def test_resolve_branch_conflict_short_circuits() -> None:
    source, err = resolve_template_source(
        "https://example.com/org/repo.git#main",
        branch="other",
    )
    assert source is None
    assert err is not None
    assert err.rule_id == RULE_BRANCH_CONFLICT
