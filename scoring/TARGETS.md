# Evaluation Targets

## Primary: query_time
Average query time (ms) per query across AkNN, kFN, and range query types on a road network.
- **Metric**: avg_query_time_ms (lower is better)

## Constraint: correctness
All query results must match the exact ground truth computed by brute force.
- **Metric**: accuracy (1.0 = 100% correct, lower means incorrect results)
- **Baseline comparison**: Result sets must be identical to brute-force for all queries.

## Constraint: preprocessing
Index construction time must remain reasonable relative to query savings.
- **Metric**: sul_time_s + col_time_s (lower is better, relative to query time savings)

## Ablation: vs_no_landmarks
Removing landmark precomputation should degrade query time significantly, proving landmarks contribute to pruning.
- **Metric**: query_time_degradation_ratio (higher is better — queries without landmarks should be slower)
