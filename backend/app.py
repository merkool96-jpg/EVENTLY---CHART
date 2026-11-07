"""EVENTLY V1.1 — local, persistent and reversible event intelligence."""
import json
import os
import secrets
import sqlite3
import time
import threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator,ValidationError
from .migrations import migrate, backup_database
from .identity import groups, merge, keep_separate, split_member, candidates
from .importing import read_sheet, records_from, apply_import, snapshot
from .reporting import people_report, events_report, public_person, matches_filter
from .profiles import canonical_profiles,save_profile,recommend
from .exporting import export_file

app = FastAPI(title='EVENTLY', version='2.2.1')
@app.exception_handler(sqlite3.Error)
async def storage_error(request,error):
    return JSONResponse(status_code=500,content={'detail':'Operazione non completata. I dati sono stati conservati: riprova o controlla il backup.'})

@app.exception_handler(ValidationError)
async def filter_error(request,error):
    return JSONResponse(status_code=422,content={'detail':'Controlla i filtri: date e limiti devono essere coerenti.'})

DB = os.getenv('EVENTLY_DB', str(Path(__file__).parent / 'evently.db'))


DB_LOCK=threading.RLock()

@contextmanager
def db(write=False):
    with DB_LOCK:
        c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield c;c.commit()
        except Exception:
            c.rollback();raise
        finally:c.close()


def init():
    migrate(DB)
init()


class Event(BaseModel):
    name: str = Field(min_length=1,max_length=200)
    date: date
    location: str = Field(default='',max_length=200)
    category:str=Field(default='',max_length=100)
    edition:str=Field(default='',max_length=100)
    registration_complete:bool=False
    cost_defined:bool|None=None
    cost: int = Field(default=0,ge=0,le=10000000000)
    participant_value_cents: int | None = Field(default=None,ge=0,le=10000000000)

    @field_validator('name')
    @classmethod
    def clean_name(cls,value):
        if not value.strip():
            raise ValueError('Nome evento obbligatorio')
        return value.strip()


class PersonDetails(BaseModel):
    first_name: str = Field(min_length=1,max_length=120)
    last_name: str = Field(default='',max_length=200)
    display_name: str = Field(min_length=1,max_length=300)
    email: str = Field(default='',max_length=254)
    phone: str = Field(default='',max_length=50)


class MergeRequest(BaseModel):
    a: int
    b: int


class Decision(BaseModel):
    a: int
    b: int
    action: Literal['merge','separate']
    profile: PersonDetails | None = None


class Status(BaseModel):
    status: Literal['registered','confirmed','absent','cancelled','unknown']


def active_event(c,eid):
    if not c.execute('SELECT id FROM events WHERE id=? AND archived=0',(eid,)).fetchone():
        raise HTTPException(404,'Evento non trovato')


@app.get('/api/health')
def health():
    with db() as c:
        version=c.execute('PRAGMA user_version').fetchone()[0]
    return {'status':'ok','schema_version':version,'version':'2.2.1'}


@app.post('/api/backup')
def backup():
    path=backup_database(DB)
    return {'file':path.name,'verified':True}


@app.get('/api/events')
def events(include_archived:bool=False):
    with db() as c:
        return [e for e in events_report(c,people_report(c,True)) if include_archived or not e['archived']]


@app.post('/api/events',status_code=201)
def create_event(e:Event):
    with db(True) as c:
        eid=c.execute('INSERT INTO events(name,date,location,cost,participant_value_cents) VALUES(?,?,?,?,?)',(e.name,str(e.date),e.location,e.cost,e.participant_value_cents)).lastrowid
        c.execute('UPDATE events SET category=?,edition=?,registration_complete=? WHERE id=?',(e.category,e.edition,int(e.registration_complete),eid))
        c.execute('UPDATE events SET cost_defined=? WHERE id=?',(int(e.cost_defined if e.cost_defined is not None else 'cost' in e.model_fields_set),eid))
    return {'id':eid}


