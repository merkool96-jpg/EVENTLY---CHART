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
