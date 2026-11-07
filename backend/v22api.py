"""Local Community Intelligence and manual CRM endpoints."""
import json,re
from datetime import date
from fastapi import HTTPException
from fastapi.responses import Response
from . import crm
from .community import Thresholds,settings,segments
from .reporting import people_report,public_person
from .identity import groups
from .querying import Filters,select_people


def register(app,db):
    @app.get('/api/v22/settings')
    def get_settings():
        with db() as c:return settings(c)

    @app.put('/api/v22/settings')
    def put_settings(body:Thresholds):
        with db(True) as c:
            before=settings(c);after=body.model_dump()
            c.execute("INSERT INTO community_settings VALUES('thresholds',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(crm.dumps(after),))
            crm.log(c,'thresholds',None,None,reason=crm.dumps({'before':before,'after':after}))
        return after

    @app.get('/api/v22/segments')
    def segment_cards(start:str='',end:str=''):
        try:
            if start:date.fromisoformat(start)
            if end:date.fromisoformat(end)
            if start and end and start>end:raise ValueError()
        except ValueError:raise HTTPException(422,'Periodo segmenti non valido')
        with db() as c:return segments(c,people_report(c),start,end)

    @app.post('/api/v22/segments')
    def save_segment(body:dict):
        name=str(body.get('name') or '').strip()
        if not name:raise HTTPException(422,'Indica il nome del segmento')
        f=Filters(**body.get('filters',{})).model_dump()
        with db(True) as c:
            sid=c.execute('INSERT INTO crm_segments(name,filters) VALUES(?,?)',(name[:120],crm.dumps(f))).lastrowid
            crm.log(c,'segment_definition',None,None,reason=crm.dumps({'id':sid,'name':name[:120],'filters':f}));return {'id':sid}

    @app.get('/api/v22/tags')
    def tags():
        with db() as c:return [dict(r) for r in c.execute('SELECT * FROM crm_tags ORDER BY archived,name')]

    def tag_values(body):
        name=str(body.get('name') or '').strip();normalized=crm.normalized(name);color=body.get('color','#2f654b')
        if not normalized or len(name)>100 or normalized.replace(' ','')=='vip':raise HTTPException(422,'Nome tag mancante, troppo lungo o riservato (VIP)')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise HTTPException(422,'Colore non valido')
        return name,normalized,color,str(body.get('description',''))[:1000],int(bool(body.get('archived',False)))

    @app.post('/api/v22/tags')
    def create_tag(body:dict):
        values=tag_values(body)
        with db(True) as c:
            if c.execute('SELECT 1 FROM crm_tags WHERE normalized=?',(values[1],)).fetchone():raise HTTPException(409,'Esiste già un tag equivalente, anche se archiviato')
            tid=c.execute('INSERT INTO crm_tags(name,normalized,color,description,archived) VALUES(?,?,?,?,?)',values).lastrowid
            crm.log(c,'tag_definition',None,None,reason=crm.dumps({'id':tid,'values':values}));return {'id':tid}

    @app.put('/api/v22/tags/{tid}')
    def update_tag(tid:int,body:dict):
        values=tag_values(body)
        with db(True) as c:
            before=c.execute('SELECT * FROM crm_tags WHERE id=?',(tid,)).fetchone()
            if not before:raise HTTPException(404,'Tag non trovato')
            if c.execute('SELECT 1 FROM crm_tags WHERE normalized=? AND id!=?',(values[1],tid)).fetchone():raise HTTPException(409,'Esiste già un tag equivalente')
            c.execute('UPDATE crm_tags SET name=?,normalized=?,color=?,description=?,archived=? WHERE id=?',(*values,tid));crm.log(c,'tag_definition',None,None,reason=crm.dumps({'before':dict(before),'after':values}));return {'ok':True}

    @app.get('/api/v22/campaigns')
    def campaigns():
        with db() as c:return [dict(r) for r in c.execute('SELECT * FROM crm_campaigns ORDER BY id DESC')]

    @app.post('/api/v22/campaigns')
    def create_campaign(body:dict):
        name=str(body.get('name') or '').strip();key=crm.normalized(name)
        if not key:raise HTTPException(422,'Indica il nome dell’iniziativa')
        with db(True) as c:
            if c.execute('SELECT 1 FROM crm_campaigns WHERE normalized=?',(key,)).fetchone():raise HTTPException(409,'Iniziativa già presente')
            cid=c.execute('INSERT INTO crm_campaigns(name,normalized) VALUES(?,?)',(name[:120],key)).lastrowid
            crm.log(c,'campaign_definition',None,None,reason=crm.dumps({'id':cid,'name':name[:120]}));return {'id':cid}

    @app.post('/api/v22/bulk/preview')
    def crm_preview(body:dict):
        with db(True) as c:return crm.preview(c,body)

    @app.post('/api/v22/bulk/{token}/confirm')
    def crm_confirm(token:str):
        with db(True) as c:return crm.commit(c,token)

    @app.post('/api/v22/bulk/{token}/undo')
    def crm_undo(token:str):
        with db(True) as c:return crm.undo(c,token)

    @app.get('/api/v22/people/{pid}')
    def crm_profile(pid:int,history_page:int=1):
        with db() as c:return crm.profile(c,pid,history_page)

    @app.post('/api/v22/people/{pid}/notes')
    def create_note(pid:int,body:dict):
        text=str(body.get('text','')).strip()
        if not text or len(text)>10000:raise HTTPException(422,'Inserisci una nota di massimo 10.000 caratteri')
        with db(True) as c:
            detail=crm.profile(c,pid)
            return {'id':crm.insert(c,'note',detail['members'],{'text':text},str(body.get('operator') or 'Amministratore locale')[:120])}

    @app.patch('/api/v22/records/{rid}')
    def edit_record(rid:int,body:dict):
        with db(True) as c:
            row=c.execute('SELECT * FROM crm_records WHERE id=? AND active=1',(rid,)).fetchone()
            if not row:raise HTTPException(404,'Informazione non trovata')
            if body.get('revision')!=row['revision']:raise HTTPException(409,'Informazione cambiata: ricarica il profilo')
            if body.get('delete'):
                if not body.get('confirm'):raise HTTPException(422,'Conferma esplicitamente la rimozione')
                crm.change(c,dict(row),active=0,reason='Rimozione confermata')
            elif row['kind']=='note':
                text=str(body.get('text','')).strip()
                if not text or len(text)>10000:raise HTTPException(422,'Nota vuota o troppo lunga')
                crm.change(c,dict(row),payload=crm.dumps({'text':text}),reason='Modifica nota')
            elif row['kind']=='reward' and body.get('status') in ('proposed','assigned'):
                ps,mapping,members=groups(c);visible,pending=crm.states(c,mapping)
                owner=next((pid for pid,rows in visible.items() if any(r['id']==rid for r in rows)),None)
                if owner is None:raise HTTPException(409,'Riassegna prima il riconoscimento a un proprietario certo')
                data=json.loads(row['payload'])
                duplicates=[r for r in visible[owner] if r['kind']=='reward' and r['id']!=rid and r['campaign_id']==row['campaign_id'] and crm.normalized(r['data']['type'])==crm.normalized(data['type'])]
                if body['status']=='assigned' and duplicates:
                    if body.get('allow_duplicate') is not True or len(str(body.get('reason','')).strip())<5:raise HTTPException(409,'Possibile doppio premio: conferma esplicita e motivazione richieste')
                    data['exception_reason']=body['reason']
                data['status']=body['status'];crm.change(c,dict(row),payload=crm.dumps(data),reason='Stato riconoscimento confermato: '+str(body.get('reason','')))

            else:raise HTTPException(422,'Modifica non supportata')
        return {'ok':True}

    @app.get('/api/v22/unresolved')
    def unresolved():
        with db() as c:
            ps,mapping,members=groups(c);rows=crm.states(c,mapping)[1]
            tags={r['id']:r['name'] for r in c.execute('SELECT id,name FROM crm_tags')}
            for row in rows:
                row['owners']=[{'id':i,'name':ps[i]['name'],'email':ps[i]['email']} for i in row['origins']]
                row['label']=tags.get(row['tag_id'],'Tag') if row['kind']=='tag' else 'VIP manuale' if row['kind']=='vip' else row['data'].get('text') or row['data'].get('name') or row['kind']
            return rows

    @app.post('/api/v22/records/{rid}/reassign')
    def reassign(rid:int,body:dict):
        with db(True) as c:return crm.reassign(c,rid,body)

    @app.post('/api/v22/records/{rid}/reassign/undo')
    def undo_reassign(rid:int,body:dict):
        with db(True) as c:return crm.undo_reassignment(c,rid,body)

    @app.get('/api/v22/performance/{eid}')
    def performance(eid:int):
        from .performance import event_performance
        with db() as c:return event_performance(c,eid)

    @app.get('/api/v22/compare')
    def compare_events(ids:str='',category:str='',format_name:str=''):
        from .performance import compare
        try:chosen=[int(i) for i in ids.split(',') if i]
        except ValueError:raise HTTPException(422,'Selezione eventi non valida')
        with db() as c:return compare(c,chosen,category,format_name)

    @app.get('/api/v22/insights')
    def community_insights(start:str='',end:str=''):
        from .performance import insights
        try:
            if start:date.fromisoformat(start)
            if end:date.fromisoformat(end)
        except ValueError:raise HTTPException(422,'Periodo non valido')
        with db() as c:return insights(c,start,end)

    @app.get('/api/v22/events/{eid}/report')
    def event_report(eid:int,format:str='pdf'):
        from .post_report import model,pdf,xlsx
        if format not in ('pdf','xlsx'):raise HTTPException(422,'Formato report non valido')
        # Materialize every field in ONE coherent read transaction. Rendering
        # uses this detached model after releasing the global DB lock/connection.
        with db() as c:data=model(c,eid)
        content=pdf(data) if format=='pdf' else xlsx(data)
        filename=f'EVENTLY-report-riepilogo-{eid}.pdf' if format=='pdf' else f'EVENTLY-report-dettagliato-dati-personali-{eid}.xlsx'
        return Response(content,media_type='application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{filename}"'})

    @app.post('/api/v22/export/preview')
    def export_preview(body:dict):
        from .strategic_export import selection,columns
        with db() as c:
            people=selection(c,body);chosen=columns(body)
            return {'count':len(people),'with_email':sum(bool(p['email']) for p in people),'without_email':sum(not p['email'] for p in people),'columns':[label for key,label in chosen],'filters':body.get('filters',{}),'message':'La disponibilità di email non equivale a consenso promozionale. Nessuna email verrà inviata.'}

    @app.post('/api/v22/export')
    def export_list(body:dict):
        from .strategic_export import export
        with db() as c:blob,format=export(c,body)
        return Response(blob,media_type='text/csv; charset=utf-8' if format=='csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="EVENTLY-lista-strategica.{format}"'})

    @app.get('/api/v22/rewards')
    def reward_history(q:str='',campaign_id:int|None=None,status:str='',page:int=1):
        with db() as c:
            report=people_report(c);people={p['id']:p for p in report[0]};visible,_=crm.states(c,report[2]);campaigns={r['id']:r['name'] for r in c.execute('SELECT * FROM crm_campaigns')};rows=[]
            for pid,records in visible.items():
                for r in records:
                    if r['kind']!='reward' or (campaign_id is not None and r['campaign_id']!=campaign_id) or (status and r['data']['status']!=status):continue
                    row={**r,'person_id':pid,'person_name':people[pid]['name'],'campaign_name':campaigns.get(r['campaign_id'],'Nessuna iniziativa')}
                    if q.casefold() not in (row['person_name']+' '+r['data']['name']+' '+r['data']['type']+' '+row['campaign_name']).casefold():continue
                    rows.append(row)
            rows.sort(key=lambda r:r['id'],reverse=True);total=len(rows);page=max(1,page)
            return {'rows':rows[(page-1)*50:page*50],'total':total,'page':page,'page_size':50}
