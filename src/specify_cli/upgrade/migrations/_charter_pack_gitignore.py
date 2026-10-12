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
#: The allow-rule that keeps the authored ``pack.yaml`` descriptor trackable.
CHARTER_PACK_YAML_ALLOW_RULE = f"!{PROJECT_PACK_ROOT_POSIX}/pack.yaml"
#: Prefix shared by every charter-pack allow-rule (``!.kittify/charter-packs/…``).
_ALLOW_RULE_PREFIX = f"!{PROJECT_PACK_ROOT_POSIX}/"


def needs_pack_yaml_allow_rule(text: str) -> bool:
    """Whether *text* carries the blanket rule but not the ``pack.yaml`` allow-rule.

    This is the exact "where the blanket rule is present" condition: a project
    that never had the blanket rule (or already allows ``pack.yaml``) is left
    untouched, so a user-owned ``.gitignore`` customisation is never clobbered.
    """
    rules = {line.strip() for line in text.splitlines()}
    return CHARTER_PACK_BLANKET_RULE in rules and CHARTER_PACK_YAML_ALLOW_RULE not in rules


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
    if CHARTER_PACK_BLANKET_RULE not in stripped or CHARTER_PACK_YAML_ALLOW_RULE in stripped:
        return lines, False

    # Anchor on the LAST blanket rule so the negation always wins, then skip
    # past any consecutive charter-pack allow-rules to keep the block grouped.
    blanket_index = max(index for index, rule in enumerate(stripped) if rule == CHARTER_PACK_BLANKET_RULE)
    insert_at = blanket_index + 1
    while insert_at < len(stripped) and stripped[insert_at].startswith(_ALLOW_RULE_PREFIX):
        insert_at += 1

    newline = _detect_newline(lines)
    out = list(lines)
    # The line the new rule follows must terminate with a newline so the
    # inserted rule lands on its own line even at end-of-file.
    anchor = insert_at - 1
    if anchor >= 0 and out[anchor] and not out[anchor].endswith(("\n", "\r")):
        out[anchor] = out[anchor] + newline
    out.insert(insert_at, f"{CHARTER_PACK_YAML_ALLOW_RULE}{newline}")
    return out, True
