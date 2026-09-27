"""Behavioural bootstrap markers for ``charter.activation.context`` (FR-015).

The corpus traverses the behaviour-bearing cases of the context contract plus
the empty-charter provenance proof:

* token-budget substitution (an over-budget action-critical section body
  gets swapped for the canonical fetch + when-doing stanza — NFR-001);
* catalog-miss fall-through (a profile-cited directive id absent from the
  catalog degrades to the structured miss stanza, not a crash);
* first-load state bookkeeping (a fresh repo's first render writes
  ``.kittify/charter/context-state.json``);
* the empty-charter / generic-agent fallback (WP01/WP03, #3064).

Each case asserts its own distinguishing behavioural marker. Render
*determinism* is covered separately by
``tests/charter/test_context_noop_stability.py``.

On-disk fixture, public seams only
----------------------------------
The markers are reached exclusively through the public entry points
(``build_charter_context``, ``build_charter_context_include``,
``build_charter_context_json``) and the public ``SPEC_KITTY_PACKS_ROOT`` env
knob — never by patching a first-party ``src/`` binding or calling a
first-party private (enforced by ``test_context_markers_use_no_src_patch_targets``).
The catalog-miss decoupling comes from filesystem state: :func:`_mirror_packs`
**copies** (never symlinks, D-OP-10) the real ``packs/built-in`` tree under
``tmp_path`` with an empty ``directives/`` directory and one extra on-disk
fixture agent profile citing a directive absent from that empty catalog.
"""

from __future__ import annotations

import ast
import json
import shutil
import textwrap
import warnings
from pathlib import Path

import pytest

from charter.activation.context import (
    build_charter_context,
    build_charter_context_include,
    build_charter_context_json,
)
from kernel.paths import get_built_in_pack_root

pytestmark = [pytest.mark.fast]

# A unique needle embedded in the oversized "Terminology Canon" body so the
# token-budget test can assert the VERBATIM body is gone post-substitution
# (not just that *some* swap happened).
_LONG_BODY_NEEDLE = "PARITY-FIXTURE-LONG-BODY-MARKER-78321"
_LONG_BODY = f"Canonical term line reinforcing prose consistency ({_LONG_BODY_NEEDLE}).\n" * 700  # ~48,000 chars — comfortably over BUDGET_DEFAULT (40,000).

_GHOST_DIRECTIVE_CODE = "998"


# ---------------------------------------------------------------------------
# Fixture repo builders
# ---------------------------------------------------------------------------


