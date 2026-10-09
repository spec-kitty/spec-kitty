#!/usr/bin/env python3
"""Validate that all @patch() / patch() target strings in test files resolve.

A patch() target like ``patch("a.b.c.attr")`` instructs unittest.mock to
import module ``a.b.c`` and replace its attribute ``attr``.  When packages
are renamed or functions are moved the string becomes stale — the test still
collects but the mock silently patches the wrong object (or raises at runtime).

This script extracts every target string and checks:
  1. The module portion (everything up to the last dot) is importable.
  2. The attribute (last segment) exists on that module.

Exit codes:
  0 — all targets valid
  1 — one or more targets broken

Usage (called by CI):
  python scripts/check_patch_targets.py
  python scripts/check_patch_targets.py tests/specific_dir/
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import ModuleType

# Matches @patch("...") and patch("...") or patch('...')
# Only captures dotted module paths (at least one dot required so plain
# builtins like "open" are excluded from the dotted-path check).
_PATCH_TARGET_RE = re.compile(
    r"""(?:@patch|(?<!\w)patch)\s*\(\s*['"]([A-Za-z_][A-Za-z0-9_.]+\.[A-Za-z_][A-Za-z0-9_]*)['"]"""
)

# Modules that are known external / stdlib and don't need validation.
# These are importable in any environment but may not be installed in the
# linting environment (e.g. httpx may be optional).
_SKIP_MODULE_PREFIXES = frozenset(
    [
        "builtins",
        "os",
        "sys",
        "time",
        "datetime",
        "platform",
        "subprocess",
        "pathlib",
        "socket",
        "threading",
        "logging",
        "json",
        "re",
        "io",
        "shutil",
        "tempfile",
        "unittest",
    ]
)


def _should_skip(module_path: str) -> bool:
    top = module_path.split(".")[0]
    return top in _SKIP_MODULE_PREFIXES


def _call_is_patch(call: ast.Call) -> bool:
    """True when *call*'s callee is (``...``.)``patch`` -- ``@patch(...)`` or
    ``patch(...)`` / ``mock.patch(...)`` / ``unittest.mock.patch(...)``."""
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    return name == "patch"


def _call_has_create_true(call: ast.Call) -> bool:
    """True when *call* passes the ``create=True`` keyword argument.

    ``unittest.mock.patch(..., create=True)`` is the documented mechanism for
    patching a target that does not (yet, or any more) exist -- the target
    string is intentionally exempt from existence validation in that case. See
    ``tests/charter/test_action_governance_bundle_activation.py``'s WP02 comment
    for a real example: the patched attribute was deliberately removed by the
    same change the test asserts on, and ``create=True`` keeps the test
    collectible (and correct) on both sides of that removal.
    """
    return any(
        kw.arg == "create" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in call.keywords
    )


def _create_true_line_ranges(path: Path) -> set[int]:
    """Return every source line covered by a ``patch(..., create=True)`` call.

    A target string's regex-matched line (from :func:`extract_targets`) falling
    inside one of these ranges is exempt from :func:`validate` -- the call
    itself declares the target need not resolve. Parsed via ``ast`` (not the
    extraction regex) so multi-line calls and nested parens/strings are
    handled correctly; a file that fails to parse contributes no exemptions
    (falls back to full validation, the safe direction).
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return set()
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_is_patch(node) and _call_has_create_true(node):
            end = node.end_lineno or node.lineno
            lines.update(range(node.lineno, end + 1))
    return lines


def extract_targets(path: Path) -> list[tuple[str, int]]:
    """Return (target_string, line_number) pairs for all patch() calls."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    results = []
    for m in _PATCH_TARGET_RE.finditer(source):
        line = source[: m.start()].count("\n") + 1
        results.append((m.group(1), line))
    return results


def _mock_importer(dotted: str) -> tuple[object | None, str | None]:
    """Resolve a dotted path the same way ``unittest.mock._importer`` does.

    Tries importing progressively shorter module paths and walking the
    remainder via ``getattr``.  This correctly handles patterns like
    ``patch("pkg.module.imported_lib.Symbol")`` where ``imported_lib`` is
    an attribute of ``pkg.module`` (via ``import imported_lib`` inside it)
    but is not a sub-package of ``pkg``.
    """
    components = dotted.split(".")
    # Try longest possible import first, falling back to shorter ones.
    for split in range(len(components), 0, -1):
        module_path = ".".join(components[:split])
        try:
            obj: object = importlib.import_module(module_path)
        except ImportError:
            continue
        # Walk remaining components via getattr.
        try:
            for comp in components[split:]:
                obj = getattr(obj, comp)
            return obj, None
        except AttributeError:
            # Shorter import worked but the getattr chain broke — don't try
            # an even shorter import; the failure is real.
            return None, f"no attribute {components[split]!r} in {dotted!r}"
    return None, f"cannot import any prefix of {dotted!r}"


class PatchTargetOutcome(StrEnum):
    """The shared verdict vocabulary for a ``patch()`` target string.

    This module owns these names. The census (``scripts/patch_seam_census.py``)
    and the mechanism-keyed gate consume them; neither redefines them, so there
    is exactly one resolver and one vocabulary behind every count.

    ``unittest.mock._get_target`` splits a target on the **last** dot and
    imports the left half. So for ``patch("a.b.c.attr")`` the object that
    actually gets mutated is ``a.b.c`` — and whether that is the *right* thing
    to mutate depends entirely on what ``a.b.c`` resolves to:

    * ``OWN_MODULE`` — a module whose ``__name__`` equals the dotted path, root
      first-party. ``patch("specify_cli.sync.client.WebSocketClient")``: the
      correct idiom, patching a symbol where it is defined.
    * ``REACH_THROUGH`` — a module whose ``__name__`` **differs** from the
      dotted path, i.e. the penultimate segment is a module *imported into*
      another module. ``patch("specify_cli.tracker.saas_client.time.sleep")``
      resolves to the stdlib ``time`` module, so the patch mutates a
      process-wide shared object. This is the defect class.
    * ``FOREIGN`` — a module, ``__name__`` equals the path, root not
      first-party. ``patch("subprocess.run")``.
    * ``NOT_A_MODULE`` — resolved, but the penultimate segment is a class or
      other object, e.g. ``patch("...runtime.SyncRuntime.start")``.
    * ``UNRESOLVABLE`` — nothing importable, or the target has no dot.
    """

    OWN_MODULE = "own_module"
    REACH_THROUGH = "reach_through"
    FOREIGN = "foreign"
    NOT_A_MODULE = "not_a_module"
    UNRESOLVABLE = "unresolvable"


@dataclass(frozen=True, slots=True)
class PatchTargetVerdict:
    """A resolved ``patch()`` target, carrying everything a caller needs.

    The resolved module name, dotted path and attribute travel on the verdict so
    no caller has to re-derive them — re-deriving is how a second, subtly
    different resolver gets born.
    """

    outcome: PatchTargetOutcome
    target: str
    module_path: str
    attr: str
    resolved_module_name: str | None = None
    error: str | None = None

    @property
    def is_module(self) -> bool:
        """True when the penultimate segment resolved to a module."""
        return self.outcome in {
            PatchTargetOutcome.OWN_MODULE,
            PatchTargetOutcome.REACH_THROUGH,
            PatchTargetOutcome.FOREIGN,
        }


def resolve_patch_target(target: str, *, first_party_roots: frozenset[str]) -> PatchTargetVerdict:
    """Classify a ``patch()`` target string by what its penultimate segment is.

    Splits on the last dot exactly as ``unittest.mock._get_target`` does, then
    resolves the module half via :func:`_mock_importer` — the same progressive
    import-then-``getattr`` walk the CLI validator uses.

    Note this deliberately does **not** consult ``_SKIP_MODULE_PREFIXES``: that
    short-circuit is a validation optimisation for stdlib targets, but the
    census must still classify ``subprocess.run`` as ``FOREIGN`` rather than
    skip it.
    """
    module_path, _, attr = target.rpartition(".")
    if not module_path:
        return PatchTargetVerdict(
            outcome=PatchTargetOutcome.UNRESOLVABLE,
            target=target,
            module_path="",
            attr=target,
            error=f"cannot split into module + attr: {target!r}",
        )

    obj, err = _mock_importer(module_path)
    if err is not None:
        return PatchTargetVerdict(
            outcome=PatchTargetOutcome.UNRESOLVABLE,
            target=target,
            module_path=module_path,
            attr=attr,
            error=err,
        )

    if not isinstance(obj, ModuleType):
        return PatchTargetVerdict(
            outcome=PatchTargetOutcome.NOT_A_MODULE,
            target=target,
            module_path=module_path,
            attr=attr,
        )

    resolved_name = obj.__name__
    outcome = _classify_module(resolved_name, module_path, first_party_roots)
    return PatchTargetVerdict(
        outcome=outcome,
        target=target,
        module_path=module_path,
        attr=attr,
        resolved_module_name=resolved_name,
    )


def _classify_module(
    resolved_name: str, module_path: str, first_party_roots: frozenset[str]
) -> PatchTargetOutcome:
    """Map a resolved module onto the own/reach-through/foreign trichotomy.

    Kept separate from :func:`resolve_patch_target` so the resolution step and
    the classification step stay independently readable — the narrowed
    discriminator lives here and nowhere else.
    """
    if resolved_name != module_path:
        return PatchTargetOutcome.REACH_THROUGH
    root = module_path.split(".")[0]
    if root in first_party_roots:
        return PatchTargetOutcome.OWN_MODULE
    return PatchTargetOutcome.FOREIGN


def validate(target: str) -> str | None:
    """Return an error message if target doesn't resolve, else None."""
    if _should_skip(target):
        return None
    # Split into (module_path, attr) — same as unittest.mock._get_target.
    parts = target.rsplit(".", 1)
    if len(parts) != 2:
        return f"cannot split into module + attr: {target!r}"
    module_path, attr = parts
    obj, err = _mock_importer(module_path)
    if err:
        return err
    if not hasattr(obj, attr):
        return f"{module_path!r} has no attribute {attr!r}"
    return None


def main(argv: list[str] | None = None) -> int:
    roots = [Path(a) for a in (argv or sys.argv[1:])] or [Path("tests")]
    errors: list[str] = []
    checked = 0

    for root in roots:
        for test_file in sorted(root.rglob("*.py")):
            create_true_lines = _create_true_line_ranges(test_file)
            for target, line in extract_targets(test_file):
                checked += 1
                if line in create_true_lines:
                    continue
                err = validate(target)
                if err:
                    errors.append(f"{test_file}:{line}: {err}")

    if errors:
        print(f"::error::Broken patch() targets ({len(errors)} of {checked} checked):")
        for e in errors:
            print(f"  {e}")
        return 1

    print(f"All {checked} patch() targets valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
