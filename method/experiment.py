#!/usr/bin/env python3
"""
Main experiment script for COL-Tree reproduction.
Runs AkNN, kFN, and range queries on available road networks.
"""

import os
import sys
import time
import random
import json
import argparse
from typing import List, Dict, Tuple, Optional

# Add project paths
sys.path.insert(0, '/home/user')

from data.graph import RoadNetwork, ObjectSet
from data.loader import load_network
from method.sul_tree import SULTree
from method.col_tree import COLTree
from method.baselines import (
    aknn_bruteforce, kfn_bruteforce, range_bruteforce,
    kfn_aubphl
)


def _valid_nearest_topk(graph, candidates, objects, Q, k, agg):
    """Accept any exact top-k set, including arbitrary choices among ties."""
    if len(set(candidates)) != min(k, len(objects.objects)):
        return False
    d_cache = {qi: graph.dijkstra(qi) for qi in Q}

    def score(obj):
        vals = [d_cache[qi][obj] for qi in Q]
        return max(vals) if agg == 'max' else sum(vals)

    all_scores = sorted(score(obj) for obj in objects.objects)
    threshold = all_scores[min(k, len(all_scores)) - 1]
    return all(score(obj) <= threshold + 1e-9 for obj in candidates)


def _valid_farthest_topk(graph, candidates, objects, q, k):
    """Accept any exact farthest top-k set, including ties."""
    if len(set(candidates)) != min(k, len(objects.objects)):
        return False
    dists = graph.dijkstra(q)
    all_scores = sorted((dists[obj] for obj in objects.objects), reverse=True)
    threshold = all_scores[min(k, len(all_scores)) - 1]
    return all(dists[obj] >= threshold - 1e-9 for obj in candidates)


def resolve_network_path(network_name: str) -> str:
    """Resolve a network file from known workspace locations."""
    candidates = {
        'usroads-48': [
            '/home/user/data/downloads/road-usroads-48.mtx',
            '/home/user/data/road-usroads-48.mtx',
        ],
        'roadnet-pa': [
            '/home/user/data/downloads/roadNet-PA.txt',
            '/home/user/data/roadNet-PA.txt',
        ],
    }
    if network_name not in candidates:
        raise ValueError(f"Unknown network: {network_name}")

    for path in candidates[network_name]:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"Could not find data for {network_name}. Run bash scripts/download.sh first."
    )


