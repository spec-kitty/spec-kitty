"""Neutral mission context for unknown-language projects (#5284, FR-009/FR-010).

Drives the real ``charter generate --from-interview`` -> ``charter context``
CLI path for a Zig project (SC-002), then proves both renders (bootstrap on the
first load, compact on the next) are language-neutral, carry exactly one
charter-extension advisory, and never list language-scoped shipped artifacts.

Red-first labelling (charter C-011): every test states in its docstring whether
it is ``RED (pins the fix)`` or a ``GREEN control (pins unchanged behaviour)``.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from specify_cli.cli.commands.charter import app as charter_app

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_RUNNER = CliRunner()
_MISSION_TYPE = "software-dev"
_ACTION = "specify"
_STATE_FILE = Path(".kittify") / "charter" / "context-state.json"
_PACK_KINDS = ("tactics", "styleguides", "toolguides", "procedures", "agent_profiles")
_PROFILE_ID_KEYS = ("id", "profile-id")


@dataclass(frozen=True)
class _Renders:
    """The two ``charter context --json`` payloads of one project."""

    repo: Path
    bootstrap: dict[str, Any]
    compact: dict[str, Any]


def _advisory() -> str:
    from charter.activation.language_advisory import CHARTER_EXTENSION_ADVISORY

    advisory: str = CHARTER_EXTENSION_ADVISORY
    return advisory


def _git_init(repo: Path) -> None:
    for args in (
        ["init", "--initial-branch=main"],
        ["config", "user.email", "test@example.com"],
        ["config", "user.name", "Test User"],
        ["config", "commit.gpgsign", "false"],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _write_answers(repo: Path, languages_answer: str | None) -> None:
    interview = repo / ".kittify" / "charter" / "interview"
    interview.mkdir(parents=True, exist_ok=True)
    body = "mission: software-dev\nprofile: minimal\nselected_paradigms: []\nselected_directives: []\navailable_tools: []\nanswers:\n  purpose: A test project.\n"
    if languages_answer is not None:
        body += f"  languages_frameworks: {languages_answer}\n"
    (interview / "answers.yaml").write_text(body, encoding="utf-8")


def _generate(repo: Path) -> None:
    with contextlib.chdir(repo), patch.object(charter_pkg, "find_repo_root", return_value=repo):
        result = _RUNNER.invoke(charter_app, ["generate", "--from-interview", "--json"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def _context(repo: Path) -> dict[str, Any]:
    args = ["context", "--action", _ACTION, "--mission-type", _MISSION_TYPE, "--json"]
    with contextlib.chdir(repo), patch.object(charter_pkg, "find_repo_root", return_value=repo):
        result = _RUNNER.invoke(charter_app, args, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def _new_project(root: Path, name: str, languages_answer: str | None) -> Path:
    repo = root / name
    repo.mkdir()
    _git_init(repo)
    _write_answers(repo, languages_answer)
    (repo / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    _generate(repo)
    return repo


def _renders(repo: Path) -> _Renders:
    return _Renders(repo=repo, bootstrap=_context(repo), compact=_context(repo))


@pytest.fixture(scope="module")
def zig(tmp_path_factory: pytest.TempPathFactory) -> _Renders:
    return _renders(_new_project(tmp_path_factory.mktemp("zig"), "zig", "Zig"))


@pytest.fixture(scope="module")
def python_project(tmp_path_factory: pytest.TempPathFactory) -> _Renders:
    return _renders(_new_project(tmp_path_factory.mktemp("py"), "py", "Python"))


@pytest.fixture(scope="module")
def rust_project(tmp_path_factory: pytest.TempPathFactory) -> _Renders:
    return _renders(_new_project(tmp_path_factory.mktemp("rust"), "rust", "Rust"))


@pytest.fixture(scope="module")
def default_project(tmp_path_factory: pytest.TempPathFactory) -> _Renders:
    return _renders(_new_project(tmp_path_factory.mktemp("dflt"), "dflt", None))


@pytest.fixture(scope="module")
def stale_compiled_python(tmp_path_factory: pytest.TempPathFactory) -> _Renders:
    """Compiled ``[python]`` charter whose interview later became Zig, with NO regeneration."""
    repo = _new_project(tmp_path_factory.mktemp("stale"), "stale", "Python")
    _write_answers(repo, "Zig")
    return _renders(repo)


def _language_scoped_ids(*, excluding_language: str | None = None) -> frozenset[str]:
    """Ids of every shipped artifact scoped to a specific language (sentinels and empty scopes excluded).

    ``excluding_language`` drops artifacts whose scope admits that language (they are legitimately listed for it).
    """
    from charter.offering.artifact_kinds import ArtifactKind
    from charter.offering.pack_paths import built_in_dir
    from charter.offering.shared.scoping import (
        RESERVED_LANGUAGE_TOKENS,
        SENTINEL_LANGUAGE_TOKENS,
        normalize_languages,
    )

    yaml = YAML(typ="safe")
    ids: set[str] = set()
    for kind in ArtifactKind:
        if kind.plural not in _PACK_KINDS:
            continue
        for path in sorted(built_in_dir(kind).rglob(kind.glob_pattern)):
            data = yaml.load(path.read_text(encoding="utf-8"))
            scope = set(normalize_languages(data.get("applies_to_languages") or [])) - RESERVED_LANGUAGE_TOKENS
            if excluding_language is not None and excluding_language in scope:
                continue
            if scope and not scope <= SENTINEL_LANGUAGE_TOKENS:
                ids.add(next(str(data[key]) for key in _PROFILE_ID_KEYS if key in data))
    return frozenset(ids)


def _catalog_reference_ids(renders: _Renders) -> set[str]:
    """Ids the compiled charter resolved as references (the source of the profile and artifact catalog)."""
    charter_yaml = renders.repo / ".kittify" / "charter" / "charter.yaml"
    catalog = YAML(typ="safe").load(charter_yaml.read_text(encoding="utf-8"))["catalog"]
    return {str(reference["id"]) for reference in catalog["references"]}


def _mentions(text: str, artifact_id: str) -> bool:
    return any(artifact_id in line for line in text.splitlines())


def test_language_scoped_id_set_is_non_vacuous() -> None:
    """GREEN control (pins unchanged behaviour): the scan finds the known scoped ids (guards vacuous ``not in``)."""
    ids = _language_scoped_ids()

    assert {"python-conventions", "python-review-checks", "python-mutation-tools", "python-pedro"} <= ids
    assert "implementer-ivan" not in ids


class TestZigBootstrap:
    def test_first_load_is_bootstrap(self, zig: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): the first load renders the bootstrap mode."""
        assert zig.bootstrap["mode"] == "bootstrap"

    def test_charter_records_unknown_language(self, zig: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): the real Zig generate path compiled ``[unknown]`` (SC-002)."""
        catalog = YAML(typ="safe").load((zig.repo / ".kittify" / "charter" / "charter.yaml").read_text(encoding="utf-8"))["catalog"]

        assert catalog["languages"] == ["unknown"]

    def test_context_is_not_empty_and_keeps_neutral_guidance(self, zig: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): language-neutral doctrine and ``implementer-ivan`` remain."""
        text = zig.bootstrap["text"]

        assert "Action Doctrine (specify):" in text
        assert "DIRECTIVE_031" in text
        assert "AGENT_PROFILE:implementer-ivan" in _catalog_reference_ids(zig)

    def test_exactly_one_advisory_line(self, zig: _Renders) -> None:
        """RED (pins the fix): the bootstrap render carries the charter-extension advisory exactly once."""
        assert zig.bootstrap["text"].count(_advisory()) == 1

    def test_no_language_scoped_artifact_ids(self, zig: _Renders) -> None:
        """RED (pins the fix): no id of any language-scoped shipped artifact is listed (FR-009)."""
        text = zig.bootstrap["text"]

        leaked = sorted(artifact_id for artifact_id in _language_scoped_ids() if _mentions(text, artifact_id))

        assert leaked == []

    def test_no_language_scoped_profile_is_listed(self, zig: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): ``python-pedro`` is not resolved for a Zig project (FR-009 profile half)."""
        assert "AGENT_PROFILE:python-pedro" not in _catalog_reference_ids(zig)


class TestZigCompact:
    def test_second_load_is_compact(self, zig: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): the next load renders the compact mode."""
        assert zig.compact["mode"] == "compact"

    def test_languages_unknown_followed_by_the_single_advisory(self, zig: _Renders) -> None:
        """RED (pins the fix): ``Languages: unknown`` is immediately followed by exactly one advisory line."""
        lines = zig.compact["text"].splitlines()

        index = lines.index("  - Languages: unknown")

        assert _advisory() in lines[index + 1]
        assert zig.compact["text"].count(_advisory()) == 1

    def test_no_python_languages_line(self, zig: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): a Zig project never reports ``Languages: python``."""
        assert "Languages: python" not in zig.compact["text"]

    def test_no_language_scoped_artifact_ids(self, zig: _Renders) -> None:
        """RED (pins the fix): the compact id rail lists no language-scoped shipped artifact (FR-009)."""
        text = zig.compact["text"]

        leaked = sorted(artifact_id for artifact_id in _language_scoped_ids() if _mentions(text, artifact_id))

        assert leaked == []


class TestPythonControl:
    def test_bootstrap_keeps_python_guidance_without_advisory(self, python_project: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): a Python project lists ``python-conventions``, no advisory."""
        text = python_project.bootstrap["text"]

        assert python_project.bootstrap["mode"] == "bootstrap"
        assert _mentions(text, "python-conventions")
        assert _advisory() not in text
        assert "AGENT_PROFILE:implementer-ivan" in _catalog_reference_ids(python_project)

    def test_compact_lists_python_without_advisory(self, python_project: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): compact shows ``Languages: python`` and no advisory."""
        text = python_project.compact["text"]

        assert python_project.compact["mode"] == "compact"
        assert "  - Languages: python" in text
        assert _advisory() not in text


class TestRecognisedLanguageBleed:
    """#5357: a recognised non-Python language must not list other languages' scoped doctrine ids."""

    def test_charter_records_rust(self, rust_project: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): the real Rust generate path compiled ``[rust]``."""
        catalog = YAML(typ="safe").load((rust_project.repo / ".kittify" / "charter" / "charter.yaml").read_text(encoding="utf-8"))["catalog"]

        assert catalog["languages"] == ["rust"]

    def test_other_language_ids_set_is_non_vacuous(self) -> None:
        """GREEN control (pins unchanged behaviour): the excluding-rust scan still finds the python/typescript ids."""
        ids = _language_scoped_ids(excluding_language="rust")

        assert {"python-conventions", "python-review-checks", "python-mutation-tools", "typescript-mutation-tools"} <= ids

    def test_bootstrap_lists_no_other_language_ids(self, rust_project: _Renders) -> None:
        """RED (pins the fix): the Rust bootstrap render lists no other language's scoped id (#5357)."""
        text = rust_project.bootstrap["text"]

        leaked = sorted(i for i in _language_scoped_ids(excluding_language="rust") if _mentions(text, i))

        assert rust_project.bootstrap["mode"] == "bootstrap"
        assert leaked == []

    def test_compact_lists_no_other_language_ids(self, rust_project: _Renders) -> None:
        """RED (pins the fix): the Rust compact id rail lists no other language's scoped id (#5357)."""
        text = rust_project.compact["text"]

        leaked = sorted(i for i in _language_scoped_ids(excluding_language="rust") if _mentions(text, i))

        assert rust_project.compact["mode"] == "compact"
        assert leaked == []

    def test_python_project_still_lists_python_conventions(self, python_project: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): Python keeps its own scoped ids in the compact rail."""
        assert _mentions(python_project.bootstrap["text"], "python-conventions")

    def test_default_project_still_admits_all(self, default_project: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): no language signal admits all, so python-conventions is still listed."""
        assert _mentions(default_project.bootstrap["text"], "python-conventions")


