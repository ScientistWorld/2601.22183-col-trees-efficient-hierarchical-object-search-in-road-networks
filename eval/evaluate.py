#!/usr/bin/env python3
"""Main evaluator: the paper's own setting -> scoring/scores.json.

Runs the public evaluator (eval/train/evaluate.py) with `--setting paper`:
the original DIMACS NW travel times and the real OpenStreetMap POI categories
exactly as published, default query parameters from the paper (Table 4).
All other arguments (--root, --output, --details) are passed through.

Usage: python3 eval/evaluate.py [--root DIR ...] [--output FILE] [--details FILE]
"""

import os
import runpy
import sys

TRAIN_EVALUATOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train", "evaluate.py")

if __name__ == "__main__":
    sys.argv = [TRAIN_EVALUATOR, "--setting", "paper"] + sys.argv[1:]
    runpy.run_path(TRAIN_EVALUATOR, run_name="__main__")
