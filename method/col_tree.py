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
from data.graph import RoadNetwork, ObjectSet


class COLNode:
    """A node in the COL-Tree."""
    def __init__(self, node_id: int, level: int,
                 sul_node: Optional[SULNode] = None,
                 parent: Optional['COLNode'] = None):
        self.node_id = node_id
        self.level = level
        self.sul_node = sul_node
        self.parent = parent
        self.children: List['COLNode'] = []
        self.is_leaf = False
        self.odls: List[List[Tuple[float, int]]] = []
        self.landmark_to_odl_idx: Dict[int, int] = {}
        self.min_dist: List[float] = []
        self.max_dist: List[float] = []
        self.num_objects = 0

        # For leaf processing
        self.RP = -1  # right pointer for ODL traversal
        self.LP = -1  # left pointer for ODL traversal
        self.seen = False

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
    """

    def __init__(self, graph: RoadNetwork, sul_tree: SULTree,
                 object_set: ObjectSet,
                 lam: int = 256, b: int = 8):
        self.graph = graph
        self.sul_tree = sul_tree
        self.object_set = object_set
        self.lam = lam
        self.b = b
        self.root: Optional[COLNode] = None
        self.node_count = 0
        self._landmark_distance_cache: Dict[int, List[float]] = {}
        self._build()

    def _build(self):
        sul_root = self.sul_tree.root
        self.root = self._build_node(sul_root, level=0, parent=None)

    def _reset_query_state(self, node: 'COLNode'):
        """Reset query state on all nodes before a new query."""
        node.seen = False
        node.RP = -1
        node.LP = -1
        for child in node.children:
            self._reset_query_state(child)

    def _build_node(self, sul_node: SULNode, level: int,
                   parent: Optional[COLNode]) -> COLNode:
        self.node_count += 1
        col_node = COLNode(self.node_count, level, sul_node=sul_node, parent=parent)
        object_vertices = self._objects_in_sul_node(sul_node)
        n_objects = len(object_vertices)

        if n_objects <= self.lam:
            col_node.is_leaf = True
            col_node.num_objects = n_objects
            self._build_leaf_odls(col_node, sul_node, object_vertices)
        else:
            col_node.is_leaf = False
            for child_sul in sul_node.children:
                child_col = self._build_node(child_sul, level + 1, col_node)
                col_node.add_child(child_col)
            col_node.num_objects = n_objects
            self._build_internal_bounds(col_node, sul_node, object_vertices)
        return col_node

    def _count_objects_in_sul_node(self, sul_node: SULNode) -> int:
        return len(self._objects_in_sul_node(sul_node))

    def _objects_in_sul_node(self, sul_node: SULNode) -> List[int]:
        vertices = self._get_vertices_in_subtree(sul_node)
        obj_set = self.object_set.obj_set
        return [v for v in vertices if v in obj_set]

    def _build_leaf_odls(self, col_node: COLNode, sul_node: SULNode,
                         object_vertices: List[int]):
        """
        Build sorted ODLs for a COL-Tree leaf node.
        The sul_node may be an internal SUL-Tree node (when few objects).
        We need to collect objects from the subtree.
        """
        if not object_vertices:
            return

        for li_idx, landmark in enumerate(sul_node.landmarks):
            odl = []
            for obj_v in object_vertices:
                dist = self._sul_sdl_distance(sul_node, li_idx, obj_v)
                if dist < float('inf'):
                    odl.append((dist, obj_v))

            odl.sort(key=lambda x: x[0])
            col_node.odls.append(odl)
            col_node.landmark_to_odl_idx[landmark] = len(col_node.odls) - 1

        for odl in col_node.odls:
            if odl:
                col_node.min_dist.append(min(d for d, _ in odl))
                col_node.max_dist.append(max(d for d, _ in odl))
            else:
                col_node.min_dist.append(0.0)
                col_node.max_dist.append(0.0)

    def _build_internal_bounds(self, col_node: COLNode, sul_node: SULNode,
                               object_vertices: List[int]):
        """Store min/max landmark-object distances for an internal COL node."""
        for li_idx, landmark in enumerate(sul_node.landmarks):
            distances = [
                self._sul_sdl_distance(sul_node, li_idx, obj_v)
                for obj_v in object_vertices
            ]
            valid = [d for d in distances if d < float('inf')]
            if valid:
                col_node.min_dist.append(min(valid))
                col_node.max_dist.append(max(valid))
            else:
                col_node.min_dist.append(0.0)
                col_node.max_dist.append(0.0)
            col_node.landmark_to_odl_idx[landmark] = li_idx

    def _get_vertices_in_subtree(self, sul_node: SULNode) -> List[int]:
        """Get all vertices in a SUL-Tree node's subtree."""
        if sul_node.is_leaf:
            return sul_node.get_vertices_in_range()
        else:
            vertices = []
            for child in sul_node.children:
                vertices.extend(self._get_vertices_in_subtree(child))
            return vertices

    def _sul_sdl_distance(self, sul_node: SULNode, landmark_idx: int,
                          vertex: int) -> float:
        """Distance from a SUL node's local landmark to a vertex in its range."""
        if landmark_idx >= len(sul_node.sdls):
            return float('inf')
        idx = sul_node.vertex_to_sdl_idx.get(vertex)
        if idx is None:
            return float('inf')
        sdl = sul_node.sdls[landmark_idx]
        if 0 <= idx < len(sdl):
            return sdl[idx]
        return float('inf')

    def compute_lb(self, q: int, node: COLNode, Q: List[int] = None,
                   agg: str = 'max') -> float:
        if node.is_leaf:
            return self._compute_lb_leaf(q, node, Q, agg)
        else:
            return self._compute_lb_internal(q, node, Q, agg)

    def _compute_lb_internal(self, q: int, node: COLNode,
                              Q: List[int], agg: str) -> float:
        landmarks = node.get_landmarks()
        if not landmarks:
            return 0.0

        if Q and len(Q) > 1:
            # Compute individual lower bounds for each query vertex
            all_lbs = []
            for qi in Q:
                lb_values = []
                for li_idx, landmark in enumerate(landmarks):
                    if li_idx < len(node.max_dist) and li_idx < len(node.min_dist):
                        M_plus = node.max_dist[li_idx]
                        M_minus = node.min_dist[li_idx]
                    else:
                        continue
                    d_li_qi = self._get_root_landmark_dist(landmark, qi)
                    if d_li_qi is None:
                        d_li_qi = 0.0
                    if d_li_qi >= M_plus:
                        lb = d_li_qi - M_plus
                    elif d_li_qi <= M_minus:
                        lb = M_minus - d_li_qi
                    else:
                        lb = 0.0
                    lb_values.append(lb)
                max_lb = max(lb_values) if lb_values else 0.0
                all_lbs.append(max_lb)
            return self._aggregate_bounds(all_lbs, agg)
        else:
            # Single query vertex - just compute max LB
            lb_values = []
            for li_idx, landmark in enumerate(landmarks):
                if li_idx < len(node.max_dist) and li_idx < len(node.min_dist):
                    M_plus = node.max_dist[li_idx]
                    M_minus = node.min_dist[li_idx]
                else:
                    continue
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
            return max(lb_values) if lb_values else 0.0

    def _compute_lb_leaf(self, q: int, node: COLNode,
                         Q: List[int], agg: str) -> float:
        if not node.odls:
            return 0.0

        if Q and len(Q) > 1:
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
        """
        Get distance from any local landmark to a query target.

        Root landmark distances are already materialized over the whole graph.
        For non-root landmarks this reproducer computes and caches the exact
        landmark SSSP lazily. The paper avoids many of these lookups using
        root/LCA lower/upper-bound substitution; exact cached values preserve
        admissibility while keeping the query algorithm easy to audit.
        """
        for li_idx, lm in enumerate(self.sul_tree.root.landmarks):
            if lm == landmark:
                if li_idx < len(self.sul_tree.root.sdls):
                    sdl = self.sul_tree.root.sdls[li_idx]
                    if 0 <= target < len(sdl):
                        return sdl[target]
        if hasattr(self.sul_tree, 'landmark_distances') and landmark in self.sul_tree.landmark_distances:
            dist = self.sul_tree.landmark_distances[landmark]
            if target < len(dist):
                return dist[target]
        if landmark not in self._landmark_distance_cache:
            self._landmark_distance_cache[landmark] = self.graph.dijkstra(landmark)
        dist = self._landmark_distance_cache[landmark]
        if target < len(dist):
            return dist[target]
        return None

    def _aggregate_bounds(self, bounds: List[float], agg: str) -> float:
        if agg == 'max':
            return max(bounds) if bounds else 0.0
        elif agg == 'sum':
            return sum(bounds)
        else:
            return max(bounds) if bounds else 0.0

    def _next_tie(self) -> int:
        self._tie_counter = getattr(self, '_tie_counter', 0) + 1
        return self._tie_counter

    # =====================================================================
    # AkNN Query Algorithm
    # =====================================================================

    def query_aknn(self, Q: List[int], k: int, agg: str = 'max',
                    return_stats: bool = False):
        """Aggregate k Nearest Neighbor query."""
        if agg == 'sum':
            result, stats = self._aknn_sum(Q, k, return_stats=True)
        else:
            result, stats = self._aknn_max(Q, k, return_stats=True)
        if return_stats:
            return result, stats
        return result

    def _aknn_max(self, Q: List[int], k: int, return_stats: bool = False) -> List[int]:
        """
        AkNN with max aggregate. Implements Algorithm 1 from the paper.
        """
        self._reset_query_state(self.root)
        self._tie_counter = 0

        dijkstra_cache = {}
        for qi in Q:
            if qi not in dijkstra_cache:
                dijkstra_cache[qi] = self.graph.dijkstra(qi)

        result_objs = []
        result_dists = []
        D_k = float('inf')
        stats = {'candidate_objects_retrieved': 0, 'exact_distance_lookups': 0}

        pq = [(0.0, self._next_tie(), self.root, 'node')]

        while pq:
            lb, _, item, itype = heapq.heappop(pq)

            if lb >= D_k:
                break

            if itype == 'node':
                node = item
                if node.is_leaf:
                    if not node.seen:
                        self._init_leaf_node_aknn(node, Q, 'max')
                        node.seen = True
                    self._retrieve_objects_odl_aknn(node, Q, 'max', result_objs,
                                                    result_dists, D_k, pq, 0)

                    # Compute LB for remaining objects in ODL
                    node_lb = self._compute_leaf_lb_remaining(node, Q, 'max')
                    # Only push if there's still work to do (LB < inf and < D_k)
                    if node_lb < float('inf') and node_lb < D_k:
                        heapq.heappush(pq, (node_lb, self._next_tie(), node, 'node'))
                else:
                    for child in node.children:
                        clb = self.compute_lb(Q[0], child, Q, 'max')
                        heapq.heappush(pq, (clb, self._next_tie(), child, 'node'))
            else:
                obj = item
                stats['candidate_objects_retrieved'] += 1
                stats['exact_distance_lookups'] += 1
                dist = self._compute_aggregate_distance(obj, Q, 'max', dijkstra_cache)
                if dist < D_k:
                    bisect.insort(result_dists, dist)
                    heapq.heappush(result_objs, (-dist, obj))
                    if len(result_dists) >= k:
                        D_k = result_dists[-1]
                        if len(result_dists) > k:
                            result_dists.pop()
                            heapq.heappop(result_objs)

        final_results = [obj for _, obj in sorted(result_objs, key=lambda x: -x[0])]
        if return_stats:
            return final_results[:k], stats
        return final_results[:k]

    def _aknn_sum(self, Q: List[int], k: int, return_stats: bool = False) -> List[int]:
        """AkNN with sum aggregate."""
        self._reset_query_state(self.root)
        self._tie_counter = 0
        dijkstra_cache = {}
        for qi in Q:
            if qi not in dijkstra_cache:
                dijkstra_cache[qi] = self.graph.dijkstra(qi)

        result_objs = []
        result_dists = []
        D_k = float('inf')
        stats = {'candidate_objects_retrieved': 0, 'exact_distance_lookups': 0}
        pq = [(0.0, self._next_tie(), self.root, 'node')]

        while pq:
            lb, _, item, itype = heapq.heappop(pq)

            if lb >= D_k:
                break

            if itype == 'node':
                node = item
                if node.is_leaf:
                    if not node.seen:
                        self._init_leaf_node_aknn(node, Q, 'sum')
                        node.seen = True
                    self._retrieve_objects_odl_aknn(node, Q, 'sum', result_objs,
                                                    result_dists, D_k, pq, 0)

                    node_lb = self._compute_leaf_lb_remaining(node, Q, 'sum')
                    if node_lb < float('inf') and node_lb < D_k:
                        heapq.heappush(pq, (node_lb, self._next_tie(), node, 'node'))
                else:
                    for child in node.children:
                        clb = self.compute_lb(Q[0], child, Q, 'sum')
                        heapq.heappush(pq, (clb, self._next_tie(), child, 'node'))
            else:
                obj = item
                stats['candidate_objects_retrieved'] += 1
                stats['exact_distance_lookups'] += 1
                dist = self._compute_aggregate_distance(obj, Q, 'sum', dijkstra_cache)
                if dist < D_k:
                    bisect.insort(result_dists, dist)
                    heapq.heappush(result_objs, (-dist, obj))
                    if len(result_dists) >= k:
                        D_k = result_dists[-1]
                        if len(result_dists) > k:
                            result_dists.pop()
                            heapq.heappop(result_objs)

        final_results = [obj for _, obj in sorted(result_objs, key=lambda x: -x[0])]
        if return_stats:
            return final_results[:k], stats
        return final_results[:k]

    def _init_leaf_node_aknn(self, node: COLNode, Q: List[int], agg: str):
        """Initialize leaf node for AkNN processing (Line 15-19 of Algorithm 1)."""
        if not node.odls:
            return

        # Choose ODL with furthest landmark from Q
        best_idx = 0
        best_avg = -1
        for li_idx, odl in enumerate(node.odls):
            if not odl:
                continue
            landmark = node.get_landmarks()[li_idx]
            avg_d = sum(self._get_root_landmark_dist(landmark, qi) or 0 for qi in Q) / len(Q)
            if avg_d > best_avg:
                best_avg = avg_d
                best_idx = li_idx

        node.landmark_to_odl_idx = {node.get_landmarks()[i]: i for i in range(len(node.odls))}
        node.best_odl_idx = best_idx

        # Compute constants C_i for each query vertex
        landmark = node.get_landmarks()[best_idx]
        C = [self._get_root_landmark_dist(landmark, qi) or 0 for qi in Q]

        # Binary search for minimizing x*
        odl = node.odls[best_idx]
        if not odl:
            return

        distances = [d for d, _ in odl]

        if agg == 'max':
            x_star = (min(C) + max(C)) / 2.0
        else:  # sum
            C_sorted = sorted(C)
            n = len(C_sorted)
            if n % 2 == 0:
                x_star = (C_sorted[n // 2 - 1] + C_sorted[n // 2]) / 2.0
            else:
                x_star = C_sorted[n // 2]

        # Find the position closest to x* by computing LB for nearby positions
        # Search more positions to ensure we find the true minimum LB
        idx = bisect.bisect_left(distances, x_star)
        idx = max(0, min(idx, len(odl) - 1))

        # Check positions around idx to find the one with minimum LB
        # Search a wider range to handle cases where x* is between two positions
        if agg == 'max':
            def lb_at(pos):
                if 0 <= pos < len(distances):
                    return max(abs(c - distances[pos]) for c in C)
                return float('inf')
        else:
            def lb_at(pos):
                if 0 <= pos < len(distances):
                    return sum(abs(c - distances[pos]) for c in C)
                return float('inf')

        best_pos = idx
        best_lb = lb_at(idx)
        # Search ±5 positions around x* to find true minimum
        for pos in range(max(0, idx - 5), min(len(odl), idx + 6)):
            pos_lb = lb_at(pos)
            if pos_lb < best_lb:
                best_lb = pos_lb
                best_pos = pos

        node.RP = best_pos
        node.LP = best_pos
        node.best_odl = odl
        node.best_distances = distances
        node.best_landmark = landmark
        node.best_C = C

    def _retrieve_objects_odl_aknn(self, node: COLNode, Q: List[int], agg: str,
                                     result_objs: List, result_dists: List,
                                     D_k: float, pq: List, tie: int):
        """Retrieve the next ODL object by aggregate lower bound.

        The same leaf is reinserted with the lower bound of the next object,
        matching Algorithm 1's incremental candidate retrieval.
        """
        if not hasattr(node, 'best_odl') or not node.best_odl:
            return

        odl = node.best_odl
        distances = node.best_distances
        C = node.best_C

        lb_left = float('inf')
        if node.LP >= 0:
            d_lp = distances[node.LP]
            lb_left = max(abs(c - d_lp) for c in C) if agg == 'max' else sum(abs(c - d_lp) for c in C)

        lb_right = float('inf')
        if node.RP < len(odl):
            d_rp = distances[node.RP]
            lb_right = max(abs(c - d_rp) for c in C) if agg == 'max' else sum(abs(c - d_rp) for c in C)

        if min(lb_left, lb_right) >= D_k:
            return

        if node.LP == node.RP and node.LP >= 0:
            pos = node.LP
            node.LP -= 1
            node.RP += 1
        elif lb_left <= lb_right and node.LP >= 0:
            pos = node.LP
            node.LP -= 1
        elif node.RP < len(odl):
            pos = node.RP
            node.RP += 1
        else:
            return

        d_retrieved, obj = odl[pos]
        obj_lb = max(abs(c - d_retrieved) for c in C) if agg == 'max' else sum(abs(c - d_retrieved) for c in C)
        heapq.heappush(pq, (obj_lb, self._next_tie(), obj, 'obj'))

    def _compute_leaf_lb_remaining(self, node: COLNode, Q: List[int], agg: str) -> float:
        """Compute LB for remaining (unprocessed) objects in ODL."""
        if not hasattr(node, 'best_odl') or not node.best_odl:
            return float('inf')
        # LP is the next left position to explore, RP is the next right position
        # If LP < 0 and RP >= len, all objects are processed
        if node.LP < 0 and node.RP >= len(node.best_odl):
            return float('inf')

        C = node.best_C
        odl = node.best_odl
        distances = node.best_distances

        lb_left = float('inf')
        if node.LP >= 0:
            d_lp = distances[node.LP]
            if agg == 'max':
                lb_left = max(abs(c - d_lp) for c in C)
            else:
                lb_left = sum(abs(c - d_lp) for c in C)

        lb_right = float('inf')
        if node.RP < len(odl):
            d_rp = distances[node.RP]
            if agg == 'max':
                lb_right = max(abs(c - d_rp) for c in C)
            else:
                lb_right = sum(abs(c - d_rp) for c in C)

        return min(lb_left, lb_right)

    def _compute_aggregate_distance(self, obj: int, Q: List[int],
                                     agg: str,
                                     dijkstra_cache: dict = None) -> float:
        distances = []
        for qi in Q:
            if dijkstra_cache and qi in dijkstra_cache:
                d = dijkstra_cache[qi][obj]
            else:
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

    def query_kfn(self, q: int, k: int, return_stats: bool = False):
        """
        k Farthest Neighbor query (Algorithm 2 from paper).
        """
        self._reset_query_state(self.root)
        self._tie_counter = 0
        self._kfn_q = q  # Store for use in helper methods
        self._kfn_k = k
        result_objs = []  # min-heap: (dist, obj)
        D_k = 0.0
        stats = {
            'nodes_popped': 0,
            'leaf_visits': 0,
            'candidate_objects_retrieved': 0,
            'exact_distance_lookups': 0,
        }

        # Precompute Dijkstra from q
        d_q = self.graph.dijkstra(q)

        # Max-heap for traversal by upper bound
        pq = []
        heapq.heappush(pq, (-self.compute_ub(q, self.root), self._next_tie(), self.root, 'node'))

        while pq:
            neg_ub, _, item, itype = heapq.heappop(pq)
            ub = -neg_ub
            stats['nodes_popped'] += 1

            # Only prune when we have k results and ub falls below D_k
            if len(result_objs) >= k and ub <= D_k:
                break

            if itype == 'node':
                node = item
                if node.is_leaf:
                    stats['leaf_visits'] += 1
                    if not node.seen:
                        self._init_leaf_node_kfn(node, q)
                        node.seen = True

                    self._retrieve_objects_odl_kfn(node, d_q, result_objs,
                                                    D_k, pq, 0,
                                                    stats)
                    D_k = result_objs[0][0] if len(result_objs) >= k else 0.0

                    node_ub = self._compute_leaf_ub_remaining(node, self._kfn_q)
                    # Re-add if: haven't found k results, OR (node has more objects AND ub >= D_k)
                    more_objects = node.RP >= 0
                    if len(result_objs) < k or (more_objects and node_ub >= D_k):
                        heapq.heappush(pq, (-node_ub, self._next_tie(), node, 'node'))
                else:
                    for child in node.children:
                        cub = self.compute_ub(q, child)
                        if len(result_objs) < k or cub >= D_k:
                            heapq.heappush(pq, (-cub, self._next_tie(), child, 'node'))
            else:
                obj = item
                dist = d_q[obj]
                if len(result_objs) < k:
                    heapq.heappush(result_objs, (dist, obj))
                elif dist > result_objs[0][0]:
                    heapq.heapreplace(result_objs, (dist, obj))
                D_k = result_objs[0][0] if len(result_objs) >= k else 0.0

        final = [obj for _, obj in sorted(result_objs, key=lambda x: -x[0])]
        if return_stats:
            return final[:k], stats
        return final[:k]

    def _init_leaf_node_kfn(self, node: COLNode, q: int):
        """Initialize leaf node for kFN processing."""
        if not node.odls:
            return

        # Choose ODL with closest landmark
        best_idx = 0
        best_min = float('inf')
        for li_idx, odl in enumerate(node.odls):
            if not odl:
                continue
            landmark = node.get_landmarks()[li_idx]
            d_lq = self._get_root_landmark_dist(landmark, q) or float('inf')
            if d_lq < best_min:
                best_min = d_lq
                best_idx = li_idx

        node.best_odl_idx = best_idx
        node.best_odl = node.odls[best_idx]
        node.best_landmark = node.get_landmarks()[best_idx]
        node.RP = len(node.best_odl) - 1 if node.best_odl else -1
        node.best_odl_size = len(node.best_odl)

    def _retrieve_objects_odl_kfn(self, node: COLNode, d_q: List[float],
                                   result_objs: List,
                                   D_k: float, pq: List, tie: int,
                                   stats: Optional[Dict[str, int]] = None):
        """Retrieve objects from ODL for kFN (Line 23-27 of Algorithm 2)."""
        if not hasattr(node, 'best_odl') or not node.best_odl:
            return

        odl = node.best_odl
        landmark = node.best_landmark
        d_lq = self._get_root_landmark_dist(landmark, self._kfn_q) or 0.0

        while node.RP >= 0:
            d_lp, obj = odl[node.RP]
            ub = d_lq + d_lp
            # For kFN, stop when ub <= D_k (no remaining object can be farther than D_k)
            if ub <= D_k:
                break

            dist = d_q[obj]
            if stats is not None:
                stats['candidate_objects_retrieved'] += 1
                stats['exact_distance_lookups'] += 1
            # For kFN, add if dist >= D_k (all k farthest objects)
            if len(result_objs) < self._kfn_k:
                heapq.heappush(result_objs, (dist, obj))
            elif dist > result_objs[0][0]:
                heapq.heapreplace(result_objs, (dist, obj))
            D_k = result_objs[0][0] if len(result_objs) >= self._kfn_k else D_k
            node.RP -= 1

    def _compute_leaf_ub_remaining(self, node: COLNode, q: int) -> float:
        """Compute UB for remaining objects in ODL."""
        if not hasattr(node, 'best_odl') or not node.best_odl:
            return 0.0
        if node.RP < 0:
            return 0.0

        d_lq = self._get_root_landmark_dist(node.best_landmark, q) or 0.0
        return d_lq + node.best_odl[node.RP][0]

    # =====================================================================
    # Range Query Algorithm
    # =====================================================================

    def query_range(self, q: int, r: float, return_stats: bool = False):
        """
        Range query: find all objects within distance r from q.
        """
        d_q = self.graph.dijkstra(q)
        results = []
        stats = {'candidate_objects_retrieved': 0, 'exact_distance_lookups': 0}
        stack = [self.root]

        while stack:
            node = stack.pop()
            if node.is_leaf:
                objs, leaf_stats = self._range_leaf(node, r, d_q)
                results.extend(objs)
                stats['candidate_objects_retrieved'] += leaf_stats['candidate_objects_retrieved']
                stats['exact_distance_lookups'] += leaf_stats['exact_distance_lookups']
            else:
                for child in node.children:
                    lb = self.compute_lb(q, child)
                    ub = self.compute_ub(q, child)
                    if ub <= r:
                        sub_objs = self._get_all_objects_in_node(child)
                        results.extend(sub_objs)
                        stats['candidate_objects_retrieved'] += len(sub_objs)
                    elif lb <= r:
                        stack.append(child)
        final = list(set(results))
        if return_stats:
            return final, stats
        return final

    def _range_leaf(self, node: COLNode, r: float, d_q: List[float]):
        """Process leaf node for range query."""
        stats = {'candidate_objects_retrieved': 0, 'exact_distance_lookups': 0}
        if not node.odls:
            return [], stats

        results = set()
        checked = set()
        # Use only the first ODL to avoid double-counting objects
        for li_idx in [0]:
            odl = node.odls[li_idx] if li_idx < len(node.odls) else []
            if not odl:
                continue
            landmark = node.get_landmarks()[li_idx]
            d_lq = d_q[landmark] if landmark < len(d_q) else float('inf')

            for d_lp, obj in odl:
                if obj in checked:
                    continue
                checked.add(obj)
                stats['candidate_objects_retrieved'] += 1
                ub = d_lq + d_lp
                if ub <= r:
                    results.add(obj)
                    continue

                M_plus = node.max_dist[li_idx] if li_idx < len(node.max_dist) else float('inf')
                M_minus = node.min_dist[li_idx] if li_idx < len(node.min_dist) else 0.0

                if d_lq >= M_plus:
                    lb = d_lq - M_plus
                elif d_lq <= M_minus:
                    lb = M_minus - d_lq
                else:
                    lb = 0.0

                if lb <= r:
                    stats['exact_distance_lookups'] += 1
                    dist = d_q[obj]
                    if dist <= r:
                        results.add(obj)

        return list(results), stats

    def _get_all_objects_in_node(self, node: COLNode) -> List[int]:
        """Get all objects in a node recursively."""
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
