"""Precision regression tests for the stale-assertion analyzer (WP01).

Covers: FR-001, FR-002, FR-004, FR-005, FR-006, NFR-001, NFR-002, C-001.

Two false-positive engines are fixed by SUPPRESSING (not emitting) findings:

1. Relocation/re-export (#2031) — an identifier removed from its origin file
   is suppressed only when that SAME origin file's HEAD still imports/
   re-exports it (``_head_still_exports_name``). This is deliberately keyed
   on head-importability, not "the bare name appears somewhere else in the
   diff" — the analyzer has no qualname primitive, so the latter would
   collide on common names (``run``/``main``) and blind genuine deletions.
2. Generic-literal noise (#2343) — a removed string literal is suppressed
   only when it is a member of the pinned generic-token set or is all
   punctuation/whitespace/empty (``_is_generic_literal``), never by length
   alone. #3957 extends this with structural noise rules
   (``_is_noise_literal``): one-character literals, ``open()`` file-mode
   strings, and single bare lowercase words ("items"/"url"/"payload") are
   suppressed too, while symbol-shaped ("E001", "old_key") and multi-word
   ("bad request") literals remain signal.

Every "paired" test below runs the SAME fixture twice: once with the
relevant suppression helper monkeypatched to always return the pre-fix
("disabled") answer, and once with the real ("enabled") implementation —
proving the suppression is the cause of the before/after delta, not an
artifact of the fixture.

Uses synthetic git repositories built with tmp_path + subprocess.run(["git",
...]) for deterministic, hermetic testing — zero network access, matching
the pattern in tests/post_merge/test_stale_assertions.py.
"""

from __future__ import annotations

import ast
import subprocess
import textwrap
from pathlib import Path
from unittest import mock

import pytest

from specify_cli.post_merge import run_check
from specify_cli.post_merge import stale_assertions
from specify_cli.post_merge.stale_assertions import FP_CEILING
from specify_cli.post_merge.stale_assertions import _head_still_exports_name

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Synthetic git repo fixture helpers (mirrors test_stale_assertions.py)
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> str:
    """Run a git command in cwd and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip()


def _setup_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with user config."""
    _git(["init"], cwd=tmp_path)
    _git(["config", "user.email", "test@example.com"], cwd=tmp_path)
    _git(["config", "user.name", "Test User"], cwd=tmp_path)
    return tmp_path


def _commit(repo: Path, message: str = "commit") -> str:
    """Stage all changes and create a commit, returning the commit SHA."""
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-m", message, "--allow-empty"], cwd=repo)
    return _git(["rev-parse", "HEAD"], cwd=repo)


def _write(repo: Path, rel_path: str, content: str) -> Path:
    """Write file content to repo/rel_path, creating parent dirs."""
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))
    return path


# ---------------------------------------------------------------------------
# Shared fixture builder: the WP05 extraction shape (#2031)
# ---------------------------------------------------------------------------

def _build_extraction_storm_fixture(
    tmp_path: Path, helper_count: int = 10
) -> tuple[Path, str, str]:
    """Build a WP05-shaped extraction fixture, sized to genuinely storm.

    Base: ``src/pkg/core.py`` defines ``helper_count`` functions, each
    referenced by exactly one test assertion.
    Head: the functions are relocated into a NEW ``src/pkg/helpers.py`` and
    re-exported back from ``core.py`` (``from .helpers import helper_00,
    ...``) — the exact shape that produced 180 false findings on PR #2028.

    Returns (repo, base_sha, head_sha).
    """
    repo = _setup_repo(tmp_path)
    _write(repo, "src/pkg/__init__.py", "")

    base_core_src = "".join(f"def helper_{i:02d}():\n    return {i}\n\n" for i in range(helper_count))
    _write(repo, "src/pkg/core.py", base_core_src)

    test_src = "".join(
        f"def test_helper_{i:02d}():\n    assert helper_{i:02d}() == {i}\n\n" for i in range(helper_count)
    )
    _write(repo, "tests/test_helpers.py", test_src)
    base_sha = _commit(repo, "base: helpers defined directly in core.py")

    head_core_src = "from .helpers import " + ", ".join(f"helper_{i:02d}" for i in range(helper_count)) + "\n"
    _write(repo, "src/pkg/core.py", head_core_src)
    head_helpers_src = "".join(f"def helper_{i:02d}():\n    return {i}\n\n" for i in range(helper_count))
    _write(repo, "src/pkg/helpers.py", head_helpers_src)
    head_sha = _commit(repo, "extract helpers into helpers.py, re-export from core.py")

    return repo, base_sha, head_sha


