"""Manual CRM, resolved through stable ORIGINAL IDs; never copied on merge/split."""
import hashlib,json,re,secrets,time
from fastapi import HTTPException
from .identity import groups,norm


def normalized(value):return ' '.join(norm(value).split())
def dumps(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)


def states(c,membership):
    resolved={};unresolved=[]
    for raw in c.execute('SELECT * FROM crm_records WHERE active=1 ORDER BY id'):
        row=dict(raw);scope=json.loads(row['scope']);roots={membership.get(i) for i in scope}
        row['data']=json.loads(row['payload']);row['origins']=scope
        if len(roots)==1 and None not in roots:resolved.setdefault(next(iter(roots)),[]).append(row)
        else:row['possible_owners']=sorted(r for r in roots if r is not None);unresolved.append(row)
    return resolved,unresolved


def decorate(c,people,membership,events):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='crm_records'").fetchone():return
    records,unresolved=states(c,membership)
    from .community import settings
    config=settings(c)
    tags={r['id']:dict(r) for r in c.execute('SELECT * FROM crm_tags')}
    for p in people:
        rows=records.get(p['id'],[])
        p['_community_settings']=config
        p['_reward_info']=[{'id':r['id'],'campaign_id':r['campaign_id'],**r['data']} for r in rows if r['kind']=='reward']
        p['vip']=any(r['kind']=='vip' and r['data'].get('enabled') for r in rows)
        p['tags']=[tags[i] for i in sorted({r['tag_id'] for r in rows if r['kind']=='tag'}) if i in tags]
        p['reward_candidates']=[r['id'] for r in rows if r['kind']=='reward' and r['data']['status']=='proposed']
        p['crm_unresolved']=sum(p['id'] in r['possible_owners'] for r in unresolved)


def log(c,action,before,after,operator='Amministratore locale',batch=None,reason=''):
    record_id=(after or before or {}).get('id')
    c.execute('INSERT INTO crm_audit(action,operator,record_id,batch,before_data,after_data,reason) VALUES(?,?,?,?,?,?,?)',(action,operator,record_id,batch,dumps(before) if before else None,dumps(after) if after else None,reason))


def insert(c,kind,scope,data,operator='Amministratore locale',tag_id=None,campaign_id=None,event_id=None,batch=None,reason=''):
    pid=c.execute('INSERT INTO crm_records(kind,scope,payload,tag_id,campaign_id,event_id,author) VALUES(?,?,?,?,?,?,?)',(kind,dumps(sorted(scope)),dumps(data),tag_id,campaign_id,event_id,operator)).lastrowid
    after=dict(c.execute('SELECT * FROM crm_records WHERE id=?',(pid,)).fetchone());log(c,'create',None,after,operator,batch,reason);return pid


def change(c,row,operator='Amministratore locale',batch=None,reason='',**fields):
    before={k:v for k,v in row.items() if k not in ('data','origins','possible_owners')}
    allowed={'active','payload','scope'}
    if not fields or set(fields)-allowed:raise HTTPException(422,'Modifica CRM non valida')
    c.execute('UPDATE crm_records SET '+','.join(k+'=?' for k in fields)+',revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?',(*fields.values(),row['id']))
    after=dict(c.execute('SELECT * FROM crm_records WHERE id=?',(row['id'],)).fetchone());log(c,'update',before,after,operator,batch,reason)


def snapshot(c):
    from .importing import snapshot as original
    return original(c)


def profile(c,pid,history_page=1):
    ps,mapping,members=groups(c)
    if pid not in mapping:raise HTTPException(404,'Persona non trovata')
    rows,unresolved=states(c,mapping);gid=mapping[pid];records=rows.get(gid,[])
    campaigns={r['id']:r['name'] for r in c.execute('SELECT id,name FROM crm_campaigns')};events={r['id']:r['name'] for r in c.execute('SELECT id,name FROM events')}
    rewards=[r for r in records if r['kind']=='reward'];dups={}
    for r in rewards:r['campaign_name']=campaigns.get(r['campaign_id'],'Nessuna iniziativa');r['event_name']=events.get(r['event_id'],'')
    for r in rewards:
        key=(r['campaign_id'],normalized(r['data']['type']));dups[key]=dups.get(key,0)+1
    for r in rewards:r['potential_duplicate']=dups[(r['campaign_id'],normalized(r['data']['type']))]>1
    owned_ids={r['id'] for r in c.execute('SELECT id,scope FROM crm_records') if {mapping.get(i) for i in json.loads(r['scope'])}=={gid}}
    history=[dict(r) for r in c.execute('SELECT * FROM crm_audit ORDER BY id DESC') if r['record_id'] in owned_ids]
    tag_ids={r['tag_id'] for r in records if r['kind']=='tag'}
    tags=[dict(r) for r in c.execute('SELECT * FROM crm_tags') if r['id'] in tag_ids]
    return {'tags':tags,'id':gid,'members':members[gid],'vip':any(r['kind']=='vip' and r['data'].get('enabled') for r in records),'records':records,'unresolved':[r for r in unresolved if gid in r['possible_owners']],'history':history[(max(1,history_page)-1)*50:max(1,history_page)*50],'history_total':len(history),'history_page':max(1,history_page)}


