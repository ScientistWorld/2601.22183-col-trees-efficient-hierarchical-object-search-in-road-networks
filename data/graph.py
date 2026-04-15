"""
Road Network Graph
=================
Core graph data structure for road networks. Used by both data loaders
and the indexing algorithms.
"""

import heapq
import random
from typing import List, Dict, Tuple, Optional


class RoadNetwork:
    """Road network graph with weighted edges."""

    def __init__(self):
        self.adj: List[List[Tuple[int, float]]] = []  # adjacency list: (neighbor, weight)
        self.coords: List[Tuple[float, float]] = []  # (lat, lon) per vertex
        self.num_vertices = 0
        self.num_edges = 0

    @classmethod
    def from_dimacs(cls, filepath: str) -> 'RoadNetwork':
        """Load road network from DIMACS format file."""
        gn = cls()
        edges = []

        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('c'):
                    continue
                parts = line.split()
                if parts[0] == 'p':
                    n = int(parts[2])
                    gn.num_vertices = n
                    gn.adj = [[] for _ in range(n)]
                    gn.coords = [(0.0, 0.0) for _ in range(n)]
                elif parts[0] == 'a':
                    u, v, w = int(parts[1]) - 1, int(parts[2]) - 1, float(parts[3])
                    edges.append((u, v, w))
                    gn.adj[u].append((v, w))
                    gn.num_edges += 1
                elif parts[0] == 'e':
                    u, v, w = int(parts[1]) - 1, int(parts[2]) - 1, float(parts[3])
                    edges.append((u, v, w))
                    edges.append((v, u, w))
                    gn.adj[u].append((v, w))
                    gn.adj[v].append((u, w))
                    gn.num_edges += 2
                elif parts[0] == 'n':
                    idx = int(parts[1]) - 1
                    lat = float(parts[2])
                    lon = float(parts[3])
                    if idx < len(gn.coords):
                        gn.coords[idx] = (lat, lon)

        if gn.num_edges == 0 and edges:
            for u, v, w in edges:
                gn.adj[u].append((v, w))
                gn.num_edges += 1

        if gn.num_vertices == 0:
            gn.num_vertices = len(gn.adj)
        return gn

    @classmethod
    def from_numpy_edges(cls, n: int, edges: List[Tuple[int, int, float]]) -> 'RoadNetwork':
        """Build road network from list of edges."""
        gn = cls()
        gn.num_vertices = n
        gn.adj = [[] for _ in range(n)]
        gn.coords = [(0.0, 0.0) for _ in range(n)]
        for u, v, w in edges:
            gn.adj[u].append((v, w))
            gn.adj[v].append((u, w))
            gn.num_edges += 2
        return gn

    def dijkstra(self, source: int) -> List[float]:
        """Single-source Dijkstra. Returns distances to all vertices."""
        INF = float('inf')
        dist = [INF] * self.num_vertices
        dist[source] = 0.0
        pq = [(0.0, source)]
        visited = [False] * self.num_vertices

        while pq:
            d, u = heapq.heappop(pq)
            if visited[u]:
                continue
            visited[u] = True
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        return dist

    def dijkstra_to_targets(self, source: int, targets: List[int],
                            early_stop: bool = True) -> List[float]:
        """Dijkstra stopping when all targets are settled."""
        INF = float('inf')
        dist = [INF] * self.num_vertices
        dist[source] = 0.0
        pq = [(0.0, source)]
        target_set = set(targets)
        remaining = len(targets)
        found = {}

        while pq and remaining > 0:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if u in target_set and u not in found:
                found[u] = d
                remaining -= 1
                if early_stop and remaining == 0:
                    break
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))

        return dist

    def dijkstra_settled(self, source: int) -> Tuple[List[float], int]:
        """Dijkstra returning distances and number of settled vertices."""
        INF = float('inf')
        dist = [INF] * self.num_vertices
        dist[source] = 0.0
        pq = [(0.0, source)]
        visited = [False] * self.num_vertices
        settled = 0

        while pq:
            d, u = heapq.heappop(pq)
            if visited[u]:
                continue
            visited[u] = True
            settled += 1
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        return dist, settled

    def dijkstra_with_cutoff(self, source: int, cutoff: float) -> List[float]:
        """Dijkstra with a distance cutoff."""
        INF = float('inf')
        dist = [INF] * self.num_vertices
        dist[source] = 0.0
        pq = [(0.0, source)]

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if d > cutoff:
                break
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist[v] and nd <= cutoff:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        return dist

    def euclidean_distance(self, u: int, v: int) -> float:
        """Approximate Euclidean distance between two vertices using coordinates."""
        lat1, lon1 = self.coords[u] if u < len(self.coords) else (0, 0)
        lat2, lon2 = self.coords[v] if v < len(self.coords) else (0, 0)
        if lat1 == 0 and lon1 == 0 and lat2 == 0 and lon2 == 0:
            return 1.0  # fallback
        return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5

    def random_vertices(self, n: int, seed: int = 42) -> List[int]:
        """Return n random vertex IDs."""
        random.seed(seed)
        return random.sample(range(self.num_vertices), min(n, self.num_vertices))

    def diameter_approx(self) -> float:
        """Approximate graph diameter using double-sweep method."""
        source = random.randint(0, self.num_vertices - 1)
        dist = self.dijkstra(source)
        farthest = max(range(self.num_vertices), key=lambda i: dist[i])
        dist2 = self.dijkstra(farthest)
        return max(dist2)


class ObjectSet:
    """Set of POI (Point of Interest) objects in a road network."""

    def __init__(self, objects: List[int], graph: RoadNetwork):
        self.objects = objects
        self.graph = graph
        self.obj_set = set(objects)

    @classmethod
    def uniform_random(cls, graph: RoadNetwork, density: float, seed: int = 42) -> 'ObjectSet':
        """Generate uniform random object set with given density = |P|/|V|."""
        n_objs = int(graph.num_vertices * density)
        random.seed(seed)
        objects = random.sample(range(graph.num_vertices), n_objs)
        return cls(objects, graph)

    @classmethod
    def from_file(cls, filepath: str, graph: RoadNetwork) -> 'ObjectSet':
        """Load object set from file (one vertex ID per line)."""
        objects = []
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    vid = int(line.strip())
                    if 0 <= vid < graph.num_vertices:
                        objects.append(vid)
        return cls(objects, graph)

    def contains(self, vertex: int) -> bool:
        return vertex in self.obj_set

    def __len__(self):
        return len(self.objects)