def run_experiment(network_name: str, query_type: str, k: int = 10,
                   n_queries: int = 50, density: float = 0.001,
                   agg: str = 'max', Q_size: int = 4,
                   radius_pct: float = 1.0,
                   b: int = 8, lam: int = 256, m: int = 2,
                   landmark_policy: str = 'random',
                   seed: int = 42) -> Dict:
    """Run a single experiment configuration."""

    # Load network
    print(f"Loading network {network_name}...")
    graph = load_network(resolve_network_path(network_name))
    print(f"  Loaded: {graph.num_vertices} vertices, {graph.num_edges} edges")

    # Generate object set
    print(f"Generating object set with density={density}...")
    obj_set = ObjectSet.uniform_random(graph, density, seed=seed)
    print(f"  Generated: {len(obj_set)} objects")

    # Build SUL-Tree
    print(f"Building SUL-Tree (b={b}, m={m}, alpha={lam*4})...")
    sul_start = time.time()
    sul_tree = SULTree(graph, b=b, m=m, alpha=lam*4, landmark_policy=landmark_policy)
    sul_tree.build()
    sul_time = time.time() - sul_start
    print(f"  SUL-Tree built in {sul_time:.2f}s")

    # Build COL-Tree
    print(f"Building COL-Tree (lambda={lam})...")
    col_start = time.time()
    col_tree = COLTree(graph, sul_tree, obj_set, lam=lam, b=b)
    col_time = time.time() - col_start
    print(f"  COL-Tree built in {col_time:.3f}s")

    # Generate query vertices
    random.seed(seed)
    query_vertices = random.sample(range(graph.num_vertices), min(n_queries * 2, graph.num_vertices))

    results = {
        'network': network_name,
        'query_type': query_type,
        'k': k,
        'density': density,
        'n_objects': len(obj_set),
        'n_query_vertices': n_queries,
        'sul_time': sul_time,
        'col_time': col_time,
        'queries': []
    }

    if query_type == 'aknn':
        results['agg'] = agg
        results['Q_size'] = Q_size
        _run_aknn_experiments(graph, obj_set, col_tree, query_vertices,
                               results, k, n_queries, agg, Q_size, seed)
    elif query_type == 'kfn':
        _run_kfn_experiments(graph, obj_set, sul_tree, col_tree, query_vertices,
                              results, k, n_queries, seed)
    elif query_type == 'range':
        results['radius_pct'] = radius_pct
        _run_range_experiments(graph, obj_set, col_tree, query_vertices,
                                results, radius_pct, n_queries, seed)
    elif query_type == 'all':
        # Run all query types
        results_all = {'aknn': None, 'kfn': None, 'range': None}
        agg_results = dict(results)
        agg_results['queries'] = []
        _run_aknn_experiments(graph, obj_set, col_tree, query_vertices,
                               agg_results, k, n_queries, agg, Q_size, seed)
        results_all['aknn'] = agg_results

        kfn_results = dict(results)
        kfn_results['queries'] = []
        _run_kfn_experiments(graph, obj_set, sul_tree, col_tree, query_vertices,
                              kfn_results, k, n_queries, seed)
        results_all['kfn'] = kfn_results

        rng_results = dict(results)
        rng_results['queries'] = []
        _run_range_experiments(graph, obj_set, col_tree, query_vertices,
                                rng_results, radius_pct, n_queries, seed)
        results_all['range'] = rng_results
        return results_all

    return results


def _run_aknn_experiments(graph, obj_set, col_tree, query_vertices,
                          results, k, n_queries, agg, Q_size, seed):
    """Run AkNN query experiments."""
    col_times = []
    brute_times = []
    correct = 0
    total = 0
    per_query_candidates = []

    for i in range(n_queries):
        if i * Q_size >= len(query_vertices):
            break
        Q = query_vertices[i * Q_size:(i + 1) * Q_size]

        # COL-Tree query with stats
        start = time.time()
        col_result, col_stats = col_tree.query_aknn(Q, k, agg, return_stats=True)
        col_time = time.time() - start
        col_times.append(col_time * 1000)
        per_query_candidates.append(col_stats['candidate_objects_retrieved'])

        start = time.time()
        brute_result = aknn_bruteforce(graph, obj_set, Q, k, agg)
        brute_time = time.time() - start
        brute_times.append(brute_time * 1000)

        if _valid_nearest_topk(graph, col_result, obj_set, Q, k, agg):
            correct += 1
        total += 1

    results['queries'] = {
        'col_avg_time_ms': sum(col_times) / len(col_times) if col_times else 0,
        'brute_avg_time_ms': sum(brute_times) / len(brute_times) if brute_times else 0,
        'correct': correct,
        'total': total,
        'accuracy': correct / total if total > 0 else 0,
        'individual_times': col_times,
        'individual_candidates': per_query_candidates,
        'col_candidate_objects_avg': sum(per_query_candidates) / len(per_query_candidates) if per_query_candidates else 0,
    }
    print(f"  AkNN ({agg}): COL avg={results['queries']['col_avg_time_ms']:.3f}ms, "
          f"Brute avg={results['queries']['brute_avg_time_ms']:.3f}ms, "
          f"Accuracy={results['queries']['accuracy']:.1%}")