def validate_reward(c,data):
    from datetime import date
    if not str(data.get('name','')).strip() or not str(data.get('type','')).strip():raise HTTPException(422,'Indica nome e tipo del riconoscimento')
    if data.get('status') not in ('proposed','assigned'):raise HTTPException(422,'Scegli proposto o assegnato')
    try:date.fromisoformat(data.get('date',''))
    except Exception:raise HTTPException(422,'Data del riconoscimento non valida')
    if data.get('campaign_id') is not None and not c.execute('SELECT 1 FROM crm_campaigns WHERE id=? AND archived=0',(data['campaign_id'],)).fetchone():raise HTTPException(422,'Iniziativa non disponibile')
    if data.get('event_id') is not None and not c.execute('SELECT 1 FROM events WHERE id=?',(data['event_id'],)).fetchone():raise HTTPException(422,'Evento non trovato')


def preview(c,body):
    from .reporting import people_report
    from .querying import select_people
    action=body.get('action');data=body.get('data',{});operator=str(body.get('operator') or 'Amministratore locale')[:120]
    if not isinstance(data,dict) or any(body.get(key) is not None and (not isinstance(body[key],list) or any(type(i) is not int or i<1 for i in body[key])) for key in ('ids','exclude_ids')):raise HTTPException(422,'Selezione CRM non valida')
    if action not in ('vip_add','vip_remove','tag_add','tag_remove','reward'):raise HTTPException(422,'Azione CRM non valida')
    selected=select_people(people_report(c),body.get('filters'),body.get('q',''))
    if body.get('ids') is not None:selected=[p for p in selected if p['id'] in set(body['ids'])]
    if body.get('exclude_ids'):
        excluded=set(body['exclude_ids']);selected=[p for p in selected if p['id'] not in excluded]
    if action.startswith('tag_'):
        if not isinstance(data.get('tag_ids'),list) or any(type(i) is not int for i in data['tag_ids']):raise HTTPException(422,'Selezione tag non valida')
        tag_ids=set(data.get('tag_ids',[]))
        if not tag_ids:raise HTTPException(422,'Seleziona almeno un tag')
        for tid in tag_ids:
            if not c.execute('SELECT 1 FROM crm_tags WHERE id=? AND (?=1 OR archived=0)',(tid,action=='tag_remove')).fetchone():raise HTTPException(422,'Tag non disponibile')
    if action=='reward':validate_reward(c,data)
    ps,mapping,members=groups(c);visible,_=states(c,mapping);changed=[];duplicates=[]
    for p in selected:
        rows=visible.get(p['id'],[])
        if action=='reward':
            existing_rewards=[r for r in rows if r['kind']=='reward' and r['campaign_id']==data.get('campaign_id') and normalized(r['data']['type'])==normalized(data['type'])]
            duplicate=bool(existing_rewards)
            if duplicate:duplicates.append({'id':p['id'],'name':p['name'],'statuses':sorted({r['data']['status'] for r in existing_rewards})})
            if duplicate and not data.get('allow_duplicate'):continue
        elif action.startswith('vip_'):
            if p.get('vip',False)==(action=='vip_add'):continue
        else:
            existing={r['tag_id'] for r in rows if r['kind']=='tag'}
            if action=='tag_add' and not(set(data['tag_ids'])-existing):continue
            if action=='tag_remove' and not(set(data['tag_ids'])&existing):continue
        changed.append({'id':p['id'],'name':p['name'] or p['email'],'members':members[p['id']]})
    if action=='reward' and duplicates and data.get('allow_duplicate') and len(str(data.get('exception_reason','')).strip())<5:raise HTTPException(422,'Per ripetere un riconoscimento indica una motivazione esplicita di almeno 5 caratteri')
    token=secrets.token_urlsafe(20);config={'action':action,'data':data,'operator':operator,'changes':changed}
    c.execute('INSERT INTO crm_batches VALUES(?,?,?,?,0,0,?)',(token,dumps(config),dumps([p['id'] for p in selected]),snapshot(c),int(time.time())))
    return {'token':token,'selected':len(selected),'changed':len(changed),'unchanged_or_excluded':len(selected)-len(changed),'duplicates':duplicates,'changes':changed,'message':'Anteprima soltanto. Nessuno stato VIP, tag o premio è stato assegnato.'}


