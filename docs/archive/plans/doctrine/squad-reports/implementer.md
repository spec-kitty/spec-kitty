---
title: Implementer lens — feasibility and the prototype slice
description: "Buildability of the creed design here: real Pydantic models, the delta representation decision, the coverage gate, and a one-day pre-registered prototype."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/archive/plans/doctrine/creed-and-values-design-hardened.md
- docs/archive/plans/doctrine/creed-and-values-design-as-proposed.md
---
# Implementer lens — feasibility and the prototype slice

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

> Raw squad report, 2026-07-26. Profile-loaded, read-only. Preserved verbatim as the
> evidence base for [`creed-and-values-design-hardened.md`](../creed-and-values-design-hardened.md).
> Forbidden-legacy-term literals are redacted where quoted, so the docs terminology guard stays green.

I have what I need. Writing up now — no files written, nothing mutated.

---

## Profile adopted

Read `src/doctrine/agent_profiles/built-in/python-pedro.agent.yaml`. Applied, and where a directive constrains this answer I say so inline:

- **DIRECTIVE_010** (Specification Fidelity) — models mirror the authored `{name, delta, rationale}` shape from §5.1 verbatim rather than a "cleaner" schema of my own.
- **DIRECTIVE_030 / 034** (quality gate, test-first) — the coverage gate is written *before* the schema in §4, and the prototype's success thresholds are fixed before the run.
- **DIRECTIVE_041** (Tests as Scaffold, Not Friction) — this is why I reject the proposed "eyeball whether top-N differ" signal: it cannot fail, so it is not evidence.
- **DIRECTIVE_043** (Close Defect Classes by Construction) — the half-open set trades type safety for an architectural gate; I name the gate.
- **DIRECTIVE_044** (Canonical Sources) — `Role` in `src/doctrine/agent_profiles/profile.py` is an existing proven half-open value object; I reuse the pattern rather than invent one. Same for the catalog-contract test shape.
- **DIRECTIVE_024/025** — the prototype touches no existing artefact file and adds no field to any shipped model.
- **tactic:test-scaffolding-as-design-smell** — the ranking function is pure (`Creed × Mapping[str, Sequence[ValueDelta]] → list[tuple[str, float]]`), so the experiment needs no filesystem, no DRG, no charter.
- **Avoidance boundary respected**: I do not decide whether to build this. §4 and the Verdict state preconditions; the go/no-go is architect + operator.

**Read-only confirmed.** Only `Read`/`grep`/`sed`/`ls`/`cat`. No git beyond none at all. No files written.

---

## Models

Python target is **3.11** (`requires-python = ">=3.11"`, `ruff target-version = "py311"`), not 3.12 — so no PEP 695 generics. Pydantic is **2.13.4**.

### `src/doctrine/values/models.py` (new)

