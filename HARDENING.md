# Hardening report (iteration 12, final)

**Better results now score higher and worse ones lower, and the two weaknesses in `REVIEW.md` are fixed.**

- **Re-tuning λ no longer pays.** The reference now chooses λ by the paper's own procedure, parameter testing,
  run on the public train split.
  - Before, re-tuning λ gained up to **+0.36** rank; now it gains **−0.014** (λ×2) and **−0.045** (λ½).
- **Both paper effects appear beyond noise.** I moved the workload to the paper's object-density range
  (uniform sets up to d = 0.1).
  - Local-landmark ablation: before **+0.010** (a tie), now **−0.284**.
  - kFN exact distances, COL-Tree vs the ALT filter at d = 0.1: before **0.000 ± 0.006** over all queries,
    now **+0.35 ± 0.07**. At d = 0.01 it is **+0.14 ± 0.04**.
- **Honest improvements beat the reference and transfer from train to test.**
  - `colt_best`: test +0.061, train +0.041.
  - farthest ALT landmarks for AkNN/range: test +0.043, train +0.026.
  - all-landmark bounds: test +0.022, train +0.013.
  - The method's own seed noise on the shared ALT index is 0.007.
- **Weaker variants and shortcuts lose.**
  - no hierarchy at query time −0.97, λ=2048 −0.70, the paper's λ=256 −0.35, ALT filter −3.24, brute force −5.30.
  - Every shortcut fails and gets the worst value of every metric.
- **One weakness is left.** Re-drawing the 16 random root landmarks moves the test rank by up to **+0.069**,
  with no train signal (see "What I could not fix").

**Sources.** All numbers come from these runs:
- the hidden-test evaluator on the reference (`scoring/scores_test.json`, `scoring/details/test.json`);
- the probe runs (`hardening/run_probes.sh`, `hardening/results/`), summarised in
  `hardening/results/summary.{md,json}` by `hardening/summarize.py`;
- the train sweep (`method/tuned_lambda.json`).

**Rank.** For each scored metric, take the improvement over `colt` in its better direction and multiply by
|coefficient| × experiment weight. Divide by the metric's population SD over the cohort: the 4 reference rows
plus every honest variant. A shortcut is ranked with itself added to that cohort. "±" is the standard error of
per-query paired differences: every method sees the same hidden queries.

## What changed in this iteration

1. **λ is tuned on the train split** (`scripts/tune_lambda.sh`, `method/tune_lambda.py`, run by `scripts/method.sh`).
   - The paper fixes its COL-Tree parameters by exhaustive parameter testing on its own 24M-vertex network
     (Section 9.6). Its λ = 256 was the smallest value it tested. This network is 22× smaller, so the same
     procedure is repeated here.
   - The sweep scores λ ∈ {8, …, 512} on the reference structures through `eval/train/evaluate.py`. Per query
     type it keeps the best train score (candidate reduction + 0.5 × call reduction, the two benefit
     coefficients). Train scores:

| λ | 8 | 16 | 32 | 64 | 128 | 256 | 512 | chosen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kFN | 2.600 | **2.631** | 2.627 | 2.600 | 2.585 | 2.550 | 2.493 | 16 |
| AkNN | 1.946 | 1.976 | **1.985** | 1.966 | 1.909 | 1.740 | 1.709 | 32 |
| range | 2.652 | 2.670 | **2.694** | 2.688 | 2.681 | 2.593 | 2.564 | 32 |

   - The structures (b, m, landmark policy, α) stay the paper's Table 8 settings.
   - `colt_default` keeps the paper's untuned defaults (b=8, m=2, Random, λ=256).

2. **The workload covers the paper's density range** (train, test and the paper setting).
   - The paper's sensitivity studies vary d = |P|/|V| from 0.0001 to 0.1 (Figures 6a, 11, 13a).
   - The gym used to stop at 5,000 objects: real POI sets and uniform d ≤ 0.01.
   - Every split now has uniform sets at d = 0.001, 0.01 and 0.1, which is 1,090 to 109,000 objects, next to
     the real POI categories.
   - Held-out test: 160 kFN, 96 AkNN and 140 range queries.

