"""Behavior of the docs spelling check (issue #5426, part 1).

Every fixture-tree test builds a throwaway repo under ``tmp_path`` that carries the real
``pyproject.toml``, so the shipped ``[tool.codespell]`` table is the one under test. Each
"not reported" assertion is paired with a same-fixture "reported" assertion, so a check that
silently scans nothing cannot pass.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

from scripts.docs import check_spelling as cs
from scripts.docs.check_spelling import (
    Finding,
    PassResult,
    SpellcheckError,
    main,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CODESPELL_PIN: Final[str] = "2.4.3"


def test_pin_is_exact_in_dev_group_and_lockfile() -> None:
    """NFR-002: the dictionary is behavior, so the pin is exact in both files."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert f"codespell=={CODESPELL_PIN}" in pyproject["dependency-groups"]["dev"]

    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = [package["version"] for package in lock["package"] if package["name"] == "codespell"]
    assert versions == [CODESPELL_PIN]
    assert "codespell" in pyproject["tool"], "[tool.codespell] must own the dictionary config"


# ---------------------------------------------------------------------------
# T010: runner core and CLI
# ---------------------------------------------------------------------------

REAL_PYPROJECT: Final[Path] = REPO_ROOT / "pyproject.toml"


def make_repo(root: Path, files: dict[str, str]) -> Path:
    """Build a fixture repo under *root* that carries the REAL ``pyproject.toml``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(REAL_PYPROJECT.read_text(encoding="utf-8"), encoding="utf-8")
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


class _FakeRun:
    """A stand-in for ``subprocess.run`` that records calls and replays a canned result."""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, "")


def test_parse_output_extracts_path_line_word_and_fix() -> None:
    findings = cs._parse_output("docs/x.md:12: behaviour ==> behavior\n", "us-spelling", {})
    assert findings == [
        Finding(
            severity="error",
            rule="us-spelling",
            path="docs/x.md",
            line=12,
            where="behaviour",
            fix="behavior",
        )
    ]


def test_parse_output_keeps_every_suggestion_and_maps_paths(tmp_path: Path) -> None:
    scratch = str(tmp_path / "unreleased.md")
    out = f"{scratch}:3: reding ==> reading, redding\nnoise that is not a finding\n"
    findings = cs._parse_output(out, "typo", {scratch: "docs/changelog/CHANGELOG.md"})
    assert [(f.path, f.line, f.where, f.fix) for f in findings] == [("docs/changelog/CHANGELOG.md", 3, "reding", "reading, redding")]


def test_cmd_names_the_module_the_config_and_every_file() -> None:
    cmd = cs._codespell_cmd(Path("/r"), ["-L", "x"], ["a.md", "b.md"])
    assert cmd[1:3] == ["-m", "codespell_lib"]
    assert cmd[3:5] == ["--toml", str(Path("/r") / "pyproject.toml")]
    assert cmd[5:] == ["-L", "x", "a.md", "b.md"]


def test_cmd_refuses_zero_files_because_codespell_would_scan_the_whole_tree() -> None:
    with pytest.raises(SpellcheckError, match="zero file"):
        cs._codespell_cmd(Path("/r"), [], [])


@pytest.mark.parametrize(("returncode", "expected"), [(0, ""), (65, "docs/x.md:1: reding ==> reading\n")])
def test_run_codespell_accepts_exit_codes_0_and_65(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, returncode: int, expected: str) -> None:
    fake = _FakeRun(returncode=returncode, stdout=expected)
    monkeypatch.setattr(subprocess, "run", fake)
    assert cs._run_codespell(["codespell"], tmp_path) == expected
    _, kwargs = fake.calls[0]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True


def test_run_codespell_rejects_any_other_exit_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", _FakeRun(returncode=2, stdout=""))
    with pytest.raises(SpellcheckError, match="exit code 2"):
        cs._run_codespell(["codespell"], tmp_path)


def test_exit_65_with_no_parsable_finding_is_an_error_not_a_green(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", _FakeRun(returncode=65, stdout="garbled\n"))
    with pytest.raises(SpellcheckError, match="could not be parsed"):
        cs._scan(tmp_path, ["docs/a.md"], (), "typo")


def test_zero_files_never_calls_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    make_repo(tmp_path, {})
    fake = _FakeRun()
    monkeypatch.setattr(subprocess, "run", fake)
    result = cs._scan(tmp_path, [], (), "typo")
    assert result == PassResult(name="typo", findings=(), scanned=0)
    assert fake.calls == []


def test_files_are_batched_at_most_150_per_invocation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    make_repo(tmp_path, {})
    fake = _FakeRun()
    monkeypatch.setattr(subprocess, "run", fake)
    files = [f"docs/f{i:03}.md" for i in range(401)]
    result = cs._scan(tmp_path, files, (), "typo")
    sizes = [len([arg for arg in cmd if arg.startswith("docs/")]) for cmd, _ in fake.calls]
    assert sizes == [150, 150, 101]
    assert result.scanned == 401


def test_missing_codespell_table_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert main(["--repo-root", str(tmp_path), "--pass", "typo"]) == 2
    assert "[tool.codespell]" in capsys.readouterr().err


def test_missing_pyproject_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--repo-root", str(tmp_path), "--pass", "typo"]) == 2
    assert "pyproject.toml" in capsys.readouterr().err


def test_codespell_not_installed_says_how_to_fix_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_repo(tmp_path, {})
    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: None if name == "codespell_lib" else real_find_spec(name, *a, **k),
    )
    assert main(["--repo-root", str(tmp_path), "--pass", "typo"]) == 2
    assert "uv sync --frozen" in capsys.readouterr().err


def test_unknown_pass_is_rejected_by_argparse() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--pass", "bogus"])
    assert excinfo.value.code == 2


def _finding(path: str, line: int, rule: str, word: str, fix: str) -> Finding:
    return Finding(severity="error", rule=rule, path=path, line=line, where=word, fix=fix)


def _stub_passes(monkeypatch: pytest.MonkeyPatch, results: dict[str, PassResult]) -> list[str]:
    ran: list[str] = []

    def fake_run_pass(name: str, repo_root: Path, changelog: Path) -> PassResult:
        ran.append(name)
        return results[name]

    monkeypatch.setattr(cs, "run_pass", fake_run_pass)
    return ran


def test_main_prints_sorted_findings_and_scanned_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_repo(tmp_path, {})
    results = {
        "typo": PassResult("typo", (_finding("docs/b.md", 2, "typo", "reding", "reading"),), 4),
        "us": PassResult("us", (_finding("docs/a.md", 9, "us-spelling", "behaviour", "behavior"),), 2),
        "unreleased": PassResult("unreleased", (), 30),
    }
    ran = _stub_passes(monkeypatch, results)
    assert main(["--repo-root", str(tmp_path)]) == 1
    assert ran == ["typo", "us", "unreleased"]
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "docs/a.md:9: [us-spelling] behaviour \u2014 fix: behavior",
        "docs/b.md:2: [typo] reding \u2014 fix: reading",
        "2 finding(s) across 2 file(s); scanned: typo=4 file(s), us=2 file(s), unreleased=30 line(s)",
    ]


def test_main_exits_zero_and_reports_only_the_passes_that_ran(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_repo(tmp_path, {})
    ran = _stub_passes(monkeypatch, {"us": PassResult("us", (), 5)})
    assert main(["--repo-root", str(tmp_path), "--pass", "us"]) == 0
    assert ran == ["us"]
    assert capsys.readouterr().out.strip() == "0 finding(s) across 0 file(s); scanned: us=5 file(s)"


def test_main_turns_a_runner_failure_into_exit_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_repo(tmp_path, {})

    def boom(name: str, repo_root: Path, changelog: Path) -> PassResult:
        raise SpellcheckError("codespell exploded")

    monkeypatch.setattr(cs, "run_pass", boom)
    assert main(["--repo-root", str(tmp_path), "--pass", "typo"]) == 2
    assert "codespell exploded" in capsys.readouterr().err


def test_findings_render_and_sort_deterministically() -> None:
    a = _finding("docs/a.md", 2, "typo", "x", "y")
    b = _finding("docs/a.md", 10, "typo", "x", "y")
    c = _finding("docs/b.md", 1, "typo", "x", "y")
    assert sorted([c, b, a], key=cs._sort_key) == [a, b, c]
    assert cs.format_finding(a) == "docs/a.md:2: [typo] x \u2014 fix: y"


# ---------------------------------------------------------------------------
# T011: typo pass (cases 1-5, 9, 11, 12, 14)
# ---------------------------------------------------------------------------

TYPO_LINE: Final[str] = "the reding tests\n"


def run_main(root: Path, *args: str) -> tuple[int, list[str]]:
    """Run ``main`` against the fixture repo and return the exit code and printed lines."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(["--repo-root", str(root), *args])
    return code, buffer.getvalue().splitlines()


