#!/usr/bin/env python3
"""COL-Tree query solver (paper Sections 3.2-6) speaking the evaluation protocol.

The SUL-Tree (hierarchy + landmarks) is the submitted structure; the evaluator
holds its subgraph distance lists.  For every query the COL-Tree of the
query's object set is the SUL-Tree compacted at nodes holding <= lambda
objects (Section 3.2): internal COL nodes are bounded through their per-landmark
min/max object distances (node summaries), COL leaves through their sorted
object distance lists (ODLs).

  * AkNN  - Algorithm 1 (best-first by aggregate lower bound, Lemma 2/3 start
            position in the leaf ODL, two-pointer retrieval).
  * kFN   - Algorithm 2 (best-first by upper bound, ODL scanned from its end).
  * range - Algorithm 3 (stack traversal, UB-confirmed and LB-pruned subtrees,
            ODL window around d(q, c.l)).

Bounds follow Section 3.3: Eq. (4)/(6) per landmark, Eq. (7) with LB/UB(l, q)
substituted through the root (and lowest-common-ancestor) landmarks when q is
outside the landmark's subgraph, plus the alternate bound from the root
landmarks.  Candidate objects are tightened with the root landmarks before
they enter the queue (Algorithm 1 line 28, Algorithm 2 line 26).

Options (defaults = paper settings, Table 8):
  --lam       maximum objects in a COL leaf (256)
  --bounds    'paper' (own + root landmarks, root/LCA substitution) or
              'all' (every landmark on the path, every common ancestor)
"""

from __future__ import annotations

import argparse
import heapq
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.oracle_client import OracleClient  # noqa: E402
from data.structure_io import load_structure  # noqa: E402

INF = float("inf")
CHUNK = 32


class Cursor:
    """Lazily peeked distances of one object distance list."""

    def __init__(self, client, node, pos, count):
        self.client, self.node, self.pos, self.count = client, node, pos, count
        self.cache = {}

    def d(self, i, forward=True):
        v = self.cache.get(i)
        if v is None:
            lo, hi = (i, min(self.count, i + CHUNK)) if forward else (max(0, i - CHUNK + 1), i + 1)
            idx = [j for j in range(lo, hi) if j not in self.cache]
            for j, x in zip(idx, self.client.peek(self.node, self.pos, idx)):
                self.cache[j] = x
            v = self.cache[i]
        return v


