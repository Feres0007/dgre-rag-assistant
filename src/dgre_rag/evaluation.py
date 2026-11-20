import json
import time
from decimal import Decimal
from dgre_rag.config import root,data_dir
from dgre_rag.answers.service import Service
from dgre_rag.retrieval.search import retrieve
from dgre_rag.storage.database import dump


def evaluate(split='test',release_id=None):
    path=root()/'evaluation/questions.jsonl'
    if not path.exists():raise ValueError('EVALUATION_ANNOTATIONS_MISSING')
    cases=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
    cases=[c for c in cases if c['split']==split]
    service=Service(release_id);results=[]
    for case in cases:
        start=time.perf_counter()
        if case['category']=='documentary':
            modes={}
            for mode in ('lexical','vector','hybrid'):
                passages,warnings=retrieve(case['question'],service.release_id,mode=mode)
                locations={(p['document_id'],p['page_pdf']) for p in passages}
                modes[mode]={'hit':all((e['document_id'],e['page_pdf']) in locations for e in case['required_evidence']),'warnings':warnings}
            result={'passed':modes['hybrid']['hit'],'status':'retrieval_only','retrieval':modes}
        else:
            answer=service.ask(case['question'],use_llm=False)
            actual=([c['value'] for c in answer.calculations] or [f['value_decimal'] for f in answer.facts])
            passed=answer.status==case['expected_status']
            if case['expected_value'] is not None:
                passed=passed and any(abs(Decimal(v)-Decimal(case['expected_value']))<=Decimal('1e-12') for v in actual)
            if case.get('expected_event'):
                passed=passed and any(f.get('event_date')==case['expected_event'] for f in answer.facts)
            if answer.status=='answered' and case['required_evidence']:
                locations={(c['document_id'],c['page_pdf']) for c in answer.citations}
                passed=passed and all((e['document_id'],e['page_pdf']) in locations for e in case['required_evidence'])
            result={'passed':passed,'status':answer.status,'values':actual,'text':answer.text,'run_id':answer.run_id}
        results.append({'question_id':case['question_id'],'category':case['category'],'expected_status':case['expected_status'],
            'expected_value':case['expected_value'],'elapsed_seconds':time.perf_counter()-start,**result})
    summary={'split':split,'release_id':service.release_id,'cases':len(results),'passed':sum(r['passed'] for r in results),
        'failed':sum(not r['passed'] for r in results),'results':results,
        'scope':'Contrôle déterministe et recherche ; génération libre et validation humaine non couvertes par ce score.'}
    dump(root()/f'reports/evaluation_{split}_{service.release_id}.json',summary)
    return summary
