#!/usr/bin/env python3
"""Train-slice evaluator for COL-Tree result artifacts.
Reads experiment JSONs and computes machine-independent metrics from the
public development slice (even-indexed queries, SLICE_PARITY=0).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SLICE_PARITY = 0


def load_json(path: Path) -> Any:
    with path.open("r") as handle:
        return json.load(handle)


def normalize_result_objects(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for item in raw:
            out.extend(normalize_result_objects(item))
        return out
    if not isinstance(raw, dict):
        return []
    if "query_type" in raw:
        return [raw]
    out = []
    for value in raw.values():
        if isinstance(value, dict):
            out.extend(normalize_result_objects(value))
        elif isinstance(value, list):
            out.extend(normalize_result_objects(value))
    return out


def load_results(input_path: str) -> list[dict[str, Any]]:
    path = Path(input_path)
    if path.is_dir():
        records: list[dict[str, Any]] = []
        for json_path in sorted(path.glob("*.json")):
            records.extend(normalize_result_objects(load_json(json_path)))
        return records
    return normalize_result_objects(load_json(path))


def split_list(values: list, parity: int) -> list:
    """Select items at indices with given parity."""
    return [v for idx, v in enumerate(values) if idx % 2 == parity]


def sliced_numeric_values(query_block: dict[str, Any], keys: tuple[str, ...]) -> list[float]:
    for key in keys:
        values = query_block.get(key)
        if isinstance(values, list) and values:
            return [float(v) for v in split_list(values, SLICE_PARITY)]
    return []


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return ordered[lower] * (1.0 - frac) + ordered[upper] * frac


def query_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    correct = 0.0
    total = 0.0
    candidate_ratios: list[float] = []
    lookup_reductions: list[float] = []

    for record in records:
        query_block = record.get("queries", {})
        if not isinstance(query_block, dict):
            continue

        n_objects = record.get("n_objects", 0)
        correctness = sliced_numeric_values(
            query_block,
            ("individual_correct", "correct_flags", "is_correct"),
        )
        if correctness:
            correct += sum(correctness)
            total += len(correctness)
        else:
            correct += float(query_block.get("correct", 0) or 0)
            total += float(query_block.get("total", 0) or 0)

        candidates = sliced_numeric_values(query_block, ("individual_candidates",))
        if candidates and n_objects:
            candidate_ratios.extend(float(c) / float(n_objects) for c in candidates)
        elif n_objects:
            avg_candidates = query_block.get("col_candidate_objects_avg")
            if isinstance(avg_candidates, (int, float)):
                candidate_ratios.append(float(avg_candidates) / float(n_objects))

        lookups = sliced_numeric_values(
            query_block,
            ("individual_exact_lookups", "individual_lookups", "individual_candidates"),
        )
        if lookups and n_objects:
            lookup_reductions.extend(float(n_objects) / value for value in lookups if value > 0)
        elif n_objects:
            avg_lookups = query_block.get("col_exact_lookups_avg")
            if isinstance(avg_lookups, (int, float)) and avg_lookups > 0:
                lookup_reductions.append(float(n_objects) / float(avg_lookups))

    accuracy = correct / total if total else 0.0
    candidates_ratio = (
        sum(candidate_ratios) / len(candidate_ratios) if candidate_ratios else 1.0
    )

    metrics: dict[str, float] = {
        "accuracy": accuracy,
        "candidates_ratio": candidates_ratio,
    }

    if candidate_ratios:
        metrics["candidate_p90_ratio"] = quantile(candidate_ratios, 0.9)
        metrics["candidate_max_ratio"] = max(candidate_ratios)
    else:
        metrics["candidate_p90_ratio"] = candidates_ratio
        metrics["candidate_max_ratio"] = candidates_ratio

    if lookup_reductions:
        metrics["lookup_reduction_vs_brute"] = sum(lookup_reductions) / len(lookup_reductions)

    return metrics


def preprocessing_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    sul_times: list[float] = []
    col_times: list[float] = []
    slice_query_total_ms = 0.0
    full_query_total_ms = 0.0

    for record in records:
        sul_time = record.get("sul_time")
        col_time = record.get("col_time")
        if isinstance(sul_time, (int, float)):
            sul_times.append(float(sul_time))
        if isinstance(col_time, (int, float)):
            col_times.append(float(col_time))

        query_block = record.get("queries", {})
        if isinstance(query_block, dict):
            raw_times = query_block.get("individual_times") or []
            if isinstance(raw_times, list) and raw_times:
                full_query_total_ms += sum(float(v) for v in raw_times)
                sliced = split_list(raw_times, SLICE_PARITY) or raw_times
                slice_query_total_ms += sum(float(v) for v in sliced)

    avg_sul = sum(sul_times) / len(sul_times) if sul_times else 0.0
    avg_col = sum(col_times) / len(col_times) if col_times else 0.0
    workload_fraction = slice_query_total_ms / full_query_total_ms if full_query_total_ms > 0 else 0.5

    return {
        "sul_time_s": avg_sul * workload_fraction,
        "col_time_s": avg_col * workload_fraction,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the public train slice")
    parser.add_argument("results_path", help="Result JSON file or directory")
    parser.add_argument("--method-name", "-m", default=None)
    parser.add_argument("--output", "-o", default="/home/user/scoring/scores_train.json")
    args = parser.parse_args()

    inferred_name = Path(args.results_path).stem if Path(args.results_path).is_file() else Path(args.results_path).name
    method_names = [n for n in (args.method_name or inferred_name).replace(",", " ").split() if n]
    records = load_results(args.results_path)

    by_type: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_type.setdefault(str(record.get("query_type", "")), []).append(record)

    scores: dict[str, Any] = {}
    for method in method_names:
        for exp_name, qt in [
            ("aknn_real_pois", "aknn"),
            ("kfn_real_pois", "kfn"),
            ("range_real_pois", "range"),
        ]:
            metrics = query_metrics(by_type.get(qt, []))
            if exp_name not in scores:
                scores[exp_name] = {"results": {}}
            scores[exp_name]["results"][method] = metrics

        pp = preprocessing_metrics(records)
        if "preprocessing" not in scores:
            scores["preprocessing"] = {"results": {}}
        scores["preprocessing"]["results"][method] = pp

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as handle:
        json.dump(scores, handle, indent=2)
        handle.write("\n")

    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
