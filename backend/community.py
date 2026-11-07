"""Dynamic segments from confirmed included history, never stored memberships."""
from datetime import date,timedelta
import json
from pydantic import BaseModel,Field
from .crm import dumps

class Thresholds(BaseModel):
    super_visits:int=Field(default=5,ge=1,le=10000)
    regular_visits:int=Field(default=3,ge=1,le=10000)
    regular_days:int=Field(default=365,ge=1,le=3650)
    recovery_visits:int=Field(default=3,ge=1,le=10000)
    recovery_days:int=Field(default=180,ge=1,le=3650)
    recovery_opportunities:int=Field(default=2,ge=1,le=10000)
    positive_visits:int=Field(default=2,ge=1,le=10000)
    vip_visits:int=Field(default=5,ge=1,le=10000)
    vip_recent_visits:int=Field(default=3,ge=1,le=10000)
    vip_recent_days:int=Field(default=365,ge=1,le=3650)
    vip_last_days:int=Field(default=180,ge=1,le=3650)


def settings(c):
    row=c.execute("SELECT value FROM community_settings WHERE key='thresholds'").fetchone()
    return Thresholds(**(json.loads(row[0]) if row else {})).model_dump()


def match(p,events,key,config,asof=None,start='',end=''):
    today=date.fromisoformat(asof) if asof else date.today();limit=today.isoformat()
    ids=[eid for eid,v in p['event_data'].items() if v['confirmed'] and events[eid]['date']<=limit]
    days=[events[eid]['date'] for eid in ids];count=len(ids);last=max(days,default='')
    recent=lambda n:sum(d>=(today-timedelta(days=n-1)).isoformat() for d in days)
    if key=='increased':
        if not start or not end:return False
        begin=date.fromisoformat(start);finish=date.fromisoformat(end);length=(finish-begin).days+1
        previous=begin-timedelta(days=length)
        return sum(start<=d<=end for d in days)>sum(previous.isoformat()<=d<start for d in days)
    if key=='super':return count>=config['super_visits']
    if key=='regular':return recent(config['regular_days'])>=config['regular_visits']
    if key=='new':return bool(days and start and start<=min(days)<= (end or limit))
    if key=='recovery':return bool(last and count>=config['recovery_visits'] and last<(today-timedelta(days=config['recovery_days'])).isoformat() and sum(last<e['date']<=limit for e in events.values())>=config['recovery_opportunities'])
    if key=='positive':return sum(events[eid]['participant_value_cents'] is not None and events[eid]['participant_value_cents']>0 for eid in ids)>=config['positive_visits']
    if key=='vip_candidates':return not p.get('vip',False) and count>=config['vip_visits'] and recent(config['vip_recent_days'])>=config['vip_recent_visits'] and bool(last and last>=(today-timedelta(days=config['vip_last_days']-1)).isoformat())
    return False


def segments(c,report,start='',end='',asof=None):
    from .querying import select_people
    config=settings(c);today=date.fromisoformat(asof) if asof else date.today();end=end or today.isoformat();start=start or (today-timedelta(days=364)).isoformat()
    definitions=[('super','Super Fedeli',f"Almeno {config['super_visits']} presenze storiche"),('regular','Partecipanti Abituali',f"Almeno {config['regular_visits']} presenze negli ultimi {config['regular_days']} giorni"),('new','Nuovi',f'Prima presenza conosciuta dal {start} al {end}'),('recovery','Inattivi da recuperare',f"Almeno {config['recovery_visits']} presenze, nessuna da {config['recovery_days']} giorni e almeno {config['recovery_opportunities']} occasioni successive"),('positive','Frequentatori con valore positivo',f"Almeno {config['positive_visits']} presenze in eventi con valore attribuito positivo"),('vip_candidates','Candidati VIP',f"Almeno {config['vip_visits']} storiche, {config['vip_recent_visits']} in {config['vip_recent_days']} giorni, ultima entro {config['vip_last_days']} giorni. Nessuna assegnazione automatica.")]
    results=[];previous=today-timedelta(days=30)
    for key,name,definition in definitions:
        ids=[p['id'] for p in report[0] if match(p,report[1],key,config,today.isoformat(),start,end)]
        if key=='new':
            length=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
            old_end=date.fromisoformat(start)-timedelta(days=1);old_start=old_end-timedelta(days=length-1)
            prior=sum(match(p,report[1],key,config,today.isoformat(),old_start.isoformat(),old_end.isoformat()) for p in report[0]);comparison=f'Periodo precedente di {length} giorni'
        else:
            prior=sum(match(p,report[1],key,config,previous.isoformat()) for p in report[0]);comparison=f'Stesso criterio al {previous.isoformat()}, ricostruito dalla storia conosciuta oggi'
        f={'community_segment':key}
        if key=='new':f.update(segment_start=start,segment_end=end)
        results.append({'key':key,'name':name,'definition':definition,'count':len(ids),'previous_count':prior,'change':None if key=='vip_candidates' else len(ids)-prior,'comparison':('Stato VIP storico non ricostruito: variazione non disponibile' if key=='vip_candidates' else comparison),'filters':f})
    for row in c.execute('SELECT * FROM crm_segments WHERE archived=0 ORDER BY id'):
        f=json.loads(row['filters']);results.append({'key':'custom_'+str(row['id']),'name':row['name'],'definition':'Segmento personalizzato: filtri salvati, membri ricalcolati','count':len(select_people(report,f)),'change':None,'comparison':'Confronto temporale non disponibile per questo filtro personalizzato','filters':f})
    return results
