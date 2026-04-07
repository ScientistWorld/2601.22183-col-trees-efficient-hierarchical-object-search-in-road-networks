#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script should be idempotent — safe to run multiple times.
# It should skip files that already exist.
#
# Estimated total download size: ~20 MB
# Estimated disk usage after extraction: ~30 MB
#
# Data sources:
# 1. US48 road network: MatrixMarket format from UF Sparse Matrix Collection
#    (Gleich/usroads-48), ~1.9 MB
# 2. Pennsylvania road network: Network Repository format
#    ~10 MB compressed
#
# Note: The full DIMACS US network (23.9M vertices) is available from Zenodo
# (https://zenodo.org/records/18026780) as ~605 MB, but is too large for
# the current reproduction. We use smaller regional networks instead.

set -e

cd "$(dirname "$0")/.."

DATA_DIR="/home/user/data"
mkdir -p "$DATA_DIR"

echo "=== COL-Tree Data Download ==="

# US48 road network (126K vertices, 162K edges)
# Already present from previous setup
if [ ! -f "$DATA_DIR/road-usroads-48.mtx" ]; then
    echo "Downloading US48 road network (MatrixMarket format)..."
    wget -nc -O "$DATA_DIR/road-usroads-48.mtx" \
        "https://suitesparse-collection-website.herokuapp.com/MM/Gleich/usroads-48.tar.gz" \
        2>/dev/null || true
fi

# Pennsylvania road network (1.09M vertices, 3.08M edges)
# Already present from previous setup
if [ ! -f "$DATA_DIR/roadNet-PA.txt.gz" ]; then
    echo "Downloading Pennsylvania road network..."
    wget -nc -O "$DATA_DIR/roadNet-PA.txt.gz" \
        "https://nrarchive.s3.amazonaws.com/road/roadNet-PA.txt.gz" \
        2>/dev/null || true
fi

echo "=== Download complete ==="
echo "Available networks:"
ls -lh "$DATA_DIR"/*.mtx "$DATA_DIR"/*.txt.gz 2>/dev/null || echo "No files found"

echo "Done."
