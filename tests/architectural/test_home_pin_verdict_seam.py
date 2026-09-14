"""The VERDICT seam's own guard: a second copy of the comparison must be a red (WP04).

Why this module exists, stated plainly
--------------------------------------
WP04 extracted ``_home_pin_verdict.py`` so the census/hash/tombstone comparison would have one
home. Extraction alone **moved the location and not the enforcement**: WP05 could still hand-roll
``discovered == census | exempt`` in three lines, never import the seam, and every other test in
this package would stay green. ``_home_pin_scan.py`` has ``test_home_pin_seam_no_second_copy.py``
to make its import the only option; this is the same mechanism for the verdict, one level up.

``_sole_door_scan.py:13-27`` records the failure both guards exist to prevent as a **live
incident**: Gates 4 and 5 each rolled an independent, drifting copy of the same primitives, Gate 4's
copy having already lost Gate 1's docstring rationale. **Prose did not prevent it there.**

The predicate, and why this one
--------------------------------
A module is doing **verdict work** when it imports the scanner **and** shows at least one of three
signals. The scanner-import gate is what makes the predicate tractable, and the denominator is
published because it is what makes that legible: measured over ``src/`` u ``tests/``, the raw
signals fire in **103** modules — ``hashlib.sha256`` is ordinary code — and gating on
``_home_pin_scan`` reduces that to **4**, all of them genuinely R1a artefacts, with **0** offenders.
The gate is not a convenience; without it this guard would be noise and would be deleted within a
month.

1. **It reads a census or baseline ARTEFACT.** A path literal matching ``census``/``baseline`` and
   ``.yaml``, or a reference to ``CENSUS_PATH`` / ``BASELINE_PATH``. This is the strongest signal
   and the one that catches WP05's actual job: the real-tree assertion **must** read the checked-in
   census, so a hand-rolled version cannot avoid touching the artefact.
2. **It hand-rolls a key-set hash.** Any ``sha256``/``sha1``/``md5``/``blake2b``/``sha512`` call.
   ``_home_pin_scan._sha256_of`` is the single checksum site in the behaviour class and
   :func:`~tests.architectural._home_pin_verdict.hash_of_key_set` is the single recomputation; a
   third is a re-implementation by definition.
3. **It relates sets named like the verdict's operands** — ``==`` **or containment** (``<=``,
   ``<``, ``>=``, ``>``, ``issubset``, ``issuperset``) over operands mentioning at least **two** of
   ``census`` / ``baseline`` / ``discovered`` / ``exempt``. Two rather than one, because one word
   alone fires on ordinary prose-shaped identifiers. This catches the cheapest copy: a comparison
   in a helper that takes the census text as a parameter and so never touches a path literal.

   **Containment is in this list because leaving it out was a real hole, not a hypothetical one.**
   Shipped with ``Eq`` alone, this guard did not see ``discovered <= census | exempt`` — a
   **subset-only ratchet**, which is the failure ``spec.md`` §0.4 spends a page refusing and the
   one this package ships ``test_the_comparison_is_set_equality_and_not_containment`` to catch. It
   named three of the four operand words and escaped on one character.

**What this guard CAN see**: the three shapes above, in any module importing the scanner. That
covers every copy a maintainer would plausibly write, because a copy has to obtain the census from
somewhere and compare something to it.

**What this guard CANNOT see, stated as an honest limit rather than discovered later**:

* a copy written with **no recognisable naming and no artefact read** — ``a == b | c`` over
  locals named without any of the four words, fed from text passed in from elsewhere. Closing that
  needs a similarity oracle, not an import graph, which is the same boundary
  ``test_home_pin_seam_no_second_copy.py:42`` records for the scanner;
* a copy in a module that **does not import the scanner** — it would have to re-implement
  ``discover`` too, which is precisely what WP02's guard is for, so the pair covers it between
  them but neither does alone;
* a copy that **imports the seam and then ignores it**, calling ``evaluate`` and asserting
  something else entirely. Import is necessary here, never sufficient;
* an artefact read whose **path is ASSEMBLED rather than written as a contiguous literal** —
  ``ROOT / "census" / "spec_kitty_home_pin_R1a.yaml"`` is invisible to a matcher looking for one
  path-shaped string, and if its operands are also named outside the vocabulary (``rows``,
  ``document``) nothing else fires either. Measured: that shape passes this guard today. It is the
  same boundary T020 records for SC-002b — *"a constant assembled at runtime rather than written as
  a literal"* — and closing it needs value resolution, which is
  ``_home_pin_scan.resolve_value``'s job over env-var values, not a path oracle this guard owns.

Exemptions are BY NAME and each carries its reason
----------------------------------------------------
A broad pattern would let the next copy in. :data:`EXEMPT` is a mapping, every entry justified, and
:func:`test_every_exemption_is_still_needed` asserts each one **still fires** — so an exemption that
has stopped being necessary is removed rather than accumulating. ``_home_pin_gate.py`` is
deliberately **absent**: it is measured, it does not trip the predicate, and pre-emptively exempting
it would be exactly the broad-pattern habit this list exists to avoid.

**The list is pinned twice, and the second pin is the load-bearing one.**
:data:`FROZEN_EXEMPT_KEYS` pins the key set by content *in this module*; :data:`EXEMPT_PIN_PATH`
pins its ``sha256`` in a **generated file beside it**. The first alone was a second lock mounted on
the same door — ten lines from the list, with a failure message naming the adjacent line to edit.
The second is what the mission already requires of ``E``, the structurally identical set: fixed by
type **plus a hash held outside the module that declares it**. Forgiving yourself costs two files,
one of them generated, and lands in the diff as a regenerated artefact.
"""