# ---------------------------------------------------------------------------
# (a) FR-001/SC-001 — extraction suppression, PAIRED before/after
# ---------------------------------------------------------------------------

class TestExtractionSuppressionPaired:
    """SC-001: WP05-shaped extraction — disabled storms, enabled ~0."""

    def test_extraction_paired_disabled_storms_enabled_near_zero(self, tmp_path: Path) -> None:
        repo, base_sha, head_sha = _build_extraction_storm_fixture(tmp_path)

        with mock.patch.object(stale_assertions, "_head_still_exports_name", return_value=False):
            disabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        enabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        disabled_helper_findings = [f for f in disabled_report.findings if f.changed_symbol.startswith("helper_")]
        enabled_helper_findings = [f for f in enabled_report.findings if f.changed_symbol.startswith("helper_")]

        assert len(disabled_helper_findings) >= 8, (
            "suppression disabled must reproduce the WP05 storm shape "
            f"(expected >= 8 relocated-helper findings, got {len(disabled_helper_findings)})"
        )
        assert len(enabled_helper_findings) == 0, (
            "suppression enabled must suppress ALL relocated/re-exported helper findings, "
            f"got: {[f.changed_symbol for f in enabled_helper_findings]}"
        )


# ---------------------------------------------------------------------------
# (b) FR-004/SC-002 — generic-literal suppression, PAIRED before/after
# ---------------------------------------------------------------------------

class TestGenericLiteralSuppressionPaired:
    """SC-002: generic-literal removals — disabled noisy, enabled ~0."""

    def test_generic_literal_paired_disabled_noisy_enabled_near_zero(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)

        _write(repo, "src/pkg/messages.py", """\
            STATUS = "ok"
            MSG = "error"
            KIND = "unknown"
        """)
        _write(repo, "tests/test_messages.py", """\
            def test_status():
                assert result == "ok"

            def test_msg():
                assert output == "error"

            def test_kind():
                assert category == "unknown"
        """)
        base_sha = _commit(repo, "base")

        _write(repo, "src/pkg/messages.py", """\
            STATUS = "ready"
            MSG = "failure"
            KIND = "known"
        """)
        head_sha = _commit(repo, "reformat: remove generic literals")

        with mock.patch.object(stale_assertions, "_is_noise_literal", return_value=False):
            disabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        enabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        generic_values = {"ok", "error", "unknown"}
        disabled_generic = {f.changed_symbol for f in disabled_report.findings} & generic_values
        enabled_generic = {f.changed_symbol for f in enabled_report.findings} & generic_values

        assert disabled_generic == generic_values, (
            f"suppression disabled must surface all 3 generic-literal removals, got {disabled_generic}"
        )
        assert enabled_generic == set(), (
            f"suppression enabled must suppress all generic-literal removals, got {enabled_generic}"
        )


# ---------------------------------------------------------------------------
# (b2) #3957 — structural noise literals (F-60/F-79), PAIRED on the same fixture
# ---------------------------------------------------------------------------

