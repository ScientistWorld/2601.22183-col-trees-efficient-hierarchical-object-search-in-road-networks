#!/usr/bin/env python3
"""Build a SUL-Tree structure (hierarchy + landmarks) on the public NW network.

SUL-Tree (paper Section 3.1): the road network is recursively partitioned into
b disjoint subgraphs of (near) equal size until a subgraph has at most alpha
vertices; every tree node selects landmarks among its own vertices.  As in the
paper's experiments (Section 9.1) the root node is the shared ALT index with
16 random landmarks.  Local landmark policies follow Section 3.3.1: Random,
Furthest Border, Slice-Based Furthest Border, Border Minmax.

Partitioning: the paper uses METIS but allows any partitioner that produces
similar-sized subgraphs.  We use recursive median bisection of the vertex
coordinates (balanced, spatially compact subgraphs), so b may be any integer.

Only the structure is written; the subgraph distance lists themselves are
computed by the evaluator on its own travel-time network.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.nw import load_graph  # noqa: E402
from data.structure_io import save_structure  # noqa: E402

try:
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra as sp_dijkstra
    HAVE_SCIPY = True
except Exception:  # pragma: no cover - stdlib fallback for tiny test graphs
    np = None
    HAVE_SCIPY = False


# ---------------------------------------------------------------------------
# Partitioning
# ---------------------------------------------------------------------------

def _coords(graph):
    xs = [float(x) for x in graph.xs]
    ys = [float(y) for y in graph.ys]
    lat0 = math.radians(sum(ys) / max(1, len(ys)) / 1e6)
    scale = math.cos(lat0)
    return [x * scale for x in xs], ys


def split_balanced(vertices, parts, px, py):
    """Recursive median bisection of `vertices` into `parts` groups."""
    if parts <= 1 or len(vertices) <= 1:
        return [vertices]
    left_parts = parts // 2
    xs = [px[v] for v in vertices]
    ys = [py[v] for v in vertices]
    if max(xs) - min(xs) >= max(ys) - min(ys):
        key = px
    else:
        key = py
    ordered = sorted(vertices, key=lambda v: (key[v], v))
    cut = (len(ordered) * left_parts) // parts
    return (split_balanced(ordered[:cut], left_parts, px, py)
            + split_balanced(ordered[cut:], parts - left_parts, px, py))


def build_hierarchy(graph, b, alpha):
    px, py = _coords(graph)
    parent = [-1]
    members = {0: list(range(graph.n))}
    leaves = []
    queue = [0]
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        verts = members[node]
        if len(verts) <= alpha:
            leaves.append(node)
            continue
        for part in split_balanced(verts, b, px, py):
            if not part:
                continue
            child = len(parent)
            parent.append(node)
            members[child] = part
            queue.append(child)
    return parent, members, leaves, px, py


# ---------------------------------------------------------------------------
# Landmark policies (paper Section 3.3.1)
# ---------------------------------------------------------------------------

def border_vertices(graph, verts, mark, stamp):
    for v in verts:
        mark[v] = stamp
    out = []
    indptr, indices = graph.indptr, graph.indices
    for v in verts:
        for i in range(int(indptr[v]), int(indptr[v + 1])):
            if mark[int(indices[i])] != stamp:
                out.append(v)
                break
    return out


class SubgraphSSSP:
    """Distances inside the subgraph induced by `verts` (public weights)."""

    def __init__(self, graph, csr=None):
        self.graph = graph
        self.csr = csr

    def from_sources(self, verts, sources):
        pos = {v: i for i, v in enumerate(verts)}
        if HAVE_SCIPY and self.csr is not None:
            idx = np.asarray(verts, dtype=np.int64)
            sub = self.csr[idx][:, idx]
            src = [pos[s] for s in sources]
            return np.atleast_2d(sp_dijkstra(sub, directed=True, indices=src))
        import heapq
        out = []
        g = self.graph
        for s in sources:
            dist = [math.inf] * len(verts)
            dist[pos[s]] = 0
            heap = [(0, s)]
            while heap:
                d, u = heapq.heappop(heap)
                if d > dist[pos[u]]:
                    continue
                for i in range(int(g.indptr[u]), int(g.indptr[u + 1])):
                    v = int(g.indices[i])
                    j = pos.get(v)
                    if j is None:
                        continue
                    nd = d + int(g.weights[i])
                    if nd < dist[j]:
                        dist[j] = nd
                        heapq.heappush(heap, (nd, v))
            out.append(dist)
        return out


def pick_random(verts, m, rng):
    return rng.sample(verts, min(m, len(verts)))


def pick_slice(verts, borders, m, px, py, rng):
    """Slice-Based Furthest Border."""
    cx = sum(px[v] for v in verts) / len(verts)
    cy = sum(py[v] for v in verts) / len(verts)
    border_set = set(borders)

    def slice_of(v):
        ang = math.atan2(py[v] - cy, px[v] - cx) % (2 * math.pi)
        return min(m - 1, int(ang / (2 * math.pi / m)))

    def dist2(v):
        return (px[v] - cx) ** 2 + (py[v] - cy) ** 2

    best_border = [None] * m
    best_any = [None] * m
    for v in verts:
        s = slice_of(v)
        if v in border_set and (best_border[s] is None or (dist2(v), -v) > (dist2(best_border[s]), -best_border[s])):
            best_border[s] = v
        if best_any[s] is None or (dist2(v), -v) > (dist2(best_any[s]), -best_any[s]):
            best_any[s] = v
    chosen = []
    for s in range(m):
        v = best_border[s] if best_border[s] is not None else best_any[s]
        if v is None or v in chosen:
            candidates = [u for u in verts if u not in chosen]
            v = rng.choice(candidates) if candidates else None
        if v is not None:
            chosen.append(v)
    return chosen[:m]


def pick_minmax(verts, borders, m, sssp, rng, sample=8):
    """Border Minmax: vertices minimising the max distance to a border sample."""
    if not borders:
        return pick_random(verts, m, rng)
    subset = rng.sample(borders, min(sample, len(borders)))
    rows = sssp.from_sources(verts, subset)
    if not isinstance(rows, list):  # numpy fast path
        worst = rows.max(axis=0)
        order = np.lexsort((np.asarray(verts, dtype=np.int64), worst))
        return [int(verts[i]) for i in order[:m]]
    worst = [max(row[i] for row in rows) for i in range(len(verts))]
    order = sorted(range(len(verts)), key=lambda i: (worst[i], verts[i]))
    return [verts[i] for i in order[:m]]


def pick_furthest_border(verts, borders, m, sssp, rng):
    """Furthest Border: repeatedly take the border furthest from chosen ones."""
    if len(borders) < m:
        pool = list(dict.fromkeys(list(borders) + rng.sample(verts, min(len(verts), m))))
    else:
        pool = list(borders)
    pos = {v: i for i, v in enumerate(verts)}
    chosen = [rng.choice(pool)]
    nearest = None
    while len(chosen) < m:
        row = list(sssp.from_sources(verts, [chosen[-1]])[0])
        nearest = row if nearest is None else [min(a, b) for a, b in zip(nearest, row)]
        cand = [v for v in pool if v not in chosen]
        if not cand:
            break
        chosen.append(max(cand, key=lambda v: (nearest[pos[v]], -v)))
    return chosen


def pick_farthest_root(graph, m, rng, csr):
    """(variant, not the paper's) Farthest landmark selection for the root ALT
    landmarks (Goldberg & Harrelson): start from a random vertex, then repeatedly
    add the vertex farthest from the landmarks chosen so far (public weights)."""
    n = graph.n
    start = rng.randrange(n)
    if HAVE_SCIPY and csr is not None:
        d = sp_dijkstra(csr, directed=True, indices=[start])[0]
        d = np.where(np.isfinite(d), d, -1.0)
        chosen = [int(np.argmax(d))]
        while len(chosen) < m:
            d = sp_dijkstra(csr, directed=True, indices=chosen, min_only=True)
            d = np.where(np.isfinite(d), d, -1.0)
            d[np.asarray(chosen, dtype=np.int64)] = -1.0
            chosen.append(int(np.argmax(d)))
        return sorted(chosen)
    import heapq  # stdlib fallback (tiny graphs)

    def multi_source(sources):
        dist = [math.inf] * n
        heap = [(0, s) for s in sources]
        for s in sources:
            dist[s] = 0
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for i in range(int(graph.indptr[u]), int(graph.indptr[u + 1])):
                v, nd = int(graph.indices[i]), d + int(graph.weights[i])
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        return dist

    def farthest(dist, exclude):
        return max((i for i in range(n) if dist[i] < math.inf and i not in exclude), key=lambda i: (dist[i], -i))

    chosen = [farthest(multi_source([start]), set())]
    while len(chosen) < m:
        chosen.append(farthest(multi_source(chosen), set(chosen)))
    return sorted(chosen)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--b", type=int, default=8, help="branching factor")
    ap.add_argument("--m", type=int, default=2, help="local landmarks per non-root node")
    ap.add_argument("--alpha", type=int, default=1024, help="max vertices per SUL leaf")
    ap.add_argument("--root-landmarks", type=int, default=16, help="ALT landmarks at the root")
    ap.add_argument("--policy", default="random", choices=["random", "slice", "minmax", "border"])
    ap.add_argument("--root-policy", default="random", choices=["random", "farthest"],
                    help="root (ALT) landmarks: random as in the paper's experiments, or farthest (variant)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--root-seed", type=int, default=None,
                    help="draw the random root (ALT) landmarks with this seed instead of --seed")
    args = ap.parse_args()

    t0 = time.time()
    graph = load_graph()
    rng = random.Random(args.seed)
    print(f"[build] graph n={graph.n} loaded in {time.time() - t0:.1f}s", file=sys.stderr)

    parent, members, leaves, px, py = build_hierarchy(graph, args.b, args.alpha)
    print(f"[build] hierarchy: {len(parent)} nodes, {len(leaves)} leaves", file=sys.stderr)

    csr = None
    if HAVE_SCIPY:
        n = graph.n
        csr = csr_matrix((np.asarray(graph.weights, dtype=np.float64),
                          np.asarray(graph.indices, dtype=np.int64),
                          np.asarray(graph.indptr, dtype=np.int64)), shape=(n, n))
    sssp = SubgraphSSSP(graph, csr)
    mark = [0] * graph.n
    landmarks = []
    for node in range(len(parent)):
        verts = members[node]
        if node == 0:
            root = sorted(pick_random(verts, args.root_landmarks, rng))
            if args.root_seed is not None:
                # a shared ALT backbone: root landmarks drawn with their own seed
                root = sorted(pick_random(verts, args.root_landmarks, random.Random(args.root_seed)))
            if args.root_policy == "farthest":
                # separate generator: the local landmarks stay those of the random-root build
                root = pick_farthest_root(graph, args.root_landmarks, random.Random(args.seed + 7919), csr)
            landmarks.append(root)
            continue
        m = min(args.m, len(verts))
        if args.policy == "random":
            chosen = pick_random(verts, m, rng)
        else:
            borders = border_vertices(graph, verts, mark, node + 1)
            if args.policy == "slice":
                chosen = pick_slice(verts, borders, m, px, py, rng)
            elif args.policy == "minmax":
                chosen = pick_minmax(verts, borders, m, sssp, rng)
            else:
                chosen = pick_furthest_border(verts, borders, m, sssp, rng)
        landmarks.append(list(chosen))
    leaf_of = [0] * graph.n
    for leaf in leaves:
        for v in members[leaf]:
            leaf_of[v] = leaf
    meta = {"b": args.b, "m": args.m, "alpha": args.alpha, "root_landmarks": args.root_landmarks,
            "policy": args.policy, "seed": args.seed, "partitioner": "recursive-median-bisection"}
    if args.root_policy != "random":
        meta["root_policy"] = args.root_policy
    if args.root_seed is not None:
        meta["root_seed"] = args.root_seed
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_structure(args.out, parent, landmarks, leaf_of, meta)
    entries = sum(len(landmarks[i]) * len(members[i]) for i in range(len(parent)))
    print(f"[build] wrote {args.out}: {len(parent)} nodes, index entries/|V| = "
          f"{entries / graph.n:.2f}, {time.time() - t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
