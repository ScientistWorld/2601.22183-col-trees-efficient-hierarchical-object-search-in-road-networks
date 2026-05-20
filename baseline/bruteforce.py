"""Method-agnostic brute-force baselines for road-network POI queries."""

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


def range_bruteforce(graph: RoadNetwork, objects: ObjectSet, query_vertex: int, radius: float) -> List[int]:
    distances = graph.dijkstra(query_vertex)
    return [
        obj for obj in objects.objects
        if obj < len(distances) and distances[obj] <= radius
    ]
