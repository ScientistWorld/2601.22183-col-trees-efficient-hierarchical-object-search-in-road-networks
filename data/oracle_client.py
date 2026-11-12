"""Client side of the evaluation protocol (see briefing/evaluation.md).

A submitted solver is a process that talks JSON lines with the evaluator over
stdin/stdout.  This module wraps the protocol; solvers must not print anything
else to stdout (use stderr for logs).

Requests:
  nodes(ids)              per-node summaries for the current query's object set
  peek(node, pos, idx)    distances stored at given ranks of an object distance list
  bisect(node, pos, x)    rank of value x in an object distance list
  get(node, pos, lo, hi)  reveal the objects at ranks [lo, hi) (+ their records)
  dist(qi, vertices)      exact network distances from query vertex qi
What is counted per query:
  candidates  every object revealed by get, passed to dist or returned, plus
              every non-root index node holding at least one of the query's
              objects that any request touches (once per node; empty nodes
              and the root are free)
  calls       every distinct (query vertex, vertex) pair passed to dist

While a solver runs, eval/, .git and data/downloads/ are empty directories:
a solver cannot read the evaluator or the raw public data (travel times,
coordinates, POI files); it carries what it needs in its own files.
"""

from __future__ import annotations

import json
import sys


class ProtocolError(RuntimeError):
    pass


class OracleClient:
    def __init__(self, fin=None, fout=None):
        self.fin = fin or sys.stdin.buffer
        self.fout = fout or sys.stdout.buffer

    # -- raw messaging -------------------------------------------------
    def send(self, obj) -> None:
        self.fout.write(json.dumps(obj, separators=(",", ":")).encode() + b"\n")
        self.fout.flush()

    def recv(self) -> dict:
        line = self.fin.readline()
        if not line:
            raise EOFError("evaluator closed the connection")
        msg = json.loads(line)
        if isinstance(msg, dict) and "error" in msg:
            raise ProtocolError(msg["error"])
        return msg

    def request(self, req: dict) -> dict:
        self.send(req)
        return self.recv()

    # -- free requests ---------------------------------------------------
    def nodes(self, ids):
        """Return {node: (count, mins, maxs)} for the requested node ids."""
        ids = [int(i) for i in ids]
        if not ids:
            return {}
        res = self.request({"op": "nodes", "ids": ids})["nodes"]
        return {i: tuple(r) for i, r in zip(ids, res)}

    def peek(self, node: int, pos: int, idx):
        return self.request({"op": "peek", "node": int(node), "pos": int(pos),
                             "idx": [int(i) for i in idx]})["d"]

    def bisect(self, node: int, pos: int, x, side: str = "left") -> int:
        return self.request({"op": "bisect", "node": int(node), "pos": int(pos),
                             "x": x, "side": side})["i"]

    # -- counted requests -----------------------------------------------
    def get(self, node: int, pos: int, lo: int, hi: int):
        """Reveal ODL entries [lo, hi): list of (object, distance, record)."""
        items = self.request({"op": "get", "node": int(node), "pos": int(pos),
                              "lo": int(lo), "hi": int(hi)})["items"]
        return [(int(o), d, rec) for o, d, rec in items]

    def dist(self, qi: int, vertices):
        vertices = [int(v) for v in vertices]
        if not vertices:
            return []
        return self.request({"op": "dist", "q": int(qi), "v": vertices})["d"]

    def answer(self, result) -> None:
        self.request({"op": "answer", "result": [int(x) for x in result]})
