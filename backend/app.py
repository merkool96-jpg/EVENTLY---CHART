"""EVENTLY: local event intelligence. All money is stored in integer cents."""
import csv
import io
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="EVENTLY", version="0.1.0")
DB = os.getenv("EVENTLY_DB", str(Path(__file__).parent / "evently.db"))

@contextmanager
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, name TEXT NOT NULL, date TEXT NOT NULL, location TEXT NOT NULL DEFAULT '', cost INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE, person_id INTEGER NOT NULL REFERENCES people(id), amount INTEGER NOT NULL DEFAULT 0, UNIQUE(event_id,person_id));
        CREATE TABLE IF NOT EXISTS separate(a INTEGER REFERENCES people(id) ON DELETE CASCADE,b INTEGER REFERENCES people(id) ON DELETE CASCADE,PRIMARY KEY(a,b));
        CREATE TABLE IF NOT EXISTS aliases(person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,name TEXT,email TEXT,phone TEXT, UNIQUE(person_id,name,email,phone));
        ''')
init()


def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower())


def cents(value):
    s = str(value or '0').replace('€', '').replace(' ', '').strip()
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        n = Decimal(s)
        if not n.is_finite() or n < 0 or n > 100000000:
            raise ValueError()
        return int((n * 100).quantize(Decimal('1')))
    except (InvalidOperation, ValueError):
        raise ValueError(f'Importo non valido: {value}')


class Event(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    date: date
    location: str = Field(default='', max_length=200)
    cost: int = Field(default=0, ge=0, le=10000000000)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Nome evento obbligatorio')
        return value.strip()

class Decision(BaseModel):
    a: int
    b: int
    action: str


@app.get('/api/health')
def health():
    with db() as c:
        c.execute('SELECT 1')
    return {'status': 'ok'}


@app.get('/api/events')
def events():
    with db() as c:
        return [dict(r) for r in c.execute('''SELECT e.*,COUNT(a.id) participants,COALESCE(SUM(a.amount),0) revenue FROM events e LEFT JOIN attendance a ON a.event_id=e.id GROUP BY e.id ORDER BY e.date DESC,e.id DESC''')]


@app.post('/api/events', status_code=201)
def create_event(e: Event):
    with db() as c:
        cur = c.execute('INSERT INTO events(name,date,location,cost) VALUES(?,?,?,?)', (e.name.strip(), str(e.date), e.location, e.cost))
        return {'id': cur.lastrowid}


@app.put('/api/events/{event_id}')
def update_event(event_id: int, e: Event):
    with db() as c:
        if not c.execute('UPDATE events SET name=?,date=?,location=?,cost=? WHERE id=?', (e.name.strip(), str(e.date), e.location, e.cost,event_id)).rowcount:
            raise HTTPException(404, 'Evento non trovato')
    return {'ok': True}


@app.delete('/api/events/{event_id}')
def delete_event(event_id: int):
    with db() as c:
        if not c.execute('DELETE FROM events WHERE id=?', (event_id,)).rowcount:
            raise HTTPException(404, 'Evento non trovato')
    return {'ok': True}


@app.get('/api/people')
def people(q: str = '', limit: int = 10000):
    with db() as c:
        return [dict(r) for r in c.execute('''SELECT p.*,COUNT(a.id) visits,COALESCE(SUM(a.amount),0) value,MAX(e.date) last_seen FROM people p LEFT JOIN attendance a ON a.person_id=p.id LEFT JOIN events e ON e.id=a.event_id WHERE p.name LIKE ? OR p.email LIKE ? GROUP BY p.id ORDER BY value DESC,visits DESC,p.name LIMIT ?''', (f'%{q}%',f'%{q}%',max(1,min(limit,10000))))]


@app.get('/api/people/{person_id}')
def profile(person_id: int):
    with db() as c:
        p = c.execute('SELECT * FROM people WHERE id=?',(person_id,)).fetchone()
        if not p:
            raise HTTPException(404,'Persona non trovata')
        return {**dict(p),'events':[dict(r) for r in c.execute('SELECT e.*,a.amount FROM attendance a JOIN events e ON e.id=a.event_id WHERE a.person_id=? ORDER BY e.date DESC',(person_id,))]}


@app.get('/api/dashboard')
def dashboard():
    es = events()
    ps = people()
    return {'people':len(ps),'events':len(es),'revenue':sum(e['revenue'] for e in es),'cost':sum(e['cost'] for e in es),'attendance':sum(e['participants'] for e in es),'returning':sum(p['visits']>1 for p in ps),'timeline':es[::-1]}


def similarity(a,b):
    if a['email'] and a['email'].lower()==b['email'].lower():
        return 1.0,'Stessa email'
    if a['phone'] and norm(a['phone'])==norm(b['phone']):
        return 1.0,'Stesso telefono'
    score=SequenceMatcher(None,norm(a['name']),norm(b['name'])).ratio()
    return score,'Nome simile'


@app.get('/api/matches')
def matches():
    with db() as c:
        ps = c.execute('SELECT * FROM people ORDER BY id').fetchall()
        excluded={tuple(r) for r in c.execute('SELECT a,b FROM separate')}
        result=[]
        for i,a in enumerate(ps):
            for b in ps[i+1:]:
                if (a['id'],b['id']) in excluded:
                    continue
                score,reason=similarity(a,b)
                if score>=0.84:
                    result.append({'a':dict(a),'b':dict(b),'score':round(score*100),'reason':reason})
        return sorted(result,key=lambda r:-r['score'])[:200]


@app.post('/api/matches/decision')
def decide(d: Decision):
    if d.a==d.b or d.action not in ('merge','separate'):
        raise HTTPException(400,'Decisione non valida')
    a,b=sorted((d.a,d.b))
    with db() as c:
        rows=c.execute('SELECT * FROM people WHERE id IN (?,?) ORDER BY id',(a,b)).fetchall()
        if len(rows)!=2:
            raise HTTPException(404,'Persona non trovata')
        if d.action=='separate':
            c.execute('INSERT OR IGNORE INTO separate VALUES(?,?)',(a,b))
        else:
            # One presence per event; preserve all economic value when combining.
            c.execute('INSERT OR IGNORE INTO aliases VALUES(?,?,?,?)',(a,rows[1]['name'],rows[1]['email'],rows[1]['phone']))
            c.execute('INSERT OR IGNORE INTO aliases SELECT ?,name,email,phone FROM aliases WHERE person_id=?',(a,b))
            c.execute('DELETE FROM aliases WHERE person_id=?',(b,))
            for r in c.execute('SELECT * FROM attendance WHERE person_id=?',(b,)).fetchall():
                c.execute('INSERT INTO attendance(event_id,person_id,amount) VALUES(?,?,?) ON CONFLICT(event_id,person_id) DO UPDATE SET amount=amount+excluded.amount',(r['event_id'],a,r['amount']))
            c.execute('DELETE FROM attendance WHERE person_id=?',(b,))
            for r in c.execute('SELECT a,b FROM separate WHERE a=? OR b=?',(b,b)).fetchall():
                other=r['b'] if r['a']==b else r['a']
                if other!=a:
                    c.execute('INSERT OR IGNORE INTO separate VALUES(?,?)',tuple(sorted((a,other))))
            c.execute('UPDATE people SET email=?,phone=? WHERE id=?',(rows[0]['email'] or rows[1]['email'],rows[0]['phone'] or rows[1]['phone'],a))
            c.execute('DELETE FROM people WHERE id=?',(b,))
    return {'ok':True,'person_id':a}

ALIASES={'name':['nomecompleto','nominativo','partecipante','fullname','name','nomeecognome'],'first':['nome','firstname'],'last':['cognome','lastname','surname'],'email':['email','mail','indirizzoemail'],'phone':['telefono','cellulare','phone','tel'],'amount':['importo','totale','amount','valore','spesa','pagato','revenue']}


def parse_file(filename,data):
    ext=Path(filename).suffix.lower()
    if ext=='.csv':
        text=data.decode('utf-8-sig')
        try:
            dialect=csv.Sniffer().sniff(text[:4096],delimiters=',;\t')
        except csv.Error:
            dialect=csv.excel
        rows=list(csv.reader(io.StringIO(text),dialect))
    elif ext=='.xlsx':
        import openpyxl
        book=openpyxl.load_workbook(io.BytesIO(data),read_only=True,data_only=True)
        rows=list(book.active.values)
        book.close()
    elif ext=='.xls':
        import xlrd
        sheet=xlrd.open_workbook(file_contents=data).sheet_by_index(0)
        rows=[sheet.row_values(i) for i in range(sheet.nrows)]
    else:
        raise ValueError('Formato supportato: XLSX, XLS o CSV')
    if len(rows)<2 or len(rows)>20001:
        raise ValueError('Il file deve contenere da 1 a 20.000 righe di dati')
    headers=[norm(h) for h in rows[0]]
    mapping={key:next((i for i,h in enumerate(headers) if h in names),None) for key,names in ALIASES.items()}
    if mapping['name'] is None and mapping['first'] is None and mapping['last'] is None:
        raise ValueError('Colonna nome non riconosciuta. Usa Nome, Cognome o Nome completo.')
    records=[]
    for number,row in enumerate(rows[1:],2):
        if not any(v is not None and str(v).strip() for v in row):
            continue
        def val(key):
            i=mapping[key]
            return str(row[i] or '').strip() if i is not None and i<len(row) else ''
        name=val('name') or ' '.join(filter(None,[val('first'),val('last')]))
        if not name:
            raise ValueError(f'Riga {number}: nome mancante')
        try:
            amount=cents(val('amount'))
        except ValueError as e:
            raise ValueError(f'Riga {number}: {e}')
        records.append((name,val('email').lower(),val('phone'),amount))
    if not records:
        raise ValueError('Nessun partecipante nel file')
    return records,{k:str(rows[0][v]) for k,v in mapping.items() if v is not None}


@app.post('/api/events/{event_id}/import')
async def import_file(event_id:int,file:UploadFile=File(...)):
    data=await file.read(10*1024*1024+1)
    if len(data)>10*1024*1024:
        raise HTTPException(413,'Limite file: 10 MB')
    try:
        records,mapping=parse_file(file.filename or '',data)
    except Exception as e:
        raise HTTPException(400,str(e) if isinstance(e,ValueError) else 'File non leggibile o danneggiato')
    added=skipped=0
    with db() as c:
        if not c.execute('SELECT id FROM events WHERE id=?',(event_id,)).fetchone():
            raise HTTPException(404,'Evento non trovato')
        known=c.execute('SELECT * FROM people UNION ALL SELECT person_id AS id,name,email,phone FROM aliases').fetchall()
        identities={(norm(p['name']),p['email'].lower(),norm(p['phone'])):p['id'] for p in known}
        for name,email,phone,amount in records:
            # Only exact normalized identity is automatic. Similar identities need human review.
            key=(norm(name),email,norm(phone))
            pid=identities.get(key)
            if pid is None:
                pid=c.execute('INSERT INTO people(name,email,phone) VALUES(?,?,?)',(name,email,phone)).lastrowid
                identities[key]=pid
            cur=c.execute('INSERT OR IGNORE INTO attendance(event_id,person_id,amount) VALUES(?,?,?)',(event_id,pid,amount))
            added+=cur.rowcount
            skipped+=not cur.rowcount
    return {'imported':added,'skipped':skipped,'columns':mapping}


@app.post('/api/demo')
def demo():
    with db() as c:
        if c.execute('SELECT COUNT(*) FROM events').fetchone()[0]:
            raise HTTPException(409,'I dati demo si caricano solo in un database senza eventi')
        names=['Giulia Rossi','Marco Bianchi','Sofia Conti','Luca Moretti','Alice Romano','Andrea Ricci','Emma Ferrari','Matteo Costa','Chiara Gallo','Davide Greco','Francesca Bruno','Lorenzo Marino']
        for i,name in enumerate(names):
            c.execute('INSERT INTO people(name,email,phone) VALUES(?,?,?)',(name,f"{name.lower().replace(' ','.')}@example.test",f'3200000{i:03}'))
        ids=[r[0] for r in c.execute('SELECT id FROM people ORDER BY id')]
        for j,(name,day,place,cost) in enumerate([('Creative Connections','2026-05-14','Milano · Spazio Base',42000),('Summer Social Club','2026-06-20','Roma · Terrazza Verde',58000),('Design & People','2026-09-18','Torino · Officine',35000),('Autumn Gathering','2026-10-23','Milano · Spazio Base',62000)]):
            eid=c.execute('INSERT INTO events(name,date,location,cost) VALUES(?,?,?,?)',(name,day,place,cost)).lastrowid
            for i,pid in enumerate(ids):
                if (i+j)%4!=0:
                    c.execute('INSERT INTO attendance(event_id,person_id,amount) VALUES(?,?,?)',(eid,pid,(35+i*8+j*5)*100))
        pid=c.execute('INSERT INTO people(name,email) VALUES(?,?)',('Giulia Rosi','giulia.rossi@example.test')).lastrowid
        c.execute('INSERT INTO attendance(event_id,person_id,amount) VALUES(?,?,?)',(eid,pid,6500))
    return {'ok':True}


DIST=Path(__file__).parent.parent/'frontend'/'dist'
if DIST.exists():
    app.mount('/',StaticFiles(directory=DIST,html=True),name='frontend')
