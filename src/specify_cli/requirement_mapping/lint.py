"""setup-plan's requirement-ID lint (FR-013 / FR-014, WP05 T024).

A pure function over spec.md text: :func:`lint_spec_requirement_ids` finds
every kind-prefixed token in a DECLARED position (table cell / heading /
bullet-or-numbered lead / bold lead) that does not match the requirement-ID
grammar (FR-013, blocking), and every unqualified, well-formed, undeclared
token in PROSE (FR-014, non-blocking). Both halves read the grammar through
:mod:`specify_cli.requirement_mapping.grammar` alone (C-001): this module
contains no requirement-ID regex literal of its own.

**Relationship to** :func:`specify_cli.requirement_mapping.
find_undeclared_requirement_citations` **(extend, do not duplicate).** That
function is the finalize/runtime scope-level signal: it fires only when a
whole scope (the document, or a "requirement"-named heading section)
declares NOTHING, and it returns prose messages with no line numbers, so its
output cannot fill this module's ``{token, line, message}`` shape. This
lint is its per-token, line-numbered extension for the planning hand-off,
built on the exact same declared set
(:func:`specify_cli.requirement_mapping.parse_requirement_ids_from_spec_md`),
the same declared shapes (:data:`grammar.DECLARED_SHAPE_PATTERNS`) and the
same comment blanking (:func:`grammar.blank_html_comments`) -- so the two
can never disagree about what is declared. This module re-implements none
of the three.

**Placeholder decision.** A placeholder such as ``FR-00N`` in a DECLARED
position IS malformed here (case-tolerant :func:`grammar.parse` accepts it,
but spec-scanning does not, so it reports :data:`RULE_LOWERCASE_SUFFIX`);
in PROSE it is silently ignored, because spec-scanning does not recognise it
as a token at all -- there is nothing for :func:`grammar.find_all` to find.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from specify_cli.requirement_mapping import grammar, parse_requirement_ids_from_spec_md

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

__all__ = ["lint_spec_requirement_ids"]

#: Reported when a declared lead case-tolerantly parses (so it names a real
#: kind + digits) but fails the lowercase-only spec-scan check -- an
#: uppercase letter suffix, or a placeholder digit-position letter such as
#: ``FR-00N``. Hoisted to a module constant (Sonar S1192): used by the rule
#: selector below, and referenced by name in three-plus tests.
RULE_LOWERCASE_SUFFIX = "write the letter suffix in lowercase (FR-006a); replace placeholders such as FR-00N with a real ID"

#: Wrapper characters a declared lead's capture never actually contains (the
#: capture charset already excludes them) -- stripped defensively so a lead
#: is never rejected purely on account of markdown emphasis markup.
_LEAD_WRAP_CHARS = "*~"
#: A single trailing punctuation mark a declared lead may carry (heading
#: colon, bullet-sentence period, list comma) that the grammar itself does
#: not accept -- stripped once, never twice.
_LEAD_TRAILING_PUNCTUATION = (".", ":", ",")

#: The declaration-shape non-blocking-warning remediation, in the vocabulary
#: FR-013's own rule text imports rather than restating (C-001: never an
#: alternation literal such as "FR|NFR").
_WARNING_REMEDIATION = (
    "Declare it in a recognised shape (a table row, an id-naming heading, a "
    "bulleted or numbered item, or a bold-led paragraph), or if it belongs to "
    "another mission, cite it as <mission-slug>#<ID>."
)


@dataclass(frozen=True, slots=True)
class InvalidRequirementId:
    """One FR-013 refusal: a malformed token in a declared position."""

    token: str
    line: int
    rule: str

    def as_dict(self) -> dict[str, object]:
        return {"token": self.token, "line": self.line, "rule": self.rule}


@dataclass(frozen=True, slots=True)
class RequirementIdWarning:
    """One FR-014 warning: an undeclared, well-formed prose token."""

    token: str
    line: int
    message: str

    def as_dict(self) -> dict[str, object]:
        return {"token": self.token, "line": self.line, "message": self.message}


@dataclass(frozen=True, slots=True)
class SpecLintResult:
    """The lint's full verdict over one spec.md text."""

    errors: tuple[InvalidRequirementId, ...]
    warnings: tuple[RequirementIdWarning, ...]

    @property
    def blocking(self) -> bool:
        """C-009: warnings never contribute here -- only ``errors`` blocks."""
        return bool(self.errors)


