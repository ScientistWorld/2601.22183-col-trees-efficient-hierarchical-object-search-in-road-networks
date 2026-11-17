# Hardening report (final iteration)

**Better results score higher, worse ones lower, and a random root-landmark redraw no longer pays.**

`REVIEW.md` reported that re-drawing the 16 random ALT root landmarks gained more on the hidden test than
the best honest variant: +0.069 rank against +0.061, with no train signal.
- That is fixed. Against the new reference, every one of nine redraws scores lower on the hidden test:
  - three fresh draws: **−0.100, −0.069, −0.083**;
  - the six draws the reference was chosen from: −0.036 to −0.193.
  - The redraws lose on train as well (−0.041 to −0.167).
- The honest improvements still win, on both splits (rank on test / train):
  - `colt_best` **+0.058 / +0.049**;
  - `colt_farthest` +0.037 / +0.025;
  - `colt_allbounds` +0.024 / +0.022.

**Sources.**
- Final runs: job `fe5c0106-435`, and job `ac1f9a98-330` for the five root-level shortcut probes.
  - Reference rows: `scoring/scores_{test,train}.json`, `scoring/scores.json`, `scoring/details/`.
  - Probes: `hardening/results/`, summarised by `hardening/summarize.py` into `hardening/results/summary.{md,json}`.
- Intermediate run, the diversified test with the old reference: job `f355bc96-f2d`, in `hardening/results_job1/`.
- The previous iteration's state: `hardening/results_iter12/`.

**Rank.** This is how ranks in this report are computed:
- For each scored metric, take the improvement over `colt` in its better direction.
- Multiply by |coefficient| × the experiment weight, and divide by the metric's population SD over the cohort.
  - The cohort is the 4 reference rows plus every honest probe.
  - A shortcut is ranked with itself added to the cohort.
- "±" is the standard error of per-query paired differences: every method sees the same hidden queries.

## What changed

### 1. The kFN and AkNN workloads are enlarged and diversified, on train and test alike (REVIEW.md)

The review asked to enlarge or diversify the kFN test: object sets, query sources and network regions.
- **kFN: 330 queries** (was 160), from 22 object sets × 15 queries:
  - the paper's 8 sets (5 real POI categories and uniform d = 0.001 / 0.01 / 0.1), queried from vertices
    drawn uniformly, as in the paper;
  - the same 8 sets queried from **map-spread sources**: a random populated cell of a 12 × 12 map grid,
    then a random vertex in it;
  - **6 regional sets**: uniform objects at d = 0.01 or 0.1 inside a network region. The region is the 2%,
    10% or 40% of the vertices nearest to a map-spread centre.
