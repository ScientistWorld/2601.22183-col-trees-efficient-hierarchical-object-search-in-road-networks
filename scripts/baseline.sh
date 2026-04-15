#!/bin/bash
# Run a baseline method from the paper.
#
# Baselines are simple reference methods the paper compares against.
# Implement this only if applicable, i.e., the paper has baselines.
# You do not need to implement all baselines to begin —
# just enough to validate that the evaluation pipeline works
# and provide a reference point.
#
# This script runs the brute-force baseline for AkNN, kFN, and range queries.
# Usage:
#   bash scripts/baseline.sh

set -e

cd /home/user

echo "=== Running brute-force baselines ==="

# AkNN baseline (brute force)
echo "AkNN brute force..."
python3 -c "
import time, json
from data.loader import load_network
from method.graph import ObjectSet
from method.baselines import aknn_bruteforce

G = load_network('data/downloads/road-usroads-48.mtx')
obj_set = ObjectSet.uniform_random(G, 0.001, seed=42)

import random
random.seed(42)
qv = random.sample(range(G.num_vertices), 40)

Q = qv[0:4]
t0 = time.time()
res = aknn_bruteforce(G, obj_set, Q, k=10, agg='max')
t1 = time.time()
print(f'AkNN BF: {len(res)} results in {(t1-t0)*1000:.0f}ms')
" 2>&1

# kFN baseline (brute force)
echo "kFN brute force..."
python3 -c "
import time
from data.loader import load_network
from method.graph import ObjectSet
from method.baselines import kfn_bruteforce

G = load_network('data/downloads/road-usroads-48.mtx')
obj_set = ObjectSet.uniform_random(G, 0.001, seed=42)

import random
random.seed(42)
qv = random.sample(range(G.num_vertices), 1)

q = qv[0]
t0 = time.time()
res = kfn_bruteforce(G, obj_set, q, k=10)
t1 = time.time()
print(f'kFN BF: {len(res)} results in {(t1-t0)*1000:.0f}ms')
" 2>&1

# Range baseline (brute force)
echo "Range brute force..."
python3 -c "
import time
from data.loader import load_network
from method.graph import ObjectSet
from method.baselines import range_bruteforce

G = load_network('data/downloads/road-usroads-48.mtx')
obj_set = ObjectSet.uniform_random(G, 0.001, seed=42)

import random
random.seed(42)
qv = random.sample(range(G.num_vertices), 1)

q = qv[0]
t0 = time.time()
res = range_bruteforce(G, obj_set, q, 10.0)
t1 = time.time()
print(f'Range BF: {len(res)} results in {(t1-t0)*1000:.0f}ms')
" 2>&1

echo "=== Baseline runs complete ==="
