# Evaluation Plan

## Dataset

- **Original paper setting**: large US road networks with real POI categories such as schools, parks, hospitals, hotels, and public services.
- **Shipped benchmark setting**: a public US48 road graph under `data/downloads/`, with reproducible POI subsets sampled from graph vertices.
- **Query vertices**: sampled from the road network and stored in method output artifacts.

## Metrics

### Correctness

Returned results are checked against exact brute-force answers on the shipped graph. Top-k ties at the kth boundary may be returned in any order or subset.

- `accuracy`: fraction of evaluated queries that return an exact valid answer. Higher is better.

### Candidate Efficiency

These metrics measure how much work a submitted method leaves for exact verification.

- `candidates_ratio`: average fraction of POIs examined as candidates. Lower is better.
- `candidate_p90_ratio`: 90th-percentile candidate fraction, used to catch methods that only improve easy queries. Lower is better.
- `candidate_max_ratio`: worst per-query candidate fraction. Lower is better.
- `lookup_reduction_vs_brute`: exact-distance lookup reduction relative to checking every POI. Higher is better.

### Preprocessing Diagnostics

Build-time fields are reported for context but have zero score weight because wall-clock timing depends on hardware and implementation language.

- `sul_time_s`: legacy field name for first-stage preprocessing time.
- `col_time_s`: legacy field name for object-index preprocessing time.

These fields are retained for compatibility with the score schema. They are not optimization targets.

## Protocol

1. Build any method-specific preprocessing structures before answering queries.
2. Run AkNN, kFN, and range-query configurations on the shipped graph and POI sets.
3. Write JSON result artifacts containing query type, number of objects, correctness counts, candidate counts, and exact lookup counts.
4. Run `scripts/evaluate.sh <results_path>` to convert artifacts into `scoring/scores.json`.
5. Optional train/test scoring uses `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh`, which score deterministic slices of the same output artifacts.

## Experiment Targets

| Experiment | Required behavior | Efficiency target |
|---|---|---|
| `kfn_real_pois` | Exact k farthest-neighbor results | Reduce exact lookup and candidate fractions versus brute force |
| `aknn_real_pois` | Exact aggregate nearest-neighbor results | Examine only a fraction of the object set |
| `range_real_pois` | Exact set of in-range objects | Examine only a fraction of the object set |
| `preprocessing` | Report index/preprocessing overhead | Diagnostic only, zero score weight |

## Correctness Rules

- A method must use the same graph, POI set, query definitions, and distance metric as the benchmark.
- Exact brute force is the correctness oracle.
- Methods that trade away correctness for pruning receive lower scores through the `accuracy` metric.
