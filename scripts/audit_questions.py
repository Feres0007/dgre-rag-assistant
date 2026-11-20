"""Importer une liste, exécuter le véritable assistant et conserver un audit reprenable.

python scripts/audit_questions.py --input fichier.txt --name avant --mode deterministic
python scripts/audit_questions.py --name apres --mode full --resume
Les verdicts ne sont jamais déduits du seul statut 'answered'.
"""
import argparse
import csv
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from datetime import datetime,timezone
from dgre_rag.config import root
from dgre_rag.answers.service import Service
from dgre_rag.storage.database import dump,file_hash


def import_questions(path):
    text=Path(path).read_text(encoding='utf-8-sig')
    if Path(path).suffix=='.json':
        loaded=json.loads(text)
        if not isinstance(loaded,list):raise ValueError('La liste JSON doit être un tableau de questions')
        result=[{'id':i+1,'question':q} if isinstance(q,str) else q for i,q in enumerate(loaded)]
        if not result or any(not isinstance(r,dict) or not isinstance(r.get('id'),int) or not isinstance(r.get('question'),str) or not r['question'].strip() for r in result):raise ValueError('Questions invalides')
        if len({r['id'] for r in result})!=len(result):raise ValueError('Numéros dupliqués')
        return result
    result=[];section=''
    for line in text.splitlines():
        if 'SECTION' in line:section=line.strip(' #-,')
        match=re.match(r'^\s*(\d+)\.\s+(.+?)\s*$',line)
        if match:result.append({'id':int(match[1]),'question':match[2],'section':section})
    if not result or len({r['id'] for r in result})!=len(result):raise ValueError('Liste vide ou numéros dupliqués')
    return result


def assess(answer,gold):
    if not gold:return 'a_verifier','Aucune référence indépendante annotée pour cette question.'
    if gold.get('question_sha256') and hashlib.sha256(answer.get('question','').encode('utf-8')).hexdigest()!=gold['question_sha256']:
        return 'a_verifier','La question a changé : les critères associés à cet ancien numéro ne sont pas réutilisés.'
    if gold.get('expected_status') and answer['status'] not in gold['expected_status']:
        return 'probleme','La réponse ne présente pas le résultat ou la réserve attendue.'
    def normalize(value):
        return ''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c)).replace('\u202f','').replace('\u00a0','')
    normalized=normalize(answer['text'].replace('\u202f','').replace('\u00a0',''))
    for term in gold.get('required',[]):
        if not any(normalize(option) in normalized for option in (term if isinstance(term,list) else [term])):
            return 'probleme','Élément attendu absent : '+str(term)
    if any(normalize(term) in normalized for term in gold.get('forbidden',[])):
        return 'probleme','Une affirmation exclue par la référence apparaît dans la réponse.'
    pages={(c['document_id'],c['page_pdf']) for c in answer.get('citations',[])}
    if gold.get('pages') and not any(tuple(p) in pages for p in gold['pages']):
        return 'probleme','La page de preuve attendue ne figure pas parmi les références.'
    if gold.get('all_pages') and not {tuple(p) for p in gold['all_pages']}<=pages:
        return 'probleme','Une des preuves nécessaires manque.'
    from decimal import Decimal
    for expected in gold.get('expected_facts',[]):
        actual=answer.get('facts',[])+answer.get('table',[])
        def matches(row):
            for key,value in expected.items():
                if key=='value_decimal':
                    if row.get(key) is None or Decimal(row[key])!=Decimal(value):return False
                elif row.get(key)!=value:return False
            return True
        if not any(matches(row) for row in actual):return 'probleme','Valeur, station, période ou unité différente de la référence structurée.'
    for expected in gold.get('expected_calculations',[]):
        if not any(all((Decimal(c[k])==Decimal(v) if k=='value' else c.get(k)==v) for k,v in expected.items()) for c in answer.get('calculations',[])):
            return 'probleme','Le calcul ne correspond pas à la référence structurée.'
    for expected in gold.get('expected_claims',[]):
        if not any(all((Decimal(c[k])==Decimal(v) if k=='value' else c.get(k)==v) for k,v in expected.items()) for c in answer.get('claims',[])):
            return 'probleme','L’affirmation vérifiée ne correspond pas à la référence.'
    if gold.get('expected_coverage') and not any(all(c.get(k)==v for k,v in gold['expected_coverage'].items()) for c in answer.get('coverage',[])):
        return 'probleme','La couverture annoncée diffère de la référence.'
    return 'conforme_aux_criteres','Les critères annotés sont satisfaits ; ce contrôle ne certifie pas chaque phrase.'


