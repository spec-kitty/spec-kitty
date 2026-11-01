"""The charter artifact-scanning seams are public, and no retired name survives (#6434).

Why this gate exists
--------------------
Issue #6434 is a pre-PR review finding on the #6404–#6408 Mission: the
``IdentityIndex`` added for #6406 was written against five private
``kind_vocabulary`` helpers, and a dozen test modules reached through the same
underscore names to count scans and seed graphs. Discovery had no interface —
only the module's private internals and whatever a reader could infer from them.

The mission promoted those helpers, plus the three other seams the issue names,
to documented module-level API and deleted the private names. This gate is the
red-first proof of that promotion and its recurrence guard:

* **no retired name is reachable** from ``src/`` or ``tests/`` — as an attribute
  on the owning module (``kind_vocabulary._scan_roots``), as an imported name
  (``from charter.activation.kind_vocabulary import _read_id``), or as the string
  argument of a ``setattr``/``patch`` call
  (``monkeypatch.setattr(kind_vocabulary, "_scan_dir_matches", …)``);
* **the public surface exists** — every promoted name resolves on its module and,
  in ``kind_vocabulary``, is listed in ``__all__`` with a docstring.

The gate is deliberately name-anchored per owning module: ``_read_id`` is still a
legitimate private helper in ``charter.offering.packs.pack_assembler`` and
``_config_stem`` in ``charter.activation.pack_manager``, so a bare word scan
would be both wrong and noisy. Planted-source controls prove the scanner can see
each of the three forms, so the "no findings" assertion cannot pass vacuously.

``src/`` and ``tests/`` are scanned, never ``docs/``: the changelog names the
retired identifiers on purpose, for anyone grepping the old spelling.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Owning module → the underscore names this mission retired on it.
_RETIRED: dict[str, frozenset[str]] = {
    "charter.activation.kind_vocabulary": frozenset(
        {
            "_scan_roots",
            "_scan_dir_matches",
            "_iter_artifact_paths",
            "_read_id",
            "_parse_id",
            "_id_field_for",
            "_config_stem",
            "_built_in_scan_dir",
        }
    ),
    "charter.activation.identity_index": frozenset({"_scan"}),
    "charter.activation.action_governance_bundle": frozenset({"_load_action_governance_bundle"}),
    "charter.activation.context": frozenset({"_load_action_governance_bundle"}),
    "charter.activation.compiler": frozenset({"_direct_root_urns"}),
}

#: The public replacements, per owning module. ``kind_vocabulary`` ones must also
#: be exported in ``__all__`` (the module's `__all__` convention).
_PUBLIC: dict[str, tuple[str, ...]] = {
    "charter.activation.kind_vocabulary": (
        "artifact_config_stem",
        "artifact_id_field",
        "built_in_scan_dir",
        "iter_artifact_paths",
        "parse_artifact_id",
        "read_artifact_id",
        "scan_dir_matches",
        "scan_roots",
    ),
    "charter.activation.identity_index": ("IdentityIndex.scan",),
    "charter.activation.action_governance_bundle": ("load_action_governance_bundle",),
    "charter.activation.context": ("load_action_governance_bundle",),
    "charter.activation.compiler": ("direct_root_urns",),
}

#: Retired name → the public name that replaced it, per owning module.
_REPLACEMENTS: dict[str, dict[str, str]] = {
    "charter.activation.kind_vocabulary": {
        "_built_in_scan_dir": "built_in_scan_dir",
        "_config_stem": "artifact_config_stem",
        "_id_field_for": "artifact_id_field",
        "_iter_artifact_paths": "iter_artifact_paths",
        "_parse_id": "parse_artifact_id",
        "_read_id": "read_artifact_id",
        "_scan_dir_matches": "scan_dir_matches",
        "_scan_roots": "scan_roots",
    },
    "charter.activation.identity_index": {"_scan": "scan"},
    "charter.activation.action_governance_bundle": {
        "_load_action_governance_bundle": "load_action_governance_bundle",
    },
    "charter.activation.context": {"_load_action_governance_bundle": "load_action_governance_bundle"},
    "charter.activation.compiler": {"_direct_root_urns": "direct_root_urns"},
}

#: Loose high-recall pre-filter, run by ``git grep`` (C speed, no Python file walk):
#: a file that never spells a retired name cannot reach one. The generic ``_scan``
#: is kept module-qualified so the pre-filter stays specific.
#: A pattern that must always match (the promoted helper's own module spells it), used
#: to prove the pre-filter search itself works rather than finding nothing.
_ALWAYS_PRESENT = "scan_roots"

#: POSIX ERE (``git grep -E``) and Python share this shape: alternation only, no
#: non-capturing groups.
_RETIRED_NAME = re.compile("(" + "|".join(sorted({name for names in _RETIRED.values() for name in names} - {"_scan"})) + r"|IdentityIndex\._scan)")


class Finding(NamedTuple):
    """One retired-name reference: where it is, and which public name replaces it."""

    path: str
    line: int
    reach: str
    replacement: str


def _retired_owner(owner: str | None) -> str | None:
    """The owning module a dotted owner expression belongs to, if it is one of ours."""
    if owner is None:
        return None
    for module in _RETIRED:
        if owner == module or owner.startswith(f"{module}."):
            return module
    return None


def _finding(path: str, node: ast.AST, owner: str, name: str) -> Finding:
    """Build a finding that names the reference as written and its public replacement."""
    reach = f"{owner.rsplit('.', 1)[-1]}.{name}"
    return Finding(path, getattr(node, "lineno", 0), reach, _REPLACEMENTS[owner][name])


def _alias_map(tree: ast.AST) -> dict[str, str]:
    """Map each local name in *tree* to the dotted path it was imported from."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                if imported.asname:
                    aliases[imported.asname] = imported.name
                else:
                    head = imported.name.split(".", 1)[0]
                    aliases[head] = head
        elif isinstance(node, ast.ImportFrom) and not node.level:
            module = node.module or ""
            for imported in node.names:
                if imported.name != "*":
                    aliases[imported.asname or imported.name] = f"{module}.{imported.name}"
    return aliases


