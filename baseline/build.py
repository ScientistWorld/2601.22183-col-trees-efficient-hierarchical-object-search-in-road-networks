#!/usr/bin/env python3
"""Root-only structure for the baselines: one node holding every vertex with
R random landmarks (R=16 is the paper's ALT index, R=1 only enumerates)."""

from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.structure_io import save_structure  # noqa: E402


def count_vertices(path):
    with open(path) as handle:
        return int(handle.readline().split()[2])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--landmarks", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    from data.nw import data_dir
    n = count_vertices(os.path.join(data_dir(), "NW-t.graph"))
    rng = random.Random(args.seed)
    lms = sorted(rng.sample(range(n), args.landmarks))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_structure(args.out, [-1], [lms], [0] * n,
                   {"kind": "root-only", "landmarks": args.landmarks, "seed": args.seed})


if __name__ == "__main__":
    main()