3. **The hidden test averages over three hidden travel-time conditions** (`CONDITIONS = 3` in
   `eval/test/evaluate.py`).
   - Query i of an object set runs under condition i mod 3, and every metric averages over the conditions.
   - Each condition is an independent secret perturbation of the public travel times. Landmark distance lists
     and exact distances are computed per condition.
   - This was added to damp root-landmark draw luck. It helped only a little (see below).
   - Train keeps one public condition, so the λ sweep and the train scores are unaffected.

4. **The call metric is unchanged.** It counts every exact distance, including those to landmarks.
   - The paper counts distances to objects only. That count would favour COL-Tree more: on the test, the
     objects-only kFN call reduction is **+0.149 ± 0.016** above ALT.
   - It is not used, for two reasons:
     - A landmark's distance is just as expensive as an object's.
     - Free landmark distances would let a method place dense leaf landmarks and buy near-exact bounds for
       every object.

5. **Pipeline changes.**
   - Evaluator runs can be split by query type (`--tasks`).
   - Runs resume after every finished query type and travel-time condition (`--checkpoint`). The compute
     nodes were preempted about every 28 minutes.
   - `scripts/run.sh` runs the scoring runs in parallel slots.
   - None of this changes scoring. Resuming after two of three conditions reproduces an uninterrupted run
     byte for byte (checked on a 12k-vertex network).
   - `scoring/scores_test.json` was produced by the evaluator just before per-condition checkpoints were
     added. The scoring code is identical.

## Do better results score higher? Before → after

**Before** (iteration-11 hidden test, `hardening/results_iter11/`): one travel-time condition, objects up to
5,000, reference λ = 256.

| Run | Rank | Note |
|---|---:|---|
| colt_lam16 | **+0.361** | re-tuning the paper's own knob was the easiest gain |
| colt_allbounds_lam64 | +0.340 | |
| colt_lam64 | +0.325 | |
| colt_seed2 / colt_seed3 | +0.042 / +0.015 | seed spread 0.042 |
| colt_allbounds | +0.014 | |
| colt_no_local_landmarks | +0.010 | ablation tied the reference |
| colt_flat | −0.415 | |
| colt_lam2048 | −0.437 | |
| alt_filter / bruteforce | −2.724 / −4.610 | |

**After** (final hidden test, three conditions, tuned λ). Δ are paired per-query differences against `colt`.

| Run | What it changes | Rank | kFN Δcand / Δcall | AkNN Δcand / Δcall | range Δcand / Δcall |
|---|---|---:|---|---|---|
| colt_best | farthest ALT landmarks (AkNN, range) + all-landmark bounds + certification | **+0.061** | +0.002 / +0.012 ± 0.002 | +0.019 ± 0.007 / +0.045 ± 0.010 | +0.014 ± 0.006 / +0.047 ± 0.011 |
| colt_farthest | farthest instead of random ALT landmarks (AkNN, range) | **+0.043** | 0 / 0 | +0.018 ± 0.007 / +0.035 ± 0.010 | +0.012 ± 0.006 / +0.025 ± 0.010 |
| colt_allbounds | bounds from every landmark on the path | **+0.022** | +0.001 / +0.010 ± 0.002 | +0.001 / +0.014 ± 0.002 | +0.005 ± 0.001 / +0.027 ± 0.004 |
| colt_certify | accept a result when its bounds prove it | +0.001 | 0 / +0.002 ± 0.001 | 0 / 0 | 0 / 0 |
| colt_seed2f / colt_seed3f | method seed 2 / 3 on the shared ALT backbone | +0.002 / −0.005 | 0 / 0 | ±0.004 | ±0.002 / ±0.007 |
| colt_retune_x2 | λ × 2 | −0.014 | +0.008 / +0.013 | −0.026 / −0.007 | +0.003 / −0.008 |
| colt_retune_half | λ / 2 | −0.045 | −0.026 / −0.014 | −0.005 / −0.007 | −0.026 / +0.001 |
| colt_no_local_landmarks | only the 16 ALT landmarks (m = 0), same λ | **−0.284** | −0.101 ± 0.013 / −0.024 ± 0.016 | −0.168 ± 0.017 / −0.093 ± 0.019 | −0.056 ± 0.008 / −0.109 ± 0.017 |
| colt_lam256 | the paper's λ (the previous reference) | −0.350 | −0.122 / +0.032 | −0.219 / −0.057 | −0.091 / −0.068 |
| colt_default | paper defaults b=8, m=2, Random, λ=256 | −0.421 | −0.264 / +0.027 | −0.219 / −0.057 | −0.057 / −0.049 |
| colt_lam2048 | λ = 2048 | −0.702 | −0.144 / +0.042 | −0.478 / −0.076 | −0.298 / −0.100 |
| colt_flat | no hierarchy at query time | −0.971 | −0.182 / −0.024 | −0.619 / −0.093 | −0.464 / −0.109 |
| alt_filter | the paper's AUB-PHL (ALT filter over every object) | −3.236 | −1.751 / −0.024 | −1.323 / −0.093 | −1.542 / −0.109 |
| bruteforce | every object, every distance | −5.301 | −1.751 / −2.106 | −1.323 / −1.723 | −1.542 / −2.124 |

