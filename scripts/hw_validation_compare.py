#!/usr/bin/env python3
"""Parse hardware validation logs without inferring missing measurements."""

import argparse
import csv
import json
import math
import re
import statistics
from pathlib import Path
from collections import Counter


STATUSES = {'PASS', 'FAIL', 'SKIP', 'INCONCLUSIVE', 'VISUAL_REVIEW_REQUIRED'}
RUN_FIELDS = ('run_id', 'sha', 'board', 'driver', 'width', 'height', 'rotation',
              'cpu_hz', 'spi_hz', 'wifi', 'flags', 'reset_reason', 'heap', 'max_block')


def _empty_run(source, records):
    return {'status': 'INCONCLUSIVE', 'warnings': [], 'raw_records': records,
            'cases': {}, 'rotation_events': [], 'bench': [], 'stress_progress': [], 'stress_end': [],
            'stress_warnings': [], 'metadata': {}, 'source': source}


def _integer(value, minimum=0, maximum=None):
    if not value or not value.isascii() or not value.isdigit():
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= minimum and (maximum is None or number <= maximum) else None


def parse_log(lines, source='<memory>'):
    records = [line.rstrip('\r\n') for line in lines]
    result = _empty_run(source, records)
    rows = []
    try:
        rows = list(csv.reader(records, strict=True))
    except csv.Error as error:
        result['warnings'].append('Malformed CSV: {}'.format(error))
    if not rows or rows[0] != ['HWTEST', '2']:
        if rows and rows[0][:1] == ['HWTEST']:
            version = rows[0][1] if len(rows[0]) > 1 else 'unknown'
            result['warnings'].append('Legacy or unsupported protocol version {}'.format(version))
        else:
            result['warnings'].append('Missing HWTEST,2 protocol header')
        return result

    runs = []
    starts = {}
    returns = set()
    cases = result['cases']
    ready = False
    active_rotation = None
    for row in rows[1:]:
        if not row:
            continue
        if row[0] == 'RUN':
            if len(row) != len(RUN_FIELDS) + 1:
                result['warnings'].append('Truncated or malformed RUN row')
                continue
            metadata = dict(zip(RUN_FIELDS, row[1:]))
            for key in ('run_id', 'sha', 'board', 'driver', 'wifi', 'flags', 'reset_reason'):
                if any(ord(char) < 32 or ord(char) > 126 or char == ','
                       for char in metadata[key]):
                    result['warnings'].append('Unsafe RUN token {}'.format(key))
            for key in ('width', 'height', 'rotation', 'cpu_hz', 'spi_hz', 'heap', 'max_block'):
                parsed = _integer(metadata[key], maximum=3 if key == 'rotation' else None)
                if parsed is None or (key in ('width', 'height', 'cpu_hz', 'spi_hz') and parsed == 0):
                    result['warnings'].append('Invalid RUN field {}'.format(key))
                    continue
                metadata[key] = parsed
            runs.append(metadata)
            active_rotation = metadata.get('rotation') if isinstance(metadata.get('rotation'), int) else None
        elif row[0] == 'ROTATION':
            rotation = _integer(row[1], maximum=3) if len(row) == 2 else None
            if rotation is None:
                active_rotation = None
                result['warnings'].append('Malformed ROTATION row')
            else:
                active_rotation = rotation
                result['rotation_events'].append(rotation)
        elif row[0] == 'CASE' and len(row) > 1 and row[1] == 'START':
            if len(row) != 4 or not row[2] or _integer(row[3], maximum=0xFFFFFFFF) is None:
                result['warnings'].append('Malformed CASE,START row')
            elif row[2] in starts:
                starts[row[2]] += 1
                cases[row[2]] = {'status': 'INCONCLUSIVE', 'warnings': ['Duplicate CASE,START']}
                result['warnings'].append('Duplicate CASE,START for {}'.format(row[2]))
            else:
                starts[row[2]] = 1
                cases[row[2]] = {'status': 'INCONCLUSIVE', 'seed': int(row[3]),
                                 'rotation': active_rotation, 'warnings': []}
        elif row[0] == 'CASE' and len(row) > 1 and row[1] == 'RETURN':
            if len(row) != 7 or row[6] not in STATUSES or any(
                    _integer(v, maximum=0xFFFFFFFF) is None for v in row[3:6]):
                result['warnings'].append('Malformed CASE,RETURN row')
            elif row[2] not in starts or starts[row[2]] != 1:
                result['warnings'].append('CASE,RETURN without unique start for {}'.format(row[2]))
                cases[row[2]] = {'status': 'INCONCLUSIVE', 'warnings': ['Missing unique start']}
            elif row[2] in returns:
                case = cases[row[2]]
                case['status'] = 'FAIL' if case['status'] == 'FAIL' or row[6] == 'FAIL' else 'INCONCLUSIVE'
                case.setdefault('warnings', []).append('Duplicate CASE,RETURN')
                result['warnings'].append('Duplicate CASE,RETURN for {}'.format(row[2]))
            else:
                returns.add(row[2])
                cases[row[2]].update({'status': row[6], 'elapsed_us': int(row[3]),
                                      'heap': int(row[4]), 'max_block': int(row[5])})
        elif row == ['READY']:
            ready = True
        elif row[0] == 'BENCH':
            if len(row) == 9:
                parsed = [_integer(v, maximum=0xFFFFFFFF) for v in row[2:]
                          if v != '']
                if (not row[1] or len(parsed) != 7 or any(v is None for v in parsed)
                        or parsed[0] not in (1, 2, 3)
                        or parsed[2] == 0 or parsed[3] == 0):
                    result['warnings'].append('Malformed BENCH row')
                else:
                    result['bench'].append({'scenario': row[1], 'round': parsed[0],
                                             'sample': parsed[1], 'repetitions': parsed[2],
                                             'total_us': parsed[3], 'heap_before': parsed[4],
                                             'heap_after': parsed[5], 'max_block': parsed[6]})
            # Legacy BENCH records remain available in raw_records only.
        elif row[0] == 'STRESS' and len(row) == 8 and row[1] == 'PROGRESS':
            values = [_integer(v, maximum=0xFFFFFFFF) for v in row[3:8]]
            if not row[2] or any(value is None for value in values):
                result['warnings'].append('Malformed STRESS,PROGRESS row')
            else:
                result['stress_progress'].append({'id': row[2], 'cycles': values[0],
                    'elapsed_ms': values[1], 'heap': values[2], 'max_block': values[3],
                    'fragmentation': values[4]})
        elif row[0] == 'STRESS' and len(row) == 9 and row[1] == 'END':
            values = [_integer(v, maximum=0xFFFFFFFF) for v in row[3:8]]
            if not row[2] or any(value is None for value in values) or row[8] not in STATUSES:
                result['warnings'].append('Malformed STRESS,END row')
            else:
                result['stress_end'].append({'id': row[2], 'cycles': values[0],
                    'elapsed_ms': values[1], 'heap': values[2], 'max_block': values[3],
                    'fragmentation': values[4], 'status': row[8]})
        elif row[:2] == ['STRESS', 'WARNING']:
            result['stress_warnings'].append(','.join(row[2:]))
        else:
            result['warnings'].append('Unknown or malformed record')

    if len(runs) != 1:
        result['warnings'].append('Expected exactly one valid RUN row')
    else:
        result['metadata'] = runs[0]
        required = ('run_id', 'sha', 'board', 'driver', 'width', 'height', 'rotation',
                    'cpu_hz', 'spi_hz', 'wifi', 'flags')
        if any(result['metadata'].get(key) in (None, '') for key in required):
            result['warnings'].append('RUN metadata is insufficient for comparison')
        unknown_fields = ('sha', 'board', 'driver', 'wifi', 'flags')
        if any(result['metadata'].get(key, '').lower() == 'unknown' for key in unknown_fields):
            result['warnings'].append('Unknown RUN metadata is not comparable')
    if not ready:
        result['warnings'].append('Missing READY marker')
    for case_id in starts:
        if starts[case_id] == 1 and cases[case_id]['status'] == 'INCONCLUSIVE':
            result['warnings'].append('Incomplete case {}'.format(case_id))

    statuses = [case['status'] for case in cases.values()]
    if 'FAIL' in statuses:
        result['status'] = 'FAIL'
    elif result['warnings'] or not statuses:
        result['status'] = 'INCONCLUSIVE'
    elif 'VISUAL_REVIEW_REQUIRED' in statuses:
        result['status'] = 'VISUAL_REVIEW_REQUIRED'
    elif all(status == 'SKIP' for status in statuses):
        result['status'] = 'SKIP'
    elif all(status in ('PASS', 'SKIP') for status in statuses):
        result['status'] = 'PASS'
    return result


