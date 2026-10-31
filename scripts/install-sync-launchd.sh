#!/usr/bin/env bash
# Install the 07:45 data copy as a launchd agent (after the maintainer's 07:30 job).
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/io.espero2.sync.plist"
mkdir -p "$DIR/logs" "$HOME/Library/LaunchAgents"
sed "s|__DIR__|$DIR|g" "$DIR/deploy/io.espero2.sync.plist" > "$PLIST"
launchctl bootout "gui/$UID/io.espero2.sync" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
echo "installed $PLIST"
echo "next run: 07:45 local; logs: $DIR/logs/sync-launchd.log"
