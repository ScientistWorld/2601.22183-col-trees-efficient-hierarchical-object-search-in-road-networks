#!/usr/bin/env python3
"""Select the COL-Tree leaf size lambda per query type on the public split.

The paper fixes lambda by parameter testing on its own network (Section 9.6,
Table 8: lambda = 256 for every query type on the 24M-vertex US network, the
smallest value it tested).  This network is 22x smaller, so the same procedure
is repeated here on the public (train) split: scripts/tune_lambda.sh scores the
reference structures with every lambda of the grid through
eval/train/evaluate.py, and this script picks, per query type, the lambda with
the best train score

    log10_candidate_reduction + 0.5 * log10_call_reduction

(the coefficients of the two benefit metrics in scoring/reference.json; all
other metrics do not depend on lambda).  Runs with an inexact answer are
excluded.  Ties go to the larger lambda (closer to the paper's setting).

It writes experiment_results/colt/submission.json (the reference method) and
method/tuned_lambda.json (the full sweep table, the chosen values and, for the
density-adaptive probe variant only, a fitted rule lambda = exp(A) * |P|^B).

Usage: python3 method/tune_lambda.py [--sweep-dir method/tuning]
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics as st

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = ("kfn", "aknn", "range")
CAND_COEF, CALL_COEF = 1.0, 0.5


def query_score(r):
    cand = max(0.0, math.log10((r["n_objects"] + 1) / (r["cands"] + 1)))
    call = max(0.0, math.log10((r["q_size"] * r["n_objects"] + 1) / (r["calls"] + 1)))
    return CAND_COEF * cand + CALL_COEF * call


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep-dir", default=os.path.join(WS, "method", "tuning"))
    ap.add_argument("--out", default=os.path.join(WS, "method", "tuned_lambda.json"))
    ap.add_argument("--submission", default=os.path.join(WS, "experiment_results", "colt", "submission.json"))
    args = ap.parse_args()

    table, chosen, rules, per_set = {}, {}, {}, {}
    for task in TASKS:
        scores = json.load(open(os.path.join(args.sweep_dir, f"sweep_{task}.json")))[task]["results"]
        details = json.load(open(os.path.join(args.sweep_dir, f"details_{task}.json")))
        rows = {}
        for name, metrics in scores.items():
            m = re.fullmatch(r"lam(\d+)", name)
            if not m:
                continue
            lam = int(m.group(1))
            ok = metrics["exact_answer_rate"] == 1.0 and details["status"].get(name) is None
            rows[lam] = {"ok": ok,
                         "log10_candidate_reduction": metrics["log10_candidate_reduction"],
                         "log10_call_reduction": metrics["log10_call_reduction"],
                         "score": CAND_COEF * metrics["log10_candidate_reduction"]
                         + CALL_COEF * metrics["log10_call_reduction"]}
        valid = [lam for lam, r in rows.items() if r["ok"]]
        if not valid:
            raise SystemExit(f"{task}: no exact lambda run in the sweep")
        best = max(valid, key=lambda lam: (round(rows[lam]["score"], 6), lam))
        table[task] = {str(lam): rows[lam] for lam in sorted(rows)}
        chosen[task] = best

        # Density-adaptive rule (probe variant only, not the reference): the rule
        # lambda = 2^round(log2(exp(A) |P|^B)) clipped to the grid that maximises
        # the mean train query score (every grid value was run on every query).
        runs = {lam: details["per_query"][f"lam{lam}"][task] for lam in valid}
        nq = len(runs[best])
        qscore = {lam: [query_score(r) for r in rows] for lam, rows in runs.items()}
        sizes = [r["n_objects"] for r in runs[best]]
        lo, hi = min(valid), max(valid)
        pow2 = [lam for lam in valid if lam & (lam - 1) == 0]
        best_rule, best_val = (math.log(best), 0.0, lo, hi), st.mean(qscore[best])
        for b10 in range(0, 11):
            b = b10 / 10.0
            for target in pow2:
                a = math.log(target) - b * math.log(st.median(sizes))
                for shift in (-0.35, 0.0, 0.35):
                    rule = (a + shift, b, lo, hi)
                    picks = [min(hi, max(lo, 2 ** int(round((rule[0] + b * math.log(max(1, s))) / math.log(2)))))
                             for s in sizes]
                    if any(p not in qscore for p in picks):
                        continue
                    val = st.mean(qscore[p][i] for i, p in enumerate(picks))
                    if val > best_val + 1e-9:
                        best_rule, best_val = rule, val
        per_set[task] = {"train_score_fixed": st.mean(qscore[best]), "train_score_rule": best_val, "queries": nq}
        rules[task] = (round(best_rule[0], 4), best_rule[1], best_rule[2], best_rule[3])

    lam_spec = ",".join(f"{t}={chosen[t]}" for t in TASKS)
    rule_spec = ",".join(f"{t}={':'.join(str(x) for x in rules[t])}" for t in TASKS)
    record = {"objective": "log10_candidate_reduction + 0.5 * log10_call_reduction on the train split",
              "chosen": chosen, "lam_spec": lam_spec, "sweep": table,
              "adaptive_rule": rule_spec, "adaptive_rule_train": per_set}
    with open(args.out, "w") as handle:
        json.dump(record, handle, indent=1)
        handle.write("\n")
    sub = {"command": ["python3", "method/solver.py", "--lam", lam_spec, "--bounds", "paper"],
           "structures": {"kfn": "sul_kfn.json", "aknn": "sul_aknn.json", "range": "sul_range.json"}}
    with open(args.submission, "w") as handle:
        json.dump(sub, handle)
        handle.write("\n")
    for task in TASKS:
        print(f"{task}: " + "  ".join(f"lam={lam}:{r['score']:.3f}{'' if r['ok'] else '(x)'}"
                                      for lam, r in table[task].items()) + f"  -> {chosen[task]}")
    print(f"colt: --lam {lam_spec}   (adaptive probe rule: {rule_spec})")


if __name__ == "__main__":
    main()
