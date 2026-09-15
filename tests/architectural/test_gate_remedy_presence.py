"""Meta-test: every enriched gate carries a content-anchored remedy (WP01, G1).

Mission ``self-documenting-repo-01M0287X`` WP01 (FR-001 / NFR-003 / C-005): the
gates enumerated in ``spec.md``'s Given/When/Then (write-side-rederivation,
schema-slot, docs-move-relative-link) each got a remedy line baked into their
own assertion message, derived from the gate's current logic. NFR-003 (echoing
``DIRECTIVE_041``'s stable-anchoring rule) requires that remedy to be
**content-anchored**: a directive verb plus a content descriptor (a resolver
name, a CLI invocation, an allow-list symbol) -- never a ``file.py:NNN``
locator that drifts on benign edits, and never a "just add the whole file to
the allow-list" blanket escape.

This module asserts the **property**, not an echo of the literal strings the
enrichment added: :func:`_is_content_anchored_remedy` is exercised standalone
against synthetic fixtures (proving it actually bites on a missing verb, a
file:line locator, and a whole-file allow-list phrase -- T003's anti-vacuity
requirement), and then applied to the STATIC source of each registered gate's
own function body. A test that merely asserted ``"route" in message`` for the
literal string an implementer also wrote would be tautological; a badly-worded
future edit that keeps the word "route" somewhere unrelated but reintroduces a
file:line locator must still fail here.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Imperative verbs a genuine remedy uses to tell the reader WHAT to do. A
#: broad-but-bounded vocabulary (not one hard-coded literal) so the property
#: check does not degenerate into an echo of a single implementer's wording.
_DIRECTIVE_VERBS: frozenset[str] = frozenset(
    {
        "route", "add", "wire", "delete", "convert", "annotate", "run", "use",
        "invoke", "call", "rename", "move", "replace", "regenerate", "freeze",
        "remove", "fix", "rewrite",
    }
)

#: A ``path/like/this.py:123`` locator -- forbidden as the REMEDY text itself
#: (DIRECTIVE_041 stable-anchoring: never key guidance to a line number that
#: drifts on a benign edit). Offender listings built from runtime data are
#: exempt: they are not string literals in the function's own source, so this
#: scan (which only ever sees literal segments) never even looks at them.
_FILE_LINE_RE = re.compile(r"[\w./-]+\.py:\d+")

#: A blanket "add the whole file to the allow-list" escape -- forbidden
#: because it excuses every future finding in that file, not just the one
#: being fixed (paula SF-2 / NFR-003).
_WHOLE_FILE_ALLOWLIST_RE = re.compile(
    r"add\s+(?:the\s+)?(?:whole\s+)?file\b.{0,120}?allow-?list", re.IGNORECASE | re.DOTALL
)


def _has_directive_verb(text: str) -> bool:
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    return bool(words & _DIRECTIVE_VERBS)


def _is_content_anchored_remedy(text: str) -> bool:
    """``True`` iff *text* reads as a content-anchored remedy (see module docstring)."""
    if not _has_directive_verb(text):
        return False
    if _FILE_LINE_RE.search(text):
        return False
    return not _WHOLE_FILE_ALLOWLIST_RE.search(text)


# --------------------------------------------------------------------------- #
# Anti-vacuity: the property check itself must bite (T003).
# --------------------------------------------------------------------------- #


def test_property_check_flags_a_message_with_no_directive_verb() -> None:
    assert not _is_content_anchored_remedy("Something here is not as expected.")


def test_property_check_flags_a_file_line_locator() -> None:
    assert not _is_content_anchored_remedy(
        "Route through the resolver -- see scripts/docs/fixer.py:123 for details."
    )


def test_property_check_flags_a_whole_file_allowlist_escape() -> None:
    assert not _is_content_anchored_remedy(
        "Add the whole file scripts/docs/fixer.py to the allow-list."
    )


def test_property_check_accepts_a_well_formed_remedy() -> None:
    assert _is_content_anchored_remedy(
        "Route the offender through the resolver, or add a rationale-carrying "
        "allow-list entry."
    )


# --------------------------------------------------------------------------- #
# Static extraction: literal string content of a named function's body.
# --------------------------------------------------------------------------- #


def _literal_text_segments(node: ast.AST) -> list[str]:
    """Every literal string an author actually wrote inside *node*: plain
    ``Constant`` strings, and the static (non-interpolated) parts of an
    f-string (``JoinedStr``). Interpolated runtime values (offender listings,
    ``{slot.name}``, ...) are never literals and are therefore never scanned --
    exactly the split the module docstring describes.
    """
    segments: list[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            segments.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            segments.append(
                "".join(
                    part.value
                    for part in n.values
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                )
            )
    return segments


def _function_literal_text(source: str, qualname: str) -> str:
    """Concatenated literal text of every function/method named *qualname* in
    *source* (module-level function or class method -- ``ast.walk`` sees both).

    Raises if zero matches: a registered gate whose function vanished (renamed,
    deleted) must fail loudly, not silently scan nothing.
    """
    tree = ast.parse(source)
    matches = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == qualname
    ]
    assert matches, f"no function/method named {qualname!r} found in source"
    segments: list[str] = []
    for match in matches:
        segments.extend(_literal_text_segments(match))
    return " ".join(segments)


# --------------------------------------------------------------------------- #
# Registered gates (WP01, G1) -- each must carry a content-anchored remedy.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RegisteredGate:
    relpath: str
    qualname: str


_REGISTERED_GATES: tuple[_RegisteredGate, ...] = (
    _RegisteredGate(
        "tests/architectural/test_no_write_side_rederivation.py",
        "test_adopted_modules_have_no_write_side_rederivation",
    ),
    _RegisteredGate(
        "tests/architectural/test_no_write_side_rederivation.py",
        "test_adopted_and_residual_modules_have_no_checkout_derived_commit_target",
    ),
    _RegisteredGate(
        "tests/architectural/test_no_inert_schema_slots.py",
        "test_live_tree_has_no_new_inert_slots",
    ),
    _RegisteredGate(
        "tests/docs/test_relative_link_fixer.py",
        "test_assembled_tree_has_no_unexpected_dead_links",
    ),
    _RegisteredGate(
        "tests/docs/test_relative_link_fixer.py",
        "test_full_tree_no_exclude_is_green",
    ),
    # An unauthored, content-anchored remedy -- included so the property
    # check is proven against a KNOWN-GOOD remedy this WP did not write, not
    # only the ones it did. Chosen for independence (#4315): the
    # golden-count gate this exemplar previously pointed at was retired
    # outright, and the two passing candidates in
    # test_ruff_format_exclude_ratchet.py guard the exclude list this
    # mission's own commits change, so neither is "a remedy this mission did
    # not author" in spirit. test_ruff_format_enforcement.py is untouched by
    # this mission and predates it (#473/#558).
    _RegisteredGate(
        "tests/architectural/test_ruff_format_enforcement.py",
        "test_ruff_format_check_is_clean_on_whole_repo",
    ),
)


@pytest.mark.parametrize(
    "gate",
    _REGISTERED_GATES,
    ids=[f"{g.relpath}::{g.qualname}" for g in _REGISTERED_GATES],
)
def test_registered_gate_carries_a_content_anchored_remedy(gate: _RegisteredGate) -> None:
    source = (_REPO_ROOT / gate.relpath).read_text(encoding="utf-8")
    text = _function_literal_text(source, gate.qualname)
    assert _is_content_anchored_remedy(text), (
        f"{gate.relpath}::{gate.qualname} carries no content-anchored remedy "
        "(a directive verb + content descriptor, no file:line locator or "
        f"whole-file allow-list escape). Literal text scanned: {text!r}"
    )