def _normalise_lead(token: str) -> str:
    """String-only normalisation (no new regex): strip emphasis wrappers and
    one trailing sentence/heading/list punctuation mark."""
    stripped = token.strip(_LEAD_WRAP_CHARS)
    if stripped and stripped[-1] in _LEAD_TRAILING_PUNCTUATION:
        stripped = stripped[:-1]
    return stripped


def _is_well_formed_declaration(token: str) -> bool:
    """True when *token* is a genuine, unambiguous requirement ID.

    Two independent grammar checks must agree: the token canonicalises at
    all, and spec-scanning ``find_all`` recovers exactly that one id from the
    bare token (spec_scan=True -- rejects an uppercase suffix letter and any
    trailing matter the strict canonical form would otherwise tolerate).
    """
    canonical_form = grammar.canonical(token)
    if canonical_form is None:
        return False
    matches = grammar.find_all(token, spec_scan=True)
    return len(matches) == 1 and matches[0].canonical == canonical_form


def _rule_for_malformed(token: str) -> str:
    """FR-013's rule text: the uppercase-suffix/placeholder case gets its own
    remediation; everything else names the grammar rule verbatim."""
    if grammar.parse(token) is not None:
        return RULE_LOWERCASE_SUFFIX
    return grammar.RULE_TEXT


def _record_malformed_lead(line: str, line_no: int, errors: list[InvalidRequirementId]) -> bool:
    """Record an FR-013 error for *line* when it holds a malformed declared
    lead. Returns True when this line was an error line (the caller must
    not also warn on it -- an error line never doubles as a warning)."""
    match = grammar.MALFORMED_DECLARED_LEAD.match(line)
    if match is None:
        return False
    token = _normalise_lead(match.group("lead"))
    if _is_well_formed_declaration(token):
        return False
    errors.append(InvalidRequirementId(token=token, line=line_no, rule=_rule_for_malformed(token)))
    return True


def _matches_declared_shape(line: str) -> bool:
    """True when *line* is a declaration line under any of the four shapes
    (first-ID-per-line: a table row's other cells never warn)."""
    return any(pattern.match(line) is not None for pattern in grammar.DECLARED_SHAPE_PATTERNS)


def _warning_message(token: str) -> str:
    return f"{token} looks like a requirement ID but this spec does not declare it. {_WARNING_REMEDIATION}"


def _lint_prose_line(
    line: str,
    line_no: int,
    declared: AbstractSet[str],
    warned: set[str],
    warnings: list[RequirementIdWarning],
) -> None:
    """FR-014: warn once per distinct undeclared, unqualified, well-formed
    token, at its first occurrence."""
    for requirement_id in grammar.find_all(line, spec_scan=True):
        if requirement_id.is_foreign:
            continue
        canonical_form = requirement_id.canonical
        if canonical_form in declared or canonical_form in warned:
            continue
        warned.add(canonical_form)
        warnings.append(RequirementIdWarning(token=canonical_form, line=line_no, message=_warning_message(canonical_form)))


def lint_spec_requirement_ids(spec_text: str) -> SpecLintResult:
    """FR-013/FR-014: the setup-plan requirement-ID lint over one spec.md text.

    Errors are malformed kind-prefixed tokens in a declared position
    (blocking). Warnings are unqualified, well-formed, undeclared tokens in
    prose (non-blocking, C-009). An error line never also warns; a
    declaration line's non-lead cells never warn (first-ID-per-line).
    """
    visible = grammar.blank_html_comments(spec_text)
    declared = set(parse_requirement_ids_from_spec_md(spec_text)["all"])
    errors: list[InvalidRequirementId] = []
    warnings: list[RequirementIdWarning] = []
    warned: set[str] = set()
    for line_no, line in enumerate(visible.splitlines(), start=1):
        if _record_malformed_lead(line, line_no, errors):
            continue
        if _matches_declared_shape(line):
            continue
        _lint_prose_line(line, line_no, declared, warned, warnings)
    return SpecLintResult(errors=tuple(errors), warnings=tuple(warnings))