```python
"""Foundational value system: half-open value names, per-artefact deltas, connascence.

The value *set* is doctrine-tier and replaceable (built-in AMMERSE ships as the
default). The *creed* — the project's weighting of those values — is charter-tier
and lives in ``src/charter/creed.py``, never here: a reusable doctrine library must
not carry project-specific data.

Authored shape fidelity (DIRECTIVE_010): ``ValueDelta`` mirrors the upstream
authored TOML entry ``{name, delta, rationale}`` exactly, including ``delta``'s
quoted-string authoring form, so a vendored corpus row parses with no translation
layer. See ``docs/archive/plans/doctrine/creed-and-values-design-as-proposed.md`` §5.1.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "AUTHORED_DELTA_GRID",
    "DELTA_LOWER_BOUND",
    "DELTA_UPPER_BOUND",
    "FoundationalValue",
    "FoundationalValueName",
    "ValueConnascence",
    "ValueConnascenceMatrix",
    "ValueDelta",
    "ValueSet",
    "off_grid_delta",
]

#: Inclusive bounds of the normalized impact scale (design §1, §2).
DELTA_LOWER_BOUND = Decimal("-1")
DELTA_UPPER_BOUND = Decimal("1")

#: The resolution the upstream corpus actually authors at (§5.5: 22 distinct
#: magnitudes at 0.05). Deliberately NOT a validation constraint — one authored
#: value in the operator's own 36-row corpus (``wipe_the_board``'s
#: ``environmental = 0.125``) is off this grid, so enforcing it would reject
#: real data. Exposed for the advisory lint via :func:`off_grid_delta`.
AUTHORED_DELTA_GRID = Decimal("0.05")

#: A delta must arrive as the authored quoted string (or an already-exact
#: Decimal). Binary floats are rejected at the boundary -- see
#: ``ValueDelta._require_authored_form``.
_AUTHORED_DELTA_TYPES: tuple[type, ...] = (str, Decimal)

_MIN_RATIONALE_CHARS = 20
_MIN_DESCRIPTION_CHARS = 20


def _normalize_value_name(value: str) -> str:
    return value.strip().lower()


class FoundationalValueName(str):
    """Half-open foundational-value name.

    Subclasses ``str`` rather than ``StrEnum`` for exactly the reason
    :class:`doctrine.agent_profiles.profile.Role` does: a ``StrEnum`` seals the
    vocabulary at class-definition time, so a consumer replacing AMMERSE with
    their own value system would have to fork the library. This type is the same
    proven pattern, including the pydantic-core hook.

    Well-known names are the seven AMMERSE axes, declared as class constants and
    listed in ``_KNOWN``. ``is_known()`` is *informational only* — a custom name
    is intentionally valid, so never use it as a validity gate. The validity gate
    is membership in the **active** :class:`ValueSet`, checked by
    :meth:`ValueSet.assert_covers`, not by this type.

    ⚠ Product code MUST NOT reference the constants below. They exist for the
    built-in seed data, migrations, and tests. Naming an axis in product code
    hardcodes the built-in basis and silently misbehaves for a consumer who
    replaced the set. Enforced by
    ``tests/architectural/test_value_names_not_referenced_in_product_code.py``.
    """

    _KNOWN: ClassVar[frozenset[str]] = frozenset()  # populated after class body

    def __new__(cls, value: str) -> FoundationalValueName:
        normalized = _normalize_value_name(value)
        if not normalized:
            raise ValueError("FoundationalValueName must be a non-empty string")
        return str.__new__(cls, normalized)

    @classmethod
    def is_known(cls, name: FoundationalValueName | str) -> bool:
        """True iff *name* is one of the built-in AMMERSE constants.

        Informational (capability lookup, diagnostics, provenance labels) —
        never a validity check. See the class docstring.
        """
        return _normalize_value_name(str(name)) in cls._KNOWN

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(strip_whitespace=True),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    # -- Built-in AMMERSE constants (seed data / tests / migrations only) ----
    AGILE: ClassVar[FoundationalValueName]
    MINIMAL: ClassVar[FoundationalValueName]
    MAINTAINABLE: ClassVar[FoundationalValueName]
    ENVIRONMENTAL: ClassVar[FoundationalValueName]
    REACHABLE: ClassVar[FoundationalValueName]
    SOLVABLE: ClassVar[FoundationalValueName]
    EXTENSIBLE: ClassVar[FoundationalValueName]


# Assigned after the class body so __new__ exists (mirrors Role).
FoundationalValueName.AGILE = FoundationalValueName("agile")
FoundationalValueName.MINIMAL = FoundationalValueName("minimal")
FoundationalValueName.MAINTAINABLE = FoundationalValueName("maintainable")
FoundationalValueName.ENVIRONMENTAL = FoundationalValueName("environmental")
FoundationalValueName.REACHABLE = FoundationalValueName("reachable")
FoundationalValueName.SOLVABLE = FoundationalValueName("solvable")
FoundationalValueName.EXTENSIBLE = FoundationalValueName("extensible")

FoundationalValueName._KNOWN = frozenset({
    str(FoundationalValueName.AGILE),
    str(FoundationalValueName.MINIMAL),
    str(FoundationalValueName.MAINTAINABLE),
    str(FoundationalValueName.ENVIRONMENTAL),
    str(FoundationalValueName.REACHABLE),
    str(FoundationalValueName.SOLVABLE),
    str(FoundationalValueName.EXTENSIBLE),
})


def off_grid_delta(delta: Decimal) -> bool:
    """True when *delta* is not a multiple of the 0.05 authoring grid.

    Advisory: an off-grid delta is a *review prompt* ("did you mean 0.15?"),
    never a validation failure. §5.5's corpus contains one legitimate off-grid
    value, so a hard constraint here would reject the calibration set itself.
    """
    return delta.copy_abs() % AUTHORED_DELTA_GRID != 0


class FoundationalValue(BaseModel):
    """One entry in a value set: the name and the definition it is scored against.

    ``description`` is required and non-trivial because it is the scoring lens.
    §4 of the design makes the prose "pivotal" for correct-ish LLM interpretation;
    a value with no definition produces uninterpretable deltas.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: FoundationalValueName
    description: str = Field(min_length=_MIN_DESCRIPTION_CHARS)
    abbreviation: str | None = Field(default=None, pattern=r"^[A-Z][a-z]?$")
    """Short form used in prose and diagrams (AMMERSE: A, Mi, Ma, E, R, S, Ex)."""


class ValueSet(BaseModel):
    """A replaceable, ordered set of foundational values (open-closed, design §1).

    ``values`` is an ordered *list*, not a mapping: any vector, matrix, or PCA
    operation needs a stable axis order, and dict ordering is an implementation
    detail nobody should depend on.

    ``attribution`` is required and non-empty. The built-in set is a third-party
    value system whose *name* is trademarked (design §4); a schema slot that
    cannot be left blank is the cheapest available guarantee that a derived or
    replaced set still carries its accreditation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str
    attribution: str = Field(min_length=1)
    values: list[FoundationalValue] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_names(self) -> Self:
        seen: set[str] = set()
        duplicates = sorted({
            str(v.name) for v in self.values
            if str(v.name) in seen or seen.add(str(v.name))  # type: ignore[func-returns-value]
        })
        if duplicates:
            raise ValueError(
                f"value set {self.id!r} declares duplicate value name(s): "
                f"{duplicates}. Names are case-insensitively normalized, so "
                f"'Minimal' and 'minimal' are the same value."
            )
        return self

    def names(self) -> tuple[FoundationalValueName, ...]:
        """Value names in authored (axis) order."""
        return tuple(v.name for v in self.values)

    def assert_covers(self, deltas: list[ValueDelta], *, subject: str) -> None:
        """Referential-integrity gate for an authored delta vector.

        This is the real validity check that :meth:`FoundationalValueName.is_known`
        is *not*. It cannot live on :class:`ValueDelta` — a half-open name has no
        access to the active set at field-validation time — so it is a
        repository-level pass that a caller can forget to invoke. That is the
        cost of the open set; see "Half-open set" below.

        Raises on either direction of mismatch. Never silently drops an unknown
        name: the three silent-kind-drop sites named in the handover
        (``query.py:231-241``, ``_classify_artifact_urns``, ``extractor._KIND_MAP``)
        are the precedent for why.
        """
        declared = {str(n) for n in self.names()}
        authored = {str(d.name) for d in deltas}
        unknown = sorted(authored - declared)
        missing = sorted(declared - authored)
        if unknown or missing:
            raise ValueError(
                f"{subject}: value-delta vector does not match value set "
                f"{self.id!r}. Unknown value name(s): {unknown or 'none'}. "
                f"Missing value name(s): {missing or 'none'}. A vector must "
                f"score every value in the active set exactly once."
            )


class ValueDelta(BaseModel):
    """One authored value-impact entry on a behavioural doctrine artefact.

    "Delta" is load-bearing (§5.1): this is the *change caused by adopting the
    artefact*, relative to not adopting it — not an absolute property of it.

    ``rationale`` is required and non-trivial, and is 1:1 with ``delta`` because
    co-location is already the upstream invariant. An unrationalized number is
    unfalsifiable, which is the objection this field answers.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: FoundationalValueName
    delta: Decimal = Field(
        ge=DELTA_LOWER_BOUND,
        le=DELTA_UPPER_BOUND,
        max_digits=4,
        decimal_places=3,
        allow_inf_nan=False,
    )
    rationale: str = Field(min_length=_MIN_RATIONALE_CHARS)

    @field_validator("delta", mode="before")
    @classmethod
    def _require_authored_form(cls, value: Any) -> Any:
        """Reject unquoted numerics so the on-disk form stays a string.

        Not decorative. An unquoted ``delta: 0.9`` loads as a binary float;
        ``Decimal(0.9)`` is ``0.9000000000000000222...``, which then fails
        ``decimal_places=3`` with an error message that says nothing useful
        about the actual mistake. More importantly, allowing the numeric form
        means the emitter can round-trip an artefact file from ``"0.9"`` to
        ``0.9`` and change the bytes of every artefact — see "delta
        representation" below.
        """
        if isinstance(value, bool) or not isinstance(value, _AUTHORED_DELTA_TYPES):
            raise ValueError(
                f"delta must be authored as a quoted string (e.g. \"0.9\", "
                f"\"-0.25\"), got {type(value).__name__}. Quote the value in "
                f"YAML/TOML: unquoted numerics load as binary floats and lose "
                f"the authored precision."
            )
        return value

    @field_validator("delta", mode="after")
    @classmethod
    def _reject_non_finite(cls, value: Decimal) -> Decimal:
        """Belt-and-braces over ``allow_inf_nan=False``.

        ``Decimal("sNaN")`` *raises* ``InvalidOperation`` on comparison rather
        than returning ``False``, so a bounds check alone can surface as an
        internal error instead of a validation error. An explicit
        ``is_finite()`` keeps the failure a clean ``ValidationError``.
        """
        if not value.is_finite():
            raise ValueError("delta must be a finite decimal (no NaN, sNaN, or Infinity)")
        return value


class ValueConnascence(BaseModel):
    """One directed cell of the value-interaction matrix (design §1).

    ⚠ Do NOT ship this or :class:`ValueConnascenceMatrix` in the first commit.
    See "Coverage gate" and the Verdict: the first-order matrix is not in this
    repository, both in-repo copies defer to an external URL, and it is the
    trademarked party's uncalibrated judgement. A matrix schema with no
    authorable source is a schema slot with no producer — the exact 3-for-3
    failure the handover documents. Declared here so the shape is settled;
    parked until a producer exists.

    Modelled as a sparse *edge list* rather than a nested ``list[list[Decimal]]``
    for three reasons: each cell needs its own rationale (the co-location
    invariant); cells address values by name so the matrix survives value-set
    replacement instead of silently mis-indexing; and a missing cell is a named
    absence rather than a positional guess.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: FoundationalValueName
    target: FoundationalValueName
    impact: Decimal = Field(
        ge=DELTA_LOWER_BOUND,
        le=DELTA_UPPER_BOUND,
        max_digits=4,
        decimal_places=3,
        allow_inf_nan=False,
    )
    rationale: str = Field(min_length=_MIN_RATIONALE_CHARS)

    @model_validator(mode="after")
    def _reject_self_cell(self) -> Self:
        if str(self.source) == str(self.target):
            raise ValueError(
                f"connascence cell {self.source!s} -> {self.target!s} is a "
                f"diagonal (self) cell; a value's impact on itself is not "
                f"modelled. Remove the cell."
            )
        return self


class ValueConnascenceMatrix(BaseModel):
    """The N x (N-1) directed off-diagonal interaction matrix for one value set.

    **Asymmetric by construction**: "how much does Agile's movement drag
    Minimal" is a different question from the reverse, so a 7-value set needs
    42 cells, not 21. Completeness is checked against the value set via
    :meth:`assert_complete_for` — not in a field validator, because a matrix
    cannot see the active set at field-validation time (same constraint as
    :class:`ValueDelta`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    value_set_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    order: int = Field(ge=1, le=1)
    """Interaction order. Pinned to 1: only first-order is contemplated, and
    even that has no in-repo source. Widen only when a second-order source
    exists and is calibrated."""
    cells: list[ValueConnascence] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_cells(self) -> Self:
        seen: set[tuple[str, str]] = set()
        for cell in self.cells:
            key = (str(cell.source), str(cell.target))
            if key in seen:
                raise ValueError(f"duplicate connascence cell {key[0]} -> {key[1]}")
            seen.add(key)
        return self

    def assert_complete_for(self, value_set: ValueSet) -> None:
        """Raise unless every directed off-diagonal pair is present exactly once."""
        names = [str(n) for n in value_set.names()]
        expected = {(a, b) for a in names for b in names if a != b}
        actual = {(str(c.source), str(c.target)) for c in self.cells}
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing or extra:
            raise ValueError(
                f"connascence matrix for {self.value_set_id!r} is not complete: "
                f"{len(missing)} missing cell(s) {missing[:5]}"
                f"{'...' if len(missing) > 5 else ''}, "
                f"{len(extra)} unexpected cell(s) {extra[:5]}"
                f"{'...' if len(extra) > 5 else ''}. Expected "
                f"{len(expected)} directed off-diagonal cells."
            )
```

