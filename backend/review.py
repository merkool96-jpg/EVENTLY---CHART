"""Explain existing merge guards and preview audited correction; no forced merge."""
from fastapi import HTTPException
from .identity import groups,merge,conflicts,compatible_names,same_email,same_phone,parts,confirmed_name_aliases
from .reporting import people_report
from .importing import snapshot


def diagnose(c,a,b,details=True):
    ps,membership,members=groups(c)
    if a not in ps or b not in ps:raise HTTPException(404,'Profilo non trovato')
    ga,gb=membership[a],membership[b]
    if ga==gb:raise HTTPException(409,'Le identità sono già nello stesso gruppo')
    can_merge=True;reason='';after=None
    c.execute('SAVEPOINT explanation')
    try:
        merge(c,ga,gb,'Unione manuale verificata')
        if details:after=people_report(c)
    except HTTPException as e:can_merge=False;reason=e.detail
    finally:c.execute('ROLLBACK TO explanation');c.execute('RELEASE explanation')
    if not details:return {'can_merge':can_merge,'reason':reason}
    impact=None
    if after is not None:
        before=people_report(c)
        impact={'people_before':len(before[0]),'people_after':len(after[0]),'presences_before':sum(p['visits'] for p in before[0]),'presences_after':sum(p['visits'] for p in after[0]),'value_before':sum(p['value'] for p in before[0]),'value_after':sum(p['value'] for p in after[0])}
    rules=[]
    for x,y in conflicts(c,members[ga],members[gb]):
        rules.append({'rule':'separazione_precedente','a':x,'b':y,'blocking':not can_merge,'message':'Separazione precedente: richiede revoca esplicita, che non unisce i profili.'})
    aliases=confirmed_name_aliases(c,set(members[ga]))|confirmed_name_aliases(c,set(members[gb]))
    for x in members[ga]:
        for y in members[gb]:
            left,right=ps[x],ps[y]
            if not compatible_names(left,right):
                strong=same_email(left,right) or same_phone(left,right)
                rules.append({'rule':'email_potenzialmente_condivisa' if same_email(left,right) else 'identita_incompatibili','a':x,'b':y,'blocking':not strong and frozenset((parts(left),parts(right))) not in aliases,'message':'Nomi incompatibili: il contatto coincidente può essere condiviso. Controllare tutti i membri del gruppo.' if strong else 'Nomi incompatibili senza identificativo forte coincidente o variante confermata.'})
    ids=set(members[ga]+members[gb])
    links=[dict(r) for r in c.execute('SELECT l.*,p.name name_a,q.name name_b FROM identity_links l JOIN people p ON p.id=l.a JOIN people q ON q.id=l.b WHERE l.active=1 ORDER BY l.id') if r['a'] in ids and r['b'] in ids]
    sources=[dict(r) for r in c.execute('SELECT r.id,r.person_id,r.row_number,r.original,i.id import_id,i.filename,e.name event_name FROM import_rows r JOIN imports i ON i.id=r.import_id JOIN events e ON e.id=i.event_id ORDER BY r.id') if r['person_id'] in ids]
    return {'impact':impact,'a':ga,'b':gb,'can_merge':can_merge,'reason':reason,'rules':rules,'members_a':[ps[i] for i in members[ga]],'members_b':[ps[i] for i in members[gb]],'links':links,'sources':sources}


def undo_preview(c,link_id):
    link=c.execute('SELECT * FROM identity_links WHERE id=? AND active=1',(link_id,)).fetchone()
    if not link:raise HTTPException(404,'Collegamento attivo non trovato')
    before=people_report(c)
    c.execute('SAVEPOINT undo_impact')
    c.execute('UPDATE identity_links SET active=0 WHERE id=?',(link_id,))
    after=people_report(c)
    c.execute('ROLLBACK TO undo_impact');c.execute('RELEASE undo_impact')
    def totals(report):return {'people':len(report[0]),'presences':sum(p['visits'] for p in report[0]),'value':sum(p['value'] for p in report[0])}
    return {'link_id':link_id,'before':totals(before),'after':totals(after),'snapshot':snapshot(c),'message':'Annulla solo questo collegamento; originali invariati. Se i gruppi si separano verrà creato un blocco, revocabile esplicitamente. Nessuna fusione automatica.'}
