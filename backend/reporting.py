"""Read models: distinct confirmed events rank people; event values stay dynamic."""
from .identity import groups, full_name, norm


def people_report(c):
    ps,membership,members=groups(c)
    es={e['id']:dict(e) for e in c.execute('SELECT * FROM events WHERE archived=0')}
    per_group={gid:{} for gid in members}
    for row in c.execute('SELECT * FROM attendance ORDER BY id'):
        if row['event_id'] not in es:
            continue
        gid=membership[row['person_id']]
        current=per_group[gid].setdefault(row['event_id'],{'confirmed':False,'registered':False,'unknown':False,'amount':0,'records':[]})
        current[row['status']]=True
        current['amount']+=row['amount']
        current['records'].append(dict(row))
    result=[]
    for gid,ids in members.items():
        visits=per_group[gid]
        confirmed=[eid for eid,v in visits.items() if v['confirmed']]
        values=[es[eid]['participant_value_cents'] for eid in confirmed]
        value=sum(v for v in values if v is not None)
        result.append({**ps[gid],'email':next((ps[i]['email'] for i in ids if ps[i]['email']),''),'phone':next((ps[i]['phone'] for i in ids if ps[i]['phone']),''),'visits':len(confirmed),'registrations':sum(not v['confirmed'] and v['registered'] for v in visits.values()),'unknown':sum(not v['confirmed'] and not v['registered'] for v in visits.values()),'value':value,'undefined_values':sum(v is None for v in values),'actual_spend':sum(v['amount'] for v in visits.values()),'last_seen':max((es[eid]['date'] for eid in confirmed),default=None),'members':[ps[i] for i in ids],'incomplete':not full_name(ps[gid]['name']),'event_data':visits})
    # Stable passes preserve alphabetical order for ties, latest date before count.
    result.sort(key=lambda p:norm(p['name']))
    result.sort(key=lambda p:p['last_seen'] or '',reverse=True)
    result.sort(key=lambda p:p['visits'],reverse=True)
    return result,es,membership


def events_report(c):
    people,es,_=people_report(c)
    for e in es.values():
        values=[p['event_data'][e['id']] for p in people if e['id'] in p['event_data']]
        e.update(participants=sum(v['confirmed'] for v in values),registrations=sum(not v['confirmed'] and v['registered'] for v in values),unknown=sum(not v['confirmed'] and not v['registered'] for v in values),actual_spend=sum(v['amount'] for v in values))
        e['attributed_value']=None if e['participant_value_cents'] is None else e['participants']*e['participant_value_cents']
    return sorted(es.values(),key=lambda e:(e['date'],e['id']),reverse=True)


def public_person(p):
    return {k:v for k,v in p.items() if k!='event_data'}
