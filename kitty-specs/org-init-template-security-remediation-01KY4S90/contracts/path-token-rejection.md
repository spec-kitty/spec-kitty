# Contract: Path-token rejection

## Tokens

`{{ORG_NAME}}` and `{{LOCAL_PATH}}` only.

## Contents

Continue to substitute in UTF-8 text file contents; fail if leftovers remain (`substitute.leftover_tokens`).

## Entry names

If any file or directory **name** (any path component under the staging/PACK tree) contains either token literally, fail with `substitute.path_token` and do not install a successful pack.

## Non-goals

No automatic renaming / path substitution engine.
