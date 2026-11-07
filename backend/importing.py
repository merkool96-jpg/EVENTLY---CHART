"""Inspectable imports with original files/rows, preview and idempotent confirmation."""
import csv
import hashlib
import io
import json
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .identity import identify, norm

ALIASES = {
    'name': ['nomecompleto','nominativo','partecipante','fullname','name','nomeecognome'],
    'first': ['nome','firstname'], 'last': ['cognome','lastname','surname'],
    'email': ['email','mail','indirizzoemail'], 'phone': ['telefono','cellulare','phone','tel'],
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


def read_sheet(filename, data, sheet=None):
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
    headers=[str(h or '') for h in rows[0]]
    mapping={key:next((i for i,h in enumerate(headers) if norm(h) in names),None) for key,names in ALIASES.items()}
    return rows, {'sheets':sheets,'sheet':selected,'headers':headers,'mapping':mapping,'sample':rows[1:6]}


def records_from(rows,mapping):
    if set(mapping)-set(ALIASES):
        raise ValueError('Campo mappatura sconosciuto')
    mapping={key:mapping.get(key) for key in ALIASES}
    for column in mapping.values():
        if column is not None and (type(column) is not int or column<0 or column>=len(rows[0])):
            raise ValueError('Indice colonna non valido')
    if all(mapping[k] is None for k in ('name','first','last')):
        raise ValueError('Colonna nome non riconosciuta. Mappa Nome completo oppure Nome/Cognome.')
    result=[]
    for number,row in enumerate(rows[1:],2):
        if not any(v is not None and str(v).strip() for v in row):
            continue
        def value(key):
            i=mapping[key]
            return str(row[i] if row[i] is not None else '').strip() if i is not None and i<len(row) else ''
        name=value('name') or ' '.join(filter(None,[value('first'),value('last')]))
        if not norm(name):
            raise ValueError(f'Riga {number}: nome mancante o non valido')
        try:
            amount=cents(value('amount'))
        except ValueError as e:
            raise ValueError(f'Riga {number}: {e}')
        result.append({'row':number,'name':name,'email':value('email').lower(),'phone':value('phone'),'amount':amount,'original':row})
    if not result:
        raise ValueError('Nessun partecipante nel file')
    return result


def fingerprint(data,config):
    return hashlib.sha256(data+json.dumps(config,sort_keys=True).encode()).hexdigest()


def snapshot(c):
    # Changes to identities, statuses or event values invalidate a stale preview.
    h=hashlib.sha256()
    for table in ('people','events','attendance','identity_links','separate','imports','profile_edits'):
        h.update(table.encode())
        columns='id,fingerprint,event_id,filename,sheet,mapping,status,created_at' if table=='imports' else '*'
        h.update(json.dumps([tuple(r) for r in c.execute(f'SELECT {columns} FROM {table} ORDER BY rowid')],default=str).encode())
    return h.hexdigest()


def apply_import(c,filename,data,config,records):
    key=fingerprint(data,config)
    prior=c.execute('SELECT id FROM imports WHERE fingerprint=?',(key,)).fetchone()
    summary={k:0 for k in ('imported','skipped','automatic','presumed','ambiguous','incomplete','new','updated')}
    if prior:
        summary['skipped']=len(records)
        return {**summary,'import_id':prior['id'],'repeated':True}
    iid=c.execute('INSERT INTO imports(fingerprint,event_id,filename,sheet,mapping,status,original) VALUES(?,?,?,?,?,?,?)',(key,config['event_id'],filename,config['sheet'],json.dumps(config['mapping']),config['status'],data)).lastrowid
    for record in records:
        pid,kind=identify(c,record['name'],record['email'],record['phone'])
        if kind in summary:
            summary[kind]+=1
        old=c.execute('SELECT * FROM attendance WHERE event_id=? AND person_id=?',(config['event_id'],pid)).fetchone()
        if not old:
            c.execute('INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,?,?)',(config['event_id'],pid,record['amount'],config['status']))
            summary['imported']+=1
        else:
            summary['skipped']+=1
            if old['status']!='confirmed' and config['status']=='confirmed':
                c.execute('UPDATE attendance SET status=? WHERE id=?',('confirmed',old['id']))
                c.execute('INSERT INTO status_history(attendance_id,old_status,new_status) VALUES(?,?,?)',(old['id'],old['status'],'confirmed'))
                summary['updated']+=1
        c.execute('INSERT INTO import_rows(import_id,row_number,person_id,original,status) VALUES(?,?,?,?,?)',(iid,record['row'],pid,json.dumps(record['original'],default=str,ensure_ascii=False),config['status']))
    return {**summary,'import_id':iid,'repeated':False}