class TestNoiseLiteralSuppressionPaired:
    """#3957: one-char/file-mode/single-lowercase-word removals — disabled
    noisy, enabled ~0, while symbol-shaped and multi-word signal survives."""

    def test_noise_literals_paired_disabled_noisy_enabled_near_zero(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)

        # Base: the F-60 shape (raw open() mode strings) and the F-79 shape
        # (generic schema words removed en masse), beside genuine signal.
        _write(repo, "src/pkg/schema.py", """\
            MODE_APPEND = "a"
            MODE_READ_BINARY = "rb"
            MODE_WRITE_PLUS = "w+"
            LIST_KEY = "items"
            LINK_KEY = "url"
            BODY_KEY = "payload"
            ERROR_CODE = "E001"
            LEGACY_MSG = "bad request"
        """)
        _write(repo, "tests/test_schema.py", """\
            def test_modes():
                assert mode == "a"
                assert binary == "rb"
                assert plus == "w+"

            def test_generic_words():
                assert body == "items"
                assert body == "url"
                assert body == "payload"

            def test_code():
                assert code == "E001"

            def test_message():
                assert msg == "bad request"
        """)
        base_sha = _commit(repo, "base")

        _write(repo, "src/pkg/schema.py", """\
            ERROR_CODE = "E002"
        """)
        head_sha = _commit(repo, "remove raw open() calls and schema keys")

        with mock.patch.object(stale_assertions, "_is_noise_literal", return_value=False):
            disabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        enabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        noise_values = {"a", "rb", "w+", "items", "url", "payload"}
        signal_values = {"E001", "bad request"}

        disabled_noise = {f.changed_symbol for f in disabled_report.findings} & noise_values
        enabled_noise = {f.changed_symbol for f in enabled_report.findings} & noise_values
        enabled_signal = {f.changed_symbol for f in enabled_report.findings} & signal_values

        assert disabled_noise == noise_values, (
            f"suppression disabled must surface all 6 noise-literal removals, got {disabled_noise}"
        )
        assert enabled_noise == set(), (
            f"suppression enabled must suppress all noise-literal removals, got {enabled_noise}"
        )
        assert enabled_signal == signal_values, (
            f"symbol-shaped and multi-word literals must remain signal, got {enabled_signal}"
        )


# ---------------------------------------------------------------------------
# (c) FR-005/SC-003 — genuine deletion (no re-export) still flagged
# ---------------------------------------------------------------------------

class TestGenuineDeletionStillFlagged:
    """SC-003: a truly-removed symbol (not relocated) is still caught."""

    def test_genuine_deletion_not_reexported_still_flagged(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)

        _write(repo, "src/pkg/util.py", """\
            def compute_total():
                return 42
        """)
        _write(repo, "tests/test_util.py", """\
            def test_total():
                assert compute_total() == 42
        """)
        base_sha = _commit(repo, "base")

        # Genuine deletion: util.py's head neither redefines compute_total
        # nor imports/re-exports it from anywhere.
        _write(repo, "src/pkg/util.py", """\
            def unrelated_thing():
                return 1
        """)
        head_sha = _commit(repo, "delete compute_total (no relocation)")

        report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        flagged = {f.changed_symbol: f.confidence for f in report.findings}
        assert "compute_total" in flagged, (
            f"genuine deletion must still be flagged, findings: {report.findings}"
        )
        assert flagged["compute_total"] in ("high", "medium"), (
            f"genuine deletion must be high/medium confidence, got {flagged['compute_total']}"
        )


# ---------------------------------------------------------------------------
# (d) FR-001/FR-005/SC-003 — the NAME-COLLISION key guard
# ---------------------------------------------------------------------------

class TestNameCollisionGuard:
    """SC-003: a genuine deletion of a common name must NOT be blinded by an
    unrelated same-name def in another changed file — proves the suppression
    is keyed on head-importability of the ORIGIN file, not bare-name-anywhere.
    """

    def test_genuine_deletion_still_flagged_despite_unrelated_same_name_elsewhere(
        self, tmp_path: Path
    ) -> None:
        repo = _setup_repo(tmp_path)

        _write(repo, "src/pkg/service_c.py", """\
            def run():
                return "c"
        """)
        _write(repo, "src/pkg/service_b.py", """\
            def run():
                return "b_old"
        """)
        _write(repo, "tests/test_service_c.py", """\
            def test_run():
                assert run() == "c"
        """)
        base_sha = _commit(repo, "base")

        # C: genuine deletion of `run` — no import/re-export of the old name.
        _write(repo, "src/pkg/service_c.py", """\
            def teardown():
                return "c2"
        """)
        # B: an UNRELATED function also named `run`, edited but not removed —
        # the trap. A bare-name-anywhere heuristic would see "run" survive in
        # the diff (via B) and wrongly suppress C's genuine deletion.
        _write(repo, "src/pkg/service_b.py", """\
            def run():
                return "b_new"
        """)
        head_sha = _commit(repo, "delete run in service_c.py; unrelated edit to run in service_b.py")

        report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        flagged = {(f.changed_symbol, f.source_file.name) for f in report.findings}
        assert ("run", "service_c.py") in flagged, (
            "FR-001/SC-003: genuine deletion of common name 'run' in service_c.py must "
            f"still be flagged despite unrelated 'run' surviving in service_b.py; got {report.findings}"
        )