class TestRecognisedLanguageWithoutSpecialistGuidance:
    """D2 (2026-09-29): the advisory follows missing specialist guidance, not the stored ``unknown`` token."""

    def test_bootstrap_shows_the_advisory_exactly_once_for_rust(self, rust_project: _Renders) -> None:
        """RED (pins D2): no shipped doctrine is rust-scoped, so the Rust bootstrap render carries the advisory once."""
        assert rust_project.bootstrap["text"].count(_advisory()) == 1

    def test_compact_keeps_languages_rust_and_shows_the_advisory_once(self, rust_project: _Renders) -> None:
        """RED (pins D2): compact keeps ``Languages: rust`` (stored value) and adds the advisory once."""
        lines = rust_project.compact["text"].splitlines()

        assert "  - Languages: rust" in lines
        assert rust_project.compact["text"].count(_advisory()) == 1

    def test_scope_filtered_miss_for_rust_carries_the_advisory(self) -> None:
        """RED (pins D2): the catalog-miss suggestion for a language without specialist guidance is the advisory."""
        from charter.activation._catalog_miss import classify_scope_filtered_miss

        diagnosis = classify_scope_filtered_miss("python-conventions", ["rust"])

        assert diagnosis.suggestion is not None
        assert _advisory() in diagnosis.suggestion
        assert "Add the active language" not in diagnosis.suggestion

    def test_python_default_and_unknown_controls(self, python_project: _Renders, default_project: _Renders, zig: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): python and default show no advisory; unknown still shows exactly one."""
        assert _advisory() not in python_project.bootstrap["text"] + python_project.compact["text"]
        assert _advisory() not in default_project.bootstrap["text"] + default_project.compact["text"]
        assert zig.bootstrap["text"].count(_advisory()) == 1
        assert zig.compact["text"].count(_advisory()) == 1


class TestDefaultInterviewControl:
    def test_bootstrap_has_no_advisory(self, default_project: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): languages absent -> no advisory, still implementer-ivan."""
        assert default_project.bootstrap["mode"] == "bootstrap"
        assert _advisory() not in default_project.bootstrap["text"]
        assert "AGENT_PROFILE:implementer-ivan" in _catalog_reference_ids(default_project)

    def test_compact_has_neither_languages_line_nor_advisory(self, default_project: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): languages absent -> no Languages line, no advisory."""
        text = default_project.compact["text"]

        assert default_project.compact["mode"] == "compact"
        assert "Languages:" not in text
        assert _advisory() not in text


class TestStaleCompiledCharterStaysCompiledFirst:
    def test_runtime_keeps_compiled_python_over_a_newer_zig_interview(self, stale_compiled_python: _Renders) -> None:
        """GREEN control (pins unchanged behaviour): without regeneration the compiled ``[python]`` still wins (US3 AS3)."""
        assert stale_compiled_python.compact["mode"] == "compact"
        assert "  - Languages: python" in stale_compiled_python.compact["text"]
        assert _advisory() not in stale_compiled_python.compact["text"]
        assert _advisory() not in stale_compiled_python.bootstrap["text"]


# ---------------------------------------------------------------------------
# Unit-level branch coverage (no CLI round-trip)
# ---------------------------------------------------------------------------


def _write_compiled_languages(repo: Path, languages_yaml: str) -> None:
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(f"catalog:\n  languages: {languages_yaml}\n", encoding="utf-8")


@pytest.mark.fast
class TestCompactLanguageLines:
    def test_hand_written_unknown_charter_gets_one_advisory(self, tmp_path: Path) -> None:
        """RED (pins the fix): a hand-written ``[unknown]`` charter renders the Languages line and one advisory."""
        from charter.activation.compact import render_compact_view

        _write_compiled_languages(tmp_path, "[unknown]")

        text = render_compact_view(tmp_path).text

        assert "  - Languages: unknown" in text
        assert text.count(_advisory()) == 1

    @pytest.mark.parametrize("languages_yaml", ["[python]", "[python, go]", "[]"])
    def test_other_language_states_get_no_advisory(self, tmp_path: Path, languages_yaml: str) -> None:
        """GREEN control (pins unchanged behaviour): recognised (or empty) languages never render the advisory."""
        from charter.activation.compact import render_compact_view

        _write_compiled_languages(tmp_path, languages_yaml)

        assert _advisory() not in render_compact_view(tmp_path).text

    def test_mixed_hand_edited_set_is_not_unknown(self, tmp_path: Path) -> None:
        """GREEN control (pins unchanged behaviour): ``[python, unknown]`` is not an unknown-language project."""
        from charter.activation.compact import render_compact_view

        _write_compiled_languages(tmp_path, "[python, unknown]")

        assert _advisory() not in render_compact_view(tmp_path).text


@pytest.mark.fast
class TestBootstrapAdvisory:
    def test_no_repo_root_means_no_advisory(self) -> None:
        """GREEN control (pins unchanged behaviour): without a repo root there is no language signal."""
        from charter.activation.context_renderers.bootstrap_text import _append_language_advisory

        lines: list[str] = []
        _append_language_advisory(lines, None)

        assert lines == []

    def test_unknown_project_appends_exactly_one_advisory(self, tmp_path: Path) -> None:
        """RED (pins the fix): an ``[unknown]`` project appends one advisory line after a blank separator."""
        from charter.activation.context_renderers.bootstrap_text import _append_language_advisory

        _write_compiled_languages(tmp_path, "[unknown]")
        lines: list[str] = ["existing"]
        _append_language_advisory(lines, tmp_path)

        assert lines == ["existing", "", f"  - Advisory: {_advisory()}"]

    def test_recognised_project_appends_nothing(self, tmp_path: Path) -> None:
        """GREEN control (pins unchanged behaviour): a recognised language adds no advisory."""
        from charter.activation.context_renderers.bootstrap_text import _append_language_advisory

        _write_compiled_languages(tmp_path, "[python]")
        lines: list[str] = []
        _append_language_advisory(lines, tmp_path)

        assert lines == []


class _FilteredRepo:
    def __init__(self, scope_filtered_ids: frozenset[str]) -> None:
        self.scope_filtered_ids = scope_filtered_ids


class _Service:
    tactics = _FilteredRepo(frozenset({"t-scoped"}))
    styleguides = _FilteredRepo(frozenset({"s-scoped"}))
    toolguides = _FilteredRepo(frozenset({"g-scoped"}))
    # ``procedures`` deliberately absent: a service without the repository is tolerated.


def _service() -> Any:
    """A duck-typed doctrine service (the helper only reads ``<slot>.scope_filtered_ids``)."""
    return _Service()


@pytest.mark.fast
class TestDropScopeFilteredIds:
    _IDS = {
        "directives": ("d1",),
        "tactics": ("t-scoped", "t-neutral"),
        "styleguides": ("s-scoped", "s-neutral"),
        "toolguides": ("g-scoped",),
        "procedures": ("p1",),
    }

    def test_unknown_project_drops_only_scope_filtered_ids(self, tmp_path: Path) -> None:
        """RED (pins the fix): only the service's scope-filtered ids leave the language-scoped slots."""
        from charter.activation.action_doctrine_bundle import _drop_scope_filtered_ids

        _write_compiled_languages(tmp_path, "[unknown]")

        result = _drop_scope_filtered_ids(self._IDS, _service(), tmp_path)

        assert result == {
            "directives": ("d1",),
            "tactics": ("t-neutral",),
            "styleguides": ("s-neutral",),
            "toolguides": (),
            "procedures": ("p1",),
        }

    def test_recognised_project_drops_scope_filtered_ids(self, tmp_path: Path) -> None:
        """RED (pins the fix): a recognised language also drops scope-filtered ids (re-pinned 2026-09-29, #5357)."""
        from charter.activation.action_doctrine_bundle import _drop_scope_filtered_ids

        _write_compiled_languages(tmp_path, "[python]")

        result = _drop_scope_filtered_ids(self._IDS, _service(), tmp_path)

        assert result["tactics"] == ("t-neutral",)

    def test_no_language_signal_is_untouched(self, tmp_path: Path) -> None:
        """GREEN control (pins unchanged behaviour): no language signal admits all ids (FR-014)."""
        from charter.activation.action_doctrine_bundle import _drop_scope_filtered_ids

        assert _drop_scope_filtered_ids(self._IDS, _service(), tmp_path) is self._IDS

    def test_empty_bundle_short_circuits(self, tmp_path: Path) -> None:
        """GREEN control (pins unchanged behaviour): a typeless (empty) bundle is returned as is."""
        from charter.activation.action_doctrine_bundle import _drop_scope_filtered_ids

        empty: dict[str, tuple[str, ...]] = {}

        assert _drop_scope_filtered_ids(empty, _service(), tmp_path) is empty


@pytest.mark.fast
def test_overlay_reusing_a_scope_filtered_builtin_id_stays_in_the_bundle(tmp_path: Path) -> None:
    """RED (pins F1): a project overlay reusing a built-in scoped id, without a scope, is not dropped for a Rust project."""
    from charter.activation.action_doctrine_bundle import _drop_scope_filtered_ids
    from charter.offering.tactics.repository import TacticRepository

    shipped = tmp_path / "built-in"
    project = tmp_path / "project"
    for directory, scope in ((shipped, "applies_to_languages: [python]\n"), (project, "")):
        directory.mkdir()
        (directory / "shared.tactic.yaml").write_text(
            f'schema_version: "1.0"\nid: shared\nname: Shared\n{scope}steps:\n  - title: Do it\n    description: Step.\n',
            encoding="utf-8",
        )
    repo = TacticRepository(built_in_dir=shipped, project_dir=project, active_languages=["rust"])
    service: Any = type("_RustService", (), {"tactics": repo})()
    _write_compiled_languages(tmp_path, "[rust]")

    result = _drop_scope_filtered_ids({"tactics": ("shared",)}, service, tmp_path)

    assert repo.scope_filtered_ids == frozenset()
    assert result["tactics"] == ("shared",)
