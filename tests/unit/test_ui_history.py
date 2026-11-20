import importlib.util
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
History=pytest.importorskip('history').History


def test_history_survives_reopen_and_pending(tmp_path):
    path=tmp_path/'history.sqlite';h=History(path)
    assert h.list()==[]
    cid,turn=h.begin('Pluie à Aïn Draham ?', 'release-a')
    assert History(path).load(cid)[0]['state']=='pending'
    answer={'question':'Pluie à Aïn Draham ?','text':'1178 mm','release_id':'release-a','conversation':{'period':{'start':'2022-09-01','end':'2023-08-31'}}}
    h.finish(turn,answer)
    assert History(path).load(cid)[0]['answer']==answer
    _,second=h.begin('Et à Amdoun ?', 'release-b',cid)
    assert len(h.load(cid))==2 and h.load(cid)[1]['answer'] is None
    h.retry(second,'release-c')
    assert h.load(cid)[1]['release_id']=='release-c'
    h.rename(cid,'Mon analyse')
    assert h.list('ANALYSE')[0]['title']=='Mon analyse'
    h.delete(cid)
    assert h.load(cid)==[] and h.list()==[]


def test_ui_restore_exact_and_only_owned_files(tmp_path):
    spec=importlib.util.spec_from_file_location('ui_versions',ROOT/'scripts/ui_versions.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (tmp_path/'app').mkdir();(tmp_path/'.streamlit').mkdir()
    old=b'original interface\r\n'
    (tmp_path/'app/main.py').write_bytes(old)
    (tmp_path/'.streamlit/config.toml').write_text('theme="old"')
    backup=module.snapshot(tmp_path)
    (tmp_path/'app/main.py').write_text('new')
    (tmp_path/'app/new.py').write_text('new')
    (tmp_path/'app/user.txt').write_text('keep')
    (tmp_path/'history.sqlite').write_text('keep history')
    delivery=tmp_path/'delivery.json';delivery.write_text(json.dumps({'new_files':['app/new.py']}))
    module.restore(backup,tmp_path,delivery)
    assert (tmp_path/'app/main.py').read_bytes()==old
    assert not (tmp_path/'app/new.py').exists()
    assert (tmp_path/'app/user.txt').exists() and (tmp_path/'history.sqlite').exists()
    delivery.write_text(json.dumps({'new_files':['../outside']}))
    with pytest.raises(ValueError):module.restore(backup,tmp_path,delivery)
