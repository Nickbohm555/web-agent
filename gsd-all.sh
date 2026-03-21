#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  gsd-all plan N [--repo PATH]
  gsd-all plan 1,3,4 [--repo PATH]
  gsd-all execute N [--repo PATH]
  gsd-all execute 1,3,4 [--repo PATH]

Modes:
  plan      Run $gsd-plan-phase in parallel, then $gsd-execute-phase sequentially
  execute   Run $gsd-execute-phase sequentially (no planning)

Phase input:
  N         Run phases 1..N
  1,3,4     Run explicit phases

Options:
  --repo PATH     Repo root (default: current working directory)

Examples:
  ./gsd-all plan 5
  ./gsd-all execute 4,5,6 --repo /path/to/repo
USAGE
}

repo="$(pwd)"
mode=""
phase_arg=""
count=""
phases_csv=""

if [[ $# -gt 0 ]]; then
  mode="$1"
  shift
fi

if [[ -z "$mode" ]]; then
  echo "Error: Missing mode (plan|execute)." >&2
  usage
  exit 1
fi

if [[ "$mode" != "plan" && "$mode" != "execute" ]]; then
  echo "Error: Unknown mode: $mode" >&2
  usage
  exit 1
fi

if [[ $# -gt 0 ]]; then
  phase_arg="$1"
  shift
fi

if [[ -z "$phase_arg" ]]; then
  echo "Error: Missing phase input (N or comma list)." >&2
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$phase_arg" =~ ^[0-9]+$ ]]; then
  count="$phase_arg"
  if [[ "$count" -le 0 ]]; then
    echo "Error: N must be a positive integer." >&2
    exit 1
  fi
  phases=()
  for ((i=1; i<=count; i++)); do
    phases+=("$i")
  done
else
  phases_csv="$phase_arg"
  IFS=',' read -r -a phases <<<"$phases_csv"
  if [[ "${#phases[@]}" -eq 0 ]]; then
    echo "Error: phase list is empty." >&2
    exit 1
  fi
fi

echo "Repo: $repo"
echo "Phases: ${phases[*]}"

if [[ "$mode" == "plan" ]]; then
  echo "Spawning Codex sessions in parallel (plan phase)..."
  for phase in "${phases[@]}"; do
    phase_trimmed="$(echo "$phase" | xargs)"
    if [[ -z "$phase_trimmed" ]]; then
      continue
    fi

  codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    -C "$repo" \
    - <<EOF &
Use \$gsd-plan-phase $phase_trimmed
EOF
  done

  wait
  echo "All gsd-plan-phase runs completed."
  echo "Pushing after plan phase (if any commits were created)..."
  git -C "$repo" push || {
    echo "Push failed after plan phase. Resolve and rerun." >&2
    exit 1
  }
fi

echo "Running gsd-execute-phase sequentially..."
for phase in "${phases[@]}"; do
  phase_trimmed="$(echo "$phase" | xargs)"
  if [[ -z "$phase_trimmed" ]]; then
    continue
  fi

  codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    -C "$repo" \
    - <<EOF
Use \$gsd-execute-phase $phase_trimmed
EOF

  echo "Pushing after execute phase $phase_trimmed..."
  git -C "$repo" push || {
    echo "Push failed after execute phase $phase_trimmed. Resolve and rerun." >&2
    exit 1
  }
done

echo "All gsd-execute-phase runs completed."

echo "Running final code simplification session..."
codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  -C "$repo" \
  - <<'EOF'
Please review recent changes on this branch (last few hours). Use git log/diff to identify what was modified, then simplify and clean up the changed code without altering behavior. Use $code-simplifier to drive the cleanup.
EOF
