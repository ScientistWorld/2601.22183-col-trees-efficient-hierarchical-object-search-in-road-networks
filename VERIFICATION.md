# Verification Report

## Initial Assessment

The previous workflow had reached `secondary_claims`, then a deeper audit temporarily reset the workspace to `method_runs` because saved artifacts were stale under the stricter evaluator. CPU job `714f3f12-b67` has now regenerated the artifacts and rerun the full scoring path successfully.

## Issues Found

- **Critical, fixed**: The saved artifacts initially lacked `queries.per_query`, causing `scripts/evaluate.sh /home/user/experiment_results/core_claim` to fail under the stricter evaluator.
- **Minor**: High-level public scoring documents still named implementation structures directly in places where future from-scratch agents should only see constraints and direction.
- **Minor**: Ignored Python bytecode directories were present under source/data directories.

## Fixes Applied

- Verified both URLs in `scripts/download.sh` with `curl -I -L --max-time 15`; both returned HTTP 200.
- Confirmed committed code does not reference `/shared` paths and `eval/` does not import from `method/`.
- Tightened `briefing/evaluation.md`, `scoring/TARGETS.md`, `scoring/CONSTRAINTS.md`, and `scoring/DIRECTION.md` to keep public gym guidance focused on the task, constraints, and allowed research direction rather than implementation names.
- Ran CPU job `714f3f12-b67`; it regenerated method artifacts, ran main/train/test scoring, and passed `python3 validate.py --compare`.
- Refreshed the shipped-benchmark `colt_us48_repro` reference rows to match the post-audit regenerated target, with notes separating those replacement-benchmark targets from paper-reported rows.

## Final Judgment

The workspace is ready to serve as a research gym. Improve-mode agents can build on the reproduced method and current results. From-scratch agents can use the problem, data, evaluation, scoring, and high-level constraints without relying on method internals. The main limitation is that this gym uses an accessible US48 graph with sampled POIs instead of the original large road-network/real-POI/PHL setup.

- Milestone: secondary_claims
- Ready for gym use: yes
- Confidence: high
- Key limitation: shipped US48/synthetic-POI replacement benchmark rather than the paper's original full-scale data and distance-oracle setup.