from __future__ import annotations

import argparse
import ast
import re
import textwrap
from pathlib import Path

import pytest
import yaml

from tests.architectural import _home_pin_scan as scan
from tests.architectural import _home_pin_verdict as verdict

pytestmark = pytest.mark.architectural

#: The real walk root. Verdict work is test-tier by construction — nothing under ``src/`` imports
#: the scanner — so the walk is stated over ``tests/`` and that scope is a deliberate limit.
TESTS_ROOT = Path("tests")

SEAM_MODULE = "_home_pin_scan"
VERDICT_MODULE = "_home_pin_verdict"

#: Byte pre-filter ahead of the parse, following ``test_home_pin_seam_no_second_copy.py``'s idiom.
#: A module that does not mention the scanner cannot import it, so the walk stays un-narrowed while
#: the parse set drops from every ``.py`` under ``tests/`` to the handful that could possibly match.
SEAM_BYTES = SEAM_MODULE.encode("utf-8")

#: A census or baseline artefact path: a **contiguous path token** containing the word and ending
#: in ``.yaml``/``.yml``.
#:
#: **The character class is deliberately narrow, and the first draft's was not.** Written
#: ``(census|baseline)[^"']*\.ya?ml`` it spanned newlines and matched any docstring that mentioned
#: "baseline" anywhere above a ``.yaml`` anywhere below — which fired on this package's own
#: pre-filter module, whose prose says "trains reviewers to re-baseline on noise". A matcher that
#: reads prose as an artefact read is a matcher nobody keeps.
_ARTEFACT_RE = re.compile(r"[\w./-]*(census|baseline)[\w./-]*\.ya?ml", re.IGNORECASE)

#: The seam's own names for those artefacts.
_ARTEFACT_NAMES = frozenset({"CENSUS_PATH", "BASELINE_PATH"})

#: Any digest constructor. The behaviour class holds exactly one checksum site and one
#: recomputation; a third is a re-implementation.
_HASH_NAMES = frozenset({"sha256", "sha1", "md5", "blake2b", "sha512"})

#: The verdict's operand vocabulary. **Two** are required to fire — see the module docstring.
_VERDICT_WORDS = frozenset({"census", "baseline", "discovered", "exempt"})

#: Comparison operators a second copy of the verdict could be written with.
#:
#: **``Eq`` alone is not enough, and shipping it alone was a real hole.** A copy written
#: ``discovered <= census | exempt`` names three of the four operand words and escaped on one
#: character — while a **subset-only ratchet** is the failure ``spec.md`` §0.4 spends a page
#: refusing, and the failure this very package ships
#: ``test_the_comparison_is_set_equality_and_not_containment`` to catch. A guard against a second
#: copy that is blind to the one second copy already known to be wrong is worse than no guard,
#: because it reads as coverage.
_COMPARISON_OPS: tuple[type[ast.cmpop], ...] = (ast.Eq, ast.LtE, ast.Lt, ast.GtE, ast.Gt)

#: The method spellings of the same containment relations.
_SUBSET_METHODS = frozenset({"issubset", "issuperset"})

#: ``relpath -> why it is allowed to do verdict work without importing the verdict seam.``
EXEMPT: dict[str, str] = {
    "architectural/_home_pin_verdict.py": (
        "It IS the verdict seam. It defines the comparison every other module must import, so "
        "requiring it to import itself is incoherent, and exempting it opens nothing."
    ),
    "architectural/test_home_pin_scan_limbs.py": (
        "WP01's generator tests reconstruct the census key-set checksum FROM FIRST PRINCIPLES with "
        "`hashlib.sha256` on purpose, so the check on `render_baseline` is INDEPENDENT of the "
        "generator. Routing them through `hash_of_key_set` would make `render_baseline` its own "
        "proof — the pass-for-the-wrong-reason shape this whole mission refuses. The duplication "
        "is the point there, and it is confined to testing the generator."
    ),
    "architectural/test_home_pin_verdict_seam.py": (
        "This module. Its matchers necessarily CONTAIN the patterns they match — the materialised "
        "copies below hold real census paths and real comparisons — so it trips its own signals by "
        "construction. It does import the verdict seam, but it is exempted by name rather than "
        "passing on that accident, so removing the import below cannot silently change what this "
        "guard means."
    ),
}

