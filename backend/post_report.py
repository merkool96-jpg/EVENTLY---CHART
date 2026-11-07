"""Local PDF/XLSX post-event reports, built from a single read transaction snapshot."""
import io,json,hashlib
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill
from .performance import event_performance,compare
from .reporting import people_report,public_person
from .community import segments
from .exporting import safe_text


def model(c,eid):
    report=people_report(c,True);result=event_performance(c,eid,report=report);event=result['event']
    pertinent=sorted([e for e in report[1].values() if e['include_analytics'] and e['date']<event['date'] and (e['name'].casefold()==event['name'].casefold() or (event['category'] and e['category']==event['category']))],key=lambda e:e['date'],reverse=True)[:3]
    result['comparisons']=compare(c,[e['id'] for e in pertinent]+[eid]) if pertinent else {'rows':[],'differences':[],'method':'Nessun precedente pertinente nello storico disponibile.'}
    included_report=people_report(c)
    from .querying import select_people
    attendee_ids={p['id'] for p in report[0] if p['event_data'].get(eid,{}).get('confirmed')}
    result['segments']=[{**{k:s[k] for k in ('name','count','definition')},'attendees_count':sum(p['id'] in attendee_ids for p in select_people(included_report,s['filters']))} for s in segments(c,included_report)]
    result['participants']=[{**public_person(p),'participation':p['event_data'][eid]} for p in report[0] if eid in p['event_data']]
    result['vip_attendees']=sum(p.get('vip',False) and p['participation']['confirmed'] for p in result['participants'])
    result['report_id']=hashlib.sha256(json.dumps(result,sort_keys=True,default=str).encode()).hexdigest()[:16]
    return result


def money(value):return 'Non definito' if value is None else f'{value/100:,.2f} EUR'.replace(',','_').replace('.',',').replace('_','.')


def xlsx(data):
    book=Workbook();book.remove(book.active)
    sheets=[('Riepilogo',[['EVENTLY — Report post-evento',data['event']['name']],['Data evento',data['event']['date']],['Luogo',data['event']['location']],['Categoria',data['event']['category']],['Generato il',data['generated_at']],['Riferimento',data['report_id']],['Presenze',data['presences']],['Nuovi',data['new']],['Ricorrenti',data['recurring']],['Valore attribuito EUR',None if data['attributed_value'] is None else Decimal(data['attributed_value'])/100],['Spesa riportata EUR',None if data['reported_spend'] is None else Decimal(data['reported_spend'])/100],['Costo organizzativo EUR',None if data['cost'] is None else Decimal(data['cost'])/100],['Incassi verificati','Non disponibili']]),('Ritorno',[['Finestra giorni','Tornati osservati','Idonei','Occasioni','Tasso definitivo','Stato']]+[[w['days'],w['returned'],w['eligible'],w['opportunities'],w['rate'],w['reason']] for w in data['windows']]),('Partecipanti',[['ID persona','Nominativo','Email','Stato evento','Presenze storiche','VIP','Valore attribuito evento EUR']]+[[p['id'],p['name'],p['email'],p['participation']['status'],p['visits'],'Sì' if p.get('vip') else 'No',None if p['participation']['confirmed'] and data['event']['participant_value_cents'] is None else Decimal(data['event']['participant_value_cents'] or 0)/100 if p['participation']['confirmed'] else 0] for p in data['participants']]),('Confronti',[['Evento','Data','Presenze','Nuovi','Ricorrenti','Valore attribuito EUR']]+[[r['event']['name'],r['event']['date'],r['presences'],r['new'],r['recurring'],None if r['attributed_value'] is None else Decimal(r['attributed_value'])/100] for r in data['comparisons']['rows']]),('Community',[['Segmento community','Persone nello storico incluso','Presenti a questo evento','Definizione']]+[[s['name'],s['count'],s['attendees_count'],s['definition']] for s in data['segments']]),('Frequenze',[['Presenze storiche','Persone presenti']]+[[int(n),count] for n,count in data['frequency_distribution'].items()]),('Differenze',[['Evento da','Evento a','Delta presenze','Delta presenze %','Delta valore EUR','Delta valore %','Delta ritorno90 punti']]+[[d['from'],d['to'],d['metrics']['presences']['absolute'],d['metrics']['presences']['percent'],None if d['metrics']['attributed_value']['absolute'] is None else Decimal(d['metrics']['attributed_value']['absolute'])/100,d['metrics']['attributed_value']['percent'],None if d['metrics']['return_90']['absolute'] is None else d['metrics']['return_90']['absolute']*100] for d in data['comparisons']['differences']]),('Metodo',[['Riferimento',data['report_id']],['Generato il',data['generated_at']],['Copertura',data['coverage']],['Riservatezza','Note personali escluse. Dati originali non modificati.'],['Economia','Valore convenzionale, spesa riportata e costo separati; nessun ROI o profitto inferito.']])]
    for name,rows in sheets:
        sheet=book.create_sheet(name)
        for row in rows:sheet.append([safe_text(v) if isinstance(v,str) else v for v in row])
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='2F654B')
        for col in sheet.columns:sheet.column_dimensions[col[0].column_letter].width=28
        for row in sheet:
            for cell in row:
                if isinstance(cell.value,(float,Decimal)) and ('EUR' in str(sheet.cell(1,cell.column).value) or (name=='Riepilogo' and 'EUR' in str(sheet.cell(cell.row,1).value))):cell.number_format='#,##0.00 "€"'
    out=io.BytesIO();book.save(out);return out.getvalue()


