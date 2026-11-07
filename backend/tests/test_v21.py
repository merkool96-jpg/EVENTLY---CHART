"""V2.1 acceptance tests, synthetic data only. No user database is opened."""
import io,json,sqlite3
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend import app as module

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'v21.db'));module.init();return TestClient(module.app)

@pytest.mark.parametrize('count',[200,10000])
def test_quality_real_pagination_bounded_payload_and_search(client,count):
    with module.db(True) as c:c.executemany('INSERT INTO people(name) VALUES(?)',[(f'Debole{i:05}',) for i in range(count)])
    a=client.get('/api/v2/quality?kind=incomplete&page=1&page_size=50').json()
    b=client.get('/api/v2/quality?kind=incomplete&page=2&page_size=50').json()
    assert a['total']==b['total']==count and a['pages']==count//50
    assert len(a['rows'])==len(b['rows'])==50
    assert not {p['id'] for p in a['rows']}&{p['id'] for p in b['rows']}
    last=client.get('/api/v2/quality',params={'kind':'no_email','page':count//50}).json()
    assert len(last['rows'])==50 and last['rows'][-1]['id']==count
    found=client.get('/api/v2/quality?kind=incomplete&q=Debole00099').json()
    assert found['total']==1 and found['rows'][0]['id']==100
    assert len(client.get('/api/v2/quality?page_size=999999').json()['rows'])==200


def test_blocked_group_diagnostics_and_audited_link_correction(client):
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[('Mario Rossi','one@example.test'),('Mario Rossi','two@example.test'),('Luca Rossi','one@example.test'),('Non Coinvolto','other@example.test')])
        c.execute("INSERT INTO events(name,date,participant_value_cents) VALUES('Originale','2026-01-01',2000)")
        c.executemany("INSERT INTO attendance(event_id,person_id,status) VALUES(1,?,'confirmed')",[(i,) for i in range(1,5)])
    joined=client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).json()['link_id']
    with module.db() as c:original=[tuple(r) for r in c.execute('SELECT * FROM attendance')]
    blocked=client.get('/api/v2/identity?queue=conflicts').json()
    assert blocked['total']==1 and not blocked['rows'][0]['can_merge']
    diag=client.get('/api/v2/identity/resolve?a=1&b=3').json()
    assert any(r['rule']=='identita_incompatibili' and r.get('blocking') for r in diag['rules'])
    assert any(r['rule']=='email_potenzialmente_condivisa' for r in diag['rules'])
    assert len(diag['members_a'])==2 and len(diag['links'])==1
    assert client.post('/api/matches/decision',json={'a':1,'b':3,'action':'merge'}).status_code==409
    preview=client.get(f'/api/v2/identity/links/{joined}/preview-undo').json()
    assert preview['before']['people']==3 and preview['after']['people']==4
    assert client.post(f'/api/identity/links/{joined}/undo',params={'expected_snapshot':preview['snapshot']}).status_code==200
    assert client.get('/api/v2/identity/resolve?a=1&b=3').json()['can_merge']
    with module.db() as c:
        assert original==[tuple(r) for r in c.execute('SELECT * FROM attendance')]
        assert c.execute("SELECT COUNT(*) FROM decisions WHERE action='undo'").fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM people').fetchone()[0]==4
    other=client.get('/api/people/4').json();assert other['visits']==1 and other['value']==2000
    # Undo added an intentional separation: explicit revocation never auto-merges.
    separated=client.get('/api/v2/identity/resolve?a=1&b=2').json()
    assert not separated['can_merge'] and any(r['rule']=='separazione_precedente' for r in separated['rules'])
    assert client.post('/api/v2/separations/revoke',json={'a':1,'b':2}).status_code==200
    assert len(client.get('/api/people').json())==4


