#!/usr/bin/env bash
# Branch ruleset: only recepsirin can push to master; others merge via PR + CI.
set -euo pipefail

OWNER="${1:-recepsirin}"
REPO="${2:-vitiligo-initiative}"
RULESET_NAME="Protect master"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: brew install gh" >&2
  exit 1
fi

gh auth status >/dev/null 2>&1 || {
  echo "Run: gh auth login" >&2
  exit 1
}

USER_ID="$(gh api "users/${OWNER}" --jq .id)"
EXISTING_ID="$(gh api "repos/${OWNER}/${REPO}/rulesets" --jq ".[] | select(.name==\"${RULESET_NAME}\") | .id" | head -1)"

read -r -d '' PAYLOAD <<EOF || true
{
  "name": "${RULESET_NAME}",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/master"],
      "exclude": []
    }
  },
  "bypass_actors": [
    {
      "actor_id": ${USER_ID},
      "actor_type": "User",
      "bypass_mode": "always"
    }
  ],
  "rules": [
    {
      "type": "update",
      "parameters": {
        "update_allows_fetch_and_merge": true
      }
    },
    {
      "type": "deletion"
    },
    {
      "type": "pull_request",
      "parameters": {
        "allowed_merge_methods": ["merge", "squash", "rebase"],
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_approving_review_count": 0,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          {
            "context": "CI / lint-and-test"
          }
        ]
      }
    }
  ]
}
EOF

if [[ -n "${EXISTING_ID}" ]]; then
  echo "Updating ruleset ${EXISTING_ID}..."
  gh api -X PUT "repos/${OWNER}/${REPO}/rulesets/${EXISTING_ID}" --input - <<<"${PAYLOAD}"
else
  echo "Creating ruleset..."
  gh api -X POST "repos/${OWNER}/${REPO}/rulesets" --input - <<<"${PAYLOAD}"
fi

echo "OK — ${OWNER} can push directly to master; others need PRs with CI passing."
