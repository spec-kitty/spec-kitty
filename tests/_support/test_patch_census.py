"""Controls for the patch census tool (a reporting tool, not a gate: no thresholds here but a sanity floor)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from collections import Counter
from pathlib import Path
from unittest import mock

import pytest

from tests.architectural._ast_scan import UnparseableSourceError
from tests._support import patch_census as pc
from tests._support.patch_census import (
    BUCKET_FAMILY,
    BUCKET_OTHER,
    BUCKET_SOURCE,
    BUCKET_STDLIB,
    CensusReport,
    PatchSite,
    derive_family_reads,
    load_runtime,
    patched_names_on,
    scan_static,
)

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
FAMILY = "specify_cli.core.mission_creation"
HEADER = "from unittest.mock import patch\nimport importlib\nimport sys\n"

# Synthetic family source: it reads these names (module-level, function-local and relative imports).
FAMILY_SOURCE = """
import subprocess
from specify_cli.core.git_ops import get_current_branch, resolve_primary_branch as rpb
from ulid import ULID
from . import paths


def create() -> None:
    from specify_cli.git.protection_policy import ProtectionPolicy
    import os
    from .helpers import local_helper
"""


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A synthetic repo: ``src/`` with a family module and a few importable modules, plus ``tests/``."""
    core = tmp_path / "src" / "specify_cli" / "core"
    core.mkdir(parents=True)
    (core / "mission_creation.py").write_text(FAMILY_SOURCE, encoding="utf-8")
    (core / "mission_creation_helpers.py").write_text("import shutil\n", encoding="utf-8")
    for name in ("git_ops", "paths", "helpers", "unrelated"):
        (core / f"{name}.py").write_text("", encoding="utf-8")
    git = tmp_path / "src" / "specify_cli" / "git"
    git.mkdir()
    (git / "protection_policy.py").write_text("", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    return tmp_path


def census(tree: Path, source: str, *, derive: bool = False) -> CensusReport:
    (tree / "tests" / "test_sample.py").write_text(HEADER + textwrap.dedent(source), encoding="utf-8")
    if not derive:
        return scan_static(tree / "tests")
    reads = derive_family_reads(tree / "src")
    return scan_static(tree / "tests", family_read_names=reads.names, read_sources=reads.sources)


def triples(report: CensusReport, bucket: str = BUCKET_FAMILY) -> list[tuple[str, str, str]]:
    return sorted((s.module, s.attr, s.form) for s in report.sites if s.bucket == bucket)


# --------------------------------------------------------------------------- #
# Positive controls: every supported form counted exactly once per site
# --------------------------------------------------------------------------- #

_ALIAS_IMPORT = "import specify_cli.core.mission_creation as m\n"
POSITIVE: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    ("string_literal", f'def t():\n    patch("{FAMILY}.safe_commit")\n', [(FAMILY, "safe_commit", "patch")]),
    (
        "fstring_over_constant",
        f'_CORE = "{FAMILY}"\ndef t():\n    patch(f"{{_CORE}}.is_git_repo")\n',
        [(FAMILY, "is_git_repo", "patch")],
    ),
    (
        "string_concat",
        f'_CORE = "{FAMILY}"\ndef t():\n    patch(_CORE + ".x")\n    patch("{FAMILY}" + ".y")\n',
        [(FAMILY, "x", "patch"), (FAMILY, "y", "patch")],
    ),
    ("monkeypatch_setattr_string", f'def t(monkeypatch):\n    monkeypatch.setattr("{FAMILY}.safe_commit", 1)\n', [(FAMILY, "safe_commit", "setattr")]),
    ("attribute_chain", f'def t():\n    patch("{FAMILY}.subprocess.run")\n', [(FAMILY, "subprocess.run", "patch")]),
    ("import_as", _ALIAS_IMPORT + 'def t(monkeypatch):\n    monkeypatch.setattr(m, "x", 1)\n', [(FAMILY, "x", "setattr")]),
    (
        "from_import_module",
        'from specify_cli.core import mission_creation as mc\ndef t(monkeypatch):\n    monkeypatch.setattr(mc, "x", 1)\n',
        [(FAMILY, "x", "setattr")],
    ),
    (
        "function_scope_import",
        'def t(monkeypatch):\n    from specify_cli.core import mission_creation\n    monkeypatch.setattr(mission_creation, "x", 1)\n',
        [(FAMILY, "x", "setattr")],
    ),
    ("patch_object", _ALIAS_IMPORT + 'def t():\n    patch.object(m, "x")\n', [(FAMILY, "x", "patch.object")]),
    ("patch_object_chain", _ALIAS_IMPORT + 'def t():\n    patch.object(m.subprocess, "run")\n', [(FAMILY, "subprocess.run", "patch.object")]),
    (
        "patch_multiple_object",
        _ALIAS_IMPORT + "def t():\n    patch.multiple(m, a=1, b=2)\n",
        [(FAMILY, "a", "patch.multiple"), (FAMILY, "b", "patch.multiple")],
    ),
    (
        "patch_multiple_string",
        f'def t():\n    patch.multiple("{FAMILY}", a=1)\n',
        [(FAMILY, "a", "patch.multiple")],
    ),
    ("monkeypatch_delattr", _ALIAS_IMPORT + 'def t(monkeypatch):\n    monkeypatch.delattr(m, "x")\n', [(FAMILY, "x", "delattr")]),
    ("monkeypatch_delattr_string", f'def t(monkeypatch):\n    monkeypatch.delattr("{FAMILY}.x")\n', [(FAMILY, "x", "delattr")]),
    ("mocker_patch", f'def t(mocker):\n    mocker.patch("{FAMILY}.x")\n    mocker.patch.object(mocker, "y")\n', [(FAMILY, "x", "patch")]),
    (
        "patch_dict_module_dict",
        _ALIAS_IMPORT + 'def t():\n    patch.dict(m.__dict__, {"a": 1}, b=2)\n',
        [(FAMILY, "a", "patch.dict"), (FAMILY, "b", "patch.dict")],
    ),
    ("patch_dict_vars", _ALIAS_IMPORT + "def t():\n    patch.dict(vars(m), {'a': 1})\n", [(FAMILY, "a", "patch.dict")]),
    ("setitem_vars", _ALIAS_IMPORT + 'def t(monkeypatch):\n    monkeypatch.setitem(vars(m), "a", 1)\n', [(FAMILY, "a", "setitem")]),
    ("setitem_dunder_dict", _ALIAS_IMPORT + 'def t(monkeypatch):\n    monkeypatch.setitem(m.__dict__, "a", 1)\n', [(FAMILY, "a", "setitem")]),
    (
        "patch_dict_sys_modules",
        f'def t():\n    patch.dict(sys.modules, {{"{FAMILY}": object()}})\n',
        [(FAMILY, "<module>", "sys_modules")],
    ),
    (
        "setitem_sys_modules",
        f'def t(monkeypatch):\n    monkeypatch.setitem(sys.modules, "{FAMILY}", object())\n',
        [(FAMILY, "<module>", "sys_modules")],
    ),
    ("attribute_assignment", _ALIAS_IMPORT + "def t():\n    m.safe_commit = lambda: None\n", [(FAMILY, "safe_commit", "assign")]),
    ("attribute_chain_assignment", _ALIAS_IMPORT + "def t():\n    m.subprocess.run = print\n", [(FAMILY, "subprocess.run", "assign")]),
    (
        "importlib_alias",
        f'def t(monkeypatch):\n    mod = importlib.import_module("{FAMILY}")\n    monkeypatch.setattr(mod, "x", 1)\n',
        [(FAMILY, "x", "setattr")],
    ),
    (
        "importlib_inline",
        f'def t(monkeypatch):\n    monkeypatch.setattr(importlib.import_module("{FAMILY}"), "x", 1)\n',
        [(FAMILY, "x", "setattr")],
    ),
    (
        "alias_dunder_name_fstring",
        _ALIAS_IMPORT + 'def t():\n    patch(f"{m.__name__}.x")\n',
        [(FAMILY, "x", "patch")],
    ),
    ("future_sibling_module", f'def t():\n    patch("{FAMILY}_helpers.x")\n', [(f"{FAMILY}_helpers", "x", "patch")]),
]


