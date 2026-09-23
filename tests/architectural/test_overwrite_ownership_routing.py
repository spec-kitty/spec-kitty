"""Non-vacuous overwrite ownership-routing gate. Delivers issue #4901.

A SEPARATE architectural seam from the removal census
(``test_mutation_ownership_routing.py``) — two seams stay separate. Where that
gate proves *removals* (``rmtree``/``unlink``) are ownership-routed, this one
proves the *overwrite / destination-clobber* class is closed for the narrow set
of mutating-flow modules that write user-visible artifacts:

* ``cli/commands/research.py`` — ``--force`` clobbers via ``shutil.copy2`` (#4926).
* ``mission_brief.py`` — the brief chokepoint refuses an existing pair (#4921).
* ``intake/brief_writer.py`` — the atomic writer the brief delegates to (#4921).

The removal census explicitly deferred this overwrite family to #4901 (see its
``_CLASSIFIER_ATTRS`` SCOPE note): ``os.replace``/``rename`` and the copy verbs
are also the safe write-then-replace atomic-write primitive, indistinguishable
from a destination-clobber by call syntax alone, so they need their own contract
— this file.

WHY A LITERAL-ONLY CENSUS WOULD BE VACUOUS HERE (the load-bearing insight)
--------------------------------------------------------------------------
Unlike the removal guard (which performs the delete itself, leaving a routed
site literal-free), the overwrite guard only *decides* — the raw ``shutil.copy2``
in ``research.py`` and the atomic ``os.replace`` in ``brief_writer.py`` remain at
their sites, and ``mission_brief.py`` delegates its write to the atomic writer
and so carries no overwrite literal at all. A classifier that only flagged an
unrouted ``os.replace``/``copy2`` literal would be *vacuously green*: a developer
could delete the ``guard_destructive_overwrite`` call from ``research.py`` (whose
``shutil.copy2`` is allowlisted) or from ``mission_brief.py`` (which has no
literal to flag) and a literal-only census would stay green. This gate therefore
has BOTH non-vacuity mechanisms:

1. **Broadened classifier** over the narrow scan set — the rename/replace family
   (``os.replace``/``rename``/``renames``, ``Path.replace``/``rename``) AND the
   copy/write clobber verbs (``shutil.copy2``/``copy``/``copyfile``,
   ``Path.write_text``/``write_bytes``/``touch``). A reference/exhaustiveness set
   catches an unmapped overwrite-shaped call rather than letting it evade. The
   ``Path.replace``/``rename`` renames are arity-guarded (exactly one positional
   arg) so a benign ``str.replace(a, b)`` never matches.
2. **Positive-routing pin** (the load-bearing non-vacuity mechanism). BOTH
   pinned modules route by the SAME uniform AST shape — an ``ast.Call`` to
   ``guard_destructive_overwrite`` (a bare import/reference must NOT satisfy it).
   The pin is completeness-checked against the live routed set, so deleting the
   guard call from EITHER ``research.py`` OR ``mission_brief.py`` reds this
   census — the exact regression a literal-only census could not catch.

MODULE-COARSE caveat (do not over-trust this gate)
--------------------------------------------------
This gate proves ROUTING + LITERAL-FREENESS at MODULE granularity: each pinned
module routes through the overwrite guard and carries no un-allowlisted raw
overwrite literal. It does NOT prove per-PATH preservation — e.g. that a
specific user-authored ``research.md`` is archived rather than clobbered. Those
per-path guarantees ride on the #4921/#4926 behavioural regression tests, not on
this architectural gate.
"""

from __future__ import annotations

import ast
import warnings
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.architectural._destructive_op_census import (
    REPO_ROOT,
    SPECIFY_CLI_ROOT,
    diff_against_allowlist,
    drop_one_entry,
    enclosing_qualname,
    from_import_map,
    import_alias_map,
    parse,
    scan_planted_source,
)

pytestmark = pytest.mark.architectural

# ---------------------------------------------------------------------------
# Scan surface (narrow — this is the load-bearing scope). Explicitly NOT the
# ~30 other atomic ``os.replace(tmp, target)`` sites across the repo: over-wide
# scans force spurious allowlisting and false-reds. Widening is a separate,
# later decision (kept shrink-only).
# ---------------------------------------------------------------------------
_RESEARCH_PY = SPECIFY_CLI_ROOT / "cli" / "commands" / "research.py"
_MISSION_BRIEF_PY = SPECIFY_CLI_ROOT / "mission_brief.py"
_BRIEF_WRITER_PY = SPECIFY_CLI_ROOT / "intake" / "brief_writer.py"