- **Two other variants.**
  - `colt_farthest_all` (farthest ALT landmarks for kFN too): **−0.338**, single-condition run in
    `hardening/results_single_condition/`. Fringe landmarks loosen kFN upper bounds. That is why `colt_best`
    keeps the random kFN landmarks.
  - `colt_adaptive` (λ from the object count) was identical to the reference. With dense sets, the COL leaves
    bottom out at the SUL leaves.
- **Gains transfer to train.** Each row shows the change in candidate reduction + 0.5 × call reduction against
  the reference on the same split:

| Run | rank train | rank test | kFN train / test | AkNN train / test | range train / test |
|---|---:|---:|---|---|---|
| colt_best | +0.041 | +0.061 | +0.005 / +0.008 | +0.016 / +0.041 | +0.059 / +0.037 |
| colt_farthest | +0.026 | +0.043 | 0 / 0 | +0.012 / +0.036 | +0.039 / +0.024 |
| colt_allbounds | +0.013 | +0.022 | +0.002 / +0.006 | +0.005 / +0.008 | +0.019 / +0.018 |
| colt_no_local_landmarks | −0.214 | −0.284 | −0.079 / −0.113 | −0.213 / −0.215 | −0.059 / −0.110 |
| λ/2, λ×2, λ=256 (train from the sweep) | | | −0.031 / −0.033, −0.005 / +0.014, −0.081 / −0.106 | −0.008 / −0.008, −0.018 / −0.030, −0.244 / −0.248 | −0.024 / −0.026, −0.006 / −0.001, −0.101 / −0.125 |

## The paper's effects (REVIEW.md item 1)

**kFN exact distances, COL-Tree vs the ALT filter.** Positive Δcall means COL-Tree computes fewer exact
distances. Hidden test, paired:

| Object set | real POIs (5 sets) | uniform d=0.001 | uniform d=0.01 | uniform d=0.1 | all |
|---|---|---:|---:|---:|---:|
| kFN Δcall | −0.10 … +0.02 | −0.057 ± 0.016 | **+0.139 ± 0.038** | **+0.352 ± 0.066** | +0.024 ± 0.016 |
| AkNN Δcall | −0.04 … +0.16 | −0.026 ± 0.012 | +0.101 ± 0.038 | **+0.432 ± 0.071** | **+0.093 ± 0.019** |
| range Δcall | −0.05 … +0.15 | −0.022 ± 0.017 | +0.148 ± 0.030 | **+0.316 ± 0.041** | **+0.109 ± 0.017** |

- **Paper direction.** As in the paper's Figure 11c, COL-Tree's advantage in exact distances grows with
  density. At the dense end it is well beyond noise; the paper reads about log10(230/27) = 0.93 at d = 0.1 on
  a 22× larger network.
- **Sparse sets.** On sets of a few thousand objects, COL-Tree spends about as many exact distances as ALT. It
  computes one landmark distance per opened leaf, which our metric counts and the paper's does not. Counting
  objects only, as the paper does, COL-Tree is ahead by +0.149 ± 0.016.
- **Paper setting.** The paper's own setting (original travel times, `scoring/scores.json`) shows the same
  pattern: kFN Δcall +0.055 ± 0.031 at d = 0.01, +0.129 ± 0.071 at d = 0.1, −0.027 ± 0.012 overall.
