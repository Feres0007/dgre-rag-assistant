"""Vérifications locales et rapports, sans installation ni modification des PDF."""
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path
from dgre_rag.config import root
from dgre_rag.storage.database import dump,backup,restore,active_release,release_path,publish
from dgre_rag.cli import doctor
from dgre_rag.domain.models import QueryPlan,Answer

if __name__=='__main__':
    project=root()
    manifest=json.loads((release_path()/'manifest.json').read_text(encoding='utf-8'))
    print('Publishing quality checks',publish(manifest['run_id'],'corpus'),flush=True)
    dump(project/'reports/environment.json',doctor())
    dump(project/'config/query_plan.schema.json',QueryPlan.model_json_schema())
    dump(project/'config/answer.schema.json',Answer.model_json_schema())
    lock=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,check=True)
    lines=[line for line in lock.stdout.splitlines() if not line.startswith(('-e ', '#', 'dgre-rag'))]
    (project/'requirements.lock.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    runpy.run_path(str(project/'scripts/build_evaluation.py'),run_name='__main__')
    from dgre_rag.evaluation import evaluate
    for split in ('dev','test'):
        print('Evaluation',split,flush=True)
        result=evaluate(split)
        print({k:v for k,v in result.items() if k!='results'},flush=True)
    release=active_release();saved=backup(release);restore(release)
    dump(project/'reports/operations.json',{'backup':saved.relative_to(project).as_posix(),
         'restore_verified':active_release()==release,'release':release})
    print('Operational checks done',flush=True)
