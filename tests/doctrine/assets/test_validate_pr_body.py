"""Behaviour of the internal ``validate-pr-body`` asset (the PR-body contract check).

The validator is a maintainer asset in ``packs/internal/assets/``; these tests
load it by path and drive ``main`` the way a landing runner does, with a valid
body as the control and one mutation per rule.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit]

_ASSET = Path(__file__).resolve().parents[3] / "packs" / "internal" / "assets" / "validate-pr-body.py"
_MODULE_NAME = "validate_pr_body_asset"

_VALID = """\
<!-- template comment
## Bogus
-->
## Issue

Closes #42

## Change

Does a thing.

## Tests run

```
uv run python -m scripts.docs.check_docs_freshness --ci  # 1 passed
PYTHONPATH=$PWD/src python -m pytest tests/doctrine/assets/test_x.py -q  # 3 passed
```

Self-review:
- read the diff, fine

## Blast radius

Discovery: `git grep -l needle`
Files:
- a.txt
- `sub/b.txt`

## Deferred

- None.
"""


@pytest.fixture(scope="module")
def validator() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_MODULE_NAME, _ASSET)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _MODULE_NAME, module)
        spec.loader.exec_module(module)
        yield module


def _check(validator: ModuleType, body: str) -> list[str]:
    result: list[str] = validator.validate(body)
    return result


def test_valid_body_has_no_violations(validator: ModuleType) -> None:
    assert _check(validator, _VALID) == []


def test_asset_is_executable_and_sidecar_matches() -> None:
    assert _ASSET.stat().st_mode & 0o111
    sidecar = _ASSET.with_name(_ASSET.name + ".asset.yaml").read_text(encoding="utf-8")
    assert "id: validate-pr-body" in sidecar
    assert "mime: text/x-python" in sidecar
    assert "path: validate-pr-body.py" in sidecar


def test_missing_section_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("## Deferred\n\n- None.\n", "")
    assert _check(validator, body) == ["structure: missing section `## Deferred`"]


def test_extra_section_is_reported(validator: ModuleType) -> None:
    body = _VALID + "\n## Summary\n\nx\n"
    assert _check(validator, body) == ["structure: unexpected section `## Summary`"]


def test_out_of_order_sections_are_reported(validator: ModuleType) -> None:
    body = _VALID.replace("## Change", "## TMP").replace("## Issue", "## Change").replace("## TMP", "## Issue")
    problems = [p for p in _check(validator, body) if p.startswith("structure:")]
    assert len(problems) == 1
    assert problems[0].startswith("structure: sections out of order")


def test_level_three_headings_and_fenced_headings_are_not_sections(validator: ModuleType) -> None:
    body = _VALID.replace("Does a thing.", "### Detail\n\n```\n## not a section\n```")
    assert _check(validator, body) == []


@pytest.mark.parametrize("text", ["closes #7", "CLOSES #7", "Closes #7"])
def test_closes_link_is_case_insensitive(validator: ModuleType, text: str) -> None:
    assert _check(validator, _VALID.replace("Closes #42", text)) == []


@pytest.mark.parametrize("text", ["see #42", "closes 42", "fixes #42", "closes #"])
def test_missing_closes_link_is_reported(validator: ModuleType, text: str) -> None:
    assert _check(validator, _VALID.replace("Closes #42", text)) == ["Issue: missing `closes #<n>` link"]


def test_missing_self_review_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("Self-review:\n- read the diff, fine\n", "")
    assert _check(validator, body) == ["Tests run: missing nested `Self-review:` block"]


def test_empty_self_review_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("- read the diff, fine\n", "")
    assert _check(validator, body) == ["Tests run: `Self-review:` block has no entries"]


def test_bare_doc_script_path_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("uv run python -m scripts.docs.check_docs_freshness --ci", "python scripts/docs/check_docs_freshness.py --ci")
    problems = _check(validator, body)
    assert len(problems) == 1
    assert problems[0].startswith("Tests run: bare doc-script path")
    assert "scripts.docs.<x>" in problems[0]


def test_bare_doc_script_in_inline_code_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("Self-review:\n", "Also ran `python scripts/docs/description_length_check.py`.\n\nSelf-review:\n")
    assert any(p.startswith("Tests run: bare doc-script path") for p in _check(validator, body))


def test_pytest_target_outside_tests_or_docs_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("tests/doctrine/assets/test_x.py", "doctrine/assets/test_x.py")
    assert _check(validator, body) == ["Tests run: pytest target `doctrine/assets/test_x.py` must start with `tests/` or `docs/`"]


def test_pytest_options_and_docs_targets_are_accepted(validator: ModuleType) -> None:
    body = _VALID.replace("tests/doctrine/assets/test_x.py -q", "-n0 -k foo --ignore=x/y docs/a/test_b.py::test_c tests/z")
    assert _check(validator, body) == []


def test_unparseable_command_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("# 3 passed", "'unterminated")
    assert any(p.startswith("Tests run: cannot parse command") for p in _check(validator, body))


def test_missing_discovery_and_files_are_reported(validator: ModuleType) -> None:
    body = _VALID.replace("Discovery: `git grep -l needle`\nFiles:\n- a.txt\n- `sub/b.txt`\n", "Nothing.\n")
    assert _check(validator, body) == [
        "Blast radius: missing `Discovery:` line",
        "Blast radius: missing `Files:` list",
    ]


def test_empty_files_list_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("- a.txt\n- `sub/b.txt`\n", "")
    assert _check(validator, body) == ["Blast radius: `Files:` list is empty"]


# --- CLI ---------------------------------------------------------------------


def test_cli_exit_codes_and_output(validator: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = tmp_path / "good.md"
    good.write_text(_VALID, encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text(_VALID.replace("Closes #42", "nope"), encoding="utf-8")

    assert validator.main([str(good)]) == 0
    assert capsys.readouterr().out == ""
    assert validator.main([str(bad)]) == 1
    assert capsys.readouterr().out == "Issue: missing `closes #<n>` link\n"


def test_cli_reads_stdin(validator: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(_VALID))
    assert validator.main(["-"]) == 0


def test_cli_unreadable_body_exits_two(validator: ModuleType, tmp_path: Path) -> None:
    assert validator.main([str(tmp_path / "missing.md")]) == 2


@pytest.mark.parametrize("extra", [["--verify-discovery"], ["--expected-head", "abc"], ["--bogus"]])
def test_cli_usage_errors_exit_two(validator: ModuleType, tmp_path: Path, extra: list[str]) -> None:
    good = tmp_path / "good.md"
    good.write_text(_VALID, encoding="utf-8")
    with pytest.raises(SystemExit) as info:
        validator.main([str(good), *extra])
    assert info.value.code == 2


def test_help_documents_exit_codes() -> None:
    result = subprocess.run([sys.executable, str(_ASSET), "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "--verify-discovery" in result.stdout
    assert "usage error" in result.stdout


# --- --verify-discovery ------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "repo"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("needle\n", encoding="utf-8")
    (root / "sub" / "b.txt").write_text("needle\n", encoding="utf-8")
    (root / "c.txt").write_text("hay\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    yield root


@pytest.fixture
def verify(validator: ModuleType, repo: Path, tmp_path: Path) -> Callable[..., int]:
    def _verify(body: str, head: str | None = None) -> int:
        path = tmp_path / "body.md"
        path.write_text(body, encoding="utf-8")
        sha = head if head is not None else _git(repo, "rev-parse", "HEAD")
        return int(validator.main([str(path), "--verify-discovery", "--expected-head", sha, "--repo", str(repo)]))

    return _verify


def test_verify_discovery_passes_on_matching_files(verify: Callable[..., int]) -> None:
    assert verify(_VALID) == 0


def test_verify_discovery_accepts_abbreviated_head(verify: Callable[..., int], repo: Path) -> None:
    assert verify(_VALID, head=_git(repo, "rev-parse", "--short", "HEAD")) == 0


def test_verify_discovery_reports_missing_and_extra(validator: ModuleType, repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    body = _VALID.replace("- `sub/b.txt`", "- ghost.txt")
    problems = validator.validate(body, expected_head=sha, repo=repo)
    assert problems == [
        "Blast radius: Files lists `ghost.txt` but Discovery does not find it",
        "Blast radius: Discovery finds `sub/b.txt` missing from Files",
    ]


def test_verify_discovery_rejects_wrong_head(validator: ModuleType, repo: Path) -> None:
    problems = validator.validate(_VALID, expected_head="deadbeef", repo=repo)
    assert len(problems) == 1
    assert "!= expected head deadbeef" in problems[0]


def test_verify_discovery_handles_content_grep_output(validator: ModuleType, repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    body = _VALID.replace("git grep -l needle", "git grep needle")
    assert validator.validate(body, expected_head=sha, repo=repo) == []


def test_verify_discovery_no_matches_means_empty_fresh_set(validator: ModuleType, repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    body = _VALID.replace("git grep -l needle", "git grep -l absent")
    problems = validator.validate(body, expected_head=sha, repo=repo)
    assert problems == [
        "Blast radius: Files lists `a.txt` but Discovery does not find it",
        "Blast radius: Files lists `sub/b.txt` but Discovery does not find it",
    ]


@pytest.mark.parametrize("command", ["rm -rf .", "git log", "echo hi", "grep -l needle ."])
def test_verify_discovery_refuses_non_git_grep(validator: ModuleType, repo: Path, command: str) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    body = _VALID.replace("git grep -l needle", command)
    problems = validator.validate(body, expected_head=sha, repo=repo)
    assert len(problems) == 1
    assert "refusing to run" in problems[0]


@pytest.mark.parametrize("command", ["git grep -l needle | xargs rm", "git grep -l needle; touch pwned", "git grep -l needle > out"])
def test_verify_discovery_refuses_shell_operators(validator: ModuleType, repo: Path, command: str) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    body = _VALID.replace("git grep -l needle", command)
    problems = validator.validate(body, expected_head=sha, repo=repo)
    assert len(problems) == 1
    assert "refusing to run" in problems[0]
    assert not (repo / "pwned").exists()
    assert not (repo / "out").exists()


def test_verify_discovery_reports_git_failure(validator: ModuleType, repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    body = _VALID.replace("git grep -l needle", "git grep --bogus-flag needle")
    problems = validator.validate(body, expected_head=sha, repo=repo)
    assert len(problems) == 1
    assert problems[0].startswith("Blast radius: Discovery command failed")


def test_verify_discovery_outside_git_repo_is_reported(validator: ModuleType, tmp_path: Path) -> None:
    empty = tmp_path / "plain"
    empty.mkdir()
    problems = validator.validate(_VALID, expected_head="abc", repo=empty)
    assert problems == ["Blast radius: cannot read `git rev-parse HEAD` in the checkout"]


# --- the shipped template ----------------------------------------------------

_TEMPLATE = Path(__file__).resolve().parents[3] / ".github" / "PULL_REQUEST_TEMPLATE.md"


def test_unmodified_template_is_rejected_for_its_placeholders(validator: ModuleType) -> None:
    problems = _check(validator, _TEMPLATE.read_text(encoding="utf-8"))

    assert "Issue: missing `closes #<n>` link" in problems
    assert "Change: section is empty" in problems
    assert any(p.startswith("Tests run: template placeholder left in command `<command>") for p in problems)
    assert "Tests run: `Self-review:` block still holds the template placeholder" in problems
    assert any(p.startswith("Blast radius: `Discovery:` still holds the template placeholder") for p in problems)
    assert "Blast radius: `Files:` still holds the template placeholder" in problems
    assert not any(p.startswith("structure:") for p in problems)


def test_template_with_placeholders_filled_in_is_accepted(validator: ModuleType) -> None:
    body = (
        _TEMPLATE.read_text(encoding="utf-8")
        .replace("closes #<n>", "closes #7")
        .replace("<command>  # <N passed, M failed>", "python -m pytest tests/x -q  # 3 passed")
        .replace("- <what you checked in your own diff, and the result>", "- checked the diff")
        .replace("`<git grep command used to find affected code>`", "`git grep -l x`")
        .replace("- <paths re-derived from a fresh run of the discovery command>", "- a.txt")
        .replace("## Change\n", "## Change\n\nDoes a thing.\n")
    )

    assert _check(validator, body) == []


def test_placeholder_only_in_a_single_slot_is_reported(validator: ModuleType) -> None:
    body = _VALID.replace("- read the diff, fine", "- <what you checked>")
    assert _check(validator, body) == ["Tests run: `Self-review:` block still holds the template placeholder"]


def test_empty_change_section_is_reported(validator: ModuleType) -> None:
    assert _check(validator, _VALID.replace("Does a thing.\n", "")) == ["Change: section is empty"]