def _dotted(node: ast.expr, aliases: dict[str, str]) -> str | None:
    """Resolve ``Name`` / nested ``Attribute`` to a dotted path, using *aliases*."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    head = aliases.get(current.id, current.id)
    return ".".join([head, *reversed(parts)])


#: Callees whose second argument names an attribute: ``setattr(x, "_y", z)``,
#: ``monkeypatch.setattr(x, "_y", z)``, ``mocker.patch.object(x, "_y")``.
_PATCH_CALLEES = frozenset({"setattr", "patch", "object"})


def _is_patch_call(func: ast.expr) -> bool:
    """Whether *func* is a ``setattr`` / ``patch`` / ``patch.object`` callee."""
    if isinstance(func, ast.Attribute):
        return func.attr in _PATCH_CALLEES
    return isinstance(func, ast.Name) and func.id in _PATCH_CALLEES


def _scan_source(source: str, path: str = "<planted>") -> list[Finding]:
    """Every retired-name reference in *source*: attribute, import and setattr forms."""
    tree = ast.parse(source)
    aliases = _alias_map(tree)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            owner = _retired_owner(_dotted(node.value, aliases))
            if owner is not None and node.attr in _RETIRED[owner]:
                findings.append(_finding(path, node, owner, node.attr))
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module in _RETIRED:
            for imported in node.names:
                if imported.name in _RETIRED[node.module]:
                    findings.append(_finding(path, node, node.module, imported.name))
        elif isinstance(node, ast.Call) and len(node.args) >= 2 and _is_patch_call(node.func):
            target = node.args[0]
            name = node.args[1]
            if isinstance(name, ast.Constant) and isinstance(name.value, str):
                owner = _retired_owner(_dotted(target, aliases))
                if owner is not None and name.value in _RETIRED[owner]:
                    findings.append(_finding(path, node, owner, name.value))
    return findings


def _grep(pattern: str) -> list[str]:
    """Repo-relative ``src/``/``tests/`` paths matching *pattern*, tracked or not.

    ``git grep`` does the file walk in one process (and honours ``.gitignore``), so the
    gate stays in the fast tier. ``--untracked`` matters: a coupling added in an
    uncommitted file must be caught before it is ever committed.
    """
    result = subprocess.run(  # noqa: S603, S607 -- fixed argv, git on PATH
        ["git", "grep", "--untracked", "-l", "-E", "-e", pattern, "--", "src", "tests"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), f"git grep failed: {result.stderr.strip()}"
    return [line for line in result.stdout.splitlines() if line]


def _candidate_files() -> list[str]:
    """Files that spell a retired name — the only ones that can reach a retired seam."""
    return _grep(_RETIRED_NAME.pattern)


def _scan_repository() -> list[Finding]:
    """Scan every ``src/``/``tests/`` file that spells a retired name, in any form."""
    # Non-vacuity of the search itself: an empty result for a name that must exist means
    # the pre-filter, not the tree, is what produced no findings.
    assert _grep(_ALWAYS_PRESENT), f"pre-filter found no file for {_ALWAYS_PRESENT!r}; the search is broken"
    findings: list[Finding] = []
    for rel in _candidate_files():
        findings.extend(_scan_source((_REPO_ROOT / rel).read_text(encoding="utf-8"), rel))
    return findings


def test_no_retired_scanning_name_is_reachable_from_src_or_tests() -> None:
    """#6434: the private scanning/identity seams are gone; nothing may reach them."""
    findings = _scan_repository()
    report = "\n".join(f"{item.path}:{item.line}: retired `{item.reach}` — use `{item.replacement}`" for item in findings)
    assert findings == [], report


