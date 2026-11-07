"""Full package upgrade rehearsal; ONLY disposable synthetic installations."""
import json
import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from scripts.update import apply_update

ROOT=Path(__file__).resolve().parent.parent
BASE='4cb44ae'


def snapshot(path):
    with sqlite3.connect(path) as c:
        result={}
        for (table,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            columns=[r[1] for r in c.execute(f'PRAGMA table_info("{table}")')]
            result[table]={'columns':columns,'rows':c.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()}
        return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',default=BASE);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='evently-v2-upgrade-') as temporary:
        target=Path(temporary)/'previous';target.mkdir()
        archive=subprocess.run(['git','archive',args.base],cwd=ROOT,capture_output=True,check=True).stdout
        subprocess.run(['tar','-x','-C',str(target)],input=archive,check=True)
        database=target/'backend/evently.db'
        env={**os.environ,'EVENTLY_DB':str(database),'PYTHONPATH':str(target)}
        seed='''from fastapi.testclient import TestClient
from backend.app import app
c=TestClient(app)
e=c.post('/api/events',json={'name':'Sintetico precedente','date':'2025-12-01','participant_value_cents':2000}).json()['id']
r=c.post(f'/api/events/{e}/import',files={'file':('synthetic.csv',b'Nome completo,Email\\nSofia,sofia@example.test\\nSofia Di Gio,sofia@example.test\\nAltra Persona,other@example.test\\n')},data={'status':'confirmed'})
assert r.status_code==200,r.text
assert c.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).status_code==200
assert c.post('/api/matches/decision',json={'a':1,'b':3,'action':'separate'}).status_code==200
if c.get('/api/health').json().get('schema_version',0)>=5:
    tid=c.post('/api/v22/tags',json={'name':'Tag sintetico aggiornamento'}).json()['id']
    cid=c.post('/api/v22/campaigns',json={'name':'Campagna sintetica'}).json()['id']
    for action,data in [('vip_add',{}),('tag_add',{'tag_ids':[tid]}),('reward',{'name':'Grazie sintetico','type':'Voucher','date':'2026-01-01','status':'proposed','campaign_id':cid})]:
        draft=c.post('/api/v22/bulk/preview',json={'action':action,'ids':[1],'data':data})
        assert draft.status_code==200,draft.text
        assert c.post('/api/v22/bulk/'+draft.json()['token']+'/confirm').status_code==200
    assert c.post('/api/v22/people/1/notes',json={'text':'Nota sintetica da preservare'}).status_code==200
'''
        subprocess.run([sys.executable,'-c',seed],cwd=target,env=env,check=True,capture_output=True)
        before=snapshot(database)
        with sqlite3.connect(database) as c:previous_schema=c.execute('PRAGMA user_version').fetchone()[0]
        backup=apply_update(ROOT,target,False)
        with sqlite3.connect(database) as c:assert c.execute('PRAGMA user_version').fetchone()[0]==previous_schema
        launch='''from backend.app import app
from fastapi.testclient import TestClient
c=TestClient(app)
assert c.get('/api/health').status_code==200
assert c.get('/api/dashboard').json()['attendance']==2
assert c.get('/api/v2/people').json()['total']==2
'''
        if 'crm_records' in before:
            launch+='''
profile=c.get('/api/v22/people/1').json()
assert profile['vip'] and len(profile['tags'])==1
assert {r['kind'] for r in profile['records']}=={'vip','tag','reward','note'}
'''
        subprocess.run([sys.executable,'-c',launch],cwd=target,env=env,check=True,capture_output=True)
        with sqlite3.connect(database) as c:
            assert c.execute('PRAGMA user_version').fetchone()[0]==5
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
            for table,data in before.items():
                columns=','.join('"'+column+'"' for column in data['columns'])
                assert c.execute(f'SELECT {columns} FROM "{table}" ORDER BY rowid').fetchall()==data['rows'],table
        assert (backup/'codice/backend/app.py').exists()
        backups=list((target/'backend/backups').glob('*.db'))
        assert backups
        with sqlite3.connect(backups[0]) as c:assert c.execute('PRAGMA user_version').fetchone()[0]==previous_schema
        compatible=json.loads((backup/'coppia-compatibile.json').read_text())
        verified=target/compatible['database_precedente']
        assert snapshot(verified)==before,'Backup does not match every pre-update table/row'
        print(json.dumps({'base':args.base,'schema_before':previous_schema,'schema_after':5,'legacy_tables_preserved':list(before),'database_backup_verified':True,'code_backup_verified':True,'scope':'temporary synthetic installation only'},indent=2))


if __name__=='__main__':main()
