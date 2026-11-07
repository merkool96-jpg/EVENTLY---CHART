"""Post-event descriptive metrics. Strict dates and explicit observation maturity."""
from datetime import date,timedelta,datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from .reporting import people_report,events_report
from .community import segments


def event_performance(c,eid,asof=None,report=None):
    today=date.fromisoformat(asof) if asof else date.today()
    report=report or people_report(c,True);people,all_events,_=report
    if eid not in all_events:raise HTTPException(404,'Evento non trovato')
    event=next(e for e in events_report(c,report) if e['id']==eid)
    included={i:e for i,e in all_events.items() if e['include_analytics'] or i==eid}
    history={p['id']:{i for i,v in p['event_data'].items() if i in included and v['confirmed'] and included[i]['date']<=today.isoformat()} for p in people}
    attendees=[p for p in people if p['event_data'].get(eid,{}).get('confirmed')]
    first=lambda p:min((included[i]['date'] for i in history[p['id']]),default=None)
    new=[p for p in attendees if first(p)==event['date']]
    recurring=[p for p in attendees if first(p) and first(p)<event['date']]
    windows=[]
    for days in (30,60,90,180):
        end=(date.fromisoformat(event['date'])+timedelta(days=days)).isoformat()
        opportunities=[e for i,e in included.items() if i!=eid and e['include_analytics'] and event['date']<e['date']<=min(end,today.isoformat())]
        returned=[p['id'] for p in attendees if any(event['date']<included[i]['date']<=min(end,today.isoformat()) for i in history[p['id']])]
        mature=today.isoformat()>=end
        measurable=bool(mature and opportunities and attendees and event['include_analytics'])
        reason='Misurabile sullo storico disponibile' if measurable else 'Evento escluso dalle statistiche' if not event['include_analytics'] else 'Periodo di osservazione non ancora completo' if not mature else 'Nessuna occasione di ritorno nella finestra conosciuta' if not opportunities else 'Nessuna presenza idonea'
        windows.append({'days':days,'end':end,'eligible':len(attendees),'returned':len(returned),'returned_ids':returned,'opportunities':len(opportunities),'mature':mature,'rate':len(returned)/len(attendees) if measurable else None,'reason':reason})
    after={p['id'] for p in attendees if any(included[i]['date']>event['date'] for i in history[p['id']])}
    expense_available=any(p['event_data'].get(eid,{}).get('amount',0)!=0 for p in people)
    if not expense_available:
        for row in c.execute('SELECT r.original,i.mapping FROM import_rows r JOIN imports i ON i.id=r.import_id WHERE i.event_id=?',(eid,)):
            import json
            column=json.loads(row['mapping']).get('amount');original=json.loads(row['original'])
            if isinstance(column,int) and 0<=column<len(original) and original[column] not in ('',None):expense_available=True;break
    distribution={str(n):sum(len(history[p['id']])==n for p in attendees) for n in sorted({len(history[p['id']]) for p in attendees})}
    return {'event':event,'presences':len(attendees),'new':len(new),'recurring':len(recurring),'recurring_rate':len(recurring)/len(attendees) if attendees else None,'returned_later':len(after),'windows':windows,'frequency_distribution':distribution,'attributed_value':event['attributed_value'],'cost':event['cost'] if event.get('cost_defined') else None,'reported_spend':event['actual_spend'] if expense_available else None,'verified_revenue':None,'asof':today.isoformat(),'generated_at':datetime.now(ZoneInfo('Europe/Rome')).isoformat(),'coverage':'Solo presenze confermate e date degli eventi inclusi caricati. Non conosciamo eventi esterni o copertura completa. Spesa riportata non è incasso verificato; importi mancanti non sono zero documentato. Costi legacy pari a zero senza conferma sono non definiti. Eventi nella stessa data non sono ordinati.'}


def compare(c,ids=None,category='',format_name='',asof=None):
    report=people_report(c,True)
    es=[e for e in report[1].values() if (ids and e['id'] in ids) or (not ids and e['include_analytics'] and (not category or e['category']==category) and (not format_name or e['name'].casefold()==format_name.casefold()))]
    es.sort(key=lambda e:(e['date'],e['id']))
    rows=[event_performance(c,e['id'],asof,report) for e in es]
    comparisons=[]
    for previous,current in zip(rows,rows[1:]):
        metrics={}
        for key in ('presences','new','recurring','attributed_value','cost','reported_spend'):
            a,b=previous[key],current[key];metrics[key]={'absolute':b-a if a is not None and b is not None else None,'percent':(b-a)/a if a not in (None,0) and b is not None else None}
        for days in (30,60,90,180):
            a=next(x for x in previous['windows'] if x['days']==days);b=next(x for x in current['windows'] if x['days']==days)
            metrics['return_'+str(days)]={'absolute':b['rate']-a['rate'] if a['rate'] is not None and b['rate'] is not None else None,'percent':None}
        comparisons.append({'from':previous['event']['id'],'to':current['event']['id'],'metrics':metrics})
    return {'rows':rows,'differences':comparisons,'method':'Confronto descrittivo: (secondo-primo)/primo solo con denominatore non nullo; ritorni solo con stessa finestra matura e occasioni note.'}


def insights(c,start='',end=''):
    from .operations import analytics
    report=people_report(c);today=date.fromisoformat(end) if end else date.today();begin=date.fromisoformat(start) if start else today-timedelta(days=89)
    length=(today-begin).days+1
    if length<1:raise HTTPException(422,'Periodo non valido')
    prev_end=begin-timedelta(days=1);prev_start=prev_end-timedelta(days=length-1)
    increased=[];distribution={};timeline=[]
    for p in report[0]:
        dates=[report[1][i]['date'] for i,v in p['event_data'].items() if v['confirmed']]
        current=sum(begin.isoformat()<=d<=today.isoformat() for d in dates);previous=sum(prev_start.isoformat()<=d<=prev_end.isoformat() for d in dates)
        if current>previous:increased.append(p['id'])
        distribution[str(p['visits'])]=distribution.get(str(p['visits']),0)+1
    for e in events_report(c,report):timeline.append({'id':e['id'],'name':e['name'],'date':e['date'],'presences':e['participants'],'value':e['attributed_value']})
    return {'start':begin.isoformat(),'end':today.isoformat(),'previous_start':prev_start.isoformat(),'previous_end':prev_end.isoformat(),'increased_count':len(increased),'increased_ids':increased,'distribution':distribution,'segments':segments(c,report,begin.isoformat(),today.isoformat(),today.isoformat()),'analytics':analytics(c,{'start':begin.isoformat(),'end':today.isoformat()}),'timeline':timeline,'method':'Aumento frequenza: più presenze in due intervalli consecutivi di pari durata, non causalità. Distribuzione sullo storico incluso.'}
