# Evaluation Plan

## Data

- **Road network**: the paper's own public dataset (Zenodo doi:10.5281/zenodo.18026780). This benchmark uses
  its North-West US subset of the 9th DIMACS Challenge travel-time network: 1,089,933 vertices and
  1,272,922 undirected edges, with per-vertex coordinates. `scripts/download.sh` puts it in `data/downloads/nw/`.
- **Objects**: 8 real OpenStreetMap POI categories mapped to vertices (`data/downloads/nw/pois/`, between
  50 and 5,099 objects each), plus uniform random vertex samples with density d = |P|/|V|.

## Settings

| File | Evaluator | Travel times | Object sets | Queries |
|---|---|---|---|---|
| `scoring/scores.json` | `eval/evaluate.py` (paper setting) | original | real POI categories as published, plus uniform d=0.001 (d=0.01 for range) | public seed |
| `scoring/scores_train.json` | `eval/train/evaluate.py` | public perturbation of the original | jittered real POIs or uniform samples, a fresh set per query | public seed |
| `scoring/scores_test.json` | `eval/test/evaluate.py` | hidden perturbation | hidden draws | hidden |

Query defaults follow the paper (Table 4). kFN uses k=10. AkNN uses k=10, |Q|=8 vertices from a connected
subnetwork holding 15% of the vertices, and alternates max and sum. Range uses r = 2.5% of the network diameter.

## Submission format

A method is a directory `experiment_results/<name>/` containing `submission.json`:

```json
{"command": ["python3", "path/to/solver.py", "..."],
 "structures": {"kfn": "a.json", "aknn": "b.json", "range": "c.json"}}
```

The command runs with the workspace root as its working directory. Each structure (format
`hier-landmark-v1`, see `data/structure_io.py`) is a rooted tree of nodes:

- `parent`: list of node parents. Node 0 is the root and has parent -1.
- `landmarks`: list of landmark vertices per node. Each node's landmarks must lie inside that node's vertex set.
- `leaf_of`: the leaf node of every vertex. A node's vertex set is the union of the leaves below it.

For every node n and landmark l of n, the evaluator computes d(l, v) for all v in the node's vertex set,
using exact distances in the full evaluation network. **Index size** is the total number of these entries.
**Construction work** is the number of vertices a shortest-path search from each landmark settles before
it covers that node's vertex set.

Budget: at most 40 entries per vertex for kFN and 24 for AkNN and range. Construction work may be at most
3,000 settled vertices per vertex for kFN and 600 for AkNN and range. Leaves need at least 128 vertices,
nodes at most 32 landmarks, and a structure at most 200,000 nodes.

## Protocol

The solver speaks JSON lines on stdin/stdout. `data/oracle_client.py` wraps the protocol. The solver
runs with the workspace root as its working directory, in its own user, mount and pid namespaces. There,
`eval/`, `.git` and `data/downloads/` are empty and `/proc` shows only the solver's processes. The raw
public data (travel times, coordinates, POI files) is therefore available to index construction, which
runs before evaluation, but not to the solver while it answers. Everything else in the workspace (its
code, the `data/*.py` modules, its structure files) is readable as usual.

1. The evaluator sends `{"type":"hello","task":...,"n_vertices":...,"structure":path}` and the solver replies `{"type":"ready"}`.
2. The evaluator sends `{"type":"landmarks","records":{v: record(v)}}` for every landmark vertex, and the solver replies `{"type":"ok"}`.
   `record(v)` is the list of d(l, v) for every landmark l on the root-to-leaf path of v, in path and landmark order.
3. Per query, the evaluator sends `{"type":"query","kind":..., "q":[...], "q_records":[...], "n_objects":|P|, "root":summary(0), "k"/"agg"/"radius"}`.
   The solver may then send requests, either singly or as `{"op":"batch","reqs":[...]}`:
   - `nodes(ids)`: per-node summary `[count, mins, maxs]`. These are the element-wise min and max of the
     record prefix (the landmarks of the node and its ancestors) over the query's objects inside that node.
   - `peek(node,pos,idx)` and `bisect(node,pos,x)`: read the sorted list of `record[pos]` values
     over the node's objects (an object distance list) without learning which objects they belong to.
   - `get(node,pos,lo,hi)`: reveal the objects at ranks [lo, hi) of that list, with their records.
   - `dist(qi, vertices)`: exact network distances from query vertex `qi`.

   What is counted: every object revealed by `get`, passed to `dist` or returned. Also counted: every
   non-root node that holds at least one of the query's objects and is accessed by any request (once per
   query). Nodes with no objects, and the root (whose summary comes with the query), are free. Every
   distinct `dist` pair is counted.
   - `answer(result)`: object ids. A range answer is the full in-range set. kFN and AkNN answers are exactly k objects.
4. `{"type":"bye"}` ends the session.

## Metrics (per experiment `kfn`, `aknn`, `range`)

- `log10_candidate_reduction` (primary, higher is better): mean of log10((|P|+1)/(candidates+1)), floored at 0.
  Candidates are the objects revealed plus the non-empty index nodes accessed (see Protocol). An object
  counts as revealed if it is returned by `get`, passed to `dist`, or included in the answer.
- `log10_call_reduction` (higher is better): mean of log10((|Q||P|+1)/(distinct (query vertex, vertex) `dist` pairs+1)).
- `exact_answer_rate` (constraint, must be 1.0): every answer is checked against the evaluator's own Dijkstra.
  Ties at the k-th distance are accepted.
- `index_entries_per_vertex` and `sdl_work_per_vertex` (constraints, lower is better): index size and construction cost.

A method that fails anything gets the worst value of every metric in every experiment. Worst values:
0 for the three rates and reductions, and the cap for index size and construction work. Failures include:
- an invalid or over-budget structure
- a crash or a protocol error
- a timeout: 2 h of the solver's own answering time per task, or 15 min without a message
- a single inexact answer

## How to run

```bash
bash scripts/method.sh && bash scripts/baseline.sh   # build submissions
bash scripts/evaluate.sh          # paper setting -> scoring/scores.json
bash scripts/evaluate_train.sh    # public split  -> scoring/scores_train.json
bash scripts/evaluate_test.sh     # held-out      -> scoring/scores_test.json
```

Each evaluator scores every directory under `experiment_results/`. Only method directories may be placed there.
