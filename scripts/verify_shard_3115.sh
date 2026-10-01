#!/usr/bin/env bash
# verify_shard_3115.sh — the FR-011 shard proof for issue #3115.
#
# Constructs and runs the two CI shards (sync, cli) with the EXACT file
# selection, --ignore set, marker selection, --dist mode and --cov flag
# copied from .github/workflows/ci-quality.yml (sync: ~L1124-1133; cli:
# ~L1540-1546), then reconciles the 13 node-ids named in
# kitty-specs/verification-trust-3115-01KYVYWM/tasks/WP13-shard-proof.md
# against the run's own collected set and its own report.
#
# It never pipes a suite whose exit status it intends to trust (NFR-003):
# each shard's full output goes to a file, and the file — not pytest's own
# exit code — is what this script reads for the collected count, the
# gw0..gwN worker header, and each node-id's outcome. It refuses to report
# a green on an empty collection (the `|| test $? -eq 5` escape hatch that
# ci-quality.yml:1545 uses is deliberately NOT reproduced here).
#
# The two shards are run one after another, never concurrently (NFR-004):
# tests/sync and tests/cli sessions spawn real daemons and pgrep/port-scan
# each other, and 16 false reds are on record from running them together.
#
# Usage:
#   scripts/verify_shard_3115.sh [output-dir]
#
# output-dir defaults to out/reports/shard-3115-<UTC timestamp>/ under the
# repo root the script is invoked from. Two full-output files are written
# there: sync.out and cli.out. A summary is printed to stdout AND appended
# to summary.txt in the same directory.
#
# Interpreter: this script assumes PYTHON is already set to a pytest 9.x
# interpreter with the xdist/timeout/cov plugins registered (the repo's
# .venv, not a bare `python3`) and that PYTHONPATH points at the source
# tree this worktree/checkout is measuring (NFR-002) — see the README-style
# preamble below, which the script prints and enforces at runtime.

set -u
set -o pipefail

# ---------------------------------------------------------------------------
# 0. Locate the repo root (the directory containing this script's parent's
#    parent, i.e. assume the script lives at <root>/scripts/verify_shard_3115.sh)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${REPO_ROOT}" || { echo "FATAL: cannot cd to repo root ${REPO_ROOT}" >&2; exit 2; }

# ---------------------------------------------------------------------------
# 1. Interpreter and import-path setup (NFR-001 interpreter clause, NFR-002)
# ---------------------------------------------------------------------------
: "${PYTHON:=${REPO_ROOT}/.venv/bin/python}"
if [[ ! -x "${PYTHON}" ]]; then
  # Fall back to a venv one level up (the common layout when this script
  # runs inside a `git worktree` that has no venv of its own — the worktree
  # then borrows the main checkout's venv, and PYTHONPATH below is what
  # keeps the *source* pinned to this tree rather than the live one).
  ALT_PYTHON="$(cd -- "${REPO_ROOT}/.." >/dev/null 2>&1 && pwd)/spec-kitty/.venv/bin/python"
  if [[ -x "${ALT_PYTHON}" ]]; then
    PYTHON="${ALT_PYTHON}"
  fi
fi
if [[ ! -x "${PYTHON}" ]]; then
  echo "FATAL: no usable interpreter at ${PYTHON}. This script requires the" >&2
  echo "repo's .venv (pytest 9.x with xdist/timeout/cov registered), never a" >&2
  echo "bare 'python3' — see standing-rules.md's interpreter clause." >&2
  exit 2
fi

export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
: "${SPEC_KITTY_TEST_DB_NAME:=test_verification_trust_3115_01KYVYWM_lane_l}"
export SPEC_KITTY_TEST_DB_NAME

echo "=== FR-011 shard proof: interpreter and import path ==="
echo "sys.executable / sys.version / plugins11 registry (quoted, not inferred):"
"${PYTHON}" - <<'PYEOF'
import sys
try:
    import importlib.metadata as md
except ImportError:  # pragma: no cover
    import importlib_metadata as md  # type: ignore
print(f"  sys.executable = {sys.executable}")
print(f"  sys.version    = {sys.version.split()[0]}")
eps = sorted(e.name for e in md.entry_points(group="pytest11"))
print(f"  pytest11 registry ({len(eps)}): {', '.join(eps)}")
PYEOF
echo "  PYTHONPATH     = ${PYTHONPATH}"
echo "  SPEC_KITTY_TEST_DB_NAME = ${SPEC_KITTY_TEST_DB_NAME}"
echo "  repo root      = ${REPO_ROOT}"
echo

