"""Acceptance IDs refer to the PRE-IMPLEMENTATION matrix in docs/."""
import io,json,sqlite3
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook,load_workbook
from backend import app as module
from backend.migrations import migrate

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'v2.db'));module.init();return TestClient(module.app)

def event(c,name='Evento',day='2026-01-01',value=2000):
    return c.post('/api/events',json={'name':name,'date':day,'participant_value_cents':value}).json()['id']

def upload(c,e,text,status='registered'):
    r=c.post(f'/api/events/{e}/import',files={'file':('x.csv',text.encode())},data={'status':status});assert r.status_code==200,r.text;return r.json()

def test_13_16_17_22_incomplete_rows_header_and_issues(client):
    e=event(client)
    result=upload(client,e,'Elenco clienti,,,,\nNome,Cognome,Email,Importo,Extra\nMaria Anna,De Luca,,20,x\nMario,,mario@test.it,0,x\n,,only@test.it,0,x\n,Nessuno,,0,x\n,,,0,riga senza ID\nErrore,Rossi,bad,0,x\n')
    assert result['rows_read']==6 and result['valid_rows']==4 and result['issue_rows']==2
    ps=client.get('/api/people').json();assert len(ps)==4
    p=next(p for p in ps if p['email']=='only@test.it');assert p['name']==''
    compound=next(p for p in ps if p['name']=='Maria Anna De Luca');assert compound['first_name']=='Maria Anna' and compound['last_name']=='De Luca'
    assert client.get('/api/v2/quality?kind=unassigned').json()['counts']['unassigned']==2
    with module.db() as c:assert c.execute('SELECT COUNT(*) FROM import_issues').fetchone()[0]==2


def test_21_27_conflicting_sources_and_admin_override(client):
    e=event(client)
    upload(client,e,'Nome completo,Email\nMario Rossi,mario@test.it\n','registered')
    upload(client,e,'Nome completo,Email\nMario Rossi,mario@test.it\n','confirmed')
    assert client.get('/api/people').json()[0]['visits']==1
    upload(client,e,'Nome completo,Email\nMario Rossi,mario@test.it\n','absent')
    p=client.get('/api/people').json()[0];assert p['visits']==0 and p['conflicts']==1
    assert client.get('/api/v2/events/'+str(e)).json()['rows'][0]['participation']['conflict']
    draft=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'confirmed','ids':None}).json()
    assert draft['changed']==1
    assert client.post('/api/v2/bulk/'+draft['token']+'/confirm').status_code==200
    assert client.get('/api/people').json()[0]['visits']==1
    assert client.post('/api/v2/bulk/'+draft['token']+'/undo').status_code==200
    assert client.get('/api/people').json()[0]['conflicts']==1


def test_26_two_hundred_bulk_all_filtered_and_undo(client):
    e=event(client)
    with module.db(True) as c:
        for i in range(200):
            pid=c.execute('INSERT INTO people(name) VALUES(?)',(f'Persona {i}',)).lastrowid
            aid=c.execute("INSERT INTO attendance(event_id,person_id,status) VALUES(?,?,'registered')",(e,pid)).lastrowid
            c.execute("INSERT INTO attendance_evidence(attendance_id,status,source) VALUES(?,'registered','test')",(aid,))
    d=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'confirmed','q':'Persona'}).json();assert d['changed']==200
    assert client.get('/api/dashboard').json()['attendance']==0
    assert client.post('/api/v2/bulk/'+d['token']+'/confirm').json()['changed']==200
    assert client.get('/api/dashboard').json()['attendance']==200
    assert client.post('/api/v2/bulk/'+d['token']+'/undo').json()['restored']==200
    assert client.get('/api/dashboard').json()['attendance']==0