def test_every_promoted_name_resolves_on_its_module() -> None:
    """Positive control: the public surface this gate protects actually exists."""
    import importlib

    missing: list[str] = []
    for module_name, names in _PUBLIC.items():
        module = importlib.import_module(module_name)
        for name in names:
            target: object = module
            for part in name.split("."):
                target = getattr(target, part, None)
                if target is None:
                    missing.append(f"{module_name}.{name}")
                    break
    assert missing == []


def test_kind_vocabulary_exports_and_documents_the_scanning_api() -> None:
    """`__all__` convention: every promoted scanning helper is published and documented."""
    from charter.activation import kind_vocabulary

    exported = set(kind_vocabulary.__all__)
    undocumented: list[str] = []
    for name in _PUBLIC["charter.activation.kind_vocabulary"]:
        attribute = getattr(kind_vocabulary, name)
        if name not in exported:
            undocumented.append(f"{name} (missing from __all__)")
        elif not (attribute.__doc__ or "").strip():
            undocumented.append(f"{name} (no docstring)")
    assert undocumented == []


@pytest.mark.parametrize(
    ("form", "source"),
    [
        ("attribute", "from charter.activation import kind_vocabulary\nkind_vocabulary._scan_roots(1)\n"),
        ("import", "from charter.activation.kind_vocabulary import _read_id\n"),
        ("setattr", 'from charter.activation import kind_vocabulary\nmonkeypatch.setattr(kind_vocabulary, "_scan_dir_matches", probe)\n'),
        ("class attribute", "from charter.activation.identity_index import IdentityIndex\nIdentityIndex._scan\n"),
        ("governance import", "from charter.activation.compiler import _direct_root_urns\n"),
        ("re-export import", "from charter.activation.context import _load_action_governance_bundle\n"),
    ],
)
def test_gate_detects_a_planted_retired_reference(form: str, source: str) -> None:
    """Negative control per detection form: the scanner can see a reference it must flag."""
    assert _scan_source(source), f"the {form} form went undetected"


def test_gate_leaves_unrelated_private_helpers_alone() -> None:
    """Scope control: same-named helpers in other modules are legitimate and must not be flagged."""
    source = (
        "from charter.activation import pack_manager\n"
        "from charter.offering.packs import pack_assembler\n"
        "pack_manager._config_stem(path)\n"
        "pack_assembler._read_id(path)\n"
    )
    assert _scan_source(source) == []
