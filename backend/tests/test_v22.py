import io,json,sqlite3
from datetime import date,timedelta
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend import app as module
from backend.migrations import migrate

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'v22.db'));module.init();return TestClient(module.app)

def seed(count=2,visits=5):
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[(f'Persona{i} Cognome{i}',f'p{i}@example.test') for i in range(count)])
        for i in range(visits):
            eid=c.execute('INSERT INTO events(name,date,participant_value_cents) VALUES(?,?,?)',(f'Evento{i}',(date.today()-timedelta(days=i+1)).isoformat(),2000 if i else 0)).lastrowid
            c.execute("INSERT INTO attendance(event_id,person_id,status) VALUES(?,1,'confirmed')",(eid,))

def batch(c,action,ids=None,data=None,filters=None):
    r=c.post('/api/v22/bulk/preview',json={'action':action,'ids':ids,'data':data or {},'filters':filters or {}});assert r.status_code==200,r.text;return r.json()

def confirm(c,d):
    r=c.post('/api/v22/bulk/'+d['token']+'/confirm');assert r.status_code==200,r.text;return r.json()


def test_1_2_3_17_dynamic_segments_vip_and_new_import(client):
    seed(visits=4)
    assert client.get('/api/v2/people',params={'filters':json.dumps({'community_segment':'super'})}).json()['total']==0
    e=client.post('/api/events',json={'name':'Quinta','date':date.today().isoformat()}).json()['id']
    r=client.post(f'/api/events/{e}/import',files={'file':('new.csv',b'Nome completo,Email\nPersona0 Cognome0,p0@example.test\n')},data={'status':'confirmed'});assert r.status_code==200
    assert client.get('/api/v2/people',params={'filters':json.dumps({'community_segment':'super'})}).json()['total']==1
    confirm(client,batch(client,'vip_add',[1]))
    draft=client.post('/api/v2/bulk/preview',json={'event_id':e,'status':'absent'}).json();client.post('/api/v2/bulk/'+draft['token']+'/confirm')
    assert client.get('/api/v2/people',params={'filters':json.dumps({'community_segment':'super'})}).json()['total']==0
    assert client.get('/api/v22/people/1').json()['vip']
    with module.db(True) as c:c.execute("UPDATE events SET date='2020-01-01'")
    assert client.get('/api/v22/people/1').json()['vip']


def test_4_5_tag_100_bulk_atomic_undo_and_stale(client):
    seed(120,1);tid=client.post('/api/v22/tags',json={'name':'Da premiare','color':'#2f654b'}).json()['id']
    assert client.post('/api/v22/tags',json={'name':'  DA PRÉMIARE  '}).status_code==409
    assert client.post('/api/v22/tags',json={'name':'VIP'}).status_code==422
    d=batch(client,'tag_add',list(range(1,101)),{'tag_ids':[tid]});assert d['changed']==100
    assert not client.get('/api/people/1').json()['tags'];confirm(client,d)
    assert client.get('/api/v2/people',params={'filters':json.dumps({'tag_ids':[tid]})}).json()['total']==100
    assert client.post('/api/v22/bulk/'+d['token']+'/undo').status_code==200
    assert client.get('/api/v2/people',params={'filters':json.dumps({'tag_ids':[tid]})}).json()['total']==0
    stale=batch(client,'vip_add',[1]);client.post('/api/v22/people/1/notes',json={'text':'Nota riservata'})
    assert client.post('/api/v22/bulk/'+stale['token']+'/confirm').status_code==409


