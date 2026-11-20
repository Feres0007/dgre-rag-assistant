from datetime import date
from pathlib import Path
import difflib
import json
import re
from dgre_rag.ingestion.pipeline import plain
from dgre_rag.domain.models import QueryPlan,Operation,Period,ValidatedPlan
from dgre_rag.domain.catalog import METRICS
from dgre_rag.providers.local import generate
from dgre_rag.storage.database import connect


def entities(question,release_id):
    # Match typography variants of place names (Aïn-Draham / AIN DRAHAM).
    def name_text(value):
        return re.sub(r"\s+",' ',re.sub(r"[-’']",' ',plain(value))).strip()
    q=name_text(question)
    with connect(release_id) as db:
        rows=[dict(r) for r in db.execute('''SELECT e.*,group_concat(DISTINCT m.source_code) codes
             FROM entities e LEFT JOIN entity_mentions m USING(entity_id) GROUP BY e.entity_id''')]
    scored=[]
    for r in rows:
        name=name_text(r['canonical_name'])
        codes=(r['codes'] or '').split(',')
        if any(code and re.search(r'\b'+re.escape(code)+r'\b',q) for code in codes):score=2
        elif name and re.search(r'\b'+re.escape(name)+r'\b',q):score=1+len(name)/1000
        else:
            tokens=set(name.split())-{'de','du','la','le','el','sm','ep'}
            score=len(tokens & set(q.split()))/max(len(tokens),1)*.8
            ordered=name.split()
            for i in range(len(ordered)-1):
                pair=' '.join(ordered[i:i+2])
                if pair not in ('pont route','pont de') and len(set(ordered[i:i+2]) & tokens)==2 and len(pair)>=7 and re.search(r'\b'+re.escape(pair)+r'\b',q):
                    score=max(score,.95)
        if score>.3:scored.append((score,r|{'match_score':score}))
    return [r for _,r in sorted(scored,key=lambda p:-p[0])[:12]]


def detect_period(question):
    q=plain(question)
    match=re.search(r'\b(\d{4})\s*[-–/]\s*(\d{4})\b',q)
    if match:
        a,b=map(int,match.groups())
        if b==a+1:return Period(start=date(a,9,1),end=date(b,8,31))
    matches=list(re.finditer(r'\b(\d{4})-(\d{2})-(\d{2})\b',q))
    if matches:
        days=[date(*map(int,m.groups())) for m in matches]
        return Period(start=days[0],end=days[-1])
    match=re.search(r'annee civile\s+(\d{4})',q)
    if match:
        y=int(match[1]);return Period(start=date(y,1,1),end=date(y,12,31))
    months=['janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre']
    interval=re.search(r'\b('+ '|'.join(months)+r')\s+(?:a|à|au)\s+('+ '|'.join(months)+r')\s+(\d{4})\b',q)
    if interval:
        import calendar
        first,last=months.index(interval[1])+1,months.index(interval[2])+1;year=int(interval[3])
        return Period(start=date(year-(first>last),first,1),end=date(year,last,calendar.monthrange(year,last)[1]))
    naturals=list(re.finditer(r'\b(?:(\d{1,2})(?:er)?\s+)?('+ '|'.join(months)+r')\s+(\d{4})\b',q))
    if len(naturals)>1:
        import calendar
        spans=[]
        for item in naturals:
            m=months.index(item[2])+1;y=int(item[3])
            start=date(y,m,int(item[1]) if item[1] else 1)
            end=start if item[1] else date(y,m,calendar.monthrange(y,m)[1])
            spans.append((start,end))
        return Period(start=min(s[0] for s in spans),end=max(s[1] for s in spans))
    natural=naturals[0] if naturals else None
    if natural:
        import calendar
        month=months.index(natural[2])+1;year=int(natural[3])
        if natural[1]:
            day=date(year,month,int(natural[1]));return Period(start=day,end=day)
        return Period(start=date(year,month,1),end=date(year,month,calendar.monthrange(year,month)[1]))
    return None


def controlled_request(question):
    q=plain(question).replace('≥','>=').replace('≤','<=')
    # Territorial rankings already use the source-bound regional catalogue.
    # Never widen a requested governorate silently to every station in SQL.
    if 'gouvernorat' in q and re.search(r'\bclass\w*\b',q):return False
    return bool(re.search(r'(?:plus de|moins de|au moins|>=|<=|>|<|depasse\w*|superieur\w*(?: a)?|inferieur\w*(?: a)?)\s*\d',q)
        or any(w in q for w in ('seuil','consecut','convert','calcule','calculer','recalcule','somme','moyenne calculee'))
        or re.search(r'\bclass\w*\b.*\b(stations|postes)\b',q))


