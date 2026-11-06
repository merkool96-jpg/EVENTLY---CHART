"""V1.1 regression tests, including real migration and recoverability checks."""
import hashlib
import io
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from backend import app as module
from backend.migrations import backup_database, migrate


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'revision.db'))
    module.init()
    return TestClient(module.app)


def event(c,name='Bottini Milano',value=None,day='2026-11-01'):
    r=c.post('/api/events',json={'name':name,'date':day,'participant_value_cents':value})
    assert r.status_code==201
    return r.json()['id']


def upload(c,e,text,status='confirmed'):
    return c.post(f'/api/events/{e}/import',files={'file':('people.csv',text.encode())},data={'status':status})


def preview(c,e,data,name='people.csv',status='registered',**options):
    return c.post('/api/imports/preview',files={'file':(name,data)},data={'event_id':e,'status':status,**options})


def test_bottini_20_to_40_and_registration_excluded(client):
    e=event(client,value=2000)
    upload(client,e,'Nome completo,Email,Importo\nAnna Rossi,anna@example.test,99\n')
    upload(client,e,'Nome completo,Email,Importo\nMarco Verdi,marco@example.test,200\n','registered')
    p=client.get('/api/people').json()
    assert p[0]['value']==2000 and p[0]['actual_spend']==9900 and p[0]['visits']==1
    assert p[1]['value']==0 and p[1]['visits']==0 and p[1]['registrations']==1
    assert client.put(f'/api/events/{e}',json={'name':'Bottini Milano','date':'2026-11-01','participant_value_cents':4000}).status_code==200
    p=client.get('/api/people').json()
    assert p[0]['value']==4000 and p[0]['actual_spend']==9900
    assert client.get('/api/dashboard').json()['attributed_value']==4000
    with module.db() as c:
        assert [r['amount'] for r in c.execute('SELECT amount FROM attendance ORDER BY id')]==[9900,20000]


def test_ranking_presence_date_name_not_money(client):
    e1=event(client,value=2000,day='2026-01-01')
    e2=event(client,value=0,day='2026-02-01')
    rich=event(client,value=999900,day='2026-03-01')
    upload(client,e1,'Nome completo\nZoe Rossi\nAnna Rossi\n')
    upload(client,e2,'Nome completo\nZoe Rossi\nAnna Rossi\nEva Verdi\n')
    upload(client,rich,'Nome completo,Importo\nMarco Ricco,100000\n')
    ranked=client.get('/api/people?ranked=true').json()
    assert [p['name'] for p in ranked]==['Anna Rossi','Zoe Rossi','Marco Ricco','Eva Verdi']
    assert [p['visits'] for p in ranked]==[2,2,1,1]
    assert ranked[2]['value']>ranked[0]['value']


def test_null_zero_positive_distinct(client):
    e=event(client)
    upload(client,e,'Nome completo\nAnna Rossi\n')
    assert client.get('/api/events').json()[0]['attributed_value'] is None
    assert client.get('/api/people').json()[0]['undefined_values']==1
    client.put(f'/api/events/{e}',json={'name':'Free','date':'2026-01-01','participant_value_cents':0})
    assert client.get('/api/events').json()[0]['attributed_value']==0
    assert client.get('/api/people').json()[0]['undefined_values']==0


def test_merge_undo_preserves_original_connections(client):
    e1=event(client,value=2000)
    e2=event(client,value=4000)
    upload(client,e1,'Nome completo,Email\nAnna Rossi,a@test.it\n')
    upload(client,e2,'Nome completo,Email\nAna Rossi,a@test.it\n')
    with module.db() as c:
        before=[tuple(r) for r in c.execute('SELECT * FROM attendance ORDER BY id')]
    r=client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'})
    assert r.status_code==200
    assert client.get('/api/people').json()[0]['visits']==2
    assert client.get('/api/people').json()[0]['value']==6000
    assert client.post('/api/identity/links/'+str(r.json()['link_id'])+'/undo').json()['separated']
    ps=client.get('/api/people').json()
    assert len(ps)==2 and sorted(p['value'] for p in ps)==[2000,4000]
    with module.db() as c:
        assert [tuple(r) for r in c.execute('SELECT * FROM attendance ORDER BY id')]==before
        assert c.execute('SELECT COUNT(*) FROM import_rows').fetchone()[0]==2
    assert client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).status_code==409


