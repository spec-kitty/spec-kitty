# Untrusted-segment → filesystem-sink audit ruleset (WP01 / FR-003, FR-004)

This ruleset is **reproducible**: a reviewer re-runs

```bash
python -m tests.architectural.untrusted_path_audit.audit
```

and the script re-walks `src/specify_cli`, re-discovers the sink set, and
fails closed (non-zero exit) if the live tree no longer matches
`inventory.md`. The machine job is to make undercounting impossible; the
**disposition** of each row is a human judgement recorded in `inventory.md`.

---

## Canonical seam (what "routed-through-seam" cites)

| Seam | Location | Guarantee |
|------|----------|-----------|
| `assert_safe_path_segment(value)` | `core/paths.py` | Raises `ValueError` on empty/`.`/`..`/separators/non-ASCII/leading-dot. |
| `safe_mission_slug(slug, fallback)` | `core/paths.py` | Fail-closed: downgrades an unsafe slug to the trusted `fallback`. |
| `ensure_within_any(path, roots=…, files=…)` | `core/utils.py` | Raises if the resolved path escapes every trusted root. |
| `ensure_within_directory` / `write_text_within_directory` | `core/utils.py` | Containment-guarded write under a single root. |
| `MissionStatus._validate_mission_slug` → `InvalidMissionSlug` | `status/aggregate.py` | Boundary guard delegating to `assert_safe_path_segment`. |
| `_validate_segment` → `ReviewCycleError` | `review/cycle.py` | Per-segment guard delegating to `assert_safe_path_segment`. |
| `reducer.safe_mission_slug` | `status/reducer.py:162` | Sanitises `snapshot.mission_slug` once, at reduction time. |

---

## Seed-set (untrusted source symbols)

A path segment is **untrusted** when its value can originate from outside the
trusted derived chain — `status.events.jsonl` rows, `meta.json` fields,
frontmatter, or CLI arguments. Seed symbols/fields:

- Named locals/params: `mission_slug`, `feature_slug`, `wp_id`, `wp_slug`,
  `slug`, `run_id`, `review_ref`.
- Attribute reads ending in an untrusted name: `snapshot.mission_slug`,
  `lifecycle.mission_slug`, `self.mission_slug`, `resolved.mission_slug`, …
- Mapping reads of an untrusted key: `meta.get("mission_slug")`,
  `meta["mission_slug"]`.

**Named-untrusted rule (SC-003):** a segment that *is* `mission_slug`,
`feature_slug`, or `wp_id` (spec Domain Language) may **never** be classified
`trusted-source`. Such a row is either `routed-through-seam` (cite the seam) or
`unreachable` (cite the chain). The audit script enforces this: a `trusted-source`
row whose source names a bare untrusted segment fails the build. (The
*derived* forms `feature_dir.name` / `mission_dir.name` / a slug looked up
*against the on-disk mission index* are trusted — they are directory names, not
raw external input.)

---

## Sink predicate

A call site is a sink when an untrusted segment reaches the filesystem via:

1. **Path-join** — a `<path-expr> / <segment>` `BinOp` where the right operand
   is an untrusted segment (the matcher recurses the left operand so
   `root / a / mission_slug` and `root / slug / "x"` both match).
2. **Sink method on a path** — `.open` / `.read_text` / `.read_bytes` /
   `.write_text` / `.write_bytes` / `.mkdir` / `.unlink` / `.touch` /
   `.replace` invoked on a receiver built from an untrusted segment.
3. **Sink function** — `open(...)`, `shutil.copy|copy2|copyfile|move|rmtree`,
   `atomic_write(...)`, `write_text_within_directory(...)` with an
   untrusted-built argument.

### Aliasing depth — **one hop** (hardened DoD #1)

The matcher follows **one hop of local-variable aliasing**:

```python
slug = meta.get("mission_slug")   # taints local `slug`
...
output_dir = root / slug          # ← detected as a sink (aliased)
output_dir.mkdir(...)             # ← sink-method on aliased path
```

It also follows the `x = <untrusted> or fallback` (`BoolOp`) idiom
(`mission_slug = snapshot.mission_slug or feature_dir.name`), because the
tainted operand still flows into the local.

---

## Known false-negative classes (what this matcher does **NOT** trace)

Stated explicitly so the reviewer judges *residual* risk, not assumes zero:

1. **Cross-function / inter-procedural flow.** Taint is computed per-function.
   A segment passed *into* another function as a `Path` argument and joined
   there is detected at the callee (where the join is written), but the matcher
   does not prove the *caller* supplied an untrusted value — provenance is
   resolved by the human disposition, not the AST.
2. **More than one alias hop.** `a = slug; b = a; root / b` (two hops) is **not**
   followed. (No such pattern exists in the audited candidates; if one is
   introduced later it is a new false negative the reviewer must catch.)
3. **Container/collection flow.** A segment stored in a list/dict/tuple and
   later popped into a join is not traced.
4. **f-strings / `os.path.join` / `str` concatenation.** Only `pathlib` `/`
   joins and the enumerated sink calls are matched. A segment interpolated into
   an f-string path (`f"{root}/{slug}"`) is **not** detected. (No audited
   candidate uses this form; it is recorded as a residual class.)
5. **`Path(...)` constructed from an untrusted *full* string** (rather than a
   join) — e.g. `Path(user_supplied_abs_path)` — is not a join and is not
   flagged. (No mission-slug/wp-id candidate uses this; the CLI path-string
   cases are dispositioned individually.)
6. **The FR-009 `meta.json` write-path.** `mission_metadata.write_meta` writes
   `feature_dir / "meta.json"` — the FS sink is keyed on the *`feature_dir`
   Path argument*, not on a literal `mission_slug` join, so the AST matcher does
   **not** discover it. It is asserted by **inventory presence** instead (the
   script requires a `mission_metadata.py` row tagged `routed-through-seam
   (TODO)`), because the untrusted `mission_slug` reaches that directory through
   upstream `KITTY_SPECS_DIR / mission_slug` composition that WP02 must guard.

Because of (1) the matcher can over-report (a join inside a function whose only
caller passes a trusted directory name): those are dispositioned
`trusted-source` / `routed-through-seam` with a cited rationale, never silently
dropped.

---

## Disposition vocabulary (exactly one per row)

| Disposition | Meaning |
|-------------|---------|
| `routed-through-seam` | Already passes a seam (cite the call) before the sink. |
| `routed-through-seam (TODO)` | Reachable with an untrusted segment, **no** seam yet → routes to WP02 (`status/`) or WP03 (other pkgs). |
| `unreachable` | The call chain cannot carry an untrusted segment to a real FS open/write (name the chain). |
| `trusted-source` | The segment provably originates from `feature_dir.name` / a derived directory name / the on-disk mission index — **never** a bare named-untrusted segment. |

---

## Anti-overfit proof (T004)

The seed-set is data (`UNTRUSTED_SEGMENT_NAMES` / `UNTRUSTED_ATTR_NAMES` in
`audit.py`), not a hard-coded file list. Adding `"filename"` to the seed-set
and re-discovering surfaces **+35 new joins** across unrelated modules — see
`inventory.md` § "Anti-overfit demonstration" for the recorded experiment.
