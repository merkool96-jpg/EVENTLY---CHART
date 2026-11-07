"""Read models: distinct confirmed events rank people; event values stay dynamic."""
from .identity import groups, full_name, norm
from .profiles import canonical_profiles
from .participations import load_evidence,consolidate,STATES


def people_report(c, include_excluded=False):
    ps,membership,members=groups(c)
    canonical=canonical_profiles(c,ps,membership,members)
    es={e['id']:dict(e) for e in c.execute('SELECT * FROM events WHERE include_analytics=1')}
    if include_excluded:es={e['id']:dict(e) for e in c.execute('SELECT * FROM events')}
    evidence=load_evidence(c)
    overrides=[dict(r) for r in c.execute('SELECT * FROM participation_overrides WHERE active=1 ORDER BY id')]
    per_group={gid:{} for gid in members}
    for row in c.execute('SELECT * FROM attendance ORDER BY id'):
        if row['event_id'] not in es:
            continue
        gid=membership[row['person_id']]
        current=per_group[gid].setdefault(row['event_id'],{**{s:False for s in STATES},'amount':0,'records':[]})
        current[row['status']]=True
        current['amount']+=row['amount']
        current['records'].append(dict(row))
    for gid,visits in per_group.items():
        for eid,v in visits.items():
            status,conflict,sources,admin=consolidate(c,eid,members[gid],v['records'],evidence,overrides)
            v.update({s:s==status for s in STATES});v.update(status=status,conflict=conflict,sources=sources,administrative=admin)
    result=[]
    for gid,ids in members.items():
        visits=per_group[gid]
        confirmed=[eid for eid,v in visits.items() if v['confirmed']]
        values=[es[eid]['participant_value_cents'] for eid in confirmed]
        value=sum(v for v in values if v is not None)
        result.append({**ps[gid],'email':next((ps[i]['email'] for i in ids if ps[i]['email']),''),'phone':next((ps[i]['phone'] for i in ids if ps[i]['phone']),''),'visits':len(confirmed),'registrations':sum(v['registered'] for v in visits.values()),'unknown':sum(v['unknown'] for v in visits.values()),'absent':sum(v['absent'] for v in visits.values()),'cancelled':sum(v['cancelled'] for v in visits.values()),'conflicts':sum(v['conflict'] for v in visits.values()),'value':value,'undefined_values':sum(v is None for v in values),'actual_spend':sum(v['amount'] for v in visits.values()),'last_seen':max((es[eid]['date'] for eid in confirmed),default=None),'members':[ps[i] for i in ids],**canonical[gid],'incomplete':not full_name(canonical[gid]['first_name']+' '+canonical[gid]['last_name']), 'first_seen':min((es[eid]['date'] for eid in confirmed),default=None),'event_data':visits})
    # Stable passes preserve alphabetical order for ties, latest date before count.
    result.sort(key=lambda p:norm(p['name']))
    result.sort(key=lambda p:p['last_seen'] or '',reverse=True)
    result.sort(key=lambda p:p['visits'],reverse=True)
    return result,es,membership


def events_report(c, report=None):
    people,es,_=report if report is not None else people_report(c)
    for e in es.values():
        values=[p['event_data'][e['id']] for p in people if e['id'] in p['event_data']]
        e.update(participants=sum(v['confirmed'] for v in values),registrations=sum(v['registered'] for v in values),unknown=sum(v['unknown'] for v in values),absent=sum(v['absent'] for v in values),cancelled=sum(v['cancelled'] for v in values),conflicts=sum(v['conflict'] for v in values),actual_spend=sum(v['amount'] for v in values))
        e['attributed_value']=None if e['participant_value_cents'] is None else e['participants']*e['participant_value_cents']
    return sorted(es.values(),key=lambda e:(e['date'],e['id']),reverse=True)


def public_person(p):
    return {k:v for k,v in p.items() if k!='event_data'}


def matches_filter(p,q):
    return q.casefold().strip() in ' '.join([p['name'],p['email'],p['phone'],*p.get('aliases',[])]).casefold()
