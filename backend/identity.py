"""Identity groups are a reversible graph. Original people and rows never move."""
import re
import unicodedata
from difflib import SequenceMatcher
from fastapi import HTTPException


def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower())


def full_name(s):
    return len([word for word in re.split(r'\s+', s.strip()) if len(norm(word)) > 1]) >= 2


def personal(email):
    local, sep, domain = email.lower().partition('@')
    generic = {'info', 'admin', 'office', 'booking', 'segreteria', 'contact', 'eventi', 'event', 'team', 'sales', 'staff', 'famiglia', 'family', 'support', 'noreply', 'no-reply', 'hello', 'assistenza', 'prenotazioni'}
    return bool(sep and '.' in domain and len(local) >= 3 and local not in generic)


def compatible(a, b):
    if a['email'] and b['email'] and a['email'].lower() != b['email'].lower():
        return False
    if a['phone'] and b['phone'] and norm(a['phone']) != norm(b['phone']):
        return False
    return SequenceMatcher(None, norm(a['name']), norm(b['name'])).ratio() >= .84


def groups(c):
    ps = {p['id']: dict(p) for p in c.execute('SELECT * FROM people ORDER BY id')}
    parent = {pid: pid for pid in ps}
    def root(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for link in c.execute('SELECT a,b FROM identity_links WHERE active=1 ORDER BY id'):
        a, b = root(link['a']), root(link['b'])
        parent[max(a, b)] = min(a, b)
    membership = {pid: root(pid) for pid in ps}
    members = {}
    for pid, group in membership.items():
        members.setdefault(group, []).append(pid)
    return ps, membership, members


def conflicts(c, left, right):
    l, r = set(left), set(right)
    return [(a,b) for a,b in c.execute('SELECT a,b FROM separate') if (a in l and b in r) or (b in l and a in r)]


def merge(c, a, b, reason):
    ps, membership, members = groups(c)
    if a not in ps or b not in ps:
        raise HTTPException(404, 'Persona non trovata')
    ga, gb = membership[a], membership[b]
    if ga == gb:
        return None
    if conflicts(c, members[ga], members[gb]):
        raise HTTPException(409, 'Unione bloccata: almeno due identità dei gruppi sono state mantenute separate')
    link = c.execute('INSERT INTO identity_links(a,b,reason) VALUES(?,?,?)', (a,b,reason)).lastrowid
    c.execute('INSERT INTO decisions(action,a,b,link_id,reason) VALUES(?,?,?,?,?)', ('merge',a,b,link,reason))
    return link


def keep_separate(c, a, b, reason='Decisione amministratore'):
    a, b = sorted((a,b))
    c.execute('INSERT OR IGNORE INTO separate VALUES(?,?)', (a,b))
    c.execute('INSERT INTO decisions(action,a,b,reason) VALUES(?,?,?,?)', ('separate',a,b,reason))


def split_member(c, pid):
    ps, membership, members = groups(c)
    if pid not in ps:
        raise HTTPException(404, 'Persona non trovata')
    others = [i for i in members[membership[pid]] if i != pid]
    c.execute('UPDATE identity_links SET active=0 WHERE a=? OR b=?', (pid,pid))
    for other in others:
        keep_separate(c,pid,other,'Separazione successiva: blocco permanente')
    c.execute('INSERT INTO decisions(action,a,reason) VALUES(?,?,?)', ('split',pid,'Scollegata identità originale dal gruppo'))


def identify(c, name, email, phone):
    ps, membership, members = groups(c)
    person = {'name':name,'email':email,'phone':phone}
    exact = [p for p in ps.values() if (norm(p['name']),p['email'].lower(),norm(p['phone'])) == (norm(name),email,norm(phone))]
    if len(exact) == 1 and (full_name(name) or personal(email)):
        return exact[0]['id'], 'existing'
    legacy = c.execute('SELECT person_id FROM aliases WHERE name=? AND lower(email)=? AND phone=?',(name,email,phone)).fetchall()
    if len(legacy)==1 and legacy[0]['person_id'] in ps:
        return legacy[0]['person_id'], 'existing'
    pid = c.execute('INSERT INTO people(name,email,phone) VALUES(?,?,?)', (name,email,phone)).lastrowid
    # Homonyms with different emails are explicitly and permanently separate.
    for p in ps.values():
        if norm(p['name']) == norm(name) and email and p['email'] and email != p['email'].lower():
            keep_separate(c,pid,p['id'],'Omonimi con email differenti')
    email_candidates = [p for p in ps.values() if personal(email) and email == p['email'].lower() and compatible(person,p)]
    name_candidates = [p for p in ps.values() if full_name(name) and full_name(p['name']) and norm(name) == norm(p['name']) and compatible(person,p)]
    # Even if email evidence is stronger, multiple plausible groups require review.
    candidates = {membership[p['id']] for p in email_candidates + name_candidates}
    if len(candidates) == 1:
        gid = next(iter(candidates))
        # Check every original identity, not just the representative.
        if all(compatible(person,ps[i]) for i in members[gid]) and not conflicts(c,[pid],members[gid]):
            reason = 'Automatica: email personale compatibile' if email_candidates else 'Presunta: nome completo univoco'
            merge(c,pid,gid,reason)
            return pid, 'automatic' if email_candidates else 'presumed'
    similar = any(similarity(person,p)[0] >= .7 for p in ps.values())
    return pid, 'ambiguous' if similar else ('new' if full_name(name) else 'incomplete')


def similarity(a,b):
    if a['email'] and a['email'].lower()==b['email'].lower():
        return 1., 'Stessa email: verificare compatibilità'
    if norm(a['phone']) and norm(a['phone'])==norm(b['phone']):
        return 1., 'Stesso telefono'
    return SequenceMatcher(None,norm(a['name']),norm(b['name'])).ratio(), 'Nome simile o parziale'


def candidates(c):
    ps, membership, members = groups(c)
    result = {}
    blocked={tuple(sorted((membership[a],membership[b]))) for a,b in c.execute('SELECT a,b FROM separate')}
    identities=list(ps.values())
    for index,a in enumerate(identities):
        for b in identities[index+1:]:
            ga,gb = sorted((membership[a['id']],membership[b['id']]))
            if ga==gb or (ga,gb) in blocked:
                continue
            score, reason = similarity(a,b)
            if score>=.7:
                key=(ga,gb)
                if key not in result or result[key]['score'] < round(score*100):
                    result[key]={'a':ps[ga],'b':ps[gb],'score':round(score*100),'reason':reason,'members_a':len(members[ga]),'members_b':len(members[gb])}
    return sorted(result.values(),key=lambda r:-r['score'])[:200]
