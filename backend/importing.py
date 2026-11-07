"""Inspectable imports with original files/rows, preview and idempotent confirmation."""
import csv
import hashlib
import io
import json
import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .identity import identify, norm, full_name, groups, parts

ALIASES = {
    'name': ['nomecompleto','nominativo','partecipante','fullname','name','nomeecognome'],
    'first': ['nome','firstname'], 'last': ['cognome','lastname','surname'],
    'email': ['email','mail','indirizzoemail'], 'phone': ['telefono','cellulare','phone','tel'],
    'registration_id':['idregistrazione','registrationid','ticketid','idbiglietto'],
    'order_id':['idordine','orderid','ordine'],
    'status':['stato','status','presenza','checkin'],
    'date':['dataregistrazione','registrationdate','date','data'],
    'amount': ['importo','totale','amount','spesa','pagato','prezzo','purchaseprice'],
}


def cents(value):
    s = str(value if value is not None else '0').replace('€','').replace(' ','').strip() or '0'
    if ',' in s:
        s=s.replace('.','').replace(',','.')
    try:
        n=Decimal(s)
        if not n.is_finite() or n<0 or n>100000000:
            raise ValueError()
        return int((n*100).quantize(Decimal('1')))
    except (InvalidOperation,ValueError):
        raise ValueError(f'Importo non valido: {value}')


def read_sheet(filename, data, sheet=None, header_row=None):
    ext=Path(filename).suffix.lower()
    if ext=='.csv':
        text=data.decode('utf-8-sig')
        try:
            dialect=csv.Sniffer().sniff(text[:4096],delimiters=',;\t')
        except csv.Error:
            dialect=csv.excel
        rows=list(csv.reader(io.StringIO(text),dialect))
        sheets=['CSV']; selected='CSV'
    elif ext=='.xlsx':
        import openpyxl
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist())>50*1024*1024:
                raise ValueError('Archivio Excel decompresso oltre 50 MB')
        book=openpyxl.load_workbook(io.BytesIO(data),read_only=True,data_only=True)
        try:
            sheets=book.sheetnames
            selected=sheet or sheets[0]
            if selected not in sheets:
                raise ValueError('Foglio non trovato')
            rows=[]
            for row in book[selected].values:
                rows.append(list(row))
                if len(rows)>20001 or len(row)>200:
                    raise ValueError('Limite: 20.000 righe e 200 colonne')
        finally:
            book.close()
    elif ext=='.xls':
        import xlrd
        book=xlrd.open_workbook(file_contents=data,on_demand=True)
        try:
            sheets=book.sheet_names(); selected=sheet or sheets[0]
            if selected not in sheets:
                raise ValueError('Foglio non trovato')
            tab=book.sheet_by_name(selected)
            if tab.nrows>20001 or tab.ncols>200:
                raise ValueError('Limite: 20.000 righe e 200 colonne')
            rows=[tab.row_values(i) for i in range(tab.nrows)]
        finally:
            book.release_resources()
    else:
        raise ValueError('Formato supportato: XLSX, XLS o CSV')
    if not 2<=len(rows)<=20001 or any(len(row)>200 for row in rows):
        raise ValueError('Il file deve contenere da 1 a 20.000 righe e massimo 200 colonne')
    raw_preview=rows[:20]
    if header_row is None:
        scores=[sum(norm(h) in {alias for aliases in ALIASES.values() for alias in aliases} for h in row) for row in rows[:min(20,len(rows)-1)]]
        header_row=max(range(len(scores)),key=lambda i:scores[i])+1
    if not 1<=header_row<len(rows):raise ValueError('Riga intestazione non valida')
    rows=rows[header_row-1:]
    headers=[str(h or '') for h in rows[0]]
    mapping={key:next((i for i,h in enumerate(headers) if norm(h) in names),None) for key,names in ALIASES.items()}
    for key,pattern in [('email',r'[^\s@]+@[^\s@]+\.[^\s@]+'),('phone',r'\+?[\d ().-]{7,20}')]:
        if mapping[key] is None:
            for i in range(len(headers)):
                values=[str(row[i] or '').strip() for row in rows[1:21] if i<len(row) and row[i] is not None]
                if values and sum(bool(re.fullmatch(pattern,v)) for v in values)/len(values)>=.8 and i not in [v for v in mapping.values() if v is not None]:mapping[key]=i;break
    return rows, {'header_row':header_row,'raw_preview':raw_preview,'sheets':sheets,'sheet':selected,'headers':headers,'mapping':mapping,'sample':rows[1:6]}