# ---------------------------------------------------------------------------
# 2. Output directory
# ---------------------------------------------------------------------------
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${1:-out/reports/shard-3115-${TS}}"
mkdir -p "${OUT_DIR}"
SUMMARY="${OUT_DIR}/summary.txt"
: > "${SUMMARY}"

log() {
  # Print to stdout AND append to the summary file — never rely on a pipe.
  echo "$*"
  echo "$*" >> "${SUMMARY}"
}

log "=== FR-011 shard proof — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
log "repo root: ${REPO_ROOT}"
log "python:    ${PYTHON}"
log "output:    ${OUT_DIR}"
log ""

# ---------------------------------------------------------------------------
# 3. Helpers
# ---------------------------------------------------------------------------

# Extract the xdist gw0..gwN worker-count header from a captured run file.
# xdist's own startup line is one of:
#   "N workers [M items]"
#   "gw0 [M] / gw1 [M] / ... / gwK [M]" (older/verbose form)
# We search for both and report whichever the run actually printed —
# never inferred from the runner label or from -n's argument.
extract_worker_header() {
  local file="$1"
  local line
  line="$(grep -m1 -E '^[0-9]+ workers? \[[0-9]+ items?\]' "${file}" 2>/dev/null || true)"
  if [[ -n "${line}" ]]; then
    echo "${line}"
    return 0
  fi
  line="$(grep -m1 -E '^gw[0-9]+ \[[0-9]+\]( / gw[0-9]+ \[[0-9]+\])*' "${file}" 2>/dev/null || true)"
  if [[ -n "${line}" ]]; then
    echo "${line}"
    return 0
  fi
  echo "NO gw/workers HEADER FOUND IN OUTPUT"
  return 1
}

# Extract the final pytest summary count line (e.g. "12 passed, 1 failed in
# 3.21s"). pytest centre-pads this line with "=" on both sides when it fits
# the terminal width (e.g. "=========== 2108 passed, ... ============"), so
# it must NOT be anchored to the start of the line — an earlier version of
# this function anchored with ^[0-9] and silently matched nothing.
#
# Returns 1 and prints a named sentinel if no count line is found — this
# script names the count line as the evidence for NFR-003 ("the collected
# count and the count line below are the evidence, not this number"), so an
# absent count line must not be silently swallowed by a caller.
extract_count_line() {
  local file="$1"
  local line
  line="$(grep -E '[0-9]+ (passed|failed|error|skipped|deselected|xfailed|xpassed)' "${file}" | tail -1)"
  if [[ -z "${line}" ]]; then
    echo "NO COUNT LINE FOUND IN OUTPUT"
    return 1
  fi
  echo "${line}"
  return 0
}

# Extract the collected-count-bearing line. Under xdist, that is the
# "N workers [M items]" header itself (there is no separate "collected"
# line when -n/--dist is active — verified empirically in this worktree).
# Falls back to --collect-only-style "N tests collected" / "no tests
# collected" / collection-error phrasing for non-distributed invocations.
extract_collected_line() {
  local file="$1"
  local line
  line="$(grep -m1 -E '^[0-9]+ workers? \[[0-9]+ items?\]' "${file}" 2>/dev/null || true)"
  if [[ -n "${line}" ]]; then
    echo "${line}"
    return 0
  fi
  grep -E '[0-9]+ (tests?) collected|no tests? (ran|collected)|error(s)? during collection' "${file}" \
    | tail -3
}

