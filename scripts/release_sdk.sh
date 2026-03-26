#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SDK_DIR="${SDK_DIR:-$REPO_ROOT/sdk/python}"
DIST_DIR="$SDK_DIR/dist"
PUBLISH="${PUBLISH:-0}"
RELEASE_TAG="${RELEASE_TAG:-}"
PACKAGE_NAME=""
DIST_BASENAME=""

log() {
  echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") INFO release_sdk: $*"
}

error() {
  echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") ERROR release_sdk: $*" >&2
}

run_build() {
  if command -v uv >/dev/null 2>&1; then
    (cd "$SDK_DIR" && uvx --from build python -m build .)
  else
    (cd "$SDK_DIR" && python3 -m build)
  fi
}

run_twine_check() {
  if command -v uv >/dev/null 2>&1; then
    uvx twine check "$DIST_DIR"/*
  else
    python3 -m twine check "$DIST_DIR"/*
  fi
}

run_twine_upload() {
  local twine_password="${TWINE_PASSWORD:-${TWINE_API_TOKEN:-}}"
  if [[ -z "$twine_password" ]]; then
    error "PUBLISH=1 requires TWINE_API_TOKEN or TWINE_PASSWORD"
    exit 1
  fi

  if command -v uv >/dev/null 2>&1; then
    TWINE_USERNAME="__token__" TWINE_PASSWORD="$twine_password" uvx twine upload "$DIST_DIR"/*
  else
    TWINE_USERNAME="__token__" TWINE_PASSWORD="$twine_password" python3 -m twine upload "$DIST_DIR"/*
  fi
}

verify_dist_filenames() {
  local wheel_path sdist_path wheel_name sdist_name
  wheel_path="$(ls "$DIST_DIR"/"$DIST_BASENAME"-*.whl | head -n 1)"
  sdist_path="$(ls "$DIST_DIR"/"$DIST_BASENAME"-*.tar.gz | head -n 1)"

  if [[ -z "$wheel_path" || -z "$sdist_path" ]]; then
    error "expected wheel and sdist under $DIST_DIR"
    exit 1
  fi

  wheel_name="$(basename "$wheel_path")"
  sdist_name="$(basename "$sdist_path")"

  if [[ "$wheel_name" != "$DIST_BASENAME"-"$PACKAGE_VERSION"-*.whl ]]; then
    error "wheel version mismatch expected_version=$PACKAGE_VERSION wheel=$wheel_name"
    exit 1
  fi

  if [[ "$sdist_name" != "$DIST_BASENAME"-"$PACKAGE_VERSION".tar.gz ]]; then
    error "sdist version mismatch expected_version=$PACKAGE_VERSION sdist=$sdist_name"
    exit 1
  fi

  log "distribution filename check passed wheel=$wheel_name sdist=$sdist_name"
}

verify_wheel_contents() {
  local wheel_path
  wheel_path="$(ls "$DIST_DIR"/"$DIST_BASENAME"-*.whl | head -n 1)"
  if [[ -z "$wheel_path" ]]; then
    error "wheel not found under $DIST_DIR"
    exit 1
  fi

  python3 - <<'PY' "$wheel_path"
import sys
import zipfile

wheel_path = sys.argv[1]
with zipfile.ZipFile(wheel_path) as zf:
    names = zf.namelist()

if not any(name.startswith("web_agent_sdk/") for name in names):
    raise SystemExit(f"wheel missing web_agent_sdk package: {wheel_path}")

if not any(name.startswith("web_agent_backend/") for name in names):
    raise SystemExit(f"wheel missing web_agent_backend package: {wheel_path}")
PY

  log "wheel content check passed wheel=$wheel_path"
}

if [[ ! -f "$SDK_DIR/pyproject.toml" ]]; then
  error "sdk pyproject not found path=$SDK_DIR/pyproject.toml"
  exit 1
fi

PACKAGE_VERSION="$(sed -nE 's/^version = "([^"]+)"/\1/p' "$SDK_DIR/pyproject.toml" | head -n 1)"
if [[ -z "$PACKAGE_VERSION" ]]; then
  error "unable to determine project version from $SDK_DIR/pyproject.toml"
  exit 1
fi

PACKAGE_NAME="$(sed -nE 's/^name = "([^"]+)"/\1/p' "$SDK_DIR/pyproject.toml" | head -n 1)"
if [[ -z "$PACKAGE_NAME" ]]; then
  error "unable to determine project name from $SDK_DIR/pyproject.toml"
  exit 1
fi

DIST_BASENAME="${PACKAGE_NAME//-/_}"
EXPECTED_TAG="${PACKAGE_NAME}-v${PACKAGE_VERSION}"
if [[ -n "$RELEASE_TAG" && "$RELEASE_TAG" != "$EXPECTED_TAG" ]]; then
  error "release tag mismatch expected=$EXPECTED_TAG actual=$RELEASE_TAG"
  exit 1
fi

if [[ "$PUBLISH" == "1" && -z "$RELEASE_TAG" ]]; then
  error "PUBLISH=1 requires RELEASE_TAG=$EXPECTED_TAG"
  exit 1
fi

log "starting sdk_dir=$SDK_DIR version=$PACKAGE_VERSION publish=$PUBLISH"
log "cleaning dist directory path=$DIST_DIR"
rm -rf "$DIST_DIR"

log "building sdist and wheel"
run_build

log "verifying distribution filenames"
verify_dist_filenames

log "verifying wheel contents"
verify_wheel_contents

log "running twine check"
run_twine_check

if [[ "$PUBLISH" == "1" ]]; then
  log "uploading distributions to PyPI"
  run_twine_upload
  log "publish complete version=$PACKAGE_VERSION"
else
  log "dry run complete; skipping upload (set PUBLISH=1 to publish)"
fi