def test_analytics_segments_exact_people_and_exports(client):
    with module.db(True) as c:
        for i in range(1,5):c.execute('INSERT INTO people(name) VALUES(?)',(f'Persona{i} Cognome{i}',))
        for i in range(1,4):c.execute('INSERT INTO events(name,date,category,participant_value_cents) VALUES(?,?,?,?)',(f'Evento{i}',f'{2024+i}-01-01','Community',0 if i==1 else 2000))
        c.executemany("INSERT INTO attendance(event_id,person_id,status) VALUES(?,?,'confirmed')",[(1,1),(2,1),(3,1),(2,2),(3,2),(3,3)])
    all_data=client.get('/api/v2/analytics').json()
    assert all_data['new'] is None and all_data['returning'] is None and all_data['historical_returning']==2
    filters={'start':'2026-01-01','end':'2026-12-31','category':'Community'}
    scoped=client.get('/api/v2/analytics',params={'filters':json.dumps(filters)}).json()
    assert scoped['new']==1 and scoped['returning']==1
    for n in (2,3,5,10):
        query={**filters,'min_visits':n}
        rows=client.get('/api/v2/people',params={'filters':json.dumps(query)}).json()
        assert rows['total']==scoped['frequencies'][str(n)]
        assert client.get('/api/exports/count',params={'filters':json.dumps(query)}).json()['count']==rows['total']
    for days in (30,90,180,365):
        rows=client.get('/api/v2/people',params={'filters':json.dumps({**filters,'inactive_days':days})}).json()
        assert rows['total']==scoped['inactive'][str(days)]
    assert client.get('/api/v2/people',params={'filters':json.dumps({'global_min_visits':2})}).json()['total']==2
    known=client.get('/api/dashboard').json()['attributed_value']
    assert known==all_data['attributed_value']==10000
    assert sum(e['attributed_value'] or 0 for e in client.get('/api/events').json())==known
    assert sum(p['value'] for p in client.get('/api/v2/people?ranked=true').json()['rows'])==known
    assert client.get('/api/people/1').json()['value']==4000
    book=load_workbook(io.BytesIO(client.get('/api/exports/participants').content))
    headers=list(book['Partecipanti'].values)[0];column=headers.index('Valore attribuito totale EUR')
    assert sum(r[column] for r in list(book['Partecipanti'].values)[1:])*100==known


def test_backup_metadata_and_preview_comparison(client):
    client.post('/api/events',json={'name':'Sintetico','date':'2026-01-01'})
    backup=client.post('/api/backup').json()['file']
    metadata=next(r for r in client.get('/api/v2/backups').json() if r['name']==backup)
    assert metadata['verified'] and metadata['schema_version']==5 and metadata['counts']['events']==1
    blob=client.get('/api/v2/backups/'+backup).content
    client.post('/api/events',json={'name':'Secondo','date':'2026-02-01'})
    draft=client.post('/api/v2/restore/preview',files={'file':('backup.db',blob)}).json()
    assert draft['current_counts']['events']==2 and draft['counts']['events']==1
    assert len(client.get('/api/events').json())==2


def test_stale_correction_preview_and_old_backup_metadata(client,tmp_path):
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[('Sofia','sofia@example.test'),('Sofia Di Gio','sofia@example.test')])
    joined=client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).json()['link_id']
    preview=client.get(f'/api/v2/identity/links/{joined}/preview-undo').json()
    client.post('/api/events',json={'name':'Intervento successivo','date':'2026-01-01'})
    assert client.post(f'/api/identity/links/{joined}/undo',params={'expected_snapshot':preview['snapshot']}).status_code==409
    assert len(client.get('/api/people').json())==1
    from backend.backup_info import describe_backup
    legacy=tmp_path/'legacy.db'
    with sqlite3.connect(legacy) as c:
        for table in ('people','events','attendance'):c.execute(f'CREATE TABLE {table}(id INTEGER PRIMARY KEY)')
    info=describe_backup(legacy)
    assert info['verified'] and info['counts']['people']==0 and info['counts']['imports'] is None
    bad=tmp_path/'corrupt.db';bad.write_bytes(b'not a database')
    assert not describe_backup(bad)['verified']
