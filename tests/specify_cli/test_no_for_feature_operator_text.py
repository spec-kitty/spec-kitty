"""FR-014 (mission-writer-followups): keep "for feature" / leading "Feature:"
out of operator-facing text under ``src/specify_cli``.

The Terminology Canon forbids "feature" for a Mission in operator-facing text
(charter, Terminology Canon; #5885). This module scans every NON-docstring
string constant under ``src/specify_cli`` and fails if any such string contains
``"for feature"`` or begins (after leading whitespace) with ``"Feature:"``.

The scan reconstructs a *static string skeleton* for every string-producing
expression, so it catches the wording regardless of how the string was
constructed:

* **f-string** — the literal parts of an ``ast.JoinedStr`` are joined, dynamic
  ``{...}`` holes become empty placeholders;
* **concatenation** — adjacent string literals are folded by the parser, and
  explicit ``"a" + "b"`` string ``BinOp(Add)`` is folded here;
* **variable / ``.format``** — a plain ``ast.Constant`` (whether assigned to a
  name, passed as an argument, or the template of a ``.format(...)`` call) is
  checked directly.

Two STRUCTURAL exemptions (each with its own test below), never a literal
allowlist of offending strings:

1. the module-level legacy-subject constant the finalize drift check keeps for
   back-compat (FR-013) — any module-level assignment whose target name
   contains ``LEGACY``;
2. hosted-only modules — files matching ``tracker/saas_*`` (C-007: the hosted
   Team Kitty strings stay out of scope).

The machine-contract error CODE ``FEATURE_CONTEXT_UNRESOLVED`` is deliberately
NOT in scope (it is a stable contract token, not operator prose) and is filed
as a follow-up.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "specify_cli"

_FORBIDDEN_SUBSTRING = "for feature"
_FORBIDDEN_LEADING = "feature:"


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def _is_hosted_only_path(rel_path: str) -> bool:
    """Structural exemption 2: hosted-only ``tracker/saas_*`` modules (C-007)."""
    parts = Path(rel_path).parts
    return any(parts[i] == "tracker" and i + 1 < len(parts) and parts[i + 1].startswith("saas_") for i in range(len(parts)))


def _string_skeleton(node: ast.AST) -> str | None:
    """Static string value of a str-producing expression, or ``None``.

    Dynamic parts of an f-string become empty placeholders so the surrounding
    literal text (e.g. ``" for feature "``) is still matched as one span.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:  # FormattedValue — a dynamic {...} hole
                parts.append("")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _string_skeleton(node.left)
        right = _string_skeleton(node.right)
        if left is None and right is None:
            return None
        return (left or "") + (right or "")
    return None


