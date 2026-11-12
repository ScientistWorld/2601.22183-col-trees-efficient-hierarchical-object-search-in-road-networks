# Progress

## What Works

- Paper analysis and briefing files are in place for the COL-Tree/SUL-Tree road-network POI search paper.
- Data download script provides the US48 road graph and Pennsylvania road graph fallback.
- SUL-Tree now builds graph-aware recursive partitions and computes local per-node landmark SDLs.
- COL-Tree now builds POI-specific internal min/max landmark bounds and leaf ODLs.
- kFN, AkNN, and range query entry points run on a small local smoke graph and match exact results when ties are handled correctly.
- `scripts/run.sh` submits the core kFN reproduction and calls `scripts/evaluate.sh` to refresh `scoring/scores.json`.
- kFN leaf processing now advances on every revisited COL leaf, avoiding a stale requeue state after initialization.
- `environment/container.def` no longer tries to copy gitignored download artifacts into the container; data is prepared by `scripts/download.sh` in the bind-mounted workspace.
- Baseline helpers used by the experiment harness now live under `baseline/`; `method/` contains the COL/SUL implementation and experiment driver.

## Results Achieved

- Current milestone is temporarily reset to `method_runs` while a fresh CPU job regenerates artifacts after paper-alignment and evaluator-integrity fixes.
- Previous artifacts reached `secondary_claims`, but a sub-agent audit found they were not acceptable as final evidence because `scripts/run.sh` scored stale JSON and COL query bounds used exact full-graph local-landmark distances instead of the paper's root/LCA-style bound substitution.
- CPU job `90b0e53b-aab` ran the revised COL/SUL kFN implementation on US48 at object density 0.05 with 6,307 objects and 12 queries.
- Reproduced score: `accuracy=1.0`, `candidates_ratio=0.165015`, `lookup_reduction_vs_brute=6.060053`, `sul_time_s=23.6116`, `col_time_s=1.0631`.
- The result is weaker than the paper's reported `candidates_ratio=0.01` and `lookup_reduction_vs_brute=100`, but it supports the core claim at reduced scale: exact kFN answers while verifying a fraction of the object set.
- CPU job `e203f389-121` expanded kFN to densities 0.05 and 0.10 with 24/24 exact queries. Averaged scoring is `accuracy=1.0`, `candidates_ratio=0.156648`, `lookup_reduction_vs_brute=6.402002`.
- CPU job `26aa2eab-2d1` added AkNN and range runs. AkNN reached `accuracy=1.0` with `candidates_ratio=0.166640`; range reached `accuracy=1.0` but scanned all objects with `candidates_ratio=1.0`, so it does not yet support the secondary efficiency claim.
- CPU job `d266aebb-8f5` reran secondary queries after range ODL pruning. Final scores are kFN `accuracy=1.0`, `candidates_ratio=0.156648`, `lookup_reduction_vs_brute=6.402002`; AkNN `accuracy=1.0`, `candidates_ratio=0.166640`; range `accuracy=1.0`, `candidates_ratio=0.084351`; preprocessing `sul_time_s=19.5664`, `col_time_s=0.4934`.
- On 2026-05-20 02:21, the evaluator was tightened to report the p90 and max per-query candidate-ratio constraint metrics already defined in `reference.json`. The refreshed scores add kFN `candidate_p90_ratio=0.241636`, `candidate_max_ratio=0.302323`; AkNN `candidate_p90_ratio=0.204693`, `candidate_max_ratio=0.245917`; and range `candidate_p90_ratio=0.093705`, `candidate_max_ratio=0.100365`.
- `python validate.py --compare` passes after the evaluator refresh, including train/test score independence checks.
- Scores are reported under `colt_us48_repro` because this is a documented US48/synthetic-POI substitute. The paper's `colt_phl` reference row remains reserved for the original DIMACS/OSM+PHL setting; `reference.json` also includes `colt_us48_repro` rows as the fixed target for validating this shipped replacement benchmark.
- On 2026-05-20 02:27, `python3 -m py_compile baseline/bruteforce.py method/experiment.py eval/evaluate.py`, `bash scripts/evaluate.sh /home/user/experiment_results/core_claim`, and `python3 validate.py --compare` all passed after moving baseline helpers out of `method/`.
- On 2026-05-20 02:32, bytecode checks and a tiny local graph smoke test passed after correcting SUL/COL distance storage and kFN candidate scheduling. Fresh benchmark scores are pending the submitted CPU job.
- On 2026-05-20 02:35, final verification confirmed the current saved artifacts are stale under the stricter evaluator: `scripts/evaluate.sh /home/user/experiment_results/core_claim` fails until the prepared CPU job regenerates artifacts with `queries.per_query`.
- CPU job `714f3f12-b67` completed the post-audit regeneration successfully. Fresh scores are kFN `accuracy=1.0`, `candidates_ratio=0.147928`, `candidate_p90_ratio=0.229903`, `candidate_max_ratio=0.286785`, `lookup_reduction_vs_brute=6.778398`; AkNN `accuracy=1.0`, `candidates_ratio=0.166640`; range `accuracy=1.0`, `candidates_ratio=0.039374`.
- The regenerated train/test slices also pass validation: kFN train/test candidate ratios are `0.133463`/`0.162392`, AkNN `0.147614`/`0.204693`, and range `0.038000`/`0.040748`.
- An earlier resubmission did not reach the job stage because the container build attempted to copy `data/downloads/road-usroads-48.mtx`, which is not present in a fresh build checkout. The packaging issue was fixed before job `90b0e53b-aab`.