def test_33_archive_keeps_ranking_distinct_exclusion_preview(client):
    e=event(client);upload(client,e,'Nome completo\nMario Rossi\n','confirmed')
    client.delete('/api/events/'+str(e));assert client.get('/api/people').json()[0]['visits']==1
    preview=client.post(f'/api/v2/events/{e}/analytics-impact',json={'include':False}).json();assert preview['presences_after']==0
    assert client.get('/api/people').json()[0]['visits']==1
    client.post(f'/api/v2/events/{e}/analytics-impact',json={'include':False,'confirm':True});assert client.get('/api/people').json()[0]['visits']==0
    client.post(f'/api/v2/events/{e}/analytics-impact',json={'include':True,'confirm':True});assert client.get('/api/people').json()[0]['visits']==1


def test_11_revoke_no_auto_merge(client):
    e=event(client);upload(client,e,'Nome completo,Email\nMario Rossi,a@test.it\nMario Rosssi,a@test.it\n')
    client.post('/api/matches/decision',json={'a':1,'b':2,'action':'separate'})
    assert client.get('/api/matches').json()==[]
    assert client.post('/api/v2/separations/revoke',json={'a':1,'b':2}).status_code==200
    assert len(client.get('/api/people').json())==2
    assert client.get('/api/matches').json()


def test_31_32_search_before_top50_and_shared_export_filters(client):
    e=event(client)
    with module.db(True) as c:
        for i in range(61):
            pid=c.execute('INSERT INTO people(name) VALUES(?)',(f'Persona {i:02}',)).lastrowid
            c.execute("INSERT INTO attendance(event_id,person_id,status) VALUES(?,?,'confirmed')",(e,pid))
    r=client.get('/api/v2/people?ranked=true&q=Persona%2060').json();assert r['total']==1 and r['rows'][0]['name']=='Persona 60'
    f=json.dumps({'event_id':e,'min_visits':1})
    count=client.get('/api/exports/count',params={'filters':f,'q':'Persona 60'}).json()['count']
    assert count==1
    book=load_workbook(io.BytesIO(client.get('/api/exports/participants',params={'filters':f,'q':'Persona 60'}).content));assert book['Partecipanti'].max_row==2


def test_34_36_history_before_period_and_return_window(client):
    a=event(client,'2025','2025-12-01',0);b=event(client,'2026','2026-01-01',2000)
    for e in (a,b):upload(client,e,'Nome completo,Email\nMario Rossi,mario@test.it\n','confirmed')
    data=client.get('/api/v2/analytics',params={'filters':json.dumps({'start':'2026-01-01'})}).json()
    assert data['new']==0 and data['returning']==1
    assert all(e['id']!=a for e in data['events'])
    all_data=client.get('/api/v2/analytics').json()
    old=next(e for e in all_data['events'] if e['id']==a);assert old['returned_after']==1
    new=next(e for e in data['events'] if e['id']==b);assert new['returned_after']==0
    assert old['conversion'] is None and new['conversion'] is None


