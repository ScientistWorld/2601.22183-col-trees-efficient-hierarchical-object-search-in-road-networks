#!/usr/bin/env python3
"""Baselines that evaluate every object (no hierarchical pruning).

  --mode bruteforce  reveal every object and compute every exact distance
                     (what the paper's index exists to avoid).
  --mode alt_filter  reveal every object, bound each one with the 16 root
                     (ALT) landmarks and verify candidates in bound order:
                     the paper's AUB-PHL competitor for kFN (Section 9.1) and
                     the landmark analogue of the multi-step filter for AkNN /
                     range (Section 10, refs. [51, 57]).

Both use a root-only structure written by baseline/build.py.
"""

from __future__ import annotations

import argparse
import heapq
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.oracle_client import OracleClient  # noqa: E402


def bounds(qrec, rec, m):
    lb, ub = 0, float("inf")
    for j in range(m):
        x, y = rec[j], qrec[j]
        if abs(x - y) > lb:
            lb = abs(x - y)
        if x + y < ub:
            ub = x + y
    return lb, ub


def serve(mode):
    c = OracleClient()
    hello = c.recv()
    task = hello["task"]
    c.send({"type": "ready"})
    c.recv()  # landmark records (unused)
    c.send({"type": "ok"})
    while True:
        msg = c.recv()
        if msg.get("type") == "bye":
            return
        if msg.get("type") != "query":
            continue
        cnt = msg["root"][0]
        items = c.get(0, 0, 0, cnt)
        objs = [o for o, _, _ in items]
        recs = {o: r for o, _, r in items}
        m = len(msg["root"][1])
        qrecs = msg["q_records"]
        nq = len(msg["q"])
        if mode == "bruteforce":
            dist = [c.dist(i, objs) for i in range(nq)]
            if task == "kfn":
                order = sorted(zip(dist[0], objs), reverse=True)
                c.answer([o for _, o in order[:msg["k"]]])
            elif task == "range":
                c.answer([o for d, o in zip(dist[0], objs) if d <= msg["radius"]])
            else:
                agg = max if msg["agg"] == "max" else sum
                score = sorted((agg(col), o) for o, col in zip(objs, zip(*dist)))
                c.answer([o for _, o in score[:msg["k"]]])
            continue
        if task == "kfn":
            k = msg["k"]
            order = sorted(((bounds(qrecs[0], recs[o], m)[1], o) for o in objs), reverse=True)
            best = []
            for ub, o in order:
                if len(best) >= k and ub <= best[0][0]:
                    break
                d = c.dist(0, [o])[0]
                if len(best) < k:
                    heapq.heappush(best, (d, o))
                elif d > best[0][0]:
                    heapq.heapreplace(best, (d, o))
            c.answer([o for _, o in best])
        elif task == "range":
            r = msg["radius"]
            out = []
            for o in objs:
                lb, ub = bounds(qrecs[0], recs[o], m)
                if ub <= r:
                    out.append(o)
                elif lb <= r and c.dist(0, [o])[0] <= r:
                    out.append(o)
            c.answer(out)
        else:
            k = msg["k"]
            agg = max if msg["agg"] == "max" else sum
            order = sorted((agg(bounds(qrecs[i], recs[o], m)[0] for i in range(nq)), o) for o in objs)
            best = []  # max-heap (-d, o)
            for lb, o in order:
                if len(best) >= k and lb >= -best[0][0]:
                    break
                res = c.request({"op": "batch", "reqs": [{"op": "dist", "q": i, "v": [o]} for i in range(nq)]})
                d = agg(r["d"][0] for r in res["res"])
                if len(best) < k:
                    heapq.heappush(best, (-d, o))
                elif d < -best[0][0]:
                    heapq.heapreplace(best, (-d, o))
            c.answer([o for _, o in best])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["bruteforce", "alt_filter"], required=True)
    serve(ap.parse_args().mode)


if __name__ == "__main__":
    main()