def test_6_7_merge_split_ownership_notes_rewards_and_tags(client):
    with module.db(True) as c:c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[('Sofia','sofia@example.test'),('Sofia Di Gio','sofia@example.test')])
    tags=[client.post('/api/v22/tags',json={'name':n}).json()['id'] for n in ('Partner','Storico')]
    for pid,tid in zip((1,2),tags):confirm(client,batch(client,'tag_add',[pid],{'tag_ids':[tid]}));client.post(f'/api/v22/people/{pid}/notes',json={'text':f'Origine {pid}'})
    link=client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).json()['link_id']
    p=client.get('/api/people/1').json();assert {t['id'] for t in p['tags']}==set(tags)
    note=client.post('/api/v22/people/1/notes',json={'text':'Aggiunta sul gruppo'}).json()['id']
    confirm(client,batch(client,'reward',[1],{'name':'Grazie','type':'Voucher','date':date.today().isoformat(),'status':'proposed'}))
    client.post(f'/api/identity/links/{link}/undo')
    a=client.get('/api/v22/people/1').json();b=client.get('/api/v22/people/2').json()
    assert [r['data']['text'] for r in a['records'] if r['kind']=='note']==['Origine 1']
    assert [r['data']['text'] for r in b['records'] if r['kind']=='note']==['Origine 2']
    pending=client.get('/api/v22/unresolved').json();assert len(pending)==2
    row=next(r for r in pending if r['id']==note)
    assert client.post(f'/api/v22/records/{note}/reassign',json={'person_id':2,'revision':row['revision'],'reason':'Appartiene alla seconda Sofia'}).status_code==200
    assert len([r for r in client.get('/api/v22/people/2').json()['records'] if r['kind']=='note'])==2


def test_8_9_reward_duplicate_policy_and_no_economy_effect(client):
    seed();campaign=client.post('/api/v22/campaigns',json={'name':'Premi 2026'}).json()['id']
    reward={'name':'Grazie','type':'Voucher25','date':date.today().isoformat(),'status':'assigned','campaign_id':campaign}
    before=client.get('/api/dashboard').json()['attributed_value'];confirm(client,batch(client,'reward',[1],reward))
    duplicate=batch(client,'reward',[1],reward);assert duplicate['changed']==0 and len(duplicate['duplicates'])==1
    confirm(client,batch(client,'reward',[1],{**reward,'type':'Tshirt'}))
    other=client.post('/api/v22/campaigns',json={'name':'Premi 2027'}).json()['id'];confirm(client,batch(client,'reward',[1],{**reward,'campaign_id':other}))
    assert client.post('/api/v22/bulk/preview',json={'action':'reward','ids':[1],'data':{**reward,'allow_duplicate':True}}).status_code==422
    confirm(client,batch(client,'reward',[1],{**reward,'allow_duplicate':True,'exception_reason':'Secondo contributo straordinario'}))
    assert client.get('/api/dashboard').json()['attributed_value']==before


def test_10_11_12_return_maturity_same_day_and_opportunities(client):
    with module.db(True) as c:
        c.execute("INSERT INTO people(name) VALUES('Persona Uno')")
        for name,day in [('Prima','2025-01-01'),('Stessa data','2025-01-01'),('Dopo','2026-01-01')]:
            eid=c.execute('INSERT INTO events(name,date,participant_value_cents) VALUES(?,?,0)',(name,day)).lastrowid;c.execute("INSERT INTO attendance(event_id,person_id,status) VALUES(?,1,'confirmed')",(eid,))
    from backend.performance import event_performance
    with module.db() as c:
        a=event_performance(c,1,'2025-02-01');assert a['new']==1 and a['windows'][0]['returned']==0 and a['windows'][0]['rate'] is None
        assert event_performance(c,2,'2025-02-01')['new']==1
        assert event_performance(c,3,'2026-01-02')['recurring']==1
        assert 'non ancora completo' in event_performance(c,3,'2026-01-02')['windows'][2]['reason']
        assert 'Nessuna occasione' in event_performance(c,3,'2026-12-01')['windows'][2]['reason']


def test_13_14_15_16_18_reports_export_and_private_notes(client):
    seed(101,2);client.post('/api/v22/people/1/notes',json={'text':'SEGRETO NON ESPORTARE'})
    perf=client.get('/api/v22/performance/1').json();assert perf['attributed_value']==0
    x=client.get('/api/v22/events/1/report?format=xlsx');assert x.status_code==200
    book=load_workbook(io.BytesIO(x.content));assert book['Riepilogo']['B7'].value==perf['presences']
    pdf=client.get('/api/v22/events/1/report?format=pdf');assert pdf.status_code==200,pdf.text;assert pdf.content.startswith(b'%PDF-') and len(pdf.content)>10000
    exp=client.post('/api/v22/export',json={'ids':list(range(1,102))});assert exp.status_code==200
    book=load_workbook(io.BytesIO(exp.content));assert book.active.max_row==102
    assert 'SEGRETO NON ESPORTARE' not in str(list(book.active.values))
    assert client.post('/api/v22/export',json={'columns':['id','notes']}).status_code==422
    assert client.post('/api/v22/export',json={'columns':['id','notes'],'include_notes':True}).status_code==200


