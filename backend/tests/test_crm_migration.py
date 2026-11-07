import sqlite3
from backend.migrations import migrate

def test_19_schema5_preserves_v21_and_backs_up(tmp_path):
    path=tmp_path/'old.db';migrate(path,4)
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO people(name) VALUES('Originale')");before=c.execute('SELECT * FROM people').fetchall()
    migrate(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==5
        assert c.execute('SELECT * FROM people').fetchall()==before
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
    backups=list((tmp_path/'backups').glob('*.db'));assert len(backups)==1
    with sqlite3.connect(backups[0]) as c:assert c.execute('PRAGMA user_version').fetchone()[0]==4
    migrate(path);assert len(list((tmp_path/'backups').glob('*.db')))==1

