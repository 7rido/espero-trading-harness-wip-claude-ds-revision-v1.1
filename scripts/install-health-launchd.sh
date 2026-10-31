#!/usr/bin/env bash
# Daily 08:30 health check (after the 07:45 copy). Non-zero exit shows in logs/health-launchd.err.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/io.espero2.health.plist"
mkdir -p "$DIR/logs" "$HOME/Library/LaunchAgents"
sed "s|__DIR__|$DIR|g" "$DIR/deploy/io.espero2.health.plist" > "$PLIST"
launchctl bootout "gui/$UID/io.espero2.health" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
echo "installed $PLIST (daily 08:30); logs: $DIR/logs/health-launchd.log"
