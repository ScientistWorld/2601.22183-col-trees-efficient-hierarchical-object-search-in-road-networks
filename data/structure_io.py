"""File format for a submitted hierarchical landmark index ("structure").

A structure fixes *which* precomputed landmark distances exist; the evaluator
computes the distances themselves on its own (hidden) travel-time network.

JSON object with keys:
  "format":    "hier-landmark-v1"
  "parent":    list[int]   parent node of each node; node 0 is the root with
                           parent -1, and parent[i] < i for every other node
  "landmarks": list[list[int]]  landmark vertex ids of each node (may be empty)
  "leaf_of":   {"encoding": "zlib-base64-uint32-le", "data": str}  or list[int]
               leaf node of every vertex (only childless nodes may be used)
  "meta":      optional free-form dict (ignored by the evaluator)

The vertex set of a node is the union of the vertex sets of the leaves below
it.  For every node n and landmark l of n the evaluator stores d(l, v) for all
v in S(n) (a "subgraph distance list").  Index size is the total number of
such entries; see briefing/evaluation.md for the limits that are enforced.
"""

from __future__ import annotations

import base64
import json
import sys
import zlib
from array import array

FORMAT = "hier-landmark-v1"


def encode_leaf_of(leaf_of) -> dict:
    arr = array("I", (int(x) for x in leaf_of))
    if sys.byteorder != "little":
        arr.byteswap()
    data = base64.b64encode(zlib.compress(arr.tobytes(), 9)).decode("ascii")
    return {"encoding": "zlib-base64-uint32-le", "data": data}


def decode_leaf_of(obj) -> array:
    if isinstance(obj, list):
        return array("I", obj)
    if obj.get("encoding") != "zlib-base64-uint32-le":
        raise ValueError(f"unknown leaf_of encoding {obj.get('encoding')!r}")
    arr = array("I")
    arr.frombytes(zlib.decompress(base64.b64decode(obj["data"])))
    if sys.byteorder != "little":
        arr.byteswap()
    return arr


def save_structure(path, parent, landmarks, leaf_of, meta=None) -> None:
    payload = {
        "format": FORMAT,
        "parent": [int(p) for p in parent],
        "landmarks": [[int(v) for v in lm] for lm in landmarks],
        "leaf_of": encode_leaf_of(leaf_of),
        "meta": meta or {},
    }
    with open(path, "w") as handle:
        json.dump(payload, handle, separators=(",", ":"))


class Structure:
    """Parsed structure with derived tree helpers (no distances)."""

    def __init__(self, parent, landmarks, leaf_of, meta=None):
        self.parent = list(parent)
        self.landmarks = [list(lm) for lm in landmarks]
        self.leaf_of = leaf_of
        self.meta = meta or {}
        n_nodes = len(self.parent)
        self.children = [[] for _ in range(n_nodes)]
        for i in range(1, n_nodes):
            self.children[self.parent[i]].append(i)
        self.depth = [0] * n_nodes
        # offset[i]: position of node i's first landmark inside the record of
        # any vertex below i (records list the landmarks of the root first,
        # then each node on the path down to the vertex's leaf).
        self.offset = [0] * n_nodes
        for i in range(1, n_nodes):
            p = self.parent[i]
            self.depth[i] = self.depth[p] + 1
            self.offset[i] = self.offset[p] + len(self.landmarks[p])
        self.prefix_len = [self.offset[i] + len(self.landmarks[i]) for i in range(n_nodes)]

    @property
    def n_nodes(self) -> int:
        return len(self.parent)

    def path(self, node: int) -> list[int]:
        out = []
        while node >= 0:
            out.append(node)
            node = self.parent[node]
        out.reverse()
        return out

    def path_of_vertex(self, v: int) -> list[int]:
        return self.path(int(self.leaf_of[v]))

    def is_ancestor(self, a: int, node: int) -> bool:
        """True if `a` is an ancestor of (or equal to) `node`."""
        da = self.depth[a]
        while self.depth[node] > da:
            node = self.parent[node]
        return node == a

    def lca(self, a: int, b: int) -> int:
        while self.depth[a] > self.depth[b]:
            a = self.parent[a]
        while self.depth[b] > self.depth[a]:
            b = self.parent[b]
        while a != b:
            a = self.parent[a]
            b = self.parent[b]
        return a


def load_structure(path) -> Structure:
    with open(path) as handle:
        payload = json.load(handle)
    if payload.get("format") != FORMAT:
        raise ValueError(f"{path}: unsupported structure format {payload.get('format')!r}")
    return Structure(payload["parent"], payload["landmarks"], decode_leaf_of(payload["leaf_of"]),
                     payload.get("meta"))
