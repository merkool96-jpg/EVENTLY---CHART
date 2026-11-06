import io
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from backend import app as module

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'test.db'))
    module.init()
    return TestClient(module.app)

def event(c):
    r=c.post('/api/events',json={'name':'Test','date':'2026-11-06','cost':1000})
    assert r.status_code==201
    return r.json()['id']

def upload(c,e,data,name='people.csv'):
    return c.post(f'/api/events/{e}/import',files={'file':(name,data)},data={'status':'confirmed'})

def test_csv_auto_columns_money_idempotence_persistence(client):
    e=event(client)
    content='Nome;Cognome;Email;Importo\nAnna;Rossi;anna@example.test;1.234,56\n'.encode()
    r=upload(client,e,content)
    assert r.status_code==200 and r.json()['imported']==1
    assert upload(client,e,content).json()['skipped']==1
    assert client.get('/api/dashboard').json()['actual_spend']==123456
    module.init()
    assert client.get('/api/people').json()[0]['name']=='Anna Rossi'
    assert client.get('/api/people/1').json()['events'][0]['amount']==123456

def test_xlsx(client):
    e=event(client)
    w=Workbook();w.active.append(['Full name','Email','Amount']);w.active.append(['Eva Verdi','eva@example.test',12.5])
    b=io.BytesIO();w.save(b)
    assert upload(client,e,b.getvalue(),'people.xlsx').json()['imported']==1
    assert client.get('/api/events').json()[0]['actual_spend']==1250

def test_xls(client):
    import xlwt
    e=event(client)
    w=xlwt.Workbook();s=w.add_sheet('People')
    for i,row in enumerate([['Nome completo','Importo'],['Paolo Gialli',24.75]]):
        for j,v in enumerate(row):s.write(i,j,v)
    b=io.BytesIO();w.save(b)
    assert upload(client,e,b.getvalue(),'people.xls').json()['imported']==1
    assert client.get('/api/dashboard').json()['actual_spend']==2475

def test_separate_merge_aliases_and_totals(client):
    # V1.1 retains all original identities; costs and attributed value are separate.
    e=event(client)
    upload(client,e,b'Nome completo,Email,Importo\nGiulia Rossi,g@example.test,20\nGiulia Rosi,g@example.test,30\n')
    match=client.get('/api/matches').json()[0]
    a,b=match['a']['id'],match['b']['id']
    result=client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge'})
    assert result.status_code==200
    link=result.json()['link_id']
    p=client.get('/api/people').json()
    assert len(p)==1 and p[0]['actual_spend']==5000 and p[0]['visits']==1
    assert p[0]['value']==0 and p[0]['undefined_values']==1
    e2=event(client)
    upload(client,e2,b'Nome completo,Email,Importo\nGiulia Rosi,g@example.test,10\n')
    assert len(client.get('/api/people').json())==1
    assert client.get('/api/dashboard').json()['actual_spend']==6000
    assert client.post(f'/api/identity/links/{link}/undo').json()['separated']
    assert len(client.get('/api/people').json())==2
    assert client.post('/api/matches/decision',json={'a':a,'b':b,'action':'separate'}).status_code==200
    assert not client.get('/api/matches').json()
    assert client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge'}).status_code==409

def test_invalid_import_is_atomic(client):
    e=event(client)
    r=upload(client,e,b'Nome,Importo\nAnna,20\nEva,wrong\n')
    assert r.status_code==400
    assert client.get('/api/people').json()==[]
    assert upload(client,e,b'Other\ndata\n').status_code==400
    assert upload(client,e,b'broken','bad.xlsx').status_code==400
    assert upload(client,999,b'Nome\nAnna\n').status_code==404

def test_event_crud_validation(client):
    e=event(client)
    assert client.put(f'/api/events/{e}',json={'name':'Edited','date':'2026-12-01','cost':2345}).status_code==200
    assert client.get('/api/events').json()[0]['cost']==2345
    assert client.post('/api/events',json={'name':'X','date':'bad'}).status_code==422
    upload(client,e,b'Nome\nAnna\n')
    assert client.delete(f'/api/events/{e}').status_code==200
    assert not client.get('/api/people/1').json()['events']
    assert client.delete(f'/api/events/{e}').status_code==404

def test_demo(client):
    assert client.post('/api/demo').status_code==200
    assert client.post('/api/demo').status_code==409
    d=client.get('/api/dashboard').json()
    assert d['events']==4 and d['people']==13 and d['actual_spend']>d['cost']
    assert client.get('/api/matches').json()

def test_separation_survives_merge_and_alias_collision(client):
    e=event(client)
    upload(client,e,b'Nome completo,Email,Importo\nAnna Rossi,a@test.it,10\nAna Rossi,a@test.it,20\nAnnamaria Rossi,other@test.it,30\nAnna Rosi,a@test.it,40\n')
    ids={p['name']:p['id'] for p in client.get('/api/people').json()}
    a,b,c,d=[ids[n] for n in ['Anna Rossi','Ana Rossi','Annamaria Rossi','Anna Rosi']]
    assert client.post('/api/matches/decision',json={'a':b,'b':c,'action':'separate'}).status_code==200
    assert client.post('/api/matches/decision',json={'a':b,'b':d,'action':'merge'}).status_code==200
    assert client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge'}).status_code==200
    # The original b-c exclusion blocks a-c at group level; no row is moved.
    assert client.post('/api/matches/decision',json={'a':a,'b':c,'action':'merge'}).status_code==409
    with module.db() as conn:
        assert conn.execute('SELECT 1 FROM separate WHERE a=? AND b=?',tuple(sorted((b,c)))).fetchone()
        assert conn.execute('SELECT COUNT(*) FROM people').fetchone()[0]==4
    e2=event(client)
    upload(client,e2,b'Nome completo,Email,Importo\nAnna Rosi,a@test.it,5\n')
    assert len(client.get('/api/people').json())==2
    assert client.get('/api/dashboard').json()['actual_spend']==10500

def test_blank_name_and_bad_money(client):
    assert client.post('/api/events',json={'name':'   ','date':'2026-01-01'}).status_code==422
    e=event(client)
    for value in ['NaN','Infinity','-10']:
        assert upload(client,e,f'Nome,Importo\nAnna,{value}\n'.encode()).status_code==400
