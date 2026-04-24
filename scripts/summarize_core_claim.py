#!/usr/bin/env python3
"""Aggregate core-claim experiment outputs into a compact summary."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="Experiment result JSON files")
    parser.add_argument("--output", required=True, help="Summary JSON path")
    args = parser.parse_args()

    summary = {"experiments": []}
    for path_str in sorted(args.inputs):
        path = Path(path_str)
        with path.open() as f:
            payload = json.load(f)
        queries = payload.get("queries", {})
        summary["experiments"].append({
            "file": path.name,
            "density": payload.get("density"),
            "n_objects": payload.get("n_objects"),
            "accuracy": queries.get("accuracy"),
            "aub_accuracy": queries.get("aub_accuracy"),
            "col_avg_time_ms": queries.get("col_avg_time_ms"),
            "aub_avg_time_ms": queries.get("aub_avg_time_ms"),
            "brute_avg_time_ms": queries.get("brute_avg_time_ms"),
            "speedup_over_aub": queries.get("speedup_over_aub"),
            "col_exact_lookups_avg": queries.get("col_exact_lookups_avg"),
            "aub_exact_lookups_avg": queries.get("aub_exact_lookups_avg"),
            "col_candidate_objects_avg": queries.get("col_candidate_objects_avg"),
            "aub_candidate_objects_avg": queries.get("aub_candidate_objects_avg"),
        })

    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
