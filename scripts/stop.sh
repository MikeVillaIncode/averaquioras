#!/bin/sh
# Stop the progress loop and the widget started by run.sh for one config (by PID).
DIR=$(cd "$(dirname "$1")" && pwd)
for f in progress widget; do
  if [ -f "$DIR/$f.pid" ]; then
    P=$(cat "$DIR/$f.pid")
    pgrep -P "$P" | while read c; do kill "$c" 2>/dev/null; done
    kill "$P" 2>/dev/null
    rm -f "$DIR/$f.pid"
  fi
done
