"""Local launcher: install once, serve the built UI and open the user's browser."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent


def digest(paths):
    value = hashlib.sha256()
    for path in sorted(paths):
        value.update(str(path.relative_to(ROOT)).encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def run(args, cwd=ROOT):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True, stdin=subprocess.DEVNULL)


def prepare():
    if sys.version_info < (3, 12):
        raise RuntimeError('Installa Python 3.12 o successivo da https://www.python.org/downloads/macos/ e riapri EVENTLY.')
    npm = shutil.which('npm')
    node = shutil.which('node')
    if not npm or not node:
        raise RuntimeError('Installa Node.js LTS da https://nodejs.org/ e riapri EVENTLY.')
    major = int(subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')[0])
    if major < 22:
        raise RuntimeError('Aggiorna Node.js alla versione LTS da https://nodejs.org/ e riapri EVENTLY.')
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('Preparazione iniziale di EVENTLY…', flush=True)
        run([sys.executable, '-m', 'venv', ROOT / '.venv'])
    state_dir = ROOT / '.evently-local'
    state_dir.mkdir(exist_ok=True)
    state_path = state_dir / 'state.json'
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}
    requirements = ROOT / 'backend/requirements.lock'
    py_key = digest([requirements]) + str(sys.version_info[:2])
    frontend = ROOT / 'frontend'
    npm_key = digest([frontend / 'package.json', frontend / 'package-lock.json'])
    if state.get('python') != py_key:
        print('Installazione delle dipendenze gratuite (solo al primo avvio o dopo un aggiornamento)…', flush=True)
        run([python, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', requirements])
        state['python'] = py_key
    if state.get('npm') != npm_key or not (frontend / 'node_modules').exists():
        run([npm, 'ci', '--no-fund', '--no-audit'], frontend)
        state['npm'] = npm_key
    sources = [p for folder in ('src', 'public') for p in (frontend / folder).rglob('*') if p.is_file()]
    sources += [p for p in frontend.iterdir() if p.is_file() and p.suffix in ('.json', '.ts', '.js', '.html')]
    build_key = digest(sources)
    if state.get('build') != build_key or not (frontend / 'dist/index.html').is_file():
        print('Preparazione della dashboard…', flush=True)
        run([npm, 'run', 'build'], frontend)
        state['build'] = build_key
    state_path.write_text(json.dumps(state))
    return python


def healthy(url):
    try:
        with urllib.request.urlopen(url + '/api/health', timeout=1) as response:
            return json.load(response).get('schema_version') == 2
    except (OSError, ValueError, urllib.error.URLError):
        return False


def serve(python, port, open_browser=True):
    url = f'http://127.0.0.1:{port}'
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise RuntimeError(f'La porta {port} è già occupata. Chiudi la precedente finestra EVENTLY e riprova.')
    process = subprocess.Popen([str(python), '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('EVENTLY non si è avviato. Conserva il messaggio di errore visualizzato in questa finestra.')
            if healthy(url):
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Avvio non completato entro 30 secondi. Conserva i messaggi visualizzati.')
        print(f'\nEVENTLY è pronto: {url}\nLascia aperta questa finestra mentre usi la dashboard.\nPer chiudere EVENTLY premi Ctrl+C qui.\n', flush=True)
        if open_browser:
            webbrowser.open(url)
        process.wait()
    except KeyboardInterrupt:
        print('\nChiusura di EVENTLY. I dati sono salvati nel database locale.', flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description='Avvia EVENTLY sul tuo computer')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('La porta deve essere compresa tra 1024 e 65535')
    try:
        serve(prepare(), args.port, not args.no_browser)
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'\nImpossibile avviare EVENTLY: {error}\nI tuoi dati non sono stati cancellati.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
