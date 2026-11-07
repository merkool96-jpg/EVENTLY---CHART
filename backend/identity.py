"""Identity groups are a reversible graph. Original people and rows never move."""
import re
import unicodedata
from functools import lru_cache
from collections import defaultdict
from fastapi import HTTPException


def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower())


def full_name(s):
    return len([word for word in re.split(r'\s+', s.strip()) if len(norm(word)) > 1]) >= 2


@lru_cache(maxsize=20000)
def personal(email):
    local, sep, domain = email.lower().partition('@')
    generic = {'info', 'admin', 'office', 'booking', 'segreteria', 'contact', 'eventi', 'event', 'team', 'sales', 'staff', 'famiglia', 'family', 'support', 'noreply', 'no-reply', 'hello', 'assistenza', 'prenotazioni'}
    return bool(sep and '.' in domain and len(local) >= 3 and local not in generic)


@lru_cache(maxsize=20000)
def name_parts(name):
    """Without structured source fields, first token is given name, rest surname.

    Keep the boundary: a surname can never compensate a different given name.
    Compound-name boundaries that cannot be inferred remain conservative.
    """
    words = [norm(word) for word in str(name).split() if norm(word)]
    return (words[0], ''.join(words[1:])) if words else ('', '')


def parts(person):
    if person.get('name_structure') in ('structured','given_only','surname_only','email_only'):
        return norm(person.get('first_name','')),norm(person.get('last_name',''))
    return name_parts(person['name'])


def surname_typo(a, b):
    if a == b or min(len(a), len(b)) < 4 or abs(len(a)-len(b)) > 1:
        return False
    if len(a) == len(b):
        different = [i for i in range(len(a)) if a[i] != b[i]]
        return len(different) == 1 or (len(different) == 2 and different[1] == different[0]+1 and a[different[0]] == b[different[1]] and a[different[1]] == b[different[0]])
    short, long = (a,b) if len(a)<len(b) else (b,a)
    return any(long[:i]+long[i+1:] == short for i in range(len(long)))


def compatible_names(a,b):
    first_a,last_a = parts(a)
    first_b,last_b = parts(b)
    return bool(first_a and first_a == first_b and last_a and last_b and (last_a == last_b or surname_typo(last_a,last_b)))


def same_email(a,b):
    return bool(a['email'] and a['email'].casefold() == b['email'].casefold())


def same_phone(a,b):
    return bool(norm(a['phone']) and norm(a['phone']) == norm(b['phone']))


def contradictory_contacts(a,b):
    email_conflict = personal(a['email']) and personal(b['email']) and a['email'].casefold() != b['email'].casefold()
    phone_conflict = norm(a['phone']) and norm(b['phone']) and norm(a['phone']) != norm(b['phone'])
    return bool(email_conflict or phone_conflict)


def compatible(a,b):
    return compatible_names(a,b) and not contradictory_contacts(a,b)


def partial_email_clue(a,b):
    first_a,last_a = parts(a)
    first_b,last_b = parts(b)
    if not first_a or first_a != first_b or bool(last_a) == bool(last_b):
        return False
    partial, surname = (a,last_b) if not last_a else (b,last_a)
    if not personal(partial['email']):
        return False
    local = partial['email'].split('@',1)[0]
    tokens = [norm(t) for t in re.split(r'[^a-zA-ZÀ-ÿ]+',local) if norm(t)]
    return norm(local) in (first_a+surname,surname+first_a) or (first_a in tokens and surname in tokens)


