# Data model: Upgrade and Windows drift

No new persisted entity. Two classifications change.

## Command-skill file classification

Inputs: `disk` (SHA-256 of on-disk bytes), `recorded` (`ManifestEntry.content_hash`), `canonical` (SHA-256 of today's rendering), `consent` (`ApplyConsent.overwrite_paths`).

| disk vs recorded | disk vs canonical | Before | After | Write? |
|------------------|-------------------|--------|-------|--------|
| equal | equal | present | present | no |
| equal | different | present/stale | unchanged (install refreshes as today) | as today |
| different | equal | **drifted, consent_required** | **present; `recorded := canonical`** | manifest only |
| different | different, path not in consent | drifted, consent_required | drifted, consent_required (reported) | no |
| different | different, path in consent | drifted, consent_required (write refused) | **overwritten with canonical; `recorded := canonical`** | yes |
| no entry | equal | adopted | adopted | manifest only |
| no entry | different | preserve | preserve | no |

`consent` is populated only by `CommandSkillsProvider.repair` for statuses in `STATE_DRIFTED`, reached from `doctor tool-surfaces --fix` or an interactive upgrade "yes".

## Planning-artifact staging classification

Inputs: `oid_ref` (object id of `<ref>:<rel>`, absent if the path is not in the ref), `oid_work` (`git hash-object --stdin-paths` of the working file, clean filter applied).

| Condition | Before | After |
|-----------|--------|-------|
| bytes equal | clean | clean |
| bytes differ only by line endings Git normalizes | **changed** | clean |
| real text change (any line ending) | changed | changed |
| path absent in ref | changed | changed |
| git error for this path | n/a | changed (fail closed) |