def _is_offender(skeleton: str) -> bool:
    low = skeleton.lower()
    if _FORBIDDEN_SUBSTRING in low:
        return True
    return low.lstrip().startswith(_FORBIDDEN_LEADING)


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """Node ids of module/class/function docstring Constants (scan skips them)."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _legacy_exempt_node_ids(tree: ast.AST) -> set[int]:
    """Node ids of string values assigned to a module-level ``*LEGACY*`` name.

    Structural exemption 1 (FR-013): the finalize drift check keeps the legacy
    "Add tasks for feature {mission_slug}" subject as a named module-level
    constant. Any module-level assignment target whose name contains ``LEGACY``
    exempts its string value.
    """
    out: set[int] = set()
    module = tree if isinstance(tree, ast.Module) else None
    if module is None:
        return out
    for stmt in module.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets = [stmt.target]
            value = stmt.value
        if value is None:
            continue
        if any(isinstance(t, ast.Name) and "LEGACY" in t.id.upper() for t in targets):
            for sub in ast.walk(value):
                out.add(id(sub))
    return out


def scan_python_source(source: str, rel_path: str) -> list[str]:
    """Return a sorted list of offender descriptions for one Python source.

    Honors both structural exemptions. The ``rel_path`` is used for the
    hosted-only exemption and for human-readable offender locations.
    """
    if _is_hosted_only_path(rel_path):
        return []
    tree = ast.parse(source)
    skip = _docstring_node_ids(tree) | _legacy_exempt_node_ids(tree)
    offenders: dict[tuple[int, int], str] = {}
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        skeleton = _string_skeleton(node)
        if skeleton is None or not _is_offender(skeleton):
            continue
        lineno = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)
        offenders.setdefault((lineno, col), f"{rel_path}:{lineno}: {skeleton!r}")
    return [offenders[key] for key in sorted(offenders)]


def scan_tree(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root.parent).as_posix()
        offenders.extend(scan_python_source(path.read_text(encoding="utf-8"), rel))
    return offenders


# ---------------------------------------------------------------------------
# Primary guard: the real tree is clean
# ---------------------------------------------------------------------------


def test_no_for_feature_operator_text_in_src() -> None:
    offenders = scan_tree(SRC_ROOT)
    assert offenders == [], (
        "operator-facing text under src/specify_cli must say 'mission', not "
        '"for feature" / a leading "Feature:" (Terminology Canon, #5885):\n' + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# Offender-form coverage (one synthetic offender per construction form)
# ---------------------------------------------------------------------------


def test_scan_catches_fstring_offender() -> None:
    src = 'def f(slug):\n    return f"Add tasks for feature {slug}"\n'
    assert scan_python_source(src, "pkg/mod.py")


def test_scan_catches_adjacent_concatenation_offender() -> None:
    src = 'MSG = ("Add tasks "\n       "for feature X")\n'
    assert scan_python_source(src, "pkg/mod.py")


def test_scan_catches_explicit_plus_concatenation_offender() -> None:
    src = 'def f(slug):\n    return "Add tasks for " + "feature " + slug\n'
    assert scan_python_source(src, "pkg/mod.py")


def test_scan_catches_variable_offender() -> None:
    src = 'MSG = "Status not found for feature here"\ndef f():\n    return MSG\n'
    assert scan_python_source(src, "pkg/mod.py")


def test_scan_catches_format_template_offender() -> None:
    src = 'def f(slug):\n    return "Add tasks for feature {}".format(slug)\n'
    assert scan_python_source(src, "pkg/mod.py")


def test_scan_catches_leading_feature_colon_offender() -> None:
    src = 'def f(slug):\n    print(f"   Feature: {slug}")\n'
    assert scan_python_source(src, "pkg/mod.py")


# ---------------------------------------------------------------------------
# Near-miss negatives (must stay green)
# ---------------------------------------------------------------------------


def test_scan_ignores_clean_mission_wording() -> None:
    src = 'def f(slug):\n    return f"Add tasks for mission {slug}"\n'
    assert scan_python_source(src, "pkg/mod.py") == []


def test_scan_ignores_feature_identifier_loops() -> None:
    src = "def f(dirs):\n    return [feature_dir for feature_dir in dirs]\n"
    assert scan_python_source(src, "pkg/mod.py") == []


def test_scan_ignores_docstring_mentions() -> None:
    src = '"""Helper for feature detection.\n\nFeature: notes.\n"""\nX = 1\n'
    assert scan_python_source(src, "pkg/mod.py") == []


# ---------------------------------------------------------------------------
# Structural exemption 1: the legacy-subject constant (FR-013)
# ---------------------------------------------------------------------------


def test_legacy_subject_module_constant_is_exempt() -> None:
    src = '_LEGACY_FINALIZE_BOOKKEEPING_SUBJECT = "Add tasks for feature {mission_slug}"\n'
    assert scan_python_source(src, "pkg/mod.py") == []


def test_legacy_exemption_is_name_scoped_not_a_blanket_allow() -> None:
    """The exemption follows the ``*LEGACY*`` name, not the string value — a
    non-legacy constant with the same text is still reported."""
    src = 'CURRENT_SUBJECT = "Add tasks for feature {mission_slug}"\n'
    assert scan_python_source(src, "pkg/mod.py")


# ---------------------------------------------------------------------------
# Structural exemption 2: hosted-only tracker/saas_* modules (C-007)
# ---------------------------------------------------------------------------


def test_hosted_only_saas_module_is_exempt() -> None:
    src = 'MSG = "No tracker binding exists for feature `{feature_slug}`."\n'
    assert scan_python_source(src, "specify_cli/tracker/saas_readiness.py") == []


def test_hosted_only_exemption_does_not_cover_non_saas_tracker_modules() -> None:
    src = 'MSG = "No tracker binding exists for feature `{feature_slug}`."\n'
    assert scan_python_source(src, "specify_cli/tracker/origin.py")


# ---------------------------------------------------------------------------
# FR-013: the finalize drift check accepts BOTH the new "mission" subject and
# the legacy "feature" subject (Missions finalized earlier raise no false
# drift), while any other subject on the same history still reads as drift.
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _commit_empty(repo: Path, subject: str) -> str:
    _git(repo, "commit", "-q", "--allow-empty", "-m", subject)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def finalize_drift_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    recorded = _commit_empty(repo, "seed planning commit")
    return repo, recorded


def test_drift_check_accepts_the_new_mission_subject(finalize_drift_repo: tuple[Path, str]) -> None:
    """RED on the pre-fix tree: finalize's own bookkeeping subject becomes
    "Add tasks for mission <slug>", but the drift check only recognised the
    "feature" wording, so a Mission finalized after this change false-drifts."""
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import (
        _drift_is_finalize_bookkeeping_only,
    )

    repo, recorded = finalize_drift_repo
    tip = _commit_empty(repo, "Add tasks for mission demo-slug")
    assert _drift_is_finalize_bookkeeping_only(repo, "demo-slug", recorded, tip) is True


def test_drift_check_accepts_the_legacy_feature_subject(finalize_drift_repo: tuple[Path, str]) -> None:
    """A Mission finalized BEFORE this change (legacy "feature" subject) must
    still be treated as finalize bookkeeping — no false drift (FR-013)."""
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import (
        _drift_is_finalize_bookkeeping_only,
    )

    repo, recorded = finalize_drift_repo
    tip = _commit_empty(repo, "Add tasks for feature demo-slug")
    assert _drift_is_finalize_bookkeeping_only(repo, "demo-slug", recorded, tip) is True


def test_drift_check_still_flags_a_foreign_subject(finalize_drift_repo: tuple[Path, str]) -> None:
    """A genuine planning amendment on the same history still reads as drift."""
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import (
        _drift_is_finalize_bookkeeping_only,
    )

    repo, recorded = finalize_drift_repo
    tip = _commit_empty(repo, "Amend the spec after review")
    assert _drift_is_finalize_bookkeeping_only(repo, "demo-slug", recorded, tip) is False


def test_finalize_bookkeeping_subject_says_mission() -> None:
    """FR-012: finalize's own bookkeeping commit subject says "mission"."""
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import (
        _finalize_bookkeeping_commit_message,
    )

    assert _finalize_bookkeeping_commit_message("demo-slug") == "Add tasks for mission demo-slug"