def evidence(a,b):
    if same_email(a,b):
        if not compatible_names(a,b):
            return ('shared_email','Email coincidente, nominativo differente: possibile indirizzo condiviso',0)
        return ('email','Email coincidente e nome compatibile',1)
    if same_phone(a,b):
        return ('phone','Telefono coincidente; verificare il nominativo e i contatti',2)
    if contradictory_contacts(a,b):
        return None
    first_a,last_a = parts(a)
    first_b,last_b = parts(b)
    if first_a and first_a == first_b and last_a and last_b:
        if last_a == last_b:
            return ('exact_name','Nome e cognome identici, identificativi mancanti o da verificare',3)
        if surname_typo(last_a,last_b):
            return ('surname_typo','Possibile errore di battitura nel cognome; nome esatto',4)
    if partial_email_clue(a,b):
        return ('partial_email','Nome incompleto, email compatibile: indizio da verificare',5)
    return None


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
    excluded = conflicts(c, members[ga], members[gb])
    overridable = []
    for left,right in excluded:
        decisions = c.execute("SELECT reason FROM decisions WHERE action='separate' AND ((a=? AND b=?) OR (a=? AND b=?))",(left,right,right,left)).fetchall()
        automatic_only = bool(decisions) and all(row['reason']=='Omonimi con email differenti' for row in decisions)
        if reason!='Unione manuale verificata' or not automatic_only:
            raise HTTPException(409, 'Unione bloccata: almeno due identità dei gruppi sono state mantenute separate')
        overridable.append((left,right))
    verified_aliases = confirmed_name_aliases(c, set(members[ga])) | confirmed_name_aliases(c, set(members[gb]))
    for left in members[ga]:
        for right in members[gb]:
            x,y = ps[left],ps[right]
            if not compatible_names(x,y) and not same_email(x,y) and not same_phone(x,y) and frozenset((parts(x),parts(y))) not in verified_aliases:
                raise HTTPException(409, 'Unione bloccata: nomi incompatibili tra i membri dei gruppi senza identificativo forte coincidente')
    for left,right in overridable:
        c.execute('DELETE FROM separate WHERE a=? AND b=?',(left,right))
        c.execute('INSERT INTO decisions(action,a,b,reason) VALUES(?,?,?,?)',('override_automatic_exclusion',left,right,'Unione manuale: superata esclusione automatica legacy per email differenti'))
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


def confirmed_name_aliases(c, member_ids=None):
    aliases = set()
    for row in c.execute("SELECT p.name,q.name,l.a,l.b FROM identity_links l JOIN people p ON p.id=l.a JOIN people q ON q.id=l.b WHERE l.active=1 AND l.reason='Unione manuale verificata'"):
        if member_ids is not None and (row[2] not in member_ids or row[3] not in member_ids):
            continue
        aliases.add(frozenset((name_parts(row[0]),name_parts(row[1]))))
    return aliases


def identify(c, name, email, phone, first_name='', last_name='', structure='proposed'):
    ps,membership,members = groups(c)
    person = {'name':name,'email':email,'phone':phone,'first_name':first_name,'last_name':last_name,'name_structure':structure}
    from .profiles import canonical_profiles
    canonical=canonical_profiles(c,ps,membership,members)
    edited=[gid for gid,p in canonical.items() if p['profile_edited'] and (parts(p),p['email'].casefold(),norm(p['phone'])) == (parts(person),email.casefold(),norm(phone))]
    if len(edited)==1 and (full_name(name) or personal(email)):
        return edited[0],'existing'

    exact = [p for p in ps.values() if (parts(p),p['email'].casefold(),norm(p['phone'])) == (parts(person),email.casefold(),norm(phone))]
    # An exact original identity is reused, but name-only reuse still needs a
    # unique plausible group (homonyms with missing data must remain ambiguous).
    plausible = {membership[p['id']] for p in ps.values() if parts(p) == parts(person) and not contradictory_contacts(person,p)}
    if len(exact)==1 and (personal(email) or (full_name(name) and len(plausible)==1)):
        return exact[0]['id'],'existing'
    legacy = c.execute('SELECT person_id FROM aliases WHERE name=? AND lower(email)=? AND phone=?',(name,email,phone)).fetchall()
    if len(legacy)==1 and legacy[0]['person_id'] in ps:
        return legacy[0]['person_id'],'existing'
    pid = c.execute('INSERT INTO people(name,email,phone,first_name,last_name,name_structure) VALUES(?,?,?,?,?,?)',(name,email,phone,first_name,last_name,structure)).lastrowid
    shared = any(same_email(person,p) and not compatible_names(person,p) for p in ps.values())
    email_candidates = [p for p in ps.values() if personal(email) and same_email(person,p) and compatible(person,p) and not shared]
    name_candidates = [p for p in ps.values() if full_name(name) and parts(person)==parts(p) and compatible(person,p)]
    possible = {membership[p['id']] for p in email_candidates+name_candidates}
    if structure=='surname_only':possible=set()
    if len(possible)==1 and not shared:
        gid = next(iter(possible))
        aliases = confirmed_name_aliases(c, set(members[gid]))
        def group_safe(p):
            alias = frozenset((parts(person),parts(p))) in aliases
            return not contradictory_contacts(person,p) and (compatible_names(person,p) or alias)
        if all(group_safe(ps[i]) for i in members[gid]) and not conflicts(c,[pid],members[gid]):
            reason = 'Automatica: email personale compatibile' if email_candidates else 'Presunta: nome e cognome esatti, candidato univoco'
            merge(c,pid,gid,reason)
            return pid,'automatic' if email_candidates else 'presumed'
    # The queue and the import preview share exactly the same evidence rules.
    ambiguous = any(m['a']['id']==pid or m['b']['id']==pid for m in candidates(c, focus=pid))
    return pid,'ambiguous' if ambiguous else ('new' if full_name(name) else 'incomplete')


