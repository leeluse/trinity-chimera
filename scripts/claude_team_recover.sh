#!/bin/bash

set -euo pipefail

TEAM_NAME="${1:-trinity-design-council}"
CONFIG_PATH="${CLAUDE_TEAM_CONFIG:-$HOME/.claude/teams/$TEAM_NAME/config.json}"
ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:4000}"

resolve_cli_path() {
    if [ -n "${NIM_CLI_PATH:-}" ] && [ -x "${NIM_CLI_PATH}" ]; then
        printf '%s\n' "${NIM_CLI_PATH}"
        return 0
    fi

    if [ -x "$HOME/claude-cli/cli-dev" ]; then
        printf '%s\n' "$HOME/claude-cli/cli-dev"
        return 0
    fi

    if command -v cli-dev >/dev/null 2>&1; then
        command -v cli-dev
        return 0
    fi

    if command -v claude >/dev/null 2>&1; then
        command -v claude
        return 0
    fi

    return 1
}

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Team config not found: $CONFIG_PATH" >&2
    exit 1
fi

if ! tmux has-session -t trinity 2>/dev/null; then
    echo "tmux session 'trinity' is not running." >&2
    exit 1
fi

CLI_PATH="$(resolve_cli_path || true)"
if [ -z "${CLI_PATH:-}" ]; then
    echo "Could not resolve a working Claude CLI path." >&2
    exit 1
fi

TEAM_ROWS=()
while IFS= read -r line; do
    TEAM_ROWS+=("$line")
done < <(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text())
lead_session_id = config.get("leadSessionId", "")

for member in config.get("members", []):
    if member.get("backendType") != "tmux":
        continue
    values = [
        member.get("agentId", ""),
        member.get("name", ""),
        member.get("agentType", ""),
        member.get("color", ""),
        member.get("tmuxPaneId", ""),
        member.get("cwd", ""),
        member.get("model", ""),
        lead_session_id,
    ]
    print("\t".join(value.replace("\t", " ").replace("\n", " ") for value in values))
PY
)

if [ "${#TEAM_ROWS[@]}" -eq 0 ]; then
    echo "No tmux teammates found in $CONFIG_PATH" >&2
    exit 1
fi

echo "Using CLI path: $CLI_PATH"

for row in "${TEAM_ROWS[@]}"; do
    IFS=$'\t' read -r agent_id agent_name agent_type agent_color pane_id cwd model parent_session_id <<<"$row"

    if ! tmux list-panes -a -F '#{pane_id}' | grep -Fxq "$pane_id"; then
        echo "Skipping $agent_name: pane $pane_id does not exist."
        continue
    fi

    printf -v escaped_cli '%q' "$CLI_PATH"
    printf -v escaped_cwd '%q' "$cwd"
    printf -v escaped_agent_id '%q' "$agent_id"
    printf -v escaped_agent_name '%q' "$agent_name"
    printf -v escaped_team_name '%q' "$TEAM_NAME"
    printf -v escaped_agent_color '%q' "$agent_color"
    printf -v escaped_parent_session '%q' "$parent_session_id"
    printf -v escaped_agent_type '%q' "$agent_type"
    printf -v escaped_model '%q' "$model"
    printf -v escaped_base_url '%q' "$ANTHROPIC_BASE_URL"

    launch_cmd="cd $escaped_cwd && env CLAUDECODE=1 CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 ANTHROPIC_BASE_URL=$escaped_base_url NIM_CLI_PATH=$escaped_cli $escaped_cli --agent-id $escaped_agent_id --agent-name $escaped_agent_name --team-name $escaped_team_name --agent-color $escaped_agent_color --parent-session-id $escaped_parent_session --agent-type $escaped_agent_type --dangerously-skip-permissions --model $escaped_model"

    echo "Reviving $agent_name in $pane_id"
    tmux send-keys -t "$pane_id" C-c
    tmux send-keys -t "$pane_id" "clear" C-m
    tmux send-keys -t "$pane_id" "$launch_cmd" C-m
done

echo "Teammate revive commands sent."
