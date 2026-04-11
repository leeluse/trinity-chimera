#!/bin/bash

set -euo pipefail

TEAM_NAME="${1:-trinity-design-council}"
CONFIG_PATH="${CLAUDE_TEAM_CONFIG:-$HOME/.claude/teams/$TEAM_NAME/config.json}"
PROMPT="${CLAUDE_TEAM_PING_PROMPT:-Use SendMessage to send a one-sentence status update to team-lead right now, mentioning your specialty and whether you are blocked. After sending it, continue your analysis.}"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Team config not found: $CONFIG_PATH" >&2
    exit 1
fi

TARGETS=()
while IFS= read -r line; do
    TARGETS+=("$line")
done < <(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text())
for member in config.get("members", []):
    if member.get("backendType") == "tmux" and member.get("tmuxPaneId"):
        print(f"{member.get('name','')}\t{member.get('tmuxPaneId','')}")
PY
)

if [ "${#TARGETS[@]}" -eq 0 ]; then
    echo "No tmux teammates found in $CONFIG_PATH" >&2
    exit 1
fi

for row in "${TARGETS[@]}"; do
    IFS=$'\t' read -r agent_name pane_id <<<"$row"
    echo "Prompting $agent_name via $pane_id"
    tmux send-keys -t "$pane_id" "$PROMPT" C-m
done

echo "Ping prompt sent to all tmux teammates."