def test_20_ten_thousand_people_and_full_export(client):
    seed(10000,1)
    assert client.get('/api/v2/people?page=200').json()['rows'][-1]['id']>0
    cards=client.get('/api/v22/segments').json();assert len(cards)>=6
    ex=client.post('/api/v22/export/preview',json={'filters':{}}).json();assert ex['count']==10000 and ex['with_email']==10000
    blob=client.post('/api/v22/export',json={'format':'csv'}).content;assert len(blob.decode('utf-8-sig').splitlines())==10001


def test_post_merge_reward_warning_note_history_and_safe_later_undo(client):
    with module.db(True) as c:c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[('Mario Rossi','m@example.test'),('Mario Rosssi','m@example.test')])
    campaign=client.post('/api/v22/campaigns',json={'name':'Riconoscimenti'}).json()['id']
    data={'name':'Premio','type':'Tshirt','date':date.today().isoformat(),'status':'proposed','campaign_id':campaign}
    for pid in (1,2):confirm(client,batch(client,'reward',[pid],data))
    client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'})
    profile=client.get('/api/v22/people/1').json();rewards=[r for r in profile['records'] if r['kind']=='reward'];assert all(r['potential_duplicate'] for r in rewards)
    r=rewards[0]
    assert client.patch('/api/v22/records/'+str(r['id']),json={'revision':r['revision'],'status':'assigned'}).status_code==409
    assert client.patch('/api/v22/records/'+str(r['id']),json={'revision':r['revision'],'status':'assigned','allow_duplicate':True,'reason':'Secondo contributo distinto confermato'}).status_code==200
    tag=client.post('/api/v22/tags',json={'name':'Partner'}).json()['id']
    confirm(client,batch(client,'tag_add',[1],{'tag_ids':[tag]}))
    removed=batch(client,'tag_remove',[1],{'tag_ids':[tag]});confirm(client,removed)
    confirm(client,batch(client,'tag_add',[1],{'tag_ids':[tag]}))
    assert client.post('/api/v22/bulk/'+removed['token']+'/undo').status_code==409
    nid=client.post('/api/v22/people/1/notes',json={'text':'Testo iniziale','operator':'Admin sintetico'}).json()['id']
    with module.db(True) as c:
        from backend.crm import change
        for i in range(55):change(c,dict(c.execute('SELECT * FROM crm_records WHERE id=?',(nid,)).fetchone()),payload=json.dumps({'text':f'Versione {i}'}))
    note=next(r for r in client.get('/api/v22/people/1').json()['records'] if r['id']==nid)
    assert note['author']=='Admin sintetico'
    assert client.patch('/api/v22/records/'+str(nid),json={'delete':True,'revision':note['revision']}).status_code==422
    assert client.patch('/api/v22/records/'+str(nid),json={'delete':True,'confirm':True,'revision':note['revision']}).status_code==200
    history=client.get('/api/v22/people/1?history_page=2').json();assert history['history'] and history['history_total']>50
    with module.db() as c:
        assert c.execute('SELECT active FROM crm_records WHERE id=?',(nid,)).fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM crm_record_origins WHERE record_id=?',(nid,)).fetchone()[0]==2
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_thresholds_archive_exclusion_custom_segment_and_formula_safe(client):
    seed();confirm(client,batch(client,'vip_add',[1]))
    cfg=client.get('/api/v22/settings').json();cfg['super_visits']=6
    assert client.put('/api/v22/settings',json=cfg).status_code==200
    f={'community_segment':'super'}
    assert client.get('/api/v2/people',params={'filters':json.dumps(f)}).json()['total']==0
    cfg['super_visits']=5;client.put('/api/v22/settings',json=cfg)
    client.post('/api/v2/events/1/archive',json={'archived':True})
    assert client.get('/api/v2/people',params={'filters':json.dumps(f)}).json()['total']==1
    client.post('/api/v2/events/1/analytics-impact',json={'include':False,'confirm':True})
    assert client.get('/api/v2/people',params={'filters':json.dumps(f)}).json()['total']==0
    assert client.get('/api/people/1').json()['vip']
    sid=client.post('/api/v22/segments',json={'name':'VIP ricercati','filters':{'vip':True,'search_text':'Persona0'}}).json()['id']
    custom=next(s for s in client.get('/api/v22/segments').json() if s['key']=='custom_'+str(sid));assert custom['count']==1
    with module.db(True) as c:c.execute("UPDATE people SET name='=FORMULA(1)' WHERE id=2")
    blob=client.post('/api/v22/export',json={'columns':['id','name','email'],'format':'xlsx'}).content
    book=load_workbook(io.BytesIO(blob));assert all(cell.data_type!='f' for row in book.active for cell in row)
    assert any(str(row[1]).startswith("'=FORMULA") for row in list(book.active.values)[1:])
    cfg['super_visits']=0;assert client.put('/api/v22/settings',json=cfg).status_code==422