def export_report(folder,records):
    columns=['id','question','response','verdict','reason','reference_attendue','status','seconds','sources']
    with (folder/'reponses.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,delimiter=';');writer.writeheader()
        for r in records:
            row={k:r.get(k,'') for k in columns}
            for k,v in row.items():
                if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')):row[k]="'"+v
            writer.writerow(row)
    def esc(value):return html.escape(str(value))
    items=''.join(f'<article data-verdict="{esc(r["verdict"])}"><h2>{r["id"]}. {esc(r["question"])}</h2><p class="tag">{esc(r["verdict"])} — {esc(r["reason"])}</p><pre>{esc(r["response"])}</pre><p>{esc(r["sources"])}</p><details><summary>Critères de vérification issus des PDF</summary><pre>{esc(r.get("reference_attendue","Non annotée"))}</pre></details></article>' for r in records)
    (folder/'rapport.html').write_text('''<!doctype html><html lang="fr"><meta charset="utf-8"><title>Audit des questions</title>
<style>body{font:17px system-ui;max-width:1000px;margin:40px auto;background:#f5f7fa;color:#20323d}article{background:white;padding:24px;margin:20px 0;border-radius:12px}h2{font-size:19px}pre{white-space:pre-wrap;font:inherit}.tag{color:#765316}select{padding:10px}</style>
<h1>Questions, réponses et vérifications</h1><p>« Conforme aux critères » est un contrôle ciblé. « À vérifier » n'est pas une réponse validée.</p>
<select onchange="document.querySelectorAll('article').forEach(a=>a.hidden=this.value && a.dataset.verdict!==this.value)"><option value="">Toutes les réponses</option><option>probleme</option><option>a_verifier</option><option>conforme_aux_criteres</option></select>'''+items,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input');p.add_argument('--name',default='audit');p.add_argument('--mode',choices=['full','deterministic'],default='full')
    p.add_argument('--resume',action='store_true');p.add_argument('--ids');p.add_argument('--review-only',action='store_true')
    p.add_argument('--release-id');p.add_argument('--gold');p.add_argument('--questions')
    args=p.parse_args()
    if not re.fullmatch(r'[\w-]+',args.name):raise ValueError('Nom de campagne invalide')
    question_file=Path(args.questions) if args.questions else root()/'evaluation/user_questions.json'
    if args.input:dump(question_file,import_questions(args.input))
    cases=json.loads(question_file.read_text(encoding='utf-8'))
    if args.ids:
        ids={int(i) for i in args.ids.split(',')};cases=[c for c in cases if c['id'] in ids]
    folder=root()/'reports/question_audits'/args.name;folder.mkdir(parents=True,exist_ok=True)
    result_file=folder/'answers.jsonl'
    records=[json.loads(line) for line in result_file.read_text(encoding='utf-8').splitlines()] if result_file.exists() and (args.resume or args.review_only) else []
    if result_file.exists() and not (args.resume or args.review_only):raise ValueError('Campagne existante : choisir un autre nom ou --resume')
    gold_file=Path(args.gold) if args.gold else root()/'evaluation/user_gold.json'
    gold=json.loads(gold_file.read_text(encoding='utf-8')) if gold_file.exists() else {}
    def reference(case_id):
        annotation=gold.get(str(case_id))
        if not annotation:return 'Aucune référence indépendante annotée.'
        return 'Éléments attendus : '+json.dumps(annotation.get('required',[]),ensure_ascii=False)+'\nPages PDF : '+json.dumps(annotation.get('pages',[]),ensure_ascii=False)+'\n'+annotation.get('note','')
    srv=Service(args.release_id);done={r['id'] for r in records}
    if not args.review_only:
        from dgre_rag.config import data_dir,settings
        source_files=sorted((root()/'src/dgre_rag').rglob('*.py'))+sorted((root()/'src/dgre_rag/prompts').glob('*.txt'))
        fingerprint=hashlib.sha256(''.join(str(f.relative_to(root()))+file_hash(f) for f in source_files).encode()).hexdigest()
        catalog_file=data_dir()/f'reference_catalog_{srv.release_id}.json'
        invariant={'mode':args.mode,'release':srv.release_id,'questions_sha256':file_hash(question_file),
            'code_sha256':fingerprint,'reference_catalog_sha256':file_hash(catalog_file) if catalog_file.exists() else None,
            'configuration':settings().model_dump(mode='json')}
        manifest_file=folder/'manifest.json'
        if records:
            previous=json.loads(manifest_file.read_text(encoding='utf-8'))
            if any(previous.get(k)!=v for k,v in invariant.items()):raise ValueError('Code, données ou configuration modifiés : créez une nouvelle campagne pour éviter de mélanger les versions.')
        else:dump(manifest_file,{**invariant,
            'started':datetime.now(timezone.utc).isoformat(),'period_context':'2022-09-01 / 2023-08-31',
            'note':'Période commune explicitement fournie par le titre de la liste ; réponses sans conversation entre questions.'})
        with result_file.open('a',encoding='utf-8') as stream:
            for c in cases:
                if c['id'] in done:continue
                start=time.monotonic()
                context=c.get('context',{'period':{'start':'2022-09-01','end':'2023-08-31'}})
                if 'crue maximale observée' in c['question'] or 'date de la crue maximale' in c['question']:context={}
                try:
                    answer=srv.ask(c['question'],context,use_llm=args.mode=='full').model_dump(mode='json')
                except Exception as exc:
                    answer={'status':'technical_error','question':c['question'],'text':'Échec pendant le traitement : '+type(exc).__name__,'citations':[],'facts':[]}
                verdict,reason=assess(answer,gold.get(str(c['id'])))
                record={**c,'response':answer['text'],'status':answer['status'],'answer':answer,'seconds':round(time.monotonic()-start,2),
                    'sources':'; '.join(dict.fromkeys(f"{x['document_id']} p. {x['page_pdf']}" for x in answer['citations'])),
                    'verdict':verdict,'reason':reason,'reference_attendue':reference(c['id'])}
                records.append(record);stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush()
                if len(records)%10==0:export_report(folder,records)
                print(f"{c['id']}/{len(cases)} {answer['status']} {record['seconds']}s",flush=True)
    for r in records:
        r['verdict'],r['reason']=assess(r['answer'],gold.get(str(r['id'])))
        r['reference_attendue']=reference(r['id'])
    export_report(folder,records)
    dump(folder/'review.json',records)
    campaign=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    summary={'count':len(records),'mode':campaign['mode'],'gold_sha256':file_hash(gold_file) if gold_file.exists() else None,'verdicts':{v:sum(r['verdict']==v for r in records) for v in sorted({r['verdict'] for r in records})}}
    scored=[r for r in records if r['verdict'] in ('probleme','conforme_aux_criteres')]
    correct=sum(r['verdict']=='conforme_aux_criteres' for r in scored)
    strict=sum(any(gold.get(str(r['id']),{}).get(k) for k in ('expected_facts','expected_calculations','expected_claims')) for r in scored)
    summary.update(prepared=len(cases),executed=len(records),evaluable=len(scored),uncertain=len(records)-len(scored),
        structured_references=strict,conformity={'numerator':correct,'denominator':len(scored),
        'rate':correct/len(scored) if scored else None,'formula':'conforme_aux_criteres / verdicts exploitables',
        'scope':'Conformité aux critères annotés, pas certification de toutes les affirmations.'})
    summary['by_category']={category:{v:sum(r['verdict']==v for r in records if r.get('category',r.get('section','non renseignée'))==category) for v in summary['verdicts']}
        for category in sorted({r.get('category',r.get('section','non renseignée')) for r in records})}
    dump(folder/'summary.json',summary);print(summary)


if __name__=='__main__':main()