def test_39_41_upgrade_v12_no_original_data_loss(tmp_path):
    path=tmp_path/'v12.db';migrate(path,target_version=3)
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO people(name,email) VALUES('Sintetico','fake@test.it')")
        c.execute("INSERT INTO events(name,date,cost) VALUES('Storico','2025-01-01',0)")
        c.execute("INSERT INTO attendance(event_id,person_id,amount,status) VALUES(1,1,200,'confirmed')")
        before=c.execute('SELECT * FROM attendance').fetchall()
    migrate(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==4
        assert c.execute('SELECT * FROM attendance').fetchall()==before
        assert c.execute('SELECT COUNT(*) FROM attendance_evidence').fetchone()[0]==1
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
    assert list((tmp_path/'backups').glob('*.db'))


def test_40_restore_verified_copy_confirmation(client,tmp_path):
    e=event(client);upload(client,e,'Nome completo\nPrima Persona\n')
    original=client.post('/api/backup').json()['file']
    blob=client.get('/api/v2/backups/'+original).content
    upload(client,e,'Nome completo\nSeconda Persona\n')
    draft=client.post('/api/v2/restore/preview',files={'file':('restore.db',blob)}).json()
    assert draft['counts']['people']==1 and len(client.get('/api/people').json())==2
    assert client.post('/api/v2/restore/'+draft['token']+'/confirm').status_code==200
    assert len(client.get('/api/people').json())==1


def test_21_weak_same_source_registration_presence_no_new_people(client):
    e=event(client)
    text='Nome\nMario\nMario\n'
    first=upload(client,e,text,'registered');assert first['imported']==2
    second=upload(client,e,text,'confirmed');assert second['updated']==2 and second['imported']==0
    assert len(client.get('/api/people').json())==2
    assert client.get('/api/dashboard').json()['attendance']==2


def test_5_6_7_compound_aliases_require_review_and_keep_sources(client):
    e=event(client)
    for a,b,email in [('Iside Oliveti','Iside Oliveti Oliveti','iside@test.it'),('Francesco Son','Francesco Sonnessa','francesco@test.it'),('Rebecca Lai','Rebecca Lai Musa','rebecca@test.it')]:
        result=upload(client,e,f'Nome completo,Email\n{a},{email}\n{b},{email}\n')
        assert result['automatic']==0
    matches=client.get('/api/v2/identity').json()['rows'];assert len(matches)==3
    assert all(m['can_merge'] for m in matches)
    pair=next(m for m in matches if 'Iside' in m['a']['name'])
    preview=client.post('/api/matches/preview',json={'a':pair['a']['id'],'b':pair['b']['id']}).json()
    assert preview['recommended']['display_name']=='Iside Oliveti'


def test_19_order_shared_never_identity_registration_key_preserves_weak(client):
    e=event(client)
    first=upload(client,e,'Nome,Email,ID ordine,ID registrazione\nMario,,ORD-1,TICKET-A\nLuca,,ORD-1,TICKET-B\n')
    assert first['imported']==2
    second=upload(client,e,'Nome,Email,ID ordine,ID registrazione\nMario,,ORD-1,TICKET-A\nLuca,,ORD-1,TICKET-B\n','confirmed')
    assert second['updated']==2 and len(client.get('/api/people').json())==2
    assert client.get('/api/dashboard').json()['attendance']==2


def test_25_absent_cancelled_never_enter_ranking_and_bulk_undo_guard(client):
    e=event(client)
    upload(client,e,'Nome completo,Email\nMario Rossi,mario@test.it\n','absent')
    assert client.get('/api/v2/people?ranked=true').json()['total']==0
    a=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'confirmed'}).json()['token'];client.post('/api/v2/bulk/'+a+'/confirm')
    b=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'cancelled'}).json()['token'];client.post('/api/v2/bulk/'+b+'/confirm')
    assert client.post('/api/v2/bulk/'+a+'/undo').status_code==409
    assert client.get('/api/v2/people?ranked=true').json()['total']==0


def test_views_templates_defer_and_duplicate_event_warning(client):
    e=event(client,'Bottini Milano','2026-10-01')
    possible=client.get('/api/v2/events/similar?name=Bottini%20Milano!&day=2026-10-01').json();assert possible[0]['id']==e
    assert client.get('/api/v2/events/similar?name=Bottini%20Milano&day=2026-10-02').json()==[]
    assert client.post('/api/v2/views',json={'name':'Ricorrenti','filters':{'min_visits':2}}).status_code==200
    assert client.get('/api/v2/views').json()[0]['name']=='Ricorrenti'
    assert client.post('/api/v2/mapping-templates',json={'name':'Mio formato','headers':['Nome'],'mapping':{'first':0}}).status_code==200
    assert client.get('/api/v2/mapping-templates').json()[0]['name']=='Mio formato'
    upload(client,e,'Nome completo,Email\nMario Rossi,a@test.it\nMario Rosssi,a@test.it\n')
    client.post('/api/v2/identity/defer',json={'a':1,'b':2})
    assert client.get('/api/v2/identity').json()['rows']==[]
    assert len(client.get('/api/v2/identity?deferred=true').json()['rows'])==1
    client.post('/api/v2/identity/resume',json={'a':1,'b':2})
    assert len(client.get('/api/v2/identity').json()['rows'])==1


