# Hardening report (iteration 11)

**Better results now score higher, worse ones lower, and every major shortcut in `REDTEAM.md` is closed.**
On the hidden test, the honest improvements (smaller COL leaves, λ=16 or 64) gain **+0.33 to +0.36** rank
over the reference. The reference's own seed reruns span **0.042**. Weaker variants lose: λ=2048 −0.44,
no hierarchy at query time −0.42, ALT filter −2.72, brute force −4.61. Every shortcut tried now fails
and receives the worst value of every metric. The one exception, an exact private-search gamble on the
public travel times, gains nothing (+0.001).

All numbers come from `bash scripts/evaluate_test.sh` (reference rows) and the same test evaluator run
on probe directories (`hardening/run_probes.sh`). Raw outputs are in `scoring/scores_test.json`,
`scoring/details/test.json` and `hardening/results/` (`summary.md`, `summary.json`, `parts/`).

**How the rank is computed.** I use the gym's rule. For each scored metric, take its improvement over
the reference, in its better direction. Multiply by |coefficient| and the experiment weight, then
divide by the metric's population standard deviation. The "cohort" population is the 14 honest runs
(the reference rows plus all variants); a shortcut is ranked with itself added to that cohort. A
two-attempt "pairwise" rank (as in `REDTEAM.md`) is also in `summary.md`. It is degenerate: any
difference, however small, becomes ±1 SD.

## What changed in this iteration

The red-team audit (`REDTEAM.md`) was run on the old US48 gym. There, the hidden evaluator read numbers
the method wrote about itself, so fabricated, cherry-picked or failing submissions outranked the
reference. The graph was unit-weight, and the workload had three AkNN queries. This iteration rebuilt
the test and then hardened it:

1. **The paper's own data.** The test now uses the paper's own Zenodo dataset: the NW subset of the
   DIMACS travel-time network (1,089,933 vertices) and the paper's 8 real OSM POI categories.
2. **The evaluator owns every distance.** A method submits an index structure (hierarchy +
   landmarks) and a solver command. The evaluator builds the landmark distance lists on its own
   copy of the network, answers the solver's requests, counts them, and checks every answer
   against its own Dijkstra. Nothing a method writes about itself is read.
3. **The workload is held out.** It uses hidden travel-time conditions (a secret spatially
   correlated and per-edge perturbation), a fresh hidden object set per query (jittered real
   POIs or uniform samples), and hidden queries: 140 kFN, 84 AkNN and 120 range.
4. **Failure is total.** An invalid or over-budget index, a crash, protocol error or timeout, or a
   single inexact answer fails the run, and a failed run gets the worst value of every metric in
   every experiment. Every directory under `experiment_results/` is scored.
5. **Index nodes count as candidates.** A non-empty index node a solver opens counts as a
   retrieved candidate, like an object it reveals. Before, node lookups were free, and `--lam 0`
   alone would have raised kFN candidate reduction from 1.43 to 2.14 (objects-only metric).
6. **Construction-work caps per query type** (3,000 / 600 / 600 settled vertices per vertex).
   The index caps equal the paper's tuned configuration: 40 entries per vertex for kFN, 24 for
   AkNN and range.
7. **Solver isolation.** Each solver runs in its own user, mount and pid namespaces, in which
   `eval/`, `.git` and **`data/downloads/`** are empty mounts and `/proc` shows only its own
   processes.
   - Hiding `eval/` and `.git` closes reading the test evaluator's seed at test time.
   - Hiding `data/downloads/` (added last) closes private shortest-path search on the public
     travel times while answering; the raw data stays available to index building.
   - The job log confirms the compute container supports this:
     `solver isolation: user+mount+pid namespaces (eval, .git, data/downloads hidden, private /proc)`.