def summarize_run(parsed):
    counts = Counter(case.get('status', 'INCONCLUSIVE') for case in parsed['cases'].values())
    scenarios = {}
    for row in parsed.get('bench', []):
        scenarios.setdefault(row['scenario'], []).append(row)
    return {'status': parsed['status'], 'warnings': list(parsed['warnings']),
            'raw_records': list(parsed['raw_records']), 'cases': parsed['cases'],
            'bench': list(parsed.get('bench', [])),
            'rotation_events': list(parsed.get('rotation_events', [])),
            'bench_statistics': {name: bench_statistics(rows) for name, rows in scenarios.items()},
            'stress': summarize_stress(parsed),
            'case_counts': dict(counts), 'metadata': dict(parsed['metadata']),
            'source': parsed['source']}


def bench_statistics(rows):
    if not rows:
        return {'status': 'INCONCLUSIVE', 'reason': 'No benchmark samples'}
    by_round = {round_number: {} for round_number in (1, 2, 3)}
    values = []
    for row in rows:
        round_number = row.get('round')
        repetitions, total = row.get('repetitions'), row.get('total_us')
        if round_number not in by_round or not repetitions or not total:
            return {'status': 'INCONCLUSIVE', 'reason': 'Invalid or out-of-range sample'}
        samples = by_round[round_number]
        sample_number = row.get('sample')
        if sample_number in samples:
            return {'status': 'INCONCLUSIVE', 'reason': 'Duplicate sample number'}
        samples[sample_number] = row
        values.append(total / repetitions)
    if any(len(samples) < 10 for samples in by_round.values()):
        return {'status': 'INCONCLUSIVE', 'reason': 'Each of three rounds needs at least ten samples'}
    ordered = sorted(values)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    return {'status': 'OK', 'median_us': round(statistics.median(values), 6),
            'p95_us': round(p95, 6), 'min_us': round(ordered[0], 6),
            'max_us': round(ordered[-1], 6), 'samples': len(values), 'rounds': 3}


