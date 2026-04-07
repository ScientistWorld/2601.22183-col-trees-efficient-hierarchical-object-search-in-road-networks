# Experiment Overview

## aknn_real_pois
Tests whether the method efficiently answers Aggregate k Nearest Neighbor queries (finding k POIs minimizing aggregate distance to a set of query vertices) on a real road network with POI objects. Measures query time as the primary metric.

## aknn_sensitivity_density
Tests how query time scales with object density (the fraction of network vertices that are POIs). Higher density increases the number of objects to consider, which should stress the index's pruning ability.

## kfn_real_pois
Tests whether the method efficiently answers k Farthest Neighbor queries (finding k POIs that maximize the minimum distance to the query vertex) on a real road network. This query type is asymmetrically hard — baseline methods cannot use incremental nearest-neighbor techniques.

## range_real_pois
Tests whether the method efficiently answers range queries (finding all POIs within a given network distance from the query vertex) on a real road network. Measures query time as the primary metric.

## preprocessing
Tests the computational cost of building the spatial index before any queries can be answered. Includes construction time for both the hierarchical network partition (SUL-Tree) and the POI-specific compact index (COL-Tree).