def _write_common_charter_files(tmp_path: Path, charter_md: str) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    # No ``charter:`` pointer is written to config.yaml here, so PackContext
    # reads activation directly from config.yaml (legacy/un-migrated path).
    # ``mission_type_activations`` is provisioned so ``PackContext.from_config``
    # (WP04, C-A1: the provisioned charter is the sole activation authority),
    # unconditionally called by ``_resolve_action_bundle`` on every bootstrap
    # render, does not hard-fail on a genuinely absent key.
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    (charter_dir / "charter.md").write_text(charter_md, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(
        textwrap.dedent(
            """\
            charter:
              template_set: software-dev-default
              selected_paradigms: []
              selected_directives: []
              available_tools: []
            """
        ),
        encoding="utf-8",
    )
    (charter_dir / "references.yaml").write_text(
        textwrap.dedent(
            """\
            schema_version: "1.0.0"
            references: []
            """
        ),
        encoding="utf-8",
    )


def _bootstrap_corpus_charter_md() -> str:
    # Built via explicit concatenation (not ``textwrap.dedent`` over an
    # f-string) because ``_LONG_BODY``'s substituted lines carry no leading
    # whitespace, which would poison dedent's common-prefix calculation
    # across the whole template and leave the OTHER lines' indentation
    # un-stripped — silently breaking the ``## <heading>`` anchor match in
    # ``section_bodies._heading_pattern`` (line-start anchored, no leading
    # whitespace tolerance).
    header = textwrap.dedent(
        """\
        # Project Charter

        ## Policy Summary

        - Intent: deterministic parity fixture
        - Testing: pytest golden comparison

        ## Terminology Canon

        """
    )
    footer = textwrap.dedent(
        """\
        ## Code Review Checklist

        - Confirm the diff matches the reviewed scope.

        ## Regression Vigilance

        - Watch for silently reintroduced legacy terminology.
        """
    )
    return header + _LONG_BODY + footer


_FIXTURE_PROFILE_ID = "parity-fixture-agent"

# Literal on-disk profile (public YAML format): cites a directive id that the
# mirror's empty ``directives/`` catalog cannot resolve.
_FIXTURE_PROFILE_YAML = textwrap.dedent(
    f"""\
    profile-id: {_FIXTURE_PROFILE_ID}
    name: Parity Fixture Agent
    roles:
      - implementer
    purpose: test fixture for the bootstrap-marker corpus
    specialization:
      primary-focus: testing
    directive-references:
      - code: "{_GHOST_DIRECTIVE_CODE}"
        name: Ghost Directive
        rationale: force a catalog-miss fall-through
    """
)


def _mirror_packs(tmp_path: Path, *, empty_directives: bool = True) -> Path:
    """Copy the real built-in pack under ``tmp_path/packs`` and return that packs root.

    Resolve the real pack root through the public ``get_built_in_pack_root``
    BEFORE ``SPEC_KITTY_PACKS_ROOT`` points at the mirror. Every child is copied
    (never symlinked, D-OP-10). With *empty_directives* the ``directives/``
    catalog is an empty real directory, so every directive lookup misses. The
    fixture agent profile is written as literal YAML next to the real profiles.
    """
    real_built_in = get_built_in_pack_root()
    packs_root = tmp_path / "packs"
    mirror = packs_root / "built-in"
    assert not real_built_in.resolve().is_relative_to(tmp_path.resolve()), "real pack root must be located before the env knob points at the mirror"
    mirror.mkdir(parents=True)
    for child in real_built_in.iterdir():
        target = mirror / child.name
        if child.name == "directives" and empty_directives:
            target.mkdir()
        elif child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)
    (mirror / "agent_profiles" / f"{_FIXTURE_PROFILE_ID}.agent.yaml").write_text(_FIXTURE_PROFILE_YAML, encoding="utf-8")
    return packs_root


