#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 \"<test instructions>\"" >&2
  echo "How to run: ./codex_superpower_session.sh \"test the open_url runtime wiring end to end and fix failures\"" >&2
  exit 1
fi

TEST_INSTRUCTIONS="$*"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTING_SUFFIX="make sure this works, track the data flow, find the root cause if there are errors and solve them"

codex exec \
  --cd "$REPO_ROOT" \
  --dangerously-bypass-approvals-and-sandbox \
  - <<EOF
Start a fresh Codex session and do \$writing-plans.
Do not ask clarifying questions.
If there are design decisions to make, make them.
There should be exactly one superpowers spec for this work in docs/superpowers/specs.
Use that single spec instead of creating multiple superpowers specs.
EOF

codex exec \
  --cd "$REPO_ROOT" \
  --dangerously-bypass-approvals-and-sandbox \
  - <<EOF
Start a fresh Codex session and do \$executing-plans.
There should be exactly one superpowers plan for this work in docs/superpowers/plans.
Use that single plan instead of creating or selecting multiple superpowers plans.
EOF

codex exec \
  --cd "$REPO_ROOT" \
  --dangerously-bypass-approvals-and-sandbox \
  - <<EOF
Start a fresh Codex session for the first testing pass.
Focus on testing and fixing the requested work.
User request: $TEST_INSTRUCTIONS
$TESTING_SUFFIX
EOF

codex exec \
  --cd "$REPO_ROOT" \
  --dangerously-bypass-approvals-and-sandbox \
  - <<EOF
Start a fresh Codex session for the second testing pass.
Re-test the full requested work end to end after the earlier sessions.
Fix any remaining issues you find, then verify the final runtime behavior again.
User request: $TEST_INSTRUCTIONS
$TESTING_SUFFIX
EOF

codex exec \
  --cd "$REPO_ROOT" \
  --dangerously-bypass-approvals-and-sandbox \
  - <<EOF
Start a fresh final Codex session for cleanup after the planning, execution, and testing sessions.
Review the end-to-end flow for this requested work and identify code that is now obsolete, dead, or unused.
Use \$code-simplifier to simplify or remove that obsolete code without changing behavior.
Use git diff, git log, and the current runtime paths to verify what changed and what is still needed.
Do not broaden scope beyond cleanup that is justified by the current request.
EOF