def test_distinct_events_after_merge_overlap(client):
    e=event(client,value=2000)
    upload(client,e,'Nome completo,Email,Importo\nAnna Rossi,a@test.it,10\nAna Rossi,a@test.it,20\n')
    r=client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'})
    assert r.status_code==200
    p=client.get('/api/people').json()[0]
    assert p['visits']==1 and p['value']==2000 and p['actual_spend']==3000
    client.post('/api/identity/2/split')
    assert len(client.get('/api/people').json())==2
    assert client.get('/api/dashboard').json()['attributed_value']==4000


def test_homonyms_with_different_email_never_auto_merge(client):
    e=event(client)
    upload(client,e,'Nome completo,Email\nAnna Rossi,anna.one@example.test\nAnna Rossi,anna.two@example.test\n')
    assert len(client.get('/api/people').json())==2
    assert client.get('/api/matches').json()==[]
    assert client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).status_code==200


def test_automatic_personal_email_compatible_and_presumed_name(client):
    e=event(client,value=1000)
    r=upload(client,e,'Nome completo,Email\nGiulia Rossi,giulia.rossi@example.test\nGiulia Rosi,giulia.rossi@example.test\n')
    assert r.json()['automatic']==1
    assert len(client.get('/api/people').json())==1
    assert len(client.get('/api/people').json()[0]['members'])==2
    e2=event(client)
    r=upload(client,e2,'Nome completo,Email\nGiulia Rossi,\n')
    assert r.json()['presumed']==1
    assert len(client.get('/api/people').json())==1
    assert client.get('/api/identity/history').json()[0]['reason'].startswith('Presunta')


def test_partial_generic_incompatible_and_multiple_candidates_review(client):
    e=event(client)
    upload(client,e,'Nome completo,Email\nAnna Rossi,anna@example.test\nGianni Verdi,anna@example.test\nAnna,anna@example.test\n')
    assert len(client.get('/api/people').json())==3
    assert client.get('/api/matches').json()
    upload(client,e,'Nome completo,Email\nMario Bianchi,mario.one@example.test\nMario Bianchi,mario.two@example.test\nMario Bianchi,\n')
    ps=client.get('/api/people').json()
    assert len([p for p in ps if p['name']=='Mario Bianchi'])==3
    upload(client,e,'Nome completo\nSolo\n')
    assert next(p for p in client.get('/api/people').json() if p['name']=='Solo')['incomplete']


def test_preview_confirmation_idempotence_sources_and_default_status(client):
    e=event(client,value=2000)
    data=b'Nome completo,Email,Prezzo\nAnna Rossi,anna@example.test,99\n'
    r=preview(client,e,data)
    assert r.status_code==200
    assert r.json()['summary']['imported']==1
    assert client.get('/api/people').json()==[]  # Simulation rolled back completely.
    token=r.json()['token']
    result=client.post(f'/api/imports/{token}/confirm')
    assert result.status_code==200
    p=client.get('/api/people').json()[0]
    assert p['visits']==0 and p['registrations']==1 and p['value']==0
    iid=result.json()['import_id']
    assert client.get(f'/api/imports/{iid}/original').content==data
    r=preview(client,e,data)
    assert r.json()['summary']['skipped']==1
    assert client.post('/api/imports/'+r.json()['token']+'/confirm').status_code==200
    with module.db() as c:
        assert c.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM import_rows').fetchone()[0]==1
    assert client.post(f'/api/imports/{token}/confirm').status_code==410