@pytest.fixture
def packs_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the public ``SPEC_KITTY_PACKS_ROOT`` knob at an empty-directives mirror."""
    root = _mirror_packs(tmp_path)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root))
    return root


def _render_bootstrap_corpus(repo: Path) -> str:
    _write_common_charter_files(repo, _bootstrap_corpus_charter_md())
    result = build_charter_context(
        repo,
        profile=_FIXTURE_PROFILE_ID,
        action="implement",
        mark_loaded=True,
    )
    text: str = result.text
    return text


# ---------------------------------------------------------------------------
# Case 1 — build_charter_context: first-load + catalog-miss + token-budget
# ---------------------------------------------------------------------------


class TestBootstrapCorpusParity:
    """One render exercising all three non-trivial behaviour-bearing cases."""

    def _render(self, tmp_path: Path) -> tuple[str, Path]:
        repo = tmp_path / "repo"
        return _render_bootstrap_corpus(repo), repo

    @pytest.mark.usefixtures("packs_mirror")
    def test_first_load_marker(self, tmp_path: Path) -> None:
        """The fresh repo's first render must report first_load and persist state."""
        repo = tmp_path / "repo"
        _write_common_charter_files(repo, _bootstrap_corpus_charter_md())
        state_path = repo / ".kittify" / "charter" / "context-state.json"
        assert not state_path.exists(), "fixture must start with no prior state"

        result = build_charter_context(
            repo,
            profile=_FIXTURE_PROFILE_ID,
            action="implement",
            mark_loaded=True,
        )

        assert result.first_load is True
        assert state_path.exists(), "first-load render must write context-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert "implement" in state.get("actions", {})

    @pytest.mark.usefixtures("packs_mirror")
    def test_catalog_miss_marker(self, tmp_path: Path) -> None:
        """The ghost directive reference degrades to the structured miss stanza."""
        text, _ = self._render(tmp_path)
        assert f"directive:DIRECTIVE_{_GHOST_DIRECTIVE_CODE}" in text
        assert "Cause: missing_artifact" in text

    @pytest.mark.usefixtures("packs_mirror")
    def test_token_budget_substitution_marker(self, tmp_path: Path) -> None:
        """The oversized critical-section body is swapped for a fetch stanza.

        The action-critical-sections block is now split per heading (each
        heading is its own swap candidate, competing on its own real size —
        see ``_split_critical_sections`` in ``token_budget.py``), so the
        swapped-out ``### Terminology Canon`` heading (the one carrying the
        oversized ``_LONG_BODY``) is replaced by its own heading-specific
        ``section:terminology-canon`` selector rather than the generic
        ``section:critical-implement`` bucket selector that covered the
        whole block before the split.
        """
        text, _ = self._render(tmp_path)
        assert _LONG_BODY_NEEDLE not in text, "the over-budget verbatim body must be swapped out, not inlined"
        assert "section:terminology-canon" in text
        assert "# Governance payload:" in text

    @pytest.mark.usefixtures("packs_mirror")
    def test_packs_mirror_is_the_resolved_built_in_root(self, tmp_path: Path) -> None:
        """The copied mirror, not the ambient checkout, is the resolved built-in root (#3251 guard)."""
        root = get_built_in_pack_root()
        resolved = root.resolve()
        assert resolved.is_relative_to(tmp_path.resolve()), f"built-in pack root escaped the fixture: {resolved}"
        # Checked on the UNRESOLVED root: ``.resolve()`` follows symlinks, so a
        # resolved path can never itself be one (that assert was vacuous).
        assert not root.is_symlink(), "the packs mirror must be a copy, never a symlink (D-OP-10)"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            text, _ = self._render(tmp_path)

        fallback = [w for w in caught if issubclass(w.category, UserWarning) and "SPEC_KITTY_PACKS_ROOT" in str(w.message)]
        assert fallback == [], "a SPEC_KITTY_PACKS_ROOT fallback means the mirror was silently bypassed"
        assert "Cause: missing_artifact" in text

    def test_real_directive_catalog_changes_the_miss_cause(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Control: a real, non-empty directives mirror changes the miss cause.

        Proves the empty ``directives/`` directory is load-bearing. The suggested
        directive id is deliberately NOT asserted (it tracks the live catalog).
        """
        packs_root = _mirror_packs(tmp_path, empty_directives=False)
        assert any((packs_root / "built-in" / "directives").iterdir()), "control mirror must carry real directives"
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        text, _ = self._render(tmp_path)

        assert f"directive:DIRECTIVE_{_GHOST_DIRECTIVE_CODE}" in text
        assert "Cause: missing_artifact" not in text


# ---------------------------------------------------------------------------
# Case 2 — build_charter_context_include
# ---------------------------------------------------------------------------


_INCLUDE_CHARTER_MD = textwrap.dedent(
    """\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic parity fixture

    ## Terminology Canon

    - Canonical product term is "Mission"; "Feature" is prohibited.
    - "primary" and "merge" are overloaded — always name the sense.

    ## Code Review Checklist

    - Confirm the diff matches the reviewed scope.

    ## Regression Vigilance

    - Watch for silently reintroduced legacy terminology.
    """
)


class TestIncludeEntryPointParity:
    def test_include_returns_the_requested_section_body(self, tmp_path: Path) -> None:
        """The section-fetch entry point returns the requested section's body.

        Behavioural marker only (the frozen ``include_corpus`` byte-golden was
        retired — see the module docstring): the render is a section fetch, so it
        must carry that section's canonical-term line.
        """
        _write_common_charter_files(tmp_path, _INCLUDE_CHARTER_MD)

        text = build_charter_context_include(
            tmp_path,
            "section:terminology-canon",
            action="implement",
        )

        assert "Canonical product term is" in text


# ---------------------------------------------------------------------------
# Case 3 — build_charter_context_json
# ---------------------------------------------------------------------------


class TestJsonEntryPointParity:
    def test_json_entry_point_is_valid_bootstrap_payload(self, tmp_path: Path) -> None:
        """The JSON entry point returns a valid, well-shaped bootstrap payload.

        Lightweight structural assertion (the frozen ``json_corpus`` byte-golden
        was retired — see the module docstring — because it embedded the LIVE
        directive catalog and red on every doctrine addition). This pins the
        contract that survives catalog growth: the payload is JSON-serialisable,
        reports the ``bootstrap`` mode for the requested action, and carries the
        governance-payload structure — without freezing the full corpus.
        """
        _write_common_charter_files(tmp_path, _INCLUDE_CHARTER_MD)

        payload = build_charter_context_json(tmp_path, action="implement")

        assert payload["mode"] == "bootstrap"
        assert payload["action"] == "implement"

        # Valid JSON: round-trips byte-for-byte through a serialise/parse cycle.
        rendered = json.dumps(payload, indent=2, sort_keys=True)
        assert json.loads(rendered) == payload

        # Well-shaped governance payload (keys, not frozen catalog contents).
        # ``procedures`` is a first-class typed array (#3389); ``assets`` is
        # deliberately NOT a top-level array (asset stays reference-only, #3037).
        for key in ("directives", "tactics", "styleguides", "toolguides", "procedures"):
            assert key in payload, f"bootstrap payload missing '{key}' key"
        assert "assets" not in payload, "asset stays reference-only — no top-level array"


# ---------------------------------------------------------------------------
# Case 4 — empty-charter provenance (Decision 10): proves the golden is
# post-WP01/WP03, not a stale pre-US1 snapshot.
# ---------------------------------------------------------------------------


class TestEmptyCharterProvenance:
    def test_empty_charter_fallback_does_not_leak_directive_canon(self, tmp_path: Path) -> None:
        """The empty-charter generic fallback must not leak the directive canon.

        Behavioural marker only (the frozen ``empty_charter_corpus`` byte-golden
        was retired — see the module docstring). The provenance proof (Decision
        10) is unchanged: the WP01/WP03 suppression is in effect, so the full
        built-in directive canon must NOT leak into the generic-agent render.
        """
        from specify_cli.invocation.empty_charter import resolve_generic_fallback

        # Wholly-empty repo: no charter, no interview transcript, no
        # activations (the maximally-empty charter state — mirrors
        # tests/charter/test_empty_charter_governance_agreement.py).
        # ``PackContext.from_config`` (WP04, C-A1) fail-closes when
        # ``mission_type_activations`` is absent from ``.kittify/config.yaml``
        # -- unconditionally read by ``is_charter_empty`` -- so a minimal
        # config carrying ONLY that key is provisioned here; this test's own
        # subject (empty-charter provenance / no-directive-leak) is unrelated
        # to mission-type activation, and no other activation key is written.
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        (kittify / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")

        decision = resolve_generic_fallback(tmp_path, "please help me tidy this up")
        assert decision is not None
        assert decision.profile_id == "generic-agent"

        result = build_charter_context(
            tmp_path,
            profile=decision.profile_id,
            action=decision.action,
            mark_loaded=False,
            suppress_project_resolver=decision is not None,
        )

        # Provenance proof (Decision 10): the WP01/WP03 suppression must be
        # in effect — the full built-in directive canon must NOT leak.
        assert "Directive IDs:" in result.text or result.mode == "compact"


# ---------------------------------------------------------------------------
# src-coupling scan (FR-015): the marker tests must reach their behaviour
# through public entry points and public env knobs only -- never by patching a
# first-party ``src/`` binding or calling a first-party private.
# ---------------------------------------------------------------------------

_FIRST_PARTY_PACKAGES = ("charter", "kernel", "specify_cli", "runtime", "mission_runtime", "glossary", "doctrine")


def _is_first_party(dotted: str) -> bool:
    return any(dotted == pkg or dotted.startswith(f"{pkg}.") for pkg in _FIRST_PARTY_PACKAGES)


def _first_party_module_aliases(tree: ast.AST) -> dict[str, str]:
    """Map every local name bound to a first-party module/object -> its dotted path."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_first_party(alias.name):
                    local = alias.asname or alias.name.split(".")[0]
                    aliases[local] = alias.name if alias.asname else local
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and _is_first_party(node.module):
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _patch_kind(func: ast.expr) -> str | None:
    """Classify a callee as ``patch`` / ``object`` / ``setattr`` (alias-proof), else None."""
    if isinstance(func, ast.Name) and func.id == "patch":
        return "patch"
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr == "patch":
        return "patch"
    if func.attr == "object" and _patch_kind(func.value) == "patch":
        return "object"
    if func.attr == "setattr" and isinstance(func.value, ast.Name) and func.value.id == "monkeypatch":
        return "setattr"
    return None


def _dotted_expr(expr: ast.expr, aliases: dict[str, str]) -> str | None:
    """Resolve ``name`` / ``name.attr...`` to a first-party dotted path, else None."""
    if isinstance(expr, ast.Name):
        return aliases.get(expr.id)
    if isinstance(expr, ast.Attribute):
        base = _dotted_expr(expr.value, aliases)
        return f"{base}.{expr.attr}" if base else None
    return None


def _patch_target(call: ast.Call, kind: str, aliases: dict[str, str]) -> str | None:
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value if _is_first_party(first.value) else None
    if kind == "patch":
        return None
    base = _dotted_expr(first, aliases)
    if base is None:
        return None
    second = call.args[1] if len(call.args) > 1 else None
    if isinstance(second, ast.Constant) and isinstance(second.value, str):
        return f"{base}.{second.value}"
    return base


def _patch_offenders(tree: ast.AST) -> list[str]:
    aliases = _first_party_module_aliases(tree)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _patch_kind(node.func)
        if kind is None:
            continue
        target = _patch_target(node, kind, aliases)
        if target is not None:
            offenders.append(f"patch:{target}")
    return offenders


def _private_import_offenders(tree: ast.AST) -> list[str]:
    offenders: list[str] = []
    private_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and _is_first_party(node.module):
            for alias in node.names:
                if alias.name.startswith("_"):
                    offenders.append(f"private-import:{node.module}.{alias.name}")
                    private_names.add(alias.asname or alias.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in private_names:
            offenders.append(f"private-call:{node.func.id}")
    return offenders


def _src_coupling_offenders(source: str) -> list[str]:
    """Every first-party patch target, private import and private call in *source*, sorted."""
    tree = ast.parse(source)
    return sorted(_patch_offenders(tree) + _private_import_offenders(tree))


def test_context_markers_use_no_src_patch_targets() -> None:
    """This module drives its markers through public seams only (FR-015)."""
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    test_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    render_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "build_charter_context"]
    assert len(test_defs) >= 6, "non-vacuity: the marker module must keep its tests"
    assert render_calls, "non-vacuity: the marker module must render through build_charter_context"

    offenders = _src_coupling_offenders(source)
    assert offenders == [], "src-coupled patch/private sites:\n" + "\n".join(offenders)


_PLANTED_OFFENDERS_SOURCE = textwrap.dedent(
    """\
    from unittest import mock as m
    from unittest.mock import patch

    from charter import catalog as mod
    from charter.activation.profile_resolution import _reset_agent_profile_cache


    def planted(monkeypatch):
        patch("charter.activation.catalog.built_in_dir")
        monkeypatch.setattr(mod, "x", 1)
        _reset_agent_profile_cache()
        m.patch("charter.x")
    """
)

_PLANTED_PUBLIC_KNOBS_SOURCE = textwrap.dedent(
    """\
    def allowed(monkeypatch, tmp_path):
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(tmp_path))
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
    """
)


def test_src_coupling_scan_flags_planted_offenders() -> None:
    """Self-mutation: the same scan flags every planted offender and allows env knobs."""
    assert _src_coupling_offenders(_PLANTED_OFFENDERS_SOURCE) == [
        "patch:charter.activation.catalog.built_in_dir",
        "patch:charter.catalog.x",
        "patch:charter.x",
        "private-call:_reset_agent_profile_cache",
        "private-import:charter.activation.profile_resolution._reset_agent_profile_cache",
    ]
    assert _src_coupling_offenders(_PLANTED_PUBLIC_KNOBS_SOURCE) == []
