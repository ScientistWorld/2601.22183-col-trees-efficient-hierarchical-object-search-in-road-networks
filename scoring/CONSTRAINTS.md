# Scientist Constraints

## Protocol
A submission is a directory under `experiment_results/` containing `submission.json`:
a solver command and one index structure file per query type (see `briefing/evaluation.md`).
The evaluators compute every distance stored in the index and every exact network distance themselves, on their own copy of the network.
The test split uses hidden travel times, object sets and queries.
Scores come only from what the evaluator observes. Nothing a method writes about itself is read.
Every non-empty index node a solver accesses counts as a retrieved candidate, like every object it reveals.
Solvers run isolated from the evaluator. `eval/`, `.git` and `data/downloads/` are not visible to them,
and neither are the evaluator's processes.

## Index budget (enforced)
- Distance-list entries per vertex: at most 40 for kFN and 24 for AkNN and range.
- Index construction work: at most 3,000 settled vertices per vertex for kFN and 600 for AkNN and range.
- Leaves need at least 128 vertices, nodes may have at most 32 landmarks, and there may be at most 200,000 nodes.
Larger indexes are rejected, which counts as a failure.

## Correctness (enforced)
Every answer must be exact. Ties at the k-th distance may be broken arbitrarily.
One wrong answer, crash, timeout or protocol violation scores the method with the worst value of every metric in every experiment.

## Data
Use only the provided NW road network and POI files in `data/downloads/nw/`, and only to build the index.
The solver learns object sets and distances through the protocol alone: it must not carry the public travel
times (or shortest-path distances computed from them) into query answering. Do not try to reconstruct the
evaluation network's travel times from the public ones. Do not answer from estimates that the protocol
does not let you verify. One inexact answer fails the run.
On the held-out split, the travel times differ from the public file: three hidden traffic conditions, with the queries split across them.

## Compliance Checklist
- [ ] Submission directory contains `submission.json` and a structure for kfn, aknn and range
- [ ] Index within the per-query entry cap and the construction-work cap
- [ ] All answers exact on train (`exact_answer_rate` = 1.0)
- [ ] Solver talks only the documented protocol on stdin/stdout
