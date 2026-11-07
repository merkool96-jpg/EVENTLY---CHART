"""V2.2.1 post-audit regressions; only isolated synthetic databases."""
import io,json,threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend import app as module,crm,post_report

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'audit.db'));module.init()
    return TestClient(module.app)


def conflicted(kind):
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[(f'Persona {i}',f'p{i}@example.test') for i in (1,2,3)])
        tid=c.execute("INSERT INTO crm_tags(name,normalized,color) VALUES('Partner','partner','#2f654b')").lastrowid if kind=='tag' else None
        data={'text':'Nota privata originale'} if kind=='note' else {'enabled':True} if kind=='vip' else {'name':'Premio','type':'Voucher','date':'2026-01-01','status':'proposed'} if kind=='reward' else {}
        rid=crm.insert(c,kind,[1,2],data,'Autore originale',tag_id=tid)
    return rid


def state(rid):
    with module.db() as c:
        return dict(c.execute('SELECT * FROM crm_records WHERE id=?',(rid,)).fetchone()),[tuple(r) for r in c.execute('SELECT * FROM crm_audit')],[tuple(r) for r in c.execute('SELECT * FROM crm_record_origins')]


@pytest.mark.parametrize('kind',['note','vip','tag','reward'])
def test_reassignment_rejects_outsiders_without_any_mutation(client,kind):
    rid=conflicted(kind);before=state(rid)
    r=client.post(f'/api/v22/records/{rid}/reassign',json={'person_id':3,'revision':1,'reason':'Tentativo estraneo'})
    assert r.status_code==422,r.text
    assert state(rid)==before
    # Even if an outsider is merged into a legitimate owner's current group,
    # it is not an ORIGINAL identity involved in this record's conflict.
    client.post('/api/matches/decision',json={'a':1,'b':3,'action':'merge'})
    before=state(rid)
    r=client.post(f'/api/v22/records/{rid}/reassign',json={'person_id':3,'revision':1,'reason':'Stesso gruppo attuale'})
    assert r.status_code==422,r.text
    assert state(rid)==before


@pytest.mark.parametrize('kind',['note','vip','tag','reward'])
def test_reassignment_revision_history_and_safe_undo(client,kind):
    rid=conflicted(kind);original=state(rid)[0];url=f'/api/v22/records/{rid}/reassign'
    assert client.post(url,json={'person_id':2,'revision':99,'reason':'Scelta corretta'}).status_code==409
    assert client.post(url,json={'person_id':2,'revision':1,'reason':'  '}).status_code==422
    r=client.post(url,json={'person_id':2,'revision':1,'reason':'Confermato dal referente'})
    assert r.status_code==200,r.text
    row,audit,origins=state(rid)
    assert row['scope']=='[2]' and row['revision']==2
    for key in ('id','payload','kind','author','created_at','tag_id','campaign_id','event_id'):assert row[key]==original[key]
    assert len(audit)==2 and origins==[(rid,2)]
    # A resolved record is never a general-purpose "move to another person" API.
    before=state(rid)
    assert client.post(url,json={'person_id':2,'revision':2,'reason':'Spostamento risolto'}).status_code==409
    assert state(rid)==before
    undo=url+'/undo'
    assert client.post(undo,json={'revision':1,'confirm':True}).status_code==409
    assert client.post(undo,json={'revision':2}).status_code==422
    assert client.post(undo,json={'revision':2,'confirm':True}).status_code==200
    row,audit,origins=state(rid)
    assert json.loads(row['scope'])==[1,2] and row['revision']==3 and len(audit)==3
    assert len(origins)==2 and len(client.get('/api/v22/unresolved').json())==1
    assert client.post(undo,json={'revision':3,'confirm':True}).status_code==409
    # Later editing makes an undo stale, preserving the newer information.
    client.post(url,json={'person_id':1,'revision':3,'reason':'Nuova scelta documentata'})
    with module.db(True) as c:crm.change(c,dict(c.execute('SELECT * FROM crm_records WHERE id=?',(rid,)).fetchone()),payload=row['payload'],reason='Modifica successiva')
    assert client.post(undo,json={'revision':4,'confirm':True}).status_code==409