# Extract pytest's own "platform … / plugins: …" header lines (versioned
# plugin list, e.g. "xdist-3.8.0") from a captured run file. NFR-001 says
# "quotes the run's own plugins: header" — distinct from the pytest11
# entry-point registry printed once at script start (name-only, no
# versions, installed rather than run-specific). This is the line NFR-001
# actually names, and the run that omitted it is the one this mission
# records as having been bitten by exactly that omission.
#
# Returns 1 if EITHER line is missing. A prior version of this function
# used `grep … || echo "NO … FOUND"` per line, which always exits 0 (the
# echo's own exit code, not grep's) — the sentinel text printed correctly
# but the function's return code never reflected the absence, so a caller
# discarding the return code (as every call site previously did) saw a
# named gap on screen and a green exit regardless.
extract_plugins_header() {
  local file="$1"
  local platform_line plugins_line rc=0
  platform_line="$(grep -m1 -E '^platform ' "${file}" 2>/dev/null || true)"
  if [[ -z "${platform_line}" ]]; then
    platform_line="NO 'platform' LINE FOUND"
    rc=1
  fi
  plugins_line="$(grep -m1 -E '^plugins: ' "${file}" 2>/dev/null || true)"
  if [[ -z "${plugins_line}" ]]; then
    plugins_line="NO 'plugins:' LINE FOUND"
    rc=1
  fi
  echo "${platform_line}"
  echo "${plugins_line}"
  return "${rc}"
}

# Extract the distinct set of gwK worker tags actually observed in a `-v`
# run's per-test lines ("[gw0] [  1%] PASSED <nodeid>"), sorted numerically.
# This is the literal "gw0..gwN" evidence NFR-001 asks for — read from the
# run's own report, not inferred from -n's argument or the runner label.
extract_gw_range() {
  local file="$1"
  local tags
  tags="$(grep -oE '^\[gw[0-9]+\]' "${file}" 2>/dev/null | sort -u -t w -k2 -n || true)"
  if [[ -z "${tags}" ]]; then
    echo "NO [gwK] TAGS FOUND IN OUTPUT"
    return 1
  fi
  echo "${tags}" | tr '\n' ' '
  echo ""
  echo "  ($(echo "${tags}" | wc -l) distinct workers actually used)"
}

# Extract just the numeric collected count (M) from whichever form matched.
extract_collected_count() {
  local file="$1"
  local n
  n="$(grep -m1 -oE '^[0-9]+ workers? \[[0-9]+ items?\]' "${file}" 2>/dev/null \
        | grep -oE '\[[0-9]+' | tr -d '[' || true)"
  if [[ -n "${n}" ]]; then
    echo "${n}"
    return 0
  fi
  grep -oE '^[0-9]+ tests? collected' "${file}" | tail -1 | grep -oE '^[0-9]+' || true
}

# Print the per-node-id outcome for a given node-id, taken from the run's
# own report. Under this script's `-v` invocation (see the disclosed
# deviation note above) each test gets its own
# "[gwK] [ N%] PASSED|FAILED <nodeid>" line, so a plain substring grep
# finds it directly. A node-id with no matching line is genuinely absent
# from the collected set (marker-deselected, --ignore-swallowed, or
# renamed) rather than merely un-printed.
#
# Returns 0 ONLY when a "[gwK] [ N%] PASSED <nodeid>" verdict line was
# found and no verdict line for the same node-id says FAILED/ERROR. Returns
# 1 for ABSENT, for a FAILED/ERROR verdict, or for a match with no verdict
# line at all (e.g. only the pre-run announce line matched) — a caller that
# discards this return code will still see the reason printed, but must not
# report success on it.
report_node_outcome() {
  local file="$1"
  local nodeid="$2"
  local hits verdicts nonverdicts
  hits="$(grep -F "${nodeid}" "${file}" || true)"
  if [[ -z "${hits}" ]]; then
    echo "ABSENT (no line in the run's output mentions this node-id)"
    return 1
  fi
  verdicts="$(echo "${hits}" | grep -E '^\[gw[0-9]+\]' || true)"
  nonverdicts="$(echo "${hits}" | grep -vE '^\[gw[0-9]+\]' || true)"
  # Print ALL verdict-bearing ("[gwK] …") lines unconditionally — a prior
  # version capped the whole match set at `head -5`, so a node-id with more
  # than 5 matching lines whose FAILED/ERROR verdict fell past the cut
  # would correctly exit 1 while the printed record showed only PASSED
  # lines. Non-verdict lines (the pre-run announce line) carry no outcome
  # information and are capped; they are noise, not evidence.
  if [[ -n "${nonverdicts}" ]]; then
    echo "${nonverdicts}" | head -2
  fi
  if [[ -n "${verdicts}" ]]; then
    echo "${verdicts}"
  fi
  if [[ -z "${verdicts}" ]]; then
    echo "NO VERDICT LINE (only a pre-run announce line matched; treating as unresolved)"
    return 1
  fi
  if echo "${verdicts}" | grep -qE '\b(FAILED|ERROR)\b'; then
    return 1
  fi
  if ! echo "${verdicts}" | grep -q '\bPASSED\b'; then
    echo "NO PASSED VERDICT (e.g. SKIPPED; treating as unresolved for this guard)"
    return 1
  fi
  return 0
}

