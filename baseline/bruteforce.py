"""Method-agnostic baselines for road-network POI queries."""

import heapq
from typing import Optional
from typing import List

from data.graph import ObjectSet, RoadNetwork


def aknn_bruteforce(
    graph: RoadNetwork, objects: ObjectSet, query_vertices: List[int], k: int, agg: str = "max"
) -> List[int]:
    distance_cache = {q: graph.dijkstra(q) for q in query_vertices}
    scored = []
    for obj in objects.objects:
        distances = [distance_cache[q][obj] for q in query_vertices]
        score = sum(distances) if agg == "sum" else max(distances)
        scored.append((score, obj))
    scored.sort(key=lambda item: item[0])
    return [obj for _, obj in scored[:k]]


def kfn_bruteforce(graph: RoadNetwork, objects: ObjectSet, query_vertex: int, k: int) -> List[int]:
    distances = graph.dijkstra(query_vertex)
    scored = [(distances[obj], obj) for obj in objects.objects if obj < len(distances)]
    scored.sort(key=lambda item: -item[0])
    return [obj for _, obj in scored[:k]]


def kfn_aubphl(
    graph: RoadNetwork,
    objects: ObjectSet,
    query_vertex: int,
    k: int,
    landmarks: Optional[List[int]] = None,
    landmark_sdls: Optional[List[List[float]]] = None,
    return_stats: bool = False,
):
    """AUB-PHL-style upper-bound baseline with exact Dijkstra verification."""
    distances = graph.dijkstra(query_vertex)

    if landmarks and landmark_sdls:
        landmark_to_query = []
        for li_idx, landmark in enumerate(landmarks):
            if li_idx < len(landmark_sdls) and query_vertex < len(landmark_sdls[li_idx]):
                landmark_to_query.append(landmark_sdls[li_idx][query_vertex])
            else:
                landmark_to_query.append(distances[landmark])

        candidates = []
        for obj in objects.objects:
            upper_bounds = []
            for li_idx, _ in enumerate(landmarks):
                if li_idx < len(landmark_sdls) and obj < len(landmark_sdls[li_idx]):
                    upper_bounds.append(landmark_to_query[li_idx] + landmark_sdls[li_idx][obj])
            candidates.append((min(upper_bounds) if upper_bounds else distances[obj], obj))
    else:
        candidates = [(distances[obj], obj) for obj in objects.objects]

    candidates.sort(key=lambda item: -item[0])

    topk = []
    exact_lookups = 0
    scanned_candidates = 0
    kth_distance = 0.0

    for rank, (upper_bound, obj) in enumerate(candidates):
        if len(topk) >= k and upper_bound <= kth_distance:
            break
        distance = distances[obj]
        exact_lookups += 1
        scanned_candidates = rank + 1
        if len(topk) < k:
            heapq.heappush(topk, (distance, obj))
        elif distance > topk[0][0]:
            heapq.heapreplace(topk, (distance, obj))
        kth_distance = topk[0][0] if len(topk) >= k else 0.0

    final = [obj for _, obj in sorted(topk, key=lambda item: -item[0])]
    if return_stats:
        return final[:k], {
            "upper_bound_candidates": len(candidates),
            "scanned_candidates": scanned_candidates,
            "exact_distance_lookups": exact_lookups,
        }
    return final[:k]


def range_bruteforce(graph: RoadNetwork, objects: ObjectSet, query_vertex: int, radius: float) -> List[int]:
    distances = graph.dijkstra(query_vertex)
    return [
        obj for obj in objects.objects
        if obj < len(distances) and distances[obj] <= radius
    ]
