"""Anti-regression ratchet for the built-in pack-location authority (WP04, #3039).

Mission ``doctrine-built-in-seam-consolidation-01KYW3TX`` centralizes "where does
built-in kind K live" and "where is the built-in root" into exactly two
callables in :mod:`charter.offering.pack_paths` -- :func:`~charter.offering.pack_paths.built_in_dir`
and :func:`~charter.offering.pack_paths.built_in_root`. WP01 created the authorities;
WP02/WP03/WP05 rerouted every production reader onto them; WP04 (this file)
drops the fail-open ``DoctrineService.built_in_root`` param that made the old
nested shape constructable, and makes the single-authority invariant a CI gate
so a sixth resolver cannot be quietly born (NFR-002).

This file is deliberately its OWN module -- NOT folded into
``test_no_dead_doctrine_paths.py`` (cf. #3039's planned split; C3.4). It covers
three independent contract clauses:

* **C3.1 / C3.1b -- the joins-only AST ratchet.** AST-scans ``src/`` for a
  built-in path *join* -- a ``resolve_pack_root("built-in") / …`` ``BinOp``
  (direct or **variable-indirected**: ``x = resolve_pack_root("built-in"); x /
  …``), or a ``<path> / "built-in"`` filesystem join. Both limbs are
  load-bearing: a ``BinOp``-only scan would false-green the indirected form
  paula flagged as the exact drift class (MAJOR-2); a naive *constant* scan
  would false-red the ~20 legitimate bare ``"built-in"`` string markers used as
  layer/provenance tags. This gate is **join-only, not a constant-scan** --
  it only inspects ``ast.BinOp`` nodes, so a bare string literal used as a
  dict key, docstring text, or comparison operand never trips it, with no
  per-site marker allowlist required. A bare ``resolve_pack_root("built-in")``
  root call (the sanctioned ``built_in_root()`` seam) is likewise permitted --
  it is never the ``.left`` of a ``Div`` ``BinOp`` at any of its call sites, so
  it never matches either limb.
* **C3.2 / NFR-003/005 -- positive per-kind coverage + the #3091 marker.** Every
  kind WITH a ``packs/built-in/<plural>/`` content dir (the 9) resolves inside
  an *existing* directory, asserted **through** :func:`resolve_pack_root`
  (never a raw repo-relative ``.exists()`` -- cf. #3036, survives the future
  wheel-split). The derived complement ``{mission_step_contract, template,
  anti_pattern}`` -- computed from :attr:`~charter.offering.artifact_kinds.ArtifactKind.has_built_in_content_dir`,
  never hand-listed -- raises :class:`~charter.offering.pack_paths.BuiltInContentDirNotAvailable`.
* **C3.3 / NFR-003 -- anti-vacuity.** The shipped ``agent_profiles`` set
  resolved through the authority is non-empty, so a stale/misconfigured root
  fails loudly instead of passing vacuously (the exact latent false-green this
  mission exists to kill; US2 acceptance #2).

Known pre-existing exemption (read before extending ``_KNOWN_JOIN_ALLOWLIST``)
--------------------------------------------------------------------------------
``src/charter/activation/kind_vocabulary.py``'s ``_scan_roots`` iterates ``org_roots`` and
joins ``root / kind.plural / "built-in"`` -- syntactically a filesystem join
(C3.1's third limb), but *semantically* it is the **ORG tier's** own legacy
nested-pack contract (``<org_root>/<plural>/built-in``, documented in-file:
"this nested layout is still live for org packs (unaffected by the built-in
relocation)"). It does not call ``resolve_pack_root("built-in")`` or
``built_in_dir``/``built_in_root`` at all, and it is out of scope for this
mission (built-in-tier consolidation only -- WP02's own Definition of Done
covers the OTHER two joins in this file, which were built-in-tier and are
gone). A pure syntax scan cannot distinguish "root walks an org pack" from
"root walks the built-in tier" -- both would look identical -- so this ONE
site is allowlisted by exact ``(file, lineno)``, not by file, so any FUTURE
join added to this file (e.g. a resurrected built-in-tier dual-read) still
fails the gate. Reintroducing a similar org-tier convention elsewhere requires
a deliberate allowlist edit naming the new site's rationale, mirroring
``tests/architectural/test_protection_resolver_call_sites.py``.

Additional exemptions (2026-08-05, mission
``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP05 CI-remediation
fold, #3204) fall into two rationale classes, neither of which is a
``resolve_pack_root("built-in")``/``built_in_root()`` reconstruction:

1. **Layer-boundary / import-avoidance sibling-shape sites.** ``kernel`` sits
   *below* ``doctrine`` (``kernel <- doctrine <- charter <- specify_cli``,
   C-004) and cannot import ``charter.offering.pack_paths`` at all --
   ``src/kernel/paths.py``'s own module docstring states these functions "have
   no spec-kitty-specific dependencies". ``specify_cli/runtime/agent_commands.py``
   *could* import ``charter.offering.pack_paths`` (the layer allows it) but
   deliberately does not, to avoid triggering doctrine's heavy validation
   imports on every CLI startup (see its own module docstring: "Uses import
   metadata rather than ``import doctrine``"). It instead consumes
   ``kernel.paths.MISSION_ASSETS_SIBLING_PATTERN`` -- the kernel-owned
   ``packs/built-in/missions`` *relative-shape constant* (FR-012, mission
   ``resolution-activation-foundation-01KZ9FKG`` WP02 collapsed the
   independently-typed per-module literal onto this one authority) -- as the
   ``sibling_relative_path`` input to
   :func:`kernel.sibling_paths.resolve_installed_sibling`, a *different*,
   domain-agnostic primitive than the ``charter.offering.pack_paths`` authority this
   gate protects. Consuming an imported constant by plain-name reference is
   not a ``/``-join, so this site never trips the AST scan below regardless of
   its line number -- it needs no allowlist entry.
   ``charter.offering.missions.repository.MissionTemplateRepository.default_missions_root``
   (formerly a peer convergent call site of this same primitive) was
   re-pointed by the same WP02 onto :func:`charter.offering.pack_paths.built_in_missions_root`
   -- a join that lives inside the authority file itself -- so it no longer
   performs its own sibling-resolution walk or needs a class-1 exemption
   either.
2. **Caller-supplied-root sites (env-var override / legacy dev-checkout
   acceptance).** Several sites resolve ``packs/built-in/missions`` relative to
   an arbitrary directory the *caller* supplied (``SPEC_KITTY_TEMPLATE_ROOT``,
   a ``--template-root``/``--local-repo`` override, or a lint's ``repo_root``
   parameter) rather than relative to the running installation's own module
   location. ``resolve_pack_root("built-in")``/``built_in_root()`` ignore any
   such caller-supplied root entirely -- they only ever resolve *this*
   installation's own built-in tier -- so routing these through the authority
   would silently substitute the real installed tree for the caller's
   explicitly-requested one, breaking the exact ``tmp_path``-rooted fixtures
   these functions are tested against (e.g.
   ``tests/charter/test_neutrality_lint.py::test_default_scan_roots_include_relocated_builtin_missions``,
   ``tests/test_template/test_manager.py::test_copy_specify_base_from_local_copies_expected_assets``).
   These are the "org-tier own contract" pattern above, generalized to a
   caller-root pattern instead of an org-pack pattern.

Each site below is allowlisted by exact ``(file, lineno)``, not by file, so any
FUTURE join added to these files still fails the gate. Reintroducing a similar
pattern elsewhere requires a deliberate allowlist edit naming the new site's
rationale.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.architectural.conftest import SourceFile

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The single-authority module: only file permitted to construct a built-in
#: path join (both `built_in_dir` and `built_in_root` live here -- C2.1/C3.1).
#: Relocated from ``src/doctrine/pack_paths.py`` by
#: charter-code-topology-01M152G1 (MAP-000 / CR-06).
_AUTHORITY_FILE = Path("src/charter/offering/pack_paths.py")

#: Narrow, exact (file, lineno) allowlist for known pre-existing non-authority
#: joins -- see the module docstring "Known pre-existing exemption" section
#: above for the full rationale of each. Extending this requires a deliberate,
#: documented policy decision naming the new site and WHY it is not a
#: built-in-tier reconstruction.
_KNOWN_JOIN_ALLOWLIST: frozenset[tuple[Path, int]] = frozenset(
    {
        # src/charter/activation/kind_vocabulary.py::_org_scan_dirs -- org-tier legacy
        # nested-pack join (`flat / "built-in"`), NOT a built-in-tier
        # reconstruction. See module docstring.
        # FRESHENED 2026-08-11 (#3317 landing): the join was extracted out of
        # _scan_roots into _org_scan_dirs (S3776 complexity reduction), moving
        # it from line 183 to 206; behaviour-preserving, same org-tier join.
        # FRESHENED 2026-08-13 (#3385 landing, org-activation-scan-dirs): the
        # join was rewritten from the single chained
        # `root / kind.plural / "built-in"` to `flat / "built-in"` (reusing
        # the new `flat = root / kind.plural` variable introduced to also
        # scan the flat, non-built-in org layout ahead of this legacy one),
        # moving it from line 206 to 244; behaviour-preserving for this join
        # itself, same org-tier legacy shape.
        # FRESHENED 2026-08-14 (#3385 fix-agent pass, PR-BOUNDARY-002): the
        # `_org_scan_dirs` docstring was expanded to document the new
        # global flat-before-legacy grouping fix, pushing the (unchanged)
        # `flat / "built-in"` join from line 244 to line 254; the join
        # itself is unchanged -- only the accumulator variable name
        # (`legacy_dirs` instead of `dirs`) and the docstring moved.
        # FRESHENED 2026-08-14 (#3385 fix-agent pass, docstring-overclaim
        # fix): the `_scan_roots` docstring was further expanded to correct
        # an overclaim about which repositories' org-layer scans are
        # non-recursive, pushing the (unchanged) join from line 254 to
        # line 269; the join itself remains unchanged.
        # FRESHENED 2026-08-14 (#3399 landing pass, #3426 residual note): the
        # `_org_scan_dirs` docstring gained a "Known residual (tracked #3426)"
        # paragraph documenting the nested-org styleguide activation gap,
        # pushing the (unchanged) `flat / "built-in"` join from line 269 to
        # line 283; the join itself remains unchanged.
        # FRESHENED 2026-08-19 (#3490/#3426/#2981 landing, single-authority-
        # resolution-parity M1): `_org_scan_dirs` gained the recursion-authority
        # rewrite and an operator-authorized precedence-widening docstring, and
        # DROPPED the "Known residual (tracked #3426)" paragraph now that #3426
        # is fixed by this mission -- net-shortening the docstring and pulling
        # the (unchanged) `flat / "built-in"` join back up from line 283 to
        # line 269; the org-tier legacy join itself is unchanged.
        # 2026-09-09: project/org precedence wiring moved the unchanged
        # caller-owned legacy org-pack join; FRESHENED 2026-09-11 (#4185
        # landing rebase): merging the org-directive-identity change onto
        # current main pulled the (unchanged) `flat / "built-in"` join to
        # line 272; the join itself is unchanged, same exact site.
        (Path("src/charter/activation/kind_vocabulary.py"), 273),
        # src/kernel/paths.py::_MISSION_ASSETS_SIBLING_PATTERN -- a relative
        # SHAPE constant (input to kernel.sibling_paths.resolve_installed_sibling),
        # not a filesystem join against a concrete root. kernel cannot import
        # charter.offering.pack_paths (layer boundary, C-004). See module docstring
        # class 1.
        (Path("src/kernel/paths.py"), 88),
        # (formerly src/kernel/paths.py:130 -- _find_relocated_missions_ancestor
        # re-inlined the packs/built-in/missions shape; it now reuses the
        # _MISSION_ASSETS_SIBLING_PATTERN constant, so it no longer joins a
        # built-in literal and needs no exemption. Removed 2026-08-05, PR #3204.)
        # (formerly src/doctrine/missions/repository.py:29 --
        # _MISSIONS_ROOT_SIBLING_PATTERN. Mission
        # resolution-activation-foundation-01KZ9FKG WP02 re-bound this constant
        # to kernel.paths.MISSION_ASSETS_SIBLING_PATTERN by plain-name
        # reference (no `/` join at this site at all) and retired
        # default_missions_root's own sibling-resolution walk in favor of
        # charter.offering.pack_paths.built_in_missions_root -- a join that lives
        # inside the authority file itself. Removed 2026-08-05.)
        # (formerly src/specify_cli/runtime/agent_commands.py:93 --
        # _MISSIONS_SIBLING_PATTERN. Mission
        # resolution-activation-foundation-01KZ9FKG WP02 re-bound this constant
        # to kernel.paths.MISSION_ASSETS_SIBLING_PATTERN by plain-name
        # reference; the constant definition itself is no longer a `/` join
        # (only its use as resolve_installed_sibling's sibling_relative_path
        # argument remains, unchanged, and that call is not a `/` join either).
        # See module docstring class 1. Removed 2026-08-05.)
        # src/specify_cli/runtime/home.py::_find_relocated_missions_ancestor --
        # walks a caller-supplied SPEC_KITTY_TEMPLATE_ROOT override directory
        # (legacy specify_cli shim mirroring kernel.paths's own env-var
        # handling), not this installation's own built-in tier. See module
        # docstring class 2.
        (Path("src/specify_cli/runtime/home.py"), 79),
        # src/specify_cli/template/manager.py::copy_specify_base_from_local --
        # joins against a caller-supplied `repo_root` (a local dev checkout
        # to copy FROM), not this installation's own built-in tier. See
        # module docstring class 2.
        # FRESHENED (charter-code-topology-01M152G1 landing): line 52 -> 53,
        # a doctrine-relocation comment (R-12) was added directly above this
        # join; the join itself is unchanged.
        (Path("src/specify_cli/template/manager.py"), 53),
        # src/specify_cli/template/manager.py::get_local_repo_root::_is_template_root --
        # content-sniffs a caller-supplied `override_path`/checkout root, not
        # this installation's own built-in tier. See module docstring class 2.
        # FRESHENED (charter-code-topology-01M152G1 landing): line 165 -> 166;
        # the sibling AGENTS.md sniff line above it now reads
        # `src/charter/offering/templates/AGENTS.md` (relocated from
        # `src/doctrine/templates/`), pushing this join down one line.
        (Path("src/specify_cli/template/manager.py"), 166),
        # src/charter/activation/neutrality/lint.py::_default_scan_roots -- scans a
        # caller-supplied `repo_root` (tmp_path-rooted in tests; see
        # tests/charter/test_neutrality_lint.py::test_default_scan_roots_include_relocated_builtin_missions),
        # not this installation's own built-in tier. See module docstring
        # class 2.
        # FRESHENED (charter-activation-split-01M16ZSE M2b landing): line 362 -> 379;
        # behaviour-preserving, same caller-supplied-root join.
        (Path("src/charter/activation/neutrality/lint.py"), 379),
    }
)

_RESOLVE_PACK_ROOT_BUILTIN = "resolve_pack_root"
_BUILT_IN_LITERAL = "built-in"
_BUILT_IN_ROOT_FUNC = "built_in_root"


def _is_resolve_pack_root_builtin_call(node: ast.AST) -> bool:
    """Return whether *node* is a bare ``resolve_pack_root("built-in")`` call."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _RESOLVE_PACK_ROOT_BUILTIN
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == _BUILT_IN_LITERAL
    )


