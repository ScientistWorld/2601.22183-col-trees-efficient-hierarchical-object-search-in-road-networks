#!/usr/bin/env python3
"""
Evaluation and scoring for COL-Tree reproduction.
Computes metrics from experiment results and writes scores.json.
"""

import sys
import os
import json
import argparse
from pathlib import Path

sys.path.insert(0, '/home/user')


def load_scores(results_file: str) -> dict:
    """Load experiment results from JSON."""
    with open(results_file, 'r') as f:
        return json.load(f)


def compute_composite_score(experiment_results: dict, reference: dict,
                            experiment_name: str) -> float:
    """
    Compute composite score for an experiment.
    Based on the metric coefficients in reference.json.
    """
    if experiment_name not in reference['experiments']:
        return 0.0

    exp_ref = reference['experiments'][experiment_name]
    metrics = exp_ref.get('metrics', {})
    weight = exp_ref.get('weight', 1.0)

    if experiment_name not in experiment_results:
        return 0.0

    exp_res = experiment_results[experiment_name]
    results = exp_res.get('results', {})

    score = 0.0
    for method_name, method_results in results.items():
        method_score = 0.0
        for metric_name, metric_info in metrics.items():
            if metric_name in method_results:
                value = method_results[metric_name]
                coeff = metric_info.get('coefficient', 0.0)
                hib = metric_info.get('higher_is_better', True)

                if hib:
                    # Higher is better: positive contribution
                    # Normalize relative to baseline
                    method_score += coeff * value
                else:
                    # Constraint metric: negative coefficient means lower is better
                    method_score += coeff * value

        score += method_score

    return score * weight


def evaluate_aknn(results: dict) -> dict:
    """Evaluate AkNN query results."""
    q = results.get('queries', {})

    avg_col_time = q.get('col_avg_time_ms', 0)
    avg_brute_time = q.get('brute_avg_time_ms', 0)
    accuracy = q.get('accuracy', 0)

    # Speedup over brute force
    speedup = avg_brute_time / avg_col_time if avg_col_time > 0 else 0

    return {
        'avg_query_time_ms': avg_col_time,
        'brute_force_time_ms': avg_brute_time,
        'speedup_over_brute': speedup,
        'correct': q.get('correct', 0),
        'total': q.get('total', 0),
        'accuracy': accuracy,
    }


def evaluate_kfn(results: dict) -> dict:
    """Evaluate kFN query results."""
    q = results.get('queries', {})

    avg_col_time = q.get('col_avg_time_ms', 0)
    avg_brute_time = q.get('brute_avg_time_ms', 0)
    accuracy = q.get('accuracy', 0)

    speedup = avg_brute_time / avg_col_time if avg_col_time > 0 else 0

    return {
        'avg_query_time_ms': avg_col_time,
        'brute_force_time_ms': avg_brute_time,
        'speedup_over_brute': speedup,
        'correct': q.get('correct', 0),
        'total': q.get('total', 0),
        'accuracy': accuracy,
    }


def evaluate_range(results: dict) -> dict:
    """Evaluate range query results."""
    q = results.get('queries', {})

    avg_col_time = q.get('col_avg_time_ms', 0)
    avg_brute_time = q.get('brute_avg_time_ms', 0)
    accuracy = q.get('accuracy', 0)
    radius = q.get('radius', 0)

    speedup = avg_brute_time / avg_col_time if avg_col_time > 0 else 0

    return {
        'avg_query_time_ms': avg_col_time,
        'brute_force_time_ms': avg_brute_time,
        'speedup_over_brute': speedup,
        'radius': radius,
        'correct': q.get('correct', 0),
        'total': q.get('total', 0),
        'accuracy': accuracy,
    }


def evaluate_preprocessing(results: dict) -> dict:
    """Evaluate preprocessing performance."""
    return {
        'sul_time_s': results.get('sul_time', 0),
        'col_time_s': results.get('col_time', 0),
        'n_objects': results.get('n_objects', 0),
        'network': results.get('network', ''),
    }


def main():
    parser = argparse.ArgumentParser(description='Evaluate COL-Tree results')
    parser.add_argument('results_file', help='Path to results JSON file')
    parser.add_argument('--reference', '-r',
                        default='/home/user/scoring/reference.json',
                        help='Reference JSON file')
    parser.add_argument('--output', '-o',
                        default='/home/user/scoring/scores.json',
                        help='Output scores JSON file')
    parser.add_argument('--method-name', '-m',
                        default='colt_our',
                        help='Method name for reporting')
    args = parser.parse_args()

    # Load results
    results = load_scores(args.results_file)

    # Build scores structure
    scores = {}

    # Determine experiment type and evaluate accordingly
    query_type = results.get('query_type', 'unknown')

    if query_type == 'aknn' or 'aknn' in str(results):
        scores['aknn_queries'] = {
            'results': {
                args.method_name: evaluate_aknn(results)
            }
        }

    if query_type == 'kfn':
        scores['kfn_queries'] = {
            'results': {
                args.method_name: evaluate_kfn(results)
            }
        }

    if query_type == 'range':
        scores['range_queries'] = {
            'results': {
                args.method_name: evaluate_range(results)
            }
        }

    scores['preprocessing'] = {
        'results': {
            args.method_name: evaluate_preprocessing(results)
        }
    }

    # Write scores
    with open(args.output, 'w') as f:
        json.dump(scores, f, indent=2)
    print(f"Scores written to {args.output}")
    print(json.dumps(scores, indent=2))


if __name__ == '__main__':
    main()