# Runs report_node_outcome, logs each output line with the given indent,
# and accumulates any non-zero outcome into the script-global FAIL — the
# thing the prior version of this script omitted. set -o pipefail (top of
# file) makes `report_node_outcome | while …` propagate
# report_node_outcome's own exit status as the pipeline's exit status
# (verified empirically); this function is what actually reads that status
# instead of letting it fall on the floor.
#
# Also increments the script-global CHECKS_RUN on every invocation,
# regardless of outcome — this is what lets the checks-run guard (section 6)
# detect a check_node call site (or an entire loop) having been deleted: a
# PASS with fewer than EXPECTED_CHECKS checks executed is not a real pass,
# per standing-rules.md's "print the input count alongside any 'all checks
# passed'" — measured directly: stripping all 7 call sites while leaving
# this function and everything downstream intact previously produced an
# identical PASS verdict and exit 0 with zero checks run.
check_node() {
  local file="$1"
  local nodeid="$2"
  local indent="${3:-    }"
  local rc
  CHECKS_RUN=$((CHECKS_RUN + 1))
  report_node_outcome "${file}" "${nodeid}" | while IFS= read -r l; do log "${indent}${l}"; done
  rc=$?
  if [[ ${rc} -ne 0 ]]; then
    FAIL=1
  fi
  return "${rc}"
}