def _is_built_in_root_call(node: ast.AST) -> bool:
    """Return whether *node* is a bare ``built_in_root()`` call (no args).

    Covers both ``built_in_root()`` (``ast.Name`` callee, the normal
    ``from charter.offering.pack_paths import built_in_root`` import shape) and
    ``<module-or-obj>.built_in_root()`` (``ast.Attribute`` callee). The
    sanctioned bare-root seam is legitimate on its own (C3.1b); joining its
    result with ``/`` to reconstruct a per-kind path is the drift this limb
    exists to catch (see :func:`_is_builtin_root_seam_call`).
    """
    return (
        isinstance(node, ast.Call)
        and not node.args
        and not node.keywords
        and (
            (isinstance(node.func, ast.Name) and node.func.id == _BUILT_IN_ROOT_FUNC)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == _BUILT_IN_ROOT_FUNC)
        )
    )


def _is_builtin_root_seam_call(node: ast.AST) -> bool:
    """Return whether *node* is either sanctioned bare-root seam call.

    ``resolve_pack_root("built-in")`` and ``built_in_root()`` are the two
    call shapes that hand back the built-in root without a per-kind segment
    -- either one becoming the base of a ``/`` join is the "reconstruct a
    per-kind path locally" drift this gate exists to catch.
    """
    return _is_resolve_pack_root_builtin_call(node) or _is_built_in_root_call(node)