def test_35_complete_registration_conversion_requires_known_outcomes(client):
    e=event(client)
    upload(client,e,'Nome completo,Email\nMario Rossi,m@test.it\nLuca Rossi,l@test.it\n')
    client.put('/api/events/'+str(e),json={'name':'Completo','date':'2026-01-01','registration_complete':True})
    assert client.get('/api/v2/analytics').json()['events'][0]['conversion'] is None
    a=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'confirmed','ids':[1]}).json();client.post('/api/v2/bulk/'+a['token']+'/confirm')
    b=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'absent','ids':[2]}).json();client.post('/api/v2/bulk/'+b['token']+'/confirm')
    assert client.get('/api/v2/analytics').json()['events'][0]['conversion']==.5


def test_pattern_email_and_structured_double_given_name_no_false_merge(client):
    e=event(client)
    result=upload(client,e,'Nome,Cognome,Contatto sconosciuto\nMaria Anna,De Luca,maria.anna@test.it\nMaria Sara,De Luca,sara@test.it\n')
    assert result['valid_rows']==2
    people=client.get('/api/people').json();assert {p['first_name'] for p in people}=={'Maria Anna','Maria Sara'}
    assert {p['email'] for p in people}=={'maria.anna@test.it','sara@test.it'}
    assert client.get('/api/matches').json()==[]


def test_37_frequency_free_paid_and_export_five_states(client):
    free=[event(client,'Gratuito '+str(i),f'2026-01-0{i+1}',0) for i in range(3)]
    paid=event(client,'Valore positivo','2026-02-01',4000)
    for e in free:upload(client,e,'Nome completo,Email\nFrequente Gratuita,free@test.it\n','confirmed')
    upload(client,paid,'Nome completo,Email\nOccasionale Pagante,paid@test.it\n','confirmed')
    upload(client,paid,'Nome completo,Email\nPersona Assente,absent@test.it\n','absent')
    upload(client,paid,'Nome completo,Email\nPersona Annullata,cancelled@test.it\n','cancelled')
    people=client.get('/api/v2/people?ranked=true&sort=value').json()['rows']
    assert [p['name'] for p in people]==['Occasionale Pagante','Frequente Gratuita']
    assert people[1]['visits']==3 and people[1]['value']==0
    book=load_workbook(io.BytesIO(client.get('/api/exports/participants').content))
    es=[dict(zip(list(book['Eventi'].values)[0],row)) for row in list(book['Eventi'].values)[1:]]
    e=next(e for e in es if e['Evento']=='Valore positivo')
    assert e['Assenti inclusi']==1 and e['Annullati inclusi']==1 and e['Da verificare inclusi']==0
    assert client.get('/api/v2/analytics').json()['frequencies']['3']==1


def test_38_xlsx_ten_thousand_and_one_all_three_sheets_read_only(client):
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[(f'Sintetica {i}',f'fake{i}@example.test') for i in range(10001)])
        before=c.total_changes
    book=load_workbook(io.BytesIO(client.get('/api/exports/participants').content),read_only=True)
    assert book.sheetnames==['Partecipanti','Partecipazioni','Eventi']
    assert sum(1 for _ in book['Partecipanti'].values)==10002
    with module.db() as c:assert c.execute('SELECT COUNT(*) FROM people').fetchone()[0]==10001


def test_stale_bulk_invalid_restore_and_explicit_registration_conflict(client):
    e=event(client)
    upload(client,e,'Nome,Email,ID registrazione\nMario,m@test.it,REG1\n')
    draft=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'confirmed'}).json()
    result=upload(client,e,'Nome,Email,ID registrazione\nLuca,l@test.it,REG1\n','confirmed')
    assert result['issue_rows']==1
    assert client.post('/api/v2/bulk/'+draft['token']+'/confirm').status_code==409
    assert client.post('/api/v2/restore/preview',files={'file':('bad.db',b'not sqlite')}).status_code==400
    assert client.get('/api/dashboard').json()['attendance']==0
    assert len(client.get('/api/people').json())==1