# ---------------------------------------------------------------------------
# (e) FR-002 edge case — relocate-AND-rename still flagged
# ---------------------------------------------------------------------------

class TestRelocateAndRenameStillFlagged:
    """FR-002: a relocate-and-rename is a real change, not a suppression —
    the origin file's head no longer imports the OLD name under any form."""

    def test_relocate_and_rename_still_flagged(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)
        _write(repo, "src/pkg/__init__.py", "")

        _write(repo, "src/pkg/core.py", """\
            def old_name():
                return 1
        """)
        _write(repo, "tests/test_core.py", """\
            def test_it():
                assert old_name() == 1
        """)
        base_sha = _commit(repo, "base")

        # Relocated to util.py AND renamed to new_name — core.py's head
        # imports "new_name", never "old_name".
        _write(repo, "src/pkg/core.py", """\
            from .util import new_name
        """)
        _write(repo, "src/pkg/util.py", """\
            def new_name():
                return 1
        """)
        head_sha = _commit(repo, "relocate old_name -> util.new_name")

        report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        flagged = {f.changed_symbol for f in report.findings}
        assert "old_name" in flagged, (
            f"relocate-and-rename must still be flagged (origin head no longer imports "
            f"the OLD name), got: {report.findings}"
        )


# ---------------------------------------------------------------------------
# (f) FR-004 edge case — genuinely SHORT assert-critical literal still emitted
# ---------------------------------------------------------------------------

class TestShortAssertCriticalLiteralStillEmitted:
    """FR-004: genericness, not length, is the discriminator — a short but
    non-generic literal (an error code) is never suppressed."""

    def test_short_assert_critical_literal_still_emitted(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)

        _write(repo, "src/pkg/errors.py", """\
            ERROR_CODE = "E001"
        """)
        _write(repo, "tests/test_errors.py", """\
            def test_code():
                assert code == "E001"
        """)
        base_sha = _commit(repo, "base")

        _write(repo, "src/pkg/errors.py", """\
            ERROR_CODE = "E002"
        """)
        head_sha = _commit(repo, "change error code")

        report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        flagged = {f.changed_symbol for f in report.findings}
        assert "E001" in flagged, (
            f"a short but non-generic literal must still be emitted (genuineness, not "
            f"length, is the rule), got: {report.findings}"
        )


# ---------------------------------------------------------------------------
# (g) FR-006/SC-004 — FP-ceiling PAIRED on the SAME storming fixture
# ---------------------------------------------------------------------------

class TestFPCeilingPairedOnExtractionFixture:
    """SC-004: the ceiling proof must be a paired before/after on the SAME
    fixture that genuinely storms — a 0.0-on-empty fixture does not count."""

    def test_fp_ceiling_paired_disabled_trips_enabled_within_ceiling(self, tmp_path: Path) -> None:
        repo, base_sha, head_sha = _build_extraction_storm_fixture(tmp_path)

        with mock.patch.object(stale_assertions, "_head_still_exports_name", return_value=False):
            disabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        enabled_report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        assert disabled_report.findings_per_100_loc > FP_CEILING, (
            "FR-006: the SAME extraction fixture must genuinely storm when suppression is "
            f"disabled ({disabled_report.findings_per_100_loc:.2f} must exceed {FP_CEILING}) — "
            "otherwise the fixture is not sized to storm."
        )
        # Guard against gaming the metric with a vacuous 0-LOC / 0-finding fixture.
        assert disabled_report.findings_per_100_loc > 0.0

        assert enabled_report.findings_per_100_loc <= FP_CEILING, (
            f"FR-006: suppression enabled must bring findings_per_100_loc "
            f"({enabled_report.findings_per_100_loc:.2f}) back within the {FP_CEILING} ceiling "
            "on the SAME fixture."
        )


