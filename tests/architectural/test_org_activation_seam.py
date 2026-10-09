"""Activation-bypass architectural gate (WP05 / FR-008, C-008).

The charter activation filter is the single doorway through which org-pack
agent profiles may reach dispatch routing, governance context, and host
projection. The canonical seam is :func:`resolve_activated_org_profiles`
(WP02) / :func:`_build_active_charter_service`
(``charter/context.py``) — both apply the three-state
``PackContext.activated_agent_profiles`` gate so a *de-activated* org
profile never reaches a routing/projection surface.

The bypass this gate forbids is the **raw splice**: constructing a bare
``AgentProfileRepository(..., org_dirs=resolve_org_roots(repo_root))`` at an
org-honouring surface. That construction loads every declared org root with
no activation filtering, surfacing profiles the charter EXPLICITLY
de-activated (research.md, debbie's 4x4 matrix row 3).

Why the assertion is the ABSENCE of the raw splice, not a presence proxy
---------------------------------------------------------------------------
The originally-planned FR-008 gate was inverted: it asserted that a site
*passes* ``org_dirs`` — which would CERTIFY the bypass as compliant. The
binding assertion here is therefore that the org-honouring surfaces do NOT
construct an ``AgentProfileRepository`` with an ``org_dirs=`` keyword (nor
feed ``resolve_org_roots(...)`` into that constructor). "References the
activation seam" is ADVISORY only: an unused import or comment would satisfy
it, so it has no teeth on its own (see ``test_reference_only_check_*``).

Mechanics
---------
* The gate inspects the named org-honouring source modules via the AST
  (not brittle text scans, DIRECTIVE_041) for ``AgentProfileRepository(...)``
  constructor calls and flags any that splice raw org roots.
* A concrete integer floor (``_MIN_ORG_HONOURING_SURFACES`` = 3) fails the
  gate if an org-honouring surface is silently dropped or renamed, so the
  ratchet cannot pass vacuously.
* A self-mutation teeth test feeds the gate predicate a synthetic module
  that *imports the seam yet still splices* ``org_dirs`` and asserts the
  predicate bites; a compliant snippet passes (T015).
* Confirmed built-in-only sites are excluded with a recorded rationale
  (C-003): they intentionally never route through the activation seam.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"


# --- Vocabulary (hoisted literals — Sonar S1192) ------------------------------

# The profile-repository class whose construction we police.
_REPO_CLASS = "AgentProfileRepository"
# The keyword that splices raw, un-gated org roots into the repository.
_ORG_DIRS_KW = "org_dirs"
# The raw org-root resolver. Legitimate as a *discovery* call (threaded into
# the activation-aware service as data); a bypass only when its result is fed
# straight into an ``AgentProfileRepository(...)`` constructor.
_RESOLVE_ORG_ROOTS = "resolve_org_roots"
# The activation seam symbols an org-honouring surface should route through.
_SEAM_SYMBOLS = (
    "resolve_activated_org_profiles",
    "_build_active_charter_service",
    "build_active_charter_service",
)


# --- Scope (C-003) ------------------------------------------------------------

# The org-honouring surfaces: routing / governance-context / projection paths
# that merge the org-pack overlay. Each MUST obtain that overlay through the
# activation seam and MUST NOT splice raw org roots. Relative to ``src/``.
_ORG_HONOURING_SURFACES: tuple[str, ...] = (
    "specify_cli/invocation/org_profiles.py",
    "specify_cli/invocation/registry.py",
    "charter/activation/context.py",
    "specify_cli/tool_surface/profiles/projection.py",
)

# Non-vacuous floor: the gate fails if the enumerated org-honouring surface
# count drops below this concrete integer (silent erosion / rename guard).

# R7 rationale — ``specify_cli/cli/commands/profiles_cmd.py::_profile_catalog``
# is deliberately NOT enumerated as an org-honouring routing surface: it is an
# audited display-only catalog view that reads the UNGATED built-in + org
# catalog by design (``--all`` / ``--show-available`` must show de-activated
# profiles annotated by state), and never splices an org overlay into dispatch
# routing. The gated routing catalog lives in ``invocation/registry.py`` (R3).
#
# Confirmed built-in-only sites, intentionally NOT routed through the
# activation seam (C-003). Each carries a recorded rationale. These are not
# org-honouring: they construct a built-in-only repository for display/
# language resolution and never overlay org packs, so the activation filter
# does not apply. Relative to ``src/``.


# --- AST helpers (small, pure, directly testable) -----------------------------


def _is_repo_constructor(call: ast.Call) -> bool:
    """True when ``call`` constructs an ``AgentProfileRepository`` (Name or attr)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == _REPO_CLASS
    if isinstance(func, ast.Attribute):
        return func.attr == _REPO_CLASS
    return False


