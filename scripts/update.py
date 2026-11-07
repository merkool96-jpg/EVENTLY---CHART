"""Offline, verified Mac update from an extracted release into an existing app.

Only files in the release manifest are installed; databases and local files are
never copied from the release or removed. Original code and SQLite are backed up.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

SOURCE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(SOURCE))
from backend.migrations import backup_database

PROTECTED={'.git','.venv','node_modules','dist','backups','.evently-local','.env','exports','attachments'}


def safe_path(root,relative):
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts or any(part in PROTECTED for part in path.parts) or any(part.startswith('.env') for part in path.parts) or path.name.lower().endswith(('.db','.sqlite','.sqlite3','.db-wal','.db-shm','.db-journal','.sqlite-wal','.sqlite-shm','.sqlite-journal','.sqlite3-wal','.sqlite3-shm','.sqlite3-journal')):
        raise ValueError('Percorso non consentito nel pacchetto: '+relative)
    dest=root/path
    if root not in dest.resolve().parents or any(p.is_symlink() for p in [dest,*dest.parents] if p!=root and root in p.parents):
        raise ValueError('Percorso o collegamento non sicuro: '+relative)
    return dest


def active_application(target):
    if sys.platform=='darwin':
        result=subprocess.run(['pgrep','-f','uvicorn|scripts/launch.py|vite'],capture_output=True,text=True)
        for pid in result.stdout.split():
            rows=subprocess.run(['lsof','-a','-p',pid,'-d','cwd','-Fn'],capture_output=True,text=True).stdout.splitlines()
            if any(line.startswith('n') and (Path(line[1:]).resolve()==target or target in Path(line[1:]).resolve().parents) for line in rows):
                return True
    elif Path('/proc').exists():
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit() or proc.name==str(os.getpid()):
                continue
            try:
                cmd=(proc/'cmdline').read_bytes().decode(errors='replace')
                cwd=(proc/'cwd').resolve()
                if any(name in cmd for name in ('uvicorn','scripts/launch.py','vite')) and (cwd==target or target in cwd.parents):
                    return True
            except OSError:
                continue
    return False


def apply_update(source,target,check_running=True):
    source=source.resolve();target=target.resolve()
    if source==target:
        raise ValueError('Seleziona la vecchia cartella EVENTLY che contiene i tuoi dati, non quella appena scaricata.')
    if not (target/'backend/app.py').is_file() or not (target/'frontend/package.json').is_file():
        raise ValueError('La cartella selezionata non sembra la tua installazione EVENTLY.')
    if check_running and active_application(target):
        raise ValueError('Chiudi EVENTLY con Ctrl+C nella sua finestra di avvio, poi riprova.')
    manifest=json.loads((source/'update-manifest.json').read_text())
    files=manifest['files']
    if not files or len(files)>500:
        raise ValueError('Manifest del pacchetto non valido')
    for relative,info in files.items():
        src=safe_path(source,relative);safe_path(target,relative)
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest()!=info['sha256']:
            raise ValueError('Pacchetto incompleto o modificato: '+relative)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=target/'backend/backups'/('aggiornamento-'+stamp)
    backup.mkdir(parents=True,mode=0o700)
    database=(target/'backend/evently.db').resolve()
    verified=None
    if database.exists():
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:
            if connection.execute('PRAGMA user_version').fetchone()[0]>4:
                raise ValueError('Il database usa una versione più recente. Aggiornamento interrotto: usa un pacchetto più nuovo.')
        verified=backup_database(database)
        print('Backup database verificato:',verified,flush=True)
    (backup/'coppia-compatibile.json').write_text(json.dumps({'database_precedente':str(verified.relative_to(target)) if verified else None,'schema_massimo_codice_nuovo':4,'istruzioni':'Per tornare indietro, usare insieme codice/ e una copia del database_precedente, con EVENTLY fermo. Non aprire schema4 con codice V1.2.'},indent=2))
    old={}
    # Preserve and verify every overwritten file before changing any source.
    for relative in files:
        dest=safe_path(target,relative)
        if dest.exists():
            saved=backup/'codice'/relative;saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dest,saved)
            if saved.read_bytes()!=dest.read_bytes():
                raise RuntimeError('Backup codice non verificato')
            old[relative]=True
        else:
            old[relative]=False
    (backup/'ripristino.json').write_text(json.dumps(old,indent=2))
    installed=[]
    try:
        for relative,info in files.items():
            dest=safe_path(target,relative);dest.parent.mkdir(parents=True,exist_ok=True)
            installed.append(relative)
            fd,temp_name=tempfile.mkstemp(prefix='.evently-code-',dir=dest.parent)
            os.close(fd)
            temp=Path(temp_name)
            try:
                shutil.copyfile(source/relative,temp)
                temp.chmod(0o755 if info.get('executable') else 0o644)
                os.replace(temp,dest)
            finally:
                if temp.exists():temp.unlink()
    except Exception:
        for relative in reversed(installed):
            dest=safe_path(target,relative)
            if old[relative]:shutil.copy2(backup/'codice'/relative,dest)
            elif dest.exists():dest.unlink()
        raise
    return backup


def main():
    parser=argparse.ArgumentParser(description='Aggiorna EVENTLY conservando dati e backup')
    parser.add_argument('--target',type=Path)
    args=parser.parse_args()
    target=args.target
    if target is None:
        if sys.platform!='darwin':
            parser.error('Specificare --target con la cartella esistente di EVENTLY')
        chosen=subprocess.run(['osascript','-e','POSIX path of (choose folder with prompt "Seleziona la VECCHIA cartella EVENTLY che usi già: i tuoi dati saranno conservati")'],capture_output=True,text=True)
        if chosen.returncode:
            print('Aggiornamento annullato. Nessun dato modificato.');return 0
        target=Path(chosen.stdout.strip())
    try:
        backup=apply_update(SOURCE,target)
        print('\nAggiornamento completato. Dati conservati.\nBackup:',backup,'\nOra riapri AVVIA_EVENTLY.command nella tua cartella originale.',flush=True)
        return 0
    except Exception as error:
        print('Aggiornamento interrotto:',error,file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
