#!/usr/bin/env bash
# Create a GitHub Release for an existing annotated tag (local fallback).
#
# Preferred: push an annotated v* tag — .github/workflows/release.yml publishes automatically.
#
# Usage:
#   git tag -a v1.0.1 -m "v1.0.1"
#   git push origin v1.0.1                    # triggers workflow
#   ./scripts/release/create-github-release.sh v1.0.1   # or run locally with gh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

TAG="${1:?Usage: $0 vX.Y.Z}"

if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "error: tag not found locally: $TAG" >&2
  exit 1
fi

if command -v gh >/dev/null 2>&1; then
  gh release view "$TAG" >/dev/null 2>&1 && {
    echo "Release $TAG already exists on GitHub." >&2
    exit 0
  }
  gh release create "$TAG" --title "$TAG" --generate-notes
  echo "Created GitHub release for $TAG"
  exit 0
fi

echo "gh CLI not installed. Push tag to origin to trigger the release workflow:" >&2
echo "  git push origin $TAG" >&2
exit 1
