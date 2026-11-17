# Evaluation Targets

Three experiments, one per query type: `kfn`, `aknn`, `range`. Every one is
scored on the same five metrics, in three settings:

- `scoring/scores.json`: the paper's own setting (original NW travel times, real POI categories).
- `scoring/scores_train.json`: the public development split.
- `scoring/scores_test.json`: the held-out split (three hidden travel-time conditions, hidden object sets and queries).

Object sets are real POI categories (50 to 5,000 objects) and uniform samples at d = 0.001, 0.01 and 0.1
(up to 109,000 objects). On train and test, kFN and AkNN are also queried from map-spread sources, and kFN
also has regional object sets (uniform objects inside a network region). The paper's effects, fewer objects
touched and fewer exact distances than landmark filtering of every object, grow with density.

## Benefit: avoid touching objects individually (primary)

- **Metric**: `log10_candidate_reduction` (higher is better). The mean over queries of log10((|P|+1)/(candidates+1)).
  Candidates are the objects revealed individually plus the non-empty index nodes the method accessed, so
  descending the index is not free.
  A value of 0 means every object was retrieved, as any method that scans the object set does.

## Benefit: avoid exact network-distance computations

- **Metric**: `log10_call_reduction` (higher is better). The mean over queries of log10((|Q||P|+1)/(distance computations+1)).

## Constraint: exact answers

- **Metric**: `exact_answer_rate` (must be 1.0). One wrong answer, crash, timeout or protocol
  violation scores the method with the worst value of every metric in every experiment.

## Constraint: index size

- **Metric**: `index_entries_per_vertex` (lower is better). Hard caps: 40 for kFN, 24 for AkNN and range.
  These caps equal 16 ALT landmarks plus the paper's tuned hierarchy for that query type.
  A larger index is rejected, which counts as a failure.

## Constraint: index construction cost

- **Metric**: `sdl_work_per_vertex` (lower is better). Hard caps: 3,000 settled vertices per vertex for kFN and
  600 for AkNN and range.