@app.put('/api/events/{event_id}')
def update_event(event_id:int,e:Event):
    with db(True) as c:
        row=c.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
        if not row:raise HTTPException(404,'Evento non trovato')
        before=dict(row);values={}
        for key in ('name','date','location','cost','participant_value_cents','category','edition','registration_complete'):
            if key in e.model_fields_set:
                value=getattr(e,key);values[key]=str(value) if key=='date' else int(value) if key=='registration_complete' else value
        if 'cost' in e.model_fields_set or e.cost_defined is not None:values['cost_defined']=int(e.cost_defined if e.cost_defined is not None else True)
        if values:c.execute('UPDATE events SET '+','.join(key+'=?' for key in values)+' WHERE id=?',(*values.values(),event_id))
        from .crm import log,dumps
        log(c,'event_metadata',None,None,reason=dumps({'event_id':event_id,'before':before,'changes':values}))
    return {'ok':True}


@app.delete('/api/events/{event_id}')
def delete_event(event_id:int):
    with db(True) as c:
        active_event(c,event_id)
        c.execute('UPDATE events SET archived=1 WHERE id=?',(event_id,))
    return {'ok':True,'archived':True}


@app.get('/api/people')
def people(q:str='',limit:int=10000,ranked:bool=False):
    with db() as c:
        ps,_,_=people_report(c)
        ps=[public_person(p) for p in ps if (not ranked or p['visits']>0) and matches_filter(p,q)]
        return ps[:max(1,min(limit,10000))]


@app.get('/api/exports/count')
def export_count(q:str='',filters:str='{}'):
    with db() as c:
        from .querying import select_people
        try:selection=json.loads(filters)
        except Exception:raise HTTPException(422,'Filtri non validi')
        return {'count':len(select_people(people_report(c),selection,q))}


@app.get('/api/exports/participants')
def export_participants(format:Literal['xlsx','csv']='xlsx',q:str='',filters:str='{}'):
    with db() as c:
        try:selection=json.loads(filters)
        except Exception:raise HTTPException(422,'Filtri non validi')
        data=export_file(c,format,q,selection)
    media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if format=='xlsx' else 'text/csv; charset=utf-8'
    return Response(data,media_type=media,headers={'Content-Disposition':f'attachment; filename="EVENTLY-partecipanti.{format}"','Cache-Control':'no-store'})


@app.post('/api/matches/preview')
def merge_preview(d:MergeRequest):
    if d.a==d.b:
        raise HTTPException(400,'Seleziona due identità differenti')
    with db(True) as c:
        ps,membership,members=groups(c)
        if d.a not in ps or d.b not in ps:
            raise HTTPException(404,'Persona non trovata')
        if membership[d.a]==membership[d.b]:
            raise HTTPException(409,'Queste identità sono già unite')
        canonical=canonical_profiles(c,ps,membership,members)
        options=[canonical[membership[d.a]],canonical[membership[d.b]]]
        c.execute('SAVEPOINT validation')
        merge(c,d.a,d.b,'Unione manuale verificata')
        c.execute('ROLLBACK TO validation');c.execute('RELEASE validation')
        suggested=recommend(options)
        suggested.update(email=options[0]['email'] or options[1]['email'],phone=options[0]['phone'] or options[1]['phone'])
        return {'options':options,'recommended':suggested,'members':len(members[membership[d.a]])+len(members[membership[d.b]])}


@app.patch('/api/people/{person_id}')
def edit_person(person_id:int,details:PersonDetails):
    with db(True) as c:
        gid=save_profile(c,person_id,details.model_dump())
    return {'ok':True,'person_id':gid}


@app.get('/api/people/{person_id}/history')
def person_history(person_id:int):
    with db() as c:
        ps,membership,members=groups(c)
        if person_id not in ps:
            raise HTTPException(404,'Persona non trovata')
        ids=set(members[membership[person_id]])
        return [dict(row) for row in c.execute('SELECT * FROM profile_edits ORDER BY id DESC') if row['person_id'] in ids]