def _overwrite_module_set() -> list[Path]:
    return [_RESEARCH_PY, _MISSION_BRIEF_PY, _BRIEF_WRITER_PY]


# ---------------------------------------------------------------------------
# Op classifier. Module-receiver verbs (``os``/``shutil``) are qualified by an
# ``os``/``shutil`` receiver; Path write verbs (``write_text``/``write_bytes``/
# ``touch``) are Path-only names so they match on any non-module receiver; Path
# rename verbs (``replace``/``rename``) collide with ``str.replace`` so they
# match a non-module receiver ONLY when called with exactly one positional arg
# (``Path.replace(target)`` vs ``str.replace(old, new)``).
#
# ``_REFERENCE_*`` is the broader exhaustiveness reference (adds copy/link verbs
# the classifier does NOT route) so an overwrite-shaped call the classifier does
# not map is caught by the exhaustiveness self-test rather than silently evading
# the census. SCOPE: overwrite family only — the removal family (``rmtree``/
# ``unlink``/``shutil.move``) belongs to the removal census and is deliberately
# absent from both vocabularies here.
# ---------------------------------------------------------------------------
_MODULE_RECEIVERS: frozenset[str] = frozenset({"os", "shutil"})
_MODULE_VERBS: Mapping[str, frozenset[str]] = {
    "os": frozenset({"replace", "rename", "renames"}),
    "shutil": frozenset({"copy2", "copy", "copyfile"}),
}
_REFERENCE_MODULE_VERBS: Mapping[str, frozenset[str]] = {
    "os": frozenset({"replace", "rename", "renames", "link", "symlink"}),
    "shutil": frozenset({"copy2", "copy", "copyfile", "copytree", "copyfileobj"}),
}
_PATH_WRITE_METHODS: frozenset[str] = frozenset({"write_text", "write_bytes", "touch"})
_PATH_RENAME_METHODS: frozenset[str] = frozenset({"replace", "rename"})


def _receiver_name(func: ast.Attribute, module_aliases: Mapping[str, str]) -> str | None:
    """Canonical receiver name for an attribute call, resolving an aliased
    module import (``import shutil as sh`` -> ``sh`` reads as ``shutil``)."""
    recv = func.value
    if isinstance(recv, ast.Name):
        return module_aliases.get(recv.id, recv.id)
    return None


def _is_single_positional(call: ast.Call) -> bool:
    """True for a call with exactly one positional arg and no keywords/splats —
    the ``Path.replace(target)`` / ``Path.rename(target)`` shape, distinct from
    ``str.replace(old, new)`` (2+ args) so a benign string replace never matches."""
    return len(call.args) == 1 and not call.keywords and not any(isinstance(a, ast.Starred) for a in call.args)


def _attr_label(
    call: ast.Call,
    module_aliases: Mapping[str, str],
    *,
    verbs_map: Mapping[str, frozenset[str]],
) -> str | None:
    """Overwrite op label for an *attribute* call, or ``None``.

    Precedence: a module-receiver verb (``os.replace`` / ``shutil.copy2``)
    first; a call on a known module receiver whose attr is not a mapped verb is
    deliberately not a Path method (so ``os.open`` never matches); then a Path
    write verb on any other receiver; then an arity-guarded Path rename.
    """
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    attr = func.attr
    canonical_recv = _receiver_name(func, module_aliases)
    if canonical_recv in _MODULE_RECEIVERS:
        if attr in verbs_map.get(canonical_recv, frozenset()):
            return f"{canonical_recv}.{attr}"
        return None
    if attr in _PATH_WRITE_METHODS:
        return f"Path.{attr}"
    if attr in _PATH_RENAME_METHODS and _is_single_positional(call):
        return f"Path.{attr}"
    return None