def classify_regression(base_median, cand_median, base_p95, cand_p95,
                        med_pct=10.0, p95_pct=15.0, min_abs_us=2.0):
    median_slow = cand_median - base_median
    p95_slow = cand_p95 - base_p95
    if ((median_slow > min_abs_us and median_slow / base_median * 100 > med_pct)
            or (p95_slow > min_abs_us and p95_slow / base_p95 * 100 > p95_pct)):
        return 'REGRESSION_CANDIDATE'
    return 'OK'


def summarize_stress(run):
    progress = run.get('stress_progress', [])
    endings = run.get('stress_end', [])
    samples = progress + endings
    heap_values = [entry['heap'] for entry in samples]
    block_values = [entry['max_block'] for entry in samples]
    result = {'cycles': endings[0]['cycles'] if len(endings) == 1 else
                         (progress[-1]['cycles'] if progress else 0),
              'elapsed_ms': endings[0]['elapsed_ms'] if len(endings) == 1 else
                            (progress[-1]['elapsed_ms'] if progress else 0),
              'min_heap': min(heap_values) if heap_values else None,
              'min_block': min(block_values) if block_values else None,
              'trend': [{'cycles': p['cycles'], 'heap': p['heap'], 'max_block': p['max_block']}
                        for p in progress],
              'heap_drop_warning': 'HEAP_DROP' in run.get('stress_warnings', []),
              'status': 'INCONCLUSIVE', 'reason': 'Missing complete STRESS,END'}
    if len(endings) != 1 or run.get('warnings'):
        return result
    end = endings[0]
    if any(p['id'] != end['id'] for p in progress):
        result['reason'] = 'Mixed stress profiles'
        return result
    if end['id'] == 'L':
        if [p['cycles'] for p in progress] != list(range(1000, 10001, 1000)) or end['cycles'] != 10000:
            result['reason'] = 'Missing or invalid L checkpoints'
            return result
    elif end['id'] == 'E30':
        if end['status'] != 'PASS' or end['elapsed_ms'] < 1800000:
            result['reason'] = 'E30 did not complete its full duration'
            return result
    elif end['id'] == 'M':
        if end['status'] not in ('PASS', 'SKIP', 'INCONCLUSIVE'):
            result['reason'] = 'Invalid M result'
            return result
    else:
        result['reason'] = 'Unknown stress profile'
        return result
    result['status'] = end['status']
    result['reason'] = ('Post-cleanup heap drop needs investigation'
                        if result['heap_drop_warning'] else '')
    if result['heap_drop_warning'] and result['status'] == 'PASS':
        result['status'] = 'INCONCLUSIVE'
    return result


