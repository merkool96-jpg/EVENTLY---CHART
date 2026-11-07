"""Developer packaging step; the Mac updater itself never needs Git/network."""
import hashlib
import json
from pathlib import Path
import subprocess
from scripts.update import safe_path

ROOT=Path(__file__).resolve().parent.parent


def main():
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    files={}
    for name in sorted(set(filter(None,names))):
        if name=='update-manifest.json':continue
        path=safe_path(ROOT,name)
        if path.is_file():files[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'executable':bool(path.stat().st_mode&0o111)}
    (ROOT/'update-manifest.json').write_text(json.dumps({'release':'evently-v2.1.0','files':files},indent=2)+'\n')
    print('Manifest generato:',len(files),'file applicativi; nessun database o backup incluso')


if __name__=='__main__':main()