def pdf(data):
    import reportlab
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether,PageBreak
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.colors import HexColor,white
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.graphics.shapes import Drawing,Rect,String
    fonts=Path(reportlab.__file__).parent/'fonts'
    if 'Evently' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Evently',str(fonts/'Vera.ttf')));pdfmetrics.registerFont(TTFont('EventlyBold',str(fonts/'VeraBd.ttf')))
    green=HexColor('#2f654b');muted=HexColor('#526353');styles=getSampleStyleSheet()
    styles.add(ParagraphStyle('Brand',fontName='EventlyBold',fontSize=32,leading=39,textColor=green,spaceAfter=18))
    styles.add(ParagraphStyle('SectionTitle',fontName='EventlyBold',fontSize=16,leading=21,textColor=green,spaceBefore=19,spaceAfter=10))
    styles.add(ParagraphStyle('Copy',fontName='Evently',fontSize=9,leading=14,textColor=muted,spaceAfter=8))
    out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=44,bottomMargin=48,title='EVENTLY — '+data['event']['name'],author='EVENTLY locale')
    story=[]
    def paragraph(text,style='Copy'):return Paragraph(escape(str(text)),styles[style])
    def heading(text):story.append(paragraph(text,'SectionTitle'))
    def table(rows,widths=None):
        cells=[[paragraph(v) for v in row] for row in rows];t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#edf4e9')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),1,green),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#f7f9f7')]) ]));story.append(t)
    story.extend([paragraph('evently.','Brand'),paragraph('REPORT POST-EVENTO','SectionTitle'),paragraph(data['event']['name'],'Brand'),paragraph(f"{data['event']['date']} · {data['event']['location'] or 'Luogo non specificato'} · {data['event']['category'] or 'Categoria non specificata'}"),paragraph('Generato il '+data['generated_at']+' · Riferimento '+data['report_id']),Spacer(1,12)])
    heading('Executive summary')
    table([['Presenze confermate','Nuovi nella giornata','Già conosciuti','Valore attribuito'],[data['presences'],data['new'],data['recurring'],money(data['attributed_value'])]],[128]*4)
    story.append(paragraph(f"{data['returned_later']} {'persona ha' if data['returned_later']==1 else 'persone hanno'} una presenza successiva conosciuta. {data['vip_attendees']} {'presente è' if data['vip_attendees']==1 else 'presenti sono'} VIP per decisione manuale. I conteggi descrivono lo storico disponibile e non attribuiscono cause al ritorno."))
    heading('Profilo e frequenza dei partecipanti')
    graph=Drawing(505,120);max_count=max([int(v) for v in data['frequency_distribution'].values()]+[1]);items=list(data['frequency_distribution'].items())[:12]
    for i,(n,count) in enumerate(items):
        x=10+i*(480/max(1,len(items)));height=70*count/max_count;graph.add(Rect(x,24,25,height,fillColor=green,strokeColor=None));graph.add(String(x,10,str(n)+' pres.',fontName='Evently',fontSize=7));graph.add(String(x,30+height,str(count),fontName='Evently',fontSize=8))
    story.extend([graph,paragraph('Distribuzione delle frequenze storiche dei presenti (prime 12 frequenze, valori completi nei dati XLSX e scheda). Nessuna informazione riservata delle note personali è inclusa.')])
    heading('Ritorno successivo')
    table([['Finestra','Tornati / idonei','Occasioni','Tasso definitivo / osservazione']]+[[str(w['days'])+' giorni',f"{w['returned']} / {w['eligible']}",w['opportunities'],(f"{w['rate']:.1%}" if w['rate'] is not None else w['reason'])] for w in data['windows']],[65,95,60,292])
    heading('Confronti pertinenti')
    if data['comparisons']['rows']:
        table([['Evento precedente / corrente','Data','Presenze','Valore attribuito']]+[[r['event']['name'],r['event']['date'],r['presences'],money(r['attributed_value'])] for r in data['comparisons']['rows']],[220,90,65,137])
        for diff in data['comparisons']['differences']:
            a=next(r for r in data['comparisons']['rows'] if r['event']['id']==diff['from']);b=next(r for r in data['comparisons']['rows'] if r['event']['id']==diff['to']);delta=diff['metrics']['presences'];percent='non disponibile (base zero)' if delta['percent'] is None else f"{delta['percent']*100:+.1f}%"
            story.append(paragraph(f"{a['event']['name']} → {b['event']['name']}: differenza presenze {delta['absolute']:+d}, percentuale {percent}."))
        story.append(paragraph('Precedenti dello stesso nome o categoria; nessun confronto definitivo fra finestre non mature. Le differenze sono descrittive, non spiegazioni causali.'))
    else:story.append(paragraph('Non sono disponibili eventi precedenti pertinenti per un confronto.'))
    heading('Analisi economica')
    table([['Misura','Importo / disponibilità'],['Valore convenzionale attribuito',money(data['attributed_value'])],['Spesa riportata dalle fonti (non incassi verificati)',money(data['reported_spend'])],['Costo organizzativo registrato',money(data['cost'])],['Incassi verificati / ROI / profitto','Non disponibili / non calcolati']],[310,202])
    heading('Community insights')
    table([['Segmento dinamico','Community inclusa','Presenti evento']]+[[s['name'],s['count'],s['attendees_count']] for s in data['segments']],[280,116,116])
    story.append(paragraph('I segmenti possono sovrapporsi: sono indicate separatamente community e persone presenti a questo evento, alla generazione. Lo stato VIP e i premi richiedono sempre decisioni manuali.'))
    heading('Metodo e copertura')
    story.append(paragraph(data['coverage']));story.append(paragraph('Presenza: una persona unificata per evento con stato confermato. Ricorrente: almeno una data precedente. Ritorno: soltanto eventi a date successive nella finestra; percentuale definitiva solo con osservazione completa e almeno una occasione nota. Zero e valore non definito restano distinti.'))
    def footer(canvas,doc):
        canvas.setStrokeColor(green);canvas.line(42,35,A4[0]-42,35);canvas.setFont('Evently',7);canvas.setFillColor(muted);canvas.drawString(42,23,'EVENTLY · Report locale · '+data['report_id']);canvas.drawRightString(A4[0]-42,23,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return out.getvalue()
