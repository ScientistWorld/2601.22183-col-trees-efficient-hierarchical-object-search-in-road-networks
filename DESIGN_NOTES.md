# Design Notes

Checked the train/test evaluation split, both evaluate scripts, the scoring schema, existing result artifact shape, and the paper context available at `paper/2601.22183.md`.

Changes made:
- Added `candidate_p90_ratio` and `candidate_max_ratio` to both `eval/train/evaluate.py` and `eval/test/evaluate.py`. These are computed on the same parity split as `candidates_ratio`, so a method that only optimizes mean candidate retrieval on visible queries is more likely to regress on held-out tail queries.
- Added the new tail-pruning metrics to `scoring/reference.json` for `kfn_real_pois`, `aknn_real_pois`, and `range_real_pois`.
- Reweighted experiments from `0.40/0.25/0.25/0.10` to `0.49/0.25/0.25/0.01`, moving nearly all score weight away from preprocessing wall-clock seconds and onto the core kFN pruning claim while keeping the schema validator's positive-weight requirement satisfied.
- Set preprocessing time metric coefficients to `0.0` and marked them diagnostic because wall-clock build time is hardware-dependent. The values are still emitted for runner visibility, but they no longer drive ranking.

Checks:
- `scripts/evaluate_train.sh` points at `eval/train/evaluate.py` and writes `scoring/scores_train.json`.
- `scripts/evaluate_test.sh` points at `eval/test/evaluate.py` and writes `scoring/scores_test.json`.
- Both scripts discover method result artifacts from disk rather than using a hardcoded method default.
- No train/test cross-imports were found.
- No paper-agreement metrics were found in `scoring/reference.json`.
- `bash -n scripts/evaluate_train.sh` and `bash -n scripts/evaluate_test.sh` passed.
- `scoring/scores_train.json` and `scoring/scores_test.json` do not exist.

Runtime concerns for the next iteration:
- Correctness is still split only when artifacts include per-query correctness fields such as `individual_correct`, `correct_flags`, or `is_correct`. Current method artifacts include per-query candidate counts and times, but only aggregate correctness, so train/test accuracy may remain identical even when candidate-pruning metrics diverge. The runner should consider extending method artifacts in a later implementation iteration to record per-query correctness.
- If a future method emits only aggregate candidate averages and omits `individual_candidates`, the new p90/max metrics fall back to the average and lose anti-shortcut power. The evaluator remains compatible, but per-query candidate arrays should be treated as the expected artifact format.
- The legacy top-level `eval/evaluate.py` still exists and writes `scoring/scores.json`; it was outside this iteration's edit scope. The split scripts are correct, but future documentation should keep agents pointed at `scripts/evaluate_train.sh` and the held-out runner at `scripts/evaluate_test.sh`.

Stage 3 run notes:
- First scoring run discovered `experiment_results/core_claim/` as a method directory. The split shell wrappers now prefer top-level JSON artifacts when present and use the method IDs already present in `scoring/scores.json`, so the final train/test rows are keyed as `colt_us48_repro`.
- Final CPU scoring job `5bc82c35-b51` completed successfully. Both split score files contain 15 real metric values for `colt_us48_repro`, with no missing or extra metrics relative to `scoring/reference.json`.
- Candidate-pruning metrics differ across train/test: AkNN mean candidate ratio is 0.4261 train vs 0.3717 test, kFN is 0.2663 vs 0.3448, and range is 0.6738 vs 0.5885. Accuracy remains 1.0 on both slices because the available artifacts expose aggregate correctness, not per-query correctness flags.
- Range-query `candidate_p90_ratio` and `candidate_max_ratio` saturate at 1.0 on both slices because some hard range queries scan all objects. They remain emitted for diagnostics, but their reference coefficients are set to 0.0 so the ranking is driven by non-saturated mean candidate ratio plus correctness.