#: :data:`EXEMPT`'s key set, **pinned by content**. A fourth entry reds here until someone edits
#: this set deliberately, in the same commit, where a reviewer will see it.
#:
#: **This is the fix for a hole this guard shipped with, and the hole was demonstrated rather than
#: argued.** Taking positive control 1 — the copy this guard exists to catch — and adding one
#: ``EXEMPT`` row with twelve words of filler ("This module is fine and does not need the shared
#: verdict seam") moved ``offenders`` from ``['architectural/test_hand_rolled.py']`` to ``[]``, and
#: **all three** of the list's own limbs accepted it. The guard had two doors and the cheap one was
#: unguarded.
#:
#: **Set equality, never ``len(EXEMPT) == 3``.** That is not a compromise with the golden-count
#: ratchet, it is the state that ratchet converted *to* before it was retired (#4315):
#: the exemplar this sweep follows is
#: ``len(Lane) == 10`` becoming an exact frozenset of member names — because "adding, removing, or
#: renaming a member should force a *content* edit, not silently pass at an unchanged count". A
#: renamed exemption at an unchanged count is exactly what this must catch.
#:
#: The mission has already decided this shape twice. ``E`` is structurally identical — a fixed set
#: of forgiveness — and is bound by a **type** plus a pinned hash, with ``_home_pin_scan.py:145-148``
#: stating that ``why`` "is prose and entitles nothing the type does not already grant". T018 proves
#: that mechanism for ``E``; this applies it to the one set that was still guarded by a word count.
FROZEN_EXEMPT_KEYS: frozenset[str] = frozenset(
    {
        "architectural/_home_pin_verdict.py",
        "architectural/test_home_pin_scan_limbs.py",
        "architectural/test_home_pin_verdict_seam.py",
    }
)

#: The **EXTERNAL** pin: the same key set's ``sha256``, held in a generated file beside this module.
#:
#: :data:`FROZEN_EXEMPT_KEYS` alone was a second lock **mounted on the same door** — it sits ten
#: lines from :data:`EXEMPT`, and the red it raises tells a maintainer exactly which adjacent line
#: to edit. **The cost of forgiving yourself did not actually rise**, which is the shape of the word
#: count it replaced. This pin is what the mission already demands of ``E``, the structurally
#: identical set: fixed by type
#: **plus a hash held outside the module that declares it** (FR-004). Forgiving yourself now costs
#: **two files, one of them generated**.
#:
#: **RAISED DEVIATION, not silently repaired.** The instruction was to pin into "the baseline
#: artefact the guard already reads". No such artefact is available:
#:
#: * ``spec_kitty_home_pin_baseline.yaml`` **does not exist in this lane** — WP05 generates it;
#: * ``render_baseline`` emits a fixed five-key document, so carrying a sixth would mean editing
#:   ``_home_pin_scan.py``, which is WP01-owned and never editable here;
#: * its ``exempt_set_sha256`` is the hash of ``E`` — the **behaviour class's** exemption set of
#:   two ``Exempt`` rows — and this is the **verdict guard's** list of exempt MODULES. Overloading
#:   one field with two unrelated sets would be a worse defect than the one being fixed.
#:
#: So the pin follows the repository's own precedent for a guard owning an external ratchet:
#: ``_baselines.yaml`` beside ``test_ratchet_baselines.py``, in this very directory. (The closer
#: precedent, ``_golden_count_baseline.json``, was retired with its gate by #4315.)
#: **No second generator is invented**: the
#: digest comes from :func:`_home_pin_verdict.hash_of_key_set`, the seam's single recomputation,
#: which also makes this guard a consumer of the seam it guards.
EXEMPT_PIN_PATH = Path(__file__).resolve().with_name("_home_pin_verdict_exempt_pin.yaml")

#: The field inside that file.
EXEMPT_PIN_FIELD = "exempt_module_set_sha256"

#: How to regenerate it. Documented in the file it writes, and asserted to match.
EXEMPT_PIN_COMMAND = "python -m tests.architectural.test_home_pin_verdict_seam --freeze-exempt-pin"


def exempt_pin_digest(keys: frozenset[str] = frozenset()) -> str:
    """``sha256`` over the exemption key set, **through the verdict seam's own hasher**.

    Each relpath is lifted into a ``MemberKey``-shaped triple so the seam's existing payload format
    (`sorted, tab-joined, newline-separated`) is reused rather than a second one invented here.
    Only the first component carries information; the empty pair is padding and is documented as
    such so nobody reads meaning into it.
    """
    selected = keys or frozenset(EXEMPT)
    return verdict.hash_of_key_set(frozenset((relpath, "", "") for relpath in selected))


def freeze_exempt_pin() -> str:
    """Write :data:`EXEMPT_PIN_PATH` from the live :data:`EXEMPT`. The documented regeneration path."""
    digest = exempt_pin_digest()
    document = {
        "generated_by": "tests/architectural/test_home_pin_verdict_seam.py",
        "regeneration_command": EXEMPT_PIN_COMMAND,
        "note": (
            "The verdict guard's EXEMPT module list, pinned OUTSIDE the module that declares it "
            "so a self-forgiving edit costs two files. Never hand-edited. Adding an exemption is a "
            "review event: regenerate this, and say in the PR why a second copy of the verdict is "
            "warranted."
        ),
        EXEMPT_PIN_FIELD: digest,
    }
    EXEMPT_PIN_PATH.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return digest