def test_confirmed_import_upgrades_registration_without_duplicate(client):
    e=event(client,value=2000)
    data=b'Nome completo\nAnna Rossi\n'
    r=preview(client,e,data)
    client.post('/api/imports/'+r.json()['token']+'/confirm')
    r=preview(client,e,data,status='confirmed')
    assert r.json()['summary']['updated']==1
    client.post('/api/imports/'+r.json()['token']+'/confirm')
    assert client.get('/api/people').json()[0]['visits']==1
    assert client.get('/api/people').json()[0]['value']==2000
    with module.db() as c:
        assert c.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM import_rows').fetchone()[0]==2
        assert c.execute('SELECT COUNT(*) FROM status_history').fetchone()[0]==1


def test_workbook_sheet_selection_manual_mapping_and_stale_preview(client):
    e=event(client)
    book=Workbook();book.active.title='Ignora';book.active.append(['Note']);book.active.append(['non importare'])
    sheet=book.create_sheet('Ospiti');sheet.append(['Cliente custom','Costo custom']);sheet.append(['Anna Rossi',12])
    data=io.BytesIO();book.save(data);data=data.getvalue()
    inspection=client.post('/api/imports/inspect',files={'file':('multi.xlsx',data)},data={'sheet':'Ospiti'})
    assert inspection.json()['sheets']==['Ignora','Ospiti']
    mapping={'name':0,'first':None,'last':None,'email':None,'phone':None,'amount':1}
    r=preview(client,e,data,'multi.xlsx',sheet='Ospiti',mapping=json.dumps(mapping))
    assert r.status_code==200 and r.json()['sample'][0]['name']=='Anna Rossi'
    client.put(f'/api/events/{e}',json={'name':'Changed','date':'2026-01-01','participant_value_cents':2000})
    assert client.post('/api/imports/'+r.json()['token']+'/confirm').status_code==409
    r=preview(client,e,data,'multi.xlsx',sheet='Ospiti',mapping=json.dumps(mapping))
    assert client.post('/api/imports/'+r.json()['token']+'/confirm').status_code==200
    assert client.get('/api/people').json()[0]['actual_spend']==1200
    assert preview(client,e,data,'multi.xlsx',sheet='missing',mapping=json.dumps(mapping)).status_code==400
    assert preview(client,e,data,'multi.xlsx',sheet='Ospiti',mapping='[]').status_code==400


def test_explicit_status_updates_ranking(client):
    e=event(client,value=4000)
    # Missing status must always mean registration, also in compatibility endpoint.
    r=client.post(f'/api/events/{e}/import',files={'file':('x.csv',b'Nome completo\nAnna Rossi\n')})
    assert r.status_code==200
    assert client.get('/api/people?ranked=true').json()==[]
    pid=client.get('/api/people').json()[0]['id']
    record=client.get(f'/api/people/{pid}').json()['events'][0]['records'][0]['id']
    client.patch(f'/api/attendance/{record}',json={'status':'confirmed'})
    assert client.get('/api/people?ranked=true').json()[0]['value']==4000
    client.patch(f'/api/attendance/{record}',json={'status':'registered'})
    assert client.get('/api/people?ranked=true').json()==[]


def test_group_conflict_and_split_are_permanent(client):
    e=event(client)
    upload(client,e,'Nome completo,Email\nAnna Rossi,a@test.it\nAna Rossi,a@test.it\nAnnamaria Rossi,a@test.it\n')
    client.post('/api/matches/decision',json={'a':1,'b':3,'action':'separate'})
    assert client.post('/api/matches/decision',json={'a':2,'b':3,'action':'merge'}).status_code==200
    assert client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).status_code==409
    assert client.post('/api/identity/2/split').status_code==200
    module.init()
    assert client.post('/api/matches/decision',json={'a':2,'b':3,'action':'merge'}).status_code==409


def make_legacy(path):
    with sqlite3.connect(path) as c:
        c.executescript('''
        CREATE TABLE people(id INTEGER PRIMARY KEY,name TEXT,email TEXT,phone TEXT);
        CREATE TABLE events(id INTEGER PRIMARY KEY,name TEXT,date TEXT,location TEXT,cost INTEGER);
        CREATE TABLE attendance(id INTEGER PRIMARY KEY,event_id INTEGER REFERENCES events(id),person_id INTEGER REFERENCES people(id),amount INTEGER,UNIQUE(event_id,person_id));
        INSERT INTO people VALUES(1,'Legacy Person','legacy@example.test','');
        INSERT INTO events VALUES(1,'Legacy Event','2026-01-01','Milano',1200);
        INSERT INTO attendance VALUES(1,1,1,3400);
        ''')