@pytest.mark.parametrize(("source", "expected"), [(p[1], p[2]) for p in POSITIVE], ids=[p[0] for p in POSITIVE])
def test_each_supported_form_is_counted_exactly_once_per_site(tree: Path, source: str, expected: list[tuple[str, str, str]]) -> None:
    report = census(tree, source)
    assert triples(report) == sorted(expected)
    assert report.unresolved == ()


def test_by_name_by_file_and_by_namespace_helpers(tree: Path) -> None:
    report = census(tree, f'def t():\n    patch("{FAMILY}.a")\n    patch("{FAMILY}.a")\n    patch("{FAMILY}_helpers.b")\n')
    assert report.count() == 3
    assert report.by_name(BUCKET_FAMILY) == Counter({"a": 2, "b": 1})
    assert report.by_file(BUCKET_FAMILY) == Counter({"tests/test_sample.py": 3})
    assert report.by_namespace(BUCKET_FAMILY) == Counter({FAMILY: 2, f"{FAMILY}_helpers": 1})
    assert report.by_form(BUCKET_FAMILY) == Counter({"patch": 3})
    assert report.sites[0] == PatchSite("tests/test_sample.py", 5, FAMILY, "a", "patch", BUCKET_FAMILY)
    assert report.summary()["totals"][BUCKET_FAMILY] == 3


