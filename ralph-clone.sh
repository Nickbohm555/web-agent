#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ralph-clone.sh <company-url> <max-iterations>

Runs the feature-harvesting loop using `prompt_clone.md`.

Arguments:
  company-url         Company URL to inspect for features
  max-iterations      Maximum total iterations to run
  -h, --help          Show this help text

Behavior:
  - Uses the current working directory as the target repo/workspace.
  - Uses `./clone.md` in the target repo root as the feature log.
  - Stops early if `.feature_scrape_done` appears in the target repo root.
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$(pwd)"
PROMPT_FILE="$ROOT_DIR/prompt_clone.md"
AGENTS_FILE="$TARGET_DIR/AGENTS.md"

company_url=""
max_iterations=0

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$company_url" ]]; then
        company_url="$1"
        shift
        continue
      fi

      if [[ "$max_iterations" -eq 0 ]]; then
        max_iterations="$1"
        shift
        continue
      fi

      echo "Error: too many arguments." >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$company_url" ]]; then
  echo "Error: company-url is required." >&2
  usage
  exit 1
fi

if [[ "$max_iterations" -eq 0 ]]; then
  echo "Error: max-iterations is required." >&2
  usage
  exit 1
fi

clone_log_path="$TARGET_DIR/clone.md"

if ! [[ "$max_iterations" =~ ^[0-9]+$ ]] || [[ "$max_iterations" -le 0 ]]; then
  echo "Error: max-iterations must be a positive integer." >&2
  exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Missing prompt_clone.md at $PROMPT_FILE" >&2
  exit 1
fi

mkdir -p "$(dirname "$clone_log_path")"
touch "$clone_log_path"

done_marker="$TARGET_DIR/.feature_scrape_done"

iter=1
while [[ "$iter" -le "$max_iterations" ]]; do
  if [[ -f "$done_marker" ]]; then
    echo "Found $done_marker. Stopping feature loop."
    break
  fi

  echo "=================================================="
  echo "Ralph clone iteration: $iter"
  echo "Company URL: $company_url"
  echo "Clone log: $clone_log_path"
  echo "Target repo: $TARGET_DIR"
  [[ -f "$AGENTS_FILE" ]] && echo "Agents: $AGENTS_FILE"
  [ "$max_iterations" -gt 0 ] && echo "Max iterations: $max_iterations"
  echo "=================================================="

  codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    -C "$TARGET_DIR" \
    - <<EOF
$(if [[ -f "$AGENTS_FILE" ]]; then printf '@%s\n' "$AGENTS_FILE"; fi)@${PROMPT_FILE}

Company URL: ${company_url}
Feature log path: ${clone_log_path}

Start immediately. Read the existing feature log, find exactly one new feature not already recorded, and append it to the feature log. If no new feature can be found, create .feature_scrape_done in the target repo root and explain why.
EOF

  if [[ -f "$done_marker" ]]; then
    echo "Feature loop completed; done marker created."
    break
  fi

  iter=$((iter + 1))
done

if [[ "$iter" -gt "$max_iterations" ]]; then
  echo "Reached max iterations ($max_iterations). Stopping loop."
fi
