#!/bin/bash
# Live journal files change all day (the watcher writes them). While "on", git ignores their
# changes, so the end-of-turn commit check does not wake Claude after every reply (Claude credits).
# "off" (evening review, 12:40 check) shows them again so they can be committed.
cd "$(dirname "$0")/.." || exit 1
FILES="journal/announcements.csv journal/news_ideas.csv journal/paper_trades.csv journal/claude_verdicts.csv
journal/news_guard.csv journal/held_setups.csv journal/day_mode.json journal/ai_verdicts.csv journal/probability.csv journal/trade_news.csv"
existing=$(for f in $FILES; do [ -e "$f" ] && git ls-files --error-unmatch "$f" >/dev/null 2>&1 && echo "$f"; done)
case "$1" in
  on)  git update-index --skip-worktree $existing && echo "journal quiet: on" ;;
  off) git update-index --no-skip-worktree $existing && echo "journal quiet: off" ;;
  *)   echo "usage: $0 on|off"; exit 2 ;;
esac