@app.get('/api/people/{person_id}')
def profile(person_id:int):
    with db() as c:
        ps,es,membership=people_report(c)
        if person_id not in membership:
            raise HTTPException(404,'Persona non trovata')
        p=next(p for p in ps if p['id']==membership[person_id])
        timeline=[]
        for eid,v in p['event_data'].items():
            status=v['status']
            timeline.append({**es[eid],'status':status,'conflict':v['conflict'],'sources':v['sources'],'amount':v['amount'],'attributed_value':es[eid]['participant_value_cents'] if status=='confirmed' else 0,'records':v['records']})
        sources=[dict(r) for r in c.execute('SELECT r.id,r.person_id,r.original,r.status,r.row_number,i.filename,i.sheet,i.created_at FROM import_rows r JOIN imports i ON i.id=r.import_id') if r['person_id'] in {m['id'] for m in p['members']}]
        return {**public_person(p),'events':sorted(timeline,key=lambda e:e['date'],reverse=True),'sources':sources}


@app.patch('/api/attendance/{attendance_id}')
def change_status(attendance_id:int,s:Status):
    with db(True) as c:
        row=c.execute('SELECT * FROM attendance WHERE id=?',(attendance_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Registrazione non trovata')
        _,membership,members=groups(c)
        before=next(p for p in people_report(c,True)[0] if p['id']==membership[row['person_id']])['event_data'][row['event_id']]['status']
        c.execute('INSERT INTO participation_overrides(event_id,members,status,operator,batch) VALUES(?,?,?,?,?)',(row['event_id'],json.dumps(members[membership[row['person_id']]]),s.status,'Amministratore locale','single:'+secrets.token_urlsafe(10)))
        c.execute('INSERT INTO status_history(attendance_id,old_status,new_status) VALUES(?,?,?)',(attendance_id,before,s.status))
    return {'ok':True}


@app.get('/api/dashboard')
def dashboard():
    with db() as c:
        report=people_report(c)
        es=events_report(c,report)
        ps,_,_=report
    return {'people':len(ps),'events':len(es),'attributed_value':sum(e['attributed_value'] or 0 for e in es),'undefined_events':sum(e['participant_value_cents'] is None for e in es),'actual_spend':sum(e['actual_spend'] for e in es),'cost':sum(e['cost'] for e in es),'attendance':sum(e['participants'] for e in es),'registrations':sum(e['registrations'] for e in es),'unknown':sum(e['unknown'] for e in es),'returning':sum(p['visits']>1 for p in ps),'timeline':es[::-1]}


@app.get('/api/matches')
def matches():
    with db() as c:
        return candidates(c)


@app.get('/api/identity/history')
def history():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT d.*,l.active FROM decisions d LEFT JOIN identity_links l ON l.id=d.link_id ORDER BY d.id DESC')]


@app.post('/api/matches/decision')
def decide(d:Decision):
    if d.a==d.b:
        raise HTTPException(400,'Seleziona due identità differenti')
    with db(True) as c:
        ps,membership,members=groups(c)
        if d.a not in ps or d.b not in ps:
            raise HTTPException(404,'Persona non trovata')
        if d.action=='merge':
            ps0,map0,members0=groups(c)
            canonical=canonical_profiles(c,ps0,map0,members0)
            choices=[canonical[map0[d.a]],canonical[map0[d.b]]]
            recommended=recommend(choices)
            values=d.profile.model_dump() if d.profile else {k:recommended[k] for k in ('first_name','last_name','display_name')}
            if not d.profile:
                values.update(email=choices[0]['email'] or choices[1]['email'],phone=choices[0]['phone'] or choices[1]['phone'])
            link=merge(c,d.a,d.b,'Unione manuale verificata')
            if link is not None:
                save_profile(c,d.a,values,'Nominativo confermato durante unione',link)
        else:
            if membership[d.a]==membership[d.b]:
                raise HTTPException(409,'Prima separa una delle identità dal gruppo')
            for a in members[membership[d.a]]:
                for b in members[membership[d.b]]:
                    keep_separate(c,a,b)
            link=None
    return {'ok':True,'link_id':link}


@app.post('/api/identity/links/{link_id}/undo')
def undo_merge(link_id:int,expected_snapshot:str=''):
    from .importing import snapshot
    with db(True) as c:
        if expected_snapshot and snapshot(c)!=expected_snapshot:raise HTTPException(409,'I dati sono cambiati: rigenera l’anteprima')
        row=c.execute('SELECT * FROM identity_links WHERE id=? AND active=1',(link_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Unione attiva non trovata')
        # Remove this exact decision; later independent decisions are not silently undone.
        c.execute('UPDATE identity_links SET active=0 WHERE id=?',(link_id,))
        c.execute('INSERT INTO decisions(action,a,b,link_id,reason) VALUES(?,?,?,?,?)',('undo',row['a'],row['b'],link_id,'Annullamento unione'))
        _,membership,members=groups(c)
        separated=membership[row['a']]!=membership[row['b']]
        if separated:
            for a in members[membership[row['a']]]:
                for b in members[membership[row['b']]]:
                    keep_separate(c,a,b,'Annullamento: mantenere separati')
    return {'ok':True,'separated':separated}


@app.post('/api/identity/{person_id}/split')
def split(person_id:int):
    with db(True) as c:
        split_member(c,person_id)
    return {'ok':True}


async def read_upload(file):
    data=await file.read(10*1024*1024+1)
    if len(data)>10*1024*1024:
        raise HTTPException(413,'Limite file: 10 MB')
    return data


def parse_upload(filename,data,sheet=None,mapping=None,header_row=None):
    try:
        rows,info=read_sheet(filename,data,sheet,header_row)
        selected=info['mapping'] if mapping is None else mapping
        records=records_from(rows,selected)
        for record in records:record['row']+=info['header_row']-1
        return records,{**info,'mapping':selected}
    except Exception as e:
        raise HTTPException(400,str(e) if isinstance(e,ValueError) else 'File non leggibile o danneggiato')


@app.post('/api/imports/inspect')
async def inspect_import(file:UploadFile=File(...),sheet:str|None=Form(None),header_row:int|None=Form(None)):
    data=await read_upload(file)
    try:
        _,info=read_sheet(file.filename or '',data,sheet,header_row)
        return info
    except Exception as e:
        raise HTTPException(400,str(e) if isinstance(e,ValueError) else 'File non leggibile o danneggiato')


@app.post('/api/imports/preview')
async def preview_import(file:UploadFile=File(...),event_id:int=Form(...),status:Literal['registered','confirmed','absent','cancelled','unknown']=Form('registered'),sheet:str|None=Form(None),mapping:str|None=Form(None),header_row:int|None=Form(None),use_row_status:bool=Form(False)):
    data=await read_upload(file)
    try:
        selected=json.loads(mapping) if mapping is not None else None
        if selected is not None and not isinstance(selected,dict):
            raise ValueError('Mappatura non valida')
    except (ValueError,TypeError):
        raise HTTPException(400,'Mappatura JSON non valida')
    records,info=parse_upload(file.filename or '',data,sheet,selected,header_row)
    config={'event_id':event_id,'status':status,'sheet':info['sheet'],'mapping':info['mapping'],'header_row':info['header_row'],'use_row_status':locals().get('use_row_status',False)}
    with db(True) as c:
        active_event(c,event_id)
        snap=snapshot(c)
        c.execute('SAVEPOINT preview')
        summary=apply_import(c,file.filename or '',data,config,records)
        c.execute('ROLLBACK TO preview')
        c.execute('RELEASE preview')
        token=secrets.token_urlsafe(24)
        c.execute('DELETE FROM import_drafts WHERE created_at<?',(int(time.time())-3600,))
        c.execute('INSERT INTO import_drafts VALUES(?,?,?,?,?,?)',(token,file.filename or '',data,json.dumps(config),snap,int(time.time())))
    return {'token':token,'summary':summary,'config':config,'sample':records[:5],'rows':len(records)}


@app.post('/api/imports/{token}/confirm')
def confirm_import(token:str):
    with db(True) as c:
        draft=c.execute('SELECT * FROM import_drafts WHERE token=?',(token,)).fetchone()
        if not draft or draft['created_at']<int(time.time())-3600:
            raise HTTPException(410,'Anteprima scaduta. Genera una nuova anteprima.')
        config=json.loads(draft['config'])
        active_event(c,config['event_id'])
        if snapshot(c)!=draft['snapshot']:
            raise HTTPException(409,'I dati sono cambiati. Rigenera l’anteprima prima di confermare.')
        records,_=parse_upload(draft['filename'],draft['original'],config['sheet'],config['mapping'],config.get('header_row'))
        summary=apply_import(c,draft['filename'],draft['original'],config,records)
        c.execute('DELETE FROM import_drafts WHERE token=?',(token,))
    return summary


@app.get('/api/imports')
def imports_history():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT id,event_id,filename,sheet,status,created_at FROM imports ORDER BY id DESC')]


@app.get('/api/imports/{import_id}/original')
def original_import(import_id:int):
    with db() as c:
        row=c.execute('SELECT original FROM imports WHERE id=?',(import_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Importazione non trovata')
        return Response(row['original'],media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="import-{import_id}.bin"'})


@app.post('/api/events/{event_id}/import', deprecated=True)
async def import_file(event_id:int,file:UploadFile=File(...),status:Literal['registered','confirmed','absent','cancelled','unknown']=Form('registered')):
    """Compatibility API for scripts. UI always uses preview + explicit confirmation."""
    data=await read_upload(file)
    records,info=parse_upload(file.filename or '',data)
    config={'event_id':event_id,'status':status,'sheet':info['sheet'],'mapping':info['mapping'],'header_row':info['header_row'],'use_row_status':locals().get('use_row_status',False)}
    with db(True) as c:
        active_event(c,event_id)
        summary=apply_import(c,file.filename or '',data,config,records)
    return {**summary,'columns':{k:str(v) for k,v in info['mapping'].items() if v is not None}}
@app.post('/api/demo')
def demo():
    with db(True) as c:
        if c.execute('SELECT COUNT(*) FROM events').fetchone()[0]:
            raise HTTPException(409,'I dati demo si caricano solo in un database senza eventi')
        names=['Giulia Rossi','Marco Bianchi','Sofia Conti','Luca Moretti','Alice Romano','Andrea Ricci','Emma Ferrari','Matteo Costa','Chiara Gallo','Davide Greco','Francesca Bruno','Lorenzo Marino']
        for i,name in enumerate(names):
            c.execute('INSERT INTO people(name,email,phone) VALUES(?,?,?)',(name,f"{name.lower().replace(' ','.')}@example.test",f'3200000{i:03}'))
        ids=[r[0] for r in c.execute('SELECT id FROM people ORDER BY id')]
        for j,(name,day,place,cost) in enumerate([('Creative Connections','2026-05-14','Milano · Spazio Base',42000),('Summer Social Club','2026-06-20','Roma · Terrazza Verde',58000),('Design & People','2026-09-18','Torino · Officine',35000),('Autumn Gathering','2026-10-23','Milano · Spazio Base',62000)]):
            eid=c.execute('INSERT INTO events(name,date,location,cost) VALUES(?,?,?,?)',(name,day,place,cost)).lastrowid
            c.execute('UPDATE events SET participant_value_cents=? WHERE id=?',(2000+j*500,eid))
            for i,pid in enumerate(ids):
                if (i+j)%4!=0:
                    c.execute("INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,?,'confirmed')",(eid,pid,(35+i*8+j*5)*100))
        pid=c.execute('INSERT INTO people(name,email) VALUES(?,?)',('Giulia Rosi','giulia.rossi@example.test')).lastrowid
        c.execute("INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,?,'confirmed')",(eid,pid,6500))
    return {'ok':True}


from .v2api import register as register_v2
register_v2(app,db,lambda:DB,DB_LOCK)
from .v22api import register as register_v22
register_v22(app,db)

DIST=Path(__file__).parent.parent/'frontend'/'dist'
if DIST.exists():
    app.mount('/',StaticFiles(directory=DIST,html=True),name='frontend')
