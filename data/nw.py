"""Public loaders for the North-West US road network used by this gym.

Data come from the paper's own Zenodo dataset (see scripts/download.sh):
  * NW-t.graph        DIMACS travel-time road network (largest component)
  * NW-t.coordinates  longitude/latitude (x 1e6) per vertex
  * pois/<name>.txt   real OpenStreetMap POI categories mapped to vertices

This is the *public* base network.  The scored evaluations run on hidden
travel-time conditions of the same road network (see briefing/evaluation.md),
so distances computed on this graph are only approximations of the
distances the evaluator uses.

Everything here works with the standard library; numpy is used when present.
"""

from __future__ import annotations

import os
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POI_CATEGORIES = (
    "school", "park", "post_office", "fast_food",
    "hotel", "hospital", "university", "courthouse",
)

try:  # optional acceleration
    import numpy as _np
except Exception:  # pragma: no cover - stdlib fallback
    _np = None


def data_dir() -> str:
    return os.environ.get("COLT_DATA_DIR") or os.path.join(ROOT, "data", "downloads", "nw")


class Graph:
    """Undirected weighted graph in CSR form (both arc directions stored)."""

    def __init__(self, n, indptr, indices, weights, xs=None, ys=None):
        self.n = n
        self.indptr = indptr
        self.indices = indices
        self.weights = weights
        self.xs = xs
        self.ys = ys

    def neighbors(self, v):
        a, b = int(self.indptr[v]), int(self.indptr[v + 1])
        return [(int(self.indices[i]), self.weights[i]) for i in range(a, b)]

    def edges(self):
        """Yield undirected edges (u, v, w) with u < v."""
        for u in range(self.n):
            for i in range(int(self.indptr[u]), int(self.indptr[u + 1])):
                v = int(self.indices[i])
                if u < v:
                    yield u, v, self.weights[i]


def _read_edges(path):
    """Return (n, list_of_(a, b, w)) with a < b, minimum weight per pair."""
    with open(path) as handle:
        header = handle.readline().split()
        n = int(header[2])
        best = {}
        for line in handle:
            parts = line.split()
            if len(parts) < 3:
                continue
            u, v, w = int(parts[0]), int(parts[1]), int(parts[2])
            if u == v:
                continue
            a, b = (u, v) if u < v else (v, u)
            key = a * n + b
            old = best.get(key)
            if old is None or w < old:
                best[key] = w
    edges = [(key // n, key % n, w) for key, w in best.items()]
    return n, edges


def _csr_from_edges(n, edges):
    deg = [0] * (n + 1)
    for a, b, _ in edges:
        deg[a + 1] += 1
        deg[b + 1] += 1
    for i in range(n):
        deg[i + 1] += deg[i]
    indptr = array("q", deg)
    fill = list(deg[:-1])
    indices = array("q", [0]) * (2 * len(edges))
    weights = array("q", [0]) * (2 * len(edges))
    for a, b, w in edges:
        i = fill[a]; indices[i] = b; weights[i] = w; fill[a] += 1
        i = fill[b]; indices[i] = a; weights[i] = w; fill[b] += 1
    return indptr, indices, weights


def load_graph(path: str | None = None, with_coordinates: bool = True) -> Graph:
    path = path or os.path.join(data_dir(), "NW-t.graph")
    if _np is not None:
        with open(path) as handle:
            header = handle.readline().split()
            n = int(header[2])
            raw = _np.array(handle.read().split(), dtype=_np.int64).reshape(-1, 3)
        u, v, w = raw[:, 0], raw[:, 1], raw[:, 2]
        keep = u != v
        u, v, w = u[keep], v[keep], w[keep]
        a = _np.minimum(u, v)
        b = _np.maximum(u, v)
        key = a * n + b
        order = _np.lexsort((w, key))
        key, w = key[order], w[order]
        first = _np.ones(len(key), dtype=bool)
        first[1:] = key[1:] != key[:-1]
        key, w = key[first], w[first]
        a, b = key // n, key % n
        src = _np.concatenate([a, b])
        dst = _np.concatenate([b, a])
        ww = _np.concatenate([w, w])
        order = _np.lexsort((dst, src))
        src, dst, ww = src[order], dst[order], ww[order]
        indptr = _np.zeros(n + 1, dtype=_np.int64)
        _np.add.at(indptr, src + 1, 1)
        indptr = _np.cumsum(indptr)
        graph = Graph(n, indptr, dst.astype(_np.int64), ww.astype(_np.int64))
    else:
        n, edges = _read_edges(path)
        indptr, indices, weights = _csr_from_edges(n, edges)
        graph = Graph(n, indptr, indices, weights)
    if with_coordinates:
        graph.xs, graph.ys = load_coordinates(n=graph.n)
    return graph


def load_coordinates(path: str | None = None, n: int | None = None):
    """Return (xs, ys): longitude and latitude in micro-degrees."""
    path = path or os.path.join(data_dir(), "NW-t.coordinates")
    with open(path) as handle:
        header = handle.readline().split()
        count = int(header[2]) if len(header) >= 3 else (n or 0)
        xs = array("q", [0]) * count
        ys = array("q", [0]) * count
        for line in handle:
            parts = line.split()
            if len(parts) < 3:
                continue
            i = int(parts[0])
            xs[i] = int(parts[1])
            ys[i] = int(parts[2])
    if _np is not None:
        return _np.frombuffer(xs, dtype=_np.int64).copy(), _np.frombuffer(ys, dtype=_np.int64).copy()
    return xs, ys


def load_poi_category(name: str, path: str | None = None) -> list[int]:
    """Vertex ids of a real POI category (duplicates removed, file order kept)."""
    path = path or os.path.join(data_dir(), "pois", f"{name}.txt")
    seen = set()
    out = []
    with open(path) as handle:
        handle.readline()  # header: "NW real 0 1 <count>"
        for line in handle:
            line = line.strip()
            if not line:
                continue
            v = int(line)
            if v not in seen:
                seen.add(v)
                out.append(v)
    return out


def dijkstra(graph: Graph, source: int, limit: float | None = None):
    """Single-source shortest paths on `graph` (stdlib heapq implementation).

    Returns a list of distances (float('inf') beyond `limit` / unreachable).
    """
    import heapq

    INF = float("inf")
    n = graph.n
    dist = [INF] * n
    dist[source] = 0
    heap = [(0, source)]
    indptr, indices, weights = graph.indptr, graph.indices, graph.weights
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if limit is not None and d > limit:
            dist[u] = INF
            continue
        for i in range(int(indptr[u]), int(indptr[u + 1])):
            v = int(indices[i])
            nd = d + int(weights[i])
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    if limit is not None:
        dist = [d if d <= limit else INF for d in dist]
    return dist
