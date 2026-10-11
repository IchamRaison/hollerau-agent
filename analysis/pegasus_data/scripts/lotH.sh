#!/usr/bin/env bash
# Lot H : exploration sur les 5 cas figés (P04 P05 P07 P08 P18), deux ancrages généraux, 5 + 5 sessions.
cd ~/tacto/negotiation-arena-kit/starter-kit
L1=/tmp/claude-1000/-home-heezo/59742ee3-ebd1-4af1-9297-9691f27834d9/scratchpad/lotH-soft.log
L2=/tmp/claude-1000/-home-heezo/59742ee3-ebd1-4af1-9297-9691f27834d9/scratchpad/lotH-hard.log
PEGASUS_READER=1 PEGASUS_TEAM_CLAIMS=1 PEGASUS_GAP=1 PEGASUS_ANCHOR=0.88 timeout 1500 ~/.local/bin/uv run python -m hollerau.pegasus.cli practice P04 P05 P07 P08 P18 --parallel 5 > $L1 2>&1 &
PEGASUS_READER=1 PEGASUS_TEAM_CLAIMS=1 PEGASUS_GAP=1 PEGASUS_ANCHOR=0.72 timeout 1500 ~/.local/bin/uv run python -m hollerau.pegasus.cli practice P04 P05 P07 P08 P18 --parallel 5 > $L2 2>&1 &
wait
for L in $L1 $L2; do echo "=== $L"; grep -E "^case:|mean score|practice left|ERROR" $L | cut -c1-70; done