class Solver:
    def __init__(self, client: OracleClient, lam: int = 256, bounds: str = "paper"):
        self.c = client
        self.lam = lam
        self.all_bounds = bounds == "all"

    # ------------------------------------------------------------------ setup
    def serve(self):
        hello = self.c.recv()
        self.task = hello["task"]
        st = load_structure(hello["structure"])
        self.st = st
        self.L = st.landmarks
        self.off = st.offset
        self.children = st.children
        self.depth = st.depth
        self.parent = st.parent
        self.leaf_of = st.leaf_of
        self._paths = {}
        self.c.send({"type": "ready"})
        msg = self.c.recv()
        self.lrec = {int(v): r for v, r in msg["records"].items()}
        self.c.send({"type": "ok"})
        while True:
            msg = self.c.recv()
            kind = msg.get("type")
            if kind == "bye":
                return
            if kind == "query":
                self.c.answer(self.answer(msg))

    def path(self, node):
        p = self._paths.get(node)
        if p is None:
            p = self.st.path(node)
            self._paths[node] = p
        return p

    def answer(self, msg):
        self.Q = msg["q"]
        self.qrec = msg["q_records"]
        self.qleaf = [self.leaf_of[q] for q in self.Q]
        self.qpath = [set(self.path(leaf)) for leaf in self.qleaf]
        self.summ = {0: msg["root"]}
        self.bcache = {}
        self.exact = {}
        self.tie = 0
        if self.task == "aknn":
            return self.aknn(msg["k"], msg["agg"])
        if self.task == "kfn":
            return self.kfn(msg["k"])
        return self.range(msg["radius"])

    # -------------------------------------------------------------- helpers
    def next_tie(self):
        self.tie += 1
        return self.tie

    def summary(self, node):
        return self.summ[node]

    def col_children(self, node):
        kids = self.children[node]
        missing = [k for k in kids if k not in self.summ]
        if missing:
            self.summ.update(self.c.nodes(missing))
        return [k for k in kids if self.summ[k][0] > 0]

    def is_col_leaf(self, node):
        return not self.children[node] or self.summ[node][0] <= self.lam

    def leaf_landmarks(self, node):
        """(record position, landmark vertex) usable as the ODL of a COL leaf."""
        if self.L[node]:
            return [(self.off[node] + a, l) for a, l in enumerate(self.L[node])]
        out = []
        for anc in self.path(node):
            out.extend((self.off[anc] + a, l) for a, l in enumerate(self.L[anc]))
        return out

    def lq_bounds(self, i, node, a):
        """Bounds on d(q_i, l) for landmark a of `node` (Eq. 7 substitution)."""
        l = self.L[node][a]
        key = (i, l)
        hit = self.exact.get(key)
        if hit is not None:
            return hit, hit
        b = self.bcache.get(key)
        if b is not None:
            return b
        if node in self.qpath[i]:
            d = self.qrec[i][self.off[node] + a]
            b = (d, d)
        else:
            lca = self.st.lca(node, self.qleaf[i])
            if self.all_bounds:
                anchors = self.path(lca)
            else:
                anchors = [0] if lca == 0 else [0, lca]
            lr, qr = self.lrec[l], self.qrec[i]
            lo, hi = 0, INF
            for anc in anchors:
                o = self.off[anc]
                for j in range(o, o + len(self.L[anc])):
                    x, y = lr[j], qr[j]
                    if x - y > lo:
                        lo = x - y
                    elif y - x > lo:
                        lo = y - x
                    if x + y < hi:
                        hi = x + y
            b = (lo, hi)
        self.bcache[key] = b
        return b

    def exact_landmark(self, idxs, node, a):
        """Exact d(q_i, l) for the given query indices (oracle call if not free)."""
        l = self.L[node][a]
        need = []
        for i in idxs:
            if (i, l) in self.exact:
                continue
            if node in self.qpath[i]:
                self.exact[(i, l)] = self.qrec[i][self.off[node] + a]
            else:
                need.append(i)
        if need:
            res = self.c.request({"op": "batch", "reqs": [{"op": "dist", "q": i, "v": [l]} for i in need]})
            for i, r in zip(need, res["res"]):
                self.exact[(i, l)] = r["d"][0]
        return [self.exact[(i, l)] for i in idxs]

    def node_bounds(self, i, node):
        """(LB, UB) on d(q_i, p) for every object p below `node`."""
        cnt, mins, maxs = self.summ[node]
        lb, ub = 0, INF
        if self.all_bounds:
            anchors = self.path(node)
        else:
            anchors = [node] if node == 0 else [0, node]
        qr = self.qrec[i]
        for anc in anchors:
            o = self.off[anc]
            for a in range(len(self.L[anc])):
                j = o + a
                lo, hi = self.lq_bounds(i, anc, a)
                mn, mx = mins[j], maxs[j]
                if lo >= mx:
                    if lo - mx > lb:
                        lb = lo - mx
                elif hi <= mn:
                    if mn - hi > lb:
                        lb = mn - hi
                if hi + mx < ub:
                    ub = hi + mx
        return lb, ub

    def object_bounds(self, i, rec, leaf_pos, d_leaf):
        """(LB, UB) on d(q_i, p) from p's record: the COL leaf landmark (exact
        distance d_leaf) and the root landmarks, or every landmark ('all')."""
        x = rec[leaf_pos]
        lb = abs(d_leaf - x)
        ub = d_leaf + x
        qr = self.qrec[i]
        for j in range(len(self.L[0])):
            x, y = rec[j], qr[j]
            if abs(x - y) > lb:
                lb = abs(x - y)
            if x + y < ub:
                ub = x + y
        if self.all_bounds:
            j = 0
            for node, a in self._layout:
                if node == 0:
                    j += 1
                    continue
                lo, hi = self.lq_bounds(i, node, a)
                x = rec[j]
                if lo >= x:
                    if lo - x > lb:
                        lb = lo - x
                elif hi <= x:
                    if x - hi > lb:
                        lb = x - hi
                if hi + x < ub:
                    ub = hi + x
                j += 1
        return lb, ub

    def set_layout(self, node):
        """Record layout (owner node, landmark index) of vertices below `node`."""
        layout = []
        for anc in self.path(node):
            layout.extend((anc, a) for a in range(len(self.L[anc])))
        self._layout = layout

    # ----------------------------------------------------------------- AkNN
    def aknn(self, k, agg):
        nq = len(self.Q)
        idxs = list(range(nq))
        aggf = max if agg == "max" else sum
        pq = [(0, self.next_tie(), 0, 0)]  # (key, tie, kind 0=node/1=object, item)
        best = []  # max-heap of (-d, obj)
        dk = INF
        leaves = {}
        while pq and pq[0][0] < dk:
            key, _, kind, item = heapq.heappop(pq)
            if kind == 1:
                res = self.c.request({"op": "batch", "reqs": [{"op": "dist", "q": i, "v": [item]} for i in idxs]})
                d = aggf(r["d"][0] for r in res["res"])
                if d < dk:
                    heapq.heappush(best, (-d, item))
                    if len(best) > k:
                        heapq.heappop(best)
                    if len(best) == k:
                        dk = -best[0][0]
            elif self.is_col_leaf(item):
                st = leaves.get(item)
                if st is None:
                    st = self._aknn_init_leaf(item, idxs, agg)
                    leaves[item] = st
                self._aknn_retrieve(item, st, pq, idxs, aggf)
                nxt = self._aknn_next(st)
                if nxt < INF:
                    heapq.heappush(pq, (nxt, self.next_tie(), 0, item))
            else:
                for e in self.col_children(item):
                    lbs = [self.node_bounds(i, e)[0] for i in idxs]
                    heapq.heappush(pq, (aggf(lbs), self.next_tie(), 0, e))
        return [obj for _, obj in best]

    def _aknn_init_leaf(self, node, idxs, agg):
        cnt = self.summ[node][0]
        cands = self.leaf_landmarks(node)
        # ODL whose landmark has the largest average (lower-bound) distance to Q
        best_pos, best_val = None, -1.0
        for pos, l in cands:
            nd, a = self._landmark_owner(node, pos)
            avg = sum(self.lq_bounds(i, nd, a)[0] for i in idxs) / len(idxs)
            if avg > best_val:
                best_val, best_pos = avg, pos
        nd, a = self._landmark_owner(node, best_pos)
        consts = self.exact_landmark(idxs, nd, a)
        if agg == "sum":
            s = sorted(consts)
            m = len(s)
            xstar = s[m // 2] if m % 2 else (s[m // 2 - 1] + s[m // 2]) / 2.0
        else:
            xstar = (min(consts) + max(consts)) / 2.0
        cur = Cursor(self.c, node, best_pos, cnt)

        def f(dv):
            vals = [abs(cst - dv) for cst in consts]
            return max(vals) if agg == "max" else sum(vals)

        i = self.c.bisect(node, best_pos, xstar)
        # convex f: the minimiser is next to the insertion point
        cand = [j for j in (i - 1, i) if 0 <= j < cnt]
        start = min(cand, key=lambda j: (f(cur.d(j)), j))
        return {"pos": best_pos, "consts": consts, "f": f, "cur": cur, "lp": start - 1,
                "rp": start, "cnt": cnt}

    def _landmark_owner(self, node, pos):
        for anc in reversed(self.path(node)):
            if self.off[anc] <= pos < self.off[anc] + len(self.L[anc]):
                return anc, pos - self.off[anc]
        raise ValueError("bad landmark position")

    def _aknn_next(self, st):
        fl = st["f"](st["cur"].d(st["lp"], False)) if st["lp"] >= 0 else INF
        fr = st["f"](st["cur"].d(st["rp"])) if st["rp"] < st["cnt"] else INF
        return min(fl, fr)

    def _aknn_retrieve(self, node, st, pq, idxs, aggf):
        f, cur, consts = st["f"], st["cur"], st["consts"]
        if self.all_bounds:
            self.set_layout(node)
        while True:
            fl = f(cur.d(st["lp"], False)) if st["lp"] >= 0 else INF
            fr = f(cur.d(st["rp"])) if st["rp"] < st["cnt"] else INF
            low = min(fl, fr)
            minkey = pq[0][0] if pq else INF
            if low == INF or low > minkey:
                return
            if fl <= fr:
                j = st["lp"]
                st["lp"] -= 1
            else:
                j = st["rp"]
                st["rp"] += 1
            obj, dv, rec = self.c.get(node, st["pos"], j, j + 1)[0]
            if self.all_bounds:
                self.set_layout(self.leaf_of[obj])
            lbs = [self.object_bounds(i, rec, st["pos"], consts[i])[0] for i in idxs]
            heapq.heappush(pq, (aggf(lbs), self.next_tie(), 1, obj))

    # ------------------------------------------------------------------ kFN
    def kfn(self, k):
        root_ub = self.node_bounds(0, 0)[1]
        pq = [(-root_ub, self.next_tie(), 0, 0)]
        best = []  # min-heap (d, obj)
        dk = 0
        leaves = {}
        while pq and (-pq[0][0] > dk or len(best) < k):
            negkey, _, kind, item = heapq.heappop(pq)
            if kind == 1:
                d = self.c.dist(0, [item])[0]
                if len(best) < k:
                    heapq.heappush(best, (d, item))
                elif d > best[0][0]:
                    heapq.heapreplace(best, (d, item))
                dk = best[0][0] if len(best) >= k else 0
            elif self.is_col_leaf(item):
                st = leaves.get(item)
                if st is None:
                    st = self._kfn_init_leaf(item)
                    leaves[item] = st
                self._kfn_retrieve(item, st, pq)
                if st["rp"] >= 0:
                    heapq.heappush(pq, (-(st["dl"] + st["cur"].d(st["rp"], False)), self.next_tie(), 0, item))
            else:
                for e in self.col_children(item):
                    ub = self.node_bounds(0, e)[1]
                    if len(best) < k or ub > dk:
                        heapq.heappush(pq, (-ub, self.next_tie(), 0, e))
        return [obj for _, obj in best]

    def _kfn_init_leaf(self, node):
        cnt = self.summ[node][0]
        best_pos, best_ub = None, INF
        for pos, l in self.leaf_landmarks(node):
            nd, a = self._landmark_owner(node, pos)
            ub = self.lq_bounds(0, nd, a)[1]
            if best_pos is None or ub < best_ub:
                best_pos, best_ub = pos, ub
        nd, a = self._landmark_owner(node, best_pos)
        dl = self.exact_landmark([0], nd, a)[0]
        return {"pos": best_pos, "dl": dl, "cur": Cursor(self.c, node, best_pos, cnt), "rp": cnt - 1}

    def _kfn_retrieve(self, node, st, pq):
        cur, dl = st["cur"], st["dl"]
        while st["rp"] >= 0:
            u = dl + cur.d(st["rp"], False)
            maxkey = -pq[0][0] if pq else -INF
            if u < maxkey:
                return
            j = st["rp"]
            st["rp"] -= 1
            obj, dv, rec = self.c.get(node, st["pos"], j, j + 1)[0]
            if self.all_bounds:
                self.set_layout(self.leaf_of[obj])
            ub = self.object_bounds(0, rec, st["pos"], dl)[1]
            heapq.heappush(pq, (-ub, self.next_tie(), 1, obj))

    # ---------------------------------------------------------------- range
    def range(self, r):
        out = set()
        stack = [0]
        while stack:
            c = stack.pop()
            if self.is_col_leaf(c):
                self._range_leaf(c, r, out)
                continue
            for e in self.col_children(c):
                lb, ub = self.node_bounds(0, e)
                if ub <= r:
                    cnt = self.summ[e][0]
                    for obj, _, _ in self.c.get(e, 0, 0, cnt):
                        out.add(obj)
                elif lb <= r:
                    stack.append(e)
        return sorted(out)

    def _range_leaf(self, node, r, out):
        cnt, mins, _ = self.summ[node]
        if cnt == 0:
            return
        options = []
        for pos, l in self.leaf_landmarks(node):
            nd, a = self._landmark_owner(node, pos)
            lo, hi = self.lq_bounds(0, nd, a)
            options.append((pos, nd, a, lo, hi, mins[pos]))
        within = [o for o in options if o[5] + o[4] <= r]
        if within:
            pos, nd, a = min(within, key=lambda o: o[5] + o[4])[:3]
        else:
            pos, nd, a = max(options, key=lambda o: o[3])[:3]
        dl = self.exact_landmark([0], nd, a)[0]
        if self.all_bounds:
            self.set_layout(node)
        ip = self.c.bisect(node, pos, r - dl, "right")
        if ip > 0:
            for obj, _, _ in self.c.get(node, pos, 0, ip):
                out.add(obj)
        lp = self.c.bisect(node, pos, dl, "right") - 1
        rp = max(ip, lp + 1)
        cur = Cursor(self.c, node, pos, cnt)
        while lp >= ip and dl - cur.d(lp, False) <= r:
            self._range_check(node, pos, lp, dl, r, out)
            lp -= 1
        while rp < cnt and cur.d(rp) - dl <= r:
            self._range_check(node, pos, rp, dl, r, out)
            rp += 1

    def _range_check(self, node, pos, j, dl, r, out):
        obj, dv, rec = self.c.get(node, pos, j, j + 1)[0]
        if self.all_bounds:
            self.set_layout(self.leaf_of[obj])
        lb, ub = self.object_bounds(0, rec, pos, dl)
        if lb > r:
            return
        if ub <= r or self.c.dist(0, [obj])[0] <= r:
            out.add(obj)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lam", type=int, default=256)
    ap.add_argument("--bounds", choices=["paper", "all"], default="paper")
    args = ap.parse_args()
    Solver(OracleClient(), lam=args.lam, bounds=args.bounds).serve()


if __name__ == "__main__":
    main()