## Iteration 11 (hardening): benchmark rebuilt on the paper's own data with an evaluator-owned protocol

Why: the iteration-10 red-team audit (`REDTEAM.md`) showed the old US48 benchmark scored method-written self-reports. Fabricated or failing submissions could outrank the reference, the graph was unit-weight, and the workload was tiny.

- **Data**: the paper's own Zenodo dataset (doi:10.5281/zenodo.18026780), NW subset: 1,089,933 vertices, travel-time edges and the 8 real OSM POI categories (`scripts/download.sh` → `data/downloads/nw/`, md5-verified).
- **Protocol**: a method is `experiment_results/<name>/submission.json`, naming a solver command and a hierarchical landmark structure per query type.
  - The evaluator computes the landmark distance lists and all exact distances on its own network, answers the solver's requests over JSON lines, counts revealed objects and distance computations, and checks every answer.
  - Any failure (invalid or over-budget structure, crash, timeout, a single inexact answer) gives the worst value of every metric.
- **Settings**:
  - `eval/evaluate.py` → `scores.json`: the paper setting, with original travel times and real POIs as published.
  - `eval/train/evaluate.py` → `scores_train.json`: public perturbation and jittered or uniform object sets.
  - `eval/test/evaluate.py` → `scores_test.json`: hidden perturbation, objects and queries.
- **Method** (`method/build.py`, `method/solver.py`): SUL-Tree builder (recursive balanced partition, 16 ALT root landmarks plus m local landmarks per node, with Random, Slice, Minmax and Furthest-Border policies) and the COL-Tree query algorithms (Algorithms 1–3) over the evaluator's free node summaries and object distance lists.
  - `colt` uses the paper's Table 8 per-query parameters.
  - `colt_default` uses b=8, m=2, Random for every query type.
- **Baselines** (`baseline/`): `alt_filter` (the paper's AUB-PHL / ALT multi-step filter) and `bruteforce`.
- **Job `9fc1dbc3-96c`** (held-out split, colt_default config vs alt_filter): everything was exact.
  - log10 candidate reduction: kFN 1.37, AkNN 1.05, range 1.64 (COLT) vs 0 (alt_filter).
  - log10 call reduction is about equal for the two methods (kFN 1.94 vs 1.94).
  - Index: 24 entries per vertex for COLT vs 16 for alt_filter; construction work 140 vs 16 settled vertices per vertex.
- **Local smoke test** on a 3,000-vertex synthetic grid (`COLT_DATA_DIR` override): all three evaluators and all four submissions run end to end, and every method is exact.
- **Removed** the superseded US48 pipeline: `method/{col_tree,sul_tree,experiment,graph}.py`, `data/{loader,graph}.py`, the old result artifacts and score files. They remain in git history.
- `environment/setup.sh` installs numpy and scipy, which the evaluator and builder need at full scale.
- **Pending**: the first full paper/train/test job. `reference.json` rows for colt, colt_default, alt_filter and bruteforce are preliminary until it finishes.

## Deviations From Paper

- Network: the paper's NW subset (1.09M vertices) of its own continental-US dataset (24M vertices), so a full-scale run fits in a single-CPU job. Object sets are the same 8 real POI categories for that region, and the uniform densities follow the paper's Table 4.
- Partitioner: recursive balanced coordinate bisection instead of METIS. The paper allows any partitioner that produces similar-sized subgraphs.
- Distance oracle: the evaluator answers exact distances with Dijkstra in place of PHL. The scores are the paper's machine-independent heuristic-efficiency metrics (candidates retrieved, network distances computed), not wall-clock time.
- Train and held-out splits perturb the published travel times so that results cannot be precomputed. The paper setting (`scores.json`) uses the original travel times.

## What Remains

- Higher milestones would require broader coverage of the paper's full experimental tables and the original DIMACS/OSM POI setup. This workspace instead provides a reusable, smaller US48 benchmark with the paper's core and secondary query mechanisms exercised.

## Issues Encountered

- The inherited implementation used root landmarks for every SUL node, which was not faithful to the paper.
- Internal COL nodes previously lacked object-specific min/max landmark distances, weakening or breaking pruning.
- Correctness checks previously compared sets directly, which falsely rejected valid top-k ties. The experiment code now accepts any exact tied top-k result.
- kFN leaf nodes were previously only advanced on their first priority-queue visit; that control-flow bug is fixed before the next core run.
- The container definition previously baked workspace files, including gitignored downloads, into the image despite the workspace being bind-mounted at runtime. This caused the build failure and has been removed.
- Range leaf processing scanned the full ODL even when the landmark triangle lower bound excluded most objects. It now restricts exact checks to the feasible sorted-distance window.
- A later audit found the evaluator trusted method-reported aggregate correctness and train/test silently fell back to aggregate fields. The method now emits per-query outputs, main eval recomputes correctness independently, and train/test require per-query correctness and exact lookup counts.
- Final verification initially found stale pre-audit artifacts. The follow-up CPU regeneration job fixed this, and the workspace is signed off at `secondary_claims`.
