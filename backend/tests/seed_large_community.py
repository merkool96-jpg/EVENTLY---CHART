"""Disposable 10k CRM browser fixture. Refuses any existing database path."""
import os
from pathlib import Path
from datetime import date,timedelta


def main():
    target=os.getenv('EVENTLY_DB')
    if not target or Path(target).exists():raise SystemExit('Set EVENTLY_DB to a NEW disposable file; existing databases are never seeded.')
    from backend import app as module
    with module.db(True) as c:
        c.executemany('INSERT INTO people(name,email) VALUES(?,?)',[(f'Persona{i} Cognome{i}',f'p{i}@example.test' if i%2==0 else '') for i in range(10000)])
        c.execute('INSERT INTO events(name,date,participant_value_cents) VALUES(?,?,100)',('Evento sintetico 10k',(date.today()-timedelta(days=1)).isoformat()))
        c.executemany("INSERT INTO attendance(event_id,person_id,status) VALUES(1,?,'confirmed')",[(i,) for i in range(1,10001)])
    print('Seed sintetico10k completato su file nuovo.')


if __name__=='__main__':main()
