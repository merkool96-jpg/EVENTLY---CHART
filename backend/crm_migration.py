"""Additive schema5: CRM records preserve original identity scopes through splits."""
import sqlite3


def upgrade_crm(path):
    with sqlite3.connect(path) as c:
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('BEGIN IMMEDIATE')
        c.execute('ALTER TABLE events ADD COLUMN cost_defined INTEGER NOT NULL DEFAULT 0')
        c.execute('UPDATE events SET cost_defined=1 WHERE cost>0')
        for sql in [
            "CREATE TABLE crm_tags(id INTEGER PRIMARY KEY,name TEXT NOT NULL,normalized TEXT NOT NULL UNIQUE,color TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)))",
            "CREATE TABLE crm_campaigns(id INTEGER PRIMARY KEY,name TEXT NOT NULL,normalized TEXT NOT NULL UNIQUE,archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)))",
            "CREATE TABLE community_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
            "CREATE TABLE crm_segments(id INTEGER PRIMARY KEY,name TEXT NOT NULL,filters TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0)",
            "CREATE TABLE crm_batches(token TEXT PRIMARY KEY,config TEXT NOT NULL,selection TEXT NOT NULL,snapshot TEXT NOT NULL,committed INTEGER NOT NULL DEFAULT 0,undone INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)",
            """CREATE TABLE crm_records(id INTEGER PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('vip','tag','note','reward')),scope TEXT NOT NULL CHECK(json_valid(scope) AND json_type(scope)='array' AND json_array_length(scope)>0),
               payload TEXT NOT NULL,tag_id INTEGER REFERENCES crm_tags(id),campaign_id INTEGER REFERENCES crm_campaigns(id),event_id INTEGER REFERENCES events(id),
               active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),revision INTEGER NOT NULL DEFAULT 1,author TEXT NOT NULL,
               created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
            "CREATE TABLE crm_record_origins(record_id INTEGER NOT NULL REFERENCES crm_records(id),person_id INTEGER NOT NULL REFERENCES people(id),PRIMARY KEY(record_id,person_id))",
            "CREATE INDEX crm_origins_person_idx ON crm_record_origins(person_id)",
            """CREATE TABLE crm_audit(id INTEGER PRIMARY KEY,action TEXT NOT NULL,operator TEXT NOT NULL,record_id INTEGER REFERENCES crm_records(id),
               batch TEXT REFERENCES crm_batches(token),before_data TEXT,after_data TEXT,reason TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
            'CREATE INDEX crm_records_kind_idx ON crm_records(kind,active)',
            'CREATE INDEX crm_records_tag_idx ON crm_records(tag_id,active)',
            'CREATE INDEX crm_records_campaign_idx ON crm_records(campaign_id,kind)',
            'CREATE INDEX crm_audit_record_idx ON crm_audit(record_id,id)',
            "CREATE TRIGGER crm_origins_insert AFTER INSERT ON crm_records BEGIN INSERT INTO crm_record_origins(record_id,person_id) SELECT NEW.id,value FROM json_each(NEW.scope); END",
            "CREATE TRIGGER crm_origins_update AFTER UPDATE OF scope ON crm_records BEGIN DELETE FROM crm_record_origins WHERE record_id=NEW.id; INSERT INTO crm_record_origins(record_id,person_id) SELECT NEW.id,value FROM json_each(NEW.scope); END",
        ]:c.execute(sql)
        c.execute('PRAGMA user_version=5')
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Migrazione CRM annullata: verifica integrità non superata')