def _run_kfn_experiments(graph, obj_set, sul_tree, col_tree, query_vertices,
                          results, k, n_queries, seed):
    """Run kFN query experiments."""
    col_times = []
    brute_times = []
    aub_times = []
    correct = 0
    total = 0
    aub_correct = 0
    aub_total = 0
    col_candidate_counts = []
    col_exact_lookups = []
    aub_candidate_counts = []
    aub_exact_lookups = []

    for i in range(n_queries):
        q = query_vertices[i]

        # COL-Tree query
        start = time.time()
        col_result, col_stats = col_tree.query_kfn(q, k, return_stats=True)
        col_time = time.time() - start
        col_times.append(col_time * 1000)
        col_candidate_counts.append(col_stats['candidate_objects_retrieved'])
        col_exact_lookups.append(col_stats['exact_distance_lookups'])

        start = time.time()
        aub_result, aub_stats = kfn_aubphl(
            graph,
            obj_set,
            q,
            k,
            landmarks=sul_tree.root.landmarks,
            landmark_sdls=sul_tree.root.sdls,
            return_stats=True,
        )
        aub_time = time.time() - start
        aub_times.append(aub_time * 1000)
        aub_candidate_counts.append(aub_stats['scanned_candidates'])
        aub_exact_lookups.append(aub_stats['exact_distance_lookups'])

        start = time.time()
        brute_result = kfn_bruteforce(graph, obj_set, q, k)
        brute_time = time.time() - start
        brute_times.append(brute_time * 1000)

        if _valid_farthest_topk(graph, col_result, obj_set, q, k):
            correct += 1
        if _valid_farthest_topk(graph, aub_result, obj_set, q, k):
            aub_correct += 1
        total += 1
        aub_total += 1

    results['queries'] = {
        'col_avg_time_ms': sum(col_times) / len(col_times) if col_times else 0,
        'aub_avg_time_ms': sum(aub_times) / len(aub_times) if aub_times else 0,
        'brute_avg_time_ms': sum(brute_times) / len(brute_times) if brute_times else 0,
        'correct': correct,
        'total': total,
        'accuracy': correct / total if total > 0 else 0,
        'individual_times': col_times,
        'aub_individual_times': aub_times,
        'aub_correct': aub_correct,
        'aub_total': aub_total,
        'aub_accuracy': aub_correct / aub_total if aub_total > 0 else 0,
        'speedup_over_aub': (
            (sum(aub_times) / len(aub_times)) / (sum(col_times) / len(col_times))
            if col_times and aub_times and sum(col_times) > 0
            else 0
        ),
        'col_candidate_objects_avg': (
            sum(col_candidate_counts) / len(col_candidate_counts)
            if col_candidate_counts else 0
        ),
        'col_exact_lookups_avg': (
            sum(col_exact_lookups) / len(col_exact_lookups)
            if col_exact_lookups else 0
        ),
        'individual_candidates': col_candidate_counts,
        'aub_candidate_objects_avg': (
            sum(aub_candidate_counts) / len(aub_candidate_counts)
            if aub_candidate_counts else 0
        ),
        'aub_exact_lookups_avg': (
            sum(aub_exact_lookups) / len(aub_exact_lookups)
            if aub_exact_lookups else 0
        ),
    }
    print(f"  kFN: COL avg={results['queries']['col_avg_time_ms']:.3f}ms, "
          f"AUB avg={results['queries']['aub_avg_time_ms']:.3f}ms, "
          f"Brute avg={results['queries']['brute_avg_time_ms']:.3f}ms, "
          f"Accuracy={results['queries']['accuracy']:.1%}, "
          f"COL/AUB exact lookups={results['queries']['col_exact_lookups_avg']:.1f}/"
          f"{results['queries']['aub_exact_lookups_avg']:.1f}")