# --------------------------------------------------------------------------- #
# Negative controls
# --------------------------------------------------------------------------- #


def test_unrelated_module_patch_is_not_counted(tree: Path) -> None:
    report = census(
        tree,
        """
        import specify_cli.core.unrelated as u
        def t(monkeypatch):
            patch("specify_cli.core.unrelated.safe_commit")
            patch.object(u, "safe_commit")
            monkeypatch.setattr(u, "x", 1)
            patch("specify_cli.core.mission_creation_other_thing")  # module itself, still family (control below)
        """,
    )
    assert [s.module for s in report.sites] == [f"{FAMILY}_other_thing"]


def test_same_name_on_unrelated_module_is_not_family_and_needs_read_names(tree: Path) -> None:
    source = 'def t():\n    patch("specify_cli.core.unrelated.get_current_branch")\n'
    assert census(tree, source).sites == ()
    report = census(tree, source, derive=True)
    assert report.count(BUCKET_FAMILY) == 0
    assert report.count(BUCKET_OTHER) == 1
    assert report.count(BUCKET_SOURCE) == 0


# --------------------------------------------------------------------------- #
# Laundering onto source modules, derived read names
# --------------------------------------------------------------------------- #


def test_derive_family_reads_collects_module_level_function_local_and_relative_imports(tree: Path) -> None:
    reads = derive_family_reads(tree / "src")
    assert {"subprocess", "get_current_branch", "resolve_primary_branch", "rpb", "ULID", "paths", "ProtectionPolicy", "os", "local_helper"} <= reads.names
    assert reads.sources["get_current_branch"] == frozenset({"specify_cli.core.git_ops"})
    assert reads.sources["rpb"] == frozenset({"specify_cli.core.git_ops"})
    assert reads.sources["ProtectionPolicy"] == frozenset({"specify_cli.git.protection_policy"})
    assert reads.sources["local_helper"] == frozenset({"specify_cli.core.helpers"})
    assert reads.sources["paths"] == frozenset({"specify_cli.core"})
    assert "shutil" in reads.names  # a sibling family file (mission_creation_helpers.py) is scanned too
    assert reads.source_modules >= {"subprocess", "specify_cli.core.git_ops"}


def test_laundered_source_namespace_stdlib_and_process_global_patches_are_bucketed(tree: Path) -> None:
    report = census(
        tree,
        """
        import specify_cli.core.git_ops as g
        def t(monkeypatch):
            patch("specify_cli.core.git_ops.get_current_branch")
            monkeypatch.setattr(g, "resolve_primary_branch", 1)
            patch("specify_cli.git.protection_policy.ProtectionPolicy.resolve")
            patch("specify_cli.core.git_ops.subprocess.run")
            patch("subprocess.run")
            patch("os.environ")
            patch("ulid.ULID")
            patch("specify_cli.core.git_ops.os")
        """,
        derive=True,
    )
    assert triples(report, BUCKET_SOURCE) == [
        ("specify_cli.core.git_ops", "get_current_branch", "patch"),
        ("specify_cli.core.git_ops", "resolve_primary_branch", "setattr"),
        ("specify_cli.git.protection_policy", "ProtectionPolicy.resolve", "patch"),
        ("ulid", "ULID", "patch"),
    ]
    assert sorted(s.module + ":" + s.attr for s in report.sites if s.bucket == BUCKET_STDLIB) == [
        "os:environ",
        "specify_cli.core.git_ops:subprocess.run",
        "subprocess:run",
    ]
    assert triples(report, BUCKET_OTHER) == [("specify_cli.core.git_ops", "os", "patch")]
    assert report.count(BUCKET_FAMILY) == 0