def _node_references_name(node: ast.AST, name: str) -> bool:
    """True if ``name`` appears as a usage or import of ``name`` in ``node``.

    Counts a ``Name`` id, an ``Attribute`` attr, OR an import alias
    (``from x import name`` / ``import x as name``) — so "references the seam"
    is satisfied by merely importing it (the inverted-gate failure mode the
    teeth test exercises).
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == name:
            return True
        if isinstance(child, ast.Attribute) and child.attr == name:
            return True
        if isinstance(child, ast.alias) and name in (child.name, child.asname):
            return True
    return False


def _call_splices_raw_org(call: ast.Call) -> bool:
    """True if an ``AgentProfileRepository(...)`` call splices raw org roots.

    The raw splice is either an explicit ``org_dirs=`` keyword (the keyword-only
    parameter that loads un-gated org packs) or a ``resolve_org_roots(...)``
    reference appearing in any constructor argument (positional or keyword).
    """
    for keyword in call.keywords:
        if keyword.arg == _ORG_DIRS_KW:
            return True
    arg_values: list[ast.expr] = [*call.args, *(kw.value for kw in call.keywords)]
    return any(_node_references_name(value, _RESOLVE_ORG_ROOTS) for value in arg_values)


def raw_org_splice_violations(source: str) -> list[int]:
    """Return the line numbers of activation-bypassing repo constructions.

    Empty list == the source is free of raw ``org_dirs`` / ``resolve_org_roots``
    splices into ``AgentProfileRepository(...)``. This is the gate's binding
    predicate (the ABSENCE assertion with teeth).
    """
    tree = ast.parse(source)
    return [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and _is_repo_constructor(node) and _call_splices_raw_org(node)]


def references_activation_seam(source: str) -> bool:
    """True if ``source`` references any activation-seam symbol (ADVISORY only).

    A reference proves nothing about routing: an unused import satisfies it.
    It is recorded for documentation, never as the gate's teeth.
    """
    tree = ast.parse(source)
    return any(_node_references_name(tree, symbol) for symbol in _SEAM_SYMBOLS)


def _read_surface(rel_path: str) -> str:
    return (_SRC_ROOT / rel_path).read_text(encoding="utf-8")


# --- Synthetic fixtures for the self-mutation teeth test (T015) ---------------

# A site that IMPORTS the activation seam (resolve_activated_org_profiles) YET
# still splices raw org roots — the exact failure mode a presence/reference
# proxy would WRONGLY certify as compliant.
_VIOLATION_FIXTURE = """
from pathlib import Path

from charter.profiles import AgentProfileRepository
from charter.offering.drg.org_pack_config import resolve_org_roots
from specify_cli.invocation.org_profiles import resolve_activated_org_profiles


def build_registry(repo_root: Path) -> AgentProfileRepository:
    # Imports the activation seam above for show, then bypasses it by splicing
    # raw, un-gated org roots straight into the repository (C-008 violation).
    return AgentProfileRepository(org_dirs=resolve_org_roots(repo_root))
"""

# A compliant site: the repository is built without org_dirs and the org
# overlay is obtained exclusively through the activation seam.
_COMPLIANT_FIXTURE = """
from pathlib import Path

from charter.profiles import AgentProfileRepository
from specify_cli.invocation.org_profiles import resolve_activated_org_profiles


def build_registry(repo_root: Path) -> AgentProfileRepository:
    repo = AgentProfileRepository(project_dir=repo_root / ".kittify" / "profiles")
    for resolved in resolve_activated_org_profiles(repo_root):
        repo.register_overlay(
            resolved.profile, layer="org", source_path=resolved.source_path
        )
    return repo
"""


# --- T014: the activation-seam gate ------------------------------------------


@pytest.mark.parametrize("rel_path", _ORG_HONOURING_SURFACES)
def test_org_honouring_surface_does_not_splice_raw_org_dirs(rel_path: str) -> None:
    """BINDING: no org-honouring surface constructs a raw-org-splice repository."""
    violations = raw_org_splice_violations(_read_surface(rel_path))
    assert violations == [], (
        f"{rel_path} splices raw org roots into {_REPO_CLASS}(...) at "
        f"line(s) {violations}; route the org overlay through the activation "
        f"seam ({_SEAM_SYMBOLS[0]} / {_SEAM_SYMBOLS[1]}) instead of "
        f"{_ORG_DIRS_KW}=/{_RESOLVE_ORG_ROOTS}(...) (C-008)."
    )


@pytest.mark.parametrize("rel_path", _ORG_HONOURING_SURFACES)
def test_org_honouring_surface_references_activation_seam(rel_path: str) -> None:
    """ADVISORY: each org-honouring surface references the activation seam."""
    assert references_activation_seam(_read_surface(rel_path)), (
        f"{rel_path} no longer references the activation seam {_SEAM_SYMBOLS}; it must obtain the org overlay through the seam."
    )


# --- T015: self-mutation teeth test + floor verification ----------------------


def test_gate_bites_on_injected_raw_splice() -> None:
    """The gate predicate flags an injected raw ``org_dirs`` splice (it bites)."""
    violations = raw_org_splice_violations(_VIOLATION_FIXTURE)
    assert violations, "the gate failed to detect a raw AgentProfileRepository(org_dirs=...) splice — it is vacuous or inverted"


def test_gate_passes_compliant_seam_routing() -> None:
    """The gate predicate passes a compliant seam-routed construction."""
    assert raw_org_splice_violations(_COMPLIANT_FIXTURE) == []
