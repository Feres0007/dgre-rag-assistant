"""One release-bound exit gate shared by UI, CLI and conversation actions."""
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from dgre_rag.storage.database import connect, dump
from dgre_rag.config import data_dir


FIELDS=('canonical_name','metric_id','value_decimal','unit','period_start','period_end')


@lru_cache(maxsize=4)
def source_roles(release_id):
    roles={}
    with connect(release_id) as db:
        for sid,role in db.execute('SELECT DISTINCT source_id,role FROM observation_evidence'):
            roles.setdefault(sid,set()).add(role)
    return roles


def signature(row):
    return tuple(str(row.get(k,'')) for k in FIELDS)


@lru_cache(maxsize=4)
def reference_rows(release_id):
    from dgre_rag.answers.reference import catalog
    from dgre_rag.answers.reference_values import values_for
    data=catalog(release_id) or {}
    records=[]
    for family,items in data.items():
        if isinstance(items,dict):records.extend(v for v in items.values() if isinstance(v,dict) and 'source' in v)
        elif isinstance(items,list):records.extend(v for v in items if isinstance(v,dict) and 'source' in v)
    result={}
    for question in ('capacité','apports annuels','débit moyen','volume','lame','pluie','historique','crue'):
        for row in values_for(records,data,question):
            candidates=result.setdefault(signature(row),[])
            if row not in candidates:candidates.append(row)
    return result


