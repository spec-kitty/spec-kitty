# Data Model — anchor-keyed lock paths

There is no persisted data model in this Mission: it consolidates a pure path computation. The
"model" is the value shape the helper accepts and returns, and the invariants a caller may rely
on. It is recorded here because those invariants are the contract the tests pin.

## Values

### `Anchor` (`pathlib.Path`)

The path a lock family keys on. It is resolved once (`Path.resolve()`), so a symlinked checkout
and its target, or a relative anchor and its absolute form, produce one lock.

| Family | Anchor | Anchor kind |
| --- | --- | --- |
| event-log | the log file, or the family directory for `kitty-ops/<op>.jsonl` | file or directory |
| charter synthesis | the worktree root | directory |
| Mission status (checkout claim) | the write checkout root | directory |

### `AnchorDigest` (`str`)

`digest_algorithm(os.path.normcase(str(anchor.resolve())).encode("utf-8")).hexdigest()[:digest_hex_length]`

- `resolve()` first, then `normcase`, then encode UTF-8, then digest, then truncate. The order is
  the contract; changing it changes every lock name.
- `digest_algorithm` defaults to `"sha256"`, `digest_hex_length` to `32`.
- Validation: an unknown algorithm or a length outside `1..64` raises `ValueError` (the helper
  refuses to mint a name it cannot reproduce).
- The sha1 shape passes `usedforsecurity=False`; sha1 here is a file-name discriminator, not a
  security primitive.

### `LockPath` (`pathlib.Path`)

`<common dir>/spec-kitty-locks[/<subdirectory>]/<prefix><AnchorDigest><suffix>`

| Family | `subdirectory` | `prefix` | `suffix` | `digest_algorithm` / length |
| --- | --- | --- | --- | --- |
| event-log | `event-logs` | `""` | `.lock` | `sha256` / 32 |
| charter synthesis | `charter-synthesis` | `""` | `.lock` | `sha256` / 32 |
| Mission status (checkout claim) | `None` | `__checkout-` | `__.status.lock` | `sha1` / 16 |

### `CommonDir` (`pathlib.Path`)

The repository `.git` shared by a checkout and all its worktrees, from
`kernel.git_topology.git_common_dir(probe)`. `LOCK_DIRECTORY` (`"spec-kitty-locks"`) is appended
by the helper, so no caller joins it.

## Invariants

1. **Name stability.** For one resolved anchor and one family, the produced path is identical
   before and after this Mission. `tests/kernel/test_event_log_append.py` (golden digest
   `5d011f83a018c89fa185a10c696c8293`), `tests/charter/synthesizer/test_synthesis_lock.py` and
   `tests/status/test_checkout_claim_lock.py` (literal sha1 name) are the proof and stay
   unedited.
2. **One probe at most.** With `common_dir` supplied, the helper runs no git probe. Without it,
   it calls `git_common_dir` once, which is `lru_cache`d.
3. **Probe location is explicit.** `probe_dir` is what is probed — the event-log family passes
   the anchor's parent because the log file may not exist yet, and
   `kernel.git_topology._probe_dir` only normalises an existing file.
4. **No policy in the helper.** A not-a-repository or an unusable git raises the
   `kernel.git_topology` error; the family decides between a fallback path (event-log, synthesis)
   and a degraded common dir (Mission status). The helper never catches, never falls back, never
   writes.
5. **One owner.** No module under `src/` other than `kernel/locks.py` both names a file under
   `LOCK_DIRECTORY` and derives a digest from a path (gate `FR-006`).

## State transitions

None. The computation is pure with respect to the filesystem: it reads the resolved path of its
anchor and (unless given) the git common dir; it creates no directory and no lock file. Creating
the lock directory and writing the lock record stays with `kernel.locks.machine_file_lock`, as
before.