def _run_range_experiments(graph, obj_set, col_tree, query_vertices,
                           results, radius_pct, n_queries, seed):
    """Run range query experiments."""
    # Compute approximate diameter
    print("  Computing approximate diameter...")
    sample_sources = random.sample(range(graph.num_vertices), min(10, graph.num_vertices))
    max_dist = 0
    for src in sample_sources[:3]:
        dists = graph.dijkstra(src)
        max_d = max(d for d in dists if d < float('inf'))
        if max_d > max_dist:
            max_dist = max_d

    diameter = max_dist * 2 if max_dist > 0 else 1000
    radius = diameter * (radius_pct / 100.0)

    col_times = []
    brute_times = []
    correct = 0
    total = 0
    per_query_candidates = []

    for i in range(n_queries):
        q = query_vertices[i]

        # COL-Tree query with stats
        start = time.time()
        col_result, col_stats = col_tree.query_range(q, radius, return_stats=True)
        col_time = time.time() - start
        col_times.append(col_time * 1000)
        per_query_candidates.append(col_stats['candidate_objects_retrieved'])

        start = time.time()
        brute_result = range_bruteforce(graph, obj_set, q, radius)
        brute_time = time.time() - start
        brute_times.append(brute_time * 1000)

        col_set = set(col_result)
        brute_set = set(brute_result)
        if col_set == brute_set:
            correct += 1
        total += 1

    results['queries'] = {
        'radius': radius,
        'diameter_approx': diameter,
        'col_avg_time_ms': sum(col_times) / len(col_times) if col_times else 0,
        'brute_avg_time_ms': sum(brute_times) / len(brute_times) if brute_times else 0,
        'correct': correct,
        'total': total,
        'accuracy': correct / total if total > 0 else 0,
        'individual_times': col_times,
        'individual_candidates': per_query_candidates,
        'col_candidate_objects_avg': sum(per_query_candidates) / len(per_query_candidates) if per_query_candidates else 0,
    }
    print(f"  Range (r={radius:.1f}): COL avg={results['queries']['col_avg_time_ms']:.3f}ms, "
          f"Brute avg={results['queries']['brute_avg_time_ms']:.3f}ms, "
          f"Accuracy={results['queries']['accuracy']:.1%}")


def main():
    parser = argparse.ArgumentParser(description='COL-Tree experiments')
    parser.add_argument('--network', '-n', default='usroads-48',
                        choices=['usroads-48', 'roadnet-pa'],
                        help='Road network to use')
    parser.add_argument('--query', '-q', default='aknn',
                        choices=['aknn', 'kfn', 'range', 'all'],
                        help='Query type to run')
    parser.add_argument('--k', type=int, default=10, help='Number of results (k)')
    parser.add_argument('--n-queries', type=int, default=50, help='Number of queries')
    parser.add_argument('--density', type=float, default=0.001, help='Object density |P|/|V|')
    parser.add_argument('--agg', default='max', choices=['max', 'sum'], help='Aggregate function')
    parser.add_argument('--Q-size', type=int, default=4, help='Number of query vertices for AkNN')
    parser.add_argument('--radius-pct', type=float, default=1.0, help='Radius as %% of diameter')
    parser.add_argument('--b', type=int, default=8, help='Branching factor')
    parser.add_argument('--lam', type=int, default=256, help='Max objects per leaf')
    parser.add_argument('--m', type=int, default=2, help='Number of landmarks per node')
    parser.add_argument('--landmark-policy', default='random',
                        choices=['random', 'border', 'minmax'],
                        help='Landmark selection policy')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--output', '-o', help='Output JSON file')

    args = parser.parse_args()

    print("=" * 60)
    print("COL-Tree Reproduction Experiment")
    print("=" * 60)

    results = run_experiment(
        network_name=args.network,
        query_type=args.query,
        k=args.k,
        n_queries=args.n_queries,
        density=args.density,
        agg=args.agg,
        Q_size=args.Q_size,
        radius_pct=args.radius_pct,
        b=args.b,
        lam=args.lam,
        m=args.m,
        landmark_policy=args.landmark_policy,
        seed=args.seed
    )

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Network: {results['network']}")
    print(f"Objects: {results['n_objects']}")
    print(f"Queries: {results['n_query_vertices']}")
    print(f"SUL-Tree time: {results['sul_time']:.2f}s")
    print(f"COL-Tree time: {results['col_time']:.3f}s")

    if 'queries' in results:
        q = results['queries']
        print(f"COL avg query time: {q['col_avg_time_ms']:.3f}ms")
        print(f"Accuracy: {q['accuracy']:.1%}")


if __name__ == '__main__':
    main()
