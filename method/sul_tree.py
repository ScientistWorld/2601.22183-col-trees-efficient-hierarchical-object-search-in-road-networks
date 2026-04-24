"""
SUL-Tree (Subgraph-Landmark Tree)
=================================
Hierarchical partitioning of a road network with landmark-based distance lists.

Key idea: Partition the graph recursively into b-way subgraphs. Each node has m landmarks
with precomputed distances (SDL) to all vertices in its subgraph.
"""

import random
import heapq
from typing import List, Dict, Tuple, Optional, Set
from data.graph import RoadNetwork


# Vertex ID range for implicit storage
class VertexRange:
    """Represents an implicit range of vertex IDs."""
    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end
        self.size = end - start

    def contains(self, vid: int) -> bool:
        return self.start <= vid < self.end

    def __repr__(self):
        return f"[{self.start}, {self.end})"


class SULNode:
    """A node in the SUL-Tree representing a subgraph."""
    def __init__(self, node_id: int, level: int,
                 vertex_range: Optional[VertexRange] = None,
                 parent: Optional['SULNode'] = None):
        self.node_id = node_id
        self.level = level
        self.vertex_range = vertex_range  # implicit vertex ID range
        self.parent = parent
        self.children: List['SULNode'] = []
        self.is_leaf = False

        # Landmarks: list of (landmark_id, sdl)
        # SDL = list of (vertex_id, distance) for all vertices in this subgraph
        self.landmarks: List[int] = []  # landmark vertex IDs
        self.sdls: List[List[float]] = []  # one SDL per landmark
        self.sdl_size: int = 0  # number of vertices in this SDL

        # Min/max distances from landmarks to any vertex in this node's subtree
        self.min_dist: List[float] = []  # min_nT, li
        self.max_dist: List[float] = []  # max_nT, li

    def add_child(self, child: 'SULNode'):
        self.children.append(child)

    def get_vertices_in_range(self) -> List[int]:
        """Return list of vertex IDs in this node's range."""
        if self.vertex_range:
            return list(range(self.vertex_range.start, self.vertex_range.end))
        return []

    def contains_vertex(self, vid: int) -> bool:
        if self.vertex_range:
            return self.vertex_range.contains(vid)
        return False