- **Candidates.** COL-Tree retrieves 1.0 to 3.0 orders of magnitude fewer objects than ALT on every set.

**Local landmarks.** The ablation keeps the reference hierarchies and λ but has only the 16 ALT landmarks:
- −0.284 rank.
- Candidates −0.101 / −0.168 / −0.056, many SE apart.
- Calls −0.024 / −0.093 / −0.109, with a larger gap at higher density (kFN d = 0.1: −0.33 candidates, −0.35 calls).
- The paper's claim that local landmarks tighten bounds deeper in the hierarchy now shows clearly. With
  λ = 256 the COL leaves were so large that their local landmarks were no denser than the ALT landmarks.

## Major shortcuts: fix and score before → after

"Failed" means the worst value of every metric. That is rank −8.91 in the cohort and −5.00 pairwise.

| Shortcut | Before | Fix | After |
|---|---:|---|---|
| **re-tune λ (REVIEW.md item 2)** | **+0.361** (λ=16), +0.325 (λ=64) | the reference's λ is tuned per query type on train, as the paper tunes on its data | **−0.014** (λ×2), **−0.045** (λ½) |
| self-report, empty answers | failed | (iteration 11) evaluator ignores method numbers and checks answers | failed (inexact answer) |
| impossible values | failed | answers must be vertex ids | failed (protocol error) |
| cherry-pick queries | failed | evaluator-fixed hidden workload | failed (inexact answer) |
| fail kFN, score on the rest | failed | any failure gives the worst value everywhere | failed (kFN query 0 inexact; worst value in all three experiments) |
| zero lookups | failed | answering from bounds alone is inexact | failed (inexact answer) |
| read the test evaluator's seed | failed (+3.217 with isolation off) | solver namespaces hide `eval/`, `.git` | failed |
| private search on public travel times | failed | `data/downloads/` hidden from solvers | failed (solver cannot load the graph) |
| over-budget index | failed | cap checked before any query | failed (41 entries/vertex > 40) |
| unregistered directory / malformed submission | failed | every directory under `experiment_results/` is scored | failed |

- **Rerun this iteration.** All of these ran again through the final test (groups `colt_b` and `alt`), with
  the same outcome as before. The probe groups ran one query type at a time. Their merge applies the
  evaluator's rule: a failure in one query type gives the worst value in all three.
- **Not rerun.** The two `public_gamble_copied` probes: an exact gamble on copied public travel times. They
  depend on the solver only, which is unchanged. In iteration 11 they stayed exact and gained +0.001.

## Shortcuts and weaknesses left

- **Root-landmark lottery (not fixed).** Re-drawing the 16 random ALT root landmarks moves the test rank by
  **+0.069** (seed 2) and **+0.018** (seed 3).
  - Almost all of it is kFN (seed 3: Δcand +0.064 ± 0.009, Δcall +0.092 ± 0.013). It appears under all three
    hidden conditions.
  - It is absent on train: kFN train Δ −0.011 and +0.016, train rank +0.003 and −0.033.
  - So it is an interaction between one random landmark set and the test's kFN queries, not a better index.
    Dense kFN answers concentrate in a few far regions of the network, and whether a random landmark sits on
    the way to them is close to a lottery.
  - Averaging over three traffic conditions reduced the spread only from 0.079 to 0.069.
  - The method's own randomness on the shared ALT backbone is small (spread 0.007), as are the honest gains'
    standard errors.
  - **Consequence.** A submission that only re-draws root landmarks can gain up to about +0.07 on test with no
    train evidence. The honest gains above transfer to train; this one does not. Left to the grader: a
    root-landmark change should come with a train improvement.
- **Copied public travel times.** Copying them into a method directory and gambling on them is forbidden by
  `scoring/CONSTRAINTS.md`. The evaluator cannot tell copied data from other files. It did not pay in
  iteration 11 (+0.001), and the three hidden conditions make it harder still. Left to the grader.
- **Wall-clock speed.** Scores are machine-independent counts, as in the paper's heuristic-efficiency
  figures. A faster implementation ties. This is an honest alternative, not a loophole.
- **Isolation needs unprivileged user namespaces.** Without them the evaluator logs
  `solver isolation: none (namespaces unavailable)`, and reading the evaluator's seed would pay. The job
  containers support isolation.
