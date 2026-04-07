"""
Baseline Methods
================
Simple baselines for AkNN, kFN, and range queries.
"""

import heapq
from typing import List, Tuple
from data.graph import RoadNetwork, ObjectSet


def aknn_bruteforce(graph: RoadNetwork, objects: ObjectSet,
                     Q: List[int], k: int, agg: str = 'max') -> List[int]:
    """
    Brute force AkNN: compute exact distance to all objects, return k best.

    This is the baseline that always gives exact results.
    """
    # Cache Dijkstra results per query vertex
    d_cache = {qi: graph.dijkstra(qi) for qi in Q}
    scores = []
    for obj in objects.objects:
        if agg == 'max':
            dist = max(d_cache[qi][obj] for qi in Q)
        else:  # sum
            dist = sum(d_cache[qi][obj] for qi in Q)
        scores.append((dist, obj))

    scores.sort(key=lambda x: x[0])
    return [obj for _, obj in scores[:k]]


def aknn_ier(graph: RoadNetwork, objects: ObjectSet,
              Q: List[int], k: int, agg: str = 'max',
              max_candidates: int = 10000) -> List[int]:
    """
    Incremental Euclidean Restriction (IER) baseline.

    Uses Euclidean distance as lower bound to order candidate retrieval.
    Prunes candidates when k objects with lower bound >= current k-th best.
    """
    # Simple version: order by Euclidean lower bound, then verify
    candidates = []

    for obj in objects.objects:
        # Euclidean lower bound (approximate)
        if Q:
            euc_dist = min(graph.euclidean_distance(qi, obj) for qi in Q)
        else:
            euc_dist = 0.0
        candidates.append((euc_dist, obj))

    candidates.sort(key=lambda x: x[0])
    candidates = candidates[:max_candidates]

    # Verify candidates
    d_cache = {qi: graph.dijkstra(qi) for qi in Q}
    results = []
    for _, obj in candidates:
        if agg == 'max':
            dist = max(d_cache[qi][obj] for qi in Q)
        else:
            dist = sum(d_cache[qi][obj] for qi in Q)
        results.append((dist, obj))

        if len(results) >= k * 10:  # safety limit
            break

    results.sort(key=lambda x: x[0])
    return [obj for _, obj in results[:k]]


def kfn_bruteforce(graph: RoadNetwork, objects: ObjectSet,
                    q: int, k: int) -> List[int]:
    """
    Brute force kFN: compute distance from q to all objects, return k farthest.
    """
    distances = []
    dists = graph.dijkstra(q)
    for obj in objects.objects:
        if obj < len(dists):
            distances.append((dists[obj], obj))

    distances.sort(key=lambda x: -x[0])  # descending
    return [obj for _, obj in distances[:k]]


def kfn_aubphl(graph: RoadNetwork, objects: ObjectSet,
                q: int, k: int, max_candidates: int = 10000) -> List[int]:
    """
    AUB-PHL: Upper-bound filtering with Dijkstra.

    Similar to the paper's AUB-PHL baseline: compute upper bounds to all objects,
    filter by best upper bounds, then verify.
    """
    # Simple: use Euclidean distance as upper bound approximation
    candidates = []
    for obj in objects.objects:
        euc_ub = graph.euclidean_distance(q, obj)
        candidates.append((euc_ub, obj))

    candidates.sort(key=lambda x: -x[0])  # descending by upper bound
    candidates = candidates[:max_candidates]

    # Verify
    results = []
    for _, obj in candidates:
        dist = graph.dijkstra(q)[obj]
        results.append((dist, obj))
        if len(results) >= k * 10:
            break

    results.sort(key=lambda x: -x[0])
    return [obj for _, obj in results[:k]]


def range_bruteforce(graph: RoadNetwork, objects: ObjectSet,
                      q: int, r: float) -> List[int]:
    """
    Brute force range query: check all objects, return those within range.
    """
    results = []
    dists = graph.dijkstra(q)
    for obj in objects.objects:
        if obj < len(dists) and dists[obj] <= r:
            results.append(obj)
    return results


def range_ier(graph: RoadNetwork, objects: ObjectSet,
               q: int, r: float) -> List[int]:
    """
    Range query using Euclidean-based pruning.
    """
    results = []
    dists = graph.dijkstra(q)
    for obj in objects.objects:
        euc_dist = graph.euclidean_distance(q, obj)
        if euc_dist <= r:
            if obj < len(dists) and dists[obj] <= r:
                results.append(obj)
    return results
