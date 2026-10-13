"""Keep the project pack's ``pack.yaml`` trackable under the blanket ignore rule (#6076).

The charter-pack cutover (:mod:`m_4_0_0rc6_charter_pack_cutover`) rewrites a
consumer's retired project-layer ignore rules (a blanket ``**`` rule plus a
``!…/graph.yaml`` allow-rule) into ``.kittify/charter-packs/**`` +
``!.kittify/charter-packs/graph.yaml`` — but it only *rewrites* existing rules;
it never *adds* an allow-rule for ``pack.yaml``.
The later :mod:`m_4_0_0rc7_pack_level_backfill` then writes
``.kittify/charter-packs/pack.yaml``, which the blanket ``.kittify/charter-packs/**``
rule ignores, so the pack's ``pack_level`` never reaches other contributors and
each clone mints its own ``pack_id``.

This module owns the single rule for repairing that gap: *where the blanket
``.kittify/charter-packs/**`` rule is present and ``!.kittify/charter-packs/pack.yaml``
is absent, add the allow-rule beside the sibling charter-pack allow-rules*. The
cutover calls it to emit the rule going forward, and
:mod:`m_4_0_0rc7_track_charter_pack_yaml` calls it to heal already-cutover
installs, so there is ONE authority for the placement and the idempotency
rather than two drifting copies. The rule strings are built from the canonical
:mod:`kernel.charter_pack_paths` project-pack root, never a bare literal.

Both spellings of the blanket rule are recognised: the plain form and the
root-anchored form (a leading ``/``), because the cutover rewrites a legacy rule
verbatim and an anchored legacy rule stays anchored. The inserted allow-rule
matches the form of the blanket rule it negates. The *directory* form
(``.kittify/charter-packs/``) is deliberately left alone: git cannot re-include
a file beneath an excluded directory, so a negation would be inert.
"""

from __future__ import annotations

from kernel.charter_pack_paths import PROJECT_PACK_ROOT_POSIX

__all__ = [
    "CHARTER_PACK_YAML_ALLOW_RULE",
    "ensure_pack_yaml_allow_rule",
    "needs_pack_yaml_allow_rule",
]

#: The blanket ignore rule the cutover emits for the project pack root. Module
#: internal only (both public helpers below reference it), so it is deliberately
#: NOT in ``__all__``: the dead-symbol gate holds every ``__all__`` member to a
#: cross-module-export standard, and nothing outside this module imports it.
CHARTER_PACK_BLANKET_RULE = f"{PROJECT_PACK_ROOT_POSIX}/**"
#: The root-anchored spelling of the blanket rule (``/`` prefix).
_ANCHORED_BLANKET_RULE = f"/{CHARTER_PACK_BLANKET_RULE}"
#: The root-anchored spelling of the ``pack.yaml`` allow-rule.
_ANCHORED_PACK_YAML_ALLOW_RULE = f"!/{PROJECT_PACK_ROOT_POSIX}/pack.yaml"
#: The allow-rule that keeps the authored ``pack.yaml`` descriptor trackable.
CHARTER_PACK_YAML_ALLOW_RULE = f"!{PROJECT_PACK_ROOT_POSIX}/pack.yaml"
#: Every accepted spelling of the blanket rule / the ``pack.yaml`` allow-rule.
_BLANKET_RULES = frozenset({CHARTER_PACK_BLANKET_RULE, _ANCHORED_BLANKET_RULE})
_PACK_YAML_ALLOW_RULES = frozenset({CHARTER_PACK_YAML_ALLOW_RULE, _ANCHORED_PACK_YAML_ALLOW_RULE})
#: Prefixes shared by every charter-pack allow-rule (plain and anchored).
_ALLOW_RULE_PREFIXES = (f"!{PROJECT_PACK_ROOT_POSIX}/", f"!/{PROJECT_PACK_ROOT_POSIX}/")


def needs_pack_yaml_allow_rule(text: str) -> bool:
    """Whether *text* carries the blanket rule but not the ``pack.yaml`` allow-rule.

    This is the exact "where the blanket rule is present" condition: a project
    that never had the blanket rule (or already allows ``pack.yaml``) is left
    untouched, so a user-owned ``.gitignore`` customisation is never clobbered.
    """
    rules = {line.strip() for line in text.splitlines()}
    return bool(rules & _BLANKET_RULES) and not rules & _PACK_YAML_ALLOW_RULES


def _detect_newline(lines: list[str]) -> str:
    """Return ``"\\r\\n"`` when any line uses it, else ``"\\n"``."""
    return "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"


def ensure_pack_yaml_allow_rule(lines: list[str]) -> tuple[list[str], bool]:
    """Insert the ``pack.yaml`` allow-rule when the blanket rule is present.

    *lines* are ``.gitignore`` lines WITH their line endings
    (``str.splitlines(keepends=True)``). The allow-rule is inserted immediately
    after the run of charter-pack allow-rules that follows the LAST blanket
    rule — so it groups with ``!.kittify/charter-packs/graph.yaml`` and lands
    after the blanket rule it negates (``git`` is last-match-wins). When the
    blanket rule stands alone, the allow-rule is inserted directly after it.

    Returns ``(lines, changed)``. A no-op — the blanket rule is absent, or the
    allow-rule is already present — returns the input list unchanged with
    ``changed=False``. Idempotent and position-stable.
    """
    stripped = [line.strip() for line in lines]
    blanket_indexes = [index for index, rule in enumerate(stripped) if rule in _BLANKET_RULES]
    if not blanket_indexes or _PACK_YAML_ALLOW_RULES & set(stripped):
        return lines, False

    # Anchor on the LAST blanket rule so the negation always wins, then skip
    # past any consecutive charter-pack allow-rules to keep the block grouped.
    blanket_index = blanket_indexes[-1]
    allow_rule = _ANCHORED_PACK_YAML_ALLOW_RULE if stripped[blanket_index] == _ANCHORED_BLANKET_RULE else CHARTER_PACK_YAML_ALLOW_RULE
    insert_at = blanket_index + 1
    while insert_at < len(stripped) and stripped[insert_at].startswith(_ALLOW_RULE_PREFIXES):
        insert_at += 1

    newline = _detect_newline(lines)
    out = list(lines)
    # The line the new rule follows must terminate with a newline so the
    # inserted rule lands on its own line even at end-of-file.
    anchor = insert_at - 1
    if anchor >= 0 and out[anchor] and not out[anchor].endswith(("\n", "\r")):
        out[anchor] = out[anchor] + newline
    out.insert(insert_at, f"{allow_rule}{newline}")
    return out, True
