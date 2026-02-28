#!/usr/bin/env bash
# Stop hook verification gate for streetrace.
# Runs make check before allowing the agent to stop.
# Blocks with reason if checks fail; allows stop if checks pass.

set -euo pipefail

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

# Prevent infinite loop: if already retrying after a block, allow stop
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

CHECK_OUTPUT=$(make check 2>&1) || {
  # Truncate output to last 800 chars to fit in the block reason
  TRIMMED="${CHECK_OUTPUT: -800}"
  # Escape for JSON
  ESCAPED=$(echo "$TRIMMED" | jq -Rs .)
  echo "{\"decision\": \"block\", \"reason\": \"make check failed. Fix the issues and try again:\\n\"${ESCAPED}}"
  exit 0
}

# All checks passed
exit 0