def commit(c,token):
    row=c.execute('SELECT * FROM crm_batches WHERE token=?',(token,)).fetchone()
    if not row or int(time.time())-row['created_at']>3600:raise HTTPException(410,'Anteprima CRM scaduta')
    if row['committed'] or row['snapshot']!=snapshot(c):raise HTTPException(409,'Dati cambiati o operazione già confermata: rigenera l’anteprima')
    config=json.loads(row['config']);action=config['action'];data=config['data'];operator=config['operator'];ps,mapping,members=groups(c);visible,_=states(c,mapping)
    for p in config['changes']:
        rows=visible.get(p['id'],[]);scope=p['members']
        if action=='vip_add':insert(c,'vip',scope,{'enabled':True},operator,batch=token)
        elif action=='vip_remove':
            for r in rows:
                if r['kind']=='vip':change(c,r,operator,token,active=0)
        elif action=='tag_add':
            existing={r['tag_id'] for r in rows if r['kind']=='tag'}
            for tid in set(data['tag_ids'])-existing:insert(c,'tag',scope,{},operator,tag_id=tid,batch=token)
        elif action=='tag_remove':
            for r in rows:
                if r['kind']=='tag' and r['tag_id'] in data['tag_ids']:change(c,r,operator,token,active=0)
        else:
            payload={k:data.get(k,'') for k in ('name','type','date','status','note','exception_reason')}
            insert(c,'reward',scope,payload,operator,campaign_id=data.get('campaign_id'),event_id=data.get('event_id'),batch=token,reason=data.get('exception_reason',''))
    c.execute('UPDATE crm_batches SET committed=1 WHERE token=?',(token,));return {'ok':True,'changed':len(config['changes']),'token':token}


def undo(c,token):
    row=c.execute('SELECT * FROM crm_batches WHERE token=? AND committed=1 AND undone=0',(token,)).fetchone()
    if not row:raise HTTPException(409,'Operazione CRM non annullabile')
    config=json.loads(row['config']);ps,mapping,members=groups(c)
    for p in config['changes']:
        if any(set(members[mapping[i]])!=set(p['members']) for i in p['members']):raise HTTPException(409,'I gruppi identità sono cambiati: controlla prima la proprietà dei dati CRM')
    own_order=c.execute('SELECT rowid FROM crm_batches WHERE token=?',(token,)).fetchone()[0]
    own_members={i for p in config['changes'] for i in p['members']}
    for later in c.execute('SELECT config FROM crm_batches WHERE rowid>? AND committed=1 AND undone=0',(own_order,)):
        other=json.loads(later['config']);overlap=own_members & {i for p in other['changes'] for i in p['members']}
        same_vip=config['action'].startswith('vip_') and other['action'].startswith('vip_')
        same_tags=config['action'].startswith('tag_') and other['action'].startswith('tag_') and bool(set(config['data']['tag_ids']) & set(other['data']['tag_ids']))
        if overlap and (same_vip or same_tags):raise HTTPException(409,'Esistono operazioni successive sugli stessi VIP o tag: annullamento non sicuro')
    logs=c.execute('SELECT * FROM crm_audit WHERE batch=? ORDER BY id DESC',(token,)).fetchall()
    for logrow in logs:
        after=json.loads(logrow['after_data']);current=c.execute('SELECT * FROM crm_records WHERE id=?',(logrow['record_id'],)).fetchone()
        if not current or dict(current)!=after:raise HTTPException(409,'Esistono modifiche successive: annullamento interrotto')
    for logrow in logs:
        current=dict(c.execute('SELECT * FROM crm_records WHERE id=?',(logrow['record_id'],)).fetchone());before=json.loads(logrow['before_data']) if logrow['before_data'] else None
        fields={'active':0} if before is None else {k:before[k] for k in ('active','payload','scope')}
        change(c,current,reason='Annullamento batch '+token,**fields)
    c.execute('UPDATE crm_batches SET undone=1 WHERE token=?',(token,));return {'ok':True,'restored':len(logs)}
