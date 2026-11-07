"""Local operational workflows. No destructive changes to imported identities."""
import json
import secrets
import time
from fastapi import HTTPException
from .identity import groups
from .reporting import people_report
from .querying import select_people
from .importing import snapshot


def preview_bulk(c,event_id,status,ids=None,filters=None,q='',operator='Amministratore locale'):
    report=people_report(c,include_excluded=True)
    if event_id not in report[1]:raise HTTPException(404,'Evento non trovato')
    people=select_people(report,filters,q)
    chosen=[p for p in people if event_id in p['event_data'] and (ids is None or p['id'] in ids)]
    changes=[{'person_id':p['id'],'members':[m['id'] for m in p['members']],'before':p['event_data'][event_id]['status'],'name':p['name'] or p['email'] or f'Profilo #{p["id"]}'} for p in chosen if p['event_data'][event_id]['status']!=status or p['event_data'][event_id]['conflict']]
    token=secrets.token_urlsafe(20)
    config={'event_id':event_id,'status':status,'operator':operator,'changes':changes}
    c.execute('INSERT INTO bulk_operations VALUES(?,?,?,0,0,?)',(token,json.dumps(config),snapshot(c),int(time.time())))
    return {'token':token,'selected':len(chosen),'changed':len(changes),'unchanged':len(chosen)-len(changes),'changes':changes}


def commit_bulk(c,token):
    row=c.execute('SELECT * FROM bulk_operations WHERE token=?',(token,)).fetchone()
    if not row or int(time.time())-row['created_at']>3600:raise HTTPException(410,'Anteprima scaduta')
    if row['committed']:raise HTTPException(409,'Operazione già confermata')
    if row['snapshot']!=snapshot(c):raise HTTPException(409,'Dati cambiati: rigenera l’anteprima')
    config=json.loads(row['config'])
    for change in config['changes']:
        c.execute('INSERT INTO participation_overrides(event_id,members,status,operator,batch) VALUES(?,?,?,?,?)',(config['event_id'],json.dumps(change['members']),config['status'],config['operator'],token))
    c.execute('UPDATE bulk_operations SET committed=1 WHERE token=?',(token,))
    return {'ok':True,'changed':len(config['changes']),'token':token}


def undo_bulk(c,token):
    row=c.execute('SELECT * FROM bulk_operations WHERE token=? AND committed=1 AND undone=0',(token,)).fetchone()
    if not row:raise HTTPException(409,'Operazione non annullabile')
    own=c.execute('SELECT * FROM participation_overrides WHERE batch=?',(token,)).fetchall()
    for r in own:
        ids=set(json.loads(r['members']))
        later=c.execute('SELECT * FROM participation_overrides WHERE event_id=? AND id>? AND active=1',(r['event_id'],r['id'])).fetchall()
        if any(ids & set(json.loads(x['members'])) for x in later):raise HTTPException(409,'Esistono correzioni successive sugli stessi partecipanti')
    c.execute('UPDATE participation_overrides SET active=0 WHERE batch=?',(token,))
    c.execute('UPDATE bulk_operations SET undone=1 WHERE token=?',(token,))
    return {'ok':True,'restored':len(own)}


def analytics(c,filters=None,window=90,reference=None):
    from datetime import date,timedelta
    today=date.fromisoformat(reference) if reference else date.today()
    report=people_report(c);people,events,_=report;chosen=select_people(report,filters)
    confirmed={p['id']:{eid for eid,v in p['event_data'].items() if v['confirmed']} for p in people}
    event_rows=[]
    for eid,event in events.items():
        ids={pid for pid,es in confirmed.items() if eid in es}
        newbies={p['id'] for p in people if p['id'] in ids and min(confirmed[p['id']],key=lambda x:(events[x]['date'],x))==eid}
        returned={pid for pid in ids if any(event['date']<events[x]['date']<=(date.fromisoformat(event['date'])+timedelta(days=window)).isoformat() for x in confirmed[pid])}
        old={pid for pid in ids if any(events[x]['date']<event['date'] for x in confirmed[pid])}
        records=[p['event_data'][eid] for p in people if eid in p['event_data']]
        enrolled=[v for v in records if 'registered' in v['sources']]
        covered=bool(event['registration_complete'] and enrolled and len(enrolled)==len(records) and all(v['status'] in ('confirmed','absent','cancelled') and not v['conflict'] for v in enrolled))
        event_rows.append({**event,'new':len(newbies),'returning':len(old),'returned_after':len(returned),'new_returned_after':len(newbies & returned),'denominator':len(ids),'window_days':window,'recent_cohort':(today-date.fromisoformat(event['date'])).days<window,'return_rate':len(returned)/len(ids) if ids else None,'conversion':sum(v['confirmed'] for v in enrolled)/len(enrolled) if covered else None,'conversion_reason':'' if covered else 'Dati insufficienti: iscritti completi ed esiti non attestati'})
    affinity=[]
    for i,a in enumerate(event_rows):
        for b in event_rows[i+1:]:
            shared=sum(a['id'] in ids and b['id'] in ids for ids in confirmed.values())
            if shared:affinity.append({'a':a['name'],'b':b['name'],'shared':shared,'category_a':a['category'],'category_b':b['category']})
    f=filters or {}
    event_rows=[e for e in event_rows if (not f.get('event_id') or e['id']==f['event_id']) and (not f.get('category') or e['category']==f['category']) and (not f.get('start') or e['date']>=f['start']) and (not f.get('end') or e['date']<=f['end'])]
    shown={e['name'] for e in event_rows};affinity=[a for a in affinity if a['a'] in shown or a['b'] in shown]
    first_date=f.get('start','')
    return {'people':len(chosen),'with_presence':sum(p['visits']>0 for p in chosen),'new':sum(p['visits']>0 and (not first_date or p['first_seen_global']>=first_date) for p in chosen),'returning':sum(p['visits']>0 and bool(first_date) and p['first_seen_global']<first_date for p in chosen),
            'frequencies':{str(n):sum(p['visits']>=n for p in chosen) for n in (2,3,5,10)},'events':event_rows,'affinity':affinity,'coverage':'Solo lo storico importato è conosciuto; nessuna assenza è dedotta dai dati mancanti.',
            'inactive':{str(days):sum(p['last_seen'] is not None and p['last_seen']<=(today-timedelta(days=days)).isoformat() for p in people) for days in (30,90,180,365)}}
