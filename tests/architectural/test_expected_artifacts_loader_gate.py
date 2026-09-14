"""Non-vacuous arch-gate (FR-011, DIRECTIVE_043): bare ``ExpectedArtifactManifest``
construction/validation is forbidden outside the canonical loader.

Mission ``expected-artifacts-loader-unification-01M1C9VQ`` (#3770/#3412, epic
#3410) relocated the org->built-in-precedence + ``model_validate`` + error-wrap
logic for ``ExpectedArtifactManifest`` into ONE cached authority
(``charter/activation/manifest_loader.py``) and deleted the orphan
``ExpectedArtifactManifest.from_yaml_file`` (which constructed via
``cls(**data)``, invisible to a ``model_validate``-only gate). This gate keeps
both defect classes dead by construction:

- a bare ``ExpectedArtifactManifest.model_validate(`` call outside the
  authority would regrow one of the three retired mirror loaders (WP02/WP03/
  WP04 all deleted their own copy of this call).
- a bare ``ExpectedArtifactManifest(`` construction call outside the
  authority/model/tests would reopen the ``from_yaml_file`` class of bug
  (``cls(**data)`` bypasses ``model_validate`` entirely).

**AST, not regex (this is load-bearing, not stylistic).** A regex for
``ExpectedArtifactManifest(`` would false-match the class *definition* line at
``src/charter/offering/missions/expected_artifact_manifest.py:86``
(``class ExpectedArtifactManifest(BaseModel):``) -- regex has no notion of
"this parenthesis is a base-class list, not a call". This module's detector
walks the AST and only ever visits ``ast.Call`` nodes; a ``class Foo(Bar):``
statement parses to an ``ast.ClassDef`` with ``bases=[ast.Name(id="Bar")]`` --
no ``ast.Call`` node is produced for it at all, so the model's own class
statement is structurally invisible to this detector without needing a
special-cased path exemption. ``test_model_class_definition_is_not_flagged``
below is the committed proof.

**Allowlist (the only two permitted modules, T018/contracts/arch-gate.md):**

- ``charter/activation/manifest_loader.py`` -- the canonical loader. Contains
  exactly 2 ``ExpectedArtifactManifest.model_validate(`` calls (the org-tier
  and built-in-tier branches inside ``load_manifest``/
  ``_validate_and_cache_org_manifest``) and 0 bare-construction calls.
- ``charter/offering/missions/expected_artifact_manifest.py`` -- the model's
  own definition module, allowlisted defensively for any future internal
  construction; today it contains 0 matching calls (only the ``ClassDef``
  the AST approach above already ignores).

Non-vacuity (charter DIRECTIVE_043), one leg per test below:

1. **Concrete floor** -- ``test_allowlist_is_exactly_the_expected_two_modules``
   and ``test_allowlist_helper_contains_the_two_expected_calls`` assert
   equality/exact counts, never ">= 0".
2. **Self-mutation** -- ``test_forbidden_model_validate_call_is_flagged_via_self_mutation``
   and ``test_forbidden_bare_construction_call_is_flagged_via_self_mutation``
   plant a real forbidden call into an unexempted ``tmp_path`` file and prove
   the SAME detector used by the gate flags it.
3. **Refactor-stable** -- keyed by module path + AST call shape, never a line
   number; ``test_scanned_file_floor_is_met`` guards against the detector
   silently scanning zero files.
4. **Shrink-only** -- ``test_allowlist_is_exactly_the_expected_two_modules``
   pins the allowlist to a frozen count of 2; widening it requires editing
   this test file's own constant, which is itself the code-review signal.

**T021 grep proof (SC-001: one load *module*, not one call).** Two
independent claims, both mechanically re-checked below
(``test_single_module_owns_all_model_validate_calls``,
``test_from_yaml_file_is_fully_retired``) and reproducible by hand::

    $ grep -rn "ExpectedArtifactManifest\\.model_validate(\\|ExpectedArtifactManifest(" src/ \\
        | grep -v "class ExpectedArtifactManifest"
    src/charter/activation/manifest_loader.py:282:  ...model_validate(config.parsed)
    src/charter/activation/manifest_loader.py:312:  ...model_validate(org_parsed)

    $ grep -rn "from_yaml_file" src/
    (empty)

The first command's two hits are BOTH inside the one allowlisted module (the
org branch and the built-in branch of the same authority) -- the SC-001 claim
is "one module", not "one call"; conflating the two would make the proof
either fail on legitimate authority-internal duplication or miss a real
second mirror. The second command is WP01/T003's deletion proof for the
orphan ``from_yaml_file`` (FR-013): ``cls(**data)`` construction is gone from
production code entirely, not merely routed.

**Sequencing (contracts/arch-gate.md):** this gate is only valid to enable
after WP01 (relocates the canonical calls into the allowlisted module),
WP02/WP03/WP04 (delete the three mirror ``model_validate`` calls), and WP01's
FR-013 (deletes ``from_yaml_file``) have all landed -- confirmed above by the
grep proof finding exactly the 2 expected calls in exactly 1 module.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import ast

import pytest

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

#: The class this gate polices. Kept as a single constant so the two AST
#: match branches (model_validate receiver / bare-construction callee) key
#: off one literal, never a duplicated string.
_TARGET_CLASS = "ExpectedArtifactManifest"

#: The ONLY two modules (repo-relative, POSIX) permitted to call
#: ``ExpectedArtifactManifest.model_validate(`` or construct
#: ``ExpectedArtifactManifest(`` directly. Frozen: DIRECTIVE_043's
#: shrink-only rule means this set may only shrink in a future mission
#: (e.g. if the authority itself is further split) -- never silently grow.
#: Growing it is a one-line diff to THIS constant, which is the intended
#: code-review checkpoint.
ALLOWLIST_MODULES: frozenset[str] = frozenset(
    {
        "charter/activation/manifest_loader.py",
        "charter/offering/missions/expected_artifact_manifest.py",
    }
)

#: NOTE-3 (mirrors the clock-gate precedent, tests/architectural/_clock_gate_scan.py):
#: a detector silently scanning zero files must go red, not pass vacuously.
MIN_SCANNED_FILES = 500


class _Violation(NamedTuple):
    """One forbidden call site: 1-indexed source line + the matched call shape."""

    line: int
    kind: str  # "model_validate" | "construction"


class _ManifestConstructionVisitor(ast.NodeVisitor):
    """Flags ``<expr matching ExpectedArtifactManifest>.model_validate(...)``
    and bare ``<expr matching ExpectedArtifactManifest>(...)`` calls.

    "Matching" means: the literal name ``ExpectedArtifactManifest`` (always
    recognized, since it is never rebound to something else's identity by
    that name), OR a local alias introduced by
    ``from <anywhere> import ExpectedArtifactManifest as <alias>`` in the
    same file. A qualified attribute chain (``module.ExpectedArtifactManifest``,
    ``module.ExpectedArtifactManifest.model_validate``) is matched via its
    right-most attribute name, so an aliased module import
    (``import charter.offering.missions.expected_artifact_manifest as em``)
    does not evade detection either -- only the FINAL path segment has to
    read ``ExpectedArtifactManifest`` (or a same-file import alias of it).
    """

    def __init__(self) -> None:
        self.violations: list[_Violation] = []
        self._aliases: set[str] = {_TARGET_CLASS}

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == _TARGET_CLASS:
                self._aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def _terminal_name(self, node: ast.expr) -> str | None:
        """The final identifier of a (possibly chained) attribute/name expression."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "model_validate":
            receiver = self._terminal_name(func.value)
            if receiver in self._aliases:
                self.violations.append(_Violation(node.lineno, "model_validate"))
        elif isinstance(func, ast.Name) and func.id in self._aliases:
            self.violations.append(_Violation(node.lineno, "construction"))
        elif isinstance(func, ast.Attribute) and func.attr == _TARGET_CLASS:
            # Qualified bare construction, e.g. `module.ExpectedArtifactManifest(...)`.
            self.violations.append(_Violation(node.lineno, "construction"))
        self.generic_visit(node)


