#!/usr/bin/env python3
"""Held-out test-slice evaluator for COL-Tree result artifacts.

This script is method-agnostic: it reads the same pre-generated artifacts as
the train evaluator, but scores the hidden odd-index query slice.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SLICE_PARITY = 1


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


def split_times(query_block: dict[str, Any]) -> list[float]:
    times = query_block.get("individual_times") or []
    if not isinstance(times, list) or not times:
        avg = query_block.get("col_avg_time_ms", 0.0)
        return [float(avg)] if avg else []

    selected = [float(value) for idx, value in enumerate(times) if idx % 2 == SLICE_PARITY]
    return selected or [float(value) for value in times]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return ordered[idx]


def query_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    all_times: list[float] = []
    brute_values: list[float] = []
    correct = 0.0
    total = 0.0

    for record in records:
        query_block = record.get("queries", {})
        if not isinstance(query_block, dict):
            continue

        all_times.extend(split_times(query_block))

        brute_time = query_block.get("brute_avg_time_ms")
        if isinstance(brute_time, (int, float)) and brute_time > 0:
            brute_values.append(float(brute_time))

        correct += float(query_block.get("correct", 0) or 0)
        total += float(query_block.get("total", 0) or 0)

    avg_time = sum(all_times) / len(all_times) if all_times else 0.0
    brute_avg = sum(brute_values) / len(brute_values) if brute_values else 0.0

    return {
        "avg_query_time_ms": avg_time,
        "p90_query_time_ms": percentile(all_times, 90.0),
        "accuracy": correct / total if total else 0.0,
        "speedup_over_brute": brute_avg / avg_time if avg_time > 0 else 0.0,
    }


def preprocessing_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    for record in records:
        sul_time = record.get("sul_time")
        col_time = record.get("col_time")
        if isinstance(sul_time, (int, float)) and isinstance(col_time, (int, float)):
            return {"sul_time_s": float(sul_time), "col_time_s": float(col_time)}
    return {"sul_time_s": 0.0, "col_time_s": 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the held-out test slice")
    parser.add_argument("results_path", help="Result JSON file or directory of JSON artifacts")
    parser.add_argument("--method-name", "-m", default="colt_phl")
    parser.add_argument("--output", "-o", default="/home/user/scoring/scores_test.json")
    args = parser.parse_args()

    records = load_results(args.results_path)
    by_type: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_type.setdefault(str(record.get("query_type", "")), []).append(record)

    scores = {
        "aknn_real_pois": {
            "results": {args.method_name: query_metrics(by_type.get("aknn", []))}
        },
        "aknn_sensitivity_density": {
            "results": {args.method_name: query_metrics(by_type.get("aknn", []))}
        },
        "kfn_real_pois": {
            "results": {args.method_name: query_metrics(by_type.get("kfn", []))}
        },
        "range_real_pois": {
            "results": {args.method_name: query_metrics(by_type.get("range", []))}
        },
        "preprocessing": {
            "results": {args.method_name: preprocessing_metrics(records)}
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as handle:
        json.dump(scores, handle, indent=2)
        handle.write("\n")

    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
