import unittest
from pathlib import Path

from scripts.hw_validation_compare import (bench_statistics, classify_regression,
                                           compare_benchmarks, generate_report, parse_log, summarize_run,
                                           summarize_stress)


RUN = 'RUN,run1,abc123,nodemcuv2,ST7789,240,240,0,80000000,40000000,off,default,POWERON,45000,30000'


class HardwareValidationParserTests(unittest.TestCase):
    def test_protocol_fixtures(self):
        root = Path('tests/fixtures/hw_validation')
        expected = {'valid-v2.log': 'PASS', 'truncated-v2.log': 'INCONCLUSIVE',
                    'duplicate-v2.log': 'INCONCLUSIVE', 'legacy-v1.log': 'INCONCLUSIVE',
                    'duplicate-return-v2.log': 'INCONCLUSIVE', 'smoke-main.log': 'INCONCLUSIVE'}
        for name, status in expected.items():
            with self.subTest(fixture=name):
                run = parse_log((root / name).read_text().splitlines(), name)
                self.assertEqual(run['status'], status)

    def test_valid_run_and_case(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,fill,7',
                         'CASE,RETURN,fill,4,44900,29900,PASS', 'READY'], 'valid.log')
        self.assertEqual(run['status'], 'PASS')
        self.assertEqual(run['cases']['fill']['status'], 'PASS')
        self.assertEqual(summarize_run(run)['case_counts']['PASS'], 1)

    def test_rotation_records_are_attached_to_each_case_and_report(self):
        run = parse_log(['HWTEST,2', RUN, 'ROTATION,2', 'CASE,START,edge_clipping,0',
                         'CASE,RETURN,edge_clipping,20,44990,29990,VISUAL_REVIEW_REQUIRED',
                         'READY'], 'rotation.log')
        self.assertEqual(run['status'], 'VISUAL_REVIEW_REQUIRED')
        self.assertEqual(run['cases']['edge_clipping']['rotation'], 2)
        report, _ = generate_report([run])
        self.assertEqual(report['runs'][0]['cases']['edge_clipping']['rotation'], 2)

    def test_out_of_range_run_rotation_is_inconclusive(self):
        invalid = RUN.replace(',240,240,0,', ',240,240,4,')
        run = parse_log(['HWTEST,2', invalid, 'CASE,START,edge,0',
                         'CASE,RETURN,edge,1,44990,29990,PASS', 'READY'], 'bad-run-rotation.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertIn('Invalid RUN field rotation', run['warnings'])

    def test_invalid_rotation_record_is_inconclusive(self):
        run = parse_log(['HWTEST,2', RUN, 'ROTATION,4', 'CASE,START,edge,0',
                         'CASE,RETURN,edge,1,44990,29990,PASS', 'READY'], 'bad-rotation.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertIn('Malformed ROTATION row', run['warnings'])

    def test_visual_case_return_requires_human_review(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,edge_clipping,0',
                         'CASE,RETURN,edge_clipping,20,44990,29990,VISUAL_REVIEW_REQUIRED',
                         'READY'], 'visual.log')
        self.assertEqual(run['cases']['edge_clipping']['status'], 'VISUAL_REVIEW_REQUIRED')
        self.assertEqual(run['status'], 'VISUAL_REVIEW_REQUIRED')

    def test_nearest_rank_p95_and_thirty_samples(self):
        rows = [{'scenario': 'rect', 'round': i // 10 + 1, 'sample': i % 10,
                 'repetitions': 1, 'total_us': (i + 1) * 10} for i in range(30)]
        stats = bench_statistics(rows)
        self.assertEqual(stats['median_us'], 155.0)
        self.assertEqual(stats['p95_us'], 290.0)
        self.assertEqual(stats['rounds'], 3)
        duplicate = rows + [dict(rows[0])]
        self.assertEqual(bench_statistics(duplicate)['status'], 'INCONCLUSIVE')

    def test_bench_parser_and_bad_zero_sample(self):
        parsed = parse_log(['HWTEST,2', RUN,
                            'BENCH,rect,1,0,10,100,45000,45000,30000', 'READY'], 'bench.log')
        self.assertEqual(parsed['bench'][0]['total_us'], 100)
        self.assertEqual(parsed['bench'][0]['repetitions'], 10)
        bad = parse_log(['HWTEST,2', RUN,
                         'BENCH,rect,1,0,0,100,45000,45000,30000', 'READY'], 'bad-bench.log')
        self.assertIn('Malformed BENCH row', bad['warnings'])

    def test_synthetic_bench_fixtures_are_not_hardware_passes(self):
        root = Path('tests/fixtures/hw_validation')
        full = parse_log((root / 'bench-valid.log').read_text().splitlines(), 'synthetic')
        self.assertEqual(len(full['bench']), 30)
        self.assertEqual(bench_statistics(full['bench'])['status'], 'OK')
        report, markdown = generate_report([full])
        self.assertEqual(report['runs'][0]['bench_statistics']['rect']['median_us'], 155.0)
        self.assertIn('p95 µs/op', markdown)
        short = parse_log((root / 'bench-short.log').read_text().splitlines(), 'short')
        self.assertEqual(bench_statistics(short['bench'])['status'], 'INCONCLUSIVE')
        self.assertEqual(full['status'], 'INCONCLUSIVE')

    def test_absolute_regression_threshold(self):
        self.assertEqual(classify_regression(5.0, 6.5, 10.0, 11.5), 'OK')

    def test_reject_different_spi_profile(self):
        base = {'metadata': {'board': 'node', 'driver': 'st', 'width': 240, 'height': 240,
                             'rotation': 0, 'cpu_hz': 80000000, 'spi_hz': 40000000,
                             'wifi': 'off', 'flags': 'default'}, 'bench': []}
        candidates = [{'metadata': dict(base['metadata'], run_id=str(i), spi_hz=20000000),
                       'bench': []} for i in range(5)]
        baselines = [{'metadata': dict(base['metadata'], run_id='b' + str(i)), 'bench': []}
                     for i in range(5)]
        self.assertEqual(compare_benchmarks(baselines, candidates)['status'], 'INCOMPATIBLE')

    def test_dirty_build_is_not_comparable(self):
        metadata = dict(board='node', driver='st', width=240, height=240, rotation=0,
                        cpu_hz=80000000, spi_hz=40000000, wifi='off', flags='dirty')
        runs = [{'metadata': dict(metadata, run_id=str(i), sha='same'), 'bench': []}
                for i in range(5)]
        self.assertEqual(compare_benchmarks(runs, runs)['status'], 'INCONCLUSIVE')

    def test_comparison_requires_five_boots_and_classifies_regression(self):
        metadata = dict(board='node', driver='st', width=240, height=240, rotation=0,
                        cpu_hz=80000000, spi_hz=40000000, wifi='off', flags='default')
        def runs(prefix, sha, total):
            result = []
            for boot in range(5):
                rows = [{'scenario': 'rect', 'round': i // 10 + 1, 'sample': i % 10,
                         'repetitions': 10, 'total_us': total} for i in range(30)]
                result.append({'metadata': dict(metadata, run_id=prefix + str(boot), sha=sha),
                               'bench': rows})
            return result
        compared = compare_benchmarks(runs('b', 'base', 100), runs('c', 'cand', 140))
        self.assertEqual(compared['status'], 'REGRESSION_CANDIDATE')

    def test_stress_requires_end_and_all_checkpoints(self):
        root = Path('tests/fixtures/hw_validation')
        complete = parse_log((root / 'stress-complete.log').read_text().splitlines(), 'complete')
        reset = parse_log((root / 'stress-reset.log').read_text().splitlines(), 'reset')
        self.assertEqual(summarize_stress(complete)['status'], 'PASS')
        self.assertEqual(summarize_stress(reset)['status'], 'INCONCLUSIVE')
        self.assertNotEqual(summarize_stress(reset)['status'], 'PASS')

    def test_heap_recovery_after_cleanup_is_not_a_leak_warning(self):
        root = Path('tests/fixtures/hw_validation')
        recovered = parse_log((root / 'stress-recovered.log').read_text().splitlines(), 'recovered')
        self.assertFalse(summarize_stress(recovered)['heap_drop_warning'])

    def test_unfinished_x_case_is_not_green(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,image_16x16_crop,0'], 'x-reset.log')
        self.assertNotEqual(run['status'], 'PASS')

    def test_missing_baseline_never_fabricates_delta(self):
        valid = parse_log(['HWTEST,2', RUN, 'CASE,START,fill,0',
                           'CASE,RETURN,fill,4,44900,29900,PASS', 'READY'], 'valid.log')
        report, markdown = generate_report([valid], None)
        self.assertNotIn('delta_pct', report.get('comparison', {}))
        self.assertEqual(report['baseline_status'], 'NO_BASELINE')
        self.assertIn('No baseline supplied', markdown)

    def test_report_redacts_unrecognized_wifi_and_flags(self):
        valid = parse_log(['HWTEST,2', RUN.replace(',off,default,', ',secret-network,password=abc,'),
                           'CASE,START,fill,0', 'CASE,RETURN,fill,4,44900,29900,PASS', 'READY'], 'secret.log')
        report, markdown = generate_report([valid])
        self.assertNotIn('secret-network', markdown)
        self.assertNotIn('password=abc', markdown)

    def test_observed_failure_is_not_hidden_by_other_warnings(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,draw,7',
                         'CASE,RETURN,draw,4,44900,29900,FAIL', 'unexpected', 'READY'], 'failed.log')
        self.assertEqual(run['status'], 'FAIL')

    def test_duplicate_case_never_passes(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,edge,0',
                         'CASE,START,edge,0',
                         'CASE,RETURN,edge,4,44900,29900,PASS', 'READY'], 'dup.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertNotEqual(run['cases']['edge']['status'], 'PASS')

    def test_duplicate_return_never_passes(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,edge,0',
                         'CASE,RETURN,edge,4,44900,29900,INCONCLUSIVE',
                         'CASE,RETURN,edge,4,44900,29900,PASS', 'READY'], 'duplicate-return.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertIn('Duplicate CASE,RETURN', run['warnings'][0])

    def test_duplicate_return_cannot_hide_failure(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,edge,0',
                         'CASE,RETURN,edge,4,44900,29900,FAIL',
                         'CASE,RETURN,edge,4,44900,29900,PASS', 'READY'], 'duplicate-fail.log')
        self.assertEqual(run['status'], 'FAIL')

    def test_truncated_run_is_inconclusive(self):
        run = parse_log(['HWTEST,2', 'RUN,run1,abc123,nodemcuv2'], 'truncated.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertTrue(run['warnings'])

    def test_missing_comparison_metadata_is_inconclusive(self):
        fields = RUN.split(',')
        fields[2] = ''
        run = parse_log(['HWTEST,2', ','.join(fields), 'READY'], 'missing.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertEqual(run['metadata']['sha'], '')

    def test_unknown_sha_is_not_comparable(self):
        run = parse_log(['HWTEST,2', RUN.replace('abc123', 'unknown'),
                         'CASE,START,fill,1', 'CASE,RETURN,fill,4,44900,29900,PASS',
                         'READY'], 'unknown-sha.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')

    def test_unknown_driver_is_not_comparable(self):
        run = parse_log(['HWTEST,2', RUN.replace('ST7789', 'unknown'),
                         'CASE,START,fill,1', 'CASE,RETURN,fill,4,44900,29900,PASS',
                         'READY'], 'unknown-driver.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')

    def test_case_seed_must_fit_uint32(self):
        run = parse_log(['HWTEST,2', RUN, 'CASE,START,fill,4294967296',
                         'CASE,RETURN,fill,4,44900,29900,PASS', 'READY'], 'seed.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')

    def test_run_metadata_rejects_quoted_commas(self):
        run = parse_log(['HWTEST,2', RUN.replace(',default,', ',"unsafe,flags",'),
                         'CASE,START,fill,1', 'CASE,RETURN,fill,4,44900,29900,PASS',
                         'READY'], 'unsafe.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')

    def test_numeric_fields_reject_whitespace(self):
        run = parse_log(['HWTEST,2', RUN.replace(',240,240,', ', 240,240,'),
                         'CASE,START,fill,1', 'CASE,RETURN,fill,4,44900,29900,PASS',
                         'READY'], 'whitespace.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')

    def test_legacy_logs_are_preserved_without_invented_cases(self):
        run = parse_log(['HWTEST,1', 'BENCH,fill,1,10,10,1000,45000,45000',
                         'READY'], 'legacy.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertEqual(run['cases'], {})
        self.assertIn('BENCH,fill,1,10,10,1000,45000,45000', run['raw_records'])

    def test_unmapped_bench_rows_remain_raw_and_inconclusive(self):
        run = parse_log(['HWTEST,2', RUN, 'BENCH,fill,1,10,10,1000,45000,45000',
                         'READY'], 'bench.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertEqual(run['cases'], {})
        self.assertFalse(run['warnings'])

    def test_smoke_csv_is_not_treated_as_protocol(self):
        run = parse_log(['time_ms,heap', '100,45000'], 'smoke.log')
        self.assertEqual(run['status'], 'INCONCLUSIVE')
        self.assertEqual(len(run['raw_records']), 2)


if __name__ == '__main__':
    unittest.main()
