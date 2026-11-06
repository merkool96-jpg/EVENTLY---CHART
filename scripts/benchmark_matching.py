"""Compare exhaustive and indexed candidate selection on disposable fake data.
Run from the repository root: .venv/bin/python -m scripts.benchmark_matching
"""
import json
import sqlite3
import tempfile
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from backend.identity import candidates
from backend.migrations import migrate


def exhaustive(people, focus=None):
    if focus is not None:
        a=next(p for p in people if p['id']==focus)
        yield from ((a,b) for b in people if b['id']!=focus)
    else:
        yield from ((a,b) for i,a in enumerate(people) for b in people[i+1:])


def main():
    with tempfile.TemporaryDirectory(prefix='evently-benchmark-') as folder:
        path=Path(folder)/'benchmark.db'
        migrate(path)
        with sqlite3.connect(path) as c:
            c.row_factory=sqlite3.Row
            for i in range(2130):
                c.execute('INSERT INTO people(name,email,phone) VALUES(?,?,?)',(f'Nome{i%213} Cognome{i:04}',f'persona{i}@example.test',''))
            c.commit()
            start=perf_counter()
            with patch('backend.identity.evidence_pairs',exhaustive):
                baseline=candidates(c)
            baseline_seconds=perf_counter()-start
            start=perf_counter()
            indexed=candidates(c)
            indexed_seconds=perf_counter()-start
            assert baseline==indexed
            print(json.dumps({'simulated_profiles':2130,'exhaustive_seconds':round(baseline_seconds,4),'indexed_seconds':round(indexed_seconds,4),'identical_queue':True}))


if __name__=='__main__':
    main()
