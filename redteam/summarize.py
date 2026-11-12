#!/usr/bin/env python3
"""Summarize actual hidden-test outputs; ranking analysis never changes them."""
import json
import math
from pathlib import Path
import statistics

BASE = Path('/home/user/redteam')
reference_spec = json.loads((BASE / 'original/scoring/reference.json').read_text())['experiments']


def values(path):
    raw = json.loads(path.read_text())
    return {exp: next(iter(row['results'].values())) for exp, row in raw.items() if row['results']}


reference = values(BASE / 'original/scoring/scores_test.json')
attempts = {folder.name: values(folder / 'scores_test.json')
            for folder in BASE.iterdir() if (folder / 'scores_test.json').exists()}


def rank(candidate, scales):
    score = 0
    terms = {}
    for exp, spec in reference_spec.items():
        for metric, rule in spec['metrics'].items():
            coefficient = abs(rule['coefficient'])
            if not coefficient:
                continue
            a = candidate.get(exp, {}).get(metric)
            b = reference.get(exp, {}).get(metric)
            scale = scales.get((exp, metric), 0)
            if a is None or b is None or not scale:
                continue
            sign = 1 if rule['higher_is_better'] else -1
            term = spec['weight'] * coefficient * sign * (a-b) / scale
            score += term
            terms[exp + '.' + metric] = term
    return score, terms


def scales_for(population):
    result = {}
    for exp, spec in reference_spec.items():
        for metric in spec['metrics']:
            xs = [row[exp][metric] for row in population if metric in row.get(exp, {})]
            result[exp, metric] = statistics.pstdev(xs) if len(xs) > 1 else 0
    return result


honest_names = ['reference_seed42', 'reference_seed43', 'reference_seed44',
                'stronger_landmarks', 'shortcut_faster_bfs', 'weaker_bruteforce']
honest_scales = scales_for([reference] + [attempts[n] for n in honest_names if n in attempts])
summary = {'ranking_note': 'The future attempt population is unknown. pairwise_rank_delta uses '
    'population SD over [shipped reference, this attempt], with reference rank 0. '
    'honest_cohort_rank_delta uses one fixed SD across the shipped reference and '
    'the three reference seeds, stronger landmarks, faster BFS, and brute force. '
    'Both use absolute coefficients, declared better direction, experiment weights, '
    'and skip absent metrics. Scores are not sums in native metric units.',
    'shipped_reference': reference, 'attempts': {}}
for name, candidate in sorted(attempts.items()):
    pair_score, terms = rank(candidate, scales_for([reference, candidate]))
    score, honest_terms = rank(candidate, honest_scales)
    summary['attempts'][name] = {'metrics': candidate, 'pairwise_rank_delta': pair_score,
        'pairwise_terms': terms, 'honest_cohort_rank_delta': score,
        'status': json.loads((BASE/name/'status.json').read_text())}

seed_names = ['reference_seed42', 'reference_seed43', 'reference_seed44']
summary['seed_spread'] = {}
for exp, rules in reference_spec.items():
    summary['seed_spread'][exp] = {}
    for metric in rules['metrics']:
        xs = [attempts[n][exp][metric] for n in seed_names if n in attempts and metric in attempts[n][exp]]
        if xs:
            summary['seed_spread'][exp][metric] = {'min': min(xs), 'max': max(xs),
                'range': max(xs)-min(xs), 'population_sd': statistics.pstdev(xs)}
seed_ranks = [summary['attempts'][n]['honest_cohort_rank_delta'] for n in seed_names if n in attempts]
summary['seed_rank_spread'] = {'values': dict(zip(seed_names, seed_ranks)),
    'range': max(seed_ranks)-min(seed_ranks), 'population_sd': statistics.pstdev(seed_ranks)}

summary['timings'] = {}
for name in honest_names:
    source = BASE / name / 'artifacts.json'
    if not source.exists():
        continue
    records = json.loads(source.read_text())
    summary['timings'][name] = [{'query_type': r['query_type'], 'density': r['density'],
        'n_queries': len(r['queries']['individual_correct']),
        'query_time_ms': r['queries']['col_avg_time_ms'],
        'brute_time_ms': r['queries'].get('brute_avg_time_ms'),
        'aub_time_ms': r['queries'].get('aub_avg_time_ms'),
        'candidate_avg': r['queries']['col_candidate_objects_avg'],
        'exact_avg': r['queries'].get('col_exact_lookups_avg'),
        'aub_exact_avg': r['queries'].get('aub_exact_lookups_avg'),
        'build_seconds': r['sul_time']+r['col_time']} for r in records]

for name in ['shortcut_nulls', 'shortcut_missing_flags']:
    if (BASE/name/'status.json').exists():
        summary.setdefault('failed_commands', {})[name] = json.loads((BASE/name/'status.json').read_text())

(BASE/'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({name: {k: row[k] for k in ['pairwise_rank_delta', 'honest_cohort_rank_delta']}
                  for name, row in summary['attempts'].items()}, indent=2))