# ---------------------------------------------------------------------------
# Matchers. One implementation each, run over the real tree AND over materialised
# copies — an empty-set assertion without that second run is its own proof.
# ---------------------------------------------------------------------------


def imports_module(tree: ast.Module, name: str) -> bool:
    """``True`` when ``tree`` imports ``name`` in any of its three spellings.

    ``import tests.architectural.<name>``, ``from tests.architectural import <name>`` and
    ``from tests.architectural.<name> import evaluate`` all count — the guard is about the
    dependency, not the spelling.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(name in alias.name.split(".") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and name in node.module.split("."):
                return True
            if any(alias.name == name for alias in node.names):
                return True
    return False


def docstring_nodes(tree: ast.Module) -> frozenset[int]:
    """``id()`` of every string constant that is a docstring — module, class, function.

    **Docstrings are PROSE and must never count as an artefact read.** Every module in this package
    discusses the census and the baseline at length; matching their text would flag the guard's own
    documentation and make the signal worthless. Identity rather than line number, because a
    docstring and a real path literal can share a line in principle.
    """
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return frozenset(found)


def _references_an_artefact(node: ast.expr, prose: frozenset[int]) -> bool:
    """One node: a census/baseline path literal, or the seam's own constant for one."""
    if isinstance(node, ast.Constant):
        return (
            isinstance(node.value, str)
            and id(node) not in prose
            and _ARTEFACT_RE.search(node.value) is not None
        )
    if isinstance(node, ast.Attribute):
        return node.attr in _ARTEFACT_NAMES
    return isinstance(node, ast.Name) and node.id in _ARTEFACT_NAMES


def artefact_reads(tree: ast.Module) -> frozenset[int]:
    """Lines referencing a census/baseline artefact by path literal or by the seam's constant.

    Docstrings are excluded — see :func:`docstring_nodes`.
    """
    prose = docstring_nodes(tree)
    return frozenset(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.expr) and _references_an_artefact(node, prose)
    )


def _is_digest_call(node: ast.expr) -> bool:
    """One node: a call to a digest constructor, receiver-agnostic like the scanner's matchers."""
    if not isinstance(node, ast.Call):
        return False
    callee = node.func
    if isinstance(callee, ast.Attribute):
        return callee.attr in _HASH_NAMES
    return isinstance(callee, ast.Name) and callee.id in _HASH_NAMES


def hand_rolled_hashes(tree: ast.Module) -> frozenset[int]:
    """Lines calling a digest constructor — a hand-rolled ``hash_of_key_set``."""
    return frozenset(
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.expr) and _is_digest_call(node)
    )


def _verdict_vocabulary(*parts: ast.AST) -> frozenset[str]:
    """Which of the verdict's operand words appear across ``parts``."""
    source = " ".join(ast.unparse(part) for part in parts).lower()
    return _VERDICT_WORDS & frozenset(re.findall(r"[a-z_]+", source))


def verdict_comparisons(tree: ast.Module) -> frozenset[int]:
    """Lines relating the verdict's operands by equality **or containment**.

    Both spellings of containment are covered: the operators in :data:`_COMPARISON_OPS` and the
    ``issubset``/``issuperset`` methods. Two or more operand words must appear, because one alone
    fires on ordinary identifiers.
    """
    hits: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if any(isinstance(op, _COMPARISON_OPS) for op in node.ops) and len(
                _verdict_vocabulary(node.left, *node.comparators)
            ) >= 2:
                hits.add(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _SUBSET_METHODS
            and len(_verdict_vocabulary(node.func.value, *node.args)) >= 2
        ):
            hits.add(node.lineno)
    return frozenset(hits)


def verdict_signals(tree: ast.Module) -> dict[str, frozenset[int]]:
    """All three signals for one module, empty sets omitted."""
    found = {
        "artefact-read": artefact_reads(tree),
        "hand-rolled-hash": hand_rolled_hashes(tree),
        "verdict-comparison": verdict_comparisons(tree),
    }
    return {name: lines for name, lines in found.items() if lines}


def modules_doing_verdict_work(root: Path) -> dict[str, dict[str, frozenset[int]]]:
    """``relpath -> signals`` for every scanner-importing module showing verdict work.

    Root-parameterised for the same reason :func:`_home_pin_scan.discover` is (FR-009): the positive
    controls run **this production matcher** over a materialised tree, never a second copy of it
    written for the test.
    """
    found: dict[str, dict[str, frozenset[int]]] = {}
    for path in scan.enumerate_py_files(root):
        if SEAM_BYTES not in path.read_bytes():
            continue
        tree = scan.parse_module(path)
        if not imports_module(tree, SEAM_MODULE):
            continue
        signals = verdict_signals(tree)
        if signals:
            found[path.relative_to(root).as_posix()] = signals
    return found


def offenders(root: Path) -> dict[str, dict[str, frozenset[int]]]:
    """Verdict work that does **not** import the verdict seam, exemptions removed."""
    result: dict[str, dict[str, frozenset[int]]] = {}
    for relpath, signals in modules_doing_verdict_work(root).items():
        if relpath in EXEMPT:
            continue
        if imports_module(scan.parse_module(root / relpath), VERDICT_MODULE):
            continue
        result[relpath] = signals
    return result


