# Experiment Overview

## kfn_real_pois

Tests whether an indexed road-network POI method can answer exact k farthest-neighbor queries while examining only a fraction of the object set. This is the core-claim experiment used by `scripts/run.sh`.

## aknn_real_pois

Optional extension for aggregate nearest-neighbor queries with multiple query vertices. It measures exactness and object-candidate reduction.

## range_real_pois

Optional extension for range reporting queries. It measures exactness and object-candidate reduction.

## preprocessing

Measures the overhead of building the road-network hierarchy and the POI-specific compact index before query processing.

