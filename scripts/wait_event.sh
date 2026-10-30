#!/bin/bash
# Waits for the watcher's next problem line (watcher stopped, login, budget, stale data, repeating
# error, crash; also a SHOCK day), prints it plus anything within 3 seconds, then exits: run it in the
# background so Claude is woken once per event instead of every 30 minutes (Claude credits).
LOG="${1:?usage: wait_event.sh <watcher.log>}"
# Problems only (user, 30 Oct: save Claude credits): trades and results are reported in the scheduled checks.
PAT='^SHOCK |^STATUS.*"watching": false|^ERROR.*(login|Login|budget|Stale|repeats)|Traceback'
while IFS= read -r line; do
  if [[ "$line" =~ $PAT && "$line" != *"market closed"* ]]; then
    echo "${line:0:600}"
    while IFS= read -r -t 3 more; do [[ "$more" =~ $PAT ]] && echo "${more:0:600}"; done
    exit 0
  fi
done < <(tail -n 0 -F "$LOG" 2>/dev/null)
