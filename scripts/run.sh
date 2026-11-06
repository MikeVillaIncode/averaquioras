#!/bin/sh
# Start (or restart) the progress loop and the floating widget for one config.
set -e
CFG=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
DIR=$(dirname "$CFG")
SKILL=$(cd "$(dirname "$0")/.." && pwd)
"$SKILL/scripts/stop.sh" "$CFG" >/dev/null 2>&1 || true
# Drop the previous render so the window never opens on a stale page before the loop rewrites it.
rm -f "$DIR/widget.html"
nohup python3 -I "$SKILL/scripts/progress.py" "$CFG" > "$DIR/progress.log" 2>&1 &
echo $! > "$DIR/progress.pid"
i=0; while [ ! -f "$DIR/widget.html" ] && [ $i -lt 20 ]; do sleep 0.5; i=$((i+1)); done
if [ ! -x "$SKILL/widget/node_modules/.bin/electron" ]; then
  (cd "$SKILL/widget" && npm install --no-audit --no-fund electron@latest > install.log 2>&1)
fi
(cd "$SKILL/widget" && nohup ./node_modules/.bin/electron . "$DIR/widget.html" > "$DIR/widget.log" 2>&1 & echo $! > "$DIR/widget.pid")
echo "widget: $DIR/widget.html"
echo "page:   file://$DIR/index.html"
