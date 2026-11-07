"""Paginated quality read model: only selected rows cross the API boundary."""
from fastapi import HTTPException
from .reporting import people_report,public_person
from .identity import candidates


def quality_page(c,kind='incomplete',q='',page=1,page_size=50):
    people=people_report(c,True)[0]
    categories={
        'incomplete':[p for p in people if p['incomplete']],
        'no_email':[p for p in people if not p['email']],
        'no_contacts':[p for p in people if not p['email'] and not p['phone']],
        'conflicts':[p for p in people if p['conflicts']],
        'unassigned':[dict(r) for r in c.execute('SELECT * FROM import_issues WHERE resolved=0 ORDER BY id')],
        'duplicates':[dict(r) for r in c.execute('SELECT import_id,person_id,COUNT(*) count FROM import_rows GROUP BY import_id,person_id HAVING COUNT(*)>1 ORDER BY import_id,person_id')],
        'undefined_values':[dict(r) for r in c.execute('SELECT * FROM events WHERE participant_value_cents IS NULL ORDER BY date,id')],
        'ambiguous':candidates(c,limit=None),
    }
    categories['import_errors']=categories['unassigned']
    if not kind:kind='incomplete'
    if kind not in categories:raise HTTPException(422,'Categoria qualità non valida')
    query=q.casefold().strip()
    rows=[r for r in categories[kind] if not query or query in ' '.join(str(r.get(k,'')) for k in ('name','email','phone','reason','original','person_id','import_id')) .casefold() or query in str(r.get('a',{}).get('name','')).casefold()]
    size=min(200,max(1,page_size));page=max(1,page);total=len(rows)
    rows=rows[(page-1)*size:page*size]
    if kind in ('incomplete','no_email','no_contacts','conflicts'):rows=[public_person(r) for r in rows]
    return {'counts':{k:len(v) for k,v in categories.items()},'rows':rows,'kind':kind,'total':total,'page':page,'page_size':size,'pages':max(1,(total+size-1)//size)}
