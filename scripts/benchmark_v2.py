"""Reproducible core-workflow benchmarks on disposable synthetic archives."""
import argparse
import asyncio
import io
import json
import os
import platform
import sqlite3
import tempfile
from pathlib import Path
from time import perf_counter


def measure(fn):
    start=perf_counter();value=fn();return round(perf_counter()-start,6),value


def run_size(size,folder):
    from backend.migrations import migrate
    path=folder/f'archive-{size}.db';migrate(path)
    with sqlite3.connect(path) as c:
        e=c.execute("INSERT INTO events(name,date,cost,participant_value_cents) VALUES('Benchmark','2026-01-01',0,2000)").lastrowid
        for i in range(size):
            pid=c.execute('INSERT INTO people(name,email) VALUES(?,?)',(f'Persona{i} Cognome{i}',f'persona{i}@example.test')).lastrowid
            aid=c.execute('INSERT INTO attendance(event_id,person_id,amount,status) VALUES(?,?,0,?)',(e,pid,'confirmed' if i%2==0 else 'registered')).lastrowid
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='attendance_evidence'").fetchone():c.execute('INSERT INTO attendance_evidence(attendance_id,status,source) VALUES(?,?,?)',(aid,'confirmed' if i%2==0 else 'registered','synthetic'))
        a=c.execute("INSERT INTO people(name,email) VALUES('Mario Rossi','control@example.test')").lastrowid
        b=c.execute("INSERT INTO people(name,email) VALUES('Mario Rosssi','control@example.test')").lastrowid
    os.environ['EVENTLY_DB']=str(path)
    from backend import app as module
    module.DB=str(path)
    from backend.identity import candidates
    from backend.exporting import export_file
    from starlette.datastructures import UploadFile
    out={'synthetic_profiles':size,'additional_control_profiles':2,'archive_attendance':size}
    out['dashboard_s'],_=measure(module.dashboard)
    people_endpoint=next((r.endpoint for r in module.app.routes if getattr(r,'path','')=='/api/v2/people'),None)
    out['search_s'],_=measure(lambda:people_endpoint(q=f'Persona{size-1}') if people_endpoint else module.people(q=f'Persona{size-1}',limit=50))
    with module.db() as c:out['identity_review_s'],_=measure(lambda:candidates(c))
    review_endpoint=next((r.endpoint for r in module.app.routes if getattr(r,'path','')=='/api/v2/identity'),None)
    if review_endpoint:out['identity_screen_s'],_=measure(review_endpoint)
    imports=[]
    import inspect
    for count in (10,100):
        content=('Nome completo,Email\n'+'\n'.join(f'Import{count}Persona{i} Cognome{i},i{count}p{i}@example.test' for i in range(count))+'\n').encode()
        args={'file':UploadFile(filename='synthetic.csv',file=io.BytesIO(content)),'event_id':e,'status':'registered','sheet':None,'mapping':None,'header_row':1,'use_row_status':False}
        args={k:v for k,v in args.items() if k in inspect.signature(module.preview_import).parameters}
        seconds,draft=measure(lambda:asyncio.run(module.preview_import(**args)))
        confirm,_=measure(lambda:module.confirm_import(draft['token']))
        imports.append({'rows':count,'preview_s':seconds,'confirm_s':confirm})
    out['imports']=imports
    out['merge_s'],_=measure(lambda:module.decide(module.Decision(a=a,b=b,action='merge')))
    out['keep_separate_s'],_=measure(lambda:module.decide(module.Decision(a=1,b=2,action='separate')))
    with module.db() as c:
        try:
            from backend.operations import analytics
            out['analytics_s'],_=measure(lambda:analytics(c))
        except ImportError:out['analytics_s']=None
        out['xlsx_s'],blob=measure(lambda:export_file(c,'xlsx'))
        out['xlsx_bytes']=len(blob)
    return out


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='docs/BENCHMARK_V2.json');args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='evently-v2-benchmark-') as name:
        result={'platform':platform.platform(),'python':platform.python_version(),'logical_cpus':os.cpu_count(),'method':'Core API functions, wall clock, single run, warm interpreter, synthetic unique names/emails plus two controlled identity variants. No browser/network latency. Search uses the V2 paginated selector when available, legacy API otherwise. identity_review is matching core; identity_screen additionally runs V2 group preflight and impact. Imports add 110 profiles before merge/analytics/export measurements.','results':[]}
        if Path('/proc/cpuinfo').exists():result['cpu']=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),'unknown')
        for size in (2000,10000):
            row=run_size(size,Path(name));result['results'].append(row);print(json.dumps(row),flush=True)
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
