#!/usr/bin/env python3
"""
Evaluation and scoring for COL-Tree reproduction.
Computes machine-independent metrics from experiment results and writes scores.json.
Metric names match scoring/reference.json experiment keys.
"""

import json
import argparse
import os
import glob
from pathlib import Path


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_results(input_path):
    """Load one or many result JSONs from a file or directory."""
    p = Path(input_path)
    if p.is_dir():
        records = []
        for jf in sorted(p.glob("*.json")):
            records.append(load_json(jf))
        return records
    return [load_json(p)]


def add_result(accumulator, experiment, method, metrics):
    bucket = accumulator.setdefault(experiment, {}).setdefault(method, [])
    bucket.append(metrics)


def average_metrics(metric_records):
    if not metric_records:
        return {}
    keys = sorted({key for record in metric_records for key in record})
    averaged = {}
    for key in keys:
        values = [record[key] for record in metric_records if isinstance(record.get(key), (int, float))]
        if values:
            averaged[key] = sum(values) / len(values)
    return averaged


def evaluate_kfn(result, method_name):
    """Compute kFN metrics matching reference.json kfn_real_pois."""
    q = result.get("queries", {})
    n_objects = result.get("n_objects", 0)

    accuracy = q.get("accuracy", 0)

    col_candidates = q.get("col_candidate_objects_avg", 0)
    col_exact = q.get("col_exact_lookups_avg", 0)

    candidates_ratio = col_candidates / n_objects if n_objects > 0 else 1.0
    lookup_reduction = n_objects / col_exact if col_exact > 0 else 1.0

    return {
        "accuracy": accuracy,
        "candidates_ratio": candidates_ratio,
        "lookup_reduction_vs_brute": lookup_reduction,
    }


def evaluate_aknn(result, method_name):
    """Compute AkNN metrics matching reference.json aknn_real_pois."""
    q = result.get("queries", {})
    n_objects = result.get("n_objects", 0)
    accuracy = q.get("accuracy", 0)
    col_candidates = q.get("col_candidate_objects_avg", 0)
    candidates_ratio = col_candidates / n_objects if n_objects > 0 else 1.0
    return {"accuracy": accuracy, "candidates_ratio": candidates_ratio}


def evaluate_range(result, method_name):
    """Compute range metrics matching reference.json range_real_pois."""
    q = result.get("queries", {})
    n_objects = result.get("n_objects", 0)
    accuracy = q.get("accuracy", 0)
    col_candidates = q.get("col_candidate_objects_avg", 0)
    candidates_ratio = col_candidates / n_objects if n_objects > 0 else 1.0
    return {"accuracy": accuracy, "candidates_ratio": candidates_ratio}


def evaluate_preprocessing(result, method_name):
    """Compute preprocessing metrics matching reference.json preprocessing."""
    return {
        "sul_time_s": result.get("sul_time", 0),
        "col_time_s": result.get("col_time", 0),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate COL-Tree results")
    parser.add_argument("results_path", help="Result JSON file or directory")
    parser.add_argument("--method-name", "-m", default="colt_us48_repro")
    parser.add_argument("--output", "-o", default="/home/user/scoring/scores.json")
    args = parser.parse_args()

    records = load_results(args.results_path)
    method = args.method_name

    accumulator = {}

    for rec in records:
        qt = rec.get("query_type", "")

        if qt == "kfn":
            add_result(accumulator, "kfn_real_pois", method, evaluate_kfn(rec, method))
        elif qt == "aknn":
            add_result(accumulator, "aknn_real_pois", method, evaluate_aknn(rec, method))
        elif qt == "range":
            add_result(accumulator, "range_real_pois", method, evaluate_range(rec, method))

        # Every record contributes preprocessing info
        if "sul_time" in rec and "col_time" in rec:
            add_result(accumulator, "preprocessing", method, evaluate_preprocessing(rec, method))

    scores = {}
    for experiment, methods in accumulator.items():
        scores[experiment] = {"results": {}}
        for method_name, metric_records in methods.items():
            scores[experiment]["results"][method_name] = average_metrics(metric_records)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(scores, f, indent=2)
        f.write("\n")

    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
