#!/usr/bin/env python3
"""Execute the installed research variant using the shipped configurations."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, '/home/user')
from method.experiment import run_experiment

p = argparse.ArgumentParser()
p.add_argument('name')
p.add_argument('--seed', type=int, default=42)
p.add_argument('--m', type=int, default=4)
p.add_argument('--only-range', action='store_true')
a = p.parse_args()
configs = [('aknn', .05, 6), ('kfn', .05, 12), ('kfn', .10, 12), ('range', .05, 6)]
if a.only_range:
    configs = configs[-1:]
records = []
for qt, density, count in configs:
    record = run_experiment('usroads-48', qt, k=10, n_queries=count,
        density=density, agg='max', Q_size=4, radius_pct=1,
        b=4, lam=2048, m=a.m, landmark_policy='random', seed=a.seed)
    records.append(record)
    # Save after each configuration, so a killed job retains progress.
    dest = Path('/home/user/redteam') / a.name / 'artifacts.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(records, indent=2) + '\n')
