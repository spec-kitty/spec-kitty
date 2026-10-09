# Built-in Charter Pack

The **built-in** pack ships with Spec Kitty itself: the baseline directives,
tactics, styleguides, toolguides, paradigms, procedures, agent profiles, and
mission-step contracts every project starts with before any org or project
layer is applied.

It has no `parent_pack` (it is the root of every lineage chain).

This file, and its sibling `pack.yaml`, are **authored** — hand-edited data
that is never regenerated. The pack's constituent inventory, content hashes,
and self-integrity hash live in the **generated** `pack-manifest.yaml` next
to this file; that file is machine-written only and must never be hand-edited
(see `tests/architectural/test_pack_manifest_no_author_edit.py`).
