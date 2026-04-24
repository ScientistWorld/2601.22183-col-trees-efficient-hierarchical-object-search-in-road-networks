#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script is idempotent and first reuses workspace-local copies so
# compute nodes can run without network access.
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

cd "$(dirname "$0")/.."

ROOT_DATA_DIR="/home/user/data"
DATA_DIR="$ROOT_DATA_DIR/downloads"
mkdir -p "$DATA_DIR"

echo "=== COL-Tree Data Download ==="

if [ ! -f "$DATA_DIR/road-usroads-48.mtx" ]; then
    if [ -f "$ROOT_DATA_DIR/road-usroads-48.mtx" ]; then
        echo "Reusing workspace copy of US48 road network..."
        cp "$ROOT_DATA_DIR/road-usroads-48.mtx" "$DATA_DIR/road-usroads-48.mtx"
    else
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
fi

if [ ! -f "$DATA_DIR/roadNet-PA.txt" ]; then
    if [ -f "$ROOT_DATA_DIR/roadNet-PA.txt.gz" ]; then
        echo "Decompressing workspace copy of Pennsylvania road network..."
        gzip -dc "$ROOT_DATA_DIR/roadNet-PA.txt.gz" > "$DATA_DIR/roadNet-PA.txt"
    else
        echo "Downloading Pennsylvania road network..."
        if [ ! -f "$DATA_DIR/roadNet-PA.txt.gz" ]; then
            wget -O "$DATA_DIR/roadNet-PA.txt.gz" \
                "https://snap.stanford.edu/data/roadNet-PA.txt.gz"
        fi
        gzip -dc "$DATA_DIR/roadNet-PA.txt.gz" > "$DATA_DIR/roadNet-PA.txt"
    fi
fi

echo "=== Download complete ==="
echo "Available networks:"
ls -lh "$DATA_DIR"/*.mtx "$DATA_DIR"/*.txt 2>/dev/null || echo "No files found"