8. **Pipeline.** `scripts/run.sh` runs the probes in small groups, each with its own output file,
   in priority order. Compute nodes were preempted ("SLURM worker drain") 12 times across two
   jobs, and a single 70-minute probe run never finished.
   - A change to the evaluator's search engine to speed it up made no difference: the cost is the
     settled-vertex work itself. It was reverted, so the evaluators are byte-identical to the
     version that produced `scoring/scores_test.json`.

## Do better results score higher?

**Before** (`REDTEAM.md`, old gym, fixed-cohort rank):
- stronger landmarks: +0.47
- seed-rerun range: 0.31
- exhaustive enumeration: −2.65
- an honest faster implementation: tied

**After** (hidden test, rank against the reference `colt`; per-query paired differences in log10
candidate reduction, mean ± standard error):

| Run | What it changes | Cohort rank | kFN Δcand | AkNN Δcand | range Δcand |
|---|---|---:|---:|---:|---:|
| colt_lam16 | COL leaves of ≤16 objects (paper: 256) | **+0.361** | +0.191 ± 0.019 | +0.185 ± 0.015 | +0.043 ± 0.013 |
| colt_allbounds_lam64 | λ=64 and bounds from every landmark on the path | **+0.340** | +0.148 ± 0.019 | +0.160 ± 0.014 | +0.076 ± 0.013 |
| colt_lam64 | λ=64 | **+0.325** | +0.148 ± 0.019 | +0.159 ± 0.014 | +0.073 ± 0.013 |
| colt_lam0 | COL leaves = SUL leaves | +0.045 | +0.011 ± 0.021 | +0.088 ± 0.016 | −0.016 ± 0.014 |
| colt_seed2 | reference, landmark/partition seed 2 | +0.042 | +0.037 ± 0.011 | −0.021 ± 0.013 | +0.012 ± 0.010 |
| colt_seed3 | reference, seed 3 | +0.015 | +0.045 ± 0.010 | −0.020 ± 0.015 | −0.014 ± 0.008 |
| colt_allbounds | bounds from every landmark on the path | +0.014 | +0.000 | +0.000 | +0.001 |
| colt_no_local_landmarks | 16 ALT landmarks only, no local landmarks (m=0) | +0.010 | +0.073 ± 0.026 | −0.070 ± 0.018 | −0.018 ± 0.015 |
| colt (reference) | paper Table 8 parameters | 0 | | | |
| colt_default | b=8, m=2, Random for every query | −0.041 | −0.082 ± 0.021 | 0 | +0.024 ± 0.013 |
| colt_flat | no hierarchy at query time (root lists only) | −0.415 | +0.016 ± 0.044 | −0.292 ± 0.028 | −0.297 ± 0.032 |
| colt_lam2048 | λ=2048 | −0.437 | −0.119 ± 0.043 | −0.267 ± 0.025 | −0.171 ± 0.028 |
| alt_filter | paper's AUB-PHL / ALT multi-step filter | −2.724 | −1.369 | −1.001 | −1.461 |
| bruteforce | every object, every distance | −4.610 | −1.369 | −1.001 | −1.461 |

**Seed noise.** The reference with three landmark/partition seeds spans 0.042 in rank. In
candidate reduction the spread is 0.045 (kFN), 0.021 (AkNN) and 0.027 (range). The λ=16/64 gains are
about 8× the rank spread, and on each query type larger than the seed spread with many standard
errors to spare. All methods see the same hidden queries, so these are paired comparisons.

**Train agrees in direction.** On the public split, colt_lam64 beats the reference by
+0.033 ± 0.019 (kFN), +0.158 ± 0.016 (AkNN) and +0.071 ± 0.014 (range). The reference itself scores
alike on train and test (candidate reduction 1.33 / 1.37, 0.88 / 1.00, 1.49 / 1.46).

## Major shortcuts: fix and score before → after

"Before" is the pairwise rank in `REDTEAM.md` (old gym). "After" is the hidden test. "Failed" means
worst values everywhere: cohort rank −7.911, pairwise −5.004.

