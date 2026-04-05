"""
COL-Tree (Compacted Object-Landmark Tree)
==========================================
Hierarchical object index for road network POI search.

Key idea: Compacted version of SUL-Tree where leaf nodes contain at most λ objects
with sorted Object Distance Lists (ODL) for efficient candidate retrieval.
Supports AkNN, kFN, and range queries.
"""

import heapq
import bisect
from typing import List, Dict, Tuple, Optional, Set
from method.sul_tree import SULTree, SULNode
from method.graph import RoadNetwork, ObjectSet


class COLNode:
    """A node in the COL-Tree."""

    def __init__(self, node_id: int, level: int,
                 sul_node: Optional[SULNode] = None,
                 parent: Optional['COLNode'] = None):
        self.node_id = node_id
        self.level = level
        self.sul_node = sul_node  # corresponding SUL-Tree node
        self.parent = parent
        self.children: List['COLNode'] = []
        self.is_leaf = False

        # For leaf nodes: Object Distance Lists (ODL)
        # Each ODL_i is a list of (object_distance, object_id) sorted by distance
        self.odls: List[List[Tuple[float, int]]] = []  # one per landmark
        self.landmark_to_odl_idx: Dict[int, int] = {}  # landmark vertex -> ODL index

        # Min/max distances from landmarks to any object in this node
        self.min_dist: List[float] = []
        self.max_dist: List[float] = []

        # Number of objects in this leaf
        self.num_objects = 0

    def add_child(self, child: 'COLNode'):
        self.children.append(child)

    def get_landmarks(self) -> List[int]:
        if self.sul_node:
            return self.sul_node.landmarks
        return []

    def get_num_landmarks(self) -> int:
        return len(self.get_landmarks())


