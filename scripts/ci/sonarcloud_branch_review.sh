#!/usr/bin/env bash
#
# sonarcloud_branch_review.sh — read-only SonarCloud review tool.
#
# Queries SonarCloud's public REST API for the spec-kitty project and prints
# parseable summaries for quality gate, coverage, per-file uncovered lines,
# open issues, and the analysed project version / new-code baseline history.
#
# Read-only by construction: every call is an HTTP GET against the public API
# (curl --get). The tool never writes, creates, updates, or removes any
# SonarCloud resource, and never requires SONAR_TOKEN — the public read
# endpoints for this public project are reachable unauthenticated. A token, if
# present in the environment, is passed through for higher rate limits only; it
# is never mandatory.
#
# Sibling of scripts/ci/quality_gate_decision.py. See mission
# sonar-qa-config-remediation-01KWYCX7 (FR-005, FR-006, NFR-001, SC-003) and
# tests/ci/test_sonarcloud_branch_review.py for the token-free smoke test.

set -euo pipefail

readonly DEFAULT_PROJECT_KEY="spec-kitty_spec-kitty"
readonly DEFAULT_BASE_URL="https://sonarcloud.io"

SONAR_BASE_URL="${SONARCLOUD_URL:-${DEFAULT_BASE_URL}}"
PROJECT_KEY="${SONAR_PROJECT_KEY:-${DEFAULT_PROJECT_KEY}}"
ISSUE_RULE=""
ISSUE_FILE=""

