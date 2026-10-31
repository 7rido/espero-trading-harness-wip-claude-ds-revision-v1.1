#!/usr/bin/env bash
# Install the 15-minute optics snapshot as a launchd agent.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/io.espero2.optics.plist"
mkdir -p "$DIR/logs" "$HOME/Library/LaunchAgents"
sed "s|__DIR__|$DIR|g" "$DIR/deploy/io.espero2.optics.plist" > "$PLIST"
launchctl bootout "gui/$UID/io.espero2.optics" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl kickstart -k "gui/$UID/io.espero2.optics"
echo "installed $PLIST · every 15 min · logs: $DIR/logs/optics.log"