### `src/charter/creed.py` (new) — the charter-tier weighting

```python
"""The project's creed: how important each foundational value is to *us*.

Charter-tier by design (design §3, and the handover's "project-specific data in a
reusable library" resolution): the value *set* is doctrine, the *weighting* is the
project's own declaration and lives with the charter.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from doctrine.values.models import FoundationalValueName

__all__ = ["Creed", "CreedWeight", "WEIGHT_LOWER_BOUND", "WEIGHT_UPPER_BOUND"]

#: Importance is a magnitude on [0, 1], NOT a delta on [-1, 1]. A negative
#: importance ("this value is anti-important to us") has no meaning, and sharing
#: one scalar type with ValueDelta would admit it. Two bounded types, not one.
WEIGHT_LOWER_BOUND = Decimal("0")
WEIGHT_UPPER_BOUND = Decimal("1")

_MIN_RATIONALE_CHARS = 20


class CreedWeight(BaseModel):
    """One value's importance to this project, with the reason it holds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: FoundationalValueName
    weight: Decimal = Field(
        ge=WEIGHT_LOWER_BOUND,
        le=WEIGHT_UPPER_BOUND,
        max_digits=4,
        decimal_places=3,
        allow_inf_nan=False,
    )
    rationale: str = Field(min_length=_MIN_RATIONALE_CHARS)

    @field_validator("weight", mode="before")
    @classmethod
    def _require_authored_form(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (str, Decimal)):
            raise ValueError(
                'weight must be authored as a quoted string (e.g. "0.8"); '
                "unquoted numerics load as binary floats."
            )
        return value


class Creed(BaseModel):
    """A project's authored weighting over the active value set.

    Weights are deliberately NOT required to sum to 1. "How important is this to
    us" is an independent magnitude per value; forcing authors to normalize
    destroys that reading and no interview reliably elicits a simplex. Normalization
    happens once, at the ranking boundary (``doctrine.values.ranking``), so exactly
    one place owns it.

    ``authored_by`` is required: per the handover's second human decision, a creed
    is the operator's declaration of their own values and an agent drafting it is
    the self-scoring failure mode. The field makes authorship auditable rather
    than assumed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    value_set_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    weights: list[CreedWeight] = Field(min_length=1)
    authored_by: str = Field(min_length=1)
    authored_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def _reject_duplicate_and_degenerate(self) -> Self:
        names = [str(w.name) for w in self.weights]
        if len(names) != len(set(names)):
            raise ValueError("creed declares the same value name more than once")
        if all(w.weight == WEIGHT_LOWER_BOUND for w in self.weights):
            raise ValueError(
                "creed assigns zero importance to every value, which cannot rank "
                "anything. Declare at least one non-zero weight, or do not "
                "declare a creed."
            )
        return self
```