# ---------------------------------------------------------------------------
# Limb 1 — the ban over the real tree
# ---------------------------------------------------------------------------


def test_no_module_reimplements_the_verdict() -> None:
    """**The guard.** Verdict work without the verdict seam is a red.

    The failure message names the module, the signal and the lines, because the repair is always
    the same one line — import ``_home_pin_verdict`` — and a reviewer should not have to derive it.
    """
    found = offenders(TESTS_ROOT)
    assert found == {}, (
        f"module(s) perform the census/baseline comparison without importing "
        f"`{VERDICT_MODULE}`: { {k: {s: sorted(v) for s, v in sig.items()} for k, sig in found.items()} }. "
        f"The verdict has ONE home. Import `evaluate` / `census_keys` / `hash_of_key_set` from "
        f"`tests.architectural._home_pin_verdict` rather than re-deriving them."
    )


def test_the_verdict_work_population_is_non_empty() -> None:
    """The instrument check for the assertion above.

    ``{} == {}`` is true, so a matcher that sees nothing at all satisfies the ban forever. This
    asserts the predicate really does find the R1a modules that do verdict work.
    """
    doing = modules_doing_verdict_work(TESTS_ROOT)
    assert doing, (
        "the verdict-work population is EMPTY — the matcher sees nothing, so the ban above proves "
        "nothing. A hard-coded list would have greened here, which is why the set is discovered."
    )
    assert f"architectural/{VERDICT_MODULE}.py" in doing, (
        f"the seam itself must register as verdict work; if it does not, the signals no longer "
        f"describe the thing they are meant to detect. Found: {sorted(doing)}"
    )


# ---------------------------------------------------------------------------
# Limb 2 — the POSITIVE CONTROLS. A guard for a copy that has never been shown
# to catch a copy is the shape this mission exists to refuse.
# ---------------------------------------------------------------------------


def _materialise(root: Path, relpath: str, source: str) -> Path:
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return target


#: The copy WP05 would most plausibly write: read the checked-in census, compare it to the walk.
_HAND_ROLLED_COMPARISON = '''
from pathlib import Path

import yaml

from tests.architectural._home_pin_scan import discover


def test_the_real_tree_matches_the_frozen_census():
    document = yaml.safe_load(
        Path("tests/architectural/census/spec_kitty_home_pin_R1a.yaml").read_text(encoding="utf-8")
    )
    census = {tuple(row["key"]) for row in document["rows"]}
    discovered = {member.key for member in discover(Path("tests"))}
    assert discovered == census
'''

#: The other plausible copy: re-derive the key-set checksum instead of calling `hash_of_key_set`.
_HAND_ROLLED_HASH = '''
import hashlib

from tests.architectural._home_pin_scan import discover


def recompute(keys, pinned):
    payload = "\\n".join("\\t".join(key) for key in sorted(keys))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest() == pinned
'''

#: The SUBSET-ONLY copy — the second copy already known to be wrong. It names three of the four
#: operand words and, under an ``Eq``-only matcher, escaped on one character.
_SUBSET_ONLY_COPY = '''
from pathlib import Path

from tests.architectural._home_pin_scan import discover


def test_no_new_members(census, exempt):
    discovered = {member.key for member in discover(Path("tests"))}
    assert discovered <= census | exempt
'''

#: The same relation spelled as a method call.
_ISSUBSET_COPY = '''
from tests.architectural._home_pin_scan import discover


def check(discovered, census, exempt):
    return discovered.issubset(census | exempt)
'''

#: A scanner consumer doing NO verdict work — the negative control.
_ORDINARY_CONSUMER = '''
from pathlib import Path

from tests.architectural._home_pin_scan import discover, enumerate_py_files


def test_every_member_lives_in_a_walked_file():
    root = Path("tests")
    walked = {path.relative_to(root).as_posix() for path in enumerate_py_files(root)}
    assert {member.relpath for member in discover(root)} <= walked
'''


def test_the_guard_bites_on_a_hand_rolled_comparison(tmp_path: Path) -> None:
    """POSITIVE CONTROL 1: a materialised module that reads the census and compares it, reds.

    This is the copy the extraction alone did not prevent, and the reason this module exists.
    """
    root = tmp_path / "copy_by_comparison"
    _materialise(root, "architectural/test_hand_rolled.py", _HAND_ROLLED_COMPARISON)
    found = offenders(root)
    assert set(found) == {"architectural/test_hand_rolled.py"}
    assert set(found["architectural/test_hand_rolled.py"]) == {"artefact-read", "verdict-comparison"}


def test_the_guard_bites_on_a_hand_rolled_key_set_hash(tmp_path: Path) -> None:
    """POSITIVE CONTROL 2: a materialised module re-deriving the checksum reds on the hash signal.

    Distinct from control 1 — it reads no artefact and names no operand, so only the hash signal
    can see it. Without this limb that signal could be deleted with control 1 still green.
    """
    root = tmp_path / "copy_by_hash"
    _materialise(root, "architectural/test_rolled_hash.py", _HAND_ROLLED_HASH)
    found = offenders(root)
    assert set(found) == {"architectural/test_rolled_hash.py"}
    assert set(found["architectural/test_rolled_hash.py"]) == {"hand-rolled-hash"}


