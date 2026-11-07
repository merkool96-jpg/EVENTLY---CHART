"""One filter contract for paginated UI, Top 50, segments and exports."""
from copy import deepcopy
from datetime import date,timedelta
from pydantic import BaseModel,Field,field_validator,model_validator
from .reporting import matches_filter

class Filters(BaseModel):
    event_id:int|None=None
    category:str=''
    start:str=''
    end:str=''
    min_visits:int=Field(default=0,ge=0)
    max_visits:int|None=Field(default=None,ge=0)
    min_value:int=Field(default=0,ge=0)
    max_value:int|None=Field(default=None,ge=0)
    last_before:str=''
    segment:str=''
    pricing:str=''
    quality:str=''
    inactive_days:int|None=Field(default=None,ge=0)

    @field_validator('start','end','last_before')
    @classmethod
    def valid_date(cls,value):
        if value:date.fromisoformat(value)
        return value

    @model_validator(mode='after')
    def bounds(self):
        if self.start and self.end and self.start>self.end:raise ValueError('Periodo non valido')
        if self.max_visits is not None and self.max_visits<self.min_visits:raise ValueError('Limiti presenze invertiti')
        if self.max_value is not None and self.max_value<self.min_value:raise ValueError('Limiti valore invertiti')
        return self


def select_people(report,filters=None,q='',sort='visits',direction='desc',ranked=False):
    f=filters if isinstance(filters,Filters) else Filters(**(filters or {}))
    people,events,_=report
    selected=[]
    scoped=bool(f.event_id or f.category or f.start or f.end or f.pricing)
    for original in people:
        if not matches_filter(original,q):continue
        p={**original};p['first_seen_global']=p['first_seen']
        visits={eid:v for eid,v in p['event_data'].items() if (not f.event_id or eid==f.event_id) and (not f.category or events[eid]['category']==f.category) and (not f.start or events[eid]['date']>=f.start) and (not f.end or events[eid]['date']<=f.end) and (not f.pricing or (f.pricing=='free' and events[eid]['participant_value_cents']==0) or (f.pricing=='paid' and events[eid]['participant_value_cents'] is not None and events[eid]['participant_value_cents']>0) or (f.pricing=='undefined' and events[eid]['participant_value_cents'] is None))}
        if scoped and not visits:continue
        confirmed=[eid for eid,v in visits.items() if v['confirmed']]
        p.update(event_data=visits,visits=len(confirmed),value=sum(events[eid]['participant_value_cents'] or 0 for eid in confirmed),undefined_values=sum(events[eid]['participant_value_cents'] is None for eid in confirmed),last_seen=max((events[eid]['date'] for eid in confirmed),default=None))
        p.update(first_seen=min((events[eid]['date'] for eid in confirmed),default=None),actual_spend=sum(v['amount'] for v in visits.values()),conflicts=sum(v['conflict'] for v in visits.values()))
        p.update({key:sum(v[state] for v in visits.values()) for key,state in [('registrations','registered'),('unknown','unknown'),('absent','absent'),('cancelled','cancelled')]})
        if ranked and not p['visits']:continue
        if p['visits']<f.min_visits or (f.max_visits is not None and p['visits']>f.max_visits):continue
        if p['value']<f.min_value or (f.max_value is not None and p['value']>f.max_value):continue
        if f.last_before and (not p['last_seen'] or p['last_seen']>f.last_before):continue
        first_in_scope=min((events[eid]['date'] for eid in confirmed),default=None)
        if f.segment=='new' and (not first_in_scope or first_in_scope!=p['first_seen_global']):continue
        if f.segment=='returning' and (not first_in_scope or not p['first_seen_global'] or p['first_seen_global']>=first_in_scope):continue
        if f.quality=='incomplete' and not p['incomplete']:continue
        if f.quality=='no_email' and p['email']:continue
        if f.quality=='no_contacts' and (p['email'] or p['phone']):continue
        if f.quality=='conflict' and not any(v['conflict'] for v in visits.values()):continue
        if f.inactive_days is not None and (not original['last_seen'] or original['last_seen']>(date.today()-timedelta(days=f.inactive_days)).isoformat()):continue
        p['later_events']=sum(e['date']>original['last_seen'] and e['date']<=date.today().isoformat() for e in events.values()) if original['last_seen'] else 0
        selected.append(p)
    if sort not in ('name','visits','registrations','value','last_seen'):sort='visits'
    selected.sort(key=lambda p:(-p['visits'],''.join(chr(255-ord(ch)) for ch in (p['last_seen'] or '')),p['name'].casefold(),p['id']))
    selected.sort(key=lambda p:(p[sort].casefold() if sort=='name' else p[sort] or '' if sort=='last_seen' else p[sort]),reverse=direction=='desc')
    if sort=='last_seen':selected.sort(key=lambda p:p['last_seen'] is None)
    return selected
