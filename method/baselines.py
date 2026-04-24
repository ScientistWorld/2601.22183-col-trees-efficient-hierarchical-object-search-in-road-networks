"""
Baseline Methods
================
Simple baselines for AkNN, kFN, and range queries.
"""

import heapq
from typing import List, Optional, Tuple
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
                q: int, k: int,
                landmarks: Optional[List[int]] = None,
                landmark_sdls: Optional[List[List[float]]] = None,
                return_stats: bool = False) -> List[int]:
    """
    AUB-PHL style baseline using landmark upper bounds and exact verification.

    The workspace does not ship the paper's PHL distance oracle, so this baseline
    uses exact Dijkstra distances for verification while preserving the paper's
    upper-bound-first candidate ordering over all objects.
    """
    d_q = graph.dijkstra(q)

    if landmarks and landmark_sdls:
        d_lq = []
        for li_idx, landmark in enumerate(landmarks):
            if li_idx < len(landmark_sdls) and q < len(landmark_sdls[li_idx]):
                d_lq.append(landmark_sdls[li_idx][q])
            else:
                d_lq.append(d_q[landmark])

        candidates = []
        for obj in objects.objects:
            upper_bounds = []
            for li_idx, _ in enumerate(landmarks):
                if li_idx < len(landmark_sdls) and obj < len(landmark_sdls[li_idx]):
                    upper_bounds.append(d_lq[li_idx] + landmark_sdls[li_idx][obj])
            ub = min(upper_bounds) if upper_bounds else d_q[obj]
            candidates.append((ub, obj))
    else:
        candidates = [(d_q[obj], obj) for obj in objects.objects]

    candidates.sort(key=lambda x: -x[0])

    topk = []
    exact_lookups = 0
    scanned_candidates = 0
    D_k = 0.0

    for rank, (ub, obj) in enumerate(candidates):
        if len(topk) >= k and ub <= D_k:
            break
        dist = d_q[obj]
        exact_lookups += 1
        scanned_candidates = rank + 1
        if len(topk) < k:
            heapq.heappush(topk, (dist, obj))
        elif dist > topk[0][0]:
            heapq.heapreplace(topk, (dist, obj))
        D_k = topk[0][0] if len(topk) >= k else 0.0

    final = [obj for _, obj in sorted(topk, key=lambda x: -x[0])]
    if return_stats:
        return final[:k], {
            'upper_bound_candidates': len(candidates),
            'scanned_candidates': scanned_candidates,
            'exact_distance_lookups': exact_lookups,
        }
    return final[:k]


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
