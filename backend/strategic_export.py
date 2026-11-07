"""Explicit fields, private notes opt-in, full filtered selection, formula safe."""
import csv,io
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill
from .reporting import people_report
from .querying import select_people
from .exporting import safe_text
from .crm import states

COLUMNS={'id':'ID persona','name':'Nominativo','email':'Email','visits':'Presenze confermate','first_seen':'Prima presenza','last_seen':'Ultima presenza','value':'Valore attribuito EUR','vip':'VIP manuale','tags':'Tag','rewards':'Riconoscimenti','notes':'Note riservate'}
DEFAULT=['id','name','email','visits','first_seen','last_seen','value','vip','tags']

def columns(body):
    keys=body.get('columns',DEFAULT)
    if not isinstance(keys,list) or not keys or set(keys)-set(COLUMNS):raise HTTPException(422,'Campi export non validi')
    if 'notes' in keys and body.get('include_notes') is not True:raise HTTPException(422,'Conferma esplicitamente l’esportazione delle note riservate')
    return [(k,COLUMNS[k]) for k in dict.fromkeys(keys)]


def selection(c,body):
    selected=select_people(people_report(c),body.get('filters'),body.get('q',''))
    if body.get('ids') is not None:selected=[p for p in selected if p['id'] in set(body['ids'])]
    if body.get('exclude_ids'):
        excluded=set(body['exclude_ids']);selected=[p for p in selected if p['id'] not in excluded]
    return selected


def export(c,body):
    chosen=columns(body);people=selection(c,body);format=body.get('format','xlsx')
    if format not in ('xlsx','csv'):raise HTTPException(422,'Formato lista non valido')
    _,_,membership=people_report(c);visible,_=states(c,membership)
    rows=[]
    for p in people:
        row=[]
        for key,_ in chosen:
            value=p.get(key,'')
            if key=='vip':value='Sì' if p.get('vip') else 'No'
            if key=='tags':value='; '.join(t['name'] for t in p.get('tags',[]))
            if key=='rewards':value='; '.join(f"{r['data']['name']} ({r['data']['status']}, {r['data']['date']})" for r in visible.get(p['id'],[]) if r['kind']=='reward')
            if key=='notes':value='\n'.join(r['data']['text'] for r in visible.get(p['id'],[]) if r['kind']=='note')
            if key=='value':value=Decimal(p['value'])/100
            if key in ('first_seen','last_seen') and value:value=date.fromisoformat(value)
            if isinstance(value,str):value=safe_text(value)
            row.append(value)
        rows.append(row)
    headers=[label for key,label in chosen]
    if format=='csv':
        out=io.StringIO(newline='');writer=csv.writer(out,delimiter=';');writer.writerow(headers)
        writer.writerows([str(v).replace('.',',') if isinstance(v,Decimal) else v.strftime('%d/%m/%Y') if isinstance(v,date) else '' if v is None else v for v in row] for row in rows)
        return ('\ufeff'+out.getvalue()).encode('utf-8'),'csv'
    book=Workbook();sheet=book.active;sheet.title='Lista strategica';sheet.append(headers)
    for row in rows:sheet.append(row)
    for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='2F654B')
    sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
    for i,(key,label) in enumerate(chosen,1):
        sheet.column_dimensions[sheet.cell(1,i).column_letter].width=28
        if key in ('value','first_seen','last_seen'):
            for row in sheet.iter_rows(min_row=2):row[i-1].number_format='#,##0.00 "€"' if key=='value' else 'dd/mm/yyyy'
    out=io.BytesIO();book.save(out);return out.getvalue(),'xlsx'
