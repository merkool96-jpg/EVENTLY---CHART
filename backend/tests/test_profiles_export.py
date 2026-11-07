import csv
import io
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend import app as module
from backend.migrations import migrate


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'profiles.db'))
    module.init()
    return TestClient(module.app)


def seed():
    with module.db(True) as c:
        a=c.execute("INSERT INTO people(name,email) VALUES('Sofia','sofia@example.test')").lastrowid
        b=c.execute("INSERT INTO people(name,email) VALUES('Sofia Di Gio','sofia@example.test')").lastrowid
        e=c.execute("INSERT INTO events(name,date,cost,participant_value_cents) VALUES('Bottini Milano','2026-11-07',15000,2000)").lastrowid
        for p in (a,b):c.execute("INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,99900,'confirmed')",(e,p))
    return a,b,e


def details(name='Sofia Di Gio',email='sofia@example.test'):
    return {'first_name':name.split()[0],'last_name':' '.join(name.split()[1:]),'display_name':name,'email':email,'phone':''}


def test_merge_preview_name_choice_history_and_import_persistence(client):
    a,b,e=seed()
    preview=client.post('/api/matches/preview',json={'a':a,'b':b})
    assert preview.status_code==200 and preview.json()['recommended']['display_name']=='Sofia Di Gio'
    assert len(client.get('/api/people').json())==2
    r=client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge','profile':details()})
    assert r.status_code==200
    person=client.get('/api/people').json()[0]
    assert person['name']=='Sofia Di Gio' and person['last_name']=='Di Gio'
    assert set(person['aliases'])=={'Sofia','Sofia Di Gio'}
    assert person['visits']==1 and person['value']==2000
    new=client.post('/api/events',json={'name':'Secondo','date':'2026-11-08'}).json()['id']
    client.post(f'/api/events/{new}/import',files={'file':('x.csv',b'Nome,Email\nSofia,sofia@example.test\n')})
    person=client.get('/api/people').json()[0]
    assert person['name']=='Sofia Di Gio'
    assert client.get('/api/people?q=Sofia').json()[0]['id']==a
    assert client.get(f'/api/people/{a}/history').json()[0]['reason']=='Nominativo confermato durante unione'
    client.post('/api/identity/links/'+str(r.json()['link_id'])+'/undo')
    assert {p['name'] for p in client.get('/api/people').json()}=={'Sofia','Sofia Di Gio'}


def test_recommendation_removes_repeat_not_just_longest(client):
    from backend.profiles import recommend
    assert recommend([{'name':'Iside Oliveti Oliveti'},{'name':'Iside Oliveti'}])['display_name']=='Iside Oliveti'
    assert recommend([{'name':'Sofia'},{'name':'Sofia Di Gio'}])['last_name']=='Di Gio'


def test_profile_edits_alias_search_contacts_and_sources(client):
    a,b,e=seed()
    client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge','profile':details()})
    r=client.patch(f'/api/people/{a}',json=details('Sofia Di Giò','sofia.new@example.test'))
    assert r.status_code==200
    assert client.get('/api/people?q=Di Gio').json()[0]['name']=='Sofia Di Giò'
    assert len(client.get(f'/api/people/{a}/history').json())==2
    with module.db() as c:
        assert c.execute('SELECT name FROM people WHERE id=?',(a,)).fetchone()[0]=='Sofia'
        assert c.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]==2
    with module.db(True) as c:c.execute("INSERT INTO people(name,email,phone) VALUES('Altra Persona','used@example.test','3331234567')")
    assert client.patch(f'/api/people/{a}',json=details(email='used@example.test')).status_code==409
    assert client.patch(f'/api/people/{a}',json={**details(),'phone':'3331234567'}).status_code==409
    assert client.patch(f'/api/people/{a}',json=details(email='not-an-email')).status_code==422
    assert client.patch(f'/api/people/{a}',json={**details(),'display_name':'   '}).status_code==422


def test_profile_choice_never_bypasses_separation_and_rolls_back_on_error(client):
    a,b,e=seed()
    client.post('/api/matches/decision',json={'a':a,'b':b,'action':'separate'})
    assert client.post('/api/matches/preview',json={'a':a,'b':b}).status_code==409
    assert client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge','profile':details()}).status_code==409
    with module.db() as c:
        assert c.execute('SELECT COUNT(*) FROM identity_links').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM profile_edits').fetchone()[0]==0


def test_failed_profile_validation_rolls_back_merge(client):
    a,b,e=seed()
    r=client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge','profile':details(email='bad')})
    assert r.status_code==422
    assert len(client.get('/api/people').json())==2
    with module.db() as c:assert c.execute('SELECT COUNT(*) FROM identity_links').fetchone()[0]==0