def records_from(rows,mapping):
    if set(mapping)-set(ALIASES):
        raise ValueError('Campo mappatura sconosciuto')
    mapping={key:mapping.get(key) for key in ALIASES}
    for column in mapping.values():
        if column is not None and (type(column) is not int or column<0 or column>=len(rows[0])):
            raise ValueError('Indice colonna non valido')
    result=[]
    for number,row in enumerate(rows[1:],2):
        if not any(v is not None and str(v).strip() for v in row):continue
        def value(key):
            i=mapping[key]
            return str(row[i] if row[i] is not None else '').strip() if i is not None and i<len(row) else ''
        first,last=value('first'),value('last')
        name=value('name') or ' '.join(filter(None,[first,last]))
        email=value('email').casefold();phone=value('phone')
        valid_email=bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email))
        issue=''
        if not norm(name) and not valid_email:issue='Nessun identificativo utile: nome/cognome o email valida mancanti'
        elif email and not valid_email:issue='Email non valida: correggere prima di attribuire la riga'
        try:amount=cents(value('amount'))
        except ValueError:amount=0;issue='Spesa riportata non valida'
        status={'presente':'confirmed','present':'confirmed','confirmed':'confirmed','checkin':'confirmed','assente':'absent','absent':'absent','annullato':'cancelled','cancelled':'cancelled','iscritto':'registered','registrato':'registered','registered':'registered','unknown':'unknown','daverificare':'unknown'}.get(norm(value('status')))
        if value('status') and status is None:issue='Stato partecipazione non riconosciuto'
        structure='structured' if first and last else 'surname_only' if last and not first else 'given_only' if first and not last else 'email_only' if not name else 'proposed'
        incomplete=not (first and last) if structure!='proposed' else not full_name(name)
        missing=(['Nome mancante'] if structure in ('surname_only','email_only') else [])+(['Cognome mancante'] if structure in ('given_only','email_only') or (structure=='proposed' and not full_name(name)) else [])
        result.append({'incomplete':incomplete,'missing':missing,'row':number,'name':name,'first_name':first,'last_name':last,'structure':structure,'email':email,'phone':phone,'amount':amount,'original':row,'issue':issue,'registration_id':value('registration_id'),'order_id':value('order_id'),'source_date':value('date'),'status':status})
    if not result:raise ValueError('Nessuna riga di dati nel file')
    return result


def fingerprint(data,config):
    return hashlib.sha256(data+json.dumps(config,sort_keys=True).encode()).hexdigest()


def snapshot(c):
    # Changes to identities, statuses or event values invalidate a stale preview.
    h=hashlib.sha256()
    for table in ('people','events','attendance','identity_links','separate','imports','profile_edits','participation_overrides','attendance_evidence','source_keys'):
        h.update(table.encode())
        columns='id,fingerprint,event_id,filename,sheet,mapping,status,created_at' if table=='imports' else '*'
        h.update(json.dumps([tuple(r) for r in c.execute(f'SELECT {columns} FROM {table} ORDER BY rowid')],default=str).encode())
    return h.hexdigest()