def finalize(service,answer):
    from dgre_rag.analytics.engine import calculate,compare_rows
    from dgre_rag.domain.models import Period
    from dgre_rag.answers.service import calculation_sentence
    checked=[];trusted={};sources={}
    if service.release_id:
        with connect(service.release_id) as db:
            for claim in answer.claims:
                if claim.get('kind')=='rating':
                    import json
                    from dgre_rag.analytics.engine import interpolate_rating
                    points=[json.loads(r[0])['record'] for r in db.execute("SELECT payload_json FROM structured_records WHERE family='rating_points'")]
                    points=[p for p in points if p['entity_id']==claim['entity_id'] and p['curve_id']==claim['curve_id']]
                    repeated=interpolate_rating(claim['height'],points,claim['on_date'],claim['curve_id'])
                    if any(repeated[k]!=claim[k] for k in ('value','unit','origin','evidence_ids')):raise ValueError('UNSUPPORTED_INTERPOLATION')
                    if not set(repeated['evidence_ids'])<={c['source_id'] for c in answer.citations}:raise ValueError('MISSING_EVIDENCE')
                    checked.append(claim)
            for citation in answer.citations:
                sid=citation.get('source_id')
                row=db.execute('SELECT * FROM sources WHERE source_id=?',(sid,)).fetchone()
                if not row or any(citation.get(k,row[k])!=row[k] for k in ('document_id','page_pdf','raw_text')):
                    raise ValueError('INVALID_CITATION')
                sources[sid]=dict(row)
                roles=source_roles(service.release_id).get(sid,set())
                if roles:sources[sid]['role']='value' if 'value' in roles else sorted(roles)[0]
            for fact in answer.facts+answer.table:
                oid=fact.get('observation_id')
                if oid:
                    row=db.execute('SELECT * FROM published_observations WHERE observation_id=?',(oid,)).fetchone()
                    if not row or signature(fact)!=signature(dict(row)):raise ValueError('UNSUPPORTED_CLAIM')
                    row=dict(row)
                    if any(fact.get(k) is not None and fact[k]!=row.get(k) for k in ('entity_id','event_date','event_time')):
                        raise ValueError('UNSUPPORTED_CLAIM')
                    proofs={r[0] for r in db.execute('SELECT source_id FROM observation_evidence WHERE observation_id=?',(oid,))}
                    if not proofs & sources.keys():raise ValueError('MISSING_EVIDENCE')
                    trusted[oid]=row
                else:
                    candidates=reference_rows(service.release_id).get(signature(fact),[])
                    if not candidates:raise ValueError('UNSUPPORTED_REFERENCE_VALUE')
                    row=next((r for r in candidates if set(r['evidence_ids'])<=sources.keys()),None)
                    if not row:raise ValueError('MISSING_EVIDENCE')
                    proofs=set(row['evidence_ids'])
                    if not proofs<=sources.keys():raise ValueError('MISSING_EVIDENCE')
                    oid='reference:'+':'.join(fact['evidence_ids'])+':'+fact['canonical_name']+':'+fact['period_start']
                    trusted[oid]=dict(fact,observation_id=oid)
                checked.append({'kind':'value','observation_id':oid,'value':fact['value_decimal'],
                    'unit':fact['unit'],'station':fact['canonical_name'],'period_start':fact['period_start'],
                    'period_end':fact['period_end'],'evidence_ids':sorted(proofs & sources.keys())})
            for calculation in answer.calculations:
                rows=[]
                for oid in calculation['input_ids']:
                    row=trusted.get(oid)
                    if row is None:
                        record=db.execute('SELECT * FROM published_observations WHERE observation_id=?',(oid,)).fetchone()
                        if record:row=dict(record)
                    if row is None:raise ValueError('UNKNOWN_CALCULATION_INPUT')
                    rows.append(row)
                if calculation['formula_id'] in ('difference','ratio_to_baseline','relative_anomaly','positive_deficit'):
                    if len(rows)!=2:raise ValueError('INVALID_CALCULATION_INPUTS')
                    repeated=compare_rows(*rows,calculation['formula_id'])
                else:
                    period=Period.model_validate(calculation['period']) if calculation.get('period') else None
                    repeated=calculate(calculation['formula_id'],rows,period,allow_partial=True,options=calculation.get('parameters'))
                if Decimal(repeated['value'])!=Decimal(calculation['value']) or repeated['unit']!=calculation['unit']:
                    raise ValueError('UNSUPPORTED_CALCULATION')
                if repeated['coverage']!=calculation['coverage']:raise ValueError('ALTERED_COVERAGE')
                if repeated.get('groups')!=calculation.get('groups'):raise ValueError('ALTERED_GROUPS')
                sentence=calculation_sentence(calculation)
                if sentence not in answer.text:answer.text+='\n\n'+sentence
                if calculation['coverage'].get('complete') is False and answer.status=='answered':answer.status='partial'
                checked.append({'kind':'calculation','formula_id':calculation['formula_id'],
                    'value':calculation['value'],'unit':calculation['unit'],'input_ids':calculation['input_ids']})
    answer.citations=list(sources.values())
    resolution=answer.temporal_resolution
    if resolution.get('period') and answer.status in ('answered','partial'):
        span=Period.model_validate(resolution['period'])
        for fact in answer.facts+answer.table:
            if fact.get('period_start') and not (str(span.start)<=fact['period_start']<=fact['period_end']<=str(span.end)):
                raise ValueError('TEMPORAL_EVIDENCE_MISMATCH')
        for calculation in answer.calculations:
            if calculation.get('period') and calculation['period']!=resolution['period']:
                raise ValueError('TEMPORAL_CALCULATION_MISMATCH')
        if resolution['origin']=='default_campaign':
            answer.text+=f'\n\nPériode utilisée : campagne {span.start.year}–{span.end.year}.'
        elif resolution['origin']=='question_in_campaign':
            from dgre_rag.answers.service import display_date
            answer.text+=f'\n\nPériode utilisée : du {display_date(str(span.start))} au {display_date(str(span.end))}.'
    if resolution:
        answer.plan['temporal_resolution']=resolution
        answer.conversation['temporal_resolution']=resolution
        if resolution.get('period'):answer.conversation['period']=resolution['period']
    answer.claims=list({str(c):c for c in checked}.values())
    answer.coverage=[c['coverage'] for c in answer.calculations]
    answer.validation={'version':'common-gate-v2','accepted':True,'sources_checked':len(sources),'structured_claims_checked':len(answer.claims),
        'scope':'Source identity, structured values and replayed calculations. Free prose is not certified by this gate.'}
    dump(data_dir()/'query_logs'/f'{answer.run_id}.final.json',
        {'answer':answer.model_dump(mode='json'),'finalized':datetime.now(timezone.utc).isoformat()})
    return answer