| Shortcut | Before | Fix | After |
|---|---:|---|---|
| self-report (forged scores, empty answers) | +1.977 | evaluator ignores method-written numbers and checks answers | failed (kFN query 0 inexact) |
| impossible values (flags 2, negative counts) | +3.957 | answers must be vertex ids; every metric is computed by the evaluator | failed (protocol error) |
| denominator (inflated object count) | +1.977 | the evaluator owns \|P\| and \|Q\| | not expressible |
| cherry-pick queries | +1.977 | evaluator-fixed hidden workload, every query scored | failed (answers [] on large sets) |
| cached answers | +1.683 | hidden travel times, objects and queries; public data hidden from solvers | not expressible; see the gambles below |
| replace ground truth / baseline | +0.425 | ground truth is the evaluator's Dijkstra | not expressible |
| fail kFN, score on the rest | +0.147 | any failure gives the worst value of every metric | failed |
| zero lookups (metric dropped) | 0 (tie) | every metric always written; answering from bounds alone is inexact | failed (kFN query 1 inexact) |
| unregistered method directory | 0 (tie) | every directory under `experiment_results/` is scored | failed (no submission.json) |
| empty answers / malformed flags | −3.663 / unranked | worst vector for every failure | failed (malformed submission) |
| over-budget index | n/a | cap enforced before any query | failed (41 entries/vertex > 40) |
| **read the test evaluator's seed at test time** (new) | isolation off: **+3.217**, the maximum on every metric | solver namespaces hide `eval/` and `.git` | failed |
| **free index-node opens via `--lam 0`** (new) | objects-only metric: kFN 1.43 → 2.14 | non-empty opened nodes are candidates | +0.045, about the seed spread (0.042); kFN Δcand +0.011 ± 0.021 |
| **private search on the public travel times** (new: `public_oracle`, `public_gamble` ×1.00/×1.15) | n/a | `data/downloads/` hidden from solvers | failed (solver cannot load the graph) |

## Shortcuts left, and why

- **Copying the public travel times into the method's own directory and gambling on them.** This
  is `public_gamble_copied` ×1.15 and ×1.30: COL-Tree kFN search plus a non-admissible
  public-distance bound. It is forbidden by `scoring/CONSTRAINTS.md`, and the evaluator cannot tell
  copied data from other files. Measured on the hidden test, both stay exact but **do not pay**:
  rank +0.001 and +0.000, kFN Δcand −0.000. Because travel times are perturbed, public distances
  cannot sharpen the landmark bounds without risking an inexact answer. Left to the grader.
- **Faster implementations** (wall-clock). This is an honest alternative the test cannot tell
  apart, not a loophole. Scores are machine-independent counts, as in the paper's
  heuristic-efficiency figures, and no metric depends on time.
- **Isolation depends on user namespaces.** If a future hidden-test container does not allow
  unprivileged user namespaces, the evaluator logs `solver isolation: none (namespaces
  unavailable)`. The secret-reading shortcut then pays in full (+3.217). The container used in
  this iteration supports isolation.
- **Solvers can write to the workspace during evaluation.** Each hidden test runs in a fresh
  container, so this is not defended.

## Reference score before and after

- **Old gym** (`REDTEAM.md`): a different, self-reported metric (fraction of objects), not
  comparable.
- **Start of this iteration** (job 9fc1dbc3, no node charging, default configuration): candidate
  reduction kFN 1.366, AkNN 1.046, range 1.641; call reduction 1.935 / 1.545 / 2.096.