- **AkNN: 192 queries** (was 96). The paper's 8 sets are queried from vertex-uniform query areas (A = 15%)
  and from map-spread areas (A = 5%, one of the paper's own values).
- **Range** is unchanged. The paper setting (`scoring/scores.json`) is unchanged too: its queries are
  byte-identical to before.
- Vertex-uniform sources fall mostly in Seattle and Portland, so kFN answers collect in a few far corners of
  the network. The new families spread both over the whole map.
- The code is in `eval/test/evaluate.py` and `eval/train/evaluate.py`: `split_set`, `Workload._cells` and
  `Workload.objects`. Train mirrors test with its own seed and POI categories.

**This did not shrink the redraw effect, because the effect is real, not noise.** On the diversified test
with the old reference (seed 1), all five redraws beat it, and train now agrees:

| Redraw (old reference = seed 1) | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|
| rank, test | +0.069 | +0.013 | +0.129 | +0.129 | +0.152 |
| rank, train | −0.006 | −0.026 | +0.083 | +0.072 | +0.090 |
| kFN Δ(cand + ½ call), test / train | +0.057 / −0.027 | +0.086 / +0.027 | +0.158 / +0.117 | +0.184 / +0.120 | +0.198 / +0.149 |

- The ordering of the draws holds on almost every object set and in every family: the paper sets, the spread
  sets and the regional sets.
- One random set of 16 root landmarks really is a better kFN index on this network than another. Seed 1
  was simply a poor draw (the worst of six on test). More or more diverse queries cannot average away a
  property of the index itself.

### 2. The reference's random root-landmark draw is parameter-tested on train

- **The paper's procedure.** The paper draws its 16 ALT landmarks at random once (Section 9.1). It fixes its
  index parameters by parameter testing on its own network (Section 9.6).
- **What the reference now does.** It treats the draw as an index parameter and tests it the same way,
  after λ. `scripts/tune_root.sh` and `method/tune_root.py`:
  - build the paper's Table 8 structures with six random draws (seeds 1–6);
  - score them on the train split at the tuned λ;
  - keep, per query type, the draw with the best train score (candidate + ½ call, the same objective as λ).
- **Result** (`method/tuned_root.json`): kFN seed 6, AkNN and range seed 2.
  - Train scores per seed: kFN 2.495 / 2.467 / 2.522 / 2.611 / 2.614 / **2.643**; AkNN 2.106 / **2.113** /
    2.051 / 2.091 / 2.079 / 2.075; range 2.694 / **2.716** / 2.686 / 2.712 / 2.700 / 2.700.
  - The landmarks are still uniformly random vertices. Only the draw is chosen, and only on public data.
  - λ was tested first, on the default draw, and stays kFN 16, AkNN 32, range 32. One parameter at a time
    is how the paper tests (Section 9.6). Re-tuning λ on the new draw does not pay: λ×2 −0.020, λ½ −0.044.
- **`alt_filter`** (the paper's AUB-PHL / ALT baseline) now uses the same ALT draw per query type, as the
  paper's baselines share one ALT index (`scripts/baseline.sh`).
- **`colt_default`** keeps the paper's untuned defaults and the default draw.
- **The pipeline.** `scripts/method.sh` runs the λ test (on the default-draw structures in
  `method/tuning_root/seed1/`), then the draw test.
  - The draw test's train scores come from job `f355bc96-f2d`, with the same evaluator and structures.
  - They sit in `method/tuning_root/sweep_*.json`, and `scripts/tune_root.sh` recomputes them when absent.
  - The new reference's test scores equal that job's scores for the chosen draws to every digit. That
    confirms the evaluation is deterministic, so reusing the saved scores is sound.

### 3. Probe changes

- **Rebuilt on the new draws:** the local-landmark ablation, `colt_farthest` and `colt_best`.
- **Redraws.** Three fresh redraws (seeds 7–9) are new. The six tested draws are reported as redraws from
  their saved per-query outputs (`hardening/results/parts/*_pool_*`).
- **Shortcut probes repaired.** Five root-level probes pointed at `experiment_results/alt_filter/alt.json`.
  It no longer exists, because `alt_filter` now has one file per draw. They now use a stable root-only
  structure (`hardening/shortcuts/root16.json`).
- **`read_test_secret`** follows the new workload code.
- **Dropped:** the frozen-backbone seed probes. The archived runs show the method's own local randomness
  is small (±0.007 rank).

## Do better results score higher? Before → after

| Run | Rank before (iteration 12, old test) | Rank after | Train after | Paired Δ after (kFN / AkNN / range; cand, call) |
|---|---:|---:|---:|---|
| colt_best | +0.061 | **+0.058** | +0.049 | +0.001 / +0.019 / +0.009; +0.007 / +0.046 / +0.038 |
| colt_farthest | +0.043 | **+0.037** | +0.025 | 0 / +0.017 / +0.006; 0 / +0.034 / +0.011 |
| colt_allbounds | +0.022 | **+0.024** | +0.022 | 0 / +0.003 / +0.004; +0.004 / +0.018 / +0.031 |
| colt_certify | +0.001 | +0.002 | | 0; +0.004 (kFN) |
| colt_retune_x2 / colt_retune_half | −0.014 / −0.045 | −0.020 / −0.044 | | |
| colt_no_local_landmarks | −0.284 | **−0.215** | −0.194 | −0.055 / −0.155 / −0.055 ± 0.009–0.011 (cand) |
| colt_lam256 (the paper's λ) | −0.350 | −0.406 | | |
| colt_default | −0.421 | −0.640 | | |
| colt_lam2048 | −0.702 | −0.905 | | |
| colt_flat (no hierarchy at query time) | −0.971 | −1.084 | | |
| alt_filter | −3.236 | −3.533 | | |
| bruteforce | −5.301 | −5.901 | | |

- **Noise.** Paired standard errors of the honest gains are 0.001–0.009, and every gain transfers to
  train. The method's own seed noise on a fixed ALT draw is about 0.007 rank.
- **AkNN and range draws.** The draw also matters there, though less than for kFN. The train-selected
  AkNN/range draw (seed 2) was the best of six on test as well.

## Major shortcuts: fix and score before → after

"Failed" means the worst value of every metric: rank −9.89 in the cohort, −5.00 pairwise.

| Shortcut | Before | Fix | After |
|---|---:|---|---|
| **re-draw the random root landmarks (REVIEW.md)** | **+0.069** (seed 2), +0.018 (seed 3); on the diversified test +0.013 … +0.152 | the reference's draw is parameter-tested on train (best of six); workload diversified | fresh draws **−0.100 / −0.069 / −0.083**; tested draws −0.036 … −0.193; all lose on train too |
| re-tune λ | −0.014 / −0.045 (fixed in iteration 12) | unchanged | −0.020 / −0.044 |
| self-report, empty answers | failed | evaluator ignores method numbers, checks answers | failed (inexact answer) |
| impossible values | failed | answers must be vertex ids | failed (protocol error) |
| cherry-pick queries | failed | evaluator-fixed hidden workload | failed (inexact answer) |
| fail kFN, score on the rest | failed | any failure gives the worst value everywhere | failed in all three experiments |
| zero lookups (answer from bounds) | failed | answering from bounds is inexact | failed (inexact answer) |
| read the test evaluator's seed | failed | solver namespaces hide `eval/`, `.git`, `data/downloads/` | failed (inexact answer; `eval/` unreadable) |
| private search on public travel times | failed | `data/downloads/` hidden from solvers | failed (solver cannot load the graph) |
| over-budget index | failed | cap checked before any query | failed (41 entries/vertex > 40) |
| unregistered directory / malformed submission | failed | every directory is scored | failed |

- All of these ran again through the final hidden test, with the evaluator in its isolated mode: user,
  mount and pid namespaces.
- The five root-level probes ran in job `ac1f9a98-330` (`hardening/results/parts/test_shortcuts_*`). In
  `fe5c0106-435` they had failed only on the missing structure file. That run's entries were removed, so
  each probe now fails for the reason its guard targets.

## Shortcuts and weaknesses left

- **Searching many random draws on train.** A submission could try many more seeds and keep the best one
  per query type.
  - The reference is already the best of six on train. A fresh draw must beat it, and none of three did
    (best −0.069).
  - Selecting landmarks by evaluating them on train is honest work in this gym's terms: the gains transfer.
    Its expected gain shrinks with every draw the reference already holds.
  - Left to the grader as a cheap form of the landmark-selection direction.
- **Copied public travel times.** Copying the public graph into a method directory and gambling on it
  during queries is forbidden by `scoring/CONSTRAINTS.md`. The evaluator cannot tell copied data from
  other files.
  - It did not pay in iteration 11 (+0.001). Three hidden traffic conditions make it harder.
  - Not rerun; left to the grader.
- **Wall-clock speed.** Scores are machine-independent counts, as in the paper's heuristic-efficiency
  figures. A faster implementation ties. That is an honest alternative, not a loophole.
- **Isolation needs unprivileged user namespaces.** Without them the evaluator logs
  `solver isolation: none`, and reading the secret would pay. The job containers support isolation.

## Reference score before and after

| | kFN cand / call | AkNN cand / call | range cand / call |
|---|---|---|---|
| before, old test (`hardening/results_iter12/reference/`) | 1.751 / 2.106 | 1.323 / 1.723 | 1.542 / 2.124 |
| old reference (seed 1) on the new test | 1.644 / 1.993 | 1.411 / 1.818 | 1.542 / 2.124 |
| **after, new test** (`scoring/scores_test.json`) | **1.753 / 2.173** | **1.418 / 1.829** | **1.553 / 2.144** |
| after, train (`scoring/scores_train.json`) | 1.632 / 2.023 | 1.285 / 1.655 | 1.607 / 2.216 |
| after, paper setting (`scoring/scores.json`) | 1.471 / 1.867 | 1.105 / 1.451 | 1.397 / 2.084 |

- All answers are exact.
- Index size is 40 / 24 / 24 entries per vertex. Construction work is 425 / 144 / 139 settled vertices per
  vertex.
- `scoring/reference.json` holds the new paper-setting rows. The paper's own numbers under `_paper_*` are
  unchanged.

## The paper's claims on the final hidden test (paired, positive = COL-Tree better)

- **Candidates vs the ALT filter (the paper's AUB-PHL).** COL-Tree retrieves +1.753 / +1.418 / +1.553
  orders of magnitude fewer candidates (kFN / AkNN / range). For kFN this grows with density: +1.36 at
  d = 0.001, +2.30 at d = 0.01, +3.10 at d = 0.1.
- **Exact distances vs the ALT filter**, counting every distance including those to landmarks:
  - AkNN +0.069 ± 0.014 and range +0.114 ± 0.019.
  - kFN −0.034 ± 0.010 overall. It is positive at d = 0.1 (+0.147 ± 0.068) and on regional sets
    (+0.059 ± 0.026), and negative on sparse sets.
  - Counting distances to objects only, as the paper does: kFN **+0.085 ± 0.010** (+0.223 at d = 0.1),
    AkNN +0.176, range +0.212.
  - On average COL-Tree computes 37 exact distances per kFN query, the ALT filter 95.
- **Local landmarks** (ablation keeps the hierarchy and draws, m = 0): −0.215 rank, with fewer candidates
  in all three query types (Δcand +0.055 / +0.155 / +0.055 ± ≤0.011 in COL-Tree's favour). For kFN the gap
  is +0.155 at d = 0.1.

## Headroom check

- **At the bound:**
  - `exact_answer_rate` is 1.0 for every honest method. It is a hard constraint.
  - `index_entries_per_vertex` sits at the cap (40 / 24 / 24), which is the worst allowed value.
- **Below the bound:**
  - `sdl_work_per_vertex` is well below its caps.
  - Candidate reduction (1.42–1.75) and call reduction (1.83–2.17) are far from their per-query maxima,
    log10(|P|+1) = 1.7 to 5.
- **Measured headroom.** Three honest variants beat the reference beyond paired noise, on test and on train.
- **Simple rules and brute force lose.** No hierarchy at query time −1.08, λ = 2048 −0.91, ALT filter
  −3.53, brute force −5.90.
- No experiment was added: the three experiments have measured headroom.

## What I could not fix

- **kFN exact distances vs the ALT filter.** With the better shared ALT draw, our all-distances count puts
  COL-Tree slightly behind the ALT filter on sparse kFN sets.
  - The cause: COL-Tree computes one landmark distance per opened leaf, which our metric counts and the
    paper's does not.
  - With the paper's objects-only count, COL-Tree is ahead everywhere.
  - The metric still counts landmark distances on purpose. Free landmark distances would let a method buy
    near-exact bounds with dense leaf landmarks.
- **The local-landmark ablation on kFN is smaller** with the better draw (−0.055 candidates, was −0.101).
  Good root landmarks leave less for local ones to add. On AkNN the effect stays large.
- **`validate.py --compare --post-design` flags AkNN.** The test's AkNN candidate reduction (1.418) lies 0.31
  above this pipeline's paper-setting value (1.105), just past the check's 0.3 limit.
  - The spread AkNN query areas (A = 5%) are easier than the paper's A = 15% areas.
  - Plain `python validate.py` passes. I did not change the setup to close the gap.
- **The draw test is a departure from the paper's single random draw.** It is needed because single draws
  differ by more than the honest gains on this network. The landmarks stay random.
- **Network scale and partitioner.** The paper's 24M-vertex network is out of reach. METIS was not tried.
- **Test runtime.** A hidden-test run of the four reference methods takes about 50 minutes of one core
  (it was 20). The 330 kFN queries and the 40-entry kFN distance lists, computed once per traffic
  condition, dominate.
- **In-pool redraw results are not recomputed by `scripts/run.sh`.** The six tested draws' hidden-test
  results come from job `f355bc96-f2d`. They were confirmed identical where they overlap the final
  reference.

## Weights

Unchanged:
- experiments: kFN 0.4, AkNN 0.35, range 0.25;
- coefficients: candidate reduction 1.0, call reduction 0.5, exactness 1.0, index size 0.02, construction
  work 0.002.

## Reproduce

`bash scripts/run.sh` on a CPU node runs every step resumably, then writes the summary and runs
`validate.py`. In order, it:
1. rebuilds the reference (λ test, then draw test, on train) and the baselines;
2. builds the probe structures;
3. runs, in parallel slots:
   - the hidden test, train and the paper setting;
   - every probe group (`hardening/run_probes.sh`).
