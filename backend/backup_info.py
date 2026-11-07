"""Read-only backup metadata; invalid copies remain visible and cannot be called verified."""
from datetime import datetime,timezone
import hashlib,json,sqlite3
from pathlib import Path


def database_counts(c):
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    counts={t:c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] if t in tables else None for t in ('people','events','attendance','imports','decisions')}
    for key,kind in [('crm_notes','note'),('crm_rewards','reward'),('crm_vips','vip')]:
        counts[key]=c.execute('SELECT COUNT(*) FROM crm_records WHERE kind=?',(kind,)).fetchone()[0] if 'crm_records' in tables else None
    for key,table in [('crm_tags','crm_tags'),('crm_segments','crm_segments')]:counts[key]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in tables else None
    return counts


def describe_backup(path):
    stat=path.stat()
    info={'name':path.name,'bytes':stat.st_size,'created_at':datetime.fromtimestamp(stat.st_mtime,timezone.utc).isoformat(),'verified':False,'schema_version':None,'counts':None,'error':''}
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError()
            info['schema_version']=c.execute('PRAGMA user_version').fetchone()[0]
            info['counts']=database_counts(c)
            if any(info['counts'][t] is None for t in ('people','events','attendance')):raise ValueError()
        manifest=path.with_suffix('.json')
        if manifest.exists() and json.loads(manifest.read_text()).get('sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError()
        info['verified']=True
    except Exception:info['error']='Copia non verificabile: non usarla prima di una verifica su copia.'
    return info
