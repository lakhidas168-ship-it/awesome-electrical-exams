"""Control fixtures only: no invented student content or claimed production data."""
import concurrent.futures
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('feeder', Path(__file__).with_name('feed_frogs.py'))
feeder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feeder)


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.root = self.home / '.air10/frog'
        self.pool = self.home / '.air10/opencode_pool'
        self.root.mkdir(parents=True)
        for sub in ('done', 'todo', 'running', 'waiting'):
            (self.pool / sub).mkdir(parents=True)
        self.frogs = [
            {'rank': 1, 'title': 'Verify source', 'done_when': 'Source acceptance', 'depends_on': [], 'status': 'queued'},
            {'rank': 2, 'title': 'Use accepted source', 'done_when': 'Consumer acceptance', 'depends_on': [1], 'status': 'todo'},
        ]
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.root / 'TOP100_FROGS.json').write_text(json.dumps(self.frogs))

    def states(self):
        return json.loads((self.root / 'TOP100_FROGS.json').read_text())

    def receipt(self, frog=None):
        frog = frog or self.frogs[0]
        out = self.root / f"check-{frog['rank']}.log"
        out.write_text('Recorded control check output\n')
        artifact = self.root / f"artifact-{frog['rank']}.txt"
        artifact.write_text('Source acceptance control artifact\n')
        receipt = {
            'rank': frog['rank'], 'criterion_sha256': feeder.criterion_digest(frog),
            'checks': [{'phase': phase, 'argv': ['control-check', phase], 'returncode': 0,
                        'output_path': str(out), 'output_sha256': feeder.digest(out)} for phase in ('dry', 'stress', 'live')],
            'artifacts': [{'path': str(artifact), 'sha256': feeder.digest(artifact)}],
        }
        target = self.root / 'acceptance' / f"FROG_{frog['rank']:03d}.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(receipt))
        return target, receipt, out, artifact

    def test_done_queue_without_receipt_cannot_complete(self):
        (self.pool / 'done/FROG_001.json').write_text('{}')
        feeder.feed(self.home)
        self.assertEqual(self.states()[0]['status'], 'verification_pending')
        self.assertEqual(self.states()[1]['status'], 'blocked')

    def test_historical_done_is_preserved_as_claim(self):
        self.frogs[0]['status'] = 'done'
        self.frogs[0]['proof'] = 'Historical claim'
        self.save()
        feeder.feed(self.home)
        self.assertEqual(self.states()[0]['proof'], 'Historical claim')
        self.assertEqual(self.states()[0]['previous_completion_claim'], 'done')
        self.assertEqual(self.states()[0]['status'], 'verification_pending')

    def test_prefix_collision_does_not_count_as_done(self):
        (self.pool / 'done/FROG_001_incomplete.json').write_text('{}')
        feeder.feed(self.home)
        self.assertEqual(self.states()[0]['status'], 'queued')

    def test_complete_receipt_unblocks_dependency(self):
        self.receipt()
        result = feeder.feed(self.home)
        self.assertEqual(result['accepted'], [1])
        self.assertEqual(self.states()[1]['status'], 'queued')

    def test_accepted_receipt_clears_stale_verification_note(self):
        self.frogs[0]['status'] = 'verification_pending'
        self.frogs[0]['verification_note'] = 'Missing receipt'
        self.frogs[0]['previous_completion_claim'] = 'done'
        self.save()
        self.receipt()
        feeder.feed(self.home)
        state = self.states()[0]
        self.assertEqual(state['status'], 'done')
        self.assertNotIn('verification_note', state)
        self.assertEqual(state['previous_completion_claim'], 'done')

    def test_mutated_artifact_revokes_completion(self):
        _, _, _, artifact = self.receipt()
        feeder.feed(self.home)
        artifact.write_text('Changed source')
        feeder.feed(self.home)
        self.assertEqual(self.states()[0]['status'], 'verification_pending')
        self.assertFalse((self.pool / 'todo/FROG_002.json').exists())
        self.assertTrue((self.pool / 'waiting/FROG_002.json').exists())

    def test_mutated_output_revokes_completion(self):
        _, _, output, _ = self.receipt()
        output.write_text('Changed result')
        self.assertFalse(feeder.valid_receipt(self.frogs[0], self.root))

    def test_failed_or_boolean_exit_is_rejected(self):
        path, receipt, _, _ = self.receipt()
        for rc in (1, False):
            receipt['checks'][0]['returncode'] = rc
            path.write_text(json.dumps(receipt))
            self.assertFalse(feeder.valid_receipt(self.frogs[0], self.root))

    def test_incomplete_checks_or_no_artifact_rejected(self):
        path, receipt, _, _ = self.receipt()
        for bad in ({**receipt, 'checks': receipt['checks'][:1]}, {**receipt, 'artifacts': []}):
            path.write_text(json.dumps(bad))
            self.assertFalse(feeder.valid_receipt(self.frogs[0], self.root))

    def test_changed_acceptance_criterion_is_rejected(self):
        self.receipt()
        changed = {**self.frogs[0], 'done_when': 'New acceptance'}
        self.assertFalse(feeder.valid_receipt(changed, self.root))

    def test_malformed_receipt_is_rejected(self):
        path, receipt, _, _ = self.receipt()
        for body in ('not-json', 'null', '[]', json.dumps({**receipt, 'checks': [None]})):
            path.write_text(body)
            self.assertFalse(feeder.valid_receipt(self.frogs[0], self.root))

    def test_dependency_cycle_cannot_be_accepted(self):
        self.frogs[0]['depends_on'] = [2]
        self.save()
        for frog in self.frogs:
            self.receipt(frog)
        self.assertEqual(feeder.feed(self.home)['accepted'], [])

    def test_unknown_dependency_stays_blocked(self):
        self.frogs[1]['depends_on'] = [999]
        self.save()
        feeder.feed(self.home)
        self.assertEqual(self.states()[1]['blocked_by'], [999])

    def test_held_task_restores_without_losing_metadata(self):
        (self.pool / 'todo/FROG_002.json').write_text('{"retries":7,"original":"preserve"}')
        feeder.feed(self.home)
        self.receipt()
        feeder.feed(self.home)
        self.assertEqual(json.loads((self.pool / 'todo/FROG_002.json').read_text())['retries'], 7)

    def test_running_task_is_preserved(self):
        (self.pool / 'running/FROG_002.json').write_text('{}')
        feeder.feed(self.home)
        self.assertTrue((self.pool / 'running/FROG_002.json').exists())

    def test_duplicate_ranks_fail_before_mutation(self):
        self.frogs.append(copy.deepcopy(self.frogs[0]))
        self.save()
        before = (self.root / 'TOP100_FROGS.json').read_bytes()
        with self.assertRaises(ValueError):
            feeder.feed(self.home)
        self.assertEqual((self.root / 'TOP100_FROGS.json').read_bytes(), before)

    def test_missing_queued_job_is_recreated(self):
        feeder.feed(self.home)
        self.assertTrue((self.pool / 'todo/FROG_001.json').exists())
        (self.pool / 'todo/FROG_001.json').rename(self.pool / 'waiting/lost-control-job.json')
        feeder.feed(self.home)
        self.assertTrue((self.pool / 'todo/FROG_001.json').exists())

    def test_accepted_task_is_not_dispatched_again(self):
        (self.pool / 'todo/FROG_001.json').write_text('{"keep":"accepted task"}')
        self.receipt()
        feeder.feed(self.home)
        self.assertFalse((self.pool / 'todo/FROG_001.json').exists())
        copies = list((self.pool / 'accepted').glob('FROG_001.*.json'))
        self.assertEqual(len(copies), 1)
        self.assertEqual(json.loads(copies[0].read_text())['keep'], 'accepted task')

    def test_conflicting_waiting_versions_are_preserved(self):
        (self.pool / 'todo/FROG_002.json').write_text('{"version":2}')
        (self.pool / 'waiting/FROG_002.json').write_text('{"version":1}')
        feeder.feed(self.home)
        self.assertFalse((self.pool / 'todo/FROG_002.json').exists())
        self.assertEqual(json.loads((self.pool / 'waiting/FROG_002.json').read_text())['version'], 1)
        held = list((self.pool / 'waiting_conflicts').glob('FROG_002.*.json'))
        self.assertEqual(json.loads(held[0].read_text())['version'], 2)
        self.assertEqual(self.states()[1]['status'], 'blocked')

    def test_concurrent_feeders_remain_idempotent(self):
        self.frogs[0]['status'] = 'todo'
        self.save()
        argv = [sys.executable, str(Path(__file__).with_name('feed_frogs.py')), '--home', str(self.home)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: subprocess.run(argv, capture_output=True, text=True), range(40)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results if r.returncode])
        self.assertEqual(len(list((self.pool / 'todo').glob('FROG_*.json'))), 1)
        self.assertEqual(self.states()[1]['status'], 'blocked')


if __name__ == '__main__':
    unittest.main(verbosity=2)