- **Final reference** (`colt`, paper Table 8 per query type, `scoring/scores_test.json`): candidate
  reduction **kFN 1.369, AkNN 1.001, range 1.461**; call reduction 1.943 / 1.545 / 2.076. All
  answers are exact. Index 40 / 24 / 24 entries per vertex; construction work 410 / 140 / 135.
  With objects only (the paper's metric), candidate reduction is 1.433 / 1.046 / 1.612.
- **Paper setting** (`scoring/scores.json`: original travel times, real POI sets as published):
  candidate reduction 1.091 / 0.787 / 1.382. The paper's figure gives about 1.38 for kFN
  candidates (`reference.json`, `_paper_colt_phl`).

## Headroom check

Where the reference sits on each scored metric:
- `exact_answer_rate` is at its bound (1.0). It is a hard constraint, and every honest method is
  there.
- `index_entries_per_vertex` sits at the cap (40 / 24 / 24). That is the worst allowed value; a
  smaller index scores better.
- `sdl_work_per_vertex` is well below its cap (410 of 3,000; 140 of 600).
- The benefit metrics are far from their bounds:
  - Candidate reduction is 1.37 / 1.00 / 1.46. An answer-only oracle (the unisolated secret
    reader) reaches 2.25 / 2.25 / 2.25.
  - Call reduction is 1.94 / 1.55 / 2.08, against the oracle's 3.29 / 4.19 / 3.56.
- Simple honest changes beat the reference by more than noise, and no simple variant comes close
  to the bound. So no extra experiment was added.

The brute force the paper avoids, and its AUB-PHL baseline, both score 0 candidate reduction and rank
−4.6 and −2.7. ALT filtering alone matches the reference on calls, but retrieves every object
(2,732 per kFN query vs 103 for the reference).

## What I could not fix (stated plainly)

- **The paper's kFN network-distance advantage is not reproduced.** The paper reads as COLT
  computing fewer exact distances than AUB-PHL for kFN (call reduction about 2.27 vs 1.5). Here
  they are equal: 1.943 vs 1.943 on test, 1.530 vs 1.535 in the paper setting.
  - Our call metric counts every distance request, including those to landmarks, which the paper
    does not count. Counting only object distances would let a method buy exact bounds for free
    through neighbours of objects.
  - The candidate-reduction advantage, the paper's key heuristic-efficiency claim, is reproduced
    in the paper's direction for all three query types.
- **Local landmarks only pay off for AkNN and range here.** The ablation without local landmarks
  ties the reference (+0.010, inside the 0.042 seed spread). It is better on kFN (+0.073), worse on
  AkNN (−0.070) and range (−0.018), with a smaller index.
  - On this 1.09M-vertex network, 16 global ALT landmarks already bound kFN well. The paper's
    24M-vertex network is out of reach: building one kFN structure's distance lists on the 1.09M-vertex
    network takes 5–28 minutes on these preemptible nodes.
  - The ablation is honest and does not outrank the reference, so it is a headroom note, not a
    loophole.
- **The paper's λ=256 is not optimal under this metric.** Opened nodes count as candidates, and
  λ=16–64 does better. The paper tuned λ for wall-clock time on its own hardware. This is genuine
  headroom for future methods, not a defect, and the reference keeps the paper's setting.
- **Runtime.** A full hidden-test run costs 10–30 minutes per submitted method, dominated by
  building the method's landmark distance lists.

## Weights

Weights are unchanged: kFN 0.4, AkNN 0.35, range 0.25. Coefficients are 1.0 for candidate
reduction, 0.5 for call reduction, 1.0 for exactness, 0.02 for index size and 0.002 for construction
work. The paper's contribution is aimed at AkNN and kFN, and it calls range a secondary case.
"Candidates retrieved" is the heuristic-efficiency metric that separates COL-Trees from the
landmark-based competitors in the paper.

## Reproduce

`bash scripts/run.sh` on a CPU node rebuilds the reference and baseline submissions, then runs, in
priority order:
- the hidden test,
- the probe groups (`hardening/build.sh` builds the variants and shortcuts),
- train and the paper setting,
- the seed reruns,
- the unisolated secret-reading probe (a temporary copy of the test evaluator with
  `SANDBOX = False`, deleted afterwards),
- `hardening/summarize.py`.

Each step is resumable.
