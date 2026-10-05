# Design decisions: pack-shipped-builtin-override-sanction-01M45WB7

- 2026-10-05: Option (a), a pack-declared sanction read in place, rather than (b) a fetch-time copy or (c) a per-node `replaces:` marker. See research.md D1.
- 2026-10-05: A pack-root file rather than an `org-charter.yaml` key, because `OrgCharterPolicy` is `extra="forbid"` and any new key breaks CLIs that have already shipped. See D2.
- 2026-10-05: The legacy-template hint prints the `{urn, reason}` entries, not a whole-file `cp`, so it does not reintroduce the drift. See D7.
- 2026-10-05: Consumer revocation works per URN or per pack, so that delegated sanctions stay revocable. See D5.
