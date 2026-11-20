"""Source-bound catalogues and availability; never infer absent measurements."""
import json
from dgre_rag.storage.database import uid


def store_catalog(db, catalogue):
    for family, records in catalogue.items():
        if not isinstance(records,(dict,list)):
            continue
        iterator=records.items() if isinstance(records,dict) else enumerate(records)
        for key,record in iterator:
            source=record.get('source')
            if not source:
                continue
            sid=source['source_id']
            if not db.execute('SELECT 1 FROM sources WHERE source_id=?',(sid,)).fetchone():
                raise ValueError('UNKNOWN_SOURCE')
            payload={'key':key,'record':record,'container':'dict' if isinstance(records,dict) else 'list'}
            db.execute('INSERT OR REPLACE INTO structured_records VALUES (?,?,?,?,?,?)',
                (uid(family,key,sid),family,json.dumps(payload,ensure_ascii=False),sid,'source_bound','family_parser_v2'))
    db.execute("INSERT OR REPLACE INTO run_metadata VALUES ('reference_catalog_version','2')")


def load_catalog(db,release_id):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='structured_records'").fetchone():
        return None
    rows=db.execute('SELECT family,payload_json FROM structured_records ORDER BY family,rowid').fetchall()
    if not rows:return None
    result={'release_id':release_id,'version':2}
    for row in rows:
        payload=json.loads(row['payload_json']);family=row['family']
        if payload['container']=='dict':result.setdefault(family,{})[payload['key']]=payload['record']
        else:result.setdefault(family,[]).append(payload['record'])
    for key in ('regions','history','monthly','seasons','governorates','metadata'):result.setdefault(key,{})
    for key in ('dams','rain_days','coordinates','hydro_summaries','floods','geography'):result.setdefault(key,[])
    return result


def update_availability(db):
    db.execute('DELETE FROM availability')
    for r in db.execute('SELECT * FROM coverage').fetchall():
        status='usable' if r['valid_count']==r['expected_count'] else 'partial' if r['valid_count'] else 'unvalidated'
        db.execute('INSERT INTO availability VALUES (?,?,?,?,?,?,?,?)',
            (r['coverage_id'],r['entity_id'],r['metric_id'],r['period_start'],r['period_end'],status,
             json.dumps(dict(r),ensure_ascii=False),None))
    for r in db.execute("SELECT * FROM table_extractions WHERE state='candidate'").fetchall():
        db.execute('INSERT INTO availability VALUES (?,?,?,?,?,?,?,?)',
            (uid('raw',r['source_id']),None,'raw_table',None,None,'not_extracted',r['reason'],r['source_id']))


def availability(db,entity_id=None,metric_id=None,start=None,end=None):
    clauses=[];args=[]
    for field,value in (('entity_id',entity_id),('metric_id',metric_id)):
        if value:clauses.append(field+'=?');args.append(value)
    if start:clauses.append('period_start>=?');args.append(str(start))
    if end:clauses.append('period_end<=?');args.append(str(end))
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    rows=db.execute('SELECT quality_status,count(*) n FROM observations'+where+' GROUP BY quality_status',args).fetchall()
    counts={r['quality_status']:r['n'] for r in rows}
    if counts.get('validated'):status='usable' if not counts.get('blocked') else 'partial'
    elif counts:status='unvalidated'
    else:status='not_retrieved'
    return {'status':status,'counts':counts,'absence_confirmed':False}
