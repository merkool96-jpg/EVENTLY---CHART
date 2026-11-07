from types import SimpleNamespace
from scripts import find_installation as finder


def test_running_folder_is_derived_from_server_process_not_download_folder(tmp_path,monkeypatch):
    current=tmp_path/'existing';(current/'backend').mkdir(parents=True);(current/'backend/app.py').write_text('');(current/'AVVIA_EVENTLY.command').write_text('')
    def run(args,**kwargs):
        if '-iTCP:8765' in args:return SimpleNamespace(stdout='123\n')
        if '-iTCP:8000' in args:return SimpleNamespace(stdout='')
        if args[0]=='/bin/ps':return SimpleNamespace(stdout='python -m uvicorn backend.app:app --port 8765')
        return SimpleNamespace(stdout=f'p123\nn{current}\n')
    monkeypatch.setattr(finder.subprocess,'run',run)
    assert finder.running_installations()==[current]


def test_other_service_on_port_is_not_assumed_to_be_evently(tmp_path,monkeypatch):
    def run(args,**kwargs):return SimpleNamespace(stdout='python unrelated_server.py' if args[0]=='/bin/ps' else '123\n')
    monkeypatch.setattr(finder.subprocess,'run',run)
    assert finder.running_installations()==[]


def test_finder_does_not_open_arbitrary_folder_or_choose_between_two_installs(monkeypatch,tmp_path):
    monkeypatch.setattr(finder.sys,'platform','darwin')
    monkeypatch.setattr(finder,'running_installations',lambda:[tmp_path/'one',tmp_path/'two'])
    def reject(*args,**kwargs):raise AssertionError('Must not open Finder when ambiguous')
    monkeypatch.setattr(finder.subprocess,'run',reject)
    assert finder.main()==1
