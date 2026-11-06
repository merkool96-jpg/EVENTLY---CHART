"""Specific evidence, never full-string percentages, controls the review queue."""
import pytest
from fastapi.testclient import TestClient
from backend import app as module
from backend.identity import evidence, surname_typo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module,'DB',str(tmp_path/'identities.db'))
    module.init()
    return TestClient(module.app)


def record(name,email='',phone=''):
    return {'name':name,'email':email,'phone':phone}


def add(c,*records):
    with module.db(True) as db:
        return [db.execute('INSERT INTO people(name,email,phone) VALUES(?,?,?)',(p['name'],p['email'],p['phone'])).lastrowid for p in records]


def upload(c,rows):
    events=c.get('/api/events').json()
    eid=events[0]['id'] if events else c.post('/api/events',json={'name':'Evidence test','date':'2026-11-06','participant_value_cents':2000}).json()['id']
    text='Nome completo,Email,Telefono\n'+'\n'.join(','.join((p['name'],p['email'],p['phone'])) for p in rows)+'\n'
    return c.post(f'/api/events/{eid}/import',files={'file':('identities.csv',text.encode())},data={'status':'confirmed'})


@pytest.mark.parametrize('left,right',[
    ('Marco Giacalone','Rocco Giacalone'),
    ('Arianna Aricò','Marianna Marino'),
    ('Mario Rossi','Luca Rossi'),
    ('Arianna Rossi','Marianna Rossi'),
    ('Anna Marino','Marianna Marino'),
    ('Marianna Marino','Martina Marino'),
])
def test_different_given_names_without_evidence_never_flagged(client,left,right):
    assert evidence(record(left),record(right)) is None
    r=upload(client,[record(left),record(right)])
    assert r.status_code==200 and r.json()['automatic']==0
    assert len(client.get('/api/people').json())==2
    assert client.get('/api/matches').json()==[]
    with module.db() as c:
        assert c.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]==2
        assert c.execute('SELECT COUNT(*) FROM import_rows').fetchone()[0]==2


def test_exact_name_without_email_presumed_only_when_unique(client):
    upload(client,[record('Mario Rossi','mario.rossi@gmail.com')])
    r=upload(client,[record('Mario Rossi')])
    assert r.json()['presumed']==1
    p=client.get('/api/people').json()
    assert len(p)==1 and len(p[0]['members'])==2 and p[0]['visits']==1
    assert p[0]['value']==2000


def test_exact_names_no_contacts_reuse_unique_identity(client):
    upload(client,[record('Mario Rossi')])
    r=upload(client,[record('Mario Rossi')])
    assert r.json()['skipped']==1
    assert len(client.get('/api/people').json())==1


def test_only_exact_given_name_allows_surname_typo_review(client):
    add(client,record('Mario Rossi'),record('Mario Rosssi'))
    matches=client.get('/api/matches').json()
    assert len(matches)==1 and matches[0]['evidence']=='surname_typo'
    assert 'battitura nel cognome' in matches[0]['reason']
    assert 'score' not in matches[0]
    assert surname_typo('rossi','ros') is False


def test_personal_email_and_surname_typo_can_auto_merge(client):
    r=upload(client,[record('Mario Rossi','mario.rossi@gmail.com'),record('Mario Rosssi','mario.rossi@gmail.com')])
    assert r.json()['automatic']==1
    assert len(client.get('/api/people').json())==1


def test_partial_name_email_is_only_a_unique_review_clue(client):
    r=upload(client,[record('Mario Rossi'),record('Mario','mario.rossi@gmail.com')])
    assert r.json()['automatic']==0 and r.json()['presumed']==0
    assert len(client.get('/api/people').json())==2
    matches=client.get('/api/matches').json()
    assert len(matches)==1 and matches[0]['evidence']=='partial_email'


def test_partial_email_cannot_bridge_multiple_groups(client):
    add(client,record('Mario Rossi'),record('Mario Rossi'),record('Mario','mario.rossi@gmail.com'))
    matches=client.get('/api/matches').json()
    assert all(m['evidence']!='partial_email' for m in matches)


def test_partial_name_without_email_content_evidence_is_not_flagged(client):
    add(client,record('Mario Rossi'),record('Mario','mario.other@gmail.com'))
    assert client.get('/api/matches').json()==[]


@pytest.mark.parametrize('email',['mario.rossi@gmail.com','info@example.test'])
def test_shared_email_with_incompatible_names_never_auto_merges(client,email):
    r=upload(client,[record('Mario Rossi',email),record('Luca Rossi',email),record('Mario Rosssi',email)])
    assert r.json()['automatic']==0 and r.json()['presumed']==0
    assert len(client.get('/api/people').json())==3
    matches=client.get('/api/matches').json()
    assert any(m['evidence']=='shared_email' and 'condiviso' in m['reason'] for m in matches)


def test_different_personal_emails_default_distinct_manual_override(client):
    upload(client,[record('Mario Rossi','mario.one@gmail.com'),record('Mario Rossi','mario.two@gmail.com')])
    assert len(client.get('/api/people').json())==2
    assert client.get('/api/matches').json()==[]
    assert client.post('/api/matches/decision',json={'a':1,'b':2,'action':'merge'}).status_code==200


