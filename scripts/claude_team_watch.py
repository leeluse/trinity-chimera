#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def collect_state(team_name: str):
    team_root = Path.home() / ".claude" / "teams" / team_name
    config_path = team_root / "config.json"
    config = load_json(config_path)
    if not config:
        raise FileNotFoundError(f"Missing team config: {config_path}")

    panes_output = run(
        [
            "tmux",
            "list-panes",
            "-a",
            "-F",
            "#{pane_id}\t#{session_name}\t#{window_name}\t#{pane_current_command}\t#{pane_current_path}",
        ]
    )
    panes = {}
    for line in panes_output.splitlines():
        pane_id, session_name, window_name, current_command, current_path = line.split("\t", 4)
        panes[pane_id] = {
            "session_name": session_name,
            "window_name": window_name,
            "current_command": current_command,
            "current_path": current_path,
        }

    rows = []
    for member in config.get("members", []):
        inbox_path = team_root / "inboxes" / f"{member.get('name')}.json"
        inbox = load_json(inbox_path) or []
        unread = sum(1 for item in inbox if not item.get("read"))
        last_message = inbox[-1] if inbox else {}
        pane_id = member.get("tmuxPaneId", "")
        pane = panes.get(
            pane_id,
            {
                "session_name": "-",
                "window_name": "-",
                "current_command": "-",
                "current_path": "-",
            },
        )
        rows.append(
            {
                "name": member.get("name", ""),
                "agent_id": member.get("agentId", ""),
                "backend_type": member.get("backendType", "-"),
                "pane_id": pane_id or "-",
                "pane_command": pane["current_command"],
                "pane_window": pane["window_name"],
                "unread": unread,
                "last_from": last_message.get("from", "-"),
                "last_timestamp": last_message.get("timestamp", "-"),
                "last_summary": (last_message.get("summary") or last_message.get("text") or "-").replace("\n", " "),
            }
        )
    return config_path, rows


def render(config_path: Path, rows: list[dict]):
    lines = []
    lines.append(f"Team config: {config_path}")
    lines.append("")
    header = (
        f"{'name':<18} {'backend':<8} {'pane':<6} {'cmd':<10} "
        f"{'window':<12} {'unread':<6} {'last_from':<12} {'last_timestamp':<24} last_message"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        summary = row["last_summary"]
        if len(summary) > 80:
            summary = summary[:77] + "..."
        lines.append(
            f"{row['name']:<18} {row['backend_type']:<8} {row['pane_id']:<6} "
            f"{row['pane_command']:<10} {row['pane_window']:<12} {row['unread']:<6} "
            f"{row['last_from']:<12} {row['last_timestamp']:<24} {summary}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Watch Claude team pane and inbox state.")
    parser.add_argument("--team", default="trinity-design-council")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    while True:
        config_path, rows = collect_state(args.team)
        output = render(config_path, rows)
        if args.watch:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(output + "\n")
            sys.stdout.flush()
            time.sleep(args.interval)
        else:
            print(output)
            return


if __name__ == "__main__":
    main()
