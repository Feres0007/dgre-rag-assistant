import argparse
import json
import platform
import sys
from pathlib import Path
from dgre_rag.config import root, data_dir, settings
from dgre_rag.storage.database import active_release, dump, publish, backup, restore, connect
from dgre_rag.ingestion.pipeline import register,extract,validate
from dgre_rag.answers.service import Service


def doctor():
    import sqlite3
    import importlib.metadata
    from dgre_rag.providers.local import model_status
    return {'python':sys.version,'platform':platform.platform(),'root':str(root()),
        'sqlite':sqlite3.sqlite_version,'release':active_release(),'llm':model_status(),
        'dependencies':{p:importlib.metadata.version(p) for p in ['pymupdf','streamlit','pydantic','fastembed']},
        'corpus_present':len(list((root()/settings().corpus_dir).glob('*.pdf')))==2}


def last_run():
    path=data_dir()/'last_run.json'
    if not path.exists():raise ValueError('NO_EXTRACTION_RUN')
    return json.loads(path.read_text(encoding='utf-8'))['run_id']


def main():
    parser=argparse.ArgumentParser(description='DGRE — consultation locale et traçable des annuaires')
    subs=parser.add_subparsers(dest='command',required=True)
    for name in ['doctor','register','inventory','coverage','backup']:
        subs.add_parser(name)
    for name in ['extract','validate']:
        p=subs.add_parser(name);p.add_argument('--scope',choices=['pilot','all'],default='pilot');p.add_argument('--run-id')
    p=subs.add_parser('publish');p.add_argument('--run-id');p.add_argument('--label',default='corpus');p.add_argument('--no-activate',action='store_true')
    for name in ['index','rebuild-index']:
        p=subs.add_parser(name);p.add_argument('--allow-download',action='store_true');p.add_argument('--release-id')
    p=subs.add_parser('ask');p.add_argument('question');p.add_argument('--no-llm',action='store_true');p.add_argument('--release-id')
    p=subs.add_parser('search');p.add_argument('question');p.add_argument('--mode',choices=['lexical','vector','hybrid'],default='hybrid')
    p=subs.add_parser('resolve');p.add_argument('question')
    p=subs.add_parser('inspect-source');p.add_argument('source_id')
    p=subs.add_parser('restore');p.add_argument('release_id')
    p=subs.add_parser('activate');p.add_argument('release_id')
    p=subs.add_parser('evaluate');p.add_argument('--split',choices=['dev','test'],default='test');p.add_argument('--release-id')
    args=parser.parse_args()
    try:
        match args.command:
            case 'doctor':result=doctor()
            case 'register':result=register()
            case 'inventory':
                records=register()
                import pymupdf
                rows=[]
                for record in records:
                    with pymupdf.open(root()/record['relative_path']) as doc:
                        rows += [{'document_id':record['document_id'],'page_pdf':i+1,'width':p.rect.width,'height':p.rect.height,'rotation':p.rotation,'text_characters':len(p.get_text())} for i,p in enumerate(doc)]
                dump(data_dir()/'inventory.json',rows);result={'pages':len(rows)}
            case 'extract':result={'run_id':extract(args.scope)}
            case 'validate':result=validate(args.run_id or last_run())
            case 'publish':result={'release_id':publish(args.run_id or last_run(),args.label,activate=not args.no_activate)}
            case 'index'|'rebuild-index':
                from dgre_rag.retrieval.search import build_index
                result=build_index(release_id=args.release_id,allow_download=args.allow_download)
            case 'ask':result=Service(args.release_id).ask(args.question,use_llm=not args.no_llm).model_dump(mode='json')
            case 'search':
                from dgre_rag.retrieval.search import retrieve
                rows,warnings=retrieve(args.question,mode=args.mode)
                result={'warnings':warnings,'passages':[{k:r[k] for k in ['source_id','document_id','page_pdf','text','score']} for r in rows]}
            case 'resolve':
                from dgre_rag.query.planner import entities
                result=entities(args.question,active_release())
            case 'coverage':result=Service().get_coverage()
            case 'inspect-source':
                with connect() as db:
                    row=db.execute('SELECT * FROM sources WHERE source_id=?',(args.source_id,)).fetchone()
                    if not row:raise ValueError('UNKNOWN_SOURCE')
                    result=dict(row)
                rendered=Service().get_source_page(result['document_id'],result['page_pdf'],args.source_id)
                out=data_dir()/'inspections'/f'{args.source_id}.png';out.parent.mkdir(exist_ok=True)
                out.write_bytes(rendered['image']);result['rendered_path']=str(out)
            case 'backup':result={'backup':str(backup())}
            case 'restore'|'activate':restore(args.release_id);result={'release_id':args.release_id}
            case 'evaluate':
                from dgre_rag.evaluation import evaluate
                result=evaluate(args.split,args.release_id)
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    except (ValueError,RuntimeError,OSError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr);raise SystemExit(2)


if __name__=='__main__':main()