@pytest.mark.parametrize('pid',[True,1.0,'1',None,{},-1])
def test_reassign_rejects_invalid_identifiers(client,pid):
    rid=conflicted('note');before=state(rid)
    assert client.post(f'/api/v22/records/{rid}/reassign',json={'person_id':pid,'revision':1,'reason':'Scelta valida'}).status_code==422
    assert state(rid)==before


def seed_report(count=1):
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[(f'PersonaSintetica{i}',f'p{i}@example.test') for i in range(count)])
        eid=c.execute('INSERT INTO events(name,date,participant_value_cents) VALUES(?,?,100)',('Evento passato sintetico',(date.today()-timedelta(days=400)).isoformat())).lastrowid
        c.executemany("INSERT INTO attendance(event_id,person_id,status) VALUES(?,?,'confirmed')",[(eid,i) for i in range(1,count+1)])
        crm.insert(c,'vip',[1],{'enabled':True});crm.insert(c,'note',[1],{'text':'RISERVATO NON ESPORTARE'})
    return eid


def test_past_report_labels_current_crm_and_personal_data(client):
    eid=seed_report()
    with module.db() as c:data=post_report.model(c,eid)
    assert data['vip_attendees']==1
    assert data['crm_asof']==data['generated_at']
    assert 'non ricostruisce' in data['crm_temporal_note']
    book=load_workbook(io.BytesIO(client.get(f'/api/v22/events/{eid}/report?format=xlsx').content))
    assert 'VIP alla generazione' in list(book['Partecipanti'].values)[0]
    text=str([list(s.values) for s in book])
    assert 'DATI PERSONALI' in text and data['crm_temporal_note'] in text
    assert 'p0@example.test' in text and 'RISERVATO NON ESPORTARE' not in text
    # Guard the PDF rendering boundary: its model is detached and PDF renders aggregates only.
    from unittest.mock import patch
    captured=[];original=post_report.pdf
    with patch('reportlab.platypus.Paragraph',side_effect=lambda text,*a,**kw:(captured.append(text),__import__('reportlab.platypus',fromlist=['']).paragraph.Paragraph(text,*a,**kw))[1]):
        blob=original(data)
    rendered=' '.join(captured)
    assert blob.startswith(b'%PDF-') and 'VIP alla generazione' in rendered
    assert data['crm_temporal_note'] in rendered
    assert 'p0@example.test' not in rendered and 'PersonaSintetica0' not in rendered and 'RISERVATO' not in rendered


@pytest.mark.parametrize('format',['pdf','xlsx'])
def test_large_report_releases_lock_before_render_and_keeps_snapshot(client,monkeypatch,format):
    eid=seed_report(10000)
    started=threading.Event();release=threading.Event();write_done=threading.Event();seen=[]
    renderer=getattr(post_report,format)
    def paused(data):
        # Every object must remain usable after closing the read connection.
        json.dumps(data,default=str);seen.append(data);started.set()
        assert release.wait(15),'Test barrier not released'
        return renderer(data)
    monkeypatch.setattr(post_report,format,paused)
    with ThreadPoolExecutor(max_workers=3) as pool:
        future=pool.submit(client.get,f'/api/v22/events/{eid}/report?format={format}')
        assert started.wait(60),'Snapshot did not finish'
        def write():
            with module.db(True) as c:c.execute("UPDATE attendance SET status='absent' WHERE person_id=1")
            write_done.set()
        writer=pool.submit(write)
        try:
            unlocked=write_done.wait(2)
            if unlocked:assert client.get('/api/health').status_code==200
        finally:release.set()
        response=future.result(timeout=60);writer.result(timeout=10)
    assert unlocked,'Document rendering still holds the global database lock'
    assert response.status_code==200,response.text[:200] if response.status_code!=200 else ''
    assert seen[0]['presences']==10000 and len(seen[0]['participants'])==10000
    assert client.get(f'/api/v22/performance/{eid}').json()['presences']==9999
    if format=='xlsx':
        book=load_workbook(io.BytesIO(response.content),read_only=True)
        assert book['Riepilogo']['B7'].value==10000 and book['Partecipanti'].max_row==10001
    else:assert response.content.startswith(b'%PDF-')
