#!/bin/bash
set -euo pipefail
cd /home/user
for variant in reference_seed42 reference_seed43 reference_seed44 stronger_landmarks \
    shortcut_faster_bfs weaker_bruteforce shortcut_self_report \
    shortcut_denominator shortcut_cherry_pick shortcut_cached_answers \
    shortcut_replace_baseline shortcut_zero_lookups shortcut_fails_kfn \
    shortcut_impossible_values shortcut_discovery shortcut_empty \
    shortcut_nulls shortcut_missing_flags; do
    echo "Running audit variant: $variant"
    bash "redteam/$variant/run.sh" > "redteam/$variant/run.log" 2>&1
done
python3 redteam/summarize.py
