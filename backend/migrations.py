"""Versioned, additive migrations. A verified online backup precedes every upgrade."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def backup_database(path):
    path = Path(path)
    folder = path.parent / 'backups'
    folder.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = folder / f'{path.stem}-{stamp}.db'
    with sqlite3.connect(path) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup non integro: migrazione interrotta')
        if dest.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Backup con riferimenti non validi: migrazione interrotta')
    target.chmod(0o600)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = target.with_suffix('.json')
    manifest.write_text(json.dumps({'database': target.name, 'sha256': digest, 'integrity_check': 'ok', 'created_at': stamp}))
    manifest.chmod(0o600)
    return target


def migrate(path):
    with sqlite3.connect(path) as c:
        version = c.execute('PRAGMA user_version').fetchone()[0]
        existing = c.execute("SELECT 1 FROM sqlite_master WHERE name='people'").fetchone()
    if version >= 2:
        return
    if existing:
        backup_database(path)  # Fail closed: no schema changes if backup fails.
    with sqlite3.connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        statements = [
            "CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '')",
            "CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, name TEXT NOT NULL, date TEXT NOT NULL, location TEXT NOT NULL DEFAULT '', cost INTEGER NOT NULL DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE, person_id INTEGER NOT NULL REFERENCES people(id), amount INTEGER NOT NULL DEFAULT 0, UNIQUE(event_id,person_id))",
            'CREATE TABLE IF NOT EXISTS separate(a INTEGER REFERENCES people(id),b INTEGER REFERENCES people(id),PRIMARY KEY(a,b))',
            'CREATE TABLE IF NOT EXISTS aliases(person_id INTEGER REFERENCES people(id),name TEXT,email TEXT,phone TEXT, UNIQUE(person_id,name,email,phone))',
        ]
        for sql in statements:
            c.execute(sql)
        for table, column, definition in [
            ('events', 'participant_value_cents', 'INTEGER CHECK(participant_value_cents >= 0)'),
            ('events', 'archived', 'INTEGER NOT NULL DEFAULT 0'),
            ('attendance', 'status', "TEXT NOT NULL DEFAULT 'unknown' CHECK(status IN ('registered','confirmed','unknown'))"),
        ]:
            columns = {r[1] for r in c.execute(f'PRAGMA table_info({table})')}
            if column not in columns:
                c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        for sql in [
            "CREATE TABLE identity_links(id INTEGER PRIMARY KEY,a INTEGER NOT NULL REFERENCES people(id),b INTEGER NOT NULL REFERENCES people(id),active INTEGER NOT NULL DEFAULT 1,reason TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE decisions(id INTEGER PRIMARY KEY,action TEXT NOT NULL,a INTEGER,b INTEGER,link_id INTEGER,reason TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE imports(id INTEGER PRIMARY KEY,fingerprint TEXT UNIQUE NOT NULL,event_id INTEGER REFERENCES events(id),filename TEXT NOT NULL,sheet TEXT NOT NULL,mapping TEXT NOT NULL,status TEXT NOT NULL,original BLOB NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE import_rows(id INTEGER PRIMARY KEY,import_id INTEGER NOT NULL REFERENCES imports(id),row_number INTEGER NOT NULL,person_id INTEGER NOT NULL REFERENCES people(id),original TEXT NOT NULL,status TEXT NOT NULL,UNIQUE(import_id,row_number))",
            "CREATE TABLE import_drafts(token TEXT PRIMARY KEY,filename TEXT NOT NULL,original BLOB NOT NULL,config TEXT NOT NULL,snapshot TEXT NOT NULL,created_at INTEGER NOT NULL)",
            "CREATE TABLE status_history(id INTEGER PRIMARY KEY,attendance_id INTEGER REFERENCES attendance(id),old_status TEXT,new_status TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
            'CREATE INDEX attendance_person_idx ON attendance(person_id)',
            'CREATE INDEX import_rows_person_idx ON import_rows(person_id)',
        ]:
            c.execute(sql)
        c.execute('PRAGMA user_version=2')
