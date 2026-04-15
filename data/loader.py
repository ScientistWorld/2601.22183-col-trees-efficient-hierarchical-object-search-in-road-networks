"""
DIMACS-format road network loaders.
Supports MatrixMarket (.mtx), DIMACS (.gr), and Network Repository formats.
"""

from typing import List, Tuple
from data.graph import RoadNetwork


def load_mtx_network(filepath: str) -> RoadNetwork:
    """Load road network from MatrixMarket format (.mtx)."""
    gn = RoadNetwork()
    edges = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('%'):
                continue
            parts = line.split()
            if len(parts) == 3:
                # First non-comment line is the matrix header
                try:
                    n, _, m = int(parts[0]), int(parts[1]), int(parts[2])
                    gn.num_vertices = n
                    gn.adj = [[] for _ in range(n)]
                    gn.coords = [(0.0, 0.0) for _ in range(n)]
                except ValueError:
                    pass
            elif len(parts) == 2:
                u, v = int(parts[0]) - 1, int(parts[1]) - 1
                if 0 <= u < gn.num_vertices and 0 <= v < gn.num_vertices:
                    # Unweighted - use default edge weight of 1.0
                    # Since this is a pattern matrix, edges exist but no weights
                    edges.append((u, v, 1.0))

    # Build adjacency list (undirected)
    for u, v, w in edges:
        gn.adj[u].append((v, w))
        gn.adj[v].append((u, w))
        gn.num_edges += 2

    if gn.num_vertices == 0:
        gn.num_vertices = len(gn.adj)
    return gn


def load_dimacs_network(filepath: str) -> RoadNetwork:
    """Load road network from DIMACS .gr format."""
    return RoadNetwork.from_dimacs(filepath)


def load_network_repository_network(filepath: str) -> RoadNetwork:
    """Load road network from Network Repository format (roadNet-XX.txt)."""
    gn = RoadNetwork()
    edges = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                u, v = int(parts[0]), int(parts[1])
                u -= 1  # 1-indexed to 0-indexed
                v -= 1
                w = 1.0  # default weight
                if len(parts) >= 3:
                    try:
                        w = float(parts[2])
                    except ValueError:
                        pass
                edges.append((u, v, w))

    if edges:
        max_vertex = max(max(u, v) for u, v, _ in edges)
        gn.num_vertices = max_vertex + 1
        gn.adj = [[] for _ in range(gn.num_vertices)]
        gn.coords = [(0.0, 0.0) for _ in range(gn.num_vertices)]

        for u, v, w in edges:
            if u < gn.num_vertices and v < gn.num_vertices:
                gn.adj[u].append((v, w))
                gn.adj[v].append((u, w))
                gn.num_edges += 2

    return gn


def load_network(filepath: str) -> RoadNetwork:
    """Auto-detect format and load road network."""
    if filepath.endswith('.mtx'):
        return load_mtx_network(filepath)
    elif filepath.endswith('.gr') or filepath.endswith('.gr.gz'):
        return load_dimacs_network(filepath)
    else:
        # Try network repository format
        return load_network_repository_network(filepath)


# Get available networks
def get_available_networks() -> dict:
    """Return info about available road networks in data/downloads/ directory."""
    return {
        'usroads-48': {
            'file': 'downloads/road-usroads-48.mtx',
            'format': 'mtx',
            'description': 'US road network (48 states), 126K vertices, 162K edges',
            'vertices': 126146,
            'edges': 161950,
        },
        'roadnet-pa': {
            'file': 'downloads/roadNet-PA.txt',
            'format': 'network-repository',
            'description': 'Pennsylvania road network, 1.09M vertices, 3.08M edges',
            'vertices': 1088092,
            'edges': 3083796,
        },
    }
