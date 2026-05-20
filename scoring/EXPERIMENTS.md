# Experiment Overview

## kfn_real_pois

Tests whether an indexed road-network POI method can answer exact k farthest-neighbor queries while examining only a fraction of the object set. This is the core-claim experiment used by `scripts/run.sh`.

The reproduced score row `colt_us48_repro` is the US48/synthetic-POI substitute setting, kept separate from the paper's original `colt_phl` DIMACS/OSM+PHL row in `reference.json`.

## aknn_real_pois

Optional extension for aggregate nearest-neighbor queries with multiple query vertices. It measures exactness and object-candidate reduction.

## range_real_pois

Optional extension for range reporting queries. It measures exactness and object-candidate reduction.

## preprocessing

Measures the overhead of building the road-network hierarchy and the POI-specific compact index before query processing.
