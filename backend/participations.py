"""Single source of consolidated states, shared by UI, ranking and exports."""
import json
STATES=('registered','confirmed','absent','cancelled','unknown')
LABELS={'registered':'Iscritto','confirmed':'Presente confermato','absent':'Assente confermato','cancelled':'Annullato','unknown':'Da verificare'}


def load_evidence(c):
    result={}
    for r in c.execute('SELECT attendance_id,status FROM attendance_evidence'):
        result.setdefault(r['attendance_id'],set()).add(r['status'])
    return result


def consolidate(c,event_id,member_ids,records,evidence,overrides):
    sources=set()
    for row in records:sources.update(evidence.get(row['id'],{row['status']}))
    # After group changes an override still concerns the original members it names.
    relevant=[r for r in overrides if r['event_id']==event_id and set(json.loads(r['members'])) & set(member_ids)]
    administrative={r['status'] for r in relevant if r['active']}
    if relevant:
        latest={}
        for row in relevant:
            if row['active']:
                for pid in set(json.loads(row['members'])) & set(member_ids):latest[pid]=row['status']
        administrative=set(latest.values())
    values=administrative or sources
    conflict=('confirmed' in values and bool(values & {'absent','cancelled'})) or ('absent' in values and 'cancelled' in values)
    status='unknown' if conflict else next((s for s in ('confirmed','absent','cancelled','registered','unknown') if s in values),'unknown')
    return status,conflict,sorted(sources),bool(administrative)