def evidence_pairs(identities, focus=None):
    """A pair can have evidence only if given name, email or phone is shared.

    Blocking is an exact superset of the existing evidence rules, not a weaker
    threshold or a heuristic that drops candidates. Original ID order is kept.
    """
    by_first,by_email,by_phone = defaultdict(set),defaultdict(set),defaultdict(set)
    people={p['id']:p for p in identities}
    keys={}
    for p in identities:
        first=parts(p)[0]
        email=p['email'].casefold()
        phone=norm(p['phone'])
        keys[p['id']]=(first,email,phone)
        for index,key in ((by_first,first),(by_email,email),(by_phone,phone)):
            if key:
                index[key].add(p['id'])
    selected=[people[focus]] if focus is not None else identities
    for a in selected:
        neighbors=set()
        for index,key in zip((by_first,by_email,by_phone),keys[a['id']]):
            if key:
                neighbors.update(index[key])
        for pid in sorted(neighbors):
            if (focus is not None and pid!=focus) or (focus is None and pid>a['id']):
                yield a,people[pid]


def candidates(c, focus=None, deferred=False):
    ps,membership,members = groups(c)
    blocked = {tuple(sorted((membership[a],membership[b]))) for a,b in c.execute('SELECT a,b FROM separate')}
    deferred_groups={tuple(sorted((membership[a],membership[b]))) for a,b in c.execute('SELECT a,b FROM deferred_pairs')}
    identities = list(ps.values())
    result = {}
    # First collect evidence from ORIGINAL identities, not fabricated root pairs.
    pairs = evidence_pairs(identities,focus)
    for a,b in pairs:
        ga,gb = sorted((membership[a['id']],membership[b['id']]))
        if ga==gb or (ga,gb) in blocked or (focus is None and (((ga,gb) in deferred_groups)!=deferred)):
            continue
        proof = evidence(a,b)
        if not proof:
            continue
        kind,reason,priority = proof
        key = (ga,gb)
        candidate = {'a':a,'b':b,'reason':reason,'evidence':kind,'priority':priority,'members_a':len(members[membership[a['id']]]),'members_b':len(members[membership[b['id']]])}
        if key not in result or priority < result[key]['priority']:
            result[key] = candidate
    valid = []
    for row in result.values():
        if row['evidence']=='partial_email':
            partial = row['a'] if not name_parts(row['a']['name'])[1] else row['b']
            plausible_groups = {membership[p['id']] for p in identities if membership[p['id']] != membership[partial['id']] and tuple(sorted((membership[p['id']],membership[partial['id']]))) not in blocked and (proof := evidence(partial,p)) and proof[0]=='partial_email'}
            if len(plausible_groups) != 1:
                continue
        valid.append(row)
    return sorted(valid,key=lambda r:(r['priority'],r['a']['id'],r['b']['id']))[:200]
