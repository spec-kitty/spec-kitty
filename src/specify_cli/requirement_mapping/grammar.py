"""The single requirement-ID grammar authority (C-001).

Every product-code surface that recognises, canonicalises or tokenises a
requirement ID -- the planning hand-off, ``map-requirements``,
``finalize-tasks`` (including its tasks.md fallback reader), the runtime
readiness check and the merge-cleanup retention reader's constraint-row
check -- reads IDs through this module and this module alone. No other
product module may compile a requirement-ID pattern, change an ID's case,
or tokenise a ``requirement_refs`` value; that boundary is enforced by
``tests/architectural/test_requirement_id_grammar_single_source.py``.

See ``kitty-specs/requirement-id-grammar-01M3NRCA/data-model.md`` and
``kitty-specs/requirement-id-grammar-01M3NRCA/contracts/grammar.md`` for the
software-development grammar contract, with additional kinds for research Missions:

    id         := [qualifier "#"] kind "-" digits [suffix]
    kind       := "FR" | "NFR" | "C" | "SC"  ; every Mission type
                | "DR" | "AR" | "QR"       ; research only
                                                        ; input case-insensitive
    digits     := DIGIT+                              ; verbatim, width significant
    suffix     := LOWER_LETTER                         ; spec scan: lowercase only
                                                        ; ref matching: either case
    qualifier  := slug                                 ; foreign citation, never resolved
    slug       := [a-z0-9][a-z0-9-]* ["-" 8[0-9A-Z]]    ; optional mid8 tail

Every pattern below is generated from the mission-scoped kind set
(``_KIND_ALT`` plus research kinds) and compiled through :mod:`kernel._safe_re` (RE2, C-005): no
lookbehind, no lookahead, no backreferences. Case-insensitivity is scoped to
the kind only (``(?i:...)``); nothing here passes a global ``IGNORECASE``
flag, because that would leak into the suffix and the qualifier's slug/mid8
classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from kernel._safe_re import re

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet
    from re import Match, Pattern

__all__ = [
    "RequirementId",
    "Accepted",
    "Rejected",
    "RefVerdict",
    "kinds_for",
    "parse",
    "canonical",
    "find_all",
    "is_compound_tail",
    "tokenize_refs",
    "blank_html_comments",
    "classify",
    "DECLARED_SHAPE_PATTERNS",
    "DECLARED_TABLE_ROW",
    "DECLARED_LIST_ITEM",
    "MALFORMED_DECLARED_LEAD",
    "MALFORMED",
    "UNKNOWN_SPEC_ID",
    "FOREIGN_QUALIFIED",
    "FAILING_REASONS",
    "RULE_TEXT",
]

Kind = Literal["FR", "NFR", "C", "SC", "DR", "AR", "QR"]

#: The default requirement-ID kind alternation (C-001). Research kinds are
#: appended only when the Mission type is research. Order
#: carries no matching semantics: every kind is prefix-disjoint from every
#: other (no kind is a leading substring of another), so alternation order
#: cannot shadow a longer match. The C-001 architectural gate's floor test
#: asserts that the one grammar.py site it detects IS this named constant.
_KIND_ALT: str = "FR|NFR|SC|C"
_RESEARCH_KINDS: tuple[str, ...] = ("DR", "AR", "QR")


def kinds_for(mission_type: str = "software-dev") -> frozenset[str]:
    """Requirement kinds admitted by this Mission type."""
    kinds = frozenset(("FR", "NFR", "SC", "C"))
    return kinds | frozenset(_RESEARCH_KINDS) if mission_type == "research" else kinds


def _kind_alt(mission_type: str) -> str:
    allowed = kinds_for(mission_type)
    return "|".join(kind for kind in (*_KIND_ALT.split("|"), *_RESEARCH_KINDS) if kind in allowed)


#: Legacy kinds only -- the frozen, unqualified, unsuffixed alias below
#: exists solely to keep ``tests/specify_cli/test_bare_prose_false_negative_sample.py``'s
#: pre-grammar ``finditer``/``group(0)`` figures unchanged (contract: "legacy-compat
#: alias"). Production code never uses it; production uses :func:`find_all`.
_LEGACY_KINDS = ("FR", "NFR", "C")

#: Requirement-ID slug qualifier: lowercase-word-joined, optional 8-char mid8 tail.
_SLUG = r"[a-z0-9][a-z0-9-]*(?:-[0-9A-Z]{8})?"

#: The core: kind (case-insensitive) + "-" + digits (verbatim). Every pattern
#: below is generated from this one string (C-001) plus a suffix variant.
_KIND_DIGITS = rf"(?i:{_KIND_ALT})-\d+"

#: Declared-shape core: spec scanning accepts only a LOWERCASE suffix.
_DECLARED_CORE = rf"{_KIND_DIGITS}(?:[a-z])?"

#: The qualified kind+digits core, named groups included: the optional
#: ``slug#`` qualifier, the kind (case-insensitive) and the digits. Shared by
#: every ref-matching / token-boundary pattern below (one named-group core,
#: not a re-spelling per pattern).
_QUALIFIED_KIND_DIGITS = rf"(?:(?P<mission>{_SLUG})#)?(?P<kind>(?i:{_KIND_ALT}))-(?P<digits>\d+)"

# --------------------------------------------------------------------------- #
# RequirementId value object.
# --------------------------------------------------------------------------- #


def _normalize_kind(raw: str) -> Kind:
    """Uppercase *raw* onto the closed :data:`Kind` literal.

    The regexes below only ever hand this a string that matched the selected
    mission kind set, so every branch is reachable; the final ``raise``
    exists to keep the return type total for mypy --strict rather than to
    signal a real runtime possibility.
    """
    upper = raw.upper()
    if upper == "FR":
        return "FR"
    if upper == "NFR":
        return "NFR"
    if upper == "SC":
        return "SC"
    if upper == "C":
        return "C"
    if upper == "DR":
        return "DR"
    if upper == "AR":
        return "AR"
    if upper == "QR":
        return "QR"
    raise ValueError(f"unrecognized requirement-id kind: {raw!r}")


@dataclass(frozen=True)
class RequirementId:
    """A parsed requirement ID (C-001 value object).

    Equality and hashing are the dataclass default over the canonical tuple
    ``(kind, digits, suffix, mission)`` -- exactly the fields declared here,
    per ``data-model.md``.
    """

    kind: Kind
    digits: str
    suffix: str | None = None
    mission: str | None = None

    @property
    def canonical(self) -> str:
        """The unqualified canonical string: kind uppercase, suffix lowercase."""
        return f"{self.kind}-{self.digits}{self.suffix or ''}"

    @property
    def is_foreign(self) -> bool:
        return self.mission is not None

    @property
    def is_functional(self) -> bool:
        return self.kind == "FR"

    @property
    def is_success_criterion(self) -> bool:
        return self.kind == "SC"

    def __str__(self) -> str:
        """The qualified form when foreign, else the bare canonical string."""
        if self.mission is not None:
            return f"{self.mission}#{self.canonical}"
        return self.canonical


# --------------------------------------------------------------------------- #
# parse / canonical -- ref-matching (suffix case-tolerant either way).
# --------------------------------------------------------------------------- #

_STRICT_REF_MATCH: Pattern[str] = re.compile(rf"^{_QUALIFIED_KIND_DIGITS}(?P<suffix>[a-zA-Z])?$")


def parse(token: str, *, mission_type: str = "software-dev") -> RequirementId | None:
    """Strict full-match on *token* (qualifier optional, suffix case-tolerant).

    Used for ``map-requirements`` input, WP ref classification, and the
    consolidation retention constraint-row check.
    """
    pattern = _STRICT_REF_MATCH
    if mission_type == "research":
        pattern = re.compile(
            rf"^(?:(?P<mission>{_SLUG})#)?(?P<kind>(?i:{_kind_alt(mission_type)}))"
            r"-(?P<digits>\d+)(?P<suffix>[a-zA-Z])?$"
        )
    match = pattern.fullmatch(token)
    if match is None:
        return None
    suffix = match.group("suffix")
    return RequirementId(
        kind=_normalize_kind(match.group("kind")),
        digits=match.group("digits"),
        suffix=suffix.lower() if suffix else None,
        mission=match.group("mission"),
    )


def canonical(token: str, *, mission_type: str = "software-dev") -> str | None:
    """The canonical string for *token* (qualified when *token* was), or ``None``."""
    requirement_id = parse(token, mission_type=mission_type)
    return str(requirement_id) if requirement_id is not None else None


# --------------------------------------------------------------------------- #
# find_all -- token-boundary scan over free text (declared/prose/refs).
# --------------------------------------------------------------------------- #

_TOKEN_LOWER_SUFFIX: Pattern[str] = re.compile(rf"\b{_QUALIFIED_KIND_DIGITS}(?P<suffix>(?-i:[a-z]))?\b")
_TOKEN_ANY_SUFFIX: Pattern[str] = re.compile(rf"\b{_QUALIFIED_KIND_DIGITS}(?P<suffix>[a-zA-Z])?\b")
_COMPOUND_TAIL: Pattern[str] = re.compile(r"^[-.][A-Za-z0-9]")
_INVALID_QUALIFIER_LEAD: Pattern[str] = re.compile(r"[#.]$")


def is_compound_tail(text: str, end: int) -> bool:
    """True when a token boundary is immediately followed by a
    ``-<letter|digit>`` or a ``.<letter|digit>``.

    ``FR-008-mandated`` is not an ID in prose and not well-formed in a
    declared position (contract: token boundary + in-code compound check,
    no lookahead). ``FR-002.3`` is likewise not an ID: the grammar has no
    dotted-tail form, so a following ``.`` + alphanumeric (a dotted
    sub-requirement id, e.g. ``FR-002.3``, ``### FR-001.1 Title``,
    ``**FR-004.1** x``) must drop the whole token rather than silently
    truncate it to the well-formed prefix (``FR-002``) -- truncation would
    let a spec-scan/declared-id consumer accept a token the setup-plan lint
    (:mod:`specify_cli.requirement_mapping.lint`, which reads the same
    ``.``-inclusive lead charset) refuses as malformed, disagreeing about
    what the document declares. A sentence-final period is NOT a dotted
    tail: ``.`` followed by whitespace or end-of-string (``see FR-001.``)
    leaves nothing alphanumeric for this check to match, so it still yields
    ``FR-001``. Public: reused by :func:`find_all` and by the
    declared-shape scan in ``requirement_mapping/__init__.py``.
    """
    return _COMPOUND_TAIL.match(text[end : end + 2]) is not None


def _has_invalid_qualifier_prefix(text: str, match: Match[str]) -> bool:
    """True when *match*'s start reveals a leaked or truncated qualifier (FR-009).

    ``#`` is itself a non-word character, so ``\\b`` holds right after it: when
    a slug fails the qualifier grammar (an uppercase letter, an underscore,
    ...), the optional qualifier group backs off to zero-width and the match
    silently restarts as a LOCAL id right after the dropped ``#``
    (``Other-Mission#FR-001`` / ``other_mission#FR-001`` -> local ``FR-001``).
    And when a qualifier DID capture (``match.group("mission")`` is set), a
    leading ``.`` right before the captured slug means a longer run was
    silently truncated to a shorter, wrong qualifier (``x.y#FR-001`` ->
    foreign ``y#FR-001`` instead of not-an-id). Mirrors :func:`is_compound_tail`:
    plain text indexing, no lookbehind.
    """
    if match.start() == 0:
        return False
    lead = text[match.start() - 1 : match.start()]
    if _INVALID_QUALIFIER_LEAD.match(lead) is None:
        return False
    return lead == "#" or match.group("mission") is not None


def find_all(text: str, *, spec_scan: bool, mission_type: str = "software-dev") -> list[RequirementId]:
    """Every ID token in *text*, with the qualifier consumed.

    ``spec_scan=True`` recognises only a lowercase suffix (spec scanning);
    ``spec_scan=False`` is case-tolerant on the suffix (ref-item matching).
    A compound tail (``-mandated``, ``-mission``) drops the token entirely,
    and so does a leaked or truncated qualifier (FR-009): a match whose
    start is preceded by ``#`` (a failed qualifier attempt silently
    dropped), or whose captured qualifier is preceded by ``.`` (a truncated
    slug), is never a local or foreign id -- the whole ``...#ID`` run is
    dropped.
    """
    pattern = _TOKEN_LOWER_SUFFIX if spec_scan else _TOKEN_ANY_SUFFIX
    if mission_type == "research":
        suffix = r"(?P<suffix>(?-i:[a-z]))?" if spec_scan else r"(?P<suffix>[a-zA-Z])?"
        pattern = re.compile(rf"\b(?:(?P<mission>{_SLUG})#)?(?P<kind>(?i:{_kind_alt(mission_type)}))-(?P<digits>\d+){suffix}\b")
    found: list[RequirementId] = []
    for match in pattern.finditer(text):
        if is_compound_tail(text, match.end()):
            continue
        if _has_invalid_qualifier_prefix(text, match):
            continue
        suffix = match.group("suffix")
        found.append(
            RequirementId(
                kind=_normalize_kind(match.group("kind")),
                digits=match.group("digits"),
                suffix=suffix.lower() if suffix else None,
                mission=match.group("mission"),
            )
        )
    return found


# --------------------------------------------------------------------------- #
# tokenize_refs -- raw frontmatter value -> raw string tokens (case preserved).
# --------------------------------------------------------------------------- #

_TOKEN_SPLIT: Pattern[str] = re.compile(r"[,\s]+")


def _split_scalar(value: str) -> list[str]:
    return [token for token in _TOKEN_SPLIT.split(value) if token.strip()]


def tokenize_refs(value: object) -> list[str]:
    """Raw tokens from a frontmatter ``requirement_refs`` value.

    A list keeps its ``str`` items verbatim; a non-``str`` item becomes
    ``<NON_STRING:...>``. A scalar string is split on ``[,\\s]+``. Case is
    preserved so diagnostics can show exactly what was written.
    """
    tokens: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                tokens.extend(_split_scalar(item))
            else:
                tokens.append(f"<NON_STRING:{item}>")
    elif isinstance(value, str):
        tokens.extend(_split_scalar(value))
    return tokens


# --------------------------------------------------------------------------- #
# Declared shapes + the malformed-declared-lead locator.
# --------------------------------------------------------------------------- #

#: Declared shape: a table row whose id cell (optional **bold**/~~strike~~
#: wrapper, either side) is group 1. The match ends after the id cell's
#: closing ``|``, so ``line[match.end():]`` is the row's remaining cells.
DECLARED_TABLE_ROW: Pattern[str] = re.compile(rf"^\s*\|\s*(?:\*\*|~~){{0,2}}({_DECLARED_CORE})(?:\*\*|~~){{0,2}}\s*\|")

#: Declared shape: a bulleted / numbered list item whose lead (bold
#: optional) is the id, group 1.
DECLARED_LIST_ITEM: Pattern[str] = re.compile(rf"^\s*(?:[-*]|\d+\.)\s*\*{{0,2}}({_DECLARED_CORE})\b")

DECLARED_SHAPE_PATTERNS: tuple[Pattern[str], ...] = (
    DECLARED_TABLE_ROW,
    # Heading naming the id (``### FR-001`` / ``### FR-001: Title``).
    re.compile(rf"^#{{1,6}}\s*({_DECLARED_CORE})\b"),
    DECLARED_LIST_ITEM,
    # Bold id leading a bare paragraph.
    re.compile(rf"^\s*\*\*({_DECLARED_CORE})\b"),
)


def declared_shape_patterns(mission_type: str = "software-dev") -> tuple[Pattern[str], ...]:
    if mission_type != "research":
        return DECLARED_SHAPE_PATTERNS
    core = rf"(?i:{_kind_alt(mission_type)})-\d+(?:[a-z])?"
    return (
        re.compile(rf"^\s*\|\s*(?:\*\*|~~){{0,2}}({core})(?:\*\*|~~){{0,2}}\s*\|"),
        re.compile(rf"^#{{1,6}}\s*({core})\b"),
        re.compile(rf"^\s*(?:[-*]|\d+\.)\s*\*{{0,2}}({core})\b"),
        re.compile(rf"^\s*\*\*({core})\b"),
    )


def malformed_declared_lead(mission_type: str = "software-dev") -> Pattern[str]:
    if mission_type != "research":
        return MALFORMED_DECLARED_LEAD
    return cast(
        "Pattern[str]",
        re.compile(
            r"^(?:\s*\|\s*(?:\*\*|~~){0,2}|#{1,6}\s*|\s*(?:[-*]|\d+\.)\s*\*{0,2}|\s*\*\*)"
            rf"(?P<lead>(?:{_kind_alt(mission_type)})[-_][0-9A-Z][A-Za-z0-9_.\-]*)"
        ),
    )


#: A kind-prefixed lead in a declared position, uppercase-kind-only and
#: case-sensitive (FR-013). This is a LOCATOR: it finds the candidate lead
#: token; a caller then checks ``parse(lead) is None`` to decide malformed-ness
#: (RE2 has no negative lookahead, so "does not full-match" cannot live
#: inside the pattern itself). The captured charset ``[A-Za-z0-9_.-]`` stops
#: at the first other character (analysis B6), so ``FR-009's``, ``FR-001/FR-002``
#: and ``FR-002–FR-006`` each capture a well-formed lead and do not error.
MALFORMED_DECLARED_LEAD: Pattern[str] = re.compile(
    r"^(?:"
    r"\s*\|\s*(?:\*\*|~~){0,2}"
    r"|#{1,6}\s*"
    r"|\s*(?:[-*]|\d+\.)\s*\*{0,2}"
    r"|\s*\*\*"
    rf")(?P<lead>(?:{_KIND_ALT})[-_][0-9A-Z][A-Za-z0-9_.\-]*)"
)


# --------------------------------------------------------------------------- #
# blank_html_comments -- position-preserving comment blanking.
# --------------------------------------------------------------------------- #

_HTML_COMMENT_TERMINATED: Pattern[str] = re.compile(r"(?s)<!--.*?-->")
_HTML_COMMENT_UNTERMINATED: Pattern[str] = re.compile(r"(?s)<!--.*")


def _blank_span(match: Match[str]) -> str:
    return "".join(ch if ch == "\n" else " " for ch in match.group(0))


def blank_html_comments(text: str) -> str:
    """*text* with every ``<!-- ... -->`` span replaced by spaces.

    Newlines inside the span are kept, so line count and character
    positions are preserved. An unterminated ``<!--`` blanks to the end of
    the text.
    """
    text = _HTML_COMMENT_TERMINATED.sub(_blank_span, text)
    return _HTML_COMMENT_UNTERMINATED.sub(_blank_span, text)


# --------------------------------------------------------------------------- #
# classify / RefVerdict -- the shared FR-019 verdict table.
# --------------------------------------------------------------------------- #

MALFORMED = "malformed"
UNKNOWN_SPEC_ID = "unknown_spec_id"
FOREIGN_QUALIFIED = "foreign_qualified"
FAILING_REASONS: frozenset[str] = frozenset({MALFORMED, UNKNOWN_SPEC_ID})

RULE_TEXT = "<kind>-<digits>[<lowercase letter>]"


@dataclass(frozen=True)
class Accepted:
    """A ref that parsed, is unqualified and is in the declared set."""

    requirement_id: RequirementId


@dataclass(frozen=True)
class Rejected:
    """A ref the grammar could not accept, with exactly one reason."""

    raw: str
    reason: str


RefVerdict = Accepted | Rejected


def classify(raw: str, declared: AbstractSet[str], *, mission_type: str = "software-dev") -> RefVerdict:
    """Apply the FR-019 verdict table to *raw* against the *declared* canonical-ID set.

    Order: does not parse -> ``malformed``; has a qualifier ->
    ``foreign_qualified`` (never fails); not in ``declared`` by canonical
    form -> ``unknown_spec_id``; otherwise accepted.
    """
    requirement_id = parse(raw, mission_type=mission_type)
    if requirement_id is None:
        return Rejected(raw, MALFORMED)
    if requirement_id.mission is not None:
        return Rejected(raw, FOREIGN_QUALIFIED)
    if requirement_id.canonical not in declared:
        return Rejected(raw, UNKNOWN_SPEC_ID)
    return Accepted(requirement_id)


#: The legacy-compat alias (contract "Home" section): unqualified,
#: unsuffixed, no compound check. Generated from :data:`_LEGACY_KINDS` --
#: never a second hand-written alternation (analysis F14). Kept importable
#: ONLY so ``tests/specify_cli/test_bare_prose_false_negative_sample.py``'s
#: frozen ``finditer``/``group(0)`` figures do not move; production code
#: uses :func:`find_all`.
_LEGACY_REF_FIND_PATTERN: Pattern[str] = re.compile(rf"\b(?i:{'|'.join(_LEGACY_KINDS)})-\d+\b")