run_shard() {
  local name="$1"
  local outfile="$2"
  shift 2
  local start end
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  log "--- running shard: ${name} ---"
  log "start (UTC): ${start}"
  log "command: ${PYTHON} -u -m pytest $*"
  # Full output to a file; we never trust a piped exit status (NFR-003).
  "${PYTHON}" -u -m pytest "$@" > "${outfile}" 2>&1
  local rc=$?
  end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  log "end   (UTC): ${end}"
  log "pytest's own exit code: ${rc} (informational only — the collected"
  log "  count and the count line below are the evidence, not this number)"
  log "output file: ${outfile} ($(wc -l < "${outfile}") lines)"
  if [[ ! -s "${outfile}" ]]; then
    log "FATAL: ${outfile} is EMPTY. An empty output file is no measurement"
    log "  (NFR-003). Aborting shard proof for ${name}."
    return 3
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 4. SYNC shard — copied verbatim (selection) from
#    .github/workflows/ci-quality.yml:1124-1133
# ---------------------------------------------------------------------------
## DISCLOSED DEVIATION FROM ci-quality.yml's LITERAL FLAGS, explained once here:
## ci-quality.yml's actual command carries `-q`. pytest-xdist's worker-count
## header ("N workers [M items]", xdist/dsession.py:498-504 in this repo's
## .venv) is gated purely on `config.option.verbose >= 0` — `-q` sets
## verbose=-1, so the header is UNCONDITIONALLY suppressed under `-q`,
## independent of tty-ness. Separately, under BOTH `-q` and pytest's own
## default verbosity (0), individual PASSED node-ids are never printed at
## all (only dots) — only `-v` (verbose=1) prints one
## "[gwK] [ N%] PASSED <nodeid>" line per test, which is also the literal
## source of the "[gw5]"-style tag quoted in
## notes/sleep-count-attribution.md's own CI-log excerpt. T041 requires each
## of the 13 node-ids' outcome "quoted from the run's own report", which is
## unobtainable under CI's literal `-q`. So this script runs with `-v`
## instead of `-q` — file selection, --ignore set, marker selection, --dist
## mode and --cov are byte-identical to ci-quality.yml; verbosity is the one
## flag this script does not reproduce, and it is the flag that makes
## NFR-001's worker count and T041's per-node-id quoting possible instead of
## assumed absent. Verified empirically in this worktree (see the WP13
## transition note for the exact before/after).
# FAIL accumulates every way this script can find to say "this is not a
# clean, fully-accounted-for pass": an empty/fatal shard run, an absent or
# non-PASSED T041 node-id, or a zero collected count. It is declared here,
# before the first thing that can set it, and never reset to 0 afterwards —
# a prior version of this script re-initialised FAIL=0 in the
# zero-collection-guard section, which silently discarded anything set
# earlier. Initialising to 0 exactly once, here, is what makes accumulation
# (rather than overwriting) the only thing that can happen to it.
FAIL=0

SYNC_OUT="${OUT_DIR}/sync.out"
if ! run_shard "sync (fast-tests-sync)" "${SYNC_OUT}" \
  tests/sync/ -m "fast and not windows_ci" -v --tb=short \
  --ignore=tests/sync/test_orphan_sweep.py \
  --ignore=tests/sync/test_daemon_orphan_classification.py \
  --ignore=tests/sync/test_daemon_cleanup_boundary.py \
  --ignore=tests/sync/test_issue_1071_singleton_reconfirmation.py \
  -n auto --dist loadfile \
  --durations=50 \
  --cov=src/specify_cli/sync
then
  FAIL=1
  log "FATAL: sync shard's run_shard reported failure (see above) — accumulating into overall exit status."
fi

log ""
log "sync shard — pytest's own platform/plugins header (NFR-001, versioned, OBSERVED):"
extract_plugins_header "${SYNC_OUT}" | while IFS= read -r l; do log "  ${l}"; done
SYNC_PLUGINS_RC=$?
if [[ ${SYNC_PLUGINS_RC} -ne 0 ]]; then
  FAIL=1
  log "  FAIL: at least one plugins-header line was absent from the run's own"
  log "    output — folded into overall exit status, not just printed."
fi
log "sync shard — distribution OBSERVED from the run's own report (NFR-001):"
SYNC_WORKERS="$(extract_worker_header "${SYNC_OUT}")"
SYNC_WORKERS_RC=$?
log "  worker header : ${SYNC_WORKERS}"
if [[ ${SYNC_WORKERS_RC} -ne 0 ]]; then
  FAIL=1
  log "  FAIL: worker header absent from the run's own output — folded into"
  log "    overall exit status, not just printed."
fi
log "  gw tags seen  :"
extract_gw_range "${SYNC_OUT}" | while IFS= read -r l; do log "    ${l}"; done
SYNC_GW_RC=$?
if [[ ${SYNC_GW_RC} -ne 0 ]]; then
  FAIL=1
  log "    FAIL: no [gwK] tags observed — folded into overall exit status."
fi
log "  collected     :"
extract_collected_line "${SYNC_OUT}" | while IFS= read -r l; do log "    ${l}"; done
log "  count line    :"
SYNC_COUNT_LINE="$(extract_count_line "${SYNC_OUT}")"
SYNC_COUNT_RC=$?
log "    ${SYNC_COUNT_LINE}"
if [[ ${SYNC_COUNT_RC} -ne 0 ]]; then
  FAIL=1
  log "    FAIL: count line absent from the run's own output — this script"
  log "      names that line as NFR-003's evidence; folded into overall"
  log "      exit status, not just printed."
fi
log "sync shard — declared invocation (this script's own constants, matching"
log "  the argv logged above as \"command: …\"; NOT independently re-derived"
log "  or re-measured from the run — see LOW-4 in the recorded-output note):"
log "  --dist        : loadfile"
log "  marker        : -m \"fast and not windows_ci\""
log "  --ignore (4)  : tests/sync/test_orphan_sweep.py,"
log "                  tests/sync/test_daemon_orphan_classification.py,"
log "                  tests/sync/test_daemon_cleanup_boundary.py,"
log "                  tests/sync/test_issue_1071_singleton_reconfirmation.py"
log "  --cov         : ON (--cov=src/specify_cli/sync)"

# ---------------------------------------------------------------------------
# 5. CLI shard — copied verbatim (selection) from
#    .github/workflows/ci-quality.yml:1540-1546
#    NOTE: CI wraps this with `|| test $? -eq 5` (treats "no tests
#    collected" as success). We deliberately do NOT reproduce that escape
#    hatch — see the zero-collection guard in section 7 below.
# ---------------------------------------------------------------------------
## Same disclosed `-q`-for-`-v` swap as the sync shard above, for the same reason.
CLI_OUT="${OUT_DIR}/cli.out"
# fast-tests-cli (ci-quality.yml) and the later router tests-cli job are both retired; the cli module row is the live executor (FR-008).
if ! run_shard "cli (fast-tests-cli)" "${CLI_OUT}" \
  tests/cli/ tests/specify_cli/cli/ -m "fast and not windows_ci" -v --tb=short \
  -n auto --dist loadfile \
  --durations=50 \
  --cov=src/specify_cli/cli
then
  FAIL=1
  log "FATAL: cli shard's run_shard reported failure (see above) — accumulating into overall exit status."
fi

log ""
log "cli shard — pytest's own platform/plugins header (NFR-001, versioned, OBSERVED):"
extract_plugins_header "${CLI_OUT}" | while IFS= read -r l; do log "  ${l}"; done
CLI_PLUGINS_RC=$?
if [[ ${CLI_PLUGINS_RC} -ne 0 ]]; then
  FAIL=1
  log "  FAIL: at least one plugins-header line was absent from the run's own"
  log "    output — folded into overall exit status, not just printed."
fi
log "cli shard — distribution OBSERVED from the run's own report (NFR-001):"
CLI_WORKERS="$(extract_worker_header "${CLI_OUT}")"
CLI_WORKERS_RC=$?
log "  worker header : ${CLI_WORKERS}"
if [[ ${CLI_WORKERS_RC} -ne 0 ]]; then
  FAIL=1
  log "  FAIL: worker header absent from the run's own output — folded into"
  log "    overall exit status, not just printed."
fi
log "  gw tags seen  :"
extract_gw_range "${CLI_OUT}" | while IFS= read -r l; do log "    ${l}"; done
CLI_GW_RC=$?
if [[ ${CLI_GW_RC} -ne 0 ]]; then
  FAIL=1
  log "    FAIL: no [gwK] tags observed — folded into overall exit status."
fi
log "  collected     :"
extract_collected_line "${CLI_OUT}" | while IFS= read -r l; do log "    ${l}"; done
log "  count line    :"
CLI_COUNT_LINE="$(extract_count_line "${CLI_OUT}")"
CLI_COUNT_RC=$?
log "    ${CLI_COUNT_LINE}"
if [[ ${CLI_COUNT_RC} -ne 0 ]]; then
  FAIL=1
  log "    FAIL: count line absent from the run's own output — this script"
  log "      names that line as NFR-003's evidence; folded into overall"
  log "      exit status, not just printed."
fi
log "cli shard — declared invocation (this script's own constants, matching"
log "  the argv logged above as \"command: …\"; NOT independently re-derived"
log "  or re-measured from the run — see LOW-4 in the recorded-output note):"
log "  --dist        : loadfile"
log "  marker        : -m \"fast and not windows_ci\""
log "  --ignore      : (none — ci-quality.yml's cli shard carries no --ignore)"
log "  --cov         : ON (--cov=src/specify_cli/cli)"

# ---------------------------------------------------------------------------
# 6. The 13 node-ids (or groups) named in WP13-shard-proof.md, T041.
#    Three groups (rows 3-6, 8-9, 10-12) are reconciliation obligations,
#    not flat node-ids — see the WP file. This script prints the collected
#    set for each ambiguous group plus the outcome of each concrete case it
#    identifies, and never invents a node-id to force a count of 13.
# ---------------------------------------------------------------------------
# EXPECTED_CHECKS is the exact number of check_node invocations below: row 1
# (1) + row 2 (1) + rows 3-6 (3, one loop) + row 7 (1) + rows 8-9 (7, one
# loop) + rows 10-12 (3, one loop) + row 13 (1) = 17. Declared here,
# deliberately hardcoded next to the list it counts, so that deleting a
# check_node call site — or an entire `for case in …` loop — makes
# CHECKS_RUN fall below this constant and the checks-run guard below fails
# loudly instead of silently passing on fewer checks. Measured: stripping
# all 7 call sites while leaving check_node and everything downstream
# intact previously produced an identical PASS verdict and exit 0 with zero
# checks run — this constant plus the guard after the loop is what closes
# that hazard (standing-rules.md: "print the input count alongside any
# 'all checks passed'").
readonly EXPECTED_CHECKS=17
CHECKS_RUN=0

log ""
log "=== per-node-id reconciliation (T041/T042) ==="

log ""
log "[1] tests/cli/commands/test_sync_status_per_project_3030.py::test_status_names_every_project_with_count_age_and_consent"
check_node "${CLI_OUT}" "tests/cli/commands/test_sync_status_per_project_3030.py::test_status_names_every_project_with_count_age_and_consent" "    "

log ""
log "[2] tests/cli/commands/test_sync_doctor_per_project_3030.py::test_doctor_names_every_project_with_count_age_and_consent"
check_node "${CLI_OUT}" "tests/cli/commands/test_sync_doctor_per_project_3030.py::test_doctor_names_every_project_with_count_age_and_consent" "    "

log ""
log "[3-6] tests/cli/commands/test_sync_doctor_consent_health_3030.py — issue says 4 param"
log "      cases; the file's only parametrisation"
log "      (test_doctor_names_the_action_for_each_project_local_fault_kind) collects 3."
log "      Reconciliation: reporting the 3 actual param-case outcomes, not inventing a 4th."
for case in \
  "test_doctor_names_the_action_for_each_project_local_fault_kind[unparseable-project:" \
  "test_doctor_names_the_action_for_each_project_local_fault_kind[wrong_shape-" \
  "test_doctor_names_the_action_for_each_project_local_fault_kind[unusable-"
do
  log "    case: ${case}"
  check_node "${CLI_OUT}" "${case}" "      "
done

log ""
log "[7] tests/cli/commands/test_sync_migrate_backfills_h4.py::test_the_consent_backfill_reports_records_it_could_not_resolve"
check_node "${CLI_OUT}" "tests/cli/commands/test_sync_migrate_backfills_h4.py::test_the_consent_backfill_reports_records_it_could_not_resolve" "    "

log ""
log "[8-9] tests/cli/commands/test_sync_purge_3030.py::TestPurgeAll — issue says 2; the"
log "      class collects 7. Reconciliation: running/reporting all 7, not guessing which 2."
for case in \
  "TestPurgeAll::test_apply_all_without_the_confirmation_phrase_deletes_nothing" \
  "TestPurgeAll::test_apply_all_with_the_wrong_phrase_deletes_nothing" \
  "TestPurgeAll::test_confirmed_all_empties_the_machine_global_stores_and_this_checkout" \
  "TestPurgeAll::test_all_reaches_the_body_rows_no_targeted_selector_could" \
  "TestPurgeAll::test_the_all_dry_run_predicts_exactly_what_the_confirmed_run_deletes" \
  "TestPurgeAll::test_all_names_the_per_checkout_scope_and_claims_nothing_wider" \
  "TestPurgeAll::test_help_does_not_promise_machine_wide_erasure"
do
  log "    case: ${case}"
  check_node "${CLI_OUT}" "${case}" "      "
done

log ""
log "[10-12] tests/sync/test_consent_write_refusal_3030.py::test_a_refused_write_is_reported_rather_than_raised_out_of_the_cli"
log "        — the only 3-wide parametrisation in the file (opt-in / opt-out / server)."
for case in \
  "test_a_refused_write_is_reported_rather_than_raised_out_of_the_cli[opt-in]" \
  "test_a_refused_write_is_reported_rather_than_raised_out_of_the_cli[opt-out]" \
  "test_a_refused_write_is_reported_rather_than_raised_out_of_the_cli[server]"
do
  log "    case: ${case}"
  check_node "${SYNC_OUT}" "${case}" "      "
done

log ""
log "[13] tests/sync/tracker/test_saas_client.py::TestRetryBehaviors::test_429_respects_retry_after"
log "     (the sync half's own case; per notes/sleep-count-attribution.md this node-id has"
log "     never itself exhibited the #3115/sleep-count failure — reported regardless.)"
check_node "${SYNC_OUT}" "tests/sync/tracker/test_saas_client.py::TestRetryBehaviors::test_429_respects_retry_after" "    "

log ""
log "=== checks-run guard (HIGH-1: erosion hazard for the T041 list) ==="
# -ne, not -lt: -lt only catches shrinkage. -ne also catches substitution at
# CHANGED cardinality — remove one check_node call site, add two others,
# land on 18, and -lt would pass while an intended node-id went unchecked.
# Measured: duplicating one call site yields "18/17" and, under -lt, exit 0;
# under -ne it correctly fails. -ne is strictly stronger for one character.
#
# What -ne does NOT catch, by construction: substitution at CONSTANT
# cardinality — swap one node-id's check_node call for a different node-id
# and CHECKS_RUN stays exactly 17. A count is a cardinality check, not an
# identity check. "17/17" means seventeen checks ran; it does not mean they
# were *these* seventeen — the node-id text logged next to each PASSED
# verdict above is what establishes identity, not this guard.
if [[ "${CHECKS_RUN}" -ne "${EXPECTED_CHECKS}" ]]; then
  FAIL=1
  log "FAIL: ${CHECKS_RUN}/${EXPECTED_CHECKS} T041 node-id checks were executed (expected exactly ${EXPECTED_CHECKS})."
  log "  EXPECTED_CHECKS is a hardcoded constant declared next to the node-id"
  log "  list precisely so a deleted (or added) check_node call site is loud"
  log "  rather than silently passing on a different number of checks."
else
  log "OK: ${CHECKS_RUN}/${EXPECTED_CHECKS} T041 node-id checks executed."
fi

# ---------------------------------------------------------------------------
# 7. Zero-collection guard (NFR-008 / the ci-quality.yml `|| test $? -eq 5`
#    hazard this WP exists to not reproduce)
# ---------------------------------------------------------------------------
log ""
log "=== zero-collection guard ==="
# COLLECTION_FAIL is scoped to this guard alone, so the "both shards
# collected" message below stays accurate to what it claims regardless of
# whether an earlier T041 node-id check already set the script-global FAIL.
# It is still folded into FAIL, same as every other failure mode.
COLLECTION_FAIL=0

SYNC_COLLECTED_N="$(extract_collected_count "${SYNC_OUT}")"
CLI_COLLECTED_N="$(extract_collected_count "${CLI_OUT}")"

if [[ -z "${SYNC_COLLECTED_N}" || "${SYNC_COLLECTED_N}" -eq 0 ]]; then
  log "FAIL: sync shard collected 0 (or unparseable) tests. A shard that did not run,"
  log "  or collected nothing, is not evidence — refusing to report a green."
  COLLECTION_FAIL=1
else
  log "OK: sync shard collected ${SYNC_COLLECTED_N} tests (non-zero)."
fi

if [[ -z "${CLI_COLLECTED_N}" || "${CLI_COLLECTED_N}" -eq 0 ]]; then
  log "FAIL: cli shard collected 0 (or unparseable) tests. ci-quality.yml's"
  log "  '|| test \$? -eq 5' would call this success; this script does not."
  COLLECTION_FAIL=1
else
  log "OK: cli shard collected ${CLI_COLLECTED_N} tests (non-zero)."
fi
if [[ "${COLLECTION_FAIL}" -eq 1 ]]; then
  FAIL=1
fi

log ""
log "=== NFR-008: input counts beside any all-checks-passed claim ==="
log "sync shard input count: ${SYNC_COLLECTED_N:-UNKNOWN}"
log "cli shard input count:  ${CLI_COLLECTED_N:-UNKNOWN}"

if [[ "${COLLECTION_FAIL}" -eq 0 ]]; then
  log ""
  log "Both shards collected a non-zero number of tests"
  log "(sync=${SYNC_COLLECTED_N}, cli=${CLI_COLLECTED_N}). This is NOT a claim that"
  log "all tests passed — see the count lines and per-node-id reconciliation above"
  log "for the actual outcomes. A caller must read those, not this guard, to know"
  log "whether the 13 node-ids passed."
fi

log ""
log "=== overall verdict ==="
if [[ "${FAIL}" -eq 0 ]]; then
  log "PASS: both shards ran, both collected non-zero, ${CHECKS_RUN}/${EXPECTED_CHECKS}"
  log "  T041 node-id checks executed and every one resolved to a PASSED"
  log "  verdict line with no FAILED/ERROR/ABSENT among them, and both"
  log "  shards' plugins-header and worker-header evidence was present."
else
  log "FAIL: at least one of — an empty/fatal shard run, a T041 node-id-check"
  log "  count other than ${EXPECTED_CHECKS} (${CHECKS_RUN} ran), a T041 node-id that was"
  log "  ABSENT or resolved to FAILED/ERROR, a zero collected count, or"
  log "  missing plugins-header/worker-header/gw-tags/count-line evidence —"
  log "  occurred. See the sections above for which."
  log "  This script's own exit code reflects this verdict; it is not just a"
  log "  printed line a caller can miss."
fi

log ""
log "=== done ==="
log "sync shard wall-clock window and cli shard wall-clock window are both printed"
log "above (start/end, UTC) so a same-machine collision with any other test run is"
log "reconstructable (NFR-004)."

exit "${FAIL}"