def _relpath(path: Path) -> str:
    """``src/``-relative POSIX path -- matches ``ALLOWLIST_MODULES``' key format."""
    return path.resolve().relative_to(SRC_ROOT).as_posix()


def find_violations_in_source(source: str) -> list[_Violation]:
    """The gate's real detector, exposed for both file scanning and self-mutation tests."""
    tree = ast.parse(source)
    visitor = _ManifestConstructionVisitor()
    visitor.visit(tree)
    return sorted(visitor.violations, key=lambda v: v.line)


def find_violations_in_file(path: Path) -> list[_Violation]:
    return find_violations_in_source(path.read_text(encoding="utf-8"))


def iter_src_python_files() -> list[Path]:
    """Every ``.py`` file under ``src/``, ``__pycache__`` excluded."""
    return sorted(p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def collect_violations_by_module() -> dict[str, list[_Violation]]:
    """``{repo-relative module path: [violations]}`` for every ``src/`` file with a hit."""
    result: dict[str, list[_Violation]] = {}
    for path in iter_src_python_files():
        violations = find_violations_in_file(path)
        if violations:
            result[_relpath(path)] = violations
    return result


# ---------------------------------------------------------------------------
# Non-vacuity leg 3: refactor-stable scan scope, guarded against silently
# scanning zero files.
# ---------------------------------------------------------------------------


def test_scanned_file_floor_is_met() -> None:
    scanned = iter_src_python_files()

    assert len(scanned) > MIN_SCANNED_FILES, f"only {len(scanned)} files scanned under {SRC_ROOT} -- the bare-construction gate would otherwise pass vacuously."


# ---------------------------------------------------------------------------
# The gate itself.
# ---------------------------------------------------------------------------


def test_no_forbidden_construction_outside_allowlist() -> None:
    """FR-011: no bare ``model_validate(``/``ExpectedArtifactManifest(`` outside the 2 allowlisted modules."""
    by_module = collect_violations_by_module()

    offenders = {module: violations for module, violations in by_module.items() if module not in ALLOWLIST_MODULES}

    assert offenders == {}, (
        "Bare `ExpectedArtifactManifest.model_validate(`/`ExpectedArtifactManifest(` "
        "construction is forbidden outside the canonical loader "
        f"({sorted(ALLOWLIST_MODULES)}). Route through "
        "`charter.activation.manifest_loader.load_manifest` instead. Offenders:\n"
        + "\n".join(f"  {module}:{violation.line} ({violation.kind})" for module, violations in sorted(offenders.items()) for violation in violations)
    )


# ---------------------------------------------------------------------------
# Non-vacuity leg 1 (concrete floor) + leg 4 (shrink-only).
# ---------------------------------------------------------------------------


def test_allowlist_is_exactly_the_expected_two_modules() -> None:
    """Concrete floor + shrink-only: the allowlist is an equality check, pinned at exactly 2 entries.

    Widening this set requires editing the ``ALLOWLIST_MODULES`` constant
    above -- a diff to THIS file -- which is DIRECTIVE_043's intended
    code-review checkpoint for "never silently grow".
    """
    # NOTE: no separate `len(ALLOWLIST_MODULES) == 2` assertion -- the frozenset
    # equality above already pins exact membership (and therefore exact size);
    # a bare-count assertion here would only duplicate that stronger contract
    # A bare-count assertion is strictly weaker than the set equality above:
    # adding, removing or renaming a member should force a *content* edit, not
    # silently pass at an unchanged count. (The `test_golden_count_ban.py` gate
    # that used to police this was retired by #4315; the reasoning stands on its
    # own and does not depend on it.)
    assert (
        frozenset(
            {
                "charter/activation/manifest_loader.py",
                "charter/offering/missions/expected_artifact_manifest.py",
            }
        )
        == ALLOWLIST_MODULES
    )


def test_allowlist_helper_contains_the_two_expected_calls() -> None:
    """Concrete floor: the canonical loader actually contains its 2 expected calls.

    Guards against the gate passing vacuously because its target moved or
    disappeared out from under it (e.g. a future refactor that deletes
    ``load_manifest`` without updating this gate).
    """
    loader = SRC_ROOT / "charter" / "activation" / "manifest_loader.py"
    assert loader.is_file(), "the canonical loader module is missing"

    violations = find_violations_in_file(loader)

    assert len(violations) == 2, f"expected exactly 2 calls in the canonical loader, found {violations}"
    assert {v.kind for v in violations} == {"model_validate"}, (
        f"the canonical loader's own calls are expected to be `model_validate(` -- got kinds {sorted({v.kind for v in violations})}"
    )


def test_model_module_carries_no_matching_calls_today() -> None:
    """Concrete floor: the model's own module is allowlisted defensively but has 0 hits today.

    If a future change adds internal construction inside the model module
    itself, this assertion (not the gate) is the one that goes red first --
    a deliberate, narrow signal distinct from the gate's "outside the
    allowlist" check.
    """
    model_module = SRC_ROOT / "charter" / "offering" / "missions" / "expected_artifact_manifest.py"
    assert model_module.is_file(), "the model's own definition module is missing"

    assert find_violations_in_file(model_module) == []


# ---------------------------------------------------------------------------
# Non-vacuity leg 2: self-mutation -- prove the detector is not theater.
# ---------------------------------------------------------------------------


def test_forbidden_model_validate_call_is_flagged_via_self_mutation(tmp_path: Path) -> None:
    """A planted `ExpectedArtifactManifest.model_validate(` in an unexempted file IS caught."""
    module = tmp_path / "offender.py"
    module.write_text(
        "from charter.offering.missions.expected_artifact_manifest import ExpectedArtifactManifest\n\n"
        "def offending_loader(raw):\n"
        "    return ExpectedArtifactManifest.model_validate(raw)\n",
        encoding="utf-8",
    )

    violations = find_violations_in_file(module)

    assert [v.kind for v in violations] == ["model_validate"]
    assert violations[0].line == 4


def test_forbidden_bare_construction_call_is_flagged_via_self_mutation(tmp_path: Path) -> None:
    """A planted bare `ExpectedArtifactManifest(` construction in an unexempted file IS caught.

    This is the ``from_yaml_file``/``cls(**data)`` class of bypass (D6):
    a ``model_validate``-only gate would miss this shape entirely.
    """
    module = tmp_path / "offender.py"
    module.write_text(
        "from charter.offering.missions.expected_artifact_manifest import ExpectedArtifactManifest\n\n"
        "def offending_constructor(**data):\n"
        "    return ExpectedArtifactManifest(**data)\n",
        encoding="utf-8",
    )

    violations = find_violations_in_file(module)

    assert [v.kind for v in violations] == ["construction"]
    assert violations[0].line == 4


def test_aliased_import_construction_is_flagged_via_self_mutation(tmp_path: Path) -> None:
    """`from ... import ExpectedArtifactManifest as EAM; EAM(...)` is caught too (alias-of-name form)."""
    module = tmp_path / "offender.py"
    module.write_text(
        "from charter.offering.missions.expected_artifact_manifest import ExpectedArtifactManifest as EAM\n\ndef offending(**data):\n    return EAM(**data)\n",
        encoding="utf-8",
    )

    violations = find_violations_in_file(module)

    assert [v.kind for v in violations] == ["construction"]


def test_qualified_module_attribute_construction_is_flagged(tmp_path: Path) -> None:
    """`module.ExpectedArtifactManifest(...)` (qualified attribute form) is caught (no import-tracking needed)."""
    module = tmp_path / "offender.py"
    module.write_text(
        "import charter.offering.missions.expected_artifact_manifest as em\n\ndef offending(**data):\n    return em.ExpectedArtifactManifest(**data)\n",
        encoding="utf-8",
    )

    violations = find_violations_in_file(module)

    assert [v.kind for v in violations] == ["construction"]


# ---------------------------------------------------------------------------
# Negative controls -- the detector must NOT over-fire.
# ---------------------------------------------------------------------------


def test_model_class_definition_is_not_flagged(tmp_path: Path) -> None:
    """The class statement itself (`class ExpectedArtifactManifest(BaseModel):`) is not a Call -- no false positive.

    This is the exact reason the contract mandates AST over regex: a regex
    for `ExpectedArtifactManifest(` matches this line's substring, but
    `ast.ClassDef` never produces an `ast.Call` node for its base-class
    list, so the real detector correctly ignores it with zero special-case
    logic.
    """
    module = tmp_path / "model.py"
    module.write_text(
        "from pydantic import BaseModel\n\n\nclass ExpectedArtifactManifest(BaseModel):\n    pass\n",
        encoding="utf-8",
    )

    assert find_violations_in_file(module) == []


def test_unrelated_model_validate_call_is_not_flagged(tmp_path: Path) -> None:
    """`SomeOtherModel.model_validate(...)` is not flagged -- the detector binds to the specific class name."""
    module = tmp_path / "offender.py"
    module.write_text(
        "from pydantic import BaseModel\n\n\nclass SomeOtherModel(BaseModel):\n    pass\n\n\nSomeOtherModel.model_validate({})\n",
        encoding="utf-8",
    )

    assert find_violations_in_file(module) == []


def test_locally_shadowed_bare_name_is_still_flagged_conservatively(tmp_path: Path) -> None:
    """A same-named local function (no import of the real model) is STILL flagged -- deliberately conservative.

    The detector does no full symbol resolution (it is a lightweight
    per-file AST walk, matching the house style of the other call-ban
    gates in this directory); it matches the bare name
    ``ExpectedArtifactManifest`` unconditionally, whether or not the file
    actually imports the real model. This means a hypothetical unrelated
    local function sharing the exact class name would also be flagged
    (a false positive in the adversarial-shadow case). That direction is
    the SAFE one for an arch-gate: erring toward over-flagging a
    vanishingly unlikely name collision is preferable to a detector that
    can be evaded by NOT importing the real class -- which would defeat
    the whole point of a construction ban.
    """
    module = tmp_path / "offender.py"
    module.write_text(
        "def ExpectedArtifactManifest(*args, **kwargs):\n    raise NotImplementedError\n\n\nExpectedArtifactManifest()\n",
        encoding="utf-8",
    )

    assert find_violations_in_file(module) == [_Violation(5, "construction")]


# ---------------------------------------------------------------------------
# T021 grep proof, mechanically re-checked (not just documented in the docstring).
# ---------------------------------------------------------------------------


def test_single_module_owns_all_model_validate_calls() -> None:
    """SC-001: exactly ONE production module contains any matching call -- the proof is "one module", not "one call".

    The allowlisted loader legitimately contains 2 `model_validate(` calls
    (org branch + built-in branch); conflating "one module" with "one call"
    would make this assertion fail on the authority's own legitimate
    duplication.
    """
    by_module = collect_violations_by_module()

    assert set(by_module) == {"charter/activation/manifest_loader.py"}, f"expected exactly one module with matching calls, found: {sorted(by_module)}"


def test_from_yaml_file_is_fully_retired() -> None:
    """FR-013/WP01-T003: `ExpectedArtifactManifest.from_yaml_file` (the `cls(**data)` orphan) is gone from src/."""
    hits = [_relpath(path) for path in iter_src_python_files() if "from_yaml_file" in path.read_text(encoding="utf-8")]

    assert hits == [], f"`from_yaml_file` must be fully deleted from src/ (FR-013); still referenced in: {hits}"
