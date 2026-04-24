# Design Notes — Train/Test Evaluation (Iteration 8, Stage 2)

## Status: Complete

## What I checked

- Both `evaluate_train.sh` / `evaluate_test.sh` scripts: correct eval path, correct output file, no hardcoded method name, method discovery from `scores_train.json` keys.
- Cross-imports between `eval/train/` and `eval/test/`: none (independent, only `SLICE_PARITY` constant differs).
- Top-level `eval/evaluate.py` (off-limits): does not leak test-specific metric/data shape into shared code.
- All metrics in `reference.json` with nonzero `coefficient`: no paper-agreement patterns, all have `higher_is_better`, `coefficient`, and `description`.
- `scores_train.json` / `scores_test.json` exist with real values (from prior run) — not stubs.
- Validator: all checks pass.

## What I changed

### 1. Added p50/p10 latency percentiles (primary improvement)

The first pass only computed p90 (tail latency). A shortcut method could optimize the worst-case query to look good on p90 while degrading median or fast-quartile performance. I added:

- **p50_query_time_ms** (coefficient -0.2): median latency. Catches methods that improve p90 at the cost of typical-case latency — the most robust new signal since it spans the full distribution.
- **p10_query_time_ms** (coefficient -0.15): 10th-percentile latency. Catches methods that cherry-pick fast queries while leaving median-latency queries slow.

These were added to all 4 query experiments (aknn_real_pois, aknn_sensitivity_density, kfn_real_pois, range_real_pois). Coefficients are modest relative to avg (-1.0) and p90 (-0.3) to avoid destabilizing the existing scoring function.

### 2. No other structural changes needed

The split style (odd/even query index partitioning of `individual_times`) is appropriate for this paper. The gaps are real (1.4%–14.0%), calibrated, and consistent with stochastic variation across query samples. The design is sound.

## Runtime concerns for Stage 3 (runner)

### AkNN eval set size (known limitation)

The AkNN experiment has only **5 individual query times** total (from the reproduction run), giving **3 train / 2 test** samples. This is small enough that p10 and p90 values can be noisy. The 3-sample train slice and 2-sample test slice each use only one or two values — the new percentile metrics (p50, p10) are less meaningful here than for kFN/range which have 50 individual times.

If a future agent re-runs AkNN experiments with more query samples, the split will become more robust automatically (as long as `individual_times` is preserved in the output).

### No runtime re-execution

Both evaluators slice pre-computed `individual_times` from saved JSON artifacts. `evaluate_test.sh` does **not** re-run the method. Lightweight and zero-effort for future agents.

### Method discovery edge case

The method discovery reads from `scores_train.json` if it exists, else from experiment result files. If a future agent deletes `scores_train.json` or never runs the train evaluator, discovery falls back to `experiment_results/*.json` (looking for a `method` key). The experiment result files don't have a `method` key — they only have query results. So in that edge case, discovery defaults to `["colt_phl"]`, silently skipping any new method variants. This is acceptable but worth noting: a future agent who wants all their variants scored must run `evaluate_train.sh` first.

## Score coverage

| Experiment | Train/test differ? | Primary signal |
|---|---|---|
| aknn_real_pois | Yes (1.4% avg) | avg, p90, speedup, new: p50 |
| aknn_sensitivity_density | Yes (same as above) | avg, p90, speedup, new: p50 |
| kfn_real_pois | Yes (2.9% avg) | avg, p90, speedup, new: p50, p10 |
| range_real_pois | Yes (12.1% avg) | avg, p90, speedup, new: p50, p10 |
| preprocessing | Nearly identical (precision rounding only) | Global, unavoidable |
