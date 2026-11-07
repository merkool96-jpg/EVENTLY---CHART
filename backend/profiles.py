"""Editable canonical attributes layered over immutable imported identities."""
import json
import re
from fastapi import HTTPException
from .identity import groups, name_parts, norm, personal


def split_name(name):
    words=name.strip().split()
    return (words[0], ' '.join(words[1:])) if words else ('','')


def clean_repetition(name):
    words=[]
    for word in name.strip().split():
        if not words or norm(words[-1])!=norm(word):
            words.append(word)
    return ' '.join(words)


def latest_profiles(c,membership,members):
    selected={}
    active={r['id'] for r in c.execute('SELECT id FROM identity_links WHERE active=1')}
    for row in c.execute('SELECT * FROM profile_edits ORDER BY id DESC'):
        gid=membership[row['person_id']]
        if gid in selected or (row['link_id'] is not None and row['link_id'] not in active):
            continue
        if set(json.loads(row['members'])) <= set(members[gid]):
            selected[gid]=dict(row)
    return selected


def aliases_for(c,ps,ids):
    names={ps[i]['name'] for i in ids}
    for row in c.execute('SELECT person_id,name FROM aliases'):
        if row['person_id'] in ids:
            names.add(row['name'])
    for row in c.execute('SELECT person_id,first_name,last_name,display_name FROM profile_edits'):
        if row['person_id'] in ids:
            names.update([row['display_name'],' '.join(filter(None,[row['first_name'],row['last_name']]))])
    return sorted(filter(None,names),key=str.casefold)


def canonical_profiles(c,ps,membership,members):
    edits=latest_profiles(c,membership,members)
    names_by_group={gid:{ps[i]['name'] for i in ids} for gid,ids in members.items()}
    for row in c.execute('SELECT person_id,name FROM aliases'):
        names_by_group[membership[row['person_id']]].add(row['name'])
    for row in c.execute('SELECT person_id,first_name,last_name,display_name FROM profile_edits'):
        names_by_group[membership[row['person_id']]].update([row['display_name'],' '.join(filter(None,[row['first_name'],row['last_name']]))])
    result={}
    for gid,ids in members.items():
        base=ps[gid]
        first,last=(base['first_name'],base['last_name']) if base.get('name_structure') in ('structured','given_only','surname_only','email_only') else split_name(base['name'])
        values={'first_name':first,'last_name':last,'name':base['name'],
                'email':next((ps[i]['email'] for i in ids if ps[i]['email']),''),
                'phone':next((ps[i]['phone'] for i in ids if ps[i]['phone']),'')}
        edit=edits.get(gid)
        if edit:
            values.update(first_name=edit['first_name'],last_name=edit['last_name'],name=edit['display_name'],email=edit['email'],phone=edit['phone'])
        values['aliases']=sorted(filter(None,names_by_group[gid]),key=str.casefold)
        values['profile_edited']=edit is not None
        result[gid]=values
    return result


def save_profile(c,pid,values,reason='Modifica anagrafica',link_id=None):
    ps,membership,members=groups(c)
    if pid not in ps:
        raise HTTPException(404,'Persona non trovata')
    gid=membership[pid]
    email=values['email'].strip().casefold()
    phone=values['phone'].strip()
    if email and (not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254):
        raise HTTPException(422,'Inserisci un indirizzo email valido')
    if phone and (not 5<=len(norm(phone))<=20 or not re.fullmatch(r'[+\d\s()./-]+',phone)):
        raise HTTPException(422,'Inserisci un numero di telefono valido')
    profiles=canonical_profiles(c,ps,membership,members)
    existing=[profiles[gid]]+[ps[i] for i in members[gid]]
    known_email=any(email==p['email'].casefold() for p in existing)
    known_phone=any(norm(phone)==norm(p['phone']) for p in existing)
    for other,profile in profiles.items():
        if other==gid:
            continue
        contacts=[profile]+[ps[i] for i in members[other]]
        if any((email and not known_email and email==p['email'].casefold()) or (norm(phone) and not known_phone and norm(phone)==norm(p['phone'])) for p in contacts):
            raise HTTPException(409,'Email o telefono già associato a un altro profilo. Verifica le identità prima di salvare.')
    fields=[values[k].strip() for k in ('first_name','last_name','display_name')]
    if not fields[0] or not fields[2] or not norm(fields[0]) or not norm(fields[2]) or (fields[1] and not norm(fields[1])):
        raise HTTPException(422,'Nome principale e nominativo visualizzato sono obbligatori')
    c.execute('INSERT INTO profile_edits(person_id,members,first_name,last_name,display_name,email,phone,reason,link_id) VALUES(?,?,?,?,?,?,?,?,?)',
              (gid,json.dumps(members[gid]),*fields,email,phone,reason,link_id))
    return gid


def recommend(options):
    def quality(p):
        original=p['name']; cleaned=clean_repetition(original)
        first,last=split_name(cleaned)
        valid=bool(first and last and norm(first) and norm(last))
        suspicious=any(ch.isdigit() or ch in '@<>' for ch in cleaned)
        return (bool(p.get('profile_edited')),not suspicious,valid,cleaned==original,len(set(norm(w) for w in cleaned.split())))
    best=max(options,key=quality)
    name=clean_repetition(best['name'])
    first,last=(best['first_name'],best['last_name']) if best.get('profile_edited') else split_name(name)
    return {'first_name':first,'last_name':last,'display_name':name,
            'reason':'Nome e cognome riconoscibili; scelta manuale precedente valorizzata e ripetizioni consecutive rimosse.'}
