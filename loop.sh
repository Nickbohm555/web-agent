#!/usr/bin/env bash
set -euo pipefail

PROMPT_FILE="${PROMPT_FILE:-PROMPT_build.md}"
AGENTS_FILE="AGENTS.md"
MAX_ITERATIONS=0
AGENT_CMD="codex exec --sandbox danger-full-access -"
REQUIRE_COMMIT_PER_ITERATION="${REQUIRE_COMMIT_PER_ITERATION:-1}"
CODEX_CONTEXT_WINDOW="${CODEX_CONTEXT_WINDOW:-400000}"

if ! [[ "$CODEX_CONTEXT_WINDOW" =~ ^[0-9]+$ ]] || [ "$CODEX_CONTEXT_WINDOW" -le 0 ]; then
  echo "Error: CODEX_CONTEXT_WINDOW must be a positive integer."
  exit 1
fi

is_codex_exec_command() {
  [[ "${AGENT_CMD:-}" == codex\ exec* ]]
}

build_codex_exec_command() {
  local cmd="$AGENT_CMD"
  if [[ ! "$cmd" =~ (^|[[:space:]])-($|[[:space:]]) ]]; then
    cmd="$cmd -"
  fi
  printf '%s' "$cmd"
}

if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
  MAX_ITERATIONS="$1"
elif [ -n "${1:-}" ]; then
  echo "Usage: ./loop.sh [max_iterations]"
  exit 1
fi

if ! [[ "$MAX_ITERATIONS" =~ ^[0-9]+$ ]]; then
  echo "Error: max iterations must be a non-negative integer."
  exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
  if [ "$PROMPT_FILE" = "PROMPT_build.md" ] && [ -f "prompt_build.md" ]; then
    PROMPT_FILE="prompt_build.md"
  elif [ "$PROMPT_FILE" = "prompt_build.md" ] && [ -f "PROMPT_build.md" ]; then
    PROMPT_FILE="PROMPT_build.md"
  else
    echo "Error: prompt file not found: $PROMPT_FILE"
    exit 1
  fi
fi

if [ ! -f "$AGENTS_FILE" ]; then
  echo "Error: agents file not found: $AGENTS_FILE"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: Ralph loop must run inside a git repository."
  exit 1
fi

if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "Error: working tree is dirty before the loop starts."
  echo "Commit, stash, or discard changes before running Ralph."
  exit 1
fi

ITERATION=0
while :; do
  ITERATION=$((ITERATION + 1))
  START_HEAD="$(git rev-parse --verify HEAD 2>/dev/null || true)"
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  LOOP_STATE_DIR="$REPO_ROOT/.git/ralph-loop"
  LOOP_MSG="$REPO_ROOT/.loop-commit-msg"
  LOOP_FULL="$REPO_ROOT/.loop-commit-msg.full"
  mkdir -p "$LOOP_STATE_DIR"
  rm -f "$LOOP_MSG" "$LOOP_FULL"
  echo "=================================================="
  echo "Ralph loop iteration: $ITERATION"
  echo "Prompt: $PROMPT_FILE"
  echo "Agents: $AGENTS_FILE"
  if is_codex_exec_command; then
    echo "Codex context window: $CODEX_CONTEXT_WINDOW"
  fi
  [ "$MAX_ITERATIONS" -gt 0 ] && echo "Max iterations: $MAX_ITERATIONS"
  echo "=================================================="

  cat "$PROMPT_FILE" "$AGENTS_FILE" | eval "$(build_codex_exec_command)"

  END_HEAD="$(git rev-parse --verify HEAD 2>/dev/null || true)"
  if [ "$START_HEAD" != "$END_HEAD" ]; then
    echo "Error: iteration $ITERATION changed git history directly."
    echo "The agent must not create commits. Write .loop-commit-msg and let loop.sh commit."
    exit 1
  fi

  if [ ! -f "$LOOP_MSG" ]; then
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
      echo "Error: iteration $ITERATION produced changes but did not write .loop-commit-msg."
      echo "The agent must provide the exact commit subject in .loop-commit-msg."
      exit 1
    fi
  else
    NONEMPTY_LINE_COUNT="$(grep -cve '^[[:space:]]*$' "$LOOP_MSG" || true)"
    if [ "$NONEMPTY_LINE_COUNT" -ne 1 ]; then
      echo "Error: .loop-commit-msg must contain exactly one non-empty line."
      exit 1
    fi

    COMMIT_SUBJECT="$(grep -v '^[[:space:]]*$' "$LOOP_MSG" | head -1 | tr -d '\r')"
    if [ -z "$COMMIT_SUBJECT" ]; then
      echo "Error: .loop-commit-msg is empty."
      exit 1
    fi

    if [[ ! "$COMMIT_SUBJECT" =~ ^[0-9]{2}-[0-9]{2}-task[0-9]+$ && ! "$COMMIT_SUBJECT" =~ ^[0-9]{2}-[0-9]{2}-test[0-9]+$ && ! "$COMMIT_SUBJECT" =~ ^[0-9]{2}-[0-9]{2}-summary$ ]]; then
      echo "Error: .loop-commit-msg does not match the required convention."
      echo "Message: $COMMIT_SUBJECT"
      exit 1
    fi

    if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
      echo "Error: .loop-commit-msg exists but there are no file changes to commit."
      exit 1
    fi

    printf '%s\n' "$COMMIT_SUBJECT" > "$LOOP_FULL"
    git add -A
    git commit -F "$LOOP_FULL"
    rm -f "$LOOP_MSG" "$LOOP_FULL"
  fi

  FINAL_HEAD="$(git rev-parse --verify HEAD 2>/dev/null || true)"
  if [ "$REQUIRE_COMMIT_PER_ITERATION" = "1" ] && [ "$START_HEAD" = "$FINAL_HEAD" ]; then
    echo "Error: iteration $ITERATION did not create a commit."
    echo "Write .loop-commit-msg so loop.sh can create the required commit."
    exit 1
  fi

  LAST_SUBJECT="$(git log -1 --pretty=%s 2>/dev/null || true)"
  if [[ ! "$LAST_SUBJECT" =~ ^[0-9]{2}-[0-9]{2}-task[0-9]+$ && ! "$LAST_SUBJECT" =~ ^[0-9]{2}-[0-9]{2}-test[0-9]+$ && ! "$LAST_SUBJECT" =~ ^[0-9]{2}-[0-9]{2}-summary$ ]]; then
    echo "Error: latest commit does not match the required history convention."
    echo "Latest commit: $LAST_SUBJECT"
    exit 1
  fi

  git push -u origin "$(git branch --show-current)"

  if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
    echo "Reached max iterations ($MAX_ITERATIONS)."
    break
  fi
done
