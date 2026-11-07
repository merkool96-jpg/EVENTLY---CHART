"""Locate a running standard Mac install without scanning folders or opening DBs."""
from pathlib import Path
import subprocess
import sys


def running_installations():
    found=set()
    for port in (8765,8000):
        result=subprocess.run(['/usr/sbin/lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-t'],capture_output=True,text=True)
        for pid in result.stdout.split():
            if not pid.isdigit():continue
            command=subprocess.run(['/bin/ps','-p',pid,'-o','command='],capture_output=True,text=True).stdout
            if 'backend.app:app' not in command:continue
            output=subprocess.run(['/usr/sbin/lsof','-a','-p',pid,'-d','cwd','-Fn'],capture_output=True,text=True).stdout
            for line in output.splitlines():
                if not line.startswith('n/'):continue
                root=Path(line[1:]).resolve()
                if (root/'backend/app.py').is_file() and (root/'AVVIA_EVENTLY.command').is_file():found.add(root)
    return sorted(found)


def main():
    if sys.platform!='darwin':
        print('Questo comando apre il Finder sul Mac.');return 1
    try:roots=running_installations()
    except OSError:
        print('Non riesco a leggere la posizione di EVENTLY. Lascia aperta la dashboard e riprova.');return 1
    if not roots:
        print('Nessuna copia EVENTLY trovata sulle porte abituali 8765/8000.\nLascia EVENTLY aperto nella sua finestra Terminale e riprova. Non scegliere una cartella a caso.');return 1
    if len(roots)>1:
        print('Ci sono più copie di EVENTLY aperte. Chiudi quelle che non usi e riprova. Nessun file modificato.');return 1
    root=roots[0]
    print(f'QUESTA È LA CARTELLA EVENTLY IN USO:\n{root}\n\nIl Finder evidenzierà AVVIA_EVENTLY.command nella cartella giusta.\nLascia questa finestra Finder aperta. Se vuoi, crea un alias di AVVIA_EVENTLY.command sulla Scrivania.\nPer aggiornare: ferma EVENTLY con Ctrl+C, poi scegli QUESTA cartella nell’aggiornamento.\nNessun database è stato aperto o modificato.')
    subprocess.run(['/usr/bin/open','-R',str(root/'AVVIA_EVENTLY.command')],check=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