def compare_benchmarks(baseline_runs, candidate_runs, med_pct=10.0,
                       p95_pct=15.0, min_abs_us=2.0):
    if not baseline_runs:
        return {'status': 'NO_BASELINE', 'reasons': ['No baseline runs']}
    if len(baseline_runs) < 5 or len(candidate_runs) < 5:
        return {'status': 'INCONCLUSIVE', 'reasons': ['Need five independently booted baseline and candidate runs']}
    if any(run.get('warnings') for run in baseline_runs + candidate_runs):
        return {'status': 'INCONCLUSIVE', 'reasons': ['A run contains protocol warnings']}
    if any(run.get('metadata', {}).get('flags') == 'dirty'
           for run in baseline_runs + candidate_runs):
        return {'status': 'INCONCLUSIVE', 'reasons': ['Dirty source builds are not comparable']}
    profile_fields = ('board', 'driver', 'width', 'height', 'rotation', 'cpu_hz',
                      'spi_hz', 'wifi', 'flags')
    profile = baseline_runs[0].get('metadata', {})
    if any(not run.get('metadata') or any(run['metadata'].get(key) in (None, '')
                                           for key in profile_fields)
           for run in baseline_runs + candidate_runs):
        return {'status': 'INCONCLUSIVE', 'reasons': ['Missing profile metadata']}
    mismatches = sorted({field for run in baseline_runs + candidate_runs
                         for field in profile_fields
                         if run.get('metadata', {}).get(field) != profile.get(field)})
    if mismatches:
        return {'status': 'INCOMPATIBLE', 'reasons': ['Mismatched profile: ' + ', '.join(mismatches)]}
    if (len({run.get('metadata', {}).get('run_id') for run in baseline_runs}) < 5
            or len({run.get('metadata', {}).get('run_id') for run in candidate_runs}) < 5):
        return {'status': 'INCONCLUSIVE', 'reasons': ['Boot IDs are not distinct']}
    if (len({run.get('metadata', {}).get('sha') for run in baseline_runs}) != 1
            or len({run.get('metadata', {}).get('sha') for run in candidate_runs}) != 1):
        return {'status': 'INCONCLUSIVE', 'reasons': ['Each revision needs one consistent SHA']}
    if any(run.get('metadata', {}).get('sha', '').lower() in ('', 'unknown')
           for run in baseline_runs + candidate_runs):
        return {'status': 'INCONCLUSIVE', 'reasons': ['Each run needs a known SHA']}
    def combine(runs):
        grouped = {}
        for run in runs:
            per_run = {}
            for row in run.get('bench', []):
                per_run.setdefault(row['scenario'], []).append(row)
            for scenario, rows in per_run.items():
                grouped.setdefault(scenario, []).append(bench_statistics(rows))
        return grouped
    baseline, candidates = combine(baseline_runs), combine(candidate_runs)
    if not baseline or set(baseline) != set(candidates):
        return {'status': 'INCONCLUSIVE', 'reasons': ['Benchmark scenario sets differ']}
    expected_scenarios = set(baseline)
    for run in baseline_runs + candidate_runs:
        if {row['scenario'] for row in run.get('bench', [])} != expected_scenarios:
            return {'status': 'INCONCLUSIVE', 'reasons': ['A boot is missing a benchmark scenario']}
    results = {}
    for scenario in sorted(baseline):
        base_runs, candidate_run_stats = baseline[scenario], candidates[scenario]
        if (len(base_runs) != len(baseline_runs) or len(candidate_run_stats) != len(candidate_runs)
                or any(s['status'] != 'OK' for s in base_runs + candidate_run_stats)):
            return {'status': 'INCONCLUSIVE', 'reasons': ['Incomplete samples or boots for ' + scenario]}
        base_stats = {'median_us': round(statistics.median(s['median_us'] for s in base_runs), 6),
                      'p95_us': round(statistics.median(s['p95_us'] for s in base_runs), 6),
                      'boots': len(base_runs)}
        candidate_stats = {'median_us': round(statistics.median(s['median_us'] for s in candidate_run_stats), 6),
                           'p95_us': round(statistics.median(s['p95_us'] for s in candidate_run_stats), 6),
                           'boots': len(candidate_run_stats)}
        results[scenario] = {'status': classify_regression(
            base_stats['median_us'], candidate_stats['median_us'], base_stats['p95_us'],
            candidate_stats['p95_us'], med_pct, p95_pct, min_abs_us),
            'baseline': base_stats, 'candidate': candidate_stats}
    status = ('REGRESSION_CANDIDATE' if any(r['status'] == 'REGRESSION_CANDIDATE'
                                            for r in results.values()) else 'OK')
    return {'status': status, 'reasons': [], 'scenarios': results}