Wiring point (not part of the prototype): `Creed` attaches as an optional field on `CharterYaml` in `src/charter/schemas.py:280` and its key joins `_OPTIONAL_EMPTY_OMIT_KEYS` (line ~330) so existing charters stay byte-identical — the established NFR-005 pattern in that file.

---

## `delta` representation

**Decision: `Decimal` in the model, authored as a quoted string on disk, serialized back to a string. Not `float`, not raw `str`.**

The deciding argument is repo-specific and comes from code I read, not from general "floats are icky":

`src/charter/schemas.py:emit_yaml` does `model_dump(mode="json")` and hands the result to ruamel with `preserve_quotes = True`. That file is saturated with the invariant that emitted YAML must stay **byte-identical** across a mission (`_prune_optional_empties`, `_OPTIONAL_EMPTY_OMIT_KEYS`, five separate "NFR-005 byte-identical" comments). Now trace a delta through it:

- **`float`** → `model_dump(mode="json")` yields a Python `float` → ruamel emits `0.9` **unquoted**. The authored `"0.9"` becomes `0.9`. First round-trip through any emitter rewrites the delta line of every artefact that carries a vector. On a 36-artefact sweep that is a diff nobody authored, and `-0.25` → `-0.25` reparses as float, so the string form is gone permanently.
- **`Decimal`** → `model_dump(mode="json")` yields the `str` `"0.9"` → ruamel represents a numeric-looking string as `'0.9'` (it must quote, or the value would reparse as a float). Byte-stable, reparses as `str`, revalidates to the same `Decimal`.
- **raw `str`** → round-trips fine but pushes `Decimal(...)` / `float(...)` parsing into every consumer, so range and resolution are unvalidated at the type boundary and arithmetic scatters. Rejected on DDD grounds: the domain object is a bounded scalar, not text.

Secondary reasons for `Decimal`: the 0.05 authoring grid is *exactly* representable in decimal and *not* in binary (`0.05`, `0.15`, `0.45`, `0.85` are all inexact as floats); `Decimal("0.9") == Decimal("0.90")` compares numerically while `str()` preserves the authored form; and `Decimal` arithmetic never appears in hot paths because ranking converts to `float` once, at one boundary.

**What the validator must enforce:**

| Rule | Mechanism | Note |
| --- | --- | --- |
| Range `[-1, 1]` inclusive | `Field(ge=Decimal("-1"), le=Decimal("1"))` | Exact in Decimal; no epsilon |
| No NaN / sNaN / Inf | `allow_inf_nan=False` **plus** an explicit `is_finite()` after-validator | `Decimal("sNaN")` *raises* `InvalidOperation` on comparison instead of returning `False`, so bounds alone can surface as an internal error rather than a `ValidationError` |
| Resolution ceiling | `max_digits=4, decimal_places=3` | Admits `-1.000`, `0.125`, `1.0`. Bounds authoring noise without banning real data |
| Authored form is a string | before-validator rejecting `float`/`int`/`bool` with a "quote the value" message | This is what makes the byte-stability above an invariant rather than a hope |
| **Never** `Decimal.normalize()` | omission, documented | `Decimal("1.0").normalize()` is `Decimal("1E+0")` and `str()` gives `"1E+0"`. Normalizing would corrupt the authored form of the most common value in the corpus |
| 0.05 grid | **advisory only** — `off_grid_delta()`, surfaced as a review/lint hint | See below |

**The grid rule would reject the author's own corpus.** §5.5 reports 22 magnitudes "with one 0.125 outlier". That outlier is real: in `_ammerse-corpus-36-practices.json`, `wipe_the_board` has `environmental = 0.125`. A `delta % 0.05 == 0` constraint rejects it. This is the **same failure §5.6 documents for the mandatory-negative rule** (which would reject 14 of 36), and as far as I can tell nobody has named the second instance. Two of the three constraints proposed for this schema reject the calibration set. That is a pattern worth the operator's attention on its own: the corpus is the evidence *and* the thing the constraints would invalidate.

---

## Half-open set

**This is already solved in this repository and does not need inventing.** `src/doctrine/agent_profiles/profile.py:58-135` defines `Role` as a half-open value object: a `str` subclass, not a `StrEnum`, with class-level constants, a `_KNOWN` frozenset, `is_known()`, and a `__get_pydantic_core_schema__` hook that wires it into Pydantic v2 with a plain-str serializer. Its docstring states the exact rationale the design needs ("`StrEnum` seals the set of valid values at class definition time… teams would need to fork or monkey-patch the library"). It carries no `noqa` and there is no per-file ignore for it in `pyproject.toml`, so the `ARG`-selected lint config already tolerates that unused-parameter hook signature — meaning I can copy the pattern verbatim with confidence it passes the gate.

