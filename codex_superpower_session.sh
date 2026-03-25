#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <writing-plans|executing-plans|testing> <request...>" >&2
  echo "How to run: ./codex_superpower_session.sh executing-plans fix the open_url runtime wiring" >&2
  exit 1
fi

MODE="$1"
shift
REQUEST="$*"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTING_SUFFIX="make sure this works, track the data flow, find the root cause if there are errors and solve them"

case "$MODE" in
  writing-plans)
    codex exec \
      --cd "$REPO_ROOT" \
      --dangerously-bypass-approvals-and-sandbox \
      - <<EOF
Start a fresh Codex session and do \$writing-plans.
Do not ask clarifying questions.
If there are design decisions to make, make them.
There should be exactly one superpowers spec for this work in docs/superpowers/specs.
Use that single spec instead of creating multiple superpowers specs.

User request: $REQUEST
EOF
    ;;
  executing-plans)
    codex exec \
      --cd "$REPO_ROOT" \
      --dangerously-bypass-approvals-and-sandbox \
      - <<EOF
Start a fresh Codex session and do \$executing-plans.
There should be exactly one superpowers plan for this work in docs/superpowers/plans.
Use that single plan instead of creating or selecting multiple superpowers plans.

User request: $REQUEST
EOF
    ;;
  testing)
    codex exec \
      --cd "$REPO_ROOT" \
      --dangerously-bypass-approvals-and-sandbox \
      - <<EOF
Start a fresh Codex session and focus on testing and fixing the requested work.
User request: $REQUEST
$TESTING_SUFFIX
EOF
    ;;
  *)
    echo "Invalid mode: $MODE" >&2
    echo "Expected one of: writing-plans, executing-plans, testing" >&2
    exit 1
    ;;
esac

codex exec \
  --cd "$REPO_ROOT" \
  --dangerously-bypass-approvals-and-sandbox \
  - <<EOF
Start a fresh final Codex session for cleanup after the main $MODE session.
Review the end-to-end flow for this requested work and identify code that is now obsolete, dead, or unused.
Use \$code-simplifier to simplify or remove that obsolete code without changing behavior.
Use git diff, git log, and the current runtime paths to verify what changed and what is still needed.
Do not broaden scope beyond cleanup that is justified by the current request.

User request: $REQUEST
EOF