def test_restricted_to_limits_the_report_to_an_explicit_file_list(tree: Path) -> None:
    report = census(tree, f'def t():\n    patch("{FAMILY}.a")\n')
    assert report.restricted_to(["tests/test_sample.py"]).count() == 1
    assert report.restricted_to(["tests/other.py"]).count() == 0


# --------------------------------------------------------------------------- #
# Unresolved sites are reported, never dropped
# --------------------------------------------------------------------------- #


def test_unresolvable_targets_are_reported_and_only_family_dependent_ones_are_suspects(tree: Path) -> None:
    report = census(
        tree,
        """
        import specify_cli.core.mission_creation as m
        def t(monkeypatch, target, name):
            patch(target)
            monkeypatch.setattr(target, 1)
            patch.object(m, name)
            patch.dict(m.__dict__, build())
            patch(f"{prefix}.x")
            patch(f"{m.__name__}.{name}")
        """,
    )
    assert len(report.unresolved) == 6
    assert sorted(u.form for u in report.family_targeting_unresolved()) == ["patch", "patch.dict", "patch.object"]


def test_comment_only_and_unused_constant_mentions_are_not_family_suspects(tree: Path) -> None:
    report = census(
        tree,
        """
        # patches specify_cli.core.mission_creation elsewhere
        CORE = "specify_cli.core.mission_creation"
        MODULE = "specify_cli.cli.commands.agent.mission"
        def t(target, mapping):
            for k, v in mapping.items():
                patch(k, v)
            patch(target)
        """,
    )
    assert len(report.unresolved) == 2
    assert report.family_targeting_unresolved() == ()


def test_loop_over_literal_family_targets_resolves_to_sites_and_unresolved_loop_over_family_is_suspect(tree: Path) -> None:
    report = census(
        tree,
        f"""
        TARGETS = ("{FAMILY}.is_git_repo", "{FAMILY}.get_current_branch")
        TABLE = {{"{FAMILY}.ULID": 1, "specify_cli.core.unrelated.x": 2}}
        def t():
            for target in TARGETS:
                patch(target)
            for k, v in TABLE.items():
                patch(k, v)
            for a, b in (("{FAMILY}.paths", 1), ("{FAMILY}.helpers", 2)):
                patch(a, b)
        """,
    )
    assert [a for _, a, _ in triples(report)] == ["ULID", "get_current_branch", "helpers", "is_git_repo", "paths"]
    assert report.unresolved == ()


def test_unresolved_loop_over_family_literal_is_a_suspect(tree: Path) -> None:
    report = census(
        tree,
        f"""
        ROWS = [("{FAMILY}.x", object()), (dynamic(), object())]
        def t():
            for k, v in ROWS:
                patch(k, v)
        """,
    )
    assert [s.attr for s in report.sites] == ["x"]  # the resolvable row counts
    assert all(u.family_suspect for u in report.unresolved)


def test_parametrized_literal_targets_resolve_per_row(tree: Path) -> None:
    report = census(
        tree,
        f"""
        import pytest
        @pytest.mark.parametrize("failure_target", ["{FAMILY}.a", "{FAMILY}.b"], ids=["a", "b"])
        def t(monkeypatch, failure_target):
            monkeypatch.setattr(failure_target, 1)
        @pytest.mark.parametrize("tgt,val", [(pytest.param("{FAMILY}.c"), 1)])
        def u(tgt, val):
            patch(tgt, val)
        """,
    )
    assert [a for _, a, _ in triples(report)] == ["a", "b"]
    # a row that wraps its value in ``pytest.param`` inside a tuple is not resolved, and is reported rather than dropped
    assert len(report.unresolved) == 1