# ---------------------------------------------------------------------------
# (h) FR-001/SC-003 — module-level-only scan: a NESTED import must NOT
# suppress a genuine deletion (guards the `ast.walk` regression).
# ---------------------------------------------------------------------------

class TestNestedImportDoesNotSuppressGenuineDeletion:
    """SC-003 (#2031 finding 2): `_head_still_exports_name` scans MODULE-LEVEL
    statements only. An unrelated ``from x import parse`` / bare
    ``import parse`` buried inside a function or method body is NOT a
    module-level re-export of the origin file — genuinely deleting
    ``def parse()`` must still be flagged. This guards against reintroducing
    an ``ast.walk`` scan, which flattens nested scopes and would wrongly
    treat those nested imports as if they were exported from the module's
    own namespace.
    """

    def test_genuine_deletion_still_flagged_despite_nested_from_import(
        self, tmp_path: Path
    ) -> None:
        repo = _setup_repo(tmp_path)

        _write(repo, "src/pkg/parser.py", """\
            def parse():
                return 1
        """)
        _write(repo, "tests/test_parser.py", """\
            def test_parse():
                assert parse() == 1
        """)
        base_sha = _commit(repo, "base")

        # Genuine deletion of `parse` — the only `import parse` in the head
        # is NESTED inside an unrelated function, not a module-level
        # re-export. A pre-fix `ast.walk` scan would wrongly find it and
        # suppress this genuine deletion.
        _write(repo, "src/pkg/parser.py", """\
            def unrelated_helper():
                def _lazy():
                    from other_module import parse
                    return parse
                return _lazy()
        """)
        head_sha = _commit(
            repo, "delete parse(); unrelated nested from-import of an unrelated 'parse'"
        )

        report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        flagged = {f.changed_symbol for f in report.findings}
        assert "parse" in flagged, (
            "a nested (non-module-level) from-import must NOT suppress a genuine "
            f"deletion of 'parse', got: {report.findings}"
        )

    def test_genuine_deletion_still_flagged_despite_nested_bare_import(
        self, tmp_path: Path
    ) -> None:
        repo = _setup_repo(tmp_path)

        _write(repo, "src/pkg/parser.py", """\
            def parse():
                return 1
        """)
        _write(repo, "tests/test_parser.py", """\
            def test_parse():
                assert parse() == 1
        """)
        base_sha = _commit(repo, "base")

        # Genuine deletion of `parse` — the only `import parse` in the head
        # is NESTED inside an unrelated method, not module-level.
        _write(repo, "src/pkg/parser.py", """\
            class Unrelated:
                def method(self):
                    import parse
                    return parse
        """)
        head_sha = _commit(
            repo, "delete parse(); unrelated nested bare import inside a method"
        )

        report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        flagged = {f.changed_symbol for f in report.findings}
        assert "parse" in flagged, (
            "a nested bare 'import parse' inside a method must NOT suppress a "
            f"genuine deletion of 'parse', got: {report.findings}"
        )