class COLTree:
    """
    COL-Tree: Compacted Object-Landmark Tree for POI search.

    Construction from SUL-Tree:
    1. Walk SUL-Tree top-down
    2. Prune when node has <= λ objects
    3. At leaf: build sorted ODLs from SUL-Tree SDLs
    """

    def __init__(self, graph: RoadNetwork, sul_tree: SULTree,
                 object_set: ObjectSet,
                 lam: int = 256, b: int = 8):
        self.graph = graph
        self.sul_tree = sul_tree
        self.object_set = object_set
        self.lam = lam  # max objects per leaf
        self.b = b

        self.root: Optional[COLNode] = None
        self.node_count = 0

        # Build the tree
        self._build()

    def _build(self):
        """Build COL-Tree from SUL-Tree."""
        sul_root = self.sul_tree.root
        self.root = self._build_node(sul_root, level=0, parent=None)

    def _build_node(self, sul_node: SULNode, level: int,
                   parent: Optional[COLNode]) -> COLNode:
        """Recursively build COL-Tree nodes from SUL-Tree nodes."""
        self.node_count += 1
        col_node = COLNode(self.node_count, level, sul_node=sul_node, parent=parent)

        # Count objects in this subtree
        n_objects = self._count_objects_in_sul_node(sul_node)

        if n_objects <= self.lam:
            # This node becomes a leaf
            col_node.is_leaf = True
            col_node.num_objects = n_objects
            self._build_leaf_odls(col_node, sul_node)
        else:
            # Expand to children
            col_node.is_leaf = False
            for child_sul in sul_node.children:
                child_col = self._build_node(child_sul, level + 1, col_node)
                col_node.add_child(child_col)

        return col_node

    def _count_objects_in_sul_node(self, sul_node: SULNode) -> int:
        """Count objects in a SUL-Tree node's subtree."""
        if sul_node.is_leaf:
            vertices = sul_node.get_vertices_in_range()
            obj_set = self.object_set.obj_set
            return sum(1 for v in vertices if v in obj_set)
        else:
            total = 0
            for child in sul_node.children:
                total += self._count_objects_in_sul_node(child)
            return total

    def _build_leaf_odls(self, col_node: COLNode, sul_node: SULNode):
        """Build sorted ODLs for a leaf node from SUL-Tree SDLs."""
        if not sul_node.is_leaf:
            return

        vertices = sul_node.get_vertices_in_range()
        obj_set = self.object_set.obj_set

        # Get object-landmark pairs
        objects_in_node = [v for v in vertices if v in obj_set]

        # Build ODL for each landmark
        for li_idx, landmark in enumerate(sul_node.landmarks):
            if li_idx >= len(sul_node.sdls):
                continue
            sdl = sul_node.sdls[li_idx]

            # Extract distances for objects only
            odl = []
            for i, v in enumerate(vertices):
                if v in obj_set:
                    dist = sdl[i] if i < len(sdl) else float('inf')
                    odl.append((dist, v))

            # Sort by distance
            odl.sort(key=lambda x: x[0])
            col_node.odls.append(odl)
            col_node.landmark_to_odl_idx[landmark] = len(col_node.odls) - 1

        # Compute min/max distances for each landmark's ODL
        for odl in col_node.odls:
            if odl:
                col_node.min_dist.append(min(d for d, _ in odl))
                col_node.max_dist.append(max(d for d, _ in odl))
            else:
                col_node.min_dist.append(0.0)
                col_node.max_dist.append(0.0)

    # =====================================================================
    # Landmark Lower-Bound and Upper-Bound Computations
    # =====================================================================

    def compute_lb(self, q: int, node: COLNode, Q: List[int] = None,
                   agg: str = 'max') -> float:
        """
        Compute lower bound from query vertex q (or query set Q) to COL-Tree node.

        Uses Lemma 1: agg(LB(q_i, p)) <= d_agg(Q, p)
        And Eq (7): LB_li(q, node) based on min/max distances.
        """
        if node.is_leaf:
            return self._compute_lb_leaf(q, node, Q, agg)
        else:
            return self._compute_lb_internal(q, node, Q, agg)

    def _compute_lb_internal(self, q: int, node: COLNode,
                              Q: List[int], agg: str) -> float:
        """Compute lower bound to internal node."""
        landmarks = node.get_landmarks()
        if not landmarks:
            return 0.0

        lb_values = []
        for li_idx, landmark in enumerate(landmarks):
            if li_idx >= len(node.max_dist) or li_idx >= len(node.min_dist):
                continue

            M_plus = node.max_dist[li_idx]
            M_minus = node.min_dist[li_idx]

            # Use root landmark distances
            d_li_q = self._get_root_landmark_dist(landmark, q)
            if d_li_q is None:
                d_li_q = 0.0

            if d_li_q >= M_plus:
                lb = d_li_q - M_plus
            elif d_li_q <= M_minus:
                lb = M_minus - d_li_q
            else:
                lb = 0.0
            lb_values.append(lb)

        max_lb = max(lb_values) if lb_values else 0.0

        # Aggregate if multiple query vertices
        if Q and len(Q) > 1:
            return self._aggregate_bounds([max_lb] * len(Q), agg)
        return max_lb

    def _compute_lb_leaf(self, q: int, node: COLNode,
                         Q: List[int], agg: str) -> float:
        """Compute lower bound to leaf node."""
        if not node.odls:
            return 0.0

        # For aggregate queries, we need the LB for each query vertex
        if Q and len(Q) > 1:
            # Compute LB for each query vertex, then aggregate
            all_lbs = []
            for qi in Q:
                lbs = []
                for li_idx, landmark in enumerate(node.get_landmarks()):
                    if li_idx >= len(node.max_dist) or li_idx >= len(node.min_dist):
                        continue
                    M_plus = node.max_dist[li_idx]
                    M_minus = node.min_dist[li_idx]
                    d_li_qi = self._get_root_landmark_dist(landmark, qi)
                    if d_li_qi is None:
                        d_li_qi = 0.0

                    if d_li_qi >= M_plus:
                        lb = d_li_qi - M_plus
                    elif d_li_qi <= M_minus:
                        lb = M_minus - d_li_qi
                    else:
                        lb = 0.0
                    lbs.append(lb)
                max_lb = max(lbs) if lbs else 0.0
                all_lbs.append(max_lb)
            return self._aggregate_bounds(all_lbs, agg)
        else:
            # Single query vertex
            lbs = []
            for li_idx, landmark in enumerate(node.get_landmarks()):
                if li_idx >= len(node.max_dist) or li_idx >= len(node.min_dist):
                    continue
                M_plus = node.max_dist[li_idx]
                M_minus = node.min_dist[li_idx]
                d_li_q = self._get_root_landmark_dist(landmark, q)
                if d_li_q is None:
                    d_li_q = 0.0

                if d_li_q >= M_plus:
                    lb = d_li_q - M_plus
                elif d_li_q <= M_minus:
                    lb = M_minus - d_li_q
                else:
                    lb = 0.0
                lbs.append(lb)
            return max(lbs) if lbs else 0.0

    def compute_ub(self, q: int, node: COLNode) -> float:
        """
        Compute upper bound from query vertex q to COL-Tree node.
        UB_min(q, node) = min_i (d(li, q) + M+_i)
        """
        landmarks = node.get_landmarks()
        if not landmarks:
            return float('inf')

        ub_values = []
        for li_idx, landmark in enumerate(landmarks):
            if li_idx >= len(node.max_dist):
                continue
            M_plus = node.max_dist[li_idx]
            d_li_q = self._get_root_landmark_dist(landmark, q)
            if d_li_q is None:
                d_li_q = 0.0
            ub_values.append(d_li_q + M_plus)

        return min(ub_values) if ub_values else float('inf')

    def _get_root_landmark_dist(self, landmark: int, target: int) -> Optional[float]:
        """Get distance from root landmark to target."""
        return self.sul_tree._get_distance_from_landmark(
            self.sul_tree.root, landmark, target)

    def _aggregate_bounds(self, bounds: List[float], agg: str) -> float:
        """Aggregate lower bounds using sum or max."""
        if agg == 'max':
            return max(bounds) if bounds else 0.0
        elif agg == 'sum':
            return sum(bounds)
        else:
            return max(bounds) if bounds else 0.0

    # =====================================================================
    # AkNN Query Algorithm
    # =====================================================================

    def query_aknn(self, Q: List[int], k: int, agg: str = 'max') -> List[int]:
        """
        Aggregate k Nearest Neighbor query.

        Returns k objects with minimum aggregate distance from Q.
        Uses hierarchical traversal with priority queue.
        """
        if agg == 'sum':
            return self._aknn_sum(Q, k)
        else:
            return self._aknn_max(Q, k)

    def _aknn_max(self, Q: List[int], k: int) -> List[int]:
        """
        AkNN with max aggregate function.

        Key insight (Lemma 3): min_x max_i |C_i - x| = (C_min + C_max) / 2
        where C_i = d(landmark, q_i) for each query vertex.
        """
        results = []  # max-heap of (neg_dist, obj)
        result_dists = []  # actual aggregate distances
        D_k = float('inf')  # k-th best distance

        # Priority queue: (lower_bound, node_or_obj)
        # Min-heap for traversal
        pq = [(0.0, self.root, None)]  # (lb, node, None=internal or obj_id)

        while pq:
            lb, item, _ = heapq.heappop(pq)

            if lb >= D_k:
                break

            if isinstance(item, COLNode):
                node = item
                if node.is_leaf:
                    # Process leaf node
                    objs = self._aknn_leaf_max(node, Q, D_k, results, result_dists)
                    if objs and len(result_dists) >= k:
                        D_k = result_dists[-1] if result_dists else float('inf')
                else:
                    # Expand non-leaf node
                    for child in node.children:
                        clb = self.compute_lb(Q[0], child, Q, 'max')
                        heapq.heappush(pq, (clb, child, None))
            else:
                # It's an object
                obj = item
                dist = self._compute_aggregate_distance(obj, Q, 'max')
                if dist < D_k:
                    bisect.insort(result_dists, dist)
                    heapq.heappush(results, (-dist, obj))
                    if len(result_dists) > k:
                        result_dists.pop()
                        if results:
                            heapq.heappop(results)
                    D_k = result_dists[-1] if len(result_dists) >= k else float('inf')

        # Return top k objects
        result_objs = [obj for _, obj in sorted(results, key=lambda x: -x[0])]
        return result_objs[:k]

    def _aknn_sum(self, Q: List[int], k: int) -> List[int]:
        """
        AkNN with sum aggregate function.

        Key insight (Lemma 2): min_x sum_i |C_i - x| = median(C_i)
        """
        results = []  # max-heap
        result_dists = []
        D_k = float('inf')

        pq = [(0.0, self.root)]

        while pq:
            lb, item = heapq.heappop(pq)

            if lb >= D_k:
                break

            if isinstance(item, COLNode):
                node = item
                if node.is_leaf:
                    objs = self._aknn_leaf_sum(node, Q, D_k, results, result_dists)
                    if objs and len(result_dists) >= k:
                        D_k = result_dists[-1]
                else:
                    for child in node.children:
                        clb = self.compute_lb(Q[0], child, Q, 'sum')
                        heapq.heappush(pq, (clb, child))
            else:
                obj = item
                dist = self._compute_aggregate_distance(obj, Q, 'sum')
                if dist < D_k:
                    bisect.insort(result_dists, dist)
                    heapq.heappush(results, (-dist, obj))
                    if len(result_dists) > k:
                        result_dists.pop()
                        if results:
                            heapq.heappop(results)
                    D_k = result_dists[-1] if len(result_dists) >= k else float('inf')

        result_objs = [obj for _, obj in sorted(results, key=lambda x: -x[0])]
        return result_objs[:k]

    def _aknn_leaf_max(self, node: COLNode, Q: List[int], D_k: float,
                        results: List, result_dists: List) -> List[int]:
        """Process leaf node for AkNN with max aggregate."""
        if not node.odls:
            return []

        # Choose ODL with furthest landmark from Q (for better bounds)
        best_odl_idx = 0
        best_avg_dist = -1
        for li_idx, odl in enumerate(node.odls):
            if not odl:
                continue
            landmark = node.get_landmarks()[li_idx]
            avg_d = sum(self._get_root_landmark_dist(landmark, qi) or 0 for qi in Q) / len(Q)
            if avg_d > best_avg_dist:
                best_avg_dist = avg_d
                best_odl_idx = li_idx

        odl = node.odls[best_odl_idx]
        if not odl:
            return []

        # Compute constants C_i = d(landmark, q_i) for each query vertex
        landmark = node.get_landmarks()[best_odl_idx]
        C = [self._get_root_landmark_dist(landmark, qi) or 0 for qi in Q]

        # For max: x* = (min(C) + max(C)) / 2
        C_sorted = sorted(C)
        x_star = (C_sorted[0] + C_sorted[-1]) / 2.0

        # Binary search to find closest object
        distances = [d for d, _ in odl]
        idx = bisect.bisect_left(distances, x_star)
        idx = max(0, min(idx, len(odl) - 1))

        # Retrieve from idx going outward
        left, right = idx, idx
        retrieved = set()

        while left > 0 or right < len(odl) - 1:
            dist_l = distances[left - 1] if left > 0 else float('inf')
            dist_r = distances[right + 1] if right < len(odl) - 1 else float('inf')

            if dist_l <= dist_r and left > 0:
                left -= 1
                d, obj = odl[left]
            elif right < len(odl) - 1:
                right += 1
                d, obj = odl[right]
            else:
                break

            if obj in retrieved:
                continue
            retrieved.add(obj)

            # Compute actual aggregate distance
            agg_dist = self._compute_aggregate_distance(obj, Q, 'max')
            if agg_dist < D_k:
                bisect.insort(result_dists, agg_dist)
                heapq.heappush(results, (-agg_dist, obj))

        return list(retrieved)

    def _aknn_leaf_sum(self, node: COLNode, Q: List[int], D_k: float,
                        results: List, result_dists: List) -> List[int]:
        """Process leaf node for AkNN with sum aggregate."""
        if not node.odls:
            return []

        # Choose ODL with furthest landmark
        best_odl_idx = 0
        best_avg_dist = -1
        for li_idx, odl in enumerate(node.odls):
            if not odl:
                continue
            landmark = node.get_landmarks()[li_idx]
            avg_d = sum(self._get_root_landmark_dist(landmark, qi) or 0 for qi in Q) / len(Q)
            if avg_d > best_avg_dist:
                best_avg_dist = avg_d
                best_odl_idx = li_idx

        odl = node.odls[best_odl_idx]
        if not odl:
            return []

        landmark = node.get_landmarks()[best_odl_idx]
        C = [self._get_root_landmark_dist(landmark, qi) or 0 for qi in Q]
        C_sorted = sorted(C)

        # For sum: x* = median
        if len(C_sorted) % 2 == 0:
            x_star = (C_sorted[len(C_sorted) // 2 - 1] + C_sorted[len(C_sorted) // 2]) / 2.0
        else:
            x_star = C_sorted[len(C_sorted) // 2]

        distances = [d for d, _ in odl]
        idx = bisect.bisect_left(distances, x_star)
        idx = max(0, min(idx, len(odl) - 1))

        left, right = idx, idx
        retrieved = set()

        while left > 0 or right < len(odl) - 1:
            dist_l = distances[left - 1] if left > 0 else float('inf')
            dist_r = distances[right + 1] if right < len(odl) - 1 else float('inf')

            if dist_l <= dist_r and left > 0:
                left -= 1
                d, obj = odl[left]
            elif right < len(odl) - 1:
                right += 1
                d, obj = odl[right]
            else:
                break

            if obj in retrieved:
                continue
            retrieved.add(obj)

            agg_dist = self._compute_aggregate_distance(obj, Q, 'sum')
            if agg_dist < D_k:
                bisect.insort(result_dists, agg_dist)
                heapq.heappush(results, (-agg_dist, obj))

        return list(retrieved)

    def _compute_aggregate_distance(self, obj: int, Q: List[int],
                                     agg: str) -> float:
        """Compute exact aggregate distance from Q to object."""
        distances = []
        for qi in Q:
            d = self.graph.dijkstra(qi)[obj]
            distances.append(d)
        if agg == 'max':
            return max(distances)
        elif agg == 'sum':
            return sum(distances)
        return max(distances)

    # =====================================================================
    # kFN Query Algorithm
    # =====================================================================

    def query_kfn(self, q: int, k: int) -> List[int]:
        """
        k Farthest Neighbor query.

        Returns k objects with maximum network distance from q.
        Uses upper-bounds for pruning (incremental retrieval by UB).
        """
        results = []  # min-heap of (dist, obj) for results
        result_dists = []  # actual distances
        D_k = 0.0  # k-th largest distance found

        # Max-heap for traversal (by upper bound)
        pq = []  # max-heap: (-ub, node_or_obj)
        heapq.heappush(pq, (-self.compute_ub(q, self.root), self.root))

        while pq:
            neg_ub, item = heapq.heappop(pq)
            ub = -neg_ub

            if ub <= D_k:
                break

            if isinstance(item, COLNode):
                node = item
                if node.is_leaf:
                    self._kfn_leaf(node, q, D_k, results, result_dists)
                    if result_dists:
                        D_k = result_dists[-1]
                else:
                    for child in node.children:
                        cub = self.compute_ub(q, child)
                        if cub > D_k:
                            heapq.heappush(pq, (-cub, child))
            else:
                obj = item
                dist = self.graph.dijkstra(q)[obj]
                if dist > D_k:
                    bisect.insort(result_dists, dist)
                    heapq.heappush(results, (dist, obj))
                    if len(result_dists) > k:
                        result_dists.pop()
                        if results:
                            heapq.heappop(results)
                    D_k = result_dists[-1] if len(result_dists) >= k else 0.0

        # Return top k farthest
        result_objs = [obj for _, obj in sorted(results, key=lambda x: -x[0])]
        return result_objs[:k]

    def _kfn_leaf(self, node: COLNode, q: int, D_k: float,
                   results: List, result_dists: List):
        """Process leaf node for kFN query."""
        if not node.odls:
            return

        # Choose ODL with closest landmark (for better upper bounds)
        best_odl_idx = 0
        best_min_dist = float('inf')
        for li_idx, odl in enumerate(node.odls):
            if not odl:
                continue
            landmark = node.get_landmarks()[li_idx]
            d_lq = self._get_root_landmark_dist(landmark, q) or float('inf')
            if d_lq < best_min_dist:
                best_min_dist = d_lq
                best_odl_idx = li_idx

        odl = node.odls[best_odl_idx]
        if not odl:
            return

        # Start from the end (largest distance = best upper bound)
        rp = len(odl) - 1
        landmark = node.get_landmarks()[best_odl_idx]

        while rp >= 0:
            d_lp, obj = odl[rp]
            # Compute upper bound: d(l, q) + d(l, p)
            d_lq = self._get_root_landmark_dist(landmark, q) or 0.0
            ub = d_lq + d_lp

            if ub <= D_k:
                break

            # Compute actual distance
            dist = self.graph.dijkstra(q)[obj]
            if dist > D_k:
                bisect.insort(result_dists, dist)
                heapq.heappush(results, (dist, obj))
                if len(result_dists) > len(odl):
                    result_dists.pop()
                    if results:
                        heapq.heappop(results)
                D_k = result_dists[-1] if len(result_dists) >= len(odl) else 0.0

            rp -= 1

    # =====================================================================
    # Range Query Algorithm
    # =====================================================================

    def query_range(self, q: int, r: float) -> List[int]:
        """
        Range query: find all objects within distance r from q.

        Uses stack-based traversal with lower/upper bound pruning.
        """
        results = []

        # Stack for DFS
        stack = [self.root]

        while stack:
            node = stack.pop()

            if node.is_leaf:
                objs = self._range_leaf(node, q, r)
                results.extend(objs)
            else:
                # Evaluate children
                for child in node.children:
                    lb = self.compute_lb(q, child)
                    ub = self.compute_ub(q, child)

                    if ub <= r:
                        # All objects are results - DFS to get them all
                        results.extend(self._get_all_objects_in_node(child))
                    elif lb <= r:
                        stack.append(child)
                    # else: pruned (lb > r)

        return list(set(results))

    def _range_leaf(self, node: COLNode, q: int, r: float) -> List[int]:
        """Process leaf node for range query."""
        if not node.odls:
            return []

        results = []

        # Try each ODL
        for li_idx, odl in enumerate(node.odls):
            if not odl:
                continue
            landmark = node.get_landmarks()[li_idx]
            d_lq = self._get_root_landmark_dist(landmark, q) or 0.0

            for d_lp, obj in odl:
                # Upper bound check first (cheaper)
                ub = d_lq + d_lp
                if ub <= r:
                    results.append(obj)
                    continue

                # Lower bound check
                M_plus = node.max_dist[li_idx] if li_idx < len(node.max_dist) else float('inf')
                M_minus = node.min_dist[li_idx] if li_idx < len(node.min_dist) else 0.0

                if d_lq >= M_plus:
                    lb = d_lq - M_plus
                elif d_lq <= M_minus:
                    lb = M_minus - d_lq
                else:
                    lb = 0.0

                if lb <= r:
                    # Need exact distance
                    dist = self.graph.dijkstra(q)[obj]
                    if dist <= r:
                        results.append(obj)

        return list(set(results))

    def _get_all_objects_in_node(self, node: COLNode) -> List[int]:
        """Get all objects in a node (recursive)."""
        if node.is_leaf:
            objs = set()
            for odl in node.odls:
                for _, obj in odl:
                    objs.add(obj)
            return list(objs)
        else:
            objs = []
            for child in node.children:
                objs.extend(self._get_all_objects_in_node(child))
            return objs