# --------------------------------------------------------------------------- #
# Aliased patch / mock bindings (B1)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "imports, call, expected",
    [
        ("from unittest.mock import patch as p", 'p("{F}.aliased_patch")', ("aliased_patch", "patch")),
        ("from unittest import mock as um", 'um.patch("{F}.aliased_mod")', ("aliased_mod", "patch")),
        ("import unittest.mock as umock", 'umock.patch.object(mc, "umock_obj")', ("umock_obj", "patch.object")),
        ("from unittest.mock import patch as p", 'p.object(mc, "obj_alias")', ("obj_alias", "patch.object")),
        ("from unittest.mock import patch as p", 'p.multiple("{F}", multi_a=1)', ("multi_a", "patch.multiple")),
        ("from unittest import mock as um", 'um.patch.dict(mc.__dict__, {{"dict_key": 1}})', ("dict_key", "patch.dict")),
        ("from unittest import mock as um\nalias = um.patch", 'alias("{F}.reassigned")', ("reassigned", "patch")),
        ("", 'mocker.patch("{F}.mocker_direct")', ("mocker_direct", "patch")),
        ("", 'mp = mocker\n    mp.patch("{F}.mocker_alias")', ("mocker_alias", "patch")),
    ],
)
def test_aliased_patch_and_mock_bindings_are_counted(tree: Path, imports: str, call: str, expected: tuple[str, str]) -> None:
    body = call.replace("{F}", FAMILY).replace("{{", "{").replace("}}", "}")
    report = census(tree, f"{imports}\nimport specify_cli.core.mission_creation as mc\ndef t(mocker):\n    {body}\n")
    assert [(a, f) for _, a, f in triples(report)] == [expected]
    assert report.unresolved == ()


def test_function_local_alias_import_is_scoped_and_client_patch_is_still_ignored(tree: Path) -> None:
    report = census(
        tree,
        f"""
        def t(client):
            from unittest.mock import patch as local_p
            local_p("{FAMILY}.scoped")
            client.patch("{FAMILY}.not_a_patch")
        def u(local_p):
            local_p("{FAMILY}.outside_scope")
        """,
    )
    assert [a for _, a, _ in triples(report)] == ["scoped"]


# --------------------------------------------------------------------------- #
# Rebinding, prefix boundary, placeholder filtering
# --------------------------------------------------------------------------- #


def test_alias_rebound_to_a_non_module_value_is_no_longer_a_family_assignment(tree: Path) -> None:
    report = census(
        tree,
        """
        import specify_cli.core.mission_creation as mc
        def t():
            mc = object()
            mc.rebound = 1
        def u():
            mc.real = 1
        """,
    )
    assert [a for _, a, _ in triples(report)] == ["real"]


def test_family_prefix_requires_a_name_boundary(tree: Path) -> None:
    report = census(
        tree,
        f"""
        def t():
            patch("{FAMILY}XYZ.q")
            patch("{FAMILY}_helpers.ok")
            patch("{FAMILY}.exact")
        """,
    )
    assert [m for m, _, _ in triples(report)] == [FAMILY, f"{FAMILY}_helpers"]