def test_schema5_backup_failure_leaves_v21_untouched(tmp_path,monkeypatch):
    from backend import migrations
    path=tmp_path/'v21.db';migrate(path,4)
    def fail(*args):raise RuntimeError('synthetic backup failure')
    monkeypatch.setattr(migrations,'backup_database',fail)
    with pytest.raises(RuntimeError):migrate(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==4
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='crm_records'").fetchone()


def test_crm_backup_restore_and_missing_financial_values(client):
    seed(1,1);confirm(client,batch(client,'vip_add',[1]));client.post('/api/v22/people/1/notes',json={'text':'Da conservare nel backup'})
    backup=client.post('/api/backup').json()['file'];blob=client.get('/api/v2/backups/'+backup).content
    client.post('/api/v22/people/1/notes',json={'text':'Aggiunta successiva'})
    preview=client.post('/api/v2/restore/preview',files={'file':('restore.db',blob)}).json()
    assert preview['current_counts']['crm_notes']==2 and preview['counts']['crm_notes']==1
    assert client.post('/api/v2/restore/'+preview['token']+'/confirm').status_code==200
    profile=client.get('/api/v22/people/1').json();assert profile['vip'] and len([r for r in profile['records'] if r['kind']=='note'])==1
    perf=client.get('/api/v22/performance/1').json();assert perf['cost'] is None and perf['reported_spend'] is None
    client.put('/api/events/1',json={'name':'Zero documentato','date':date.today().isoformat(),'cost':0,'participant_value_cents':0})
    assert client.get('/api/v22/performance/1').json()['cost']==0
    with module.db() as c:assert c.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_event_value_update_preserves_other_metadata_and_audit(client):
    e=client.post('/api/events',json={'name':'Conserva dati','date':'2026-01-01','category':'Community','location':'Luogo originale','cost':25000,'participant_value_cents':2000}).json()['id']
    client.post(f'/api/v2/events/{e}/archive',json={'archived':True})
    assert client.put(f'/api/events/{e}',json={'name':'Conserva dati','date':'2026-01-01','participant_value_cents':4000}).status_code==200
    row=next(r for r in client.get('/api/events?include_archived=true').json() if r['id']==e)
    assert row['cost']==25000 and row['cost_defined']==1 and row['category']=='Community' and row['location']=='Luogo originale'
    assert row['archived']==1 and row['participant_value_cents']==4000
    with module.db() as c:assert c.execute("SELECT COUNT(*) FROM crm_audit WHERE action='event_metadata'").fetchone()[0]==1


def test_presence_preview_invalidates_when_manual_community_filter_changes(client):
    seed(2,1)
    confirm(client,batch(client,'vip_add',[1]))
    draft=client.post('/api/v2/bulk/preview',json={'event_id':1,'status':'absent','filters':{'vip':True}})
    assert draft.status_code==200,draft.text
    confirm(client,batch(client,'vip_remove',[1]))
    result=client.post('/api/v2/bulk/'+draft.json()['token']+'/confirm')
    assert result.status_code==409,result.text
    assert client.get('/api/v22/performance/1').json()['presences']==1