class TestModuleLevelBareImportSuppressesPerDesign:
    """Documents the INTENDED counterpart to the guard above: a MODULE-LEVEL
    bare ``import parse`` still suppresses, per the head-importability rule —
    even though it binds an unrelated module of the same name rather than
    re-exporting the deleted function. The analyzer sees names, not
    qualnames, and resolving that collision would require inspecting the
    imported module's own contents (out of scope, NFR-002). This is a known,
    accepted precision/recall trade-off, distinct from the nested-scope bug
    guarded by ``TestNestedImportDoesNotSuppressGenuineDeletion`` above.
    """

    def test_module_level_bare_import_suppresses(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)

        _write(repo, "src/pkg/parser.py", """\
            def parse():
                return 1
        """)
        _write(repo, "tests/test_parser.py", """\
            def test_parse():
                assert parse() == 1
        """)
        base_sha = _commit(repo, "base")

        _write(repo, "src/pkg/parser.py", """\
            import parse
        """)
        head_sha = _commit(
            repo, "delete parse(); add unrelated module-level 'import parse'"
        )

        report = run_check(base_ref=base_sha, head_ref=head_sha, repo_root=repo)

        flagged = {f.changed_symbol for f in report.findings}
        assert "parse" not in flagged, (
            "a module-level bare 'import parse' is documented to suppress per "
            f"the head-importability rule, got: {report.findings}"
        )


# ---------------------------------------------------------------------------
# (i) FR-002 — direct unit coverage of every `_head_still_exports_name` form
# (#2031 finding 1: the acceptance matrix claimed "verified all forms" while
# the __all__/import-as/__init__-re-export branches were 0% tested).
# ---------------------------------------------------------------------------

class TestHeadStillExportsNameAllForms:
    """Direct unit tests proving each documented re-export FORM suppresses,
    at the analyzer's unit level (no git fixture needed) — these exercise
    the ``__all__``/aliased-import/``__init__.py`` branches that the
    end-to-end git fixtures above never reach.
    """

    def test_dunder_all_list_containing_name_suppresses(self) -> None:
        tree = ast.parse("__all__ = ['parse', 'other']\n")
        assert _head_still_exports_name(tree, "parse") is True

    def test_dunder_all_tuple_containing_name_suppresses(self) -> None:
        tree = ast.parse("__all__ = ('parse', 'other')\n")
        assert _head_still_exports_name(tree, "parse") is True

    def test_dunder_all_not_containing_name_does_not_suppress(self) -> None:
        tree = ast.parse("__all__ = ['other']\n")
        assert _head_still_exports_name(tree, "parse") is False

    def test_non_dunder_all_assign_at_module_level_does_not_suppress(self) -> None:
        # A module-level assignment to something other than __all__ is not
        # a re-export marker.
        tree = ast.parse("OTHER = ['parse']\n")
        assert _head_still_exports_name(tree, "parse") is False

    def test_dunder_all_assigned_non_sequence_does_not_suppress(self) -> None:
        # __all__ assigned to something other than a list/tuple/set literal
        # (e.g. built dynamically) is not statically inspectable — treat as
        # not-exported rather than guessing.
        tree = ast.parse("__all__ = SOME_COMPUTED_VALUE\n")
        assert _head_still_exports_name(tree, "parse") is False

    def test_aliased_plain_import_binds_local_name_suppresses(self) -> None:
        # `import mod as parse` binds the local name `parse`.
        tree = ast.parse("import mod as parse\n")
        assert _head_still_exports_name(tree, "parse") is True

    def test_plain_import_of_name_itself_suppresses(self) -> None:
        # `import parse` binds the local name `parse` directly.
        tree = ast.parse("import parse\n")
        assert _head_still_exports_name(tree, "parse") is True

    def test_dotted_plain_import_binds_only_top_level_package(self) -> None:
        # `import foo.parse` binds `foo`, NOT `parse` — must not suppress.
        tree = ast.parse("import foo.parse\n")
        assert _head_still_exports_name(tree, "parse") is False
        assert _head_still_exports_name(tree, "foo") is True

    def test_from_import_alias_suppresses(self) -> None:
        # `from mod import other as parse` binds the local name `parse`.
        tree = ast.parse("from mod import other as parse\n")
        assert _head_still_exports_name(tree, "parse") is True

    def test_init_style_module_reexport_suppresses(self) -> None:
        # __init__.py-style: `from .sub import parse` at module level.
        tree = ast.parse("from .sub import parse\n", filename="__init__.py")
        assert _head_still_exports_name(tree, "parse") is True

    def test_none_head_tree_does_not_suppress(self) -> None:
        assert _head_still_exports_name(None, "parse") is False