def _names_bound_to_builtin_root_call(tree: ast.AST) -> set[str]:
    """Return every bare name assigned directly from a sanctioned root-seam call.

    Backs the variable-indirected limb (``x = resolve_pack_root("built-in")``
    or ``x = built_in_root()``; later ``x / …``) -- a ``BinOp``-only scan of
    the assignment's later use would miss this, since the call itself never
    appears at the join site.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_builtin_root_seam_call(node.value):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def _join_base(node: ast.AST) -> ast.AST:
    """Walk down the left spine of a ``/``-chain to its base operand.

    ``a / b / c`` parses as ``BinOp(BinOp(a, b), c)``; the base is ``a``,
    reached by following ``.left`` through every nested ``Div`` ``BinOp``.
    """
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        node = node.left
    return node


def _find_builtin_joins(tree: ast.AST) -> set[int]:
    """Return the line numbers of every built-in path-join ``BinOp`` in *tree*.

    Flags (C3.1):
      * a ``resolve_pack_root("built-in") / …`` join, direct or
        variable-indirected;
      * a ``built_in_root() / …`` join, direct or variable-indirected -- the
        sanctioned bare-root seam reused to reconstruct a per-kind path
        locally, the most natural future drift once callers stop spelling
        ``resolve_pack_root("built-in")`` directly;
      * a ``<path> / "built-in"`` filesystem join (any base).
    Permits (C3.1b): a bare ``resolve_pack_root("built-in")`` or
    ``built_in_root()`` call that is never the base of a ``/`` join (the
    sanctioned seams themselves), and any bare ``"built-in"`` string literal
    that never appears as the right-hand operand of a ``/`` ``BinOp`` (the
    ~20 layer/provenance markers) -- both are structurally invisible to this
    join-only scan.
    """
    indirected_names = _names_bound_to_builtin_root_call(tree)
    offenders: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        base = _join_base(node)
        is_direct_or_indirected = _is_builtin_root_seam_call(base) or (isinstance(base, ast.Name) and base.id in indirected_names)
        is_filesystem_join = isinstance(node.right, ast.Constant) and node.right.value == _BUILT_IN_LITERAL
        if is_direct_or_indirected or is_filesystem_join:
            offenders.add(node.lineno)
    return offenders


def _rel(path: Path) -> Path:
    return path.relative_to(_REPO_ROOT)


def test_no_builtin_path_joins_outside_pack_paths_authority(
    src_source_tree: Mapping[Path, SourceFile],
) -> None:
    """C3.1/C3.1b/NFR-002: only ``pack_paths.py`` may join a built-in path.

    Any other ``src/`` module constructing a ``resolve_pack_root("built-in")
    / …`` join (direct or variable-indirected) or a ``<path> / "built-in"``
    filesystem join is a sixth resolver being reborn -- the exact regression
    class this gate exists to prevent. See the module docstring for the ONE
    documented, narrowly-allowlisted exception.
    """
    violations: dict[str, list[int]] = {}

    for abs_path, entry in sorted(src_source_tree.items()):
        rel = _rel(abs_path)
        if rel == _AUTHORITY_FILE:
            continue
        offending_lines = _find_builtin_joins(entry.tree)
        remaining = sorted(lineno for lineno in offending_lines if (rel, lineno) not in _KNOWN_JOIN_ALLOWLIST)
        if remaining:
            violations[rel.as_posix()] = remaining

    if violations:
        details = "\n".join(f"  {path}: lines {lines}" for path, lines in sorted(violations.items()))
        pytest.fail(
            "Found built-in path join(s) outside the charter.offering.pack_paths authority.\n"
            "Route through built_in_dir(kind) (per-kind) or built_in_root() (bare root)\n"
            'instead of composing resolve_pack_root("built-in") / ... or <path> / "built-in"\n'
            "locally -- that reintroduces a scattered, fail-open resolver "
            "(NFR-002).\n\n"
            f"Violations:\n{details}"
        )


def test_negative_bite_direct_and_variable_indirected_joins_are_caught() -> None:
    """NFR-002 anti-vacuity: prove the gate actually flags both join limbs.

    Without this, a gate that always passes (e.g. an empty offender set from a
    typo'd AST match) would be indistinguishable from a correct, strict gate.
    Two synthetic snippets are parsed directly (never written to ``src/``):
    one direct ``resolve_pack_root("built-in") / …`` join, one
    variable-indirected join. Both must be flagged.
    """
    direct_source = (
        "from charter.offering.pack_paths import resolve_pack_root\n\ndef sneaky_direct(kind):\n    return resolve_pack_root('built-in') / kind.plural\n"
    )
    indirected_source = (
        "from charter.offering.pack_paths import resolve_pack_root\n"
        "\n"
        "def sneaky_indirected(kind):\n"
        "    root = resolve_pack_root('built-in')\n"
        "    return root / kind.plural\n"
    )
    filesystem_join_source = "def sneaky_filesystem_join(some_root, kind):\n    return some_root / kind.plural / 'built-in'\n"

    direct_hits = _find_builtin_joins(ast.parse(direct_source))
    indirected_hits = _find_builtin_joins(ast.parse(indirected_source))
    filesystem_hits = _find_builtin_joins(ast.parse(filesystem_join_source))

    assert direct_hits, "Direct resolve_pack_root('built-in') / ... join must be flagged"
    assert indirected_hits, "Variable-indirected join (x = resolve_pack_root('built-in'); x / ...) must be flagged"
    assert filesystem_hits, "<path> / 'built-in' filesystem join must be flagged"

    # And the permitted forms must NOT be flagged (proves the gate is
    # join-only, not a constant-scan -- C3.1b).
    bare_root_call_source = (
        "from charter.offering.pack_paths import resolve_pack_root\n\ndef permitted_bare_root_call():\n    return resolve_pack_root('built-in')\n"
    )
    bare_marker_source = "def permitted_bare_marker(layer):\n    return {'built-in': 'built-in', 'org': 'org'}.get(layer, layer)\n"
    assert not _find_builtin_joins(ast.parse(bare_root_call_source))
    assert not _find_builtin_joins(ast.parse(bare_marker_source))


def test_negative_bite_built_in_root_call_joins_are_caught() -> None:
    """NFR-002 anti-vacuity, ``built_in_root()``-join limb (FOLD 6 widening).

    The most natural future drift is not re-spelling
    ``resolve_pack_root("built-in")`` -- it is reusing the *sanctioned*
    ``built_in_root()`` seam and then joining a per-kind segment onto it
    locally, e.g. ``built_in_root() / kind.plural``, instead of calling
    :func:`charter.offering.pack_paths.built_in_dir`. Both the direct and
    variable-indirected shapes must be flagged, while a bare
    ``built_in_root()`` call -- the sanctioned form itself -- must stay
    permitted (mirrors the ``resolve_pack_root("built-in")`` proof above).
    """
    direct_source = "from charter.offering.pack_paths import built_in_root\n\ndef sneaky_direct(kind):\n    return built_in_root() / kind.plural\n"
    indirected_source = (
        "from charter.offering.pack_paths import built_in_root\n\ndef sneaky_indirected(kind):\n    root = built_in_root()\n    return root / kind.plural\n"
    )
    attribute_call_source = "from doctrine import pack_paths\n\ndef sneaky_attribute_call(kind):\n    return pack_paths.built_in_root() / kind.plural\n"

    direct_hits = _find_builtin_joins(ast.parse(direct_source))
    indirected_hits = _find_builtin_joins(ast.parse(indirected_source))
    attribute_hits = _find_builtin_joins(ast.parse(attribute_call_source))

    assert direct_hits, "Direct built_in_root() / ... join must be flagged"
    assert indirected_hits, "Variable-indirected join (x = built_in_root(); x / ...) must be flagged"
    assert attribute_hits, "Attribute-call join (mod.built_in_root() / ...) must be flagged"

    # The sanctioned bare call itself -- with no join -- must stay permitted.
    bare_built_in_root_source = "from charter.offering.pack_paths import built_in_root\n\ndef permitted_bare_built_in_root():\n    return built_in_root()\n"
    assert not _find_builtin_joins(ast.parse(bare_built_in_root_source))


# ---------------------------------------------------------------------------
# C3.2 / NFR-003 / NFR-005 -- positive per-kind coverage + the #3091 marker
# ---------------------------------------------------------------------------

#: The 9 kinds WITH a shipped `packs/built-in/<plural>/` content directory
#: (derived from `has_built_in_content_dir`, asserted below -- not hand-listed
#: independently of that attribute).

#: #3091 marker (NFR-005): the DERIVED complement of `_CONTENT_DIR_KINDS` --
#: `{mission_step_contract, template, anti_pattern}` -- package-resource/
#: graph-only kinds with no shipped content dir (relocation deferred to
#: mission #3091). This assertion is the single place that must be edited if
#: a fourth kind joins the carve-out, or if one of these three kinds later
#: GAINS a content dir: either change is a deliberate, reviewed edit here, not
#: a silent drift, because the set below is compared against the LIVE
#: `ArtifactKind` complement rather than repeated as an independent literal.


# ---------------------------------------------------------------------------
# C3.3 / NFR-003 -- anti-vacuity
# ---------------------------------------------------------------------------
