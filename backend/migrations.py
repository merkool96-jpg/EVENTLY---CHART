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


def migrate(path,target_version=4):
    with sqlite3.connect(path) as c:
        version = c.execute('PRAGMA user_version').fetchone()[0]
        existing = c.execute("SELECT 1 FROM sqlite_master WHERE name='people'").fetchone()
    if target_version not in (2,3,4):raise ValueError("Schema target non supportato")
    if version >= target_version:
        return
    if version == 3:
        backup_database(path)
        upgrade_v2(path)
        return
    if version == 2:
        if existing:
            backup_database(path)
        if target_version>=3:upgrade_profiles(path)
        if target_version>=4:upgrade_v2(path)
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
    if target_version>=3:upgrade_profiles(path)
    if target_version>=4:upgrade_v2(path)


def upgrade_profiles(path):
    with sqlite3.connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute("""CREATE TABLE IF NOT EXISTS profile_edits(
            id INTEGER PRIMARY KEY,person_id INTEGER NOT NULL REFERENCES people(id),
            members TEXT NOT NULL,first_name TEXT NOT NULL,last_name TEXT NOT NULL,
            display_name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT NOT NULL,
            reason TEXT NOT NULL,link_id INTEGER REFERENCES identity_links(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        c.execute('CREATE INDEX IF NOT EXISTS profile_edits_person_idx ON profile_edits(person_id)')
        c.execute('PRAGMA user_version=3')


def upgrade_v2(path):
    with sqlite3.connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        for table,column,definition in [
            ('people','first_name',"TEXT NOT NULL DEFAULT ''"),('people','last_name',"TEXT NOT NULL DEFAULT ''"),('people','name_structure',"TEXT NOT NULL DEFAULT 'proposed'"),
            ('events','category',"TEXT NOT NULL DEFAULT ''"),('events','edition',"TEXT NOT NULL DEFAULT ''"),('events','include_analytics','INTEGER NOT NULL DEFAULT 1'),('events','registration_complete','INTEGER NOT NULL DEFAULT 0')]:
            c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        c.execute("""CREATE TABLE attendance_v2(id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,person_id INTEGER NOT NULL REFERENCES people(id),amount INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'unknown' CHECK(status IN ('registered','confirmed','absent','cancelled','unknown')),UNIQUE(event_id,person_id))""")
        c.execute('INSERT INTO attendance_v2 SELECT * FROM attendance')
        c.execute('DROP TABLE attendance')
        c.execute('ALTER TABLE attendance_v2 RENAME TO attendance')
        c.execute('CREATE INDEX attendance_person_idx ON attendance(person_id)')
        statements=[
            "CREATE TABLE attendance_evidence(id INTEGER PRIMARY KEY,attendance_id INTEGER NOT NULL REFERENCES attendance(id),status TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE participation_overrides(id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL REFERENCES events(id),members TEXT NOT NULL,status TEXT NOT NULL,operator TEXT NOT NULL,batch TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE bulk_operations(token TEXT PRIMARY KEY,config TEXT NOT NULL,snapshot TEXT NOT NULL,committed INTEGER NOT NULL DEFAULT 0,undone INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)",
            "CREATE TABLE import_issues(id INTEGER PRIMARY KEY,import_id INTEGER NOT NULL REFERENCES imports(id),row_number INTEGER NOT NULL,original TEXT NOT NULL,reason TEXT NOT NULL,person_id INTEGER REFERENCES people(id),resolved INTEGER NOT NULL DEFAULT 0)",
            "CREATE TABLE source_keys(event_id INTEGER REFERENCES events(id),registration_id TEXT,person_id INTEGER REFERENCES people(id),PRIMARY KEY(event_id,registration_id))",
            "CREATE TABLE mapping_templates(id INTEGER PRIMARY KEY,name TEXT NOT NULL,headers TEXT NOT NULL,mapping TEXT NOT NULL,header_row INTEGER NOT NULL)",
            "CREATE TABLE saved_views(id INTEGER PRIMARY KEY,name TEXT NOT NULL,filters TEXT NOT NULL)",
            "CREATE TABLE deferred_pairs(a INTEGER REFERENCES people(id),b INTEGER REFERENCES people(id),PRIMARY KEY(a,b))",
            "CREATE TABLE restore_drafts(token TEXT PRIMARY KEY,path TEXT NOT NULL,sha TEXT NOT NULL,created_at INTEGER NOT NULL)",
            "CREATE INDEX attendance_evidence_idx ON attendance_evidence(attendance_id)",
            "CREATE INDEX overrides_event_idx ON participation_overrides(event_id)"]
        for sql in statements:c.execute(sql)
        c.execute("INSERT INTO attendance_evidence(attendance_id,status,source) SELECT id,status,'legacy-v1' FROM attendance")
        c.execute('PRAGMA user_version=4')
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Verifica migrazione non riuscita: modifiche annullate')
