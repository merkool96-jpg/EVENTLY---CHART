"""Create or verify a local database backup without importing/migrating the app."""
import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from .migrations import backup_database


def main():
    parser=argparse.ArgumentParser(description='Backup SQLite EVENTLY verificato')
    parser.add_argument('--database',default=os.getenv('EVENTLY_DB',str(Path(__file__).parent/'evently.db')))
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args()
    if args.verify:
        path=args.verify.resolve()
        manifest=json.loads(path.with_suffix('.json').read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:
            raise SystemExit('Verifica SHA-256 fallita')
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():
                raise SystemExit('Verifica SQLite fallita')
        print('Backup verificato: SHA-256, integrità e riferimenti SQLite OK')
    else:
        if not Path(args.database).is_file():
            raise SystemExit('Database inesistente: nessun file creato')
        print(backup_database(args.database))


if __name__=='__main__':
    main()