def _name_label(
    call: ast.Call,
    from_imports: Mapping[str, tuple[str, str]],
    *,
    verbs_map: Mapping[str, frozenset[str]],
) -> str | None:
    """Overwrite op label for a bare-``Name`` call bound by a ``from``-import
    (``from shutil import copy2`` -> ``copy2(...)`` reads as ``shutil.copy2``),
    or ``None``. A plain function call not bound to a module verb has no
    receiver to canonicalize and returns ``None``."""
    func = call.func
    if not isinstance(func, ast.Name):
        return None
    bound = from_imports.get(func.id)
    if bound is None:
        return None
    module, attr = bound
    if attr in verbs_map.get(module, frozenset()):
        return f"{module}.{attr}"
    return None


def _classify_op(
    call: ast.Call,
    module_aliases: Mapping[str, str],
    from_imports: Mapping[str, tuple[str, str]],
) -> str | None:
    """The overwrite op label the census routes/allowlists, or ``None``."""
    label = _name_label(call, from_imports, verbs_map=_MODULE_VERBS)
    if label is not None:
        return label
    return _attr_label(call, module_aliases, verbs_map=_MODULE_VERBS)


def _reference_op(
    call: ast.Call,
    module_aliases: Mapping[str, str],
    from_imports: Mapping[str, tuple[str, str]],
) -> str | None:
    """The overwrite op label under the broader *reference* vocabulary."""
    label = _name_label(call, from_imports, verbs_map=_REFERENCE_MODULE_VERBS)
    if label is not None:
        return label
    return _attr_label(call, module_aliases, verbs_map=_REFERENCE_MODULE_VERBS)