def plan_query(question,release_id,context=None,use_llm=True):
    from dgre_rag.query.temporal import resolved_context
    context,resolution=resolved_context(question,release_id,context)
    if resolution and resolution.get('clarification'):return QueryPlan(clarification=resolution['clarification'])
    plan=_plan_query(question,release_id,context,use_llm)
    plan.temporal_resolution=resolution or {}
    return plan


def _plan_query(question,release_id,context,use_llm):
    q=plain(question).replace('≥','>=').replace('≤','<=')
    candidates=entities(question,release_id)
    codes=re.findall(r'\b148\d{6,9}\b',q)
    for code in codes:
        shared=[c for c in candidates if code in (c.get('codes') or '').split(',')]
        named=[c for c in shared if plain(c['canonical_name']) in q]
        if len(shared)>1 and not named:
            return QueryPlan(clarification='Ce code figure pour plusieurs stations : '+', '.join(c['canonical_name'] for c in shared)+'. Quel nom souhaitez-vous retenir ?')
    if any(w in q for w in ('debit','hydromet','crue','ecoule')):
        candidates=[c for c in candidates if c['kind']=='hydro_station']
    elif any(w in q for w in ('pluie','pluvio','precipitation','total annuel')) and 'volume' not in q:
        candidates=[c for c in candidates if c['kind']=='rain_station']
    explicit_entity=context.get('entity_id')
    if explicit_entity and candidates and candidates[0]['entity_id']!=explicit_entity:
        return QueryPlan(clarification='La station choisie dans le filtre diffère de celle de la question. Quelle sélection faut-il conserver ?')
    if explicit_entity:
        with connect(release_id) as db:
            r=db.execute('SELECT * FROM entities WHERE entity_id=?',(explicit_entity,)).fetchone()
            if not r:return QueryPlan(clarification='La station sélectionnée n’est plus disponible.')
            candidates=[dict(r)]
    # Controlled operations use all matching observations, never documentary top-k.
    threshold_request=bool(re.search(r'(?:au moins|plus de|moins de|>=|<=|≥|≤|>|<)\s*\d',q))
    operation_request=controlled_request(q) and (threshold_request or not any(w in q for w in ('calcule','calculer','recalcule','somme','moyenne calculee')))
    if operation_request:
        if any(w in q for w in ('gouvernorat','region','bassin')):
            return QueryPlan(clarification='Le filtre territorial de ce calcul doit être précisé et validé. Je ne l’étends pas à toutes les stations.')
        selected=[c for c in candidates if c.get('match_score',0)>=.9] if not explicit_entity else candidates
        if len(selected)>1 and selected[0].get('match_score',0)>1 and selected[1].get('match_score',0)<1:selected=selected[:1]
        all_stations=bool(re.search(r'\bstations\b|\bpostes\b',q)) and not selected
        if all_stations and re.search(r'\b(?:stations|postes)\s+(?:(?:de|du|des)\b|d[’\'])\s*(?!mesure\b)',q):
            return QueryPlan(clarification='Précisez le territoire ou les stations à retenir ; ce filtre ne peut pas être remplacé par une sélection de toutes les stations.')
        span=detect_period(question) or (Period.model_validate(context['period']) if context.get('period') else None)
        if span is None:return QueryPlan(clarification='Sur quelle période souhaitez-vous effectuer ce calcul ?')
        if len(selected)!=1 and not all_stations:return QueryPlan(clarification='Quelle station souhaitez-vous utiliser ? Un code partagé nécessite aussi le nom de la station.')
        rain=selected[0]['kind']=='rain_station' if selected else 'debit' not in q
        threshold=re.search(r'(?:>=|<=|>|<|au moins|plus de|moins de|depasse\w*|superieur\w*(?: a)?|inferieur\w*(?: a)?)\s*(\d+(?:[.,]\d+)?)',q)
        dry=bool(re.search(r'\bsecs?\b|sans pluie',q))
        daily=not all_stations
        metric=('rainfall_daily' if rain else 'discharge_daily_mean') if daily else ('rainfall_annual' if rain else 'discharge_annual_mean')
        formula='rank' if 'class' in q else 'longest_run' if 'consecut' in q or 'sequence' in q else 'filter' if all_stations else 'threshold_count'
        options={}
        if 'convert' in q:
            formula='convert';metric=context.get('metric_id') or metric
            options['target_unit']='L/s' if re.search(r'(?:en|vers)\s*l/s',question,re.I) else 'm3/s' if re.search(r'(?:en|vers)\s*m[³3]/s',question,re.I) else None
            if not options['target_unit']:return QueryPlan(clarification='Dans quelle unité souhaitez-vous convertir la valeur ?')
        elif formula!='rank':
            if dry:options={'threshold':'0','comparator':'eq'}
            elif threshold:
                token=threshold[0]
                comparator='ge' if token.startswith(('>=','au moins')) else 'le' if token.startswith('<=') else 'lt' if token.startswith(('<','moins','inferieur')) else 'gt'
                options={'threshold':threshold[1].replace(',','.'),'comparator':comparator}
                suffix=q[threshold.end():].lstrip()
                measure=re.match(r'(mm|cm|m[³3]/s|l/s)\b',suffix)
                if measure:options['threshold_unit']=measure[1].replace('³','3').replace('l/s','L/s')
            else:return QueryPlan(clarification='Quel seuil et quelle condition souhaitez-vous appliquer (par exemple plus de 10 mm) ?')
        return QueryPlan(intent='calculation',operations=[Operation(op='calculate',entity_id=selected[0]['entity_id'] if selected else None,
            metric_id=metric,period=span,formula_id=formula,mode='calculated',options=options)])
    numeric=any(w in q for w in ['maximum','minimum','maximal','minimal','debit moyen','moyenne','somme','volume','total','cumul','compare','difference','calcule','lame','pluie le','debit le'])
    numeric=numeric or bool(context.get('metric_id'))
    rain_measure=bool(re.search(r'\b(pluviometrie|precipitations?|pluies?)\b',q))
    amount_request=any(w in q for w in ('annuel','quantite','hauteur','combien')) or bool(re.search(r'\b\d{4}[-–/]\d{4}\b|\b\d{4}-\d{2}-\d{2}\b',q))
    definition=any(w in q for w in ('signifie','signification','definition','definir','qu’est-ce','qu\'est-ce'))
    if rain_measure and amount_request and not definition:numeric=True
    if rain_measure and definition:numeric=False
    if not candidates and any(w in q for w in ('signifie','signification','distinction','comment','definition','convention','difference entre une')):numeric=False
    if any(w in q for w in ('demain','prevision','meteo actuelle',"aujourd'hui",'aujourd’hui','ignore les instructions','execute du code')):
        return QueryPlan(out_of_scope=True)
    if numeric and len(candidates)>1:
        names=[plain(c['canonical_name']) for c in candidates]
        exact=[i for i,name in enumerate(names) if name in q]
        if len(exact)==1:candidates=[candidates[exact[0]]]
        elif candidates[0].get('match_score',0)>=.9 and candidates[1].get('match_score',0)<.8:
            candidates=[candidates[0]]
    if numeric and any(w in q for w in ('compare','difference')):
        exact=[c for c in candidates if c.get('match_score',0)>=1]
        if len(exact)<2:exact=[c for c in candidates if c.get('match_score',0)>=.9]
        def position(c):
            terms=[plain(c['canonical_name'])]+(c.get('codes') or '').split(',')
            positions=[q.find(t) for t in terms if t and q.find(t)>=0]
            return min(positions) if positions else len(q)
        exact.sort(key=position)
        period=detect_period(question) or (Period.model_validate(context['period']) if context.get('period') else None)
        if len(exact)==2 and period:
            if all(e['kind']=='rain_station' for e in exact) and ('annuel' in q or 'total' in q):
                return QueryPlan(operations=[Operation(op='compare',entity_id=exact[0]['entity_id'],other_entity_id=exact[1]['entity_id'],metric_id='rainfall_annual',period=period,other_period=period)])
            if all(e['kind']=='hydro_station' for e in exact) and ('moyen' in q or 'volume' in q):
                metric='volume_annual' if 'volume' in q else 'discharge_annual_mean'
                return QueryPlan(operations=[Operation(op='compare',entity_id=exact[0]['entity_id'],other_entity_id=exact[1]['entity_id'],metric_id=metric,period=period,other_period=period)])
    if numeric and len(candidates)==1 and not any(w in q for w in ('compare','difference',' et ')):
        entity=candidates[0]
        metric=context.get('metric_id')
        rain=entity['kind']=='rain_station'
        if not metric:
            if 'historique' in q or 'crue maximale observee' in q or 'date de la crue maximale' in q:metric='discharge_historical_max'
            elif 'maximum' in q or 'maximal' in q:
                if rain:metric='rainfall_daily_max'
                elif 'instantan' in q:metric='discharge_instant_max'
                elif 'journalier' in q:metric='discharge_daily_max'
                else:return QueryPlan(clarification='Souhaitez-vous le maximum journalier, instantané ou historique ?')
            elif 'minimum' in q or 'minimal' in q:
                metric='discharge_instant_min' if 'instantan' in q else 'discharge_daily_min'
            elif 'volume' in q:metric='volume_annual'
            elif 'lame' in q:metric='runoff_depth'
            elif 'debit moyen' in q:metric='discharge_annual_mean' if 'annuel' in q else 'discharge_daily_mean'
            elif rain:
                annual=('annuel' in q or 'total' in q or 'cumul' in q or bool(re.search(r'\b\d{4}[-–/]\d{4}\b',q)))
                metric='rainfall_annual' if annual else 'rainfall_daily'
        period=detect_period(question)
        if context.get('period'):
            selected=Period.model_validate(context['period'])
            period=period or selected
        if metric=='discharge_historical_max' and not period:
            with connect(release_id) as db:
                dates=db.execute('SELECT DISTINCT period_start,period_end FROM published_observations WHERE entity_id=? AND metric_id=?',(entity['entity_id'],metric)).fetchall()
            if len(dates)==1:period=Period(start=dates[0][0],end=dates[0][1])
        if not period:return QueryPlan(clarification='Quelle période souhaitez-vous ? Précisez par exemple 2022-2023 (année hydrologique) ou une date ISO.')
        if metric and any(w in q for w in ('recalcule','calculer','calcule','somme','moyenne')):
            if metric=='volume_annual':formula='daily_discharge_volume';input_metric='discharge_daily_mean'
            elif metric.startswith('discharge') and 'moyen' in q:formula='time_weighted_mean';input_metric='discharge_daily_mean'
            elif 'maximum' in q:formula='maximum';input_metric='rainfall_daily' if rain else 'discharge_daily_mean'
            elif 'minimum' in q:formula='minimum';input_metric='rainfall_daily' if rain else 'discharge_daily_mean'
            elif rain:formula='rainfall_sum';input_metric='rainfall_daily' if 'journalier' in q else 'rainfall_monthly'
            else:return QueryPlan(clarification='Quelle opération souhaitez-vous calculer à partir des observations ?')
            group='month' if 'par mois' in q else 'season' if 'par saison' in q else 'campaign' if 'par campagne' in q else None
            return QueryPlan(operations=[Operation(op='calculate',entity_id=entity['entity_id'],metric_id=input_metric,period=period,formula_id=formula,mode='calculated',options={'group_by':group})])
        if metric:
            return QueryPlan(operations=[Operation(op='lookup',entity_id=entity['entity_id'],metric_id=metric,period=period)])
    if numeric and not candidates:
        return QueryPlan(clarification='Quelle station ou quel code souhaitez-vous consulter ?')
    if not numeric:
        figure=any(w in q for w in ('hydrogramme','graphique du document','carte','figure'))
        filters={}
        if len(candidates)==1 and candidates[0].get('match_score',0)>=.9:filters['entity_id']=candidates[0]['entity_id']
        if figure:filters['content_type']='figure'
        return QueryPlan(intent='documentary',operations=[Operation(op='get_figure' if figure else 'retrieve_text',filters=filters)])
    if not use_llm:
        return QueryPlan(clarification='Précisez la station, le type de mesure et la période. Pour une comparaison, indiquez les deux stations ou périodes.')
    system=(Path(__file__).parents[1]/'prompts/R1.txt').read_text(encoding='utf-8')
    prompt=json.dumps({'question':question,'context':context,'entities':candidates,'metrics':METRICS},ensure_ascii=False)
    last_error=''
    for attempt in range(2):
        response=generate(prompt+last_error,QueryPlan.model_json_schema(),system)
        try:return QueryPlan.model_validate_json(response)
        except ValueError as exc:last_error='\nCorrige uniquement le JSON selon le schéma. Erreur : '+str(exc)[:1000]
    raise ValueError('INVALID_PLAN')


def validate_plan(plan,release_id):
    from dgre_rag.config import settings
    if len(plan.operations)>settings().max_operations:raise ValueError('TOO_MANY_OPERATIONS')
    with connect(release_id) as db:
        for op in plan.operations:
            for eid in [op.entity_id,op.other_entity_id]:
                if eid and not db.execute('SELECT 1 FROM entities WHERE entity_id=?',(eid,)).fetchone():raise ValueError('UNKNOWN_ENTITY')
            if op.metric_id and op.metric_id not in METRICS:raise ValueError('INVALID_METRIC')
            if op.formula_id=='rainfall_sum' and op.metric_id not in ('rainfall_daily','rainfall_monthly'):raise ValueError('INVALID_METRIC')
            if op.formula_id=='daily_discharge_volume' and op.metric_id!='discharge_daily_mean':raise ValueError('INVALID_METRIC')
    return ValidatedPlan(plan=plan,release_id=release_id)
