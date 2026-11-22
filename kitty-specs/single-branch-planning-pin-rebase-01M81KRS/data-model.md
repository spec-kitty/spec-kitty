# Data Model

One additive optional key in `lanes.json`: `planning_commit_derived` (research R4).

## PlanningCommitResolution (existing, `mission_finalize_planning_pin.py`)

| Field | Change |
|-------|--------|
| `action` | adds no value; `repinned` now also covers a patch-id follow (the report says which) |
| `refusal_reason` | adds `no_pin_underivable` and `window_would_empty` (the automatic path keeps the pin) |
| `matched_by` (new, optional) | `"patch_id"` when the re-pin followed the planning commit; `None` otherwise. JSON: carried in `planning_commit.matched_by` only when set |

## PatchIdFollow (new, `lanes/planning_base.py`)

A frozen result: `sha: str | None`, `miss: Literal["no_patch_id", "no_match", "ambiguous"] | None`, `candidates: tuple[str, ...]`. Invariant: exactly one of `sha` / `miss` is set.

## LanesManifest (existing, `lanes/models.py`)

| Field | Change |
|-------|--------|
| `planning_commit_derived` (new) | `bool`, default `False`; serialized only when `True`; read strictly (`is True`) |

## Invariants

- I-1: a `single_branch` pin and its window tip are on the same branch line (`pin_branch_line`).
- I-2: no re-pin or automatic refresh writes a pin whose window holds fewer owned-file changes than the recorded window, when the recorded window had any.
- I-3: a recorded pin changes only by an explicit refresh or an automatic refresh that passes I-2 and is not a derived pin.
