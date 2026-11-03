# Contracts

No machine-readable contract is added or changed by this mission. The only
interface the change touches is the existing, untyped Python seam:

- `specify_cli.mission_metadata.read_tracked_meta(feature_dir) -> TrackedMeta` — return type,
  fields and the `unavailable` refusal signal are unchanged; only which `TrackedMeta` value a
  folder under a non-repository `.git` produces changes (from the refusal to "nothing tracked").
- `specify_cli.upgrade.feature_meta.build_baseline_feature_meta(feature_dir, repo_root, *,
  existing_meta=None) -> dict[str, Any] | None` — signature and `None` semantics unchanged.

The CLI surfaces (`spec-kitty upgrade`, `spec-kitty migrate ledger`) keep their output shapes;
the change removes a false `wrote baseline meta.json` report rather than adding a field.
