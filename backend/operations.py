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
        newbies={p['id'] for p in people if p['id'] in ids and min(events[x]['date'] for x in confirmed[p['id']])==event['date']}
        returned={pid for pid in ids if any(event['date']<events[x]['date']<=min((date.fromisoformat(event['date'])+timedelta(days=window)).isoformat(),today.isoformat()) for x in confirmed[pid])}
        old={pid for pid in ids if any(events[x]['date']<event['date'] for x in confirmed[pid])}
        records=[p['event_data'][eid] for p in people if eid in p['event_data']]
        enrolled=[v for v in records if 'registered' in v['sources']]
        covered=bool(event['registration_complete'] and enrolled and len(enrolled)==len(records) and all(v['status'] in ('confirmed','absent','cancelled') and not v['conflict'] for v in enrolled))
        mature=(today-date.fromisoformat(event['date'])).days>=window
        opportunities=sum(event['date']<e['date']<=min((date.fromisoformat(event['date'])+timedelta(days=window)).isoformat(),today.isoformat()) for e in events.values())
        return_reason='Periodo di osservazione non ancora completo' if not mature else 'Nessuna occasione di ritorno nella finestra conosciuta' if not opportunities else 'Nessuna presenza idonea' if not ids else ''
        event_rows.append({**event,'new':len(newbies),'returning':len(old),'returned_after':len(returned),'new_returned_after':len(newbies & returned),'denominator':len(ids),'window_days':window,'recent_cohort':(today-date.fromisoformat(event['date'])).days<window,'return_rate':len(returned)/len(ids) if ids and mature and opportunities else None,'return_reason':return_reason,'return_opportunities':opportunities,'conversion':sum(v['confirmed'] for v in enrolled)/len(enrolled) if covered else None,'conversion_reason':'' if covered else 'Dati insufficienti: iscritti completi ed esiti non attestati'})
    affinity=[]
    for i,a in enumerate(event_rows):
        for b in event_rows[i+1:]:
            shared=sum(a['id'] in ids and b['id'] in ids for ids in confirmed.values())
            if shared:affinity.append({'a_id':a['id'],'b_id':b['id'],'a':a['name'],'b':b['name'],'shared':shared,'category_a':a['category'],'category_b':b['category']})
    f=filters or {}
    event_rows=[e for e in event_rows if (not f.get('event_id') or e['id']==f['event_id']) and (not f.get('category') or e['category']==f['category']) and (not f.get('start') or e['date']>=f['start']) and (not f.get('end') or e['date']<=f['end'])]
    shown={e['id'] for e in event_rows};affinity=[a for a in affinity if a['a_id'] in shown and a['b_id'] in shown];affinity.sort(key=lambda a:(-a['shared'],a['a_id'],a['b_id']))
    categories={}
    for eid,e in events.items():
        if e['category']:
            categories.setdefault(e['category'],set()).update(pid for pid,ids in confirmed.items() if eid in ids)
    category_affinity=[{'a':a,'b':b,'shared':len(categories[a]&categories[b])} for i,a in enumerate(sorted(categories)) for b in sorted(categories)[i+1:] if categories[a]&categories[b]]
    category_affinity.sort(key=lambda row:(-row['shared'],row['a'],row['b']))
    scoped_events=[(events[eid],v) for p in chosen for eid,v in p['event_data'].items() if v['confirmed']]
    first_date=f.get('start','')
    segment_new=[p for p in chosen if p['visits']>0 and p['first_seen']==p['first_seen_global']]
    segment_returning=[p for p in chosen if p['visits']>0 and p['first_seen_global']<p['first_seen']]
    scoped=bool(f.get('start') or f.get('end') or f.get('category') or f.get('event_id'))
    return {'people':len(chosen),'with_presence':sum(p['visits']>0 for p in chosen),'new':len(segment_new) if scoped else None,'returning':len(segment_returning) if scoped else None,'period_defined':scoped,'historical_returning':sum(p['visits']>=2 for p in people),'historical_people':len(people),'historical_with_presence':sum(p['visits']>0 for p in people),
            'free_presences':sum(e['participant_value_cents']==0 for e,v in scoped_events),'paid_presences':sum(e['participant_value_cents'] is not None and e['participant_value_cents']>0 for e,v in scoped_events),'undefined_presences':sum(e['participant_value_cents'] is None for e,v in scoped_events),'attributed_value':sum(p['value'] for p in chosen),'first_presence':min((e['date'] for e,v in scoped_events),default=None),'last_presence':max((e['date'] for e,v in scoped_events),default=None),'category_affinity':category_affinity,
            'frequencies':{str(n):sum(p['visits']>=n for p in chosen) for n in (2,3,5,10)},'events':event_rows,'affinity':affinity,'coverage':'Solo lo storico importato è conosciuto; nessuna assenza è dedotta dai dati mancanti.',
            'inactive':{str(days):sum(p['last_seen_global'] is not None and p['last_seen_global']<=(today-timedelta(days=days)).isoformat() for p in select_people(report,{**f,'inactive_days':days})) for days in (30,90,180,365)}}
