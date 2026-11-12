#!/usr/bin/env python3
"""Held-out (test) evaluator for exact object search on road networks.

Every method directory under the results root(s) is run through the same
protocol on workloads that exist only here:

  * hidden travel-time conditions of the NW road network (secret, spatially
    correlated + per-edge perturbation of the public travel times),
  * a fresh hidden object set for every query (jittered real POI categories or
    uniform samples), and hidden query vertices.

The evaluator owns all distances.  For a submitted index structure it
computes the landmark distance lists on the hidden network, answers the
solver's requests and measures, per query:
  - exact distance computations requested (`dist`),
  - candidates retrieved from the index: objects revealed (`get` + any object
    touched by `dist` or returned) plus every non-root index node holding at
    least one of the query's objects that the solver accessed (`nodes`,
    `peek`, `bisect` or `get`); empty nodes and the root are free,
  - whether the returned answer is exact (checked against its own Dijkstra).
Nothing a method writes about itself is read.  A method that fails anything
(invalid structure, index over budget, crash, protocol error, timeout, a
single wrong answer) is scored with the worst value of every metric of every
experiment.

Usage: python3 eval/test/evaluate.py [--root DIR ...] [--output FILE] [--details FILE]
"""

from __future__ import annotations

import argparse
import base64
import bisect
import hashlib
import heapq
import json
import math
import os
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from array import array

try:
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra as sp_dijkstra
    HAVE_SCIPY = True
except Exception:  # stdlib fallback (slow; only for tiny smoke-test graphs)
    np = None
    HAVE_SCIPY = False

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Split configuration (everything below the line is shared logic)
# ---------------------------------------------------------------------------
SPLIT = "test"
SECRET = 0x04385DECF1B74B0A
NOISE = {"grid": 12, "sigma_region": 0.35, "sigma_edge": 0.20, "clip": (0.4, 2.5)}
JITTER_STEPS = 3
REAL_SETS = ("school", "park", "post_office", "fast_food", "hotel")
TASKS = {
    "kfn": {"sets": ["school", "park", "post_office", "fast_food", "hotel",
                     "uniform:0.001", "uniform:0.005"],
            "per_set": 20, "k": 10},
    "aknn": {"sets": ["school", "park", "post_office", "fast_food", "hotel",
                      "uniform:0.001", "uniform:0.005"],
             "per_set": 12, "k": 10, "q_size": 8, "area": 0.15, "aggs": ["max", "sum"]},
    "range": {"sets": ["school", "park", "post_office", "fast_food",
                       "uniform:0.005", "uniform:0.01"],
              "per_set": 20, "radius_frac": 0.025},
}
# Index budget: subgraph-distance-list entries per vertex (the paper's tuned
# configuration for each query type: 16 ALT root landmarks plus m local
# landmarks on every level of a b-ary hierarchy with leaves of <= 1024 vertices).
INDEX_CAP = {"kfn": 40.0, "aknn": 24.0, "range": 24.0}
# Index construction work: vertices settled per vertex (Dijkstra from every
# landmark until its node is covered); the paper's kFN configuration (b=4, m=4)
# builds about four times as many distance lists as the AkNN/range one.
WORK_CAP = {"kfn": 3000.0, "aknn": 600.0, "range": 600.0}
MIN_LEAF = 128            # minimum number of vertices in a leaf node
MAX_LANDMARKS_PER_NODE = 32
MAX_NODES = 200000
TASK_TIMEOUT = 7200.0     # seconds per (method, task)
IDLE_TIMEOUT = 900.0      # seconds without a protocol message
MAX_PAIRS_PER_QUERY = 5_000_000
EXPERIMENTS = {"kfn": "kfn", "aknn": "aknn", "range": "range"}
SANDBOX = True            # isolate solvers from the evaluator (see isolation())

# ---------------------------------------------------------------------------
MASK = (1 << 64) - 1


def mix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & MASK
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & MASK
    return x ^ (x >> 31)


def hkey(*parts) -> int:
    h = 0x2545F4914F6CDD1D
    for p in parts:
        if isinstance(p, str):
            p = int.from_bytes(hashlib.blake2b(p.encode(), digest_size=8).digest(), "little")
        h = mix64(h ^ (int(p) & MASK))
    return h


def unit(x: int) -> float:
    return ((x >> 11) + 0.5) * (1.0 / (1 << 53))


def gauss(key: int) -> float:
    u1 = unit(mix64(key ^ 0x1111))
    u2 = unit(mix64(key ^ 0x2222))
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


class Rng:
    def __init__(self, seed: int):
        self.state = seed & MASK

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        return mix64(self.state)

    def below(self, n: int) -> int:
        return self.next() % n

    def sample(self, n: int, k: int) -> list:
        """k distinct values from range(n) (Floyd), in generation order."""
        chosen = {}
        out = []
        for j in range(n - k, n):
            t = self.below(j + 1)
            if t in chosen:
                t = j
            chosen[t] = True
            out.append(t)
        return out


class Invalid(Exception):
    """The submission cannot be evaluated (scored as failed)."""


# ---------------------------------------------------------------------------
# Road network
# ---------------------------------------------------------------------------