def test_unresolved_in_a_file_that_never_mentions_the_family_is_not_a_suspect(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_other.py").write_text("from unittest.mock import patch\n\ndef t(target):\n    patch(target)\n", encoding="utf-8")
    report = scan_static(tmp_path / "tests")
    assert len(report.unresolved) == 1
    assert report.family_targeting_unresolved() == ()


def test_plain_paths_and_unrelated_calls_are_not_patch_targets(tree: Path) -> None:
    report = census(tree, 'def t(client):\n    client.patch("/api/missions")\n    patch("/api/missions")\n    setattr(object(), "x", 1)\n')
    assert report.sites == ()


def test_excluded_files_are_not_scanned(tree: Path) -> None:
    source = f'def t():\n    patch("{FAMILY}.a")\n'
    census(tree, source)
    assert scan_static(tree / "tests", exclude_files=frozenset({"tests/test_sample.py"})).sites == ()
    assert "tests/_support/test_patch_census.py" in pc.DEFAULT_EXCLUDED_FILES


def test_unparseable_files_fail_the_census_closed(tree: Path) -> None:
    """An unparseable test file is never silently dropped from the count."""
    (tree / "tests" / "test_broken.py").write_text("def (:\n", encoding="utf-8")
    with pytest.raises(UnparseableSourceError, match="test_broken.py"):
        census(tree, "x = 1\n")


# --------------------------------------------------------------------------- #
# patched_names_on (the family routing check uses it for set equality)
# --------------------------------------------------------------------------- #


def test_patched_names_on_returns_first_chain_segments_for_exactly_that_module(tree: Path) -> None:
    (tree / "tests" / "test_sample.py").write_text(
        HEADER + f'def t():\n    patch("{FAMILY}.a")\n    patch("{FAMILY}.subprocess.run")\n    patch("{FAMILY}_helpers.zzz")\n',
        encoding="utf-8",
    )
    assert patched_names_on(FAMILY, tree / "tests", src_root=tree / "src") == frozenset({"a", "subprocess"})
    assert patched_names_on(f"{FAMILY}_helpers", tree / "tests", src_root=tree / "src") == frozenset({"zzz"})


def test_patched_names_on_never_returns_placeholders(tree: Path) -> None:
    (tree / "tests" / "test_sample.py").write_text(
        HEADER + f'def t(monkeypatch):\n    patch.dict(sys.modules, {{"{FAMILY}": 1}})\n    patch("{FAMILY}.real")\n',
        encoding="utf-8",
    )
    assert patched_names_on(FAMILY, tree / "tests", src_root=tree / "src") == frozenset({"real"})


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_report_text_and_json_and_files_from(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tree / "tests" / "test_sample.py").write_text(
        HEADER + f'def t():\n    patch("{FAMILY}.a")\n    patch("specify_cli.core.git_ops.get_current_branch")\n', encoding="utf-8"
    )
    listing = tree / "files.md"
    listing.write_text("## Appendix — covering test set\n\n```\ntests/test_sample.py\n```\nignored tests/not_in_appendix.py\n", encoding="utf-8")
    assert pc.main(["--report", "--tests-root", str(tree / "tests"), "--files-from", str(listing)]) == 0
    text = capsys.readouterr().out
    assert "family facade sites (bucket a, whole tree): 1" in text
    assert "source-namespace sites (bucket b, 1-file list): 1" in text
    assert pc.main(["--report", "--json", "--tests-root", str(tree / "tests"), "--files", "tests/none.py"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["static"]["totals"][BUCKET_FAMILY] == 1
    assert payload["static"]["source_view"]["totals"][BUCKET_SOURCE] == 0
    assert pc.main([]) == 2


def test_read_file_list_accepts_plain_text(tmp_path: Path) -> None:
    listing = tmp_path / "files.txt"
    listing.write_text("tests/a.py\n  tests/b.py\nother\n", encoding="utf-8")
    assert pc._read_file_list(listing) == ["tests/a.py", "tests/b.py"]


# --------------------------------------------------------------------------- #
# Runtime counter
# --------------------------------------------------------------------------- #


def _state() -> pc._RuntimeState:
    reads = derive_family_reads(REPO_ROOT / "src")
    return pc._RuntimeState(pc._Resolver(REPO_ROOT / "src", FAMILY, reads))


def test_runtime_wrappers_count_applications_and_restore_exactly() -> None:
    import specify_cli.core.mission_creation as mission_creation

    state = _state()
    installer = pc._Installer(state)
    originals = (
        pytest.MonkeyPatch.setattr,
        pytest.MonkeyPatch.delattr,
        pytest.MonkeyPatch.setitem,
        mock._patch.__enter__,
        mock._patch_dict.__enter__,
        mock.patch.multiple,
    )
    installer.install()
    try:
        state.current = "synthetic::test"
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(f"{FAMILY}.safe_commit", 1)
            mp.setattr(mission_creation, "preflight_commit", 1)
            mp.delattr(mission_creation, "now_utc_iso")
            mp.setitem(vars(mission_creation), "ULID", 1)
            mp.setitem(sys.modules, "specify_cli.core.mission_creation_nonexistent", 1)
        with mock.patch(f"{FAMILY}.is_git_repo"):
            pass
        with mock.patch.object(mission_creation, "locate_project_root"):
            pass
        with mock.patch.multiple(FAMILY, get_current_branch=1, is_worktree_context=2):
            pass
        with mock.patch.multiple(mission_creation, create_mission_core=1):
            pass
        with mock.patch.dict(mission_creation.__dict__, {"safe_commit": 3}):
            pass
        with mock.patch("subprocess.run"):  # stdlib process-global
            pass
        with mock.patch.dict({}, {"a": 1}):
            pass  # unrelated dict: not counted
    finally:
        installer.uninstall()
    assert originals == (
        pytest.MonkeyPatch.setattr,
        pytest.MonkeyPatch.delattr,
        pytest.MonkeyPatch.setitem,
        mock._patch.__enter__,
        mock._patch_dict.__enter__,
        mock.patch.multiple,
    )
    assert set(state.by_name) >= {
        "safe_commit",
        "preflight_commit",
        "now_utc_iso",
        "ULID",
        "<module>",
        "is_git_repo",
        "locate_project_root",
        "get_current_branch",
        "is_worktree_context",
        "create_mission_core",
    }
    assert state.by_bucket[BUCKET_FAMILY] == 11
    assert state.by_bucket[BUCKET_STDLIB] >= 1
    assert state.by_test == Counter({"synthetic::test": sum(state.by_bucket.values())})
    payload = state.to_json()
    assert payload["applications_total"] == sum(state.by_bucket.values())
    assert payload["tests_with_patches"] == 1


def test_runtime_counts_a_sys_modules_patch_dict_by_name() -> None:
    """``patch.dict("sys.modules", ...)`` is banned in tests (spec-kitty#89/#99), so its
    runtime recording is exercised on the recorder directly rather than by applying it."""
    state = _state()
    pc._record_patch_dict(state, "sys.modules", [FAMILY + "_ghost"])
    assert state.by_bucket[BUCKET_FAMILY] == 1


def _run_pytest(tmp_path: Path, *extra: str, out: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT)]), "PWHEADLESS": "1"}
    env.pop("PYTEST_ADDOPTS", None)
    env.pop(pc.ENV_OUT, None)
    if out is not None:
        env[pc.ENV_OUT] = str(out)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(tmp_path / "pytest.ini"), "--rootdir", str(tmp_path), "-p", "no:cacheprovider", "-q", *extra],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


