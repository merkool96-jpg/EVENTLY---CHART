"""Read-only exports: all rows come from the same SQLite read transaction."""
import csv
import io
from datetime import date
from decimal import Decimal
from openpyxl import Workbook
from .reporting import people_report,events_report,matches_filter


def safe_text(value):
    text=str(value or '')
    if text.lstrip(' \t\r\n\ufeff').startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')):
        return "'"+text
    return text


def data_rows(c,q=''):
    report=people_report(c)
    people,events,_=report
    selected=[p for p in people if matches_filter(p,q)]
    people_rows=[];attendance_rows=[];event_ids=set()
    for p in selected:
        confirmed=[events[eid] for eid,v in p['event_data'].items() if v['confirmed']]
        dates=[events[eid]['date'] for eid in p['event_data']]
        people_rows.append([p['id'],p['first_name'],p['last_name'],p['name'],p['email'],p['phone'],p['visits'],p['registrations'],p['unknown'],sum(e['participant_value_cents']==0 for e in confirmed),sum(e['participant_value_cents'] is not None and e['participant_value_cents']>0 for e in confirmed),Decimal(p['value'])/100,p['undefined_values'],date.fromisoformat(min(dates)) if dates else None,date.fromisoformat(max(dates)) if dates else None,'Nominativo incompleto' if p['incomplete'] else ('Nominativo completo, contatti mancanti' if not p['email'] and not p['phone'] else 'Completo'),date.fromisoformat(p['first_seen']) if p['first_seen'] else None,date.fromisoformat(p['last_seen']) if p['last_seen'] else None])
        for eid,v in p['event_data'].items():
            e=events[eid];event_ids.add(eid)
            status='Presenza confermata' if v['confirmed'] else ('Registrazione' if v['registered'] else 'Da verificare')
            value=e['participant_value_cents'] if v['confirmed'] else 0
            attendance_rows.append([p['id'],p['name'],e['name'],date.fromisoformat(e['date']),'Presenza' if v['confirmed'] else 'Iscrizione',status,None if value is None else Decimal(value)/100])
    event_rows=[]
    for e in events_report(c,report):
        if q and e['id'] not in event_ids:
            continue
        # Counts are scoped to the exported people, not the unfiltered archive.
        values=[p['event_data'][e['id']] for p in selected if e['id'] in p['event_data']]
        event_rows.append([e['id'],e['name'],date.fromisoformat(e['date']),sum(v['confirmed'] for v in values),sum(not v['confirmed'] and v['registered'] for v in values),sum(not v['confirmed'] and not v['registered'] for v in values),None if e['participant_value_cents'] is None else Decimal(e['participant_value_cents'])/100])
    return [
        ('Partecipanti',['ID persona','Nome principale','Cognome principale','Nominativo','Email','Telefono','Eventi con presenza confermata','Registrazioni senza presenza','Da verificare','Eventi gratuiti','Eventi con valore positivo','Valore attribuito totale EUR','Valori evento non definiti','Prima partecipazione','Ultima partecipazione','Completezza','Prima presenza','Ultima presenza'],people_rows,{12},{14,15,17,18}),
        ('Partecipazioni',['ID persona','Nominativo','Evento','Data','Tipo','Stato','Valore attribuito EUR'],attendance_rows,{7},{4}),
        ('Eventi',['ID evento','Evento','Data','Partecipanti confermati inclusi','Registrazioni incluse','Da verificare inclusi','Valore attribuito per presenza EUR'],event_rows,{7},{3}),
    ]


def export_file(c,format,q=''):
    tables=data_rows(c,q)
    if format=='csv':
        out=io.StringIO(newline='');writer=csv.writer(out,delimiter=';')
        writer.writerow(tables[0][1])
        for row in tables[0][2]:
            writer.writerow([safe_text(v) if isinstance(v,str) else str(v).replace('.',',') if isinstance(v,Decimal) else v.isoformat() if isinstance(v,date) else '' if v is None else v for v in row])
        return ('\ufeff'+out.getvalue()).encode('utf-8')
    book=Workbook();book.remove(book.active)
    for title,headers,rows,money,dates in tables:
        sheet=book.create_sheet(title);sheet.append(headers);sheet.freeze_panes='A2'
        for row in rows:
            sheet.append([safe_text(v) if isinstance(v,str) else v for v in row])
        sheet.auto_filter.ref=sheet.dimensions
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width=min(42,max(15,len(str(column[0].value))+2))
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                if cell.column in money:cell.number_format='#,##0.00 "€"'
                elif cell.column in dates:cell.number_format='dd/mm/yyyy'
        for cell in sheet[1]:
            from openpyxl.styles import Font,PatternFill
            cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='2F654B')
    out=io.BytesIO();book.save(out);return out.getvalue()
