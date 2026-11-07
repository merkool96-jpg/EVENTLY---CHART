"""Operational V2 endpoints kept separate from the compatible V1.2 API."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import tempfile
import time
from datetime import date
from fastapi import HTTPException,UploadFile,File
from fastapi.responses import Response
from pydantic import BaseModel,Field
from .identity import groups,merge,candidates
from .reporting import people_report,public_person,events_report
from .querying import Filters,select_people
from .operations import preview_bulk,commit_bulk,undo_bulk,analytics
from .participations import STATES
from .migrations import backup_database,migrate

class Bulk(BaseModel):
    event_id:int
    status:str
    ids:list[int]|None=None
    filters:dict=Field(default_factory=dict)
    q:str=''
    operator:str=Field(default='Amministratore locale',min_length=1,max_length=120)

class View(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    filters:dict

class Pair(BaseModel):
    a:int
    b:int

class Impact(BaseModel):
    include:bool
    confirm:bool=False


def register(app,db,get_db_path,lock):
    @app.get('/api/v2/people')
    def people(q:str='',filters:str='{}',sort:str='visits',direction:str='desc',ranked:bool=False,page:int=1,page_size:int=50):
        try:f=Filters(**json.loads(filters))
        except Exception:raise HTTPException(422,'Filtri non validi')
        with db() as c:
            selected=select_people(people_report(c),f,q,sort,direction,ranked)
            total=len(selected)
            if ranked:selected=selected[:50]
            size=min(200,max(1,page_size));offset=(max(1,page)-1)*size
            return {'total':total,'selected':len(selected),'rows':[public_person(p) for p in selected[offset:offset+size]],'top3':[public_person(p) for p in selected[:3]],'page':max(1,page),'page_size':size}

    @app.get('/api/v2/events/{eid}')
    def event_workspace(eid:int,q:str='',status:str=''):
        with db() as c:
            report=people_report(c,True)
            es=events_report(c,report)
            event=next((e for e in es if e['id']==eid),None)
            if not event:raise HTTPException(404,'Evento non trovato')
            people=[{**public_person(p),'participation':p['event_data'][eid]} for p in select_people(report,q=q) if eid in p['event_data'] and (not status or p['event_data'][eid]['status']==status)]
            imports=[dict(r) for r in c.execute('SELECT id,filename,status,created_at FROM imports WHERE event_id=? ORDER BY id DESC',(eid,))]
            all_analytics=analytics(c)
            analysis=next((e for e in all_analytics['events'] if e['id']==eid),{})
            return {'event':event,'rows':people,'total':len(people),'imports':imports,'analysis':analysis,'editions':[e for e in es if e['id']!=eid and e['name'].casefold()==event['name'].casefold()]}

    @app.post('/api/v2/events/{eid}/analytics-impact')
    def impact(eid:int,body:Impact):
        with db(True) as c:
            event=c.execute('SELECT * FROM events WHERE id=?',(eid,)).fetchone()
            if not event:raise HTTPException(404,'Evento non trovato')
            before=people_report(c)
            c.execute('SAVEPOINT impact')
            c.execute('UPDATE events SET include_analytics=? WHERE id=?',(int(body.include),eid))
            after=people_report(c)
            result={'presences_before':sum(p['visits'] for p in before[0]),'presences_after':sum(p['visits'] for p in after[0]),'value_before':sum(p['value'] for p in before[0]),'value_after':sum(p['value'] for p in after[0])}
            if not body.confirm:c.execute('ROLLBACK TO impact')
            c.execute('RELEASE impact')
            return result

    @app.post('/api/v2/bulk/preview')
    def bulk_preview(body:Bulk):
        if body.status not in STATES:raise HTTPException(422,'Stato non valido')
        Filters(**body.filters)
        with db(True) as c:return preview_bulk(c,body.event_id,body.status,body.ids,body.filters,body.q,body.operator)

    @app.post('/api/v2/bulk/{token}/confirm')
    def bulk_confirm(token:str):
        with db(True) as c:return commit_bulk(c,token)

    @app.post('/api/v2/bulk/{token}/undo')
    def bulk_undo(token:str):
        with db(True) as c:return undo_bulk(c,token)

    @app.get('/api/v2/bulk/history')
    def bulk_history():
        with db() as c:return [dict(r) for r in c.execute('SELECT * FROM bulk_operations WHERE committed=1 ORDER BY created_at DESC LIMIT 100')]

    @app.get('/api/v2/analytics')
    def community(filters:str='{}',window:int=90):
        try:f=Filters(**json.loads(filters)).model_dump()
        except Exception:raise HTTPException(422,'Filtri non validi')
        with db() as c:return analytics(c,f,min(365,max(1,window)))

    @app.get('/api/v2/quality')
    def quality(kind:str=''):
        with db() as c:
            report=people_report(c,True);ps=report[0]
            categories={'incomplete':[public_person(p) for p in ps if p['incomplete']],'no_email':[public_person(p) for p in ps if not p['email']],'no_contacts':[public_person(p) for p in ps if not p['email'] and not p['phone']],
                'unassigned':[dict(r) for r in c.execute('SELECT * FROM import_issues WHERE resolved=0')],
                'duplicates':[dict(r) for r in c.execute('SELECT import_id,person_id,COUNT(*) count FROM import_rows GROUP BY import_id,person_id HAVING COUNT(*)>1')],
                'undefined_values':[dict(r) for r in c.execute('SELECT * FROM events WHERE participant_value_cents IS NULL')],
                'import_errors':[dict(r) for r in c.execute('SELECT * FROM import_issues WHERE resolved=0')],
                'ambiguous':candidates(c),'conflicts':[public_person(p) for p in ps if p['conflicts']]}
            return {'counts':{k:len(v) for k,v in categories.items()},'rows':categories.get(kind,[]),'kind':kind}

    @app.post('/api/v2/issues/{issue_id}/resolve')
    def resolve_issue(issue_id:int,person_id:int):
        with db(True) as c:
            issue=c.execute('SELECT * FROM import_issues WHERE id=? AND resolved=0',(issue_id,)).fetchone()
            if not issue or not c.execute('SELECT 1 FROM people WHERE id=?',(person_id,)).fetchone():raise HTTPException(404,'Riga o persona non trovata')
            source=c.execute('SELECT * FROM imports WHERE id=?',(issue['import_id'],)).fetchone()
            aid=c.execute('INSERT OR IGNORE INTO attendance(event_id,person_id,status) VALUES(?,?,?)',(source['event_id'],person_id,source['status']))
            row=c.execute('SELECT id FROM attendance WHERE event_id=? AND person_id=?',(source['event_id'],person_id)).fetchone()
            c.execute('INSERT INTO attendance_evidence(attendance_id,status,source) VALUES(?,?,?)',(row['id'],source['status'],f'issue:{issue_id}:admin'))
            c.execute('UPDATE import_issues SET resolved=1,person_id=? WHERE id=?',(person_id,issue_id))
            c.execute('INSERT INTO decisions(action,a,reason) VALUES(?,?,?)',('resolve_issue',person_id,f'Riga non attribuita #{issue_id} assegnata esplicitamente'))
            return {'ok':True}

    @app.get('/api/v2/views')
    def views():
        with db() as c:return [dict(r) for r in c.execute('SELECT * FROM saved_views ORDER BY id DESC')]

    @app.post('/api/v2/views')
    def save_view(body:View):
        filters=Filters(**body.filters).model_dump()
        with db(True) as c:return {'id':c.execute('INSERT INTO saved_views(name,filters) VALUES(?,?)',(body.name,json.dumps(filters))).lastrowid}

    @app.get('/api/v2/mapping-templates')
    def templates():
        with db() as c:return [dict(r) for r in c.execute('SELECT * FROM mapping_templates ORDER BY id DESC')]

    @app.post('/api/v2/mapping-templates')
    def template_save(body:dict):
        from .importing import ALIASES
        mapping=body.get('mapping',{})
        if not isinstance(mapping,dict) or set(mapping)-set(ALIASES):raise HTTPException(422,'Mappatura non valida')
        with db(True) as c:return {'id':c.execute('INSERT INTO mapping_templates(name,headers,mapping,header_row) VALUES(?,?,?,?)',(str(body.get('name','Formato salvato'))[:100],json.dumps(body.get('headers',[])),json.dumps(mapping),int(body.get('header_row',1)))).lastrowid}

    @app.get('/api/v2/identity')
    def review(deferred:bool=False):
        from .profiles import canonical_profiles
        with db() as c:
            ps,membership,members=groups(c);profiles=canonical_profiles(c,ps,membership,members)
            report=people_report(c,True);reports={p['id']:p for p in report[0]}
            rows=candidates(c,deferred=deferred)
            for row in rows:
                a,b=row['a']['id'],row['b']['id'];ga,gb=membership[a],membership[b]
                row['original_a']=row['a'];row['original_b']=row['b'];row['a']={**ps[ga],**profiles[ga]};row['b']={**ps[gb],**profiles[gb]}
                row['members_a']=[ps[i] for i in members[ga]];row['members_b']=[ps[i] for i in members[gb]]
                row['events_a']=[report[1][eid]['name'] for eid in reports[ga]['event_data']];row['events_b']=[report[1][eid]['name'] for eid in reports[gb]['event_data']]
                row['can_merge']=True;row['conflict']=''
                c.execute('SAVEPOINT preflight')
                try:merge(c,ga,gb,'Unione manuale verificata')
                except HTTPException as error:row['can_merge']=False;row['conflict']=error.detail
                finally:c.execute('ROLLBACK TO preflight');c.execute('RELEASE preflight')
                overlaps=set(reports[ga]['event_data']) & set(reports[gb]['event_data'])
                row['impact']={'people_change':-1,'overlapping_events':len(overlaps),'message':'Le presenze sullo stesso evento saranno consolidate una sola volta; eventuali stati contrari diventeranno conflitti.'}
            return rows

    @app.post('/api/v2/identity/defer')
    def defer(body:Pair):
        with db(True) as c:
            a,b=sorted((body.a,body.b))
            c.execute('INSERT OR IGNORE INTO deferred_pairs VALUES(?,?)',(a,b));c.execute('INSERT INTO decisions(action,a,b,reason) VALUES(?,?,?,?)',('defer',a,b,'Decidi più tardi'))
            return {'ok':True}

    @app.post('/api/v2/identity/resume')
    def resume(body:Pair):
        with db(True) as c:
            ps,mapping,members=groups(c)
            for r in c.execute('SELECT * FROM deferred_pairs').fetchall():
                if {mapping[r['a']],mapping[r['b']]}=={mapping[body.a],mapping[body.b]}:c.execute('DELETE FROM deferred_pairs WHERE a=? AND b=?',(r['a'],r['b']))
            return {'ok':True}

    @app.get('/api/v2/separations')
    def separations():
        with db() as c:return [dict(r) for r in c.execute('SELECT s.*,p.name name_a,q.name name_b FROM separate s JOIN people p ON p.id=s.a JOIN people q ON q.id=s.b')]

    @app.post('/api/v2/separations/revoke')
    def revoke(body:Pair):
        with db(True) as c:
            a,b=sorted((body.a,body.b))
            if not c.execute('DELETE FROM separate WHERE a=? AND b=?',(a,b)).rowcount:raise HTTPException(404,'Blocco non trovato')
            c.execute('INSERT INTO decisions(action,a,b,reason) VALUES(?,?,?,?)',('revoke_separation',a,b,'Revoca amministrativa esplicita: nessuna unione automatica'))
            return {'ok':True}

    @app.get('/api/v2/backups')
    def backups():
        folder=Path(get_db_path()).parent/'backups'
        return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(folder.glob('*.db'),reverse=True)]

    @app.get('/api/v2/backups/{name}')
    def download_backup(name:str):
        if Path(name).name!=name:raise HTTPException(400,'Nome non valido')
        path=Path(get_db_path()).parent/'backups'/name
        if not path.is_file():raise HTTPException(404,'Backup non trovato')
        return Response(path.read_bytes(),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{name}"'})

    @app.post('/api/v2/restore/preview')
    async def restore_preview(file:UploadFile=File(...)):
        content=await file.read(32*1024*1024+1)
        if len(content)>32*1024*1024:raise HTTPException(413,'Per il ripristino UI il limite è 32 MB')
        folder=Path(tempfile.mkdtemp(prefix='evently-restore-'));path=folder/'candidate.db';path.write_bytes(content);path.chmod(0o600)
        try:
            with sqlite3.connect(path) as c:
                if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA user_version').fetchone()[0]>4:raise ValueError()
                for table in ('people','events','attendance'):c.execute(f'SELECT COUNT(*) FROM {table}')
            migrate(path)
            with sqlite3.connect(path) as c:
                if c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError()
                counts={table:c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('people','events','attendance','imports','decisions')}
        except Exception:
            shutil.rmtree(folder);raise HTTPException(400,'Backup non valido o incompatibile. Il database corrente non è stato modificato.')
        token=secrets.token_urlsafe(20);sha=hashlib.sha256(path.read_bytes()).hexdigest()
        with db(True) as c:c.execute('INSERT INTO restore_drafts VALUES(?,?,?,?)',(token,str(path),sha,int(time.time())))
        return {'token':token,'counts':counts,'message':'Copia temporanea verificata. Confermare sostituirà il database corrente dopo averlo salvato.'}

    @app.post('/api/v2/restore/{token}/confirm')
    def restore_confirm(token:str):
        with lock:
            with db() as c:row=c.execute('SELECT * FROM restore_drafts WHERE token=?',(token,)).fetchone()
            if not row or int(time.time())-row['created_at']>3600:raise HTTPException(410,'Verifica ripristino scaduta')
            path=Path(row['path'])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha']:raise HTTPException(409,'La copia verificata è cambiata')
            current=backup_database(get_db_path())
            try:
                with sqlite3.connect(path) as source,sqlite3.connect(get_db_path()) as dest:source.backup(dest)
            except Exception:
                with sqlite3.connect(current) as source,sqlite3.connect(get_db_path()) as dest:source.backup(dest)
                raise HTTPException(500,'Ripristino interrotto. Database precedente recuperato.')
            shutil.rmtree(path.parent)
            return {'ok':True,'previous_backup':current.name}