def apply_import(c,filename,data,config,records):
    key=fingerprint(data,config)
    prior=c.execute('SELECT id FROM imports WHERE fingerprint=?',(key,)).fetchone()
    summary={k:0 for k in ('imported','skipped','automatic','presumed','ambiguous','incomplete','new','new_profiles','updated')}
    if prior:
        summary['skipped']=len(records)
        return {**summary,'rows_read':len(records),'valid_rows':sum(not r.get('issue') for r in records),'issue_rows':sum(bool(r.get('issue')) for r in records),'details':[{**r,'category':'duplicate' if not r.get('issue') else 'issue'} for r in records],'import_id':prior['id'],'repeated':True}
    iid=c.execute('INSERT INTO imports(fingerprint,event_id,filename,sheet,mapping,status,original) VALUES(?,?,?,?,?,?,?)',(key,config['event_id'],filename,config['sheet'],json.dumps(config['mapping']),config['status'],data)).lastrowid
    ps,membership,members=groups(c)
    from .profiles import canonical_profiles
    known=list(ps.values())+list(canonical_profiles(c,ps,membership,members).values())
    known_first={parts(p)[0] for p in known}
    known_emails={p['email'].casefold() for p in known if p['email']}
    known_phones={norm(p['phone']) for p in known if norm(p['phone'])}
    for row in c.execute('SELECT name FROM aliases'):known_first.add(parts({'name':row['name']})[0])
    same_source={r['row_number']:r['person_id'] for r in c.execute('SELECT r.row_number,r.person_id FROM import_rows r JOIN imports i ON i.id=r.import_id WHERE i.event_id=? AND i.original=? AND i.sheet=? AND i.mapping=?',(config['event_id'],data,config['sheet'],json.dumps(config['mapping'])))}
    summary.update(rows_read=len(records),valid_rows=0,issue_rows=0,details=[])
    for record in records:
        category='imported'
        if record.get('issue'):
            c.execute('INSERT INTO import_issues(import_id,row_number,original,reason) VALUES(?,?,?,?)',(iid,record['row'],json.dumps(record['original'],default=str,ensure_ascii=False),record['issue']))
            summary['issue_rows']+=1
            summary['details'].append({**record,'category':'issue','reason':record['issue']})
            continue
        summary['valid_rows']+=1
        key_record=c.execute('SELECT person_id FROM source_keys WHERE event_id=? AND registration_id=?',(config['event_id'],record.get('registration_id',''))).fetchone() if record.get('registration_id') else None
        if record['row'] in same_source and not key_record:
            pid=same_source[record['row']];kind='existing'
        elif key_record:
            pid=key_record['person_id'];kind='existing'
            original=c.execute('SELECT * FROM people WHERE id=?',(pid,)).fetchone()
            if record['email'] and original['email'] and record['email']!=original['email'].casefold():
                record['issue']='ID registrazione già attribuito a un contatto differente'
                c.execute('INSERT INTO import_issues(import_id,row_number,original,reason) VALUES(?,?,?,?)',(iid,record['row'],json.dumps(record['original'],default=str),record['issue']))
                summary['valid_rows']-=1;summary['issue_rows']+=1;summary['details'].append({**record,'category':'issue'});continue
        else:
            first=parts({'name':record['name'],'first_name':record.get('first_name',''),'last_name':record.get('last_name',''),'name_structure':record.get('structure','proposed')})[0]
            if first not in known_first and not (record['email'] and record['email'] in known_emails) and not (norm(record['phone']) and norm(record['phone']) in known_phones):
                pid=c.execute('INSERT INTO people(name,email,phone,first_name,last_name,name_structure) VALUES(?,?,?,?,?,?)',(record['name'],record['email'],record['phone'],record.get('first_name',''),record.get('last_name',''),record.get('structure','proposed'))).lastrowid
                kind='new' if full_name(record['name']) else 'incomplete'
            else:
                pid,kind=identify(c,record['name'],record['email'],record['phone'],record.get('first_name',''),record.get('last_name',''),record.get('structure','proposed'))
            known_first.add(first);known_emails.add(record['email']);known_phones.add(norm(record['phone']))
        if kind in summary:summary[kind]+=1
        if kind in ('new','incomplete','ambiguous'):summary['new_profiles']+=1
        if record.get('incomplete') and kind!='incomplete':summary['incomplete']+=1
        status=record.get('status') if config.get('use_row_status') and record.get('status') else config['status']
        old=c.execute('SELECT * FROM attendance WHERE event_id=? AND person_id=?',(config['event_id'],pid)).fetchone()
        if not old:
            aid=c.execute('INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,?,?)',(config['event_id'],pid,record['amount'],status)).lastrowid
            summary['imported']+=1
        else:
            aid=old['id'];summary['skipped']+=1;category='duplicate'
            if old['status']!='confirmed' and status=='confirmed':
                c.execute('UPDATE attendance SET status=? WHERE id=?',(status,aid))
                c.execute('INSERT INTO status_history(attendance_id,old_status,new_status) VALUES(?,?,?)',(aid,old['status'],status))
                summary['updated']+=1;category='updated'
        c.execute('INSERT INTO attendance_evidence(attendance_id,status,source) VALUES(?,?,?)',(aid,status,f'import:{iid}:row:{record["row"]}'))
        if record.get('registration_id'):c.execute('INSERT OR IGNORE INTO source_keys VALUES(?,?,?)',(config['event_id'],record['registration_id'],pid))
        c.execute('INSERT INTO import_rows(import_id,row_number,person_id,original,status) VALUES(?,?,?,?,?)',(iid,record['row'],pid,json.dumps(record['original'],default=str,ensure_ascii=False),status))
        summary['details'].append({**record,'person_id':pid,'category':category,'identity':kind,'incomplete':record.get('incomplete',not full_name(record['name']))})
    return {**summary,'import_id':iid,'repeated':False}