class SULTree:
    """
    SUL-Tree: Hierarchical road network index with landmark-based distances.

    Construction:
    1. Partition graph recursively into b-way subgraphs
    2. For each node, select m landmarks and compute SDLs
    3. Store vertex IDs implicitly via range encoding
    """

    def __init__(self, graph: RoadNetwork, b: int = 8, m: int = 2,
                 alpha: int = 1024, landmark_policy: str = 'random'):
        self.graph = graph
        self.b = b  # branching factor
        self.m = m  # number of landmarks per node
        self.alpha = alpha  # min vertices per leaf
        self.landmark_policy = landmark_policy

        self.root: Optional[SULNode] = None
        self.node_count = 0

        # Partition the graph
        self._partition()

    def _partition(self):
        """Build the SUL-Tree by recursive graph partitioning."""
        n = self.graph.num_vertices

        # Use contiguous vertex ID ranges
        self.root = self._build_node(0, n, level=0, parent=None)
        self._assign_vertex_ranges(self.root)

        # Select root landmarks and compute their SDLs
        self._select_root_landmarks()

        # Propagate landmarks to all nodes (inherit from parent)
        self._propagate_landmarks(self.root)

    def _select_root_landmarks(self):
        """Select m landmarks for the root node and compute their SDLs."""
        vertices = self.root.get_vertices_in_range()
        if len(vertices) < self.m:
            self.root.landmarks = vertices[:]
        else:
            if self.landmark_policy == 'random':
                self.root.landmarks = self._select_random_landmarks(vertices)
            elif self.landmark_policy == 'border':
                self.root.landmarks = self._select_border_landmarks(self.root, vertices)
            elif self.landmark_policy == 'minmax':
                self.root.landmarks = self._select_minmax_landmarks(self.root, vertices)
            else:
                self.root.landmarks = self._select_random_landmarks(vertices)

        # Compute SDLs for root only
        self._compute_sdls(self.root)

    def _propagate_landmarks(self, node: SULNode):
        """Propagate root landmarks to all nodes and compute min/max distances."""
        if node == self.root:
            # Root already has landmarks and SDLs
            # Set min/max for root from its ODLs
            for li_idx, sdl in enumerate(node.sdls):
                valid_dists = [d for d in sdl if d < float('inf')]
                if valid_dists:
                    node.min_dist.append(min(valid_dists))
                    node.max_dist.append(max(valid_dists))
                else:
                    node.min_dist.append(0.0)
                    node.max_dist.append(0.0)
        else:
            # Non-root nodes inherit root landmarks
            node.landmarks = self.root.landmarks[:]
            # Compute min/max distances for this node from root's SDLs
            node.sdls = []  # Don't store per-node SDLs; use root's
            for li_idx, lm in enumerate(node.landmarks):
                if li_idx < len(self.root.sdls):
                    root_sdl = self.root.sdls[li_idx]
                    # Extract distances for vertices in this node's range
                    if node.vertex_range:
                        start = node.vertex_range.start
                        end = node.vertex_range.end
                        local_dists = root_sdl[start:end]
                        valid_dists = [d for d in local_dists if d < float('inf')]
                        if valid_dists:
                            node.min_dist.append(min(valid_dists))
                            node.max_dist.append(max(valid_dists))
                        else:
                            node.min_dist.append(0.0)
                            node.max_dist.append(0.0)
                    else:
                        node.min_dist.append(0.0)
                        node.max_dist.append(0.0)
                else:
                    node.min_dist.append(0.0)
                    node.max_dist.append(0.0)
            node.sdl_size = node.vertex_range.size if node.vertex_range else 0

        # Recurse to children
        for child in node.children:
            self._propagate_landmarks(child)

    def _build_node(self, start: int, end: int, level: int,
                   parent: Optional[SULNode]) -> SULNode:
        """Recursively build SUL-Tree nodes."""
        self.node_count += 1
        node = SULNode(self.node_count, level, parent=parent)

        size = end - start
        if size <= self.alpha:
            node.is_leaf = True
            node.vertex_range = VertexRange(start, end)
            return node

        # Partition into b subgraphs
        chunk_size = size // self.b
        for i in range(self.b):
            c_start = start + i * chunk_size
            c_end = start + (i + 1) * chunk_size if i < self.b - 1 else end
            child = self._build_node(c_start, c_end, level + 1, parent=node)
            node.add_child(child)

        return node

    def _assign_vertex_ranges(self, node: SULNode):
        """Assign vertex ranges bottom-up."""
        if node.is_leaf:
            node.sdl_size = node.vertex_range.size if node.vertex_range else 0
            return

        # Process children first (bottom-up)
        for child in node.children:
            self._assign_vertex_ranges(child)

        # Then compute this node's range from children
        if node.children:
            child_ranges = [c.vertex_range for c in node.children if c.vertex_range]
            if child_ranges:
                min_start = min(r.start for r in child_ranges)
                max_end = max(r.end for r in child_ranges)
                node.vertex_range = VertexRange(min_start, max_end)
                node.sdl_size = max_end - min_start
        # Non-leaf nodes don't store explicit vertices (they inherit children's ranges)

    def build(self):
        """Compute landmarks and SDLs for all nodes."""
        # Already done in __init__ via _partition(), but safe to call again
        pass

    def _select_landmarks(self, node: SULNode):
        """Select landmarks for a node using the configured policy."""
        # Select from vertices in range
        vertices = node.get_vertices_in_range()
        if not vertices:
            return

        if len(vertices) < self.m:
            node.landmarks = vertices[:]
        else:
            if self.landmark_policy == 'random':
                node.landmarks = self._select_random_landmarks(vertices)
            elif self.landmark_policy == 'border':
                node.landmarks = self._select_border_landmarks(node, vertices)
            elif self.landmark_policy == 'minmax':
                node.landmarks = self._select_minmax_landmarks(node, vertices)
            else:
                node.landmarks = self._select_random_landmarks(vertices)

        # Compute SDLs for this node
        self._compute_sdls(node)

        # Recursively process children
        for child in node.children:
            self._select_landmarks(child)

    def _select_random_landmarks(self, vertices: List[int]) -> List[int]:
        """Select m random landmarks from vertices."""
        n = min(self.m, len(vertices))
        return random.sample(vertices, n)

    def _select_border_landmarks(self, node: SULNode, vertices: List[int]) -> List[int]:
        """Select border landmarks (furthest from already selected)."""
        if len(vertices) <= self.m:
            return vertices[:]

        selected = [vertices[0]]  # start with first vertex
        adj = self.graph.adj
        vertex_set = set(vertices)

        # Find border vertices (adjacent to vertices outside the range)
        border = set()
        for v in vertices:
            for neighbor, _ in adj[v]:
                if neighbor not in vertex_set:
                    border.add(v)
                    break

        if len(border) < self.m:
            border.update(vertices)

        candidates = list(border)
        while len(selected) < self.m and candidates:
            best = max(candidates, key=lambda c: min(
                self.graph.euclidean_distance(c, s) for s in selected if self.graph.euclidean_distance(c, s) > 0
            ) if selected else 0.0)
            selected.append(best)
            candidates.remove(best) if best in candidates else None

        return selected[:self.m]

    def _select_minmax_landmarks(self, node: SULNode, vertices: List[int]) -> List[int]:
        """Select landmarks that minimize max distance to border vertices."""
        if len(vertices) <= self.m:
            return vertices[:]

        # Sample subset of border vertices
        adj = self.graph.adj
        vertex_set = set(vertices)
        border = set()
        for v in vertices:
            for neighbor, _ in adj[v]:
                if neighbor not in vertex_set:
                    border.add(v)
                    break

        if not border:
            border = set(vertices[:min(100, len(vertices))])

        sample_size = min(50, len(border))
        border_sample = random.sample(list(border), sample_size)

        selected = []
        candidates = list(vertices)

        for _ in range(self.m):
            if not candidates:
                break
            if not selected:
                # Pick vertex with best min distance to border
                best = min(candidates, key=lambda c: min(
                    self.graph.euclidean_distance(c, b) for b in border_sample
                ))
            else:
                best = min(candidates, key=lambda c: max(
                    min(self.graph.euclidean_distance(c, b) for b in border_sample),
                    *[self.graph.euclidean_distance(c, s) for s in selected]
                ))
            selected.append(best)
            candidates.remove(best) if best in candidates else None

        return selected

    def _compute_sdls(self, node: SULNode):
        """Compute Subgraph Distance Lists for landmarks in this node."""
        vertices = node.get_vertices_in_range()
        if not vertices or not node.landmarks:
            node.sdls = []
            return

        # Clear existing sdls before computing (avoids double-computation on rebuild)
        node.sdls = []
        node.min_dist = []
        node.max_dist = []

        for landmark in node.landmarks:
            # Dijkstra from landmark
            dist = self.graph.dijkstra(landmark)
            # Extract distances for vertices in this subgraph
            sdl = [dist[v] if v < len(dist) else float('inf') for v in vertices]
            node.sdls.append(sdl)

            # Compute min/max
            valid_dists = [d for d in sdl if d < float('inf')]
            if valid_dists:
                node.min_dist.append(min(valid_dists))
                node.max_dist.append(max(valid_dists))
            else:
                node.min_dist.append(0.0)
                node.max_dist.append(0.0)

    def get_sdl(self, node: SULNode, landmark_idx: int) -> List[float]:
        """Get SDL for a landmark in a node."""
        if landmark_idx < len(node.sdls):
            return node.sdls[landmark_idx]
        return []

    def get_sdl_size(self, node: SULNode) -> int:
        """Get number of vertices in a node's SDL (same for all landmarks)."""
        return node.sdl_size

    def get_vertex_from_sdl_index(self, node: SULNode, sdl_idx: int) -> int:
        """Map SDL index to vertex ID."""
        if node.vertex_range:
            return node.vertex_range.start + sdl_idx
        return sdl_idx

    def compute_lb(self, q: int, node: SULNode) -> float:
        """
        Compute lower bound distance from query vertex q to a SUL-Tree node.
        Uses landmark lower bounds via triangle inequality.
        LB_li(q, p) = |d(li, q) - d(li, p)| <= d(q, p)
        LB_max(q, node) = max over landmarks of LB_li
        """
        if not node.landmarks:
            return 0.0

        # For non-leaf nodes, use min/max distances
        # LB(q, node) = max_i max(0, d(li, q) - M+_i, M-_i - d(li, q))
        # where M+_i = max distance from landmark i to any vertex in node
        # M-_i = min distance from landmark i to any vertex in node

        # Get distances from root landmarks to q
        lb_values = []
        for li_idx, landmark in enumerate(node.landmarks):
            if li_idx >= len(node.max_dist) or li_idx >= len(node.min_dist):
                continue
            d_li_q = self._get_distance_from_landmark(landmark, q)
            M_plus = node.max_dist[li_idx] if li_idx < len(node.max_dist) else float('inf')
            M_minus = node.min_dist[li_idx] if li_idx < len(node.min_dist) else 0.0

            if d_li_q >= M_plus:
                lb = d_li_q - M_plus
            elif d_li_q <= M_minus:
                lb = M_minus - d_li_q
            else:
                lb = 0.0
            lb_values.append(lb)

        return max(lb_values) if lb_values else 0.0

    def compute_ub(self, q: int, node: SULNode) -> float:
        """
        Compute upper bound distance from query vertex q to a SUL-Tree node.
        UB_min(q, node) = min_i (d(li, q) + M+_i)
        """
        if not node.landmarks:
            return float('inf')

        ub_values = []
        for li_idx, landmark in enumerate(node.landmarks):
            if li_idx >= len(node.max_dist):
                continue
            d_li_q = self._get_distance_from_landmark(landmark, q)
            M_plus = node.max_dist[li_idx]
            ub_values.append(d_li_q + M_plus)

        return min(ub_values) if ub_values else float('inf')

    def _get_distance_from_landmark(self, landmark: int, target: int) -> float:
        """
        Get distance from landmark to target using precomputed SDLs.
        Uses the root's SDLs (which contain ALL vertices) for root landmarks.
        """
        # Root landmarks: use root's SDL
        for li_idx, lm in enumerate(self.root.landmarks):
            if lm == landmark:
                if li_idx < len(self.root.sdls):
                    sdl = self.root.sdls[li_idx]
                    if 0 <= target < len(sdl):
                        return sdl[target]
        return float('inf')

    def _find_node_containing(self, node: SULNode, vertex: int) -> Optional[SULNode]:
        """Find the leaf node containing a given vertex."""
        if node.is_leaf:
            if node.vertex_range and node.vertex_range.contains(vertex):
                return node
            return None
        for child in node.children:
            if child.vertex_range and child.vertex_range.contains(vertex):
                return self._find_node_containing(child, vertex)
        return None

    def get_sdl_dist(self, node: SULNode, landmark: int, vertex: int) -> float:
        """Get distance from landmark to vertex from node's SDL."""
        if node.is_leaf and node.vertex_range:
            idx = vertex - node.vertex_range.start
            if 0 <= idx < node.sdl_size:
                for li_idx, lm in enumerate(node.landmarks):
                    if lm == landmark and li_idx < len(node.sdls):
                        return node.sdls[li_idx][idx]
        return float('inf')
