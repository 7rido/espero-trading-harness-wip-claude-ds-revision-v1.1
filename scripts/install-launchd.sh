#!/usr/bin/env bash
# Install the loop as a launchd agent (macOS). Remove with: launchctl bootout gui/$UID/io.espero2.paper
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/io.espero2.paper.plist"
mkdir -p "$DIR/logs" "$HOME/Library/LaunchAgents"
sed "s|__DIR__|$DIR|g" "$DIR/deploy/io.espero2.paper.plist" > "$PLIST"
launchctl bootout "gui/$UID/io.espero2.paper" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl kickstart -k "gui/$UID/io.espero2.paper"
echo "installed $PLIST"
echo "logs: $DIR/logs/paper.log"