def finding_lines(lines: list[str]) -> list[str]:
    """Drop the trailing summary line."""
    return lines[:-1]


def test_typo_pass_reports_file_and_line(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/guide.md": TYPO_LINE})
    code, lines = run_main(tmp_path, "--pass", "typo")
    assert code == 1
    assert finding_lines(lines) == ["docs/guide.md:1: [typo] reding — fix: reading"]


def test_typo_pass_runs_as_a_module_from_the_repo_root(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/guide.md": TYPO_LINE})
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.docs.check_spelling", "--repo-root", str(tmp_path), "--pass", "typo"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stderr
    assert "docs/guide.md:1: [typo] reding" in proc.stdout


def test_skipped_trees_are_not_reported_but_the_paired_file_is(tmp_path: Path) -> None:
    make_repo(
        tmp_path,
        {
            "docs/guide.md": TYPO_LINE,
            "docs/archive/old.md": TYPO_LINE,
            "docs/reports/r.md": TYPO_LINE,
            "docs/plans/p.md": TYPO_LINE,
        },
    )
    code, lines = run_main(tmp_path, "--pass", "typo")
    assert code == 1
    assert [line.split(":")[0] for line in finding_lines(lines)] == ["docs/guide.md"]


def test_ignore_words_list_keeps_a_legitimate_word_green_beside_a_real_typo(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/guide.md": "disjointness of the reding tests\n"})
    _, lines = run_main(tmp_path, "--pass", "typo")
    words = [line.split("[typo] ")[1].split(" ")[0] for line in finding_lines(lines)]
    assert words == ["reding"]


def test_packs_only_markdown_is_scanned(tmp_path: Path) -> None:
    make_repo(
        tmp_path,
        {"packs/built-in/x/prompt.md": TYPO_LINE, "packs/built-in/x/tool.py": "# the reding tests\n"},
    )
    _, lines = run_main(tmp_path, "--pass", "typo")
    assert [line.split(":")[0] for line in finding_lines(lines)] == ["packs/built-in/x/prompt.md"]


def test_readme_is_scanned(tmp_path: Path) -> None:
    make_repo(tmp_path, {"README.md": TYPO_LINE})
    _, lines = run_main(tmp_path, "--pass", "typo")
    assert [line.split(":")[0] for line in finding_lines(lines)] == ["README.md"]


def test_typo_pass_still_reports_inside_a_code_span(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/guide.md": "run `the reding tests` now\n"})
    code, lines = run_main(tmp_path, "--pass", "typo")
    assert code == 1
    assert finding_lines(lines) == ["docs/guide.md:1: [typo] reding — fix: reading"]


def test_symlinked_markdown_is_reported_once_under_its_canonical_path(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/changelog/CHANGELOG.md": TYPO_LINE})
    (tmp_path / "docs" / "alias.md").symlink_to(tmp_path / "docs" / "changelog" / "CHANGELOG.md")
    _, lines = run_main(tmp_path, "--pass", "typo")
    assert [line.split(":")[0] for line in finding_lines(lines)] == ["docs/changelog/CHANGELOG.md"]


def test_output_is_deterministic_across_runs(tmp_path: Path) -> None:
    make_repo(tmp_path, {f"docs/g{i}.md": TYPO_LINE for i in range(5)})
    runs = [run_main(tmp_path, "--pass", "typo") for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert [line.split(":")[0] for line in finding_lines(runs[0][1])] == sorted(f"docs/g{i}.md" for i in range(5))


def test_typo_scanned_count_is_the_in_scope_files_only(tmp_path: Path) -> None:
    make_repo(
        tmp_path,
        {
            "docs/guide.md": TYPO_LINE,
            "docs/archive/old.md": TYPO_LINE,
            "docs/reports/r.md": TYPO_LINE,
            "docs/plans/p.md": TYPO_LINE,
            "README.md": TYPO_LINE,
            "packs/built-in/x/prompt.md": TYPO_LINE,
            "packs/built-in/x/tool.py": "# the reding tests\n",
            "docs/changelog/CHANGELOG.md": "# Changelog\n",
        },
    )
    (tmp_path / "docs" / "alias.md").symlink_to(tmp_path / "docs" / "changelog" / "CHANGELOG.md")
    result = cs.run_pass("typo", tmp_path, tmp_path / cs.DEFAULT_CHANGELOG)
    # guide.md, README.md, prompt.md, CHANGELOG.md: skipped trees, the symlink and the .py are out.
    assert result.scanned == 4
    assert {finding.path for finding in result.findings} == {"docs/guide.md", "README.md", "packs/built-in/x/prompt.md"}


# ---------------------------------------------------------------------------
# T012: US pass over guides and context (cases 6-8)
# ---------------------------------------------------------------------------

# One prose hit, then three exempt forms. The single-word anchor id is the case where the anchor
# alternative of the ignore-regex is load-bearing: codespell's word regex includes "-", so a
# hyphenated id such as "behaviour-driven" is never flagged whether or not it is exempted.
US_GUIDE: Final[str] = 'The behaviour is documented here.\nUse the `behaviour` flag.\n```\nbehaviour inside a fence\n```\n<a id="behaviour"></a>\n'


def us_lines(root: Path) -> list[str]:
    """Run only the US pass and return its finding lines."""
    _, lines = run_main(root, "--pass", "us")
    return finding_lines(lines)


def test_us_pass_reports_prose_and_exempts_span_fence_and_anchor(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/guides/g.md": US_GUIDE})
    assert us_lines(tmp_path) == ["docs/guides/g.md:1: [us-spelling] behaviour — fix: behavior"]


def test_us_pass_is_scoped_to_guides_and_context(tmp_path: Path) -> None:
    make_repo(
        tmp_path,
        {
            "docs/guides/g.md": "The behaviour here.\n",
            "docs/context/c.md": "The behaviour here.\n",
            "docs/other/o.md": "The behaviour here.\n",
        },
    )
    assert [line.split(":")[0] for line in us_lines(tmp_path)] == ["docs/context/c.md", "docs/guides/g.md"]
    # The out-of-scope file is also clean under the typo pass: behaviour is not a typo.
    _, lines = run_main(tmp_path, "--pass", "typo")
    assert finding_lines(lines) == []


def test_us_pass_leaves_dialogue_alone_but_reports_its_neighbor(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/context/c.md": "A dialogue about behaviour.\n"})
    assert us_lines(tmp_path) == ["docs/context/c.md:1: [us-spelling] behaviour — fix: behavior"]


def test_us_pass_does_not_report_plain_typos(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/guides/g.md": "the reding tests and the behaviour\n"})
    assert [line.split("[us-spelling] ")[1].split(" ")[0] for line in us_lines(tmp_path)] == ["behaviour"]


def test_us_scanned_count_covers_only_guides_and_context(tmp_path: Path) -> None:
    make_repo(
        tmp_path,
        {
            "docs/guides/a.md": "ok\n",
            "docs/guides/sub/b.md": "ok\n",
            "docs/context/c.md": "ok\n",
            "docs/other/o.md": "ok\n",
        },
    )
    assert cs.run_pass("us", tmp_path, tmp_path / cs.DEFAULT_CHANGELOG).scanned == 3


# ---------------------------------------------------------------------------
# T013: US pass over the Unreleased section (case 10)
# ---------------------------------------------------------------------------

CHANGELOG_REL: Final[str] = "docs/changelog/CHANGELOG.md"
UNRELEASED_HEADINGS: Final[tuple[str, ...]] = ("## [Unreleased]", "## [Unreleased] - 4.0.0rc5")


def changelog_text(heading: str) -> str:
    """A changelog whose Unreleased section holds prose, a code span, a fence and a post-fence hit."""
    return (
        "# Changelog\n"
        "\n"
        f"{heading}\n"
        "\n"
        "### Added\n"
        "\n"
        "- **Widget** The colour picker is new.\n"
        "- The `cancelled` state is a code span.\n"
        "\n"
        "```text\n"
        "## [9.9.9] - 2099-01-01\n"
        "```\n"
        "\n"
        "The behaviour after the fence is prose again.\n"
        "\n"
        "## [1.0.0] - 2026-01-01\n"
        "\n"
        "- A released behaviour that must never be touched.\n"
    )


def line_of(text: str, needle: str) -> int:
    """1-based line number of the first line containing *needle*."""
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not in text")


@pytest.mark.parametrize("heading", UNRELEASED_HEADINGS)
def test_unreleased_findings_carry_real_changelog_line_numbers(tmp_path: Path, heading: str) -> None:
    text = changelog_text(heading)
    make_repo(tmp_path, {CHANGELOG_REL: text})
    _, lines = run_main(tmp_path, "--pass", "unreleased")
    # The first body line sits right after the heading (off-by-one guard), and the second hit only
    # exists past the fenced block that holds a release-looking heading (FR-016 cross-check).
    assert finding_lines(lines) == [
        f"{CHANGELOG_REL}:{line_of(text, 'colour')}: [us-spelling] colour — fix: color",
        f"{CHANGELOG_REL}:{line_of(text, 'behaviour after')}: [us-spelling] behaviour — fix: behavior",
    ]


def test_unreleased_first_body_line_maps_to_heading_plus_one(tmp_path: Path) -> None:
    text = "# Changelog\n\n## [Unreleased]\ncolour on the very first body line\n\n## [1.0.0] - 2026-01-01\n"
    make_repo(tmp_path, {CHANGELOG_REL: text})
    _, lines = run_main(tmp_path, "--pass", "unreleased")
    assert finding_lines(lines) == [f"{CHANGELOG_REL}:4: [us-spelling] colour — fix: color"]


def test_unreleased_section_comes_from_the_shared_locator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from scripts.release import validate_release

    calls: list[str] = []
    real = validate_release.unreleased_section

    def spy(text: str) -> validate_release.UnreleasedSection | None:
        calls.append(text)
        return real(text)

    monkeypatch.setattr(validate_release, "unreleased_section", spy)
    make_repo(tmp_path, {CHANGELOG_REL: changelog_text("## [Unreleased]")})
    code, _ = run_main(tmp_path, "--pass", "unreleased")
    assert code == 1
    assert len(calls) == 1


def test_unreleased_scanned_count_is_the_section_line_count(tmp_path: Path) -> None:
    from scripts.release.validate_release import unreleased_section

    text = changelog_text("## [Unreleased]")
    make_repo(tmp_path, {CHANGELOG_REL: text})
    section = unreleased_section(text)
    assert section is not None
    result = cs.run_pass("unreleased", tmp_path, tmp_path / CHANGELOG_REL)
    assert result.scanned == len(section.lines)
    assert len(result.findings) == 2


def test_changelog_without_an_unreleased_section_has_no_findings(tmp_path: Path) -> None:
    make_repo(tmp_path, {CHANGELOG_REL: "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n- colour\n"})
    result = cs.run_pass("unreleased", tmp_path, tmp_path / CHANGELOG_REL)
    assert result == PassResult(name="unreleased", findings=(), scanned=0)


def test_changelog_option_selects_the_file(tmp_path: Path) -> None:
    make_repo(tmp_path, {"notes/other.md": "# C\n\n## [Unreleased]\n\ncolour here\n"})
    _, lines = run_main(tmp_path, "--pass", "unreleased", "--changelog", "notes/other.md")
    assert finding_lines(lines) == ["notes/other.md:5: [us-spelling] colour — fix: color"]


def test_missing_changelog_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_repo(tmp_path, {})
    assert main(["--repo-root", str(tmp_path), "--pass", "unreleased"]) == 2
    assert "CHANGELOG.md" in capsys.readouterr().err


def test_all_passes_run_together_and_the_summary_names_each_scan(tmp_path: Path) -> None:
    make_repo(
        tmp_path,
        {
            "docs/guides/g.md": "the reding behaviour\n",
            CHANGELOG_REL: "# C\n\n## [Unreleased]\n\ncolour\n",
        },
    )
    code, lines = run_main(tmp_path)
    assert code == 1
    assert finding_lines(lines) == [
        f"{CHANGELOG_REL}:5: [us-spelling] colour — fix: color",
        "docs/guides/g.md:1: [typo] reding — fix: reading",
        "docs/guides/g.md:1: [us-spelling] behaviour — fix: behavior",
    ]
    assert lines[-1] == "3 finding(s) across 2 file(s); scanned: typo=2 file(s), us=1 file(s), unreleased=2 line(s)"


# ---------------------------------------------------------------------------
# Small branches: config shape, path display, unknown pass, changelog outside the repo
# ---------------------------------------------------------------------------


def test_a_non_string_skip_value_yields_no_patterns() -> None:
    assert cs._skip_patterns({"skip": ["*.md"]}) == []
    assert cs._skip_patterns({}) == []
    assert cs._skip_patterns({"skip": "a, b,,"}) == ["a", "b"]


def test_display_path_is_repo_relative_inside_and_posix_outside(tmp_path: Path) -> None:
    inside = tmp_path / "docs" / "c.md"
    assert cs._display_path(inside, tmp_path) == "docs/c.md"
    outside = tmp_path.parent / "elsewhere.md"
    assert cs._display_path(outside, tmp_path) == outside.as_posix()


def test_run_pass_rejects_an_unknown_pass_name(tmp_path: Path) -> None:
    make_repo(tmp_path, {})
    with pytest.raises(SpellcheckError, match="not available"):
        cs.run_pass("bogus", tmp_path, tmp_path / cs.DEFAULT_CHANGELOG)


def test_unreleased_pass_accepts_a_changelog_outside_the_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", {})
    other = tmp_path / "elsewhere.md"
    other.write_text("# C\n\n## [Unreleased]\n\ncolour\n", encoding="utf-8")
    result = cs.run_pass("unreleased", repo, other)
    assert [(f.path, f.line) for f in result.findings] == [(other.as_posix(), 5)]


def test_python_dash_m_with_bad_args_exits_2() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.docs.check_spelling", "--pass", "bogus"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# Never pass vacuously: a scan of zero files (or of a skipped scratch file) is exit 2
# ---------------------------------------------------------------------------


def _skip_everything(root: Path) -> None:
    """Prepend ``*.md,`` to the fixture repo's codespell skip list, so codespell ignores every page."""
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    patched = text.replace('skip = "', 'skip = "*.md,', 1)
    assert patched != text, "fixture pyproject has no skip key to patch"
    pyproject.write_text(patched, encoding="utf-8")


@pytest.mark.parametrize("selected", ["typo", "us"])
def test_a_typo_or_us_pass_that_scans_no_file_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str], selected: str) -> None:
    make_repo(tmp_path, {"docs/guides/g.md": TYPO_LINE, "docs/context/c.md": TYPO_LINE, "README.md": TYPO_LINE})
    _skip_everything(tmp_path)

    assert main(["--repo-root", str(tmp_path), "--pass", selected]) == 2

    err = capsys.readouterr().err
    assert f"{selected} pass scanned 0 file(s)" in err


def test_an_empty_tree_cannot_pass_the_all_passes_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_repo(tmp_path, {"notes/c.md": "# C\n\n## [Unreleased]\n\nfine\n"})

    assert main(["--repo-root", str(tmp_path), "--changelog", "notes/c.md"]) == 2
    assert "typo pass scanned 0 file(s)" in capsys.readouterr().err


def test_a_scanned_tree_is_still_a_normal_exit(tmp_path: Path) -> None:
    make_repo(tmp_path, {"docs/guides/g.md": "# G\n\nAll fine here.\n", "docs/context/c.md": "# C\n\nAll fine here.\n"})

    code, lines = run_main(tmp_path, "--pass", "us")

    assert code == 0
    assert lines[-1].endswith("scanned: us=2 file(s)")


def test_an_unreleased_scratch_file_that_the_skip_globs_would_ignore_is_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_repo(tmp_path, {CHANGELOG_REL: changelog_text("## [Unreleased]")})
    _skip_everything(tmp_path)

    assert main(["--repo-root", str(tmp_path), "--pass", "unreleased"]) == 2

    assert "skip" in capsys.readouterr().err


def test_an_unreleased_pass_on_a_normal_config_is_unchanged(tmp_path: Path) -> None:
    make_repo(tmp_path, {CHANGELOG_REL: changelog_text("## [Unreleased]")})

    code, lines = run_main(tmp_path, "--pass", "unreleased")

    assert code == 1
    assert len(finding_lines(lines)) == 2
