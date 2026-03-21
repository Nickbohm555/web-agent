#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ralph-build [--max-iterations N]

Runs a loop of Codex build+cleanup sessions. If --max-iterations is set,
the loop stops after N iterations. Use 0 for infinite (default: 0).

Options:
  --max-iterations N    Safety cap on iterations (default: 0)
USAGE
}

max_iterations=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations)
      max_iterations="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! [[ "$max_iterations" =~ ^[0-9]+$ ]]; then
  echo "Error: --max-iterations must be a non-negative integer." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$ROOT_DIR/build_prompt.md"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Missing build_prompt.md at $PROMPT_FILE" >&2
  exit 1
fi

iter=1
while [[ "$max_iterations" -eq 0 || "$iter" -le "$max_iterations" ]]; do
  codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    - <<EOF
@${ROOT_DIR}/AGENTS.md
@${PROMPT_FILE}
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
