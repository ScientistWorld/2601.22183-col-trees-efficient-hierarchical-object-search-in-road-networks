#!/bin/bash
# Download all data needed by this environment (run on a node WITH internet,
# before submitting compute jobs; compute nodes are offline).
#
# Source: the paper's own public dataset (Abeywickrama, "USA Road Network Graph
# and Points-of-Interest Dataset", Zenodo, doi:10.5281/zenodo.18026780). It is
# the 9th DIMACS Challenge travel-time road network (largest connected
# component), per-vertex coordinates, and real OpenStreetMap POI categories
# mapped to road-network vertices. We use its North-West US subset:
#   NW-t.graph        1,089,933 vertices, 2,545,844 arcs (1,272,922 undirected edges)
#   NW-t.coordinates  lon/lat (x1e6) per vertex
#   pois/*.txt        8 real POI categories (school, park, fast_food, ...)
#
# Download size: ~635 MB (one tar.gz, deleted after extraction).
# Disk usage after extraction: ~80 MB under data/downloads/nw/.
#
# Idempotent: does nothing when the extracted files are already present and
# their checksums match.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/downloads/nw"
URL="https://zenodo.org/api/records/18026780/files/USA_road_network_and_poi.tar.gz/content"
TARBALL="$ROOT_DIR/data/downloads/USA_road_network_and_poi.tar.gz"

mkdir -p "$DATA_DIR/pois"

verify() {
    ( cd "$DATA_DIR" && md5sum -c --quiet - <<'EOF'
eab3d22c46e314fd4e7040cc785d7184  NW-t.graph
f4eea52619bb21f5cbf2d95b8b98ded4  NW-t.coordinates
eab4f01f932eab174215f9691a131f05  pois/courthouse.txt
4fc5beb7cf24ebde6555761311cb2dc3  pois/fast_food.txt
43c49ae17a895b81b5c1864c66075eaf  pois/hospital.txt
f3438ee4d68099167b8784e4d914b0d1  pois/hotel.txt
2f7ae85c38f778ba20aaaad66d72e9b2  pois/park.txt
602d68a8b3233df4e03c66a241dfad31  pois/post_office.txt
e8e974845fbe97f8b3fe4e36508154ee  pois/school.txt
c6f3f6d1794f3479e9c5d35d210269b9  pois/university.txt
EOF
    ) >/dev/null 2>&1
}

if verify; then
    echo "NW road network and POIs already present: $DATA_DIR"
    exit 0
fi

echo "Downloading the paper's road network + POI dataset from Zenodo (~635 MB)..."
wget -q --show-progress -O "$TARBALL" "$URL"

TMP_DIR="$(mktemp -d "$ROOT_DIR/data/downloads/extract.XXXXXX")"
tar -xzf "$TARBALL" -C "$TMP_DIR" data/NW-t.graph data/NW-t.coordinates real_world_pois/NW
mv "$TMP_DIR/data/NW-t.graph" "$TMP_DIR/data/NW-t.coordinates" "$DATA_DIR/"
cp "$TMP_DIR"/real_world_pois/NW/*.txt "$DATA_DIR/pois/"
rm -rf "$TMP_DIR" "$TARBALL"

if ! verify; then
    echo "Checksum verification failed for $DATA_DIR" >&2
    exit 1
fi
echo "=== Download complete ==="
ls -lh "$DATA_DIR" "$DATA_DIR/pois"