def _find_overwrite_ops(path: Path) -> list[tuple[int, str]]:
    """``(lineno, op)`` for every raw overwrite literal the classifier maps in *path*."""
    tree = parse(path)
    if tree is None:
        return []
    module_aliases = import_alias_map(tree)
    from_imports = from_import_map(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            op = _classify_op(node, module_aliases, from_imports)
            if op is not None:
                hits.append((node.lineno, op))
    return hits


def _unhandled_reference_ops(path: Path) -> list[tuple[int, str]]:
    """Overwrite-shaped calls (reference vocabulary) the classifier does NOT
    map — i.e. would silently evade the census (e.g. a future ``shutil.copytree``)."""
    tree = parse(path)
    if tree is None:
        return []
    module_aliases = import_alias_map(tree)
    from_imports = from_import_map(tree)
    unhandled: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            ref = _reference_op(node, module_aliases, from_imports)
            if ref is not None and _classify_op(node, module_aliases, from_imports) is None:
                unhandled.append((node.lineno, ref))
    return unhandled


def _scan_module_set() -> dict[str, list[tuple[int, str]]]:
    live: dict[str, list[tuple[int, str]]] = {}
    for py_file in _overwrite_module_set():
        hits = _find_overwrite_ops(py_file)
        if hits:
            live[py_file.relative_to(REPO_ROOT).as_posix()] = hits
    return live


def _flatten(live: dict[str, list[tuple[int, str]]]) -> set[str]:
    return {f"{rel}:{lineno}:{op}" for rel, hits in live.items() for lineno, op in hits}


# ---------------------------------------------------------------------------
# The frozen allowlist. Every overwrite-family literal in the scan set MUST be
# either (a) routed — the module calls the overwrite guard and the positive-
# routing pin below proves it — or (b) an individually-rationalized, shrink-only
# ``_ALLOWLIST`` entry keyed ``"{path}:{lineno}:{op}"``. Exemptions are PER-SITE,
# never by module name. Shrink-only: a literal that disappears WARNS (stale); a
# new un-rationalized literal FAILS.
# ---------------------------------------------------------------------------
_ALLOWLIST: dict[str, str] = {
    # --- intake/brief_writer.py (1): atomic write-then-replace-own-tempfile ----
    "src/specify_cli/intake/brief_writer.py:172:os.replace": (
        "atomic write-then-replace-own-tempfile idiom: os.replace(tmp, target) renames a "
        "same-directory temp THIS function just wrote (open+fsync+replace) onto target — the "
        "POSIX-atomic single-file commit, never a destination-clobber of unproven content; "
        "per-site exemption, never by module name."
    ),
    # --- cli/commands/research.py (1): guarded post-clear copy ----------------
    "src/specify_cli/cli/commands/research.py:94:shutil.copy2": (
        "guarded post-clear copy: shutil.copy2(template_path, dest_path) executes ONLY after "
        "guard_destructive_overwrite (research.py:80) returned proceed=True — package-owned or "
        "authorized content is replaced while a refusal returns before the copy. The positive-"
        "routing pin below reds if that guard call is deleted, so this copy can never run "
        "unguarded (a literal-only census would stay green — the pin is what has teeth here)."
    ),
}


# ---------------------------------------------------------------------------
# Pinned routed-module set. Paths relative to src/specify_cli. BOTH modules
# route by the SAME uniform AST shape (an ``ast.Call`` to
# ``guard_destructive_overwrite``); completeness-checked against the live set.
# brief_writer.py is SCANNED (for its atomic os.replace literal) but is NOT a
# routed module — its os.replace is the exempt atomic idiom, allowlisted per-site.
# ---------------------------------------------------------------------------
_ROUTED_MODULES: frozenset[str] = frozenset(
    {
        "cli/commands/research.py",
        "mission_brief.py",
    }
)

_GUARD_CALLABLE = "guard_destructive_overwrite"


def _calls_guard_destructive_overwrite(tree: ast.Module) -> bool:
    """True when *tree* contains an actual ``ast.Call`` to
    ``guard_destructive_overwrite`` — a bare-name call (the standard
    ``from specify_cli.asset_preservation import guard_destructive_overwrite``
    shape) or a qualified attribute call. AST-verified, not a substring match:
    a comment/import/reference mentioning the name does not count as routed."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == _GUARD_CALLABLE:
            return True
        if isinstance(func, ast.Attribute) and func.attr == _GUARD_CALLABLE:
            return True
    return False


def _live_routed_modules() -> set[str]:
    """Scanned modules that route by a recognized AST shape (a guard call) —
    never a substring match."""
    routed: set[str] = set()
    for py_file in _overwrite_module_set():
        tree = parse(py_file)
        if tree is not None and _calls_guard_destructive_overwrite(tree):
            routed.add(py_file.relative_to(SPECIFY_CLI_ROOT).as_posix())
    return routed


# ---------------------------------------------------------------------------
# Live census: every raw overwrite literal is allowlisted (research.py's copy2
# is a guarded post-clear copy; brief_writer's atomic os.replace is the exempt
# idiom; mission_brief.py carries no overwrite literal).
# ---------------------------------------------------------------------------


def test_every_overwrite_literal_is_allowlisted() -> None:
    live_flat = _flatten(_scan_module_set())
    unexpected, stale = diff_against_allowlist(live_flat, _ALLOWLIST)

    assert not unexpected, (
        "New raw overwrite/clobber literal(s) found in the mutating-flow scan set "
        "outside the frozen allowlist (#4901). Route the write through the overwrite "
        "guard (guard_destructive_overwrite), or — only for a genuinely-safe op (e.g. "
        "an atomic write-then-replace-own-tempfile) — add a one-line rationale entry to "
        f"_ALLOWLIST: {sorted(unexpected)}"
    )
    if stale:
        warnings.warn(
            f"Shrink-only allowlist: the following site(s) no longer carry a raw overwrite literal — safe to delete from _ALLOWLIST: {sorted(stale)}",
            UserWarning,
            stacklevel=1,
        )


def test_allowlisted_files_exist() -> None:
    """A renamed/deleted allowlisted file must not silently drop out of the scan
    (an absent file reads as zero live hits — a false 'shrink' masking a rename)."""
    rel_paths = {key.rsplit(":", 2)[0] for key in _ALLOWLIST}
    missing = sorted(rel for rel in rel_paths if not (REPO_ROOT / rel).is_file())
    assert not missing, f"Allowlisted file(s) no longer exist: {missing}"


# ---------------------------------------------------------------------------
# Op-vocabulary exhaustiveness: no overwrite-shaped call in the scan set is left
# unclassified (so it cannot silently evade the census).
# ---------------------------------------------------------------------------


def test_op_vocabulary_is_exhaustive() -> None:
    offenders: dict[str, list[tuple[int, str]]] = {}
    for py_file in _overwrite_module_set():
        hits = _unhandled_reference_ops(py_file)
        if hits:
            offenders[py_file.relative_to(REPO_ROOT).as_posix()] = hits
    assert not offenders, (
        "Overwrite-shaped filesystem call(s) present in the scan set that the census "
        "classifier does NOT recognise. A future op like shutil.copytree must be added "
        f"to _MODULE_VERBS (and routed/allowlisted) so it cannot evade the census: {offenders}"
    )


# ---------------------------------------------------------------------------
# Positive routing, pinned + completeness-checked (the load-bearing mechanism).
# ---------------------------------------------------------------------------


def test_calls_guard_destructive_overwrite_requires_an_actual_call() -> None:
    """Routing is an external ``ast.Call``: a module that merely MENTIONS the
    guard name (comment, docstring, string constant, import) must not read as
    routed — only a real call counts. Mirrors the removal census's
    ``test_calls_guard_destructive_removal_requires_an_actual_call``."""
    mention_only = ast.parse(
        "# conceptually related to guard_destructive_overwrite\n"
        "from specify_cli.asset_preservation import guard_destructive_overwrite\n"
        "GUARD = 'guard_destructive_overwrite'\n"
    )
    assert _calls_guard_destructive_overwrite(mention_only) is False

    bare_name_call = ast.parse("from specify_cli.asset_preservation import guard_destructive_overwrite\n\n\ndef f(x):\n    guard_destructive_overwrite(x)\n")
    assert _calls_guard_destructive_overwrite(bare_name_call) is True

    qualified_call = ast.parse("from specify_cli import asset_preservation\n\n\ndef f(x):\n    asset_preservation.guard_destructive_overwrite(x)\n")
    assert _calls_guard_destructive_overwrite(qualified_call) is True


def test_pinned_routed_module_set_is_complete() -> None:
    """The pinned routed set must EQUAL the live set of modules that route.
    Dropping a module from the pin (while it still routes) fails here; a new
    routing site must be added to the pin. This is the completeness check that
    makes deleting a guard call red the census (the deleted-call module drops
    from the live set)."""
    live = _live_routed_modules()
    assert live == _ROUTED_MODULES, (
        "Pinned routed-module set drifted from the live routed set. Missing from pin "
        f"(routes but not pinned): {sorted(live - _ROUTED_MODULES)}. Pinned but no "
        f"longer routing: {sorted(_ROUTED_MODULES - live)}."
    )


def test_each_routed_module_routes_and_is_allowlist_clean() -> None:
    """Each pinned module (a) calls guard_destructive_overwrite and (b) carries
    no overwrite literal OUTSIDE the frozen allowlist. MODULE-COARSE: per-path
    preservation is proven by the #4921/#4926 behavioural tests, not here."""
    research_tree = parse(_RESEARCH_PY)
    brief_tree = parse(_MISSION_BRIEF_PY)
    assert research_tree is not None and brief_tree is not None
    assert _calls_guard_destructive_overwrite(research_tree), "research.py must call guard_destructive_overwrite(...)"
    assert _calls_guard_destructive_overwrite(brief_tree), "mission_brief.py must call guard_destructive_overwrite(...)"

    unrouted_literals: dict[str, list[str]] = {}
    for rel in sorted(_ROUTED_MODULES):
        path = SPECIFY_CLI_ROOT / rel
        repo_rel = path.relative_to(REPO_ROOT).as_posix()
        literals = {f"{repo_rel}:{lineno}:{op}" for lineno, op in _find_overwrite_ops(path)}
        unexpected = literals - _ALLOWLIST.keys()
        if unexpected:
            unrouted_literals[rel] = sorted(unexpected)
    assert not unrouted_literals, (
        "Pinned routed module(s) carry a raw overwrite literal outside the allowlist — "
        f"route it through the guard, do not absorb an unguarded user-content site: {unrouted_literals}"
    )


# ---------------------------------------------------------------------------
# Non-vacuity — self-mutation, both directions (+ benign controls).
# ---------------------------------------------------------------------------


def test_scanner_detects_a_planted_os_replace_clobber(tmp_path: Path) -> None:
    """A planted, un-routed raw ``os.replace(pkg, preexisting_user_path)`` is
    caught by the exact scanner the census gate runs (non-vacuity, rename shape)."""
    hits = scan_planted_source(
        tmp_path,
        "planted_os_replace.py",
        "import os\n\n\ndef _clobber(pkg, user_path):\n    os.replace(pkg, user_path)\n",
        _find_overwrite_ops,
    )
    assert hits == [(5, "os.replace")], f"Non-vacuity failure: scanner missed a planted raw os.replace clobber. Got: {hits!r}."


def test_scanner_detects_a_planted_copy2_clobber(tmp_path: Path) -> None:
    """A planted, un-routed raw ``shutil.copy2(pkg, preexisting_user_path)`` is
    caught (non-vacuity, copy shape — research.py's actual clobber mechanism)."""
    hits = scan_planted_source(
        tmp_path,
        "planted_copy2.py",
        "import shutil\n\n\ndef _clobber(pkg, user_path):\n    shutil.copy2(pkg, user_path)\n",
        _find_overwrite_ops,
    )
    assert hits == [(5, "shutil.copy2")], f"Non-vacuity failure: scanner missed a planted raw shutil.copy2 clobber. Got: {hits!r}."


def test_scanner_detects_planted_aliased_import_ops(tmp_path: Path) -> None:
    """Aliased-import variants of both shapes (``import os as _os; _os.replace``
    and ``import shutil as sh; sh.copy2``) are still detected — the receiver-name
    census resolves the alias to its canonical module before the receiver check."""
    replace_hits = scan_planted_source(
        tmp_path,
        "planted_aliased_replace.py",
        "import os as _os\n\n\ndef _clobber(pkg, user_path):\n    _os.replace(pkg, user_path)\n",
        _find_overwrite_ops,
    )
    assert replace_hits == [(5, "os.replace")], f"Aliased os.replace missed: {replace_hits!r}."

    copy_hits = scan_planted_source(
        tmp_path,
        "planted_aliased_copy2.py",
        "import shutil as sh\n\n\ndef _clobber(pkg, user_path):\n    sh.copy2(pkg, user_path)\n",
        _find_overwrite_ops,
    )
    assert copy_hits == [(5, "shutil.copy2")], f"Aliased shutil.copy2 missed: {copy_hits!r}."


def test_scanner_detects_planted_from_import_ops(tmp_path: Path) -> None:
    """From-import variants of both shapes (``from os import replace; replace(...)``
    and ``from shutil import copy2; copy2(...)``) resolve to their canonical
    ``module.attr`` label — a bare-Name call a receiver-only classifier misses."""
    replace_hits = scan_planted_source(
        tmp_path,
        "planted_from_replace.py",
        "from os import replace\n\n\ndef _clobber(pkg, user_path):\n    replace(pkg, user_path)\n",
        _find_overwrite_ops,
    )
    assert replace_hits == [(5, "os.replace")], f"From-import os.replace missed: {replace_hits!r}."

    copy_hits = scan_planted_source(
        tmp_path,
        "planted_from_copy2.py",
        "from shutil import copy2\n\n\ndef _clobber(pkg, user_path):\n    copy2(pkg, user_path)\n",
        _find_overwrite_ops,
    )
    assert copy_hits == [(5, "shutil.copy2")], f"From-import shutil.copy2 missed: {copy_hits!r}."


def test_scanner_detects_a_planted_unhandled_op(tmp_path: Path) -> None:
    """A planted overwrite-shaped op OUTSIDE the classifier vocabulary
    (``shutil.copytree``) is flagged by the exhaustiveness scan — proving the
    op-vocabulary self-check has teeth against a future unmapped op."""
    unhandled = scan_planted_source(
        tmp_path,
        "planted_unhandled.py",
        "import shutil\n\n\ndef _clobber(src, dst):\n    shutil.copytree(src, dst)\n",
        _unhandled_reference_ops,
    )
    assert unhandled == [(5, "shutil.copytree")], f"Exhaustiveness scan missed a planted unclassified shutil.copytree. Got: {unhandled!r}."


def test_scanner_does_not_flag_benign_calls(tmp_path: Path) -> None:
    """Control (other direction): ``str.replace`` (2 args), ``list.remove``,
    ``dict.pop`` must NOT be flagged — the classifier keys on os/shutil receivers,
    Path write methods, and single-arg Path renames, never a bare method name."""
    hits = scan_planted_source(
        tmp_path,
        "planted_benign.py",
        'def _benign(items, text, mapping):\n    items.remove(1)\n    text = text.replace("a", "b")\n    mapping.pop("k", None)\n    return text\n',
        _find_overwrite_ops,
    )
    assert hits == [], f"Benign method calls were misclassified as overwrite ops: {hits!r}."


def test_removing_an_allowlist_entry_reproduces_a_gate_failure() -> None:
    """Non-vacuity (drop-one-entry): dropping ONE real allowlist entry and
    re-diffing against the ACTUAL live scan reproduces exactly the failure
    ``test_every_overwrite_literal_is_allowlisted`` would raise for a genuine
    un-routed regression — proving the primary gate is not vacuously green."""
    live_flat = _flatten(_scan_module_set())
    victim, shrunk_allowlist = drop_one_entry(_ALLOWLIST)

    unexpected, _stale = diff_against_allowlist(live_flat, shrunk_allowlist)

    assert victim in unexpected, (
        f"Self-mutation check failed: removing {victim!r} from the allowlist did not "
        "reproduce a gate failure against the live tree. The census gate is vacuous — "
        "investigate diff_against_allowlist / _scan_module_set before trusting a green run."
    )


# ---------------------------------------------------------------------------
# Positive-routing negatives — the pin is LOAD-BEARING: deleting the guard call
# from EITHER pinned module reds the census (via the completeness pin), even
# though a literal-only census would stay green.
# ---------------------------------------------------------------------------


def test_deleting_guard_call_in_research_reds_the_census() -> None:
    """Reading the REAL research.py source and stripping the
    ``guard_destructive_overwrite`` name flips its routing detector to False, so
    it drops from the live routed set and ``test_pinned_routed_module_set_is_complete``
    reds — the exact regression a literal-only census could not catch."""
    real = _RESEARCH_PY.read_text(encoding="utf-8")
    assert _calls_guard_destructive_overwrite(ast.parse(real)) is True

    mutated = real.replace(_GUARD_CALLABLE, "_guard_call_removed")
    assert mutated != real
    assert _calls_guard_destructive_overwrite(ast.parse(mutated)) is False


def test_positive_routing_pin_is_load_bearing_for_research(tmp_path: Path) -> None:
    """The pin — not the classifier — is what catches a deleted guard call. With
    the guard call stripped, research.py's ``shutil.copy2`` at :94 REMAINS (still
    allowlisted, so a literal-only census would stay GREEN), yet the module no
    longer routes — only the positive-routing pin reds. Demonstrates why a
    literal-only census would be vacuous here."""
    real = _RESEARCH_PY.read_text(encoding="utf-8")
    mutated = real.replace(_GUARD_CALLABLE, "_guard_call_removed")

    hits = scan_planted_source(tmp_path, "mutated_research.py", mutated, _find_overwrite_ops)
    assert any(op == "shutil.copy2" for _lineno, op in hits), (
        "fixture assumption: research.py's routed shutil.copy2 survives guard-call removal (literal-only stays green)"
    )
    assert _calls_guard_destructive_overwrite(ast.parse(mutated)) is False, "positive-routing pin must red once the guard call is gone"


def test_deleting_guard_call_in_mission_brief_reds_the_census() -> None:
    """mission_brief.py carries NO overwrite literal at all (it delegates its
    write to the atomic writer), so a literal-only census could NEVER catch a
    deleted guard call here — the positive-routing pin is the ONLY mechanism
    with teeth. Reading the REAL source and stripping the
    ``guard_destructive_overwrite`` name flips its routing detector to False, so
    it drops from the live routed set and the completeness pin reds."""
    real = _MISSION_BRIEF_PY.read_text(encoding="utf-8")
    assert _calls_guard_destructive_overwrite(ast.parse(real)) is True
    assert _find_overwrite_ops(_MISSION_BRIEF_PY) == [], "mission_brief.py must carry no overwrite literal (literal-only census is blind here)"

    mutated = real.replace(_GUARD_CALLABLE, "_guard_call_removed")
    assert mutated != real
    assert _calls_guard_destructive_overwrite(ast.parse(mutated)) is False


def test_enclosing_qualname_is_available_for_diagnostics() -> None:
    """The shared qualname helper resolves a censused op's enclosing function —
    used when a failure needs to name where an overwrite literal lives."""
    tree = parse(_BRIEF_WRITER_PY)
    assert tree is not None
    hits = _find_overwrite_ops(_BRIEF_WRITER_PY)
    assert hits, "brief_writer.py should carry at least one allowlisted overwrite literal"
    lineno = hits[0][0]
    assert enclosing_qualname(tree, lineno) != ""