SAMPLE_TESTS = f'''
from unittest.mock import patch
import pytest

@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr("{FAMILY}.safe_commit", lambda *a, **k: None)

def test_fixture_applied_patch(stub): ...
def test_fixture_applied_again(stub): ...

def test_mock_patch():
    with patch("{FAMILY}.is_git_repo"):
        pass

def test_failure_is_preserved(monkeypatch):
    monkeypatch.setattr("{FAMILY}.now_utc_iso", lambda: "x")
    raise AssertionError("boom")

@pytest.mark.skip
def test_skipped(): ...
'''


@pytest.mark.integration
def test_plugin_does_not_change_outcomes_and_counts_fixture_applications(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    sample = tmp_path / "test_sample_runtime.py"
    sample.write_text(SAMPLE_TESTS, encoding="utf-8")
    out = tmp_path / "census.json"
    baseline = _run_pytest(tmp_path, str(sample))
    counted = _run_pytest(tmp_path, "-p", "tests._support.patch_census", str(sample), out=out)

    def summary(run: subprocess.CompletedProcess[str]) -> str:
        return str(re.findall(r"\d+ \w+(?:, \d+ \w+)*(?= in )", run.stdout)[-1])

    assert baseline.returncode == counted.returncode == 1
    assert summary(baseline) == summary(counted)
    assert "3 passed" in counted.stdout and "1 failed" in counted.stdout and "1 skipped" in counted.stdout
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["applications_total"] == 4  # the stub fixture ran twice, plus one mock.patch and one monkeypatch
    assert result["tests_with_patches"] == 4
    assert result["collected_tests"] == 5
    assert result["by_name"]["safe_commit"] == 2
    assert load_runtime(out)["applications_total"] == 4


def test_load_runtime_merges_per_worker_files(tmp_path: Path) -> None:
    base = tmp_path / "census.json"
    for worker, (n, collected) in {"gw0": (2, 10), "gw1": (3, 10)}.items():
        payload = {
            "applications_total": n,
            "by_name": {"x": n},
            "by_bucket": {BUCKET_FAMILY: n},
            "by_test": {f"t::{worker}": n},
            "outcomes": {"call:passed": 1},
            "collected_tests": collected,
        }
        Path(f"{base}.{worker}.json").write_text(json.dumps(payload), encoding="utf-8")
    merged = load_runtime(base)
    assert merged["applications_total"] == 5
    assert merged["by_name"] == {"x": 5}
    assert merged["tests_with_patches"] == 2
    assert merged["collected_tests"] == 10
    assert merged["workers"] == 2
    assert merged["outcomes"] == {"call:passed": 2}
    text = pc.format_runtime(merged)
    assert "applications total" in text and ": 5" in text
    assert re.search(r"^patch budget applications \(family \+ source\): \d+$", text, re.M)
    assert merged["budget_applications"] == merged["by_bucket"].get("family", 0) + merged["by_bucket"].get("source", 0)
