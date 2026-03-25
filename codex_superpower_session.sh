#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <writing-plans|executing-plans|testing> <request...>" >&2
  exit 1
fi

MODE="$1"
shift
REQUEST="$*"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTING_SUFFIX="make sure this works, track the data flow, find the root cause if there are errors and solve them"
PROMPT=""

run_codex_session() {
  codex exec \
    --cd "$REPO_ROOT" \
    --dangerously-bypass-approvals-and-sandbox \
    - <<EOF
$PROMPT
EOF
}

set_writing_plans_prompt() {
  PROMPT=$(cat <<EOF
Start a fresh Codex session and do \$writing-plans.
Do not ask clarifying questions.
If there are design decisions to make, make them.
There should be exactly one superpowers spec for this work in docs/superpowers/specs.
Use that single spec instead of creating multiple superpowers specs.

User request: $REQUEST
EOF
)
}

set_executing_plans_prompt() {
  PROMPT=$(cat <<EOF
Start a fresh Codex session and do \$executing-plans.
There should be exactly one superpowers plan for this work in docs/superpowers/plans.
Use that single plan instead of creating or selecting multiple superpowers plans.

User request: $REQUEST
EOF
)
}

set_testing_prompt() {
  PROMPT=$(cat <<EOF
Start a fresh Codex session and focus on testing and fixing the requested work.
User request: $REQUEST
$TESTING_SUFFIX
EOF
)
}

case "$MODE" in
  writing-plans)
    set_writing_plans_prompt
    ;;
  executing-plans)
    set_executing_plans_prompt
    ;;
  testing)
    set_testing_prompt
    ;;
  *)
    echo "Invalid mode: $MODE" >&2
    echo "Expected one of: writing-plans, executing-plans, testing" >&2
    exit 1
    ;;
esac

run_codex_session
