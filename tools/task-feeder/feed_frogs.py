#!/usr/bin/env python3
"""Queue dependency-ready frogs; completion requires independently recorded evidence.

Receipt checks are read-only. Commands in receipts are NEVER executed by the feeder.
Dry/stress/live labels attest reviewer checks; hashes bind their captured outputs and
artifacts to the current acceptance criterion, not the semantic truth of those checks.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def criterion_digest(frog):
    fields = {k: frog.get(k) for k in ('rank', 'title', 'done_when', 'depends_on')}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def valid_receipt(frog, root):
    """Fail closed on absent, stale, malformed, or failed recorded acceptance checks."""
    receipt_path = root / 'acceptance' / f"FROG_{frog['rank']:03d}.json"
    try:
        receipt = json.loads(receipt_path.read_text())
        if receipt.get('rank') != frog['rank'] or receipt.get('criterion_sha256') != criterion_digest(frog):
            return False
        checks = receipt.get('checks', [])
        artifacts = receipt.get('artifacts', [])
        if not isinstance(checks, list) or not isinstance(artifacts, list) or not artifacts:
            return False
        if not {'dry', 'stress', 'live'} <= {c.get('phase') for c in checks}:
            return False
        for check in checks:
            if type(check.get('returncode')) is not int or check['returncode'] != 0:
                return False
            if not isinstance(check.get('argv'), list) or not check['argv'] or not all(isinstance(v, str) for v in check['argv']):
                return False
            path = Path(check['output_path'])
            if not path.is_file() or path.stat().st_size == 0 or digest(path) != check['output_sha256']:
                return False
        for artifact in artifacts:
            if not Path(artifact['path']).is_file() or digest(artifact['path']) != artifact['sha256']:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.' + path.name, delete=False) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)
        stream.flush()
        os.fsync(stream.fileno())
        temp_path = Path(stream.name)
    os.replace(temp_path, path)


def task_for(frog, home):
    return {
        'id': f"FROG_{frog['rank']:03d}", 'title': frog['title'], 'priority': '1',
        'retries': 0, 'source': 'top100_frogs', 'dir': str(home / '.air10/opencode_pool/work'),
        'task': (
            f"EAT-THE-FROG #{frog['rank']} ({frog.get('layer', '')}): {frog['title']}\n"
            f"Why: {frog.get('why_80_20', '')}\nDone when: {frog.get('done_when', '')}\n"
            'ARCHIVE-FIRST: read HANDOVER.md, consult archive-ask and existing agent histories before building.\n'
            'COMMUNITY-SCOUT: verify dated September 2026 onward sources and reuse licensed OSS.\n'
            'Resource gathering first; bulk AI extraction stays paused. Real source data only.\n'
            'Preserve existing results, back up before edits, respect the resource governor, no paid tools, '
            'no credentials, no permanent deletion. Work dir for code: ~/code/air10-harness.\n'
            'Queue completion is a claim. Leave acceptance verification to an independent reviewer. '
            'Capture actual dry/stress/live command outputs and artifact hashes; never invent receipts. '
            'Report your actual outcome with air10-report --agent <you> --task <task> '
            '--status done|failed|blocked --proof <evidence>; never append the shared JSONL directly.'
        ),
    }


def feed(home, limit=6):
    root = home / '.air10/frog'
    pool = home / '.air10/opencode_pool'
    root.mkdir(parents=True, exist_ok=True)
    # All feeder instances share one lock; do not replace the lock inode.
    with (root / '.feed.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / 'TOP100_FROGS.json'
        frogs = json.loads(path.read_text())
        ranks = [f['rank'] for f in frogs]
        if len(ranks) != len(set(ranks)):
            raise ValueError('duplicate frog rank')
        for sub in ('todo', 'running', 'done', 'waiting', 'accepted', 'waiting_conflicts'):
            (pool / sub).mkdir(parents=True, exist_ok=True)
        verified = set()
        for frog in frogs:
            rank = frog['rank']
            if valid_receipt(frog, root):
                frog['status'] = 'done'
                frog.pop('verification_note', None)
                verified.add(rank)
            elif frog.get('status') == 'done' or (pool / 'done' / f'FROG_{rank:03d}.json').is_file():
                frog.setdefault('previous_completion_claim', frog.get('status'))
                frog['status'] = 'verification_pending'
                frog['verification_note'] = 'Missing or stale independent acceptance receipt; preserved result.'
        # Receipts must also satisfy the dependency closure (cycles cannot become done).
        accepted = set()
        for _ in frogs:
            before = len(accepted)
            accepted.update(f['rank'] for f in frogs if f['rank'] in verified and set(f.get('depends_on', [])) <= accepted)
            if before == len(accepted):
                break
        for frog in frogs:
            rank = frog['rank']
            deps = set(frog.get('depends_on', []))
            if rank in verified and rank not in accepted:
                frog['status'] = 'verification_pending'
                frog['verification_note'] = 'Acceptance receipt exists; dependencies are not accepted.'
            task_path = pool / 'todo' / f'FROG_{rank:03d}.json'
            waiting = pool / 'waiting' / task_path.name
            running = pool / 'running' / task_path.name
            if rank in accepted and task_path.exists():
                # Do not let a stale queued copy run an already accepted task again.
                accepted_path = pool / 'accepted' / f'{task_path.stem}.{digest(task_path)}.json'
                os.replace(task_path, accepted_path)
            if frog.get('status') == 'queued' and not task_path.exists() and not running.exists():
                # A queue status is not a durable job. Recreate/resume missing work.
                frog['status'] = 'todo'
            if not deps <= accepted:
                frog['blocked_by'] = sorted(deps - accepted)
                if task_path.exists():
                    if waiting.exists():
                        held = pool / 'waiting_conflicts' / f'{task_path.stem}.{digest(task_path)}.json'
                        os.replace(task_path, held)
                        frog['queue_conflict_note'] = 'Preserved both waiting and conflicting queued versions; review required.'
                    else:
                        os.replace(task_path, waiting)
                if frog.get('status') not in ('verification_pending', 'done'):
                    frog['status'] = 'blocked'
            else:
                frog.pop('blocked_by', None)
                if frog.get('status') == 'blocked':
                    frog['status'] = 'todo'
        live = sum(len(list((pool / sub).glob('FROG_*.json'))) for sub in ('todo', 'running'))
        for frog in sorted(frogs, key=lambda f: f['rank']):
            if live >= limit:
                break
            if frog.get('status') != 'todo' or not set(frog.get('depends_on', [])) <= accepted:
                continue
            task_path = pool / 'todo' / f"FROG_{frog['rank']:03d}.json"
            running = pool / 'running' / task_path.name
            waiting = pool / 'waiting' / task_path.name
            if not task_path.exists() and not running.exists():
                if waiting.exists():
                    os.replace(waiting, task_path)
                else:
                    atomic_json(task_path, task_for(frog, home))
                live += 1
            frog['status'] = 'queued'
        atomic_json(path, frogs)
        counts = {s: sum(f['status'] == s for f in frogs) for s in sorted({f['status'] for f in frogs})}
        return {'states': counts, 'accepted': sorted(accepted), 'queued_or_running': live}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--limit', type=int, default=6)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error('--limit must be nonnegative')
    print(json.dumps(feed(args.home, args.limit)))
