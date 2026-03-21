#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ralph-build [N]
  ralph-build [--max-iterations N]

Runs a loop of Codex build+cleanup sessions. If N or --max-iterations is set,
the loop stops after that total number of iterations. Use 0 for infinite
(default: 0).

Options:
  N                     Total iterations to run (default: 0)
  --max-iterations N    Safety cap on iterations (default: 0)
USAGE
}

max_iterations=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations)
      if [[ $# -lt 2 ]]; then
        echo "Error: --max-iterations requires a value." >&2
        exit 1
      fi
      max_iterations="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    ''|*[!0-9]*)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ "$max_iterations" -ne 0 ]]; then
        echo "Error: max iterations specified more than once." >&2
        exit 1
      fi
      max_iterations="$1"
      shift
      ;;
  esac
done

if ! [[ "$max_iterations" =~ ^[0-9]+$ ]]; then
  echo "Error: --max-iterations must be a non-negative integer." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$ROOT_DIR/build_prompt.md"
IMPLEMENTATION_PLAN_FILE="$ROOT_DIR/implementation_plan.md"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Missing build_prompt.md at $PROMPT_FILE" >&2
  exit 1
fi

if [[ ! -f "$IMPLEMENTATION_PLAN_FILE" ]]; then
  echo "Missing implementation_plan.md at $IMPLEMENTATION_PLAN_FILE" >&2
  exit 1
fi

iter=1
while [[ "$max_iterations" -eq 0 || "$iter" -le "$max_iterations" ]]; do
  current_section="$(awk -F': ' '/^Current Section:/ { print $2; exit }' "$IMPLEMENTATION_PLAN_FILE")"

  if ! [[ "${current_section:-}" =~ ^[0-9]+$ ]]; then
    echo "Failed to read a valid Current Section from $IMPLEMENTATION_PLAN_FILE" >&2
    exit 1
  fi

  codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    - <<EOF
@${ROOT_DIR}/AGENTS.md
@${PROMPT_FILE}
@${IMPLEMENTATION_PLAN_FILE}

You are executing iteration ${iter}.
Start immediately on Current Section ${current_section} from implementation_plan.md.
Do not stop after merely summarizing or acknowledging files. Read the current section, implement it, run the listed tests, confirm the success conditions in the section's How to Test text, then update Current Section only if the section is fully complete.
EOF

  codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    - <<'EOF'
Please review recent changes on this branch (last few hours). Use git log/diff to identify what was modified, then simplify and clean up the changed code without altering behavior. Use $code-simplifier to drive the cleanup.
EOF

  iter=$((iter + 1))
done

if [[ "$max_iterations" -ne 0 ]]; then
  echo "Reached max iterations ($max_iterations). Stopping loop."
fi