def test_export_xlsx_current_values_filters_formulas_and_read_only(client):
    a,b,e=seed()
    client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge','profile':details()})
    with module.db(True) as c:
        c.execute("INSERT INTO people(name,email) VALUES('=HYPERLINK(1)','danger@example.test')")
        free=c.execute("INSERT INTO events(name,date,participant_value_cents) VALUES('Gratuito','2026-10-01',0)").lastrowid
        c.execute("INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,0,'confirmed')",(free,a))
        reg=c.execute("INSERT INTO events(name,date) VALUES('Registrato','2026-12-01')").lastrowid
        c.execute("INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,100,'registered')",(reg,a))
    with module.db() as c:before={t:[tuple(r) for r in c.execute(f'SELECT * FROM {t}')] for t in ['people','events','attendance','profile_edits','decisions']}
    r=client.get('/api/exports/participants?format=xlsx')
    assert r.status_code==200 and 'attachment' in r.headers['content-disposition']
    book=load_workbook(io.BytesIO(r.content))
    assert book.sheetnames==['Partecipanti','Partecipazioni','Eventi']
    rows=list(book['Partecipanti'].values);headers=rows[0];p=dict(zip(headers,rows[1]))
    assert p['Nominativo']=='Sofia Di Gio' and p['Eventi con presenza confermata']==2
    assert p['Registrazioni senza presenza']==1 and p['Eventi gratuiti']==1 and p['Eventi con valore positivo']==1
    assert p['Valore attribuito totale EUR']==20
    assert p['Prima presenza'].year==2026
    assert book['Partecipanti'].cell(2,12).number_format=='#,##0.00 "€"'
    assert all(cell.data_type!='f' for sheet in book for row in sheet for cell in row)
    filtered=load_workbook(io.BytesIO(client.get('/api/exports/participants?format=xlsx&q=Di%20Gio').content))
    assert filtered['Partecipanti'].max_row==2 and filtered['Partecipazioni'].max_row==4
    assert client.get('/api/exports/count?q=Di%20Gio').json()['count']==1
    with module.db() as c:
        assert before=={t:[tuple(r) for r in c.execute(f'SELECT * FROM {t}')] for t in before}


def test_export_csv_utf8_formula_safe_and_not_limited_to_visible_rows(client):
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[(f'Persona {i}','') for i in range(10005)])
        c.execute("INSERT INTO people(name,email) VALUES('+Èlia Rossi','')")
    r=client.get('/api/exports/participants?format=csv')
    rows=list(csv.reader(io.StringIO(r.content.decode('utf-8-sig')),delimiter=';'))
    assert len(rows)==10007
    assert any("'+Èlia Rossi" in row for row in rows)
    assert client.get('/api/exports/count').json()['count']==10006
    assert len(list(csv.reader(io.StringIO(client.get('/api/exports/participants?format=csv&q=inesistente').text),delimiter=';')))==1


def test_schema3_backup_and_original_data_preserved(tmp_path):
    path=tmp_path/'v2.db';migrate(path,target_version=2)
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO people(name,email) VALUES('Originale','originale@test.it')")
    migrate(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==5
        assert c.execute('SELECT name FROM people').fetchone()[0]=='Originale'
    backup=list((tmp_path/'backups').glob('*.db'))
    assert len(backup)==1
    with sqlite3.connect(backup[0]) as c:assert c.execute('PRAGMA user_version').fetchone()[0]==2


def test_selected_name_cannot_hide_incompatible_originals(client):
    with module.db(True) as c:
        c.execute("INSERT INTO people(name,email) VALUES('Mario Rossi','mario@example.test')")
        c.execute("INSERT INTO people(name,email) VALUES('Luca Rossi','luca@example.test')")
    assert client.post('/api/matches/preview',json={'a':1,'b':2}).status_code==409
    assert client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge','profile':details('Mario Rossi','mario@example.test')}).status_code==409
    assert len(client.get('/api/people').json())==2


def test_xlsx_over_fifty_and_scoped_event_counts(client):
    with module.db(True) as c:
        e=c.execute("INSERT INTO events(name,date,participant_value_cents) VALUES('Tutti','2026-11-07',4000)").lastrowid
        for i in range(61):
            pid=c.execute('INSERT INTO people(name) VALUES(?)',(f'Persona {i}',)).lastrowid
            c.execute("INSERT INTO attendance(event_id,person_id,status) VALUES(?,?,'confirmed')",(e,pid))
    book=load_workbook(io.BytesIO(client.get('/api/exports/participants').content))
    assert book['Partecipanti'].max_row==62 and book['Partecipazioni'].max_row==62
    filtered=load_workbook(io.BytesIO(client.get('/api/exports/participants?q=Persona%2060').content))
    assert filtered['Partecipanti'].max_row==2
    assert filtered['Eventi'].cell(2,4).value==1
    assert filtered['Partecipanti'].cell(2,12).value==40


def test_current_corrected_name_email_recognized_on_new_import(client):
    a,b,e=seed()
    client.post('/api/matches/decision',json={'a':a,'b':b,'action':'merge','profile':details()})
    client.patch(f'/api/people/{a}',json=details('Sofia Di Giò','corrected@example.test'))
    new=client.post('/api/events',json={'name':'Nuovo','date':'2026-11-09'}).json()['id']
    r=client.post(f'/api/events/{new}/import',files={'file':('new.csv','Nome completo,Email\nSofia Di Giò,corrected@example.test\n'.encode())})
    assert r.status_code==200 and len(client.get('/api/people').json())==1
    assert client.get('/api/people').json()[0]['name']=='Sofia Di Giò'
