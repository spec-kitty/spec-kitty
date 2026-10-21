"""The gate must distinguish file CREATION from file MODIFICATION.

An occurrence map constrains what may happen to occurrences in content that
already exists: every category action is a statement about existing text
("rename it", "leave it alone", "judge each one"). A file that the diff
creates has no prior occurrence, so no category action can be violated by
its creation.

Before this behaviour existed the gate read ``git diff --name-only`` and so
could not tell the two apart. Any work package that brought a tree in — an
ingest, a vendored dependency, generated migrations — was rejected wholesale
on files it had merely created, inside surfaces whose ``do_not_change``
reasons all speak about *editing* ("editing them changes history",
"renaming inside it would make diffing against upstream impossible").
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.bulk_edit.diff_check import (
    assess_file,
    check_diff_compliance,
)
from specify_cli.bulk_edit.gate import check_review_diff_compliance
from specify_cli.bulk_edit.occurrence_map import OccurrenceMap


def _run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", message)
    return _run_git(repo, "rev-parse", "HEAD")


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


PROTECTIVE_CATEGORIES = {
    "code_symbols": {"action": "manual_review"},
    "import_paths": {"action": "rename"},
    "filesystem_paths": {"action": "manual_review"},
    "serialized_keys": {"action": "do_not_change"},
    "cli_commands": {"action": "do_not_change"},
    "user_facing_strings": {"action": "do_not_change"},
    "tests_fixtures": {"action": "rename"},
    "logs_telemetry": {"action": "do_not_change"},
}


def _map(exceptions: list[dict[str, str]] | None = None) -> OccurrenceMap:
    exceptions = exceptions or []
    raw = {
        "target": {"term": "oldName", "operation": "rename"},
        "categories": PROTECTIVE_CATEGORIES,
        "exceptions": exceptions,
    }
    return OccurrenceMap(
        target_term="oldName",
        target_replacement=None,
        target_operation="rename",
        categories=PROTECTIVE_CATEGORIES,
        exceptions=exceptions,
        status=None,
        raw=raw,
    )


class TestCreationIsNotModification:
    def test_added_file_in_do_not_change_category_passes(self) -> None:
        a = assess_file("bin/deploy", _map(), None, "A")
        assert a.violation is False
        assert a.source == "added"

    def test_same_path_modified_still_blocks(self) -> None:
        a = assess_file("bin/deploy", _map(), None, "M")
        assert a.violation is True
        assert a.category == "cli_commands"

    def test_added_file_beats_a_do_not_change_exception(self) -> None:
        """Creation must outrank the map's exceptions, not just its categories.

        ``vendor/**: do_not_change`` protects vendored code from being
        renamed in place. It is not a statement that vendored code may never
        be *added* -- vendoring a dependency is how it gets there.
        """
        omap = _map([{"path": "vendor/**", "action": "do_not_change", "reason": "upstream"}])
        assert assess_file("vendor/lib/thing.rb", omap, None, "A").violation is False
        assert assess_file("vendor/lib/thing.rb", omap, None, "M").violation is True

    def test_unknown_status_is_treated_as_modification(self) -> None:
        """Fail closed: callers that pass no status get the old behaviour."""
        assert assess_file("bin/deploy", _map(), None, None).violation is True

    @pytest.mark.parametrize("status", ["D", "M", "R"])
    def test_deletion_and_rename_are_not_exempt(self, status: str) -> None:
        """Removing or relocating a protected file IS a change to it."""
        assert assess_file("bin/deploy", _map(), None, status).violation is True

    def test_rename_similarity_score_is_normalised_by_the_gate(self) -> None:
        """``R100`` reaches assess_file as ``R`` (see gate._git_diff_files)."""
        assert assess_file("bin/deploy", _map(), None, "R").violation is True


class TestExemptionsAreWarnedNotSilent:
    """Each exemption must still name the file for a reviewer."""

    @pytest.mark.parametrize(
        "path,status,exceptions,marker",
        [
            (
                "db/migrate/0001_init.rb",
                "A",
                [{"path": "db/migrate/**", "action": "do_not_change", "reason": "history"}],
                "created by this diff",
            ),
            ("app/assets/fonts/x.woff2", "M", [], "x.woff2"),
        ],
    )
    def test_exemption_names_the_file(self, path: str, status: str, exceptions: list[dict[str, str]], marker: str) -> None:
        result = check_diff_compliance([path], _map(exceptions), None, {path: status})
        assert result.passed is True
        assert any(path in w and marker in w for w in result.warnings)


class TestCrossMissionWritesStillBlock:
    """C-004: creation must not become a hole in mission-ownership."""

    def test_adding_to_another_missions_dir_still_blocks(self) -> None:
        a = assess_file(
            "kitty-specs/other-mission-01ABC/status.events.jsonl",
            _map(),
            "kitty-specs/my-mission-01XYZ",
            "A",
        )
        assert a.violation is True
        assert a.source != "added"

    def test_adding_to_own_mission_dir_is_fine(self) -> None:
        a = assess_file(
            "kitty-specs/my-mission-01XYZ/notes-new.md",
            _map(),
            "kitty-specs/my-mission-01XYZ",
            "A",
        )
        assert a.violation is False

    def test_no_anchor_fails_closed(self) -> None:
        a = assess_file("kitty-specs/other-mission-01ABC/thing.json", _map(), None, "A")
        assert a.violation is True


class TestOwnBookkeepingOutranksMapExceptions:
    """A mission cannot protect its artifacts from the tool that writes them.

    A map that carries a broad protective exception over its own planning
    directory -- ``kitty-specs/**: do_not_change``, a reasonable thing to
    write to guard an audit trail -- used to have that exception pre-empt the
    built-in runtime-state exemption, blocking review on files spec-kitty
    had itself just written during the review.
    """

    def test_status_json_exempt_despite_blanket_exception(self) -> None:
        omap = _map([{"path": "kitty-specs/**", "action": "do_not_change", "reason": "audit"}])
        a = assess_file(
            "kitty-specs/my-mission-01XYZ/status.json",
            omap,
            "kitty-specs/my-mission-01XYZ",
            "M",
        )
        assert a.violation is False
        assert a.source == "runtime-state"

    def test_a_real_artifact_is_still_protected(self) -> None:
        omap = _map([{"path": "kitty-specs/**", "action": "do_not_change", "reason": "audit"}])
        a = assess_file(
            "kitty-specs/my-mission-01XYZ/spec.md",
            omap,
            "kitty-specs/my-mission-01XYZ",
            "M",
        )
        assert a.violation is True


class TestNonOccurrenceFiles:
    def test_webfont_does_not_block(self) -> None:
        a = assess_file("app/assets/fonts/ebgaramond.woff2", _map(), None, "M")
        assert a.violation is False
        assert a.source == "non-occurrence"

    @pytest.mark.parametrize("path", ["Gemfile.lock", "package-lock.json"])
    def test_created_lockfile_does_not_block(self, path: str) -> None:
        a = assess_file(path, _map(), None, "A")
        assert a.violation is False

    @pytest.mark.parametrize("path", ["Gemfile.lock", "package-lock.json", "assets/logo.svg"])
    def test_edited_lockfile_or_svg_is_not_a_non_occurrence(self, path: str) -> None:
        """A lockfile edit can rename a package and an SVG carries ids and
        classes as text: neither may pass as incapable of an occurrence."""
        a = assess_file(path, _map(), None, "M")
        assert a.source != "non-occurrence"
        assert a.violation is True

    def test_placeholder_does_not_block(self) -> None:
        assert assess_file("app/controllers/concerns/.keep", _map(), None, "M").violation is False

    @pytest.mark.parametrize("path", ["data/corpus.dat", "store/cache.sqlite", "model.pkl"])
    def test_opaque_data_files_still_block(self, path: str) -> None:
        """They can carry serialized application data, so they are not exempt."""
        assert assess_file(path, _map(), None, "M").violation is True

    def test_an_explicit_exception_still_wins(self) -> None:
        """A reviewer who names a binary keeps the action they chose."""
        omap = _map([{"path": "app/assets/**", "action": "do_not_change", "reason": "frozen"}])
        a = assess_file("app/assets/fonts/x.woff2", omap, None, "M")
        assert a.violation is True
        assert a.source == "exception"


class TestWebAndBuildSurfacesAreClassified:
    """A Rails/Phoenix/Laravel app was largely invisible to the classifier.

    The extension table itself lives in ``test_diff_check.py::TestClassifyPath``.
    """

    def test_a_modified_template_no_longer_blocks_as_unclassified(self) -> None:
        a = assess_file("app/views/layouts/application.html.erb", _map(), None, "M")
        assert a.violation is False
        assert a.category == "code_symbols"


# ---------------------------------------------------------------------------
# End-to-end: the status must actually survive the trip from git
# ---------------------------------------------------------------------------


class TestStatusReachesTheGateFromGit:
    """The unit tests above pass a status in by hand; this proves the gate
    really gets one out of ``git diff --name-status``.

    Without the plumbing, every test above could pass while the live gate
    still blocked, because the status would never be populated.
    """

    MAP = """\
target:
  term: oldName
  operation: rename
categories:
  code_symbols:
    action: do_not_change
  user_facing_strings:
    action: do_not_change
  serialized_keys:
    action: do_not_change
exceptions:
  - path: "vendor/**"
    action: do_not_change
    reason: vendored upstream code keeps its own vocabulary
"""

    def _repo(self, tmp_path: Path) -> tuple[Path, Path]:
        repo = tmp_path / "repo"
        (repo / "kitty-specs" / "m-01XYZ").mkdir(parents=True)
        _run_git(repo, "init", "-q")
        _run_git(repo, "config", "user.email", "t@example.com")
        _run_git(repo, "config", "user.name", "t")
        feature_dir = repo / "kitty-specs" / "m-01XYZ"
        (feature_dir / "meta.json").write_text(json.dumps({"change_mode": "bulk_edit"}), encoding="utf-8")
        (feature_dir / "occurrence_map.yaml").write_text(self.MAP, encoding="utf-8")
        (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
        _commit(repo, "initial")
        return repo, feature_dir

    def test_ingesting_vendored_code_passes(self, tmp_path: Path) -> None:
        repo, feature_dir = self._repo(tmp_path)
        base = _run_git(repo, "rev-parse", "HEAD")
        (repo / "vendor" / "gem" / "lib").mkdir(parents=True)
        (repo / "vendor" / "gem" / "lib" / "gem.rb").write_text("# vendored\n", encoding="utf-8")
        _commit(repo, "vendor a gem")

        result = check_review_diff_compliance(feature_dir=feature_dir, repo_root=repo, base_ref=base, head_ref="HEAD")

        assert result is not None
        assert result.passed is True, result.errors
        assert any(a.source == "added" for a in result.assessments)

    def test_editing_that_vendored_code_afterwards_blocks(self, tmp_path: Path) -> None:
        """The exception still does its job once the file exists."""
        repo, feature_dir = self._repo(tmp_path)
        vendored = repo / "vendor" / "gem" / "lib"
        vendored.mkdir(parents=True)
        (vendored / "gem.rb").write_text("# vendored\n", encoding="utf-8")
        _commit(repo, "vendor a gem")
        base = _run_git(repo, "rev-parse", "HEAD")
        (vendored / "gem.rb").write_text("# vendored, renamed\n", encoding="utf-8")
        _commit(repo, "rename inside vendored code")

        result = check_review_diff_compliance(feature_dir=feature_dir, repo_root=repo, base_ref=base, head_ref="HEAD")

        assert result is not None
        assert result.passed is False
        assert any("vendor/gem/lib/gem.rb" in e for e in result.errors)
