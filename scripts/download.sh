#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script is idempotent and fetches all pre-existing artifacts from
# public sources so compute nodes can run without network access.
#
# Estimated total download size: ~20 MB
# Estimated disk usage after extraction: ~30 MB
#
# Data sources:
# 1. US48 road network: MatrixMarket format from UF Sparse Matrix Collection
#    (Gleich/usroads-48), ~1.9 MB
# 2. Pennsylvania road network: Network Repository format
#    ~10 MB compressed

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

DATA_DIR="$ROOT_DIR/data/downloads"
mkdir -p "$DATA_DIR"

echo "=== COL-Tree Data Download ==="

if [ ! -f "$DATA_DIR/road-usroads-48.mtx" ]; then
    echo "Downloading US48 road network (MatrixMarket format)..."
    if [ ! -f "$DATA_DIR/usroads-48.tar.gz" ]; then
        wget -O "$DATA_DIR/usroads-48.tar.gz" \
            "http://sparse-files.engr.tamu.edu/MM/Gleich/usroads-48.tar.gz"
    fi
    tar -xzf "$DATA_DIR/usroads-48.tar.gz" -C "$DATA_DIR" \
        "usroads-48/usroads-48.mtx"
    mv "$DATA_DIR/usroads-48/usroads-48.mtx" \
        "$DATA_DIR/road-usroads-48.mtx"
    rmdir "$DATA_DIR/usroads-48"
fi

if [ ! -f "$DATA_DIR/roadNet-PA.txt" ]; then
    echo "Downloading Pennsylvania road network..."
    if [ ! -f "$DATA_DIR/roadNet-PA.txt.gz" ]; then
        wget -O "$DATA_DIR/roadNet-PA.txt.gz" \
            "https://snap.stanford.edu/data/roadNet-PA.txt.gz"
    fi
    gzip -dc "$DATA_DIR/roadNet-PA.txt.gz" > "$DATA_DIR/roadNet-PA.txt"
fi

echo "=== Download complete ==="
echo "Available networks:"
ls -lh "$DATA_DIR"/*.mtx "$DATA_DIR"/*.txt 2>/dev/null || echo "No files found"
