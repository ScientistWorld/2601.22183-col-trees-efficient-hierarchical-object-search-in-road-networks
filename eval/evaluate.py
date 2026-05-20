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
import sys
from pathlib import Path

sys.path.insert(0, "/home/user")

from data.graph import ObjectSet
from data.loader import load_network


def resolve_network_path(network_name):
    candidates = {
        "usroads-48": ["/home/user/data/downloads/road-usroads-48.mtx"],
        "roadnet-pa": ["/home/user/data/downloads/roadNet-PA.txt"],
    }
    for path in candidates.get(network_name, []):
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"Missing network data for {network_name}; run scripts/download.sh")

def percentile(values, pct):
    """Nearest-rank percentile for small per-query metric lists."""
    numeric = sorted(v for v in values if isinstance(v, (int, float)))
    if not numeric:
        return 0
    idx = int((pct / 100.0) * (len(numeric) - 1))
    return numeric[idx]


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


def build_objects(record):
    graph = load_network(resolve_network_path(record["network"]))
    objects = ObjectSet.uniform_random(
        graph,
        float(record["density"]),
        seed=int(record.get("seed", 42)),
    )
    return graph, objects


def valid_nearest_topk(graph, candidates, objects, query_vertices, k, agg):
    if len(set(candidates)) != min(k, len(objects.objects)):
        return False
    distance_cache = {q: graph.dijkstra(q) for q in query_vertices}

    def score(obj):
        distances = [distance_cache[q][obj] for q in query_vertices]
        return sum(distances) if agg == "sum" else max(distances)

    all_scores = sorted(score(obj) for obj in objects.objects)
    threshold = all_scores[min(k, len(all_scores)) - 1]
    return all(score(obj) <= threshold + 1e-9 for obj in candidates)


def valid_farthest_topk(graph, candidates, objects, query_vertex, k):
    if len(set(candidates)) != min(k, len(objects.objects)):
        return False
    distances = graph.dijkstra(query_vertex)
    all_scores = sorted((distances[obj] for obj in objects.objects), reverse=True)
    threshold = all_scores[min(k, len(all_scores)) - 1]
    return all(distances[obj] >= threshold - 1e-9 for obj in candidates)


def recompute_accuracy(result):
    per_query = result.get("queries", {}).get("per_query")
    if not isinstance(per_query, list) or not per_query:
        raise ValueError("Result artifact must include queries.per_query for independent evaluation")

    graph, objects = build_objects(result)
    query_type = result.get("query_type", "")
    correct = 0
    for item in per_query:
        returned = item.get("result", [])
        if query_type == "aknn":
            ok = valid_nearest_topk(
                graph,
                returned,
                objects,
                item["query_vertices"],
                int(result["k"]),
                result.get("agg", "max"),
            )
        elif query_type == "kfn":
            ok = valid_farthest_topk(
                graph,
                returned,
                objects,
                int(item["query_vertex"]),
                int(result["k"]),
            )
        elif query_type == "range":
            distances = graph.dijkstra(int(item["query_vertex"]))
            radius = float(result.get("queries", {}).get("radius", 0.0))
            expected = {
                obj for obj in objects.objects
                if obj < len(distances) and distances[obj] <= radius
            }
            ok = set(returned) == expected
        else:
            ok = False
        correct += 1 if ok else 0
    return correct / len(per_query)


def evaluate_kfn(result, method_name):
    """Compute kFN metrics matching reference.json kfn_real_pois."""
    q = result.get("queries", {})
    n_objects = result.get("n_objects", 0)

    accuracy = recompute_accuracy(result)

    col_candidates = q.get("col_candidate_objects_avg", 0)
    col_exact = q.get("col_exact_lookups_avg", 0)

    candidates_ratio = col_candidates / n_objects if n_objects > 0 else 1.0
    lookup_reduction = n_objects / col_exact if col_exact > 0 else 1.0
    candidate_counts = q.get("individual_candidates", [])
    candidate_p90_ratio = percentile(candidate_counts, 90) / n_objects if n_objects > 0 else 1.0
    candidate_max_ratio = max(candidate_counts) / n_objects if candidate_counts and n_objects > 0 else candidates_ratio

    return {
        "accuracy": accuracy,
        "candidates_ratio": candidates_ratio,
        "candidate_p90_ratio": candidate_p90_ratio,
        "candidate_max_ratio": candidate_max_ratio,
        "lookup_reduction_vs_brute": lookup_reduction,
    }


def evaluate_aknn(result, method_name):
    """Compute AkNN metrics matching reference.json aknn_real_pois."""
    q = result.get("queries", {})
    n_objects = result.get("n_objects", 0)
    accuracy = recompute_accuracy(result)
    col_candidates = q.get("col_candidate_objects_avg", 0)
    candidates_ratio = col_candidates / n_objects if n_objects > 0 else 1.0
    candidate_counts = q.get("individual_candidates", [])
    candidate_p90_ratio = percentile(candidate_counts, 90) / n_objects if n_objects > 0 else 1.0
    candidate_max_ratio = max(candidate_counts) / n_objects if candidate_counts and n_objects > 0 else candidates_ratio
    return {
        "accuracy": accuracy,
        "candidates_ratio": candidates_ratio,
        "candidate_p90_ratio": candidate_p90_ratio,
        "candidate_max_ratio": candidate_max_ratio,
    }


def evaluate_range(result, method_name):
    """Compute range metrics matching reference.json range_real_pois."""
    q = result.get("queries", {})
    n_objects = result.get("n_objects", 0)
    accuracy = recompute_accuracy(result)
    col_candidates = q.get("col_candidate_objects_avg", 0)
    candidates_ratio = col_candidates / n_objects if n_objects > 0 else 1.0
    candidate_counts = q.get("individual_candidates", [])
    candidate_p90_ratio = percentile(candidate_counts, 90) / n_objects if n_objects > 0 else 1.0
    candidate_max_ratio = max(candidate_counts) / n_objects if candidate_counts and n_objects > 0 else candidates_ratio
    return {
        "accuracy": accuracy,
        "candidates_ratio": candidates_ratio,
        "candidate_p90_ratio": candidate_p90_ratio,
        "candidate_max_ratio": candidate_max_ratio,
    }


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
