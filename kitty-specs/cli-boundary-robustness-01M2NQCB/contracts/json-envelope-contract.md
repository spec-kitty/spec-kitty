# Contract — `--json` machine contract

Authoritative behavior every adopted `--json` command must satisfy. Test surface:
CliRunner-driven integration tests + the WP06 enumeration gate.

## C1 — Parseability (universal)
For every `--json`-capable command, on its driven error path and driven empty path:
`json.loads(stdout)` MUST succeed. stdout contains no non-JSON bytes.

## C2 — Error envelope shape (adopted commands)
On an error path, `json.loads(stdout)` == an object where:
- `ok` is `false`
- `error` is an object with a non-empty string `code` and a non-empty string `message`
Human prose (if any) is on stderr, not stdout.

## C3 — Empty-success shape (adopted commands)
On an empty-but-success path:
- exit code == 0
- `json.loads(stdout)` is the command's success payload with empty collections
- NO `error` key is present

## C4 — Exit-code fidelity
A `--json` invocation's exit code == the same command's non-`--json` exit code for
the same condition. (Per frozen `test_doctor_json_not_in_project.py`: mostly 1;
exit 2 only for `doctor` shim-registry/contracts/tool-surfaces.) The fix MUST NOT
homogenize exit codes.

## C5 — Stream discipline
Under `--json`, stdout is JSON-only on every exit path; all human-readable text
goes to stderr/`err_console`.

## C6 — Happy-path invariance
The existing successful `--json` output of every adopted command is unchanged.

## C7 — Not-in-project (universal via helper)
`get_project_root_or_exit(..., json_output=True)` emits the C2 envelope
(`code: not_in_project`) at the command's existing exit code; the prose form is
unchanged when `json_output=False` (default).