def data_dir() -> str:
    return os.environ.get("COLT_DATA_DIR") or os.path.join(WORKSPACE, "data", "downloads", "nw")


def load_base():
    path = os.path.join(data_dir(), "NW-t.graph")
    with open(path) as handle:
        n = int(handle.readline().split()[2])
        pairs = []
        for line in handle:
            parts = line.split()
            if len(parts) < 3:
                continue
            u, v, w = int(parts[0]), int(parts[1]), int(parts[2])
            if u == v:
                continue
            if u > v:
                u, v = v, u
            pairs.append((u, v, w))
    pairs.sort()
    eu, ev, ew = array("q"), array("q"), array("q")
    last = None
    for u, v, w in pairs:
        if last == (u, v):
            if w < ew[-1]:
                ew[-1] = w
            continue
        last = (u, v)
        eu.append(u); ev.append(v); ew.append(w)
    xs = array("q", [0]) * n
    ys = array("q", [0]) * n
    with open(os.path.join(data_dir(), "NW-t.coordinates")) as handle:
        handle.readline()
        for line in handle:
            parts = line.split()
            if len(parts) >= 3:
                i = int(parts[0]); xs[i] = int(parts[1]); ys[i] = int(parts[2])
    return n, eu, ev, ew, xs, ys


def hidden_weights(n, eu, ev, ew, xs, ys, seed):
    """Travel times under hidden traffic conditions (secret, deterministic)."""
    grid = NOISE["grid"]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    field = [[gauss(hkey(seed, "field", i, j)) for j in range(grid)] for i in range(grid)]
    sx = (grid - 1) / max(1, xmax - xmin)
    sy = (grid - 1) / max(1, ymax - ymin)
    sr, se = NOISE["sigma_region"], NOISE["sigma_edge"]
    lo, hi = NOISE["clip"]
    base = hkey(seed, "edge")
    out = array("q", [0]) * len(eu)
    for e in range(len(eu)):
        u, v = eu[e], ev[e]
        fx = ((xs[u] + xs[v]) * 0.5 - xmin) * sx
        fy = ((ys[u] + ys[v]) * 0.5 - ymin) * sy
        i0 = min(grid - 2, max(0, int(fx)))
        j0 = min(grid - 2, max(0, int(fy)))
        tx, ty = fx - i0, fy - j0
        z = ((1 - tx) * (1 - ty) * field[i0][j0] + tx * (1 - ty) * field[i0 + 1][j0]
             + (1 - tx) * ty * field[i0][j0 + 1] + tx * ty * field[i0 + 1][j0 + 1])
        k = mix64(mix64(base ^ u) ^ v)
        f = math.exp(sr * z + se * gauss(k))
        f = lo if f < lo else (hi if f > hi else f)
        out[e] = max(1, int(round(ew[e] * f)))
    return out


