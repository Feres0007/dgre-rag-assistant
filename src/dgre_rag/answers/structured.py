"""Queries against specialized, source-bound families of the active release."""
import json
import re
from decimal import Decimal
from dgre_rag.storage.database import connect
from dgre_rag.ingestion.pipeline import plain
from dgre_rag.query.planner import entities,detect_period
from dgre_rag.domain.models import Period


def specialized(question,release_id,context):
    q=plain(question)
    rating='lame' not in q and (any(w in q for w in ('tarage','interpol','hauteur tabulee')) or bool(re.search(r'hauteur de\s+\d',q)))
    gauging=any(w in q for w in ('jaugeage','residu sec','salinite','stagnant','station seche')) and not any(w in q for w in ('signifie','definition','qu’est','qu\'est','comment'))
    if not rating and not gauging:return None
    with connect(release_id) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='structured_records'").fetchone():return None
    candidates=[c for c in entities(question,release_id) if c.get('match_score',0)>=.9 and c['kind']==('hydro_station' if rating else 'gauging_station')]
    def result(text,status='ambiguous',**kwargs):return dict(text=text,status=status,citations=[],limits=[],table=[],**kwargs)
    if len(candidates)!=1:return result('Pour quelle station souhaitez-vous consulter '+('la courbe de tarage ?' if rating else 'les mesures ponctuelles ?'))
    entity=candidates[0]
    span=detect_period(question) or (Period.model_validate(context['period']) if context.get('period') else None)
    if span is None:return result('À quelle date ou sur quelle période souhaitez-vous consulter ces mesures ?')
    if rating:
        if span.start!=span.end:return result('À quelle date souhaitez-vous utiliser cette courbe de tarage ?')
        height=re.search(r'(\d+(?:[.,]\d+)?)\s*(cm|m)\b',q)
        if not height:return result('Quelle hauteur souhaitez-vous utiliser ? Précisez la valeur et son unité (cm ou m).')
        h=Decimal(height[1].replace(',','.'))/(100 if height[2]=='cm' else 1)
        with connect(release_id) as db:
            all_points=[json.loads(r[0])['record'] for r in db.execute("SELECT payload_json FROM structured_records WHERE family='rating_points'")]
        points=[p for p in all_points if p['entity_id']==entity['entity_id'] and p['valid_from']<=str(span.start) and p['valid_to']>=str(span.end)]
        curves={p['curve_id'] for p in points}
        if len(curves)!=1:return result('Je ne dispose pas d’une courbe de tarage unique et validée pour cette station et cette période.','unvalidated_data')
        from dgre_rag.analytics.engine import interpolate_rating,DataError
        try:calculated=interpolate_rating(h,points,span.start,next(iter(curves)))
        except DataError:return result('Cette hauteur ne permet pas une estimation fiable avec les points validés disponibles. Aucune extrapolation n’est effectuée.','unvalidated_data')
        from dgre_rag.answers.service import display_number
        qualifier='estimé par interpolation linéaire' if calculated['origin']=='estimated' else 'publié dans le tarage'
        proofs=list({p['source']['source_id']:p['source'] for p in points if p['source']['source_id'] in calculated['evidence_ids']}.values())
        return dict(text=f"À **{entity['canonical_name']}**, pour une hauteur de **{display_number(str(h))} m**, le débit {qualifier} est de **{display_number(calculated['value'])} m³/s**.",
            status='answered',table=[],citations=proofs,limits=['La validité est celle du document ; ce tarage ne décrit pas nécessairement la situation actuelle.'],
            claims=[{'kind':'rating','entity_id':entity['entity_id'],'height':str(h),'on_date':str(span.start),'curve_id':next(iter(curves)),**calculated}])
    metric='dry_residue' if 'residu' in q or 'salinite' in q else 'gauging_height' if 'cote' in q else 'gauging_discharge'
    with connect(release_id) as db:
        rows=[dict(r) for r in db.execute('''SELECT * FROM published_observations WHERE entity_id=? AND metric_id=?
            AND period_start>=? AND period_end<=? ORDER BY period_start,event_time''',(entity['entity_id'],metric,str(span.start),str(span.end)))]
        from dgre_rag.answers.service import evidence,fact_sentence
        citations=evidence(db,[r['observation_id'] for r in rows])
        for r in rows:r['evidence_ids']=[e['source_id'] for e in evidence(db,[r['observation_id']])]
        if not rows:
            blocked=[dict(r) for r in db.execute('''SELECT o.*,s.* FROM observations o JOIN observation_evidence e USING(observation_id)
                JOIN sources s USING(source_id) WHERE o.entity_id=? AND o.metric_id=? AND o.period_start>=? AND o.period_end<=?
                AND e.role='value' ''',(entity['entity_id'],metric,str(span.start),str(span.end)))]
            if blocked:return dict(text='Les cellules correspondantes portent : '+', '.join(sorted({r['raw_text'] or 'case vide' for r in blocked}))+'. Ces états ne sont pas convertis en débit nul.',
                status='unvalidated_data',citations=blocked,limits=[],table=[])
            return result('Aucune mesure ponctuelle exploitable retrouvée pour cette sélection.','not_found')
    return dict(text='\n\n'.join(fact_sentence(r) for r in rows),status='answered',citations=citations,limits=[],table=rows)