def _safe_metadata(metadata):
    allowed = ('run_id', 'sha', 'board', 'driver', 'width', 'height', 'rotation',
               'cpu_hz', 'spi_hz', 'wifi', 'flags', 'reset_reason')
    safe = {key: metadata.get(key) for key in allowed if key in metadata}
    if safe.get('wifi') not in ('off', 'on', 'sta', 'ap', 'unknown'):
        safe['wifi'] = 'redacted'
    if safe.get('flags') not in ('default', 'unknown', 'minimal', 'dirty'):
        safe['flags'] = 'redacted'
    return safe


def _safe_text(value):
    text = str(value)
    text = re.sub(r'(?i)(password|passphrase|token|secret|api[_-]?key)(\s*[:=]\s*)[^\s,;|]+',
                  r'\1\2[redacted]', text)
    return text.replace('\n', ' ').replace('\r', ' ')


def generate_report(runs, comparison=None):
    report_runs = []
    for run in runs:
        scenarios = {}
        for row in run.get('bench', []):
            scenarios.setdefault(row['scenario'], []).append(row)
        item = {'source': _safe_text(run.get('source', '<memory>')), 'status': run.get('status', 'INCONCLUSIVE'),
                'warnings': [_safe_text(warning) for warning in run.get('warnings', [])],
                'metadata': _safe_metadata(run.get('metadata', {})),
                'cases': {_safe_text(case_id): {'status': case.get('status', 'INCONCLUSIVE'),
                                    'rotation': case.get('rotation'),
                                    'warnings': [_safe_text(w) for w in case.get('warnings', [])]}
                          for case_id, case in run.get('cases', {}).items()},
                'bench': [dict(row, scenario=_safe_text(row['scenario']))
                          for row in run.get('bench', [])],
                'rotation_events': list(run.get('rotation_events', [])),
                'bench_statistics': {_safe_text(name): bench_statistics(rows)
                                     for name, rows in scenarios.items()},
                'stress': summarize_stress(run)}
        report_runs.append(item)
    comparison = ({**comparison, 'reasons': [_safe_text(reason) for reason in comparison.get('reasons', [])]}
                  if comparison else None)
    baseline_status = comparison.get('status', 'INCONCLUSIVE') if comparison else 'NO_BASELINE'
    report = {'schema_version': 1, 'status': comparison.get('status') if comparison else
              (report_runs[0]['status'] if len(report_runs) == 1 else 'INCONCLUSIVE'),
              'baseline_status': baseline_status, 'comparison': comparison or {}, 'runs': report_runs}
    lines = ['# Hardware validation report', '', 'Status: **{}**'.format(report['status']),
             'Baseline status: **{}**'.format(baseline_status), '']
    for index, run in enumerate(report_runs, 1):
        lines.extend(['## Run {}'.format(index), '', 'Source: `{}`'.format(run['source']),
                      'Status: **{}**'.format(run['status']),
                      'Profile: `{}`'.format(json.dumps(run['metadata'], sort_keys=True)), ''])
        if run['warnings']:
            lines.append('Warnings: ' + '; '.join(str(w).replace('\n', ' ') for w in run['warnings']))
            lines.append('')
        if run['cases']:
            lines.extend(['| Case | Rotation | Status |', '| --- | ---: | --- |'])
            lines.extend('| {} | {} | {} |'.format(case.replace('|', '\\|'),
                         value.get('rotation', '—'), value['status'])
                         for case, value in run['cases'].items())
            lines.append('')
        if run['bench_statistics']:
            lines.extend(['| Benchmark | Status | Median µs/op | p95 µs/op |',
                          '| --- | --- | ---: | ---: |'])
            for name, stats in run['bench_statistics'].items():
                lines.append('| {} | {} | {} | {} |'.format(
                    name.replace('|', '\\|'), stats.get('status'),
                    stats.get('median_us', '—'), stats.get('p95_us', '—')))
            lines.append('')
    if comparison:
        lines.extend(['## Comparison', '', 'Status: **{}**'.format(comparison.get('status', 'INCONCLUSIVE')), ''])
        lines.extend('- ' + str(reason).replace('\n', ' ') for reason in comparison.get('reasons', []))
        if comparison.get('scenarios'):
            lines.extend(['', '| Benchmark | Status | Baseline median | Candidate median |',
                          '| --- | --- | ---: | ---: |'])
            for name, result in comparison['scenarios'].items():
                lines.append('| {} | {} | {} | {} |'.format(
                    _safe_text(name).replace('|', '\\|'), result['status'],
                    result['baseline']['median_us'], result['candidate']['median_us']))
    else:
        lines.append('No baseline supplied; no performance delta was calculated.')
    return report, '\n'.join(lines).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', nargs='?', help='serial log to parse')
    parser.add_argument('--baseline', help='approved JSON report containing baseline runs')
    parser.add_argument('--candidate', action='append', help='candidate log or directory; repeatable')
    parser.add_argument('--output-dir', default='.build/hardware/results')
    args = parser.parse_args()
    if args.baseline or args.candidate:
        if args.baseline and not args.candidate:
            parser.error('--baseline requires at least one --candidate')
        paths = []
        for candidate in args.candidate or []:
            path = Path(candidate)
            paths.extend(sorted(path.glob('*.log')) if path.is_dir() else [path])
        if args.candidate and not paths:
            parser.error('candidate input contains no log files')
        candidate_runs = [parse_log(path.read_text(encoding='utf-8').splitlines(), str(path))
                          for path in paths]
        if args.baseline:
            with open(args.baseline, encoding='utf-8') as baseline_file:
                baseline_doc = json.load(baseline_file)
            comparison = compare_benchmarks(baseline_doc.get('runs', []), candidate_runs)
            report, markdown = generate_report(candidate_runs, comparison)
        else:
            report, markdown = generate_report(candidate_runs)
    else:
        if not args.log:
            parser.error('a log path is required unless --baseline and --candidate are supplied')
        parsed = parse_log(Path(args.log).read_text(encoding='utf-8').splitlines(), args.log)
        report, markdown = generate_report([parsed])
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = (report.get('runs') or [{}])[0].get('metadata', {}).get('run_id', 'validation')
    stem = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(run_id))[:80] or 'validation'
    json_path, markdown_path = output_dir / (stem + '.json'), output_dir / (stem + '.md')
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(markdown, encoding='utf-8')
    print(json.dumps({'status': report['status'], 'baseline_status': report['baseline_status'],
                      'json': str(json_path), 'markdown': str(markdown_path)}, indent=2))


if __name__ == '__main__':
    main()