class Engine:
    """Exact shortest paths on the hidden network."""

    def __init__(self, n, eu, ev, ww):
        self.n = n
        if HAVE_SCIPY:
            u = np.frombuffer(eu, dtype=np.int64)
            v = np.frombuffer(ev, dtype=np.int64)
            w = np.frombuffer(ww, dtype=np.int64).astype(np.float64)
            self.csr = csr_matrix((np.concatenate([w, w]), (np.concatenate([u, v]), np.concatenate([v, u]))),
                                  shape=(n, n))
        else:
            self.adj = [[] for _ in range(n)]
            for a, b, w in zip(eu, ev, ww):
                self.adj[a].append((b, w))
                self.adj[b].append((a, w))

    # rows are numpy float arrays (scipy) or python lists; values are exact
    # integers (or inf).
    def sssp_many(self, sources, limit=None):
        sources = [int(s) for s in sources]
        if HAVE_SCIPY:
            lim = np.inf if limit is None else float(limit)
            dist = sp_dijkstra(self.csr, directed=True, indices=sources, limit=lim)
            return list(np.atleast_2d(dist))
        return [self._py_sssp(s, limit) for s in sources]

    def _py_sssp(self, s, limit=None):
        inf = math.inf
        dist = [inf] * self.n
        dist[s] = 0
        heap = [(0, s)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist[v] and (limit is None or nd <= limit):
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        return dist

    def restricted(self, sources, members, members_np):
        """Distances from every source to every member vertex (exact), plus the
        number of vertices a Dijkstra search restricted to the member set
        settles (paper Section 8: SDL construction work)."""
        if HAVE_SCIPY:
            pos = np.searchsorted(members_np, np.asarray(sources, dtype=np.int64))
            sub = self.csr[members_np][:, members_np]
            dsub = np.atleast_2d(sp_dijkstra(sub, directed=True, indices=pos))
            finite = dsub[np.isfinite(dsub)]
            limit = float(finite.max()) + 1.0 if finite.size else 1.0
            while True:
                rows = self.sssp_many(sources, limit)
                vals = np.stack([r[members_np] for r in rows])
                if np.isfinite(vals).all() or limit == np.inf:
                    break
                limit = limit * 2.0 if limit < 1e15 else np.inf
            out, work = [], []
            for r, vrow in zip(rows, vals):
                top = vrow.max()
                work.append(int(np.count_nonzero(r <= top)))
                out.append(array("i", vrow.astype(np.int32).tobytes()))
            return out, work
        out, work = [], []
        member_set = set(members)
        for s in sources:
            dist = {s: 0}
            heap = [(0, s)]
            remaining = len(member_set)
            settled = set()
            while heap and remaining:
                d, u = heapq.heappop(heap)
                if u in settled:
                    continue
                settled.add(u)
                if u in member_set:
                    remaining -= 1
                for v, w in self.adj[u]:
                    nd = d + w
                    if nd < dist.get(v, math.inf):
                        dist[v] = nd
                        heapq.heappush(heap, (nd, v))
            if remaining:
                raise Invalid("subgraph vertex unreachable from landmark")
            out.append(array("i", [dist[m] for m in members]))
            work.append(len(settled))
        return out, work


def take(row, idx):
    """Exact integer distances row[v] for v in idx (inf -> -1)."""
    if HAVE_SCIPY and not isinstance(row, list):
        vals = row[np.asarray(idx, dtype=np.int64)]
        vals = np.where(np.isfinite(vals), vals, -1.0)
        return vals.astype(np.int64).tolist()
    return [int(row[v]) if row[v] != math.inf else -1 for v in idx]


def argmax_row(row):
    if HAVE_SCIPY and not isinstance(row, list):
        r = np.where(np.isfinite(row), row, -1.0)
        return int(np.argmax(r))
    best, arg = -1, 0
    for i, d in enumerate(row):
        if d != math.inf and d > best:
            best, arg = d, i
    return arg


def nearest_vertices(row, count):
    """Sorted ids of the `count` vertices nearest to the row's source."""
    if HAVE_SCIPY and not isinstance(row, list):
        idx = np.argpartition(row, count - 1)[:count]
        return sorted(int(i) for i in idx)
    order = sorted(range(len(row)), key=lambda i: (row[i], i))
    return sorted(order[:count])


# ---------------------------------------------------------------------------
# Hidden workload
# ---------------------------------------------------------------------------

def load_poi(name):
    seen, out = set(), []
    with open(os.path.join(data_dir(), "pois", f"{name}.txt")) as handle:
        handle.readline()
        for line in handle:
            line = line.strip()
            if line and int(line) not in seen:
                seen.add(int(line))
                out.append(int(line))
    return out


class Workload:
    def __init__(self, n, eu, ev, engine, seed):
        self.n = n
        self.seed = seed
        self.adj_ptr, self.adj = self._topology(n, eu, ev)
        self.poi = {name: load_poi(name) for name in REAL_SETS}
        rng = Rng(hkey(seed, "diameter"))
        s0 = rng.below(n)
        far = argmax_row(engine.sssp_many([s0])[0])
        row = engine.sssp_many([far])[0]
        self.diameter = float(row[argmax_row(row)])
        self.queries = {}
        for task, cfg in TASKS.items():
            specs = []
            for si, set_name in enumerate(cfg["sets"]):
                for qi in range(cfg["per_set"]):
                    key = hkey(seed, task, set_name, qi)
                    rng = Rng(key)
                    spec = {"task": task, "set": set_name, "obj_key": hkey(key, "objects")}
                    if task == "aknn":
                        center = rng.below(n)
                        area = nearest_vertices(engine.sssp_many([center])[0],
                                                max(cfg["q_size"], int(math.ceil(cfg["area"] * n))))
                        spec["q"] = [area[i] for i in rng.sample(len(area), cfg["q_size"])]
                        spec["agg"] = cfg["aggs"][qi % len(cfg["aggs"])]
                        spec["k"] = cfg["k"]
                    else:
                        spec["q"] = [rng.below(n)]
                        if task == "kfn":
                            spec["k"] = cfg["k"]
                        else:
                            spec["radius"] = cfg["radius_frac"] * self.diameter
                    specs.append(spec)
            self.queries[task] = specs

    @staticmethod
    def _topology(n, eu, ev):
        deg = [0] * (n + 1)
        for a, b in zip(eu, ev):
            deg[a + 1] += 1
            deg[b + 1] += 1
        for i in range(n):
            deg[i + 1] += deg[i]
        fill = deg[:-1]
        adj = array("q", [0]) * (2 * len(eu))
        for a, b in zip(eu, ev):
            adj[fill[a]] = b; fill[a] += 1
            adj[fill[b]] = a; fill[b] += 1
        return deg, adj

    def objects(self, spec):
        rng = Rng(spec["obj_key"])
        name = spec["set"]
        if name.startswith("uniform:"):
            count = max(1, int(round(float(name.split(":")[1]) * self.n)))
            return rng.sample(self.n, count)
        out, seen = [], set()
        for v in self.poi[name]:
            for _ in range(JITTER_STEPS):
                a, b = self.adj_ptr[v], self.adj_ptr[v + 1]
                if b > a:
                    v = self.adj[a + rng.below(b - a)]
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out


# ---------------------------------------------------------------------------
# Submitted index structure -> landmark distance lists on the hidden network
# ---------------------------------------------------------------------------

def decode_leaf_of(obj, n):
    if isinstance(obj, list):
        arr = array("I", obj)
    elif isinstance(obj, dict) and obj.get("encoding") == "zlib-base64-uint32-le":
        arr = array("I")
        arr.frombytes(zlib.decompress(base64.b64decode(obj["data"])))
        if sys.byteorder != "little":
            arr.byteswap()
    else:
        raise Invalid("leaf_of: unsupported encoding")
    if len(arr) != n:
        raise Invalid(f"leaf_of has {len(arr)} entries, expected {n}")
    return arr


class Index:
    def __init__(self, path, n):
        try:
            with open(path) as handle:
                payload = json.load(handle)
        except Exception as exc:
            raise Invalid(f"cannot read structure {path}: {exc}")
        if not isinstance(payload, dict) or payload.get("format") != "hier-landmark-v1":
            raise Invalid("structure format must be hier-landmark-v1")
        parent = payload.get("parent")
        landmarks = payload.get("landmarks")
        if not isinstance(parent, list) or not isinstance(landmarks, list):
            raise Invalid("structure needs parent and landmarks lists")
        k = len(parent)
        if k < 1 or k > MAX_NODES or len(landmarks) != k:
            raise Invalid("bad node count")
        if parent[0] != -1:
            raise Invalid("node 0 must be the root (parent -1)")
        for i in range(1, k):
            p = parent[i]
            if not isinstance(p, int) or isinstance(p, bool) or not 0 <= p < i:
                raise Invalid(f"node {i}: parent must be an earlier node")
        self.n = n
        self.parent = parent
        self.children = [[] for _ in range(k)]
        for i in range(1, k):
            self.children[parent[i]].append(i)
        self.depth = [0] * k
        for i in range(1, k):
            self.depth[i] = self.depth[parent[i]] + 1
        self.landmarks = []
        for i, lm in enumerate(landmarks):
            if not isinstance(lm, list) or len(lm) > MAX_LANDMARKS_PER_NODE:
                raise Invalid(f"node {i}: landmarks must be a list of <= {MAX_LANDMARKS_PER_NODE}")
            clean = []
            for v in lm:
                if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < n:
                    raise Invalid(f"node {i}: landmark out of range")
                clean.append(v)
            if len(set(clean)) != len(clean):
                raise Invalid(f"node {i}: duplicate landmarks")
            self.landmarks.append(clean)
        self.offset = [0] * k
        for i in range(1, k):
            self.offset[i] = self.offset[parent[i]] + len(self.landmarks[parent[i]])
        self.prefix = [self.offset[i] + len(self.landmarks[i]) for i in range(k)]
        self.leaf_of = decode_leaf_of(payload.get("leaf_of"), n)
        members = [[] for _ in range(k)]
        for v in range(n):
            leaf = self.leaf_of[v]
            if leaf >= k:
                raise Invalid("leaf_of refers to a missing node")
            members[leaf].append(v)
        for i in range(k):
            if self.children[i]:
                if members[i]:
                    raise Invalid(f"node {i} has children but vertices are assigned to it")
            elif len(members[i]) < MIN_LEAF:
                raise Invalid(f"leaf {i} has {len(members[i])} vertices (< {MIN_LEAF})")
        for i in range(k - 1, 0, -1):
            members[parent[i]].extend(members[i])
        for i in range(k):
            members[i].sort()
        self.members = members
        self.entries = sum(len(self.landmarks[i]) * len(members[i]) for i in range(k))
        if self.entries > max(INDEX_CAP.values()) * n:
            raise Invalid(f"index has {self.entries / n:.2f} entries per vertex "
                          f"(cap {max(INDEX_CAP.values())})")
        self.leaf_path = {}
        for leaf in range(k):
            if not self.children[leaf]:
                path, x = [], leaf
                while x >= 0:
                    path.append(x)
                    x = parent[x]
                self.leaf_path[leaf] = path[::-1]
        for i in range(1, k):
            for l in self.landmarks[i]:
                leaf = self.leaf_of[l]
                if i not in self.leaf_path[leaf]:
                    raise Invalid(f"node {i}: landmark {l} is not inside the node's subgraph")
        max_depth = max(self.depth)
        self.pos = [array("i", [-1]) * n for _ in range(max_depth + 1)]
        for i in range(k):
            if self.landmarks[i]:
                p = self.pos[self.depth[i]]
                for j, v in enumerate(members[i]):
                    p[v] = j
        self.sdl = [None] * k
        self.work = 0
        self.landmark_vertices = sorted({v for lm in self.landmarks for v in lm})

    def compute(self, engine):
        cap = max(WORK_CAP.values()) * self.n
        for i in range(len(self.parent)):
            lms = self.landmarks[i]
            if not lms:
                self.sdl[i] = []
                continue
            mem = self.members[i]
            if len(mem) == self.n:
                rows = engine.sssp_many(lms)
                vals = [array("i", take(r, mem)) for r in rows]
                if any(min(v) < 0 for v in vals):
                    raise Invalid("graph not connected from a root landmark")
                self.sdl[i] = vals
                self.work += self.n * len(lms)
            else:
                mem_np = np.asarray(mem, dtype=np.int64) if HAVE_SCIPY else None
                vals, work = engine.restricted(lms, mem, mem_np)
                self.sdl[i] = vals
                self.work += sum(work)
            if self.work > cap:
                raise Invalid(f"index construction work exceeds {max(WORK_CAP.values())} settled vertices per vertex "
                              f"(reached {self.work / self.n:.1f} after node {i + 1} of {len(self.parent)})")
        self.members = None  # free memory; positions are kept in self.pos

    def record(self, v, upto_depth=None):
        out = []
        path = self.leaf_path[self.leaf_of[v]]
        if upto_depth is not None:
            path = path[:upto_depth + 1]
        for node in path:
            lists = self.sdl[node]
            if lists:
                p = self.pos[self.depth[node]][v]
                for arr in lists:
                    out.append(arr[p])
        return out


class QueryView:
    """Per (method, query) view of the hidden object set through an index."""

    def __init__(self, index: Index, objects):
        self.index = index
        self.objects = objects
        self.by_node = {}
        for v in objects:
            for node in index.leaf_path[index.leaf_of[v]]:
                lst = self.by_node.get(node)
                if lst is None:
                    self.by_node[node] = [v]
                else:
                    lst.append(v)
        self.records = {}
        self.summaries = {}
        self.odls = {}

    def record(self, v):
        r = self.records.get(v)
        if r is None:
            r = self.index.record(v)
            self.records[v] = r
        return r

    def summary(self, node):
        s = self.summaries.get(node)
        if s is not None:
            return s
        objs = self.by_node.get(node)
        if not objs:
            s = [0, [], []]
        else:
            width = self.index.prefix[node]
            depth = self.index.depth[node]
            rec = self.records.get
            first = rec(objs[0]) or self.index.record(objs[0], depth)
            mins, maxs = list(first[:width]), list(first[:width])
            for v in objs[1:]:
                r = rec(v) or self.index.record(v, depth)
                for j in range(width):
                    x = r[j]
                    if x < mins[j]:
                        mins[j] = x
                    elif x > maxs[j]:
                        maxs[j] = x
            s = [len(objs), mins, maxs]
        self.summaries[node] = s
        return s

    def odl(self, node, pos):
        key = (node, pos)
        o = self.odls.get(key)
        if o is None:
            objs = self.by_node.get(node, [])
            if not 0 <= pos < self.index.prefix[node]:
                raise Invalid("odl position out of range")
            pairs = sorted((self.record(v)[pos], v) for v in objs)
            o = ([p[1] for p in pairs], [p[0] for p in pairs])
            self.odls[key] = o
        return o


# ---------------------------------------------------------------------------
# Solver isolation
# ---------------------------------------------------------------------------
# A solver runs while this evaluator holds the evaluation network in memory.
# It is started in fresh user, mount and pid namespaces in which the
# evaluator's directory (eval/) and the repository history (.git) are empty
# tmpfs mounts, locked by a second, nested user namespace, and /proc only shows
# the solver's own processes.  It therefore cannot read the evaluator source,
# its seed or its memory; it still reads the rest of the workspace (its own
# code, data/, its structure files).  Where namespaces are unavailable the
# solver runs unisolated and the evaluator says so in its log.

_ISOLATION = None
_PROBE = (
    "import os, sys\n"
    "ws = sys.argv[1]\n"
    "hidden = os.path.join(ws, 'eval')\n"
    "ok = os.path.isdir(hidden) and not os.listdir(hidden) and os.path.isdir(os.path.join(ws, 'data'))\n"
    "for pid in (p for p in os.listdir('/proc') if p.isdigit()):\n"
    "    try:\n"
    "        if os.listdir('/proc/%s/root%s' % (pid, hidden)):\n"
    "            ok = False\n"
    "    except OSError:\n"
    "        pass\n"
    "print('isolated' if ok else 'visible')\n"
)


def isolation():
    """(command prefix, description) used to start every solver."""
    global _ISOLATION
    if _ISOLATION is not None:
        return _ISOLATION
    _ISOLATION = ([], "none (namespaces unavailable)")
    if not SANDBOX:
        _ISOLATION = ([], "none (disabled)")
        return _ISOLATION
    if not (shutil.which("unshare") and shutil.which("mount")):
        return _ISOLATION
    hide = [os.path.join(WORKSPACE, "eval")]
    if os.path.isdir(os.path.join(WORKSPACE, ".git")):
        hide.append(os.path.join(WORKSPACE, ".git"))
    mounts = " && ".join(f"mount -t tmpfs -o size=64k,mode=0755 none {shlex.quote(p)}" for p in hide)
    nested = ' && exec unshare --user --map-root-user --mount -- "$@"'
    modes = [
        (["--pid", "--fork", "--kill-child", "--mount-proc"], mounts + nested,
         "user+mount+pid namespaces (eval/ and .git hidden, private /proc)"),
        ([], mounts + " && mount -t tmpfs -o size=64k,mode=0755 none /proc" + nested,
         "user+mount namespaces (eval/ and .git hidden, /proc hidden)"),
    ]
    for extra, script, desc in modes:
        prefix = ["unshare", "--user", "--map-root-user", "--mount", *extra, "--",
                  "/bin/sh", "-c", script, "isolated-solver"]
        try:
            res = subprocess.run(prefix + [sys.executable or "python3", "-c", _PROBE, WORKSPACE],
                                 cwd=WORKSPACE, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
            if res.returncode == 0 and res.stdout.strip() == b"isolated":
                _ISOLATION = (prefix, desc)
                break
        except Exception:
            continue
    return _ISOLATION


# ---------------------------------------------------------------------------
# Running a submitted solver
# ---------------------------------------------------------------------------

class LineChannel:
    def __init__(self, proc):
        self.proc = proc
        self.fd = proc.stdout.fileno()
        self.buf = b""

    def send(self, obj):
        data = json.dumps(obj, separators=(",", ":")).encode() + b"\n"
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            raise Invalid("solver closed its input")

    def recv(self, deadline):
        while True:
            nl = self.buf.find(b"\n")
            if nl >= 0:
                line, self.buf = self.buf[:nl], self.buf[nl + 1:]
                try:
                    return json.loads(line)
                except Exception:
                    raise Invalid("solver sent malformed JSON")
            remaining = deadline - time.time()
            if remaining <= 0:
                raise Invalid("solver timed out")
            ready, _, _ = select.select([self.fd], [], [], remaining)
            if not ready:
                continue
            chunk = os.read(self.fd, 1 << 20)
            if not chunk:
                raise Invalid("solver exited")
            self.buf += chunk


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


class Session:
    def __init__(self, method, task, index, structure_path, command, log_path):
        self.method, self.task, self.index = method, task, index
        self.log = open(log_path, "ab")
        try:
            self.proc = subprocess.Popen(isolation()[0] + list(command), cwd=WORKSPACE,
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=self.log)
        except Exception as exc:
            raise Invalid(f"cannot start solver: {exc}")
        self.chan = LineChannel(self.proc)
        self.spent = 0.0          # seconds this solver has spent answering (its own budget)
        try:
            self.chan.send({"type": "hello", "protocol": 1, "task": task, "n_vertices": index.n,
                            "structure": structure_path})
            if self._reply_type() != "ready":
                raise Invalid("solver did not reply ready")
            records = {str(v): index.record(v) for v in index.landmark_vertices}
            self.chan.send({"type": "landmarks", "records": records})
            if self._reply_type() != "ok":
                raise Invalid("solver did not acknowledge landmark records")
        except Invalid:
            self.kill()
            raise

    def recv(self):
        start = time.time()
        try:
            return self.chan.recv(start + min(IDLE_TIMEOUT, TASK_TIMEOUT - self.spent))
        finally:
            self.spent += time.time() - start

    def _reply_type(self):
        msg = self.recv()
        return msg.get("type") if isinstance(msg, dict) else None

    def close(self):
        try:
            self.chan.send({"type": "bye"})
        except Invalid:
            pass
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()
        self.log.close()

    def kill(self):
        try:
            self.proc.kill()
            self.proc.wait(timeout=30)
        except Exception:
            pass
        if not self.log.closed:
            self.log.close()

    def run_query(self, spec, objects, object_set, rows):
        view = QueryView(self.index, objects)
        qs = spec["q"]
        msg = {"type": "query", "kind": self.task, "q": qs,
               "q_records": [self.index.record(q) for q in qs],
               "n_objects": len(objects), "root": view.summary(0)}
        for key in ("k", "agg", "radius"):
            if key in spec:
                msg[key] = spec[key]
        self.chan.send(msg)
        pairs = set()
        touched = set()
        opened = set()
        while True:
            req = self.recv()
            if not isinstance(req, dict):
                raise Invalid("request must be an object")
            if req.get("op") == "answer":
                result = req.get("result")
                if not isinstance(result, list) or not all(is_int(x) for x in result):
                    raise Invalid("answer must be a list of vertex ids")
                self.chan.send({"ok": True})
                for x in result:
                    if x in object_set:
                        touched.add(x)
                work = {"calls": len(pairs), "cands": len(touched) + len(opened),
                        "objects": len(touched), "nodes": len(opened),
                        "obj_calls": sum(1 for _, v in pairs if v in object_set)}
                return result, work
            if req.get("op") == "batch":
                reqs = req.get("reqs")
                if not isinstance(reqs, list):
                    raise Invalid("batch needs reqs")
                res = [self.handle(r, view, qs, rows, object_set, pairs, touched, opened) for r in reqs]
                self.chan.send({"res": res})
            else:
                self.chan.send(self.handle(req, view, qs, rows, object_set, pairs, touched, opened))
            if len(pairs) > MAX_PAIRS_PER_QUERY:
                raise Invalid("too many distance requests")

    def handle(self, req, view, qs, rows, object_set, pairs, touched, opened):
        if not isinstance(req, dict):
            raise Invalid("request must be an object")
        op = req.get("op")
        k = len(self.index.parent)
        if op == "nodes":
            ids = req.get("ids")
            if not isinstance(ids, list) or not all(is_int(i) and 0 <= i < k for i in ids):
                raise Invalid("nodes: bad ids")
            for i in ids:
                if i and i in view.by_node:
                    opened.add(i)
            return {"nodes": [view.summary(i) for i in ids]}
        if op in ("peek", "bisect", "get"):
            node, pos = req.get("node"), req.get("pos")
            if not (is_int(node) and 0 <= node < k and is_int(pos)):
                raise Invalid(f"{op}: bad node/pos")
            if node and node in view.by_node:
                opened.add(node)
            objs, vals = view.odl(node, pos)
            if op == "peek":
                idx = req.get("idx")
                if not isinstance(idx, list) or not all(is_int(i) and 0 <= i < len(vals) for i in idx):
                    raise Invalid("peek: bad idx")
                return {"d": [vals[i] for i in idx]}
            if op == "bisect":
                x = req.get("x")
                if not isinstance(x, (int, float)) or isinstance(x, bool) or x != x:
                    raise Invalid("bisect: bad x")
                fn = bisect.bisect_right if req.get("side") == "right" else bisect.bisect_left
                return {"i": fn(vals, x)}
            lo, hi = req.get("lo"), req.get("hi")
            if not (is_int(lo) and is_int(hi) and 0 <= lo <= hi <= len(vals)):
                raise Invalid("get: bad range")
            items = []
            for i in range(lo, hi):
                v = objs[i]
                touched.add(v)
                items.append([v, vals[i], view.record(v)])
            return {"items": items}
        if op == "dist":
            qi, vs = req.get("q"), req.get("v")
            if not (is_int(qi) and 0 <= qi < len(qs)) or not isinstance(vs, list):
                raise Invalid("dist: bad query index")
            row = rows[qi]
            out = []
            for v in vs:
                if not (is_int(v) and 0 <= v < self.index.n):
                    raise Invalid("dist: bad vertex")
                pairs.add((qi, v))
                if v in object_set:
                    touched.add(v)
                d = row[v]
                out.append(int(d) if d != math.inf else -1)
            return {"d": out}
        raise Invalid(f"unknown op {op!r}")


class Truth:
    """Exact answers from the evaluator's own distances (ties accepted)."""

    def __init__(self, spec, objects, rows):
        self.task = spec["task"]
        if self.task == "range":
            d = take(rows[0], objects)
            self.inside = {v for v, dv in zip(objects, d) if 0 <= dv <= spec["radius"]}
            return
        self.k = min(spec["k"], len(objects))
        if self.task == "kfn":
            self.score = dict(zip(objects, take(rows[0], objects)))
            self.thr = sorted(self.score.values(), reverse=True)[self.k - 1]
        else:
            per_q = [take(r, objects) for r in rows]
            agg = sum if spec["agg"] == "sum" else max
            self.score = {v: agg(col) for v, col in zip(objects, zip(*per_q))}
            self.thr = sorted(self.score.values())[self.k - 1]

    def check(self, result):
        if len(set(result)) != len(result):
            return False
        if self.task == "range":
            return set(result) == self.inside
        if len(result) != self.k or not all(x in self.score for x in result):
            return False
        if self.task == "kfn":
            return all(self.score[x] >= self.thr for x in result)
        return all(self.score[x] <= self.thr for x in result)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def worst_metrics(task):
    return {"exact_answer_rate": 0.0, "log10_call_reduction": 0.0,
            "log10_candidate_reduction": 0.0,
            "index_entries_per_vertex": INDEX_CAP[task], "sdl_work_per_vertex": WORK_CAP[task]}


def task_metrics(rows, entries, work, n):
    calls = [max(0.0, math.log10((r["q_size"] * r["n_objects"] + 1) / (r["calls"] + 1))) for r in rows]
    cands = [max(0.0, math.log10((r["n_objects"] + 1) / (r["cands"] + 1))) for r in rows]
    return {"exact_answer_rate": sum(r["correct"] for r in rows) / len(rows),
            "log10_call_reduction": sum(calls) / len(calls),
            "log10_candidate_reduction": sum(cands) / len(cands),
            "index_entries_per_vertex": entries / n,
            "sdl_work_per_vertex": work / n}


def discover(roots):
    methods = []
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isdir(path) or name == "__pycache__":
                continue
            key = name if name not in seen else f"{os.path.basename(os.path.normpath(root))}/{name}"
            seen.add(key)
            methods.append((key, path))
    return methods


def load_submission(path):
    try:
        with open(os.path.join(path, "submission.json")) as handle:
            sub = json.load(handle)
    except Exception as exc:
        raise Invalid(f"missing or unreadable submission.json: {exc}")
    cmd = sub.get("command")
    structures = sub.get("structures")
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
        raise Invalid("submission.json: command must be a non-empty list of strings")
    if not isinstance(structures, dict):
        raise Invalid("submission.json: structures must map task -> file")
    out = {}
    for task in TASKS:
        rel = structures.get(task)
        if not isinstance(rel, str):
            raise Invalid(f"submission.json: no structure for task {task}")
        out[task] = os.path.normpath(os.path.join(path, rel))
    return cmd, out


def file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", default=None,
                    help="directory whose sub-directories are methods (default: experiment_results)")
    ap.add_argument("--output", default=os.path.join(WORKSPACE, "scoring", f"scores_{SPLIT}.json"))
    ap.add_argument("--details", default=None, help="optional per-query work counts (no hidden data)")
    args = ap.parse_args()
    roots = args.root or [os.path.join(WORKSPACE, "experiment_results")]

    t0 = time.time()
    log = lambda msg: print(f"[eval:{SPLIT} {time.time() - t0:7.1f}s] {msg}", file=sys.stderr, flush=True)
    n, eu, ev, ew, xs, ys = load_base()
    ww = hidden_weights(n, eu, ev, ew, xs, ys, SECRET)
    engine = Engine(n, eu, ev, ww)
    log(f"network: {n} vertices, {len(eu)} edges (scipy={HAVE_SCIPY})")
    workload = Workload(n, eu, ev, engine, SECRET)
    log("workload: " + ", ".join(f"{t}={len(q)} queries" for t, q in workload.queries.items()))

    methods = discover(roots)
    log(f"methods: {[m for m, _ in methods]}")
    log(f"solver isolation: {isolation()[1]}")
    status = {m: None for m, _ in methods}
    plans = {}
    for name, path in methods:
        try:
            cmd, structs = load_submission(path)
            for task, spath in structs.items():
                if not os.path.isfile(spath):
                    raise Invalid(f"structure file missing for {task}")
            plans[name] = (cmd, {task: (file_digest(spath), spath) for task, spath in structs.items()})
        except Invalid as exc:
            status[name] = f"invalid: {exc}"
            log(f"{name}: FAILED ({exc})")

    # Index structures are computed on first use and freed after the last task
    # that needs them (several structures of 40 entries per vertex do not fit
    # in memory at once).
    indexes = {}
    stats = {name: {} for name in plans}

    def index_for(digest, spath):
        if digest not in indexes:
            try:
                idx = Index(spath, n)
                idx.compute(engine)
                indexes[digest] = idx
            except Invalid as exc:
                indexes[digest] = exc
        idx = indexes[digest]
        if isinstance(idx, Invalid):
            raise idx
        return idx

    results = {name: {task: [] for task in TASKS} for name, _ in methods}
    logdir = tempfile.mkdtemp(prefix=f"colt_eval_{SPLIT}_")
    task_order = list(workload.queries)
    for ti, (task, specs) in enumerate(workload.queries.items()):
        sessions = {}
        for name in plans:
            if status[name] is not None:
                continue
            cmd, plan = plans[name]
            digest, spath = plan[task]
            try:
                idx = index_for(digest, spath)
                if idx.entries > INDEX_CAP[task] * n:
                    raise Invalid(f"{task} index has {idx.entries / n:.2f} entries per vertex "
                                  f"(cap {INDEX_CAP[task]})")
                if idx.work > WORK_CAP[task] * n:
                    raise Invalid(f"{task} index construction work is {idx.work / n:.1f} settled vertices "
                                  f"per vertex (cap {WORK_CAP[task]})")
                stats[name][task] = (idx.entries, idx.work)
                log(f"{name}: {task} index ready ({idx.entries / n:.1f} entries/v, {idx.work / n:.1f} work/v)")
                sessions[name] = Session(name, task, idx, spath, cmd,
                                         os.path.join(logdir, f"{name.replace('/', '_')}.log"))
            except Invalid as exc:
                status[name] = f"{task}: {exc}"
                log(f"{name}: FAILED ({status[name]})")
        for qn, spec in enumerate(specs):
            if not sessions:
                break
            objects = workload.objects(spec)
            object_set = set(objects)
            rows = engine.sssp_many(spec["q"])
            truth = Truth(spec, objects, rows)
            for name in list(sessions):
                sess = sessions[name]
                try:
                    result, work = sess.run_query(spec, objects, object_set, rows)
                except Invalid as exc:
                    status[name] = f"{task} query {qn}: {exc}"
                    log(f"{name}: FAILED ({status[name]})")
                    sess.kill()
                    del sessions[name]
                    continue
                ok = truth.check(result)
                row = {"set": spec["set"], "n_objects": len(objects), "q_size": len(spec["q"])}
                row.update(work)
                row["correct"] = bool(ok)
                results[name][task].append(row)
                if not ok and status[name] is None:
                    status[name] = f"{task} query {qn}: inexact answer"
                    log(f"{name}: FAILED ({status[name]})")
                    sess.kill()
                    del sessions[name]
            if (qn + 1) % 20 == 0:
                log(f"{task}: {qn + 1}/{len(specs)} queries")
        for sess in sessions.values():
            sess.close()
        later = {plans[m][1][t][0] for m in plans if status[m] is None for t in task_order[ti + 1:]}
        for digest in [d for d in indexes if d not in later]:
            del indexes[digest]

    scores = {EXPERIMENTS[t]: {"results": {}} for t in TASKS}
    for name, _ in methods:
        for task in TASKS:
            if status[name] is not None:
                metrics = worst_metrics(task)
            else:
                entries, work = stats[name][task]
                metrics = task_metrics(results[name][task], entries, work, n)
            scores[EXPERIMENTS[task]]["results"][name] = metrics
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(scores, handle, indent=2)
        handle.write("\n")
    if args.details:
        with open(args.details, "w") as handle:
            json.dump({"split": SPLIT, "isolation": isolation()[1], "status": status,
                       "per_query": results}, handle)
    for name, _ in methods:
        log(f"{name}: {'ok' if status[name] is None else 'FAILED - ' + status[name]}")
    log(f"scores written to {args.output} (solver logs: {logdir})")


if __name__ == "__main__":
    main()
