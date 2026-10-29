#!/bin/bash
# Waits for the watcher's next actionable line (SIGNAL/EXIT/RESULT/SHOCK, watcher stopped, serious
# error), prints it plus anything else arriving within 3 seconds, then exits: run it in the
# background so Claude is woken once per event instead of every 30 minutes (Claude credits).
LOG="${1:?usage: wait_event.sh <watcher.log>}"
PAT='^(SIGNAL|EXIT|RESULT|SHOCK) |^STATUS.*"watching": false|^ERROR.*(login|Login|limit|budget|Stale|repeats|spurt)|Traceback'
while IFS= read -r line; do
  if [[ "$line" =~ $PAT ]]; then
    echo "${line:0:600}"
    while IFS= read -r -t 3 more; do [[ "$more" =~ $PAT ]] && echo "${more:0:600}"; done
    exit 0
  fi
done < <(tail -n 0 -F "$LOG" 2>/dev/null)
