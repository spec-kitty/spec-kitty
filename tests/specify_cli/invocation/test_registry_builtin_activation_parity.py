"""R3 — dispatch routing and governance context AGREE on built-in activation.

Before R3, dispatch routing (``ProfileRegistry``) loaded built-in + project
profiles UNGATED, while the governance-context seam (``build_charter_context``)
and the canonical ``charter/resolver.py`` gated ALL doctrine layers against
``activated_agent_profiles``. A built-in the charter de-activated was therefore
absent from governance context yet still routable — a split surface.

This is the live proof of unification: with an explicit
``activated_agent_profiles`` that EXCLUDES a built-in, that built-in is absent
from BOTH the routing catalog (``ProfileRegistry.list_all()``) AND the
governance context (``build_charter_context(repo, profile=<that builtin>)``),
while the explicitly-activated built-in remains present in both. The legacy
``.kittify/profiles`` invocation project layer stays out of scope here (it is
not part of the doctrine activation model).

An org pack is declared so the context seam routes through its
activation-aware profile map (the gate only engages when org roots exist);
that does not affect the built-in parity being proved.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.context import build_charter_context
from charter.activation.profile_resolution import _load_agent_profile, _reset_agent_profile_cache
from specify_cli.invocation.registry import ProfileRegistry

# This file git-inits ``tmp_path`` via subprocess (build_charter_context needs a
# real repo root), so it carries ``git_repo`` and must NOT be ``fast`` (marker
# correctness Rules 1 & 2).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Language-AGNOSTIC built-ins (no ``applies_to_languages``) so the governance
# context — which language-filters via ``infer_repo_languages`` — loads them in
# an empty repo; the only gating dimension under test is charter activation.
# Both carry directive-references, so each one's profile-cited block renders in
# the context *iff* it resolves (i.e. iff it is activated).
_ACTIVATED_BUILTIN = "reviewer-renata"
_EXCLUDED_BUILTIN = "architect-alphonso"
_PACK_NAME = "orgzilla-governance-pack"
_ORG_ANALYST_ID = "orgzilla-org-analyst"
# Non-bootstrap action → compact governance render path (no charter file needed).
_DISPATCH_ACTION = "advise"


def _directives_marker(profile_id: str) -> str:
    return f"Profile-Cited Directives ({profile_id}):"


def _write_org_pack(repo_root: Path) -> Path:
    pack_root = repo_root / "org-packs" / _PACK_NAME
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{_ORG_ANALYST_ID}.agent.yaml").write_text(
        (
            f"profile-id: {_ORG_ANALYST_ID}\n"
            "name: Orgzilla Org Analyst\n"
            "description: Org-pack analyst profile for parity fixtures\n"
            'schema-version: "1.0"\n'
            "roles:\n"
            "  - researcher\n"
            "purpose: >\n"
            "  Organisation-provided analyst contributed through an org pack.\n"
            "specialization:\n"
            "  primary-focus: >\n"
            "    Organisation-specific evidence-provenance analysis.\n"
        ),
        encoding="utf-8",
    )
    return pack_root


def _write_config(repo_root: Path, pack_root: Path, *, activated: list[str]) -> None:
    data: dict[str, object] = {
        "charter_packs": {"org": {"packs": [{"name": _PACK_NAME, "local_path": str(pack_root)}]}},
        "activated_agent_profiles": activated,
    }
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _context_text(repo_root: Path, profile_id: str) -> str:
    result = build_charter_context(
        repo_root,
        profile=profile_id,
        action=_DISPATCH_ACTION,
        mark_loaded=False,
    )
    return str(result.text)


@pytest.fixture(autouse=True)
def _git_init_and_clean_cache(tmp_path: Path) -> None:
    """Git-init ``tmp_path`` and reset the profile/resolver caches per test.

    ``build_charter_context`` resolves the canonical repo root through
    ``ensure_charter_bundle_fresh``, which raises ``NotInsideRepositoryError``
    for a non-git path; an empty repo is the minimal real-shaped fixture.
    """
    with contextlib.suppress(FileNotFoundError, OSError):
        subprocess.run(
            ["git", "init", "--quiet", str(tmp_path)],
            check=False,
            capture_output=True,
        )
    _reset_agent_profile_cache()
    yield
    _reset_agent_profile_cache()
    with contextlib.suppress(Exception):
        from charter.resolution import resolve_canonical_repo_root

        resolve_canonical_repo_root.cache_clear()


def test_excluded_builtin_absent_from_routing_and_context(tmp_path: Path) -> None:
    """A de-activated built-in is absent from BOTH routing and context (R3)."""
    pack_root = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack_root, activated=[_ACTIVATED_BUILTIN])

    routing_ids = [p.profile_id for p in ProfileRegistry(tmp_path).list_all()]

    # Routing: the excluded built-in is gone; the activated one remains.
    assert _EXCLUDED_BUILTIN not in routing_ids
    assert _ACTIVATED_BUILTIN in routing_ids

    # Context (negative case): the excluded built-in does not resolve, so
    # its profile-cited block is absent from the rendered prose. An ABSENT
    # marker is unambiguous even under token-budget substitution (a
    # truncated render can only ever OMIT more, never fabricate the marker
    # for a profile that never resolved), so the rendered-text assertion
    # stays honest here and is kept as-is (T011 Edge Cases / Reviewer
    # Guidance: this negative assertion is unaffected by the defect).
    excluded_text = _context_text(tmp_path, _EXCLUDED_BUILTIN)
    assert _directives_marker(_EXCLUDED_BUILTIN) not in excluded_text

    # Context (positive case, T011 — structured resolution, PREFERRED fix
    # per the WP03 prompt's option 1): the ORIGINAL defect asserted a
    # rendered-text marker (`_directives_marker(_ACTIVATED_BUILTIN) in
    # activated_text`) which is exactly the assertion a token-budget
    # substitution can falsify — when the compact-governance renderer
    # exceeds its budget it substitutes a fetch-command stub for a section,
    # silently dropping the marker even though activation itself was
    # correct. `_load_agent_profile` is the SAME budget-independent
    # resolver `build_charter_context` calls internally, before any
    # rendering happens (`charter/context.py::build_charter_context`,
    # ``profile_record = _load_agent_profile(profile, repo_root) if profile
    # else None``) to decide whether a profile-cited section can render at
    # all — so asserting against its return value proves "the profile
    # resolved" (R3's actual intent) without depending on prose shape.
    assert _load_agent_profile(_ACTIVATED_BUILTIN, tmp_path) is not None, (
        f"{_ACTIVATED_BUILTIN!r} must resolve via the activation-aware "
        "resolver build_charter_context uses internally"
    )
    # Still exercise the full `build_charter_context` render path for the
    # activated builtin as a smoke check (must not raise) — this is the
    # exact call whose rendered text triggered the original defect — without
    # depending on its textual shape for the assertion.
    _context_text(tmp_path, _ACTIVATED_BUILTIN)


def test_no_activation_key_admits_all_builtins_in_routing(tmp_path: Path) -> None:
    """Guard (a): with no activation key the routing catalog admits all built-ins."""
    pack_root = _write_org_pack(tmp_path)
    # Declare the pack but write NO activated_agent_profiles key.
    data: dict[str, object] = {
        "charter_packs": {"org": {"packs": [{"name": _PACK_NAME, "local_path": str(pack_root)}]}},
    }
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)

    routing_ids = [p.profile_id for p in ProfileRegistry(tmp_path).list_all()]

    # Both built-ins are admitted (the gate is a no-op when the key is absent),
    # and the activated org profile is present too.
    assert _ACTIVATED_BUILTIN in routing_ids
    assert _EXCLUDED_BUILTIN in routing_ids
    assert _ORG_ANALYST_ID in routing_ids