usage() {
  cat <<'EOF'
Usage: sonarcloud_branch_review.sh [--project KEY] <subcommand> [args]

Read-only SonarCloud queries over the public REST API (no token required).

Subcommands:
  quality-gate                    Quality gate status + failing conditions
  coverage                        Overall + new-code coverage measures
  uncovered <file>                Uncovered-line metrics for one file
  issues [--rule R] [--file F]    Open issues, optionally by rule and/or file
  version | analyses              Analysed projectVersion + new-code baseline

Global options:
  -p, --project KEY   Project key (default: spec-kitty_spec-kitty)
  -h, --help          Show this help and exit

Environment:
  SONAR_PROJECT_KEY   Override the project key (default: spec-kitty_spec-kitty)
  SONARCLOUD_URL      Override the API base URL (default: https://sonarcloud.io)
  SONAR_TOKEN         Optional; public reads work without it
EOF
}

die() {
  local msg="$1"
  local code="${2:-1}"
  printf 'error: %s\n' "${msg}" >&2
  exit "${code}"
}

require_deps() {
  local dep
  for dep in curl jq; do
    if ! command -v "${dep}" >/dev/null 2>&1; then
      die "required dependency not found on PATH: ${dep}" 127
    fi
  done
}

# _http_get <api-path> [curl --data-urlencode args...]
#
# Issues a single read-only GET and echoes the response body on stdout. The
# method is pinned to GET via --get, so any --data-urlencode pairs are encoded
# into the query string rather than a request body. Fails loudly on any non-200
# status so callers never silently parse an error page.
_http_get() {
  local api_path="$1"
  shift
  local url="${SONAR_BASE_URL}${api_path}"

  local -a auth=()
  if [[ -n "${SONAR_TOKEN:-}" ]]; then
    auth+=(--user "${SONAR_TOKEN}:")
  fi

  local response
  if ! response="$(curl --silent --show-error --get \
    --write-out $'\n%{http_code}' \
    "${auth[@]}" \
    "${url}" "$@")"; then
    die "network error contacting ${url}" 1
  fi

  local http_code="${response##*$'\n'}"
  local body="${response%$'\n'*}"
  if [[ "${http_code}" != "200" ]]; then
    die "SonarCloud API returned HTTP ${http_code} for ${api_path}" 1
  fi
  printf '%s\n' "${body}"
}

cmd_quality_gate() {
  printf '== SonarCloud quality gate: %s ==\n' "${PROJECT_KEY}"
  _http_get "/api/qualitygates/project_status" \
    --data-urlencode "projectKey=${PROJECT_KEY}" \
    | jq -r '.projectStatus
        | "status: \(.status)",
          (.conditions[]
             | "condition: \(.metricKey) status=\(.status) actual=\(.actualValue) comparator=\(.comparator) threshold=\(.errorThreshold)")'
}

cmd_coverage() {
  printf '== Coverage: %s ==\n' "${PROJECT_KEY}"
  _http_get "/api/measures/component" \
    --data-urlencode "component=${PROJECT_KEY}" \
    --data-urlencode "metricKeys=coverage,new_coverage" \
    | jq -r '.component.measures[]
        | "\(.metric): \(.value // .period.value // (.periods[0].value) // "n/a")"'
}

cmd_uncovered() {
  local file="$1"
  printf '== Uncovered lines: %s:%s ==\n' "${PROJECT_KEY}" "${file}"
  _http_get "/api/measures/component" \
    --data-urlencode "component=${PROJECT_KEY}:${file}" \
    --data-urlencode "metricKeys=uncovered_lines,coverage,lines_to_cover" \
    | jq -r '.component.measures[] | "\(.metric): \(.value // "n/a")"'
}

cmd_issues() {
  local component="${PROJECT_KEY}"
  if [[ -n "${ISSUE_FILE}" ]]; then
    component="${PROJECT_KEY}:${ISSUE_FILE}"
  fi

  local -a params=(
    --data-urlencode "componentKeys=${component}"
    --data-urlencode "resolved=false"
    --data-urlencode "ps=100"
  )
  if [[ -n "${ISSUE_RULE}" ]]; then
    params+=(--data-urlencode "rules=${ISSUE_RULE}")
  fi

  printf '== Issues: %s (rule=%s file=%s) ==\n' \
    "${PROJECT_KEY}" "${ISSUE_RULE:-any}" "${ISSUE_FILE:-any}"
  _http_get "/api/issues/search" "${params[@]}" \
    | jq -r '"total: \(.total)",
        (.issues[]
           | "\(.rule) [\(.severity)] \(.component):\(.line // "-") \(.message)")'
}

cmd_version() {
  local analyses components
  analyses="$(_http_get "/api/project_analyses/search" \
    --data-urlencode "project=${PROJECT_KEY}" \
    --data-urlencode "ps=10")"
  components="$(_http_get "/api/components/show" \
    --data-urlencode "component=${PROJECT_KEY}")"

  printf '== Project version / analyses: %s ==\n' "${PROJECT_KEY}"
  printf 'latest_analysis_version: %s\n' \
    "$(jq -r '.analyses[0].projectVersion // "unknown"' <<<"${analyses}")"
  printf 'latest_analysis_date: %s\n' \
    "$(jq -r '.analyses[0].date // "unknown"' <<<"${analyses}")"
  printf 'component_last_analysis: %s\n' \
    "$(jq -r '.component.analysisDate // "unknown"' <<<"${components}")"
  printf 'new_code_baseline (analysis history, newest first):\n'
  jq -r '.analyses[] | "  \(.date) version=\(.projectVersion)"' <<<"${analyses}"
}

parse_issue_flags() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --rule)
        [[ $# -ge 2 ]] || die "--rule requires a value" 2
        ISSUE_RULE="$2"
        shift 2
        ;;
      --file)
        [[ $# -ge 2 ]] || die "--file requires a value" 2
        ISSUE_FILE="$2"
        shift 2
        ;;
      *)
        die "unknown issues option: $1" 2
        ;;
    esac
  done
}

main() {
  local subcommand=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        return 0
        ;;
      -p|--project)
        [[ $# -ge 2 ]] || die "--project requires a value" 2
        PROJECT_KEY="$2"
        shift 2
        ;;
      --)
        shift
        break
        ;;
      -*)
        die "unknown option: $1" 2
        ;;
      *)
        subcommand="$1"
        shift
        break
        ;;
    esac
  done

  [[ -n "${subcommand}" ]] || { usage >&2; die "missing subcommand" 2; }

  require_deps

  case "${subcommand}" in
    quality-gate)
      cmd_quality_gate
      ;;
    coverage)
      cmd_coverage
      ;;
    uncovered)
      [[ $# -ge 1 ]] || die "uncovered requires a <file> argument" 2
      cmd_uncovered "$1"
      ;;
    issues)
      parse_issue_flags "$@"
      cmd_issues
      ;;
    version|analyses)
      cmd_version
      ;;
    *)
      die "unknown subcommand: ${subcommand}" 2
      ;;
  esac
}

main "$@"
