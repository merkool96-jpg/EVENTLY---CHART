import hashlib
import json
import sqlite3
from pathlib import Path
import pytest
from scripts import update


def folders(tmp_path):
    source=tmp_path/'release';target=tmp_path/'existing';source.mkdir();target.mkdir()
    for root in (source,target):
        (root/'backend').mkdir();(root/'frontend').mkdir()
        (root/'backend/app.py').write_text('old' if root==target else 'new')
        (root/'frontend/package.json').write_text('{}')
    db=target/'backend/evently.db'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE keep(value TEXT)');c.execute("INSERT INTO keep VALUES('dati personali')")
    (target/'note-personali.txt').write_text('conservare')
    (source/'new.py').write_text('new file')
    manifest={name:{'sha256':hashlib.sha256((source/name).read_bytes()).hexdigest(),'executable':False} for name in ['backend/app.py','frontend/package.json','new.py']}
    (source/'update-manifest.json').write_text(json.dumps({'files':manifest}))
    return source,target


def test_update_preserves_database_local_files_and_backs_up_code(tmp_path):
    source,target=folders(tmp_path)
    before=(target/'backend/evently.db').read_bytes()
    backup=update.apply_update(source,target,check_running=False)
    assert (target/'backend/app.py').read_text()=='new'
    assert (backup/'codice/backend/app.py').read_text()=='old'
    assert (target/'backend/evently.db').read_bytes()==before
    assert (target/'note-personali.txt').read_text()=='conservare'
    files=list((target/'backend/backups').glob('*.db'))
    assert len(files)==1
    with sqlite3.connect(files[0]) as c:assert c.execute('SELECT value FROM keep').fetchone()[0]=='dati personali'


def test_modified_release_rejected_before_any_write(tmp_path):
    source,target=folders(tmp_path);(source/'new.py').write_text('tampered')
    with pytest.raises(ValueError):update.apply_update(source,target,False)
    assert (target/'backend/app.py').read_text()=='old'
    assert not (target/'backend/backups').exists()


def test_database_and_escape_paths_are_rejected(tmp_path):
    for name in ['../outside.py','backend/evently.db','backend/backups/x.py','.env','/etc/file']:
        with pytest.raises(ValueError):update.safe_path(tmp_path,name)


def test_code_copy_failure_restores_previous_files(tmp_path,monkeypatch):
    source,target=folders(tmp_path);original=update.shutil.copyfile
    def fail(src,dest,*args,**kwargs):
        if Path(src)==source/'new.py':raise OSError('simulated disk failure')
        return original(src,dest,*args,**kwargs)
    monkeypatch.setattr(update.shutil,'copyfile',fail)
    with pytest.raises(OSError):update.apply_update(source,target,False)
    assert (target/'backend/app.py').read_text()=='old'
    assert not (target/'new.py').exists()
    assert not list(target.rglob('*.evently-update'))


def test_running_app_and_wrong_folder_are_rejected(tmp_path,monkeypatch):
    source,target=folders(tmp_path)
    monkeypatch.setattr(update,'active_application',lambda _:True)
    with pytest.raises(ValueError):update.apply_update(source,target)
    with pytest.raises(ValueError):update.apply_update(source,source,False)


def test_newer_database_format_is_never_downgraded(tmp_path):
    source,target=folders(tmp_path)
    with sqlite3.connect(target/'backend/evently.db') as c:c.execute('PRAGMA user_version=99')
    with pytest.raises(ValueError):update.apply_update(source,target,False)
    assert (target/'backend/app.py').read_text()=='old'
    with sqlite3.connect(target/'backend/evently.db') as c:assert c.execute('PRAGMA user_version').fetchone()[0]==99