def test_backup_verified_before_migration_and_repeatability(tmp_path):
    path=tmp_path/'old.db';make_legacy(path)
    migrate(path)
    backups=list((tmp_path/'backups').glob('*.db'))
    assert len(backups)==1
    manifest=json.loads(backups[0].with_suffix('.json').read_text())
    assert hashlib.sha256(backups[0].read_bytes()).hexdigest()==manifest['sha256']
    with sqlite3.connect(backups[0]) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('PRAGMA user_version').fetchone()[0]==0
        assert c.execute('SELECT amount FROM attendance').fetchone()[0]==3400
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT amount,status FROM attendance').fetchone()==(3400,'unknown')
        assert c.execute('SELECT participant_value_cents FROM events').fetchone()[0] is None
    migrate(path)
    assert len(list((tmp_path/'backups').glob('*.db')))==1


def test_backup_failure_blocks_migration(tmp_path,monkeypatch):
    from backend import migrations
    path=tmp_path/'old.db';make_legacy(path)
    def fail(_):
        raise RuntimeError('Disk failure')
    monkeypatch.setattr(migrations,'backup_database',fail)
    with pytest.raises(RuntimeError):migrations.migrate(path)
    with sqlite3.connect(path) as c:
        assert 'status' not in {row[1] for row in c.execute('PRAGMA table_info(attendance)')}
        assert c.execute('SELECT amount FROM attendance').fetchone()[0]==3400


def test_archival_preserves_original_rows(client):
    e=event(client)
    upload(client,e,'Nome completo\nAnna Rossi\n')
    assert client.delete(f'/api/events/{e}').status_code==200
    assert client.get('/api/events').json()==[]
    with module.db() as c:
        assert c.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM import_rows').fetchone()[0]==1


def test_duplicate_rows_preserve_source_without_double_count(client):
    e=event(client,value=2000)
    r=upload(client,e,'Nome completo,Email,Importo\nAnna Rossi,anna@example.test,10\nAnna Rossi,anna@example.test,10\n')
    assert r.json()['imported']==1 and r.json()['skipped']==1
    with module.db() as c:
        assert c.execute('SELECT COUNT(*) FROM import_rows').fetchone()[0]==2
        assert c.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]==1
    p=client.get('/api/people').json()[0]
    assert p['value']==2000 and p['actual_spend']==1000


def test_generic_email_not_sufficient_and_incomplete_not_assumed(client):
    e=event(client)
    upload(client,e,'Nome completo,Email\nGiulia Rossi,info@example.test\nGiulia Rosi,info@example.test\nSolo,\n')
    e2=event(client)
    upload(client,e2,'Nome completo\nSolo\n')
    ps=client.get('/api/people').json()
    assert len(ps)==4
    assert len([p for p in ps if p['name']=='Solo'])==2
    assert client.get('/api/matches').json()


def test_xls_multi_sheet_inspection_and_preview(client):
    import xlwt
    e=event(client)
    book=xlwt.Workbook()
    for name in ['Primo','Secondo']:
        sheet=book.add_sheet(name)
        sheet.write(0,0,'Partecipante');sheet.write(1,0,'Persona '+name)
    data=io.BytesIO();book.save(data);data=data.getvalue()
    info=client.post('/api/imports/inspect',files={'file':('multi.xls',data)},data={'sheet':'Secondo'}).json()
    assert info['sheets']==['Primo','Secondo'] and info['sheet']=='Secondo'
    r=preview(client,e,data,'multi.xls',sheet='Secondo')
    assert r.json()['sample'][0]['name']=='Persona Secondo'
    assert client.post('/api/imports/'+r.json()['token']+'/confirm').status_code==200