def test_the_guard_bites_on_a_subset_only_ratchet(tmp_path: Path) -> None:
    """POSITIVE CONTROL 3: ``discovered <= census | exempt`` reds.

    **This is the copy the guard was blind to when it first shipped.** A subset-only ratchet is the
    failure ``spec.md`` §0.4 spends a page refusing and the one this package ships
    ``test_the_comparison_is_set_equality_and_not_containment`` to catch — so a second-copy guard
    that missed it was blind to the single most likely wrong copy, while reading as coverage.

    It reads no artefact and hashes nothing, so **only** the comparison signal can see it: the limb
    cannot be narrowed back to ``Eq`` with this control green.
    """
    root = tmp_path / "subset_copy"
    _materialise(root, "architectural/test_subset.py", _SUBSET_ONLY_COPY)
    found = offenders(root)
    assert set(found) == {"architectural/test_subset.py"}
    assert set(found["architectural/test_subset.py"]) == {"verdict-comparison"}


def test_the_guard_bites_on_the_method_spelling_of_containment(tmp_path: Path) -> None:
    """POSITIVE CONTROL 4: ``discovered.issubset(census | exempt)`` reds.

    Same relation, different spelling. Without this the operator list could be extended while the
    method form stayed an open door — and a maintainer who has just been told "use set equality"
    is exactly the person who reaches for ``.issubset``.
    """
    root = tmp_path / "issubset_copy"
    _materialise(root, "architectural/test_issubset.py", _ISSUBSET_COPY)
    found = offenders(root)
    assert set(found) == {"architectural/test_issubset.py"}
    assert set(found["architectural/test_issubset.py"]) == {"verdict-comparison"}


#: Every spelling the comparison signal claims to see: one per entry in :data:`_COMPARISON_OPS`
#: plus one per entry in :data:`_SUBSET_METHODS`. **Each must actually FIRE the signal**, not merely
#: execute the branch — so narrowing ``_COMPARISON_OPS`` back toward ``Eq`` reds here rather than
#: silently shrinking what this guard can see. ``==``, ``<=`` and ``issubset`` are also covered
#: end-to-end by the full-module controls above; these cases exist so the other four are not
#: untested branches shipped in the code written to close an untested-branch finding.
_COMPARISON_SPELLINGS: dict[str, str] = {
    "eq": "discovered == census | exempt",
    "lte": "discovered <= census | exempt",
    "lt": "discovered < census | exempt",
    "gte": "census | exempt >= discovered",
    "gt": "census | exempt > discovered",
    "issubset": "discovered.issubset(census | exempt)",
    "issuperset": "census.issuperset(discovered | exempt)",
}

_SPELLING_MODULE = '''
from tests.architectural._home_pin_scan import discover


def check(discovered, census, exempt):
    return {expression}
'''


@pytest.mark.parametrize("spelling", sorted(_COMPARISON_SPELLINGS))
def test_every_comparison_spelling_fires_the_signal(tmp_path: Path, spelling: str) -> None:
    """All five operators and both method forms are exercised, and each one FIRES.

    The repository's Sonar expectation is that every new branch ships tests in the same change.
    ``_COMPARISON_OPS`` grew four operators and ``_SUBSET_METHODS`` two methods to close the
    subset-ratchet hole; three of those spellings had end-to-end controls and four did not.
    """
    root = tmp_path / f"spelling_{spelling}"
    _materialise(
        root,
        "architectural/test_spelling.py",
        _SPELLING_MODULE.format(expression=_COMPARISON_SPELLINGS[spelling]),
    )
    found = offenders(root)
    assert set(found) == {"architectural/test_spelling.py"}, (
        f"the {spelling!r} spelling ({_COMPARISON_SPELLINGS[spelling]}) is INVISIBLE to the "
        f"comparison signal — a second copy written this way would ship unnoticed"
    )
    assert set(found["architectural/test_spelling.py"]) == {"verdict-comparison"}


def test_the_spelling_cases_cover_every_configured_operator() -> None:
    """The cases and the configuration cannot drift apart.

    A new entry in :data:`_COMPARISON_OPS` or :data:`_SUBSET_METHODS` without a spelling case would
    be an untested branch again; this asserts the two stay in step, by **set** comparison over the
    operator names rather than by counting them.
    """
    configured = {op.__name__.lower() for op in _COMPARISON_OPS} | {
        method.lower() for method in _SUBSET_METHODS
    }
    assert configured == set(_COMPARISON_SPELLINGS), (
        f"comparison configuration and spelling cases drifted. Configured but unexercised: "
        f"{sorted(configured - set(_COMPARISON_SPELLINGS))}; exercised but not configured: "
        f"{sorted(set(_COMPARISON_SPELLINGS) - configured)}"
    )