So `FoundationalValueName` above is that pattern, plus normalization (`strip().lower()`, matching `Role`'s `_normalize_role_value`).

The replaceable *set* is data, not code: built-in `src/doctrine/values/built-in/ammerse.value-set.yaml`, loaded by a `ValueSetRepository` subclassing `BaseDoctrineRepository` exactly as `TacticRepository` does (`built_in_dir` / `org_dirs` / `project_dir`, `_glob = "*.value-set.yaml"`). A consumer drops their own file in an org pack and it wins by the existing three-tier merge. Crucially I am **not** proposing `value_set` as a DRG `NodeKind` — that would immediately hit the three silent-kind-drop sites the handover documents (`extractor._KIND_MAP` has 11 entries and `.get()` → `None` → the edge vanishes). A repository-loaded data file sidesteps all three.

### The honest trade — four costs, stated plainly

**1. You lose static exhaustiveness, permanently.** `FoundationalValueName.MINIMAL` types as `FoundationalValueName`, not `Literal["minimal"]`. mypy will not check a `match` for completeness, will not catch `MINIMIAL` as a typo (it constructs happily), and cannot tell you that a dict keyed by value name is missing an axis. There is no partial recovery: a `Literal` union or `StrEnum` that is *also* extensible does not exist in the type system. This is the same trade `Role` already made and it was accepted.

**2. The real hazard is not typos — it is product code naming an axis at all.** Any line like `weights[FoundationalValueName.MINIMAL]` hardcodes the built-in basis, and for a consumer who replaced the set it does not crash, it silently returns a default and produces a plausible wrong ranking. Type safety was never going to catch that. So the mitigation is a construction gate, not a type: **product code may not reference the constants.** A `tests/architectural/` AST test that walks `src/` for `Attribute` access on `FoundationalValueName` and allow-lists only `src/doctrine/values/`, migrations, and `tests/` closes the class by construction (DIRECTIVE_043). ~40 lines, and it is the single highest-value test in this whole design. The constants then exist only for seed data, migrations, and fixtures.

**3. Validation moves from the type to a repository pass you can forget to call.** This is the genuine, irreducible cost, and it is worse than the lost exhaustiveness. `ValueDelta` cannot validate its own `name` — a half-open name has no access to the active set at field-validation time. So integrity lives in `ValueSet.assert_covers(...)`, called by the loader. If a future code path loads deltas without going through that loader, unknown axes flow in unchecked and a mismatched vector ranks against a partially-empty basis. The mitigation is to make the unchecked path unconstructible: the repository returns a wrapper type (e.g. `CheckedDeltaVector`) that can only be produced by the validating loader, so "did you validate?" is answered by the type of the thing you are holding rather than by discipline. That costs one small class and is worth it.

**4. Case-insensitive normalization means near-collisions.** Two org values differing only in case or surrounding whitespace collide into one. `ValueSet._reject_duplicate_names` makes that a load-time error with an explicit message rather than a silent overwrite, which is the right call, but a consumer who genuinely wants `Minimal` and `minimal` as distinct values cannot have them. Fine, and worth stating in the docs rather than discovering.

Net: the half-open set is cheap and precedented; the *type* is not where the safety comes from. Two tests carry it — the architectural no-constant-reference gate and the loader-side referential-integrity check.

---

## Coverage gate

The governing precedent, restated because it is the whole reason this section exists before the schema: three registers shipped as slots and went inert behind green tests — `Directive.severity` (13/13 uniform `warn`, 162 days, zero producers; note the doctrine-side `Directive` no longer has it, but `src/charter/schemas.py:154` **still carries `severity: str = "warn"`** today), `GovernanceConfig.enforcement` (`src/charter/schemas.py:150`, still `dict[str, str]` defaulting to `{}`), and the routing catalog (inert for ~20/21 verbs, then "repaired" by copying scores). Their tests proved Pydantic round-trips. Mine must not.

Shape borrowed from `tests/doctrine/test_task_class_map_catalog_contract.py`: derive the **universe** from one authority, the **covered set** from a second, assert set relations, and fail with the exact gap plus the remediation command.

The key design move: **do not assert coverage of all behavioural artefacts.** That is the all-artefact sweep the handover prices at 41–59 files. Instead assert coverage of a **declared, checked-in scope**, with exact equality in *both* directions. Partial population stops being a silent state and becomes a *declared* state whose declaration lives in the diff — adding an artefact to scope without a vector is red, and adding a vector outside scope is also red. That is the honest version of §8.1's mitigation, and unlike §8.1 it cannot drift silently.

`tests/doctrine/values/test_value_delta_coverage_contract.py`:

```python
"""Contract test: declared value-delta scope vs. actually-populated artefacts.

Precedent (docs/archive/plans/doctrine/manifesto-tier-verdict-and-handover.md): three
scoring registers shipped as schema-only slots and went inert behind green tests
-- `Directive.severity` (13/13 uniform "warn", 162 days, zero producers),
`GovernanceConfig.enforcement` ({}), and routing_policy/task_fit (inert for ~20
of 21 verbs, then "repaired" by copying one artifact's scores four times). Every
one of them had a passing test that proved a Pydantic round-trip.

This file asserts population, completeness, referential integrity, and
NON-DEGENERACY, and MUST land in the same commit as the `value_deltas` field.
If it is deferred, do not add the field.
"""

from __future__ import annotations

import statistics
from collections import Counter
from pathlib import Path

import pytest
import yaml

from doctrine.artifact_kinds import ArtifactKind, _NON_AUGMENTATION_ELIGIBLE_KINDS
from doctrine.values.models import ValueDelta, ValueSet
from tests.doctrine.conftest import DOCTRINE_SOURCE_ROOT, REPO_ROOT

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_SCOPE_FILE = DOCTRINE_SOURCE_ROOT / "values" / "delta-coverage-scope.yaml"
_REMEDIATION = (
    "Author the full vector on the artefact, or remove its URN from "
    "src/doctrine/values/delta-coverage-scope.yaml. Scope is exact in both "
    "directions by design -- partial population is a declared state, never a "
    "silent one."
)

#: Behavioural kinds only. Assets and templates are exempt per design §1, and
#: anti-patterns are never activated as live rules -- exactly the three members
#: of the canonical exclusion set, imported rather than re-declared (CC-4).
_BEHAVIOURAL_KINDS = frozenset(ArtifactKind) - _NON_AUGMENTATION_ELIGIBLE_KINDS
```

**A1 — the scope declaration is well-formed and behavioural.**

```python
def test_declared_scope_is_resolvable_and_behavioural() -> None:
    """Every scoped URN resolves to an existing artefact of a behavioural kind."""
    scope = _load_declared_scope()
    assert scope, "delta-coverage-scope.yaml declares no artefacts; delete the file and the field"

    unresolvable = sorted(urn for urn in scope if _artefact_path(urn) is None)
    assert not unresolvable, (
        f"scope declares URN(s) with no artefact file on disk: {unresolvable}. {_REMEDIATION}"
    )
    exempt = sorted(
        urn for urn in scope
        if ArtifactKind(urn.split(":", 1)[0]) not in _BEHAVIOURAL_KINDS
    )
    assert not exempt, (
        f"scope declares exempt kind(s) {exempt}; assets, templates, and "
        f"anti-patterns carry no value deltas (design §1)."
    )
```

**A2 — exact bidirectional coverage. The anti-`severity` assertion.**

```python
def test_scope_and_population_match_exactly() -> None:
    """Everything in scope carries a complete vector; nothing outside does."""
    scope = _load_declared_scope()
    populated = _urns_with_value_deltas()

    missing = sorted(scope - populated)
    undeclared = sorted(populated - scope)
    assert not missing and not undeclared, (
        f"value-delta population does not match declared scope.\n"
        f"  in scope but NOT populated ({len(missing)}): {missing}\n"
        f"  populated but NOT in scope ({len(undeclared)}): {undeclared}\n"
        f"{_REMEDIATION}"
    )
```

**A3 — referential integrity against the active set. No silent drop.**

```python
def test_every_delta_names_a_value_in_the_active_set() -> None:
    """A vector must score every value in the active set exactly once."""
    value_set = _active_value_set()
    for urn, deltas in _populated_vectors().items():
        value_set.assert_covers(deltas, subject=urn)  # raises with both-direction detail
```

**A4 — non-degeneracy. The anti-"copied scores" and anti-`TEMPLATE_PRACTICE` assertion.** This is the one the three dead registers would each have failed, and it is the one most likely to be omitted.

```python
def test_populated_vectors_are_not_degenerate() -> None:
    """Uniform, duplicated, or all-zero vectors are population theatre.

    `Directive.severity` was 13/13 uniform "warn" for 162 days. The routing
    catalog was "repaired" by copying one artifact's scores four times. And the
    upstream corpus itself contains the tell: `TEMPLATE_PRACTICE` and
    `quad_A_test_structure` are all-zero 7-axis vectors -- complete by schema,
    vacuous as data. Two of the 36 "complete" vectors in
    docs/plans/doctrine/_ammerse-corpus-36-practices.json are exactly this.
    """
    value_set = _active_value_set()
    vectors = _populated_vectors()
    if len(vectors) < 3:
        pytest.skip("non-degeneracy is not measurable below 3 populated artefacts")

    all_zero = sorted(u for u, ds in vectors.items() if all(d.delta == 0 for d in ds))
    assert not all_zero, (
        f"all-zero value vector(s) on {all_zero}: a vector that claims an "
        f"artefact changes nothing on any axis is an unfilled form, not data."
    )

    by_urn = {u: tuple(str(d.delta) for d in _in_axis_order(ds, value_set))
              for u, ds in vectors.items()}
    duplicated = sorted(v for v, n in Counter(by_urn.values()).items() if n > 1)
    assert not duplicated, (
        f"{len(duplicated)} value vector(s) are byte-identical across artefacts: "
        f"{[k for k, v in by_urn.items() if v in set(duplicated)]}. Copying one "
        f"artefact's scores to satisfy coverage is the documented failure mode "
        f"(routing_policy, 2026-07-04)."
    )

    for axis in value_set.names():
        column = [float(next(d.delta for d in vectors[u] if d.name == axis)) for u in vectors]
        assert statistics.pstdev(column) > 0.0, (
            f"axis {axis!s} has zero variance across {len(column)} populated "
            f"artefacts -- it carries no information and discriminates nothing. "
            f"Either it is not a value this project scores (remove it from the "
            f"value set) or the vectors were not authored independently."
        )
```

**A5 — rationale specificity.** No rationale string appears on two artefacts (the copy tell), none matches a placeholder pattern (`TODO`, `TBD`, `[`, `...`), and none is byte-identical to the value's own `description` (restating the definition is not a rationale).

**A6 — the producer is alive.** Without this, A1–A5 are all satisfiable by hand-authoring while Part 3's interview never writes a thing — the `severity` failure exactly.

```python
def test_charter_interview_producer_emits_a_non_default_creed() -> None:
    """The producer, run end to end, must actually populate the field.

    This is the assertion all three dead registers lacked: their tests proved a
    round-trip, so a field nothing ever wrote stayed green forever. Round-trip
    fidelity is NOT population. Assert the producer's output, not the model's.
    """
    creed = _run_creed_interview_producer(_scripted_answers_fixture())

    assert creed is not None, "creed interview produced no creed -- the field has no producer"
    weights = [w.weight for w in creed.weights]
    assert len(set(weights)) > 1, (
        f"producer emitted a uniform creed ({weights[0]} on every value). A "
        f"uniform weighting ranks nothing and is indistinguishable from the "
        f"13/13 uniform `warn` that made Directive.severity inert."
    )
    assert all(w.rationale.strip() for w in creed.weights), (
        "producer emitted weights with empty rationales; the rationale is the "
        "falsifiability mechanism, not decoration."
    )
```

Two notes on the gate itself. First, `_NON_AUGMENTATION_ELIGIBLE_KINDS` is documented in `src/doctrine/artifact_kinds.py` as "the **single** canonical exclusion set — downstream modules must import this rather than re-declaring their own", yet it is underscore-prefixed and absent from `__all__`. Importing it is correct and re-declaring it would be the violation, but the naming invites the wrong choice; worth a one-line rename in the same commit. Second, this gate guards the **built-in pack**. A consumer's charter varies, so their equivalent belongs in `spec-kitty doctor` (a `doctor values` check reporting scope-vs-population), not in pytest.

---

## Prototype slice

### Reaction to the proposed slice

The import, the side table, the one hand-authored creed, the ranking-only scope, and the no-new-kind constraint are all right and I would keep them unchanged. **The success signal is the problem: "eyeball whether the top-N for two different creeds actually differ" cannot fail.** Two distinct weight vectors dotted against 36 non-identical vectors will differ in top-N essentially always — that is a property of arithmetic, not evidence about the design. It is a green-for-the-wrong-reason experiment (DIRECTIVE_041), and it is the same category of error as the earlier squad's one-axis finding, which measured its own scoring bias rather than the corpus.

What actually needs answering is narrower and harder: **does creed-weighted ranking do anything a creed-independent quality score does not already do, and is the result stable under the wobble a real interview produces?** §5.4 makes the null hypothesis concrete: `solvable` has the highest mean (+0.607) and is never negative in 36 vectors, so it behaves as a near-constant "this is a good practice" signal. A creed-weighted ranking may simply be re-deriving global artefact quality with extra steps.

So I keep the slice and add three things: a **baseline arm**, a **pre-registration**, and a **perturbation-stability probe**. All three are cheap; the third can kill the design in an afternoon.

### WPs

**WP-P1 — corpus import + value set + pre-registration.** No dependency on P2/P3. ~3h implementer + operator time for the creeds.

| File | Role |
| --- | --- |
| `src/doctrine/values/corpus/ammerse-practices.snapshot.json` | 36 rows re-extracted **with rationales**, pinned commit SHA in a header block |
| `src/doctrine/values/corpus/README.md` | attribution, upstream ref, re-extraction command |
| `src/doctrine/values/models.py` | `FoundationalValueName`, `FoundationalValue`, `ValueSet`, `ValueDelta` only — **no connascence** |
| `src/doctrine/values/built-in/ammerse.value-set.yaml` | the 7 definitions, `attribution` populated |
| `tests/doctrine/values/test_ammerse_definition_parity.py` | the 7 definitions byte-identical across the tactic YAML, the architecture template, and the new value set, with the value set declared canonical |
| `tests/doctrine/values/fixtures/preregistration.yaml` | operator-authored: expected top-5 of 36 for creed A and creed B — **committed before any ranking code exists** |
| `tests/doctrine/values/fixtures/creed-a.yaml`, `creed-b.yaml` | two hand-authored creeds; **B differs from A only on `minimal`** |

Success: 36 rows parse to `list[ValueDelta]` with rationales, zero validation errors, `assert_covers` clean on all 36. The parity test is expected **red** on first run and that red is a deliverable — the handover already documents the drift (`templates/architecture/ammerse-analysis-template.md` has lost "impact on nature" from the Environmental definition). Do not fix by loosening the test.

Why B differs from A *only* on `minimal`: §5.4 identifies `minimal` as the sole genuinely discriminating axis (mean +0.022, stdev 0.391). If flipping the one axis that carries information barely moves the ranking, the mechanism is dead, and you learn it from one fixture.

**WP-P2 — the ranking function.** Dep: P1. ~4h.

| File | Role |
| --- | --- |
| `src/doctrine/values/ranking.py` | `rank_by_creed(creed, candidates, *, value_set) -> list[tuple[str, float]]` — pure, no I/O; normalizes weights internally (the one place that owns normalization); a missing axis is a hard error, never an implicit 0 |
| `src/doctrine/values/_metrics.py` | `kendall_tau_b`, `top_n`, `jaccard` — hand-rolled, ~40 lines (scipy is not a dependency and must not become one for a prototype) |
| `tests/doctrine/values/test_ranking.py` | unit: known-answer dot products, missing-axis raises, weight normalization is scale-invariant, empty-candidates is empty |

**WP-P3 — the experiment.** Dep: P2. ~3h.

| File | Role |
| --- | --- |
| `tests/doctrine/values/test_creed_ranking_experiment.py` | asserts the pre-registered thresholds below — a real pass/fail, not a print |
| `docs/plans/doctrine/creed-ranking-prototype-results.md` | numbers, verdict, and whichever threshold failed |

### Success signal — fixed before the run

1. **Creeds diverge from each other:** `kendall_tau_b(rank_A, rank_B) < 0.5`.
2. **Creeds diverge from the baseline:** baseline = unweighted mean delta (creed-independent quality). `tau_b(rank_A, baseline) < 0.8` and `tau_b(rank_B, baseline) < 0.8`. **If this fails, stop** — the creed is a decorative multiplier on a global quality score and the whole weighting apparatus buys nothing.
3. **Rankings match human expectation:** ≥3 of the 5 pre-registered picks in each arm's top-10, and the baseline hits *fewer* pre-registered picks than the matching creed arm. Without the second clause, clause 3 is satisfiable by a ranking that ignores the creed entirely.
4. **Stability under elicitation wobble — the kill switch:** perturb every creed weight by a uniform draw on ±0.10, 32 draws. In a majority of draws, top-10 membership must change by ≤2 of 10. The handover cites prior art measuring a declared value ordering moving revealed priorities by **0.145**, with rankings *inverting* between elicitation formats. If a 0.10 nudge churns more than 2 of 10, then no interview can elicit weights precise enough to produce a stable ranking, and every downstream part of the design is unbuildable regardless of everything else. ~20 lines, and it is the highest-information measurement available.

**~1.5 days implementer time**, plus operator time to author two creeds and the pre-registration. Zero production wiring: no doctrine kind, no DRG node, no field on any shipped model, no `charter.yaml` key, no CLI command, no migration, no exposure to the three silent-kind-drop sites.

**One correction that lands in WP-P1 and affects §5.3.** Two of the 36 "complete" vectors are all-zero: `TEMPLATE_PRACTICE` (which is literally the authoring template) and `quad_A_test_structure`. The PCA in §5.3 and the per-axis statistics in §5.4 were computed over n=36 including those two rows. Effective n is **34**, and the rank-5 conclusion — the finding that refutes the earlier one-axis verdict, and therefore the single most load-bearing measurement in the design document — should be re-run on the 34. That is a five-minute check and it should happen before anyone builds on §5.3. It may well hold; it is currently unverified.

---

## Import path

**Vendored snapshot, pinned by commit SHA. Not fetch-at-build, not manual port.**

- **Fetch-at-build: rejected outright.** Network access during build or test is a flake source, and the repo runs a `clean-install-verification` CI job plus architectural tests on `pyproject.toml` shape (`tests/architectural/test_pyproject_shape.py`) precisely to keep the build hermetic. A build-time fetch also puts a third party's `develop` branch in the critical path of every install.
- **Manual port: rejected.** 36 × 7 = 252 numbers plus 252 rationale sentences, transcribed by hand, with no way to tell a typo from an authored value.
- **Vendored snapshot: chosen.** `src/doctrine/values/corpus/ammerse-practices.snapshot.json`. Packaging is already handled — `pyproject.toml:159-166` globs `src/doctrine/**/*.json` and `**/*.yaml` into `[tool.hatch.build.targets.wheel].artifacts`, so the file ships with no packaging change. `src/charter/corpus/*.corpus.yaml` is the existing precedent for vendored data under `src/`.

The snapshot header must carry: upstream repo (`sddevelopment-be/penguin-pragmatic-patterns`), ref (`develop`), **resolved commit SHA**, extraction date, extractor script path, row count, and an `attribution` string.

**Do not reuse `docs/plans/doctrine/_ammerse-corpus-36-practices.json` as the corpus.** I read it: it carries `id` plus a bare `v[7]` float array and **no rationales at all**. It is fine for the numeric measurements it was made for, and unfit for this prototype — the design's entire falsifiability claim rests on rationale co-location (§4: the rationale fields are "pivotal"), and §5.1 establishes 1:1 pairing as the upstream invariant. Re-extract with rationales. Also note it stores deltas as JSON floats, which is the representation this design should not adopt; the snapshot should store them as the authored strings.

**Drift detection — two different drifts, two different mechanisms:**

1. **Upstream drift** (the snapshot vs. the source repo). A re-extraction script plus an **opt-in** test that re-fetches and diffs, marked so it is excluded from the default suite exactly as the `distribution` / `live_adapter` markers already are (see the mutmut deselection list at `pyproject.toml:394`). Never in `fast`. The snapshot's `source_commit` is what makes the diff meaningful.
2. **In-repo drift** (already happened, and this is the one that matters more). The AMMERSE definitions exist twice today — `src/doctrine/tactics/built-in/analysis/ammerse-impact-analysis.tactic.yaml` and `src/doctrine/templates/architecture/ammerse-analysis-template.md` — and the template's Environmental definition has already lost "impact on nature". **Adding `ammerse.value-set.yaml` creates a third copy.** The parity test in WP-P1 must land in the same commit as the value set, with the value set declared canonical and the other two required to match it. Without that test, this design's first commit ships a known-drifted definition triple, which is the DIRECTIVE_044 violation the handover already recommends filing as debt.

Attribution and the trademark question ride along in `src/doctrine/values/corpus/README.md` and the required `ValueSet.attribution` field, but the licensing call itself is the operator's open human decision and is not resolved by any of this.

---

## CONCESSION

Where I am guessing, and what I did not read:

- **Nothing was executed.** Read-only pass, per the hard safety constraint. No `pytest`, no `mypy`, no `ruff` on any code above. The models are conventional *by inspection against files I read* — they are not gate-verified. Expect one or two ruff/mypy nits on first run.
- **The single most load-bearing unverified claim** is ruamel's representation of a numeric-looking `str`. My `Decimal`-over-`float` decision rests on `emit_yaml`'s `model_dump(mode="json")` producing `"0.9"` and ruamel emitting it quoted (byte-stable), where a `float` emits unquoted and loses the authored form permanently. I read `emit_yaml` (`src/charter/schemas.py:363-390`) and its `preserve_quotes = True`, but I did not execute the round-trip. Verify with one line before committing to the decision: `YAML().dump({"delta": "0.9"}, sys.stdout)` and confirm the output is `delta: '0.9'`. If ruamel emits it bare, the argument weakens to the ordinary Decimal-vs-float case and the conclusion is the same but less forceful.
- **The `_reject_duplicate_names` validator** in `ValueSet` uses a `seen.add()` side effect inside a comprehension with a `type: ignore[func-returns-value]`. That is too clever for this codebase's standards and would rightly be flagged in review — rewrite it as a plain loop. I left it visible rather than quietly fixing it because it is exactly the kind of thing a reviewer should catch.
- **`Field(max_digits=..., decimal_places=...)` semantics on `Decimal` in Pydantic 2.13.4** are asserted from knowledge of Pydantic v2, not verified here. I checked that `Decimal("0.125")` and `Decimal("-1.000")` fit `max_digits=4, decimal_places=3` by reasoning over `as_tuple()`, not by running it. Also unverified: whether `allow_inf_nan` is accepted on a `Decimal` field in this exact version (it is on `float`; I am fairly confident but not certain for `Decimal`, which is why the explicit `is_finite()` after-validator is there as the real guard).
- **Files I did not read**, so claims about them are inference: `src/charter/interview.py` (so *where* the Part-3 producer writes, and therefore the concrete shape of `_run_creed_interview_producer` in A6, is inferred from field names and the handover), `src/charter/context.py`, `src/charter/consistency_check.py`, `src/doctrine/drg/org_pack_loader.py`, `src/doctrine/base.py` (so my `ValueSetRepository`-by-analogy-with-`TacticRepository` claim rests on `TacticRepository`'s first 70 lines, not on `BaseDoctrineRepository` itself), and `src/doctrine/drg/migration/extractor.py` (I take the handover's `_KIND_MAP`-has-11-entries claim on trust).
- **Whether an org pack can actually ship a `*.value-set.yaml`** is the biggest unverified structural claim. I assert it works by analogy with tactic/glossary-pack loading, but the org-pack overlay path may be kind-gated in ways that reject an unregistered artefact suffix. If it is gated, the "replaceable by consumers" property — the whole basis of the open-closed answer — needs the loader touched, and that is a real cost I have not priced. **Verify before committing to the design**, not during implementation.
- **The three dead-register facts** (162 days, 13/13 uniform, ~20/21 verbs, the copied-scores repair) are taken from the handover document. I independently confirmed two of the three slots still exist as described in `src/charter/schemas.py` (`severity: str = "warn"` at line 154, `enforcement: dict[str, str]` at line 150) and that the doctrine-side `Directive` no longer carries `severity`. I did not run `git log -S` to confirm the durations or the never-populated claim.
- **PCA / Kendall τ thresholds** (0.5, 0.8, ≤2-of-10 churn) are my judgement calls, not derived from anything. They are chosen to be pre-registered and falsifiable rather than to be right; the operator should overrule any of them *before* the run, never after.
- I did **not** independently re-derive §5.3's PCA or §5.4's statistics. I did verify from the JSON that the 0.125 outlier is `wipe_the_board.environmental` and that `TEMPLATE_PRACTICE` and `quad_A_test_structure` are all-zero rows — those two findings are mine and checked.

---

## VERDICT

**Buildable cleanly, and more cleanly than I expected — but not in the order the design implies, and three things must change first.** The type design has no novel problems: `Role` in `src/doctrine/agent_profiles/profile.py` is a proven, lint-clean, Pydantic-wired half-open value object with the exact rationale this design needs, so Part 1's "half-open enum" is a copy rather than an invention; the corpus's authored `{name, delta, rationale}` shape maps to a frozen `extra="forbid"` model with no translation layer; `Decimal`-with-string-authoring resolves the representation question in a way that actively protects the repo's byte-stable-emission invariant instead of fighting it; and the prototype slice needs no doctrine kind, no DRG node, no field on any shipped artefact, and no migration, which means it touches none of the three silent-kind-drop sites and cannot decay because there is nothing yet to decay. What must change: **(1)** `ValueConnascenceMatrix` must not be in the first commit — §9 establishes the first-order matrix is not in this repository, both existing copies defer to an external URL, and it is the trademarked party's uncalibrated judgement, which makes it precisely a schema slot with no available producer; the operator's own design therefore contains a fourth instance of the 3-for-3 pattern it was written to avoid, and the schema should be defined and parked, not shipped. **(2)** The definition-parity test must land in the same commit as `ammerse.value-set.yaml`, or that file becomes drifted copy number three of a definition set that has already silently lost "impact on nature" once. **(3)** Two of the three constraints proposed for this schema reject the author's own calibration set — the mandatory-negative rule rejects 14 of 36 (§5.6, known) and a 0.05-resolution rule rejects `wipe_the_board`'s authored 0.125 (new) — so both must be advisory lints with the corpus as their justification, and someone should re-run §5.3's PCA on the 34 non-vacuous rows before anything is built on the rank-5 finding. Sequenced that way, the honest first commit is WP-P1 through WP-P3: import the corpus, author two creeds that differ only on the one axis §5.4 shows carries information, and run the perturbation-stability probe. That probe is roughly a day of work and can falsify the entire design before a single field lands on a single artefact — which makes it worth doing whether or not `#2538` ever runs.agentId: a78d970aa1950f74d (use SendMessage with to: 'a78d970aa1950f74d', summary: '<5-10 word recap>' to continue this agent)
<usage>subagent_tokens: 171977
tool_uses: 28
duration_ms: 590901</usage>
