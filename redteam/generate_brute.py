#!/usr/bin/env python3
"""Honest exhaustive baseline on exactly the reference workload.

Enumeration computes real answers from the visible graph and query seeds.
The reference run is used only as the workload manifest (which the public
experiment generator also creates), never as an answer or correctness cache.
"""
import copy
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, '/home/user')
from data.loader import load_network
from data.graph import ObjectSet
from baseline.bruteforce import aknn_bruteforce, kfn_bruteforce, range_bruteforce
from method.experiment import _valid_nearest_topk, _valid_farthest_topk

dest = Path('/home/user/redteam') / sys.argv[1]
records = copy.deepcopy(json.loads(Path('/home/user/redteam/reference_seed42/artifacts.json').read_text()))
graph = load_network('/home/user/data/downloads/road-usroads-48.mtx')
for r in records:
    objects = ObjectSet.uniform_random(graph, r['density'], r['seed'])
    times, flags = [], []
    for row in r['queries']['per_query']:
        start = time.monotonic()
        if r['query_type'] == 'aknn':
            answer = aknn_bruteforce(graph, objects, row['query_vertices'], r['k'], r['agg'])
        elif r['query_type'] == 'kfn':
            answer = kfn_bruteforce(graph, objects, row['query_vertex'], r['k'])
        else:
            answer = range_bruteforce(graph, objects, row['query_vertex'], r['queries']['radius'])
        times.append(1000 * (time.monotonic() - start))
        if r['query_type'] == 'aknn':
            correct = _valid_nearest_topk(graph, answer, objects, row['query_vertices'], r['k'], r['agg'])
        elif r['query_type'] == 'kfn':
            correct = _valid_farthest_topk(graph, answer, objects, row['query_vertex'], r['k'])
        else:
            distances = graph.dijkstra(row['query_vertex'])
            correct = set(answer) == {o for o in objects.objects if distances[o] <= r['queries']['radius']}
        flags.append(int(correct))
        row.update(result=answer, candidates=len(objects), exact_lookups=len(objects))
    r['sul_time'] = r['col_time'] = 0
    n = len(flags)
    r['queries'].update(individual_correct=flags, individual_candidates=[len(objects)] * n,
        individual_exact_lookups=[len(objects)] * n, individual_times=times,
        col_avg_time_ms=sum(times)/n, col_candidate_objects_avg=len(objects),
        col_exact_lookups_avg=len(objects), correct=sum(flags), total=n, accuracy=sum(flags)/n)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'artifacts.json').write_text(json.dumps(records, indent=2) + '\n')