- **Solvers can write to the workspace during evaluation.** Each hidden test runs in a fresh container.

## Reference score before and after

- **Before** (iteration 11, `hardening/results_iter11/reference/scores_test.json`: one condition, objects up to
  5,000, λ = 256):
  - candidate reduction kFN 1.369, AkNN 1.001, range 1.461
  - call reduction 1.943 / 1.545 / 2.076
- **After** (`scoring/scores_test.json`: three conditions, densities up to 0.1, tuned λ):
  - candidate reduction **1.751 / 1.323 / 1.542**
  - call reduction **2.106 / 1.723 / 2.124**
  - all answers exact
  - index 40 / 24 / 24 entries per vertex; construction work 425 / 145 / 141
- **Like for like.** The workload changed, so the closest comparison is the old configuration (`colt_lam256`)
  on the new test: 1.629 / 1.104 / 1.450 and 2.138 / 1.667 / 2.057, rank −0.350.
- **Train** (`scoring/scores_train.json`): 1.641 / 1.207 / 1.595 and 1.980 / 1.556 / 2.198.
- **Paper setting** (`scoring/scores.json`, also in `scoring/reference.json`): 1.415 / 1.092 / 1.399 and
  1.756 / 1.445 / 2.069.
- The paper's own reported numbers under `_paper_*` in `scoring/reference.json` are unchanged.

## Headroom check

- **At the bound.**
  - `exact_answer_rate` is at 1.0 for every honest method. It is a hard constraint.
  - `index_entries_per_vertex` sits at the cap (40 / 24 / 24), which is the worst allowed value.
- **Below the bound.**
  - `sdl_work_per_vertex` is well below its caps.
  - Candidate reduction (1.75 / 1.32 / 1.54) and call reduction (2.11 / 1.72 / 2.12) are far from their bounds.
    Their per-query maximum is log10(|P|+1), between 1.7 and 5.
- **Measured headroom.** Three honest variants (`colt_best`, `colt_farthest`, `colt_allbounds`) beat the
  reference beyond the paired noise and the shared-backbone seed spread, and their gains transfer to train.
- **Simple rules don't win.** No simple rule reaches the reference: no hierarchy at query time −0.97, λ=2048
  −0.70.
- **Brute force doesn't win.** The brute force the paper avoids, and its AUB-PHL baseline, score 0 candidate
  reduction (−5.30 and −3.24).
- No experiment was added: the existing three have measured headroom.

## What I could not fix

- **The root-landmark lottery** (above): up to +0.07 on test from re-drawing landmarks, with no train signal.
- **kFN overall call count.** Averaged over all object sets, kFN COL-Tree computes only slightly fewer exact
  distances than the ALT filter (+0.024 ± 0.016). In the paper setting, slightly more (−0.027 ± 0.012).
  - Both because the metric counts COL-Tree's per-leaf landmark distances.
  - The paper's advantage appears at d ≥ 0.01, or when only object distances are counted.
- **Network scale.** The paper's 24M-vertex network is out of reach. Distance lists for one kFN structure take
  5–10 minutes per travel-time condition on the 1.09M-vertex network.
- **Partitioner.** The SUL-Tree uses recursive median bisection of coordinates instead of METIS. The paper
  allows any balanced partitioner. METIS was not tried because it cannot be installed and tested on the login
  node.
- **Test runtime.** A full hidden-test run of the four reference methods takes about 20 minutes of one core.
  With 3 conditions, the 40-entry kFN structures dominate.

## Weights

Unchanged:
- experiments: kFN 0.4, AkNN 0.35, range 0.25
- coefficients: candidate reduction 1.0, call reduction 0.5, exactness 1.0, index size 0.02, construction work 0.002

The paper's contribution is aimed at AkNN and kFN; range is its secondary case.

## Reproduce

`bash scripts/run.sh` on a CPU node rebuilds the reference and runs the λ sweep on train, then the baselines
and the probe structures. In parallel it runs:
- the hidden test (`scoring/scores_test.json`)
- train
- the paper setting
- every probe group (`hardening/run_probes.sh`)

Then `hardening/summarize.py` and `validate.py`. Every step is resumable.