def test_manual_separation_and_group_exclusions_survive(client):
    ids=add(client,record('Mario Rossi'),record('Mario Rosssi'),record('Mario Rossii'))
    client.post('/api/matches/decision',json={'a':ids[0],'b':ids[2],'action':'separate'})
    assert client.post('/api/matches/decision',json={'a':ids[0],'b':ids[1],'action':'merge'}).status_code==200
    assert client.post('/api/matches/decision',json={'a':ids[1],'b':ids[2],'action':'merge'}).status_code==409
    assert not client.get('/api/matches').json()
    module.init()
    assert client.post('/api/matches/decision',json={'a':ids[0],'b':ids[2],'action':'merge'}).status_code==409


def test_group_guard_prevents_chain_via_one_shared_email(client):
    ids=add(client,record('Mario Rossi','one@example.test'),record('Mario Rossi','two@example.test'),record('Luca Rossi','one@example.test'))
    assert client.post('/api/matches/decision',json={'a':ids[0],'b':ids[1],'action':'merge'}).status_code==200
    assert client.post('/api/matches/decision',json={'a':ids[0],'b':ids[2],'action':'merge'}).status_code==409
    assert len(client.get('/api/people').json())==2


def test_manual_confirmed_alias_can_be_reused_without_undoing_group(client):
    ids=add(client,record('Mario Rossi','same@example.test'),record('Luca Rossi','same@example.test'))
    assert client.post('/api/matches/decision',json={'a':ids[0],'b':ids[1],'action':'merge'}).status_code==200
    r=upload(client,[record('Luca Rossi')])
    assert r.json()['presumed']==1
    assert len(client.get('/api/people').json())==1
    assert len(client.get('/api/people').json()[0]['members'])==3


def test_accents_case_and_punctuation_keep_separate_name_boundaries(client):
    r=upload(client,[record('MARIO Aricò','mario@example.test'),record('mario arico','mario@example.test')])
    assert r.status_code==200
    assert len(client.get('/api/people').json())==1
    assert evidence(record('Anna Marino'),record('Annamarino')) is None


def test_reason_describes_actual_member_not_group_representative(client):
    ids=add(client,record('Mario Rossi','shared@example.test'),record('Luca Rossi','shared@example.test'),record('Luca Rossii'))
    client.post('/api/matches/decision',json={'a':ids[0],'b':ids[1],'action':'merge'})
    matches=client.get('/api/matches').json()
    assert len(matches)==1
    assert {matches[0]['a']['name'],matches[0]['b']['name']}=={'Luca Rossi','Luca Rossii'}


def test_legacy_automatic_email_exclusion_can_be_overridden_manually(client):
    ids=add(client,record('Mario Rossi','one@example.test'),record('Mario Rossi','two@example.test'))
    with module.db(True) as c:
        c.execute('INSERT INTO separate VALUES(?,?)',ids)
        c.execute('INSERT INTO decisions(action,a,b,reason) VALUES(?,?,?,?)',('separate',*ids,'Omonimi con email differenti'))
    assert client.post('/api/matches/decision',json={'a':ids[0],'b':ids[1],'action':'merge'}).status_code==200
    with module.db() as c:
        assert c.execute("SELECT COUNT(*) FROM decisions WHERE action='separate'").fetchone()[0]==1
        assert c.execute("SELECT COUNT(*) FROM decisions WHERE action='override_automatic_exclusion'").fetchone()[0]==1


def test_manual_decision_always_wins_over_legacy_automatic_separation(client):
    ids=add(client,record('Mario Rossi','one@example.test'),record('Mario Rossi','two@example.test'))
    with module.db(True) as c:
        c.execute('INSERT INTO separate VALUES(?,?)',ids)
        c.execute('INSERT INTO decisions(action,a,b,reason) VALUES(?,?,?,?)',('separate',*ids,'Omonimi con email differenti'))
    client.post('/api/matches/decision',json={'a':ids[0],'b':ids[1],'action':'separate'})
    assert client.post('/api/matches/decision',json={'a':ids[0],'b':ids[1],'action':'merge'}).status_code==409
    with module.db() as c:
        assert c.execute('SELECT COUNT(*) FROM separate').fetchone()[0]==1


def test_blocked_matching_is_identical_to_exhaustive_matching(client,monkeypatch):
    import random
    from backend import identity
    rng=random.Random(42)
    names=['Mario Rossi','Mario Rosssi','Mario','Luca Rossi','Anna Marino','Marianna Marino','Arianna Aricò','Carlo Bianchi','Carlo','MARIO RÓSSI','Rocco Giacalone']
    emails=['','shared@example.test','mario.rossi@gmail.com','carlo.bianchi@gmail.com','info@example.test','other@example.test']
    phones=['','+39 333 123','39333123','320999']
    rows=[record(rng.choice(names),rng.choice(emails),rng.choice(phones)) for _ in range(80)]
    ids=add(client,*rows)
    with module.db(True) as c:
        c.execute('INSERT INTO identity_links(a,b,reason) VALUES(?,?,?)',(ids[0],ids[1],'Pre-existing group'))
        c.execute('INSERT INTO separate VALUES(?,?)',(ids[2],ids[3]))
    def exhaustive(people,focus=None):
        if focus is not None:
            a=next(p for p in people if p['id']==focus)
            yield from ((a,b) for b in people if b['id']!=focus)
        else:
            yield from ((a,b) for i,a in enumerate(people) for b in people[i+1:])
    with module.db() as c:
        for focus in [None,ids[10],ids[35],ids[-1]]:
            fast=identity.candidates(c,focus)
            with monkeypatch.context() as patch:
                patch.setattr(identity,'evidence_pairs',exhaustive)
                assert fast==identity.candidates(c,focus)
