#!/usr/bin/env bash
# Manage in-detail as a background service (launchd LaunchAgent).
# It runs detached from any terminal and auto-starts every time you log in.
#
#   ./service.sh install     set it up + start it now
#   ./service.sh start        start (or restart) it
#   ./service.sh stop         stop it (and stop auto-start on login)
#   ./service.sh uninstall    remove it completely
#   ./service.sh status       is it running?
#   ./service.sh logs         tail the log
set -euo pipefail

LABEL="com.iota.in-detail"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG="$(cd "$(dirname "$0")" && pwd)/in-detail.log"
DOMAIN="gui/$(id -u)"

case "${1:-status}" in
  install|start)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    pkill -f "In Detail.app" 2>/dev/null || true   # clear any stray instances
    sleep 1
    launchctl bootstrap "$DOMAIN" "$PLIST"          # RunAtLoad starts it once
    launchctl enable "$DOMAIN/$LABEL"
    echo "started — look for 👀 (or 😴 if paused) in your menu bar"
    ;;
  stop|uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    pkill -f "In Detail.app" 2>/dev/null || true
    echo "stopped (won't auto-start on login)"
    ;;
  status)
    if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      echo "running ✓"
    else
      echo "not running"
    fi
    ;;
  logs)
    tail -f "$LOG"
    ;;
  *)
    echo "usage: ./service.sh {install|start|stop|uninstall|status|logs}"
    exit 1
    ;;
esac