def test_prose_about_the_artefacts_is_not_an_artefact_read(tmp_path: Path) -> None:
    """NEGATIVE CONTROL for a defect this guard shipped with and had to fix.

    The first draft matched ``(census|baseline)[^"']*\\.ya?ml``, whose character class spans
    newlines. A module docstring is a single string constant, so any docstring mentioning
    "baseline" above a ``.yaml`` below matched — and it fired on this package's own pre-filter
    module, whose prose says "trains reviewers to re-baseline on noise". Documentation must be free
    to discuss the artefacts; the matcher now requires a contiguous path token and skips docstrings.
    """
    root = tmp_path / "prose"
    _materialise(
        root,
        "architectural/test_prose.py",
        '''
        """Discusses the census and the baseline at length.

        It mentions re-baseline on noise, and separately mentions a spec.yaml somewhere below,
        which under a newline-spanning matcher would read as a census artefact path.
        """

        from tests.architectural._home_pin_scan import discover


        def test_walks():
            assert discover is not None
        ''',
    )
    assert modules_doing_verdict_work(root) == {}


def test_the_guard_does_not_fire_on_an_ordinary_scanner_consumer(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: a module using the scanner and doing no verdict work must PASS.

    A guard that fired on every consumer would be true, useless, and disabled by the first person
    it inconvenienced. The ban is only worth having if it discriminates.
    """
    root = tmp_path / "ordinary"
    _materialise(root, "architectural/test_ordinary.py", _ORDINARY_CONSUMER)
    assert modules_doing_verdict_work(root) == {}
    assert offenders(root) == {}


def test_importing_the_verdict_seam_clears_an_otherwise_offending_module(tmp_path: Path) -> None:
    """The repair works, and is the ONLY repair. Same source, one import added, guard clears.

    Asserted because a guard whose stated fix does not actually clear it trains maintainers to
    reach for the exemption list instead.
    """
    root = tmp_path / "repaired"
    repaired = _HAND_ROLLED_COMPARISON.replace(
        "from tests.architectural._home_pin_scan import discover",
        "from tests.architectural._home_pin_scan import discover\n"
        "from tests.architectural._home_pin_verdict import census_keys",
    )
    _materialise(root, "architectural/test_hand_rolled.py", repaired)
    assert modules_doing_verdict_work(root), "the module must still REGISTER as verdict work"
    assert offenders(root) == {}, "importing the seam must clear it"


# ---------------------------------------------------------------------------
# Limb 3 — the exemption list stays minimal and stays justified
# ---------------------------------------------------------------------------


def test_every_exemption_is_still_needed() -> None:
    """A STALE exemption is deleted, not left to accumulate.

    An entry is stale when the predicate no longer flags that module at all: it then protects
    nothing while still reading as a sanctioned hole. This is what keeps :data:`EXEMPT` from
    becoming the place copies go to be forgiven.

    Note what this does **not** claim. It cannot tell a justified exemption from an unjustified
    one — only review can, which is why every entry carries prose a reviewer can weigh. What it
    guarantees is that each entry still points at something real.
    """
    doing = modules_doing_verdict_work(TESTS_ROOT)
    stale = {relpath for relpath in EXEMPT if relpath not in doing}
    assert stale == set(), (
        f"exemption(s) that no longer flag anything and must be deleted: {sorted(stale)}. Every "
        f"entry in EXEMPT is a hole; a hole nothing falls through is still a hole."
    )


def test_the_exemption_key_set_is_pinned_by_content() -> None:
    """**Adding a row to :data:`EXEMPT` must be a REVIEW EVENT, not a one-line repair.**

    Without this, the guard has two doors: import the seam (one line), or forgive yourself (one
    line). Constructed, not argued — one filler row moved ``offenders`` from
    ``['architectural/test_hand_rolled.py']`` to ``[]`` while every other limb stayed green.

    Set equality against the frozen key set, so a fourth entry, a rename, or a swap at an unchanged
    count all red until :data:`FROZEN_EXEMPT_KEYS` is edited in the same commit.
    """
    assert frozenset(EXEMPT) == FROZEN_EXEMPT_KEYS, (
        f"EXEMPT's key set changed. Added: {sorted(frozenset(EXEMPT) - FROZEN_EXEMPT_KEYS)}; "
        f"removed: {sorted(FROZEN_EXEMPT_KEYS - frozenset(EXEMPT))}. An exemption is a sanctioned "
        f"second copy of the verdict — if that is really intended, edit FROZEN_EXEMPT_KEYS here so "
        f"the decision is visible in the diff. If it is not, import `_home_pin_verdict` instead."
    )


def test_the_exemption_key_set_is_pinned_OUTSIDE_this_module() -> None:
    """**The braces to :func:`test_the_exemption_key_set_is_pinned_by_content`'s belt.**

    That test and :data:`EXEMPT` live ten lines apart, so satisfying it is a two-adjacent-line edit
    in one file — raising no more real cost than the word count it replaced. This pin lives in a
    **generated file**, so a self-forgiving edit costs two files and shows up in the diff as a
    regenerated artefact, which is what the mission already demands of ``E``.

    Regenerate deliberately, never by hand::

        python -m tests.architectural.test_home_pin_verdict_seam --freeze-exempt-pin
    """
    assert EXEMPT_PIN_PATH.is_file(), (
        f"{EXEMPT_PIN_PATH.name} is missing — regenerate with `{EXEMPT_PIN_COMMAND}`"
    )
    document = yaml.safe_load(EXEMPT_PIN_PATH.read_text(encoding="utf-8"))
    assert exempt_pin_digest() == document[EXEMPT_PIN_FIELD], (
        f"EXEMPT no longer hashes to the pin held in {EXEMPT_PIN_PATH.name}. Adding, removing or "
        f"renaming an exemption is a REVIEW EVENT: if it is intended, run `{EXEMPT_PIN_COMMAND}` "
        f"and justify the new second copy of the verdict in the PR. If it is not intended, import "
        f"`_home_pin_verdict` instead."
    )


def test_the_external_pin_names_its_own_regeneration_command() -> None:
    """A generated artefact that does not say how to regenerate it becomes hand-edited."""
    document = yaml.safe_load(EXEMPT_PIN_PATH.read_text(encoding="utf-8"))
    assert document["regeneration_command"] == EXEMPT_PIN_COMMAND
    assert freeze_exempt_pin.__doc__, "the regeneration entry point must document itself"


def test_the_external_pin_is_sensitive_to_a_forged_exemption() -> None:
    """The instrument check: a different key set must produce a different digest.

    Without this the equality above could hold against a hasher that returns a constant, and the
    pin would green for every possible ``EXEMPT``. Uses the production digest function over a key
    set that is **not** the live one.
    """
    forged = frozenset(EXEMPT) | {"architectural/test_hand_rolled.py"}
    assert exempt_pin_digest(forged) != exempt_pin_digest(), (
        "the digest does not move when the exemption set does — the external pin is inert"
    )


def test_every_exemption_states_a_reason() -> None:
    """Prose entitles nothing, but a nameless exemption entitles everything.

    **The threshold is non-emptiness, deliberately.** This previously required ten words, which is
    a word count standing in for review — the counted-proxy shape C-002 forbids, reintroduced in
    the module whose job is refusing cheap greens. Twelve words of filler passed it. Nothing here
    can tell a good reason from a fluent one; what makes an exemption reviewable is
    :func:`test_the_exemption_key_set_is_pinned_by_content` forcing the diff, and this limb only
    guarantees a reviewer has something to read when it arrives.
    """
    unreasoned = {relpath for relpath, why in EXEMPT.items() if not why.strip()}
    assert unreasoned == set(), f"exemption(s) with no stated reason at all: {sorted(unreasoned)}"


def test_exemptions_name_real_files() -> None:
    """A stale exemption path silently protects nothing and hides that it protects nothing."""
    missing = {relpath for relpath in EXEMPT if not (TESTS_ROOT / relpath).is_file()}
    assert missing == set(), f"EXEMPT names file(s) that do not exist: {sorted(missing)}"


# ---------------------------------------------------------------------------
# The verdict seam's own input validation (the LOW raised in WP04's third pass:
# `as_key` grew two raising branches and neither was exercised).
# ---------------------------------------------------------------------------


def test_as_key_rejects_a_non_list_column() -> None:
    """A scalar where a key column belongs raises, rather than becoming a one-character tuple."""
    with pytest.raises(TypeError, match="must be a list"):
        verdict.as_key("relpath,qualname,token")


def test_as_key_rejects_a_wrong_arity_key() -> None:
    """The BARE 2-tuple is the 19-key collapse; it must raise here, never silently compare unequal.

    This is the same failure transition (8) catches behaviourally, caught one layer lower — a
    2-element key reaching a set operation would make every comparison false and every guard red
    for an unreadable reason.
    """
    with pytest.raises(ValueError, match="3-tuple"):
        verdict.as_key(["pinned_home", "monkeypatch . setenv ( )"])


def test_as_key_accepts_the_three_tuple() -> None:
    """The control: the shape the census actually holds round-trips."""
    assert verdict.as_key(["a.py", "fix", "tok"]) == ("a.py", "fix", "tok")


def test_this_module_never_parses_outside_the_seam() -> None:
    """WP02's anti-drift rule reaches this module too: zero ``ast.parse``, zero visitors."""
    tree = scan.parse_module(Path(__file__))
    parses = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "parse"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ast"
    ]
    assert parses == []


def _cli(argv: list[str] | None = None) -> int:
    """The documented regeneration entry for this seam's pin.

    A generated pin needs a generator that ships beside it; hand-editing the digest would make the
    external pin a formality. This writes it from the live :data:`EXEMPT` and nothing else.
    """
    parser = argparse.ArgumentParser(description="Regenerate the verdict guard's exemption pin.")
    parser.add_argument("--freeze-exempt-pin", action="store_true")
    args = parser.parse_args(argv)
    if not args.freeze_exempt_pin:
        parser.print_help()
        return 1
    print(f"Froze {EXEMPT_PIN_FIELD}={freeze_exempt_pin()} into {EXEMPT_PIN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
