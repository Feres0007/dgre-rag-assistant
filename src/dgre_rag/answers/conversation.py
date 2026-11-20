"""Conversation state and read-only data actions shared by UI and batch evaluation."""
import calendar
import csv
import io
import re
import uuid
from datetime import date
from decimal import Decimal
from dgre_rag.domain.models import Answer
from dgre_rag.domain.catalog import METRICS
from dgre_rag.ingestion.pipeline import plain
from dgre_rag.query.planner import entities,detect_period
from dgre_rag.storage.database import connect,dump
from dgre_rag.config import data_dir


def compare_values(a,b):
    """Use the calculation engine with explicit proof-backed reference inputs."""
    from dgre_rag.analytics.engine import compare_rows
    if a.get('scope','station')!=b.get('scope','station'):raise ValueError('INCOMPATIBLE_SCOPE')
    prepared=[]
    for row in (a,b):
        value=dict(row)
        if not value.get('observation_id'):
            proofs=value.get('evidence_ids',[])
            if not proofs:raise ValueError('MISSING_EVIDENCE')
            value['observation_id']='reference:'+':'.join(proofs)+':'+value['canonical_name']+':'+value['period_start']
        prepared.append(value)
    return compare_rows(*prepared)


def comparison_text(a,b,calculation):
    from dgre_rag.answers.service import display_number
    difference=Decimal(calculation['value']);unit=calculation['unit'].replace('m3','m³')
    if difference==0:return f"Les deux valeurs sont égales : **{display_number(a['value_decimal'])} {unit}**."
    high,low=(a,b) if difference>0 else (b,a)
    def label(row):return row['canonical_name']+' ('+row['period_start']+' / '+row['period_end']+')'
    return f"**{label(high)}** présente la valeur la plus élevée : **{display_number(high['value_decimal'])} {unit}**, contre **{display_number(low['value_decimal'])} {unit}** pour {label(low)}. L’écart est de **{display_number(str(abs(difference)))} {unit}**."


def result_rows(answer):
    """An empty filter result is intentional, not a fallback to its inputs."""
    if any(c.get('formula_id') in ('filter','rank') for c in answer.get('calculations',[])):
        return answer.get('table',[])
    return answer.get('table') or answer.get('facts',[])


def readable(rows):
    from dgre_rag.answers.service import display_number,display_date
    return [{'Station':r['canonical_name'],'Mesure':METRICS.get(r['metric_id'],(r['metric_id'],))[0],
             'Valeur':display_number(r['value_decimal']),'Unité':r['unit'].replace('m3','m³'),
             'Début':display_date(r['period_start']),'Fin':display_date(r['period_end'])} for r in rows]


def export_table(rows,citations=None):
    output=io.StringIO();values=readable(rows)
    if not values:return ''
    from dgre_rag.answers.service import source_reference
    sources={c['source_id']:source_reference(c) for c in (citations or [])}
    for value,row in zip(values,rows):
        value['Sources']=' ; '.join(dict.fromkeys(sources[s] for s in row.get('evidence_ids',[]) if s in sources))
    writer=csv.DictWriter(output,fieldnames=list(values[0]),delimiter=';');writer.writeheader()
    for row in values:
        writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return '\ufeff'+output.getvalue()


def respond(srv,question,context,use_llm,history):
    history=[h for h in history if h.get('release_id')==srv.release_id]
    previous=history[-1] if history else {}
    state=previous.get('conversation',{})
    q=plain(question).strip();effective=question;context=dict(context or {})
    def make(text,status='answered',rows=None,citations=None,presentation='text'):
        return Answer(status=status,text=text,question=question,run_id=uuid.uuid4().hex,release_id=srv.release_id,
                      table=rows or [],citations=citations or [],presentation=presentation)
    if not srv.release_id:return srv._ask(question,context,use_llm,history)
    presentation=next((p for words,p in [(('graphique','courbe','diagramme'),'chart'),(('telecharg','export','csv'),'export'),(('tableau','table '),'table'),(('ouvre la source','ouvre les sources','voir la source'),'sources')] if any(w in q for w in words)),'text')
    resolved=entities(question,srv.release_id)
    exact=[e for e in resolved if e.get('match_score',0)>=.9]
    period=detect_period(question)
    if 'mois suivant' in q and state.get('period'):
        from dgre_rag.domain.models import Period
        start=date.fromisoformat(state['period']['start']);month=start.month%12+1;year=start.year+(start.month==12)
        period=Period(start=date(year,month,1),end=date(year,month,calendar.monthrange(year,month)[1]))
    # A short clarification completes only a pending request; a new question replaces it.
    if previous.get('status')=='ambiguous' and state.get('pending') and not re.search(r'\b(quels?|quelles?|compare|montre|pourquoi|comment)\b',q):
        effective=state['pending']+' ; '+question
    elif re.match(r'^(et\b|pour la meme\b|la meme\b)',q) and state.get('request'):
        effective=plain(state['request'])
        if exact:
            old_names=state.get('names',[])
            for name in old_names:effective=re.sub(re.escape(plain(name)),exact[0]['canonical_name'],effective,flags=re.I)
            if not old_names:effective+=' ; station '+exact[0]['canonical_name']
        if period:
            effective=re.sub(r'\b\d{4}[-–/]\d{4}\b',f'{period.start.year}-{period.end.year}',effective)
            if period.start.month!=9 or period.end.month!=8:
                effective=re.sub(r'\b\d{4}-\d{2}-\d{2}\b|\b(?:janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+\d{4}\b','',effective)
                effective+=f' du {period.start.isoformat()} au {period.end.isoformat()}'
            context['period']=period.model_dump(mode='json')
        elif state.get('period'):context.setdefault('period',state['period'])
        # Unknown place must never inherit an old station silently.
        if re.match(r'^et\s+(a|au|aux)\s+',q) and not exact:effective=question
    action_only=presentation!='text' and not exact and not period and not any(w in q for w in ('mensuel','journalier','annuel','disponib'))
    from dgre_rag.query.temporal import resolved_context
    if not action_only:
        context,resolution=resolved_context(effective,srv.release_id,context)
    else:
        resolution=previous.get('temporal_resolution')
    answer=None
    if resolution and resolution.get('clarification'):
        answer=make(resolution['clarification'],'ambiguous')
    if action_only:
        data_previous=next((h for h in reversed(history) if h.get('table') or h.get('facts')),previous)
        rows=result_rows(data_previous)
        if presentation=='sources' and previous.get('citations'):
            answer=make('Voici les sources de la réponse précédente.',citations=previous['citations'],presentation='sources')
        elif rows:
            answer=make('Voici les valeurs du résultat précédent.' if presentation!='export' else 'Le tableau est prêt à être téléchargé.',rows=rows,citations=data_previous.get('citations',[]),presentation=presentation)
        else:answer=make('Quelles valeurs souhaitez-vous afficher ? Précisez une station, une mesure et une période.','ambiguous')
    if answer is None and re.search(r'compare\w*\s+(?:les|ces)\s+deux',q):
        selections=[]
        for h in reversed(history):
            for row in result_rows(h):
                key=(row.get('observation_id'),row.get('canonical_name'),row.get('metric_id'),row.get('period_start'))
                if key not in [k for k,_ in selections]:selections.append((key,row))
            if len(selections)>=2:break
        if len(selections)==2:
            a,b=[r for _,r in reversed(selections)]
            if a.get('observation_id') and b.get('observation_id'):
                try:
                    result=srv.compare(a['observation_id'],b['observation_id'])
                    from dgre_rag.answers.service import display_number
                    calc=result['calculation']
                    text=f"**{a['canonical_name']} : {display_number(a['value_decimal'])} {a['unit'].replace('m3','m³')}** ; **{b['canonical_name']} : {display_number(b['value_decimal'])} {b['unit'].replace('m3','m³')}**.\n\nL’écart ({a['canonical_name']} moins {b['canonical_name']}) est de **{display_number(calc['value'])} {calc['unit'].replace('m3','m³')}**."
                    if calc.get('relative_difference_percent') is not None:text+=f" Cela représente {display_number(str(round(Decimal(calc['relative_difference_percent']),2)))} % par rapport à {b['canonical_name']}."
                    answer=make(text,rows=[a,b],citations=result['citations'],presentation='table');answer.calculations=[calc]
                except ValueError:answer=make('Ces deux valeurs ne sont pas comparables : vérifiez les mesures, les unités, les périodes et les lacunes.','ambiguous')
            else:
                try:
                    calculation=compare_values(a,b)
                    evidence_ids=set(a.get('evidence_ids',[])+b.get('evidence_ids',[]))
                    citations=list({c['source_id']:c for h in history for c in h.get('citations',[]) if c['source_id'] in evidence_ids}.values())
                    answer=make(comparison_text(a,b,calculation),rows=[a,b],citations=citations,presentation='table');answer.calculations=[calculation]
                except ValueError:answer=make('Ces valeurs ne portent pas sur la même mesure, le même type de lieu ou des périodes comparables. Précisez les deux sélections.','ambiguous')
        else:answer=make('Quelles sont les deux valeurs à comparer ? Indiquez les stations ou les périodes.','ambiguous')
    eq=plain(effective)
    candidates=entities(effective,srv.release_id)
    if any(w in eq for w in ('debit','hydrom','crue')):candidates=[e for e in candidates if e['kind']=='hydro_station']
    elif any(w in eq for w in ('pluie','pluv')):candidates=[e for e in candidates if e['kind']=='rain_station']
    selected=[e for e in candidates if e.get('match_score',0)>=.9]
    if len(selected)>1 and selected[0]['match_score']>1 and selected[1]['match_score']<1:selected=selected[:1]
    comparison=bool(re.search(r'\bcompar\w*\b|\bdifference\b',eq))
    periods=re.findall(r'\b(\d{4})[-–/](\d{4})\b',effective)
    if answer is None and comparison and len(periods)==2 and len(selected)==1:
        metric='discharge_annual_mean' if 'debit' in eq and 'moyen' in eq else 'volume_annual' if 'volume' in eq else 'rainfall_annual' if selected[0]['kind']=='rain_station' else None
        if metric:
            rows=[]
            for y,z in periods:
                if int(z)!=int(y)+1:continue
                rows+=srv.query_observations(selected[0]['entity_id'],metric,f'{y}-09-01',f'{z}-08-31')
            if len(rows)==2:
                try:
                    calc=compare_values(*rows);answer=make(comparison_text(*rows,calc),rows=rows,citations=srv.get_evidence([r['observation_id'] for r in rows]),presentation='table');answer.calculations=[calc]
                except ValueError:answer=make('Les périodes ou la qualité des séries ne permettent pas ce calcul.','ambiguous')
            else:answer=make('Je ne dispose pas des deux valeurs annuelles nécessaires. Voici les valeurs retrouvées ; la comparaison ne peut pas être calculée.','partial' if rows else 'not_found',rows=rows,citations=srv.get_evidence([r['observation_id'] for r in rows]))
    if answer is None and comparison and 'barrage' in eq:
        from dgre_rag.answers.reference import catalog,norm
        data=catalog(srv.release_id) or {}
        dams=[r for r in data.get('dams',[]) if re.search(r'\b'+re.escape(norm(r['name']))+r'\b',norm(effective))]
        metric_word='capacité' if 'capacite' in eq else 'apports annuels' if any(w in eq for w in ('apport','recu')) else None
        if len(dams)==2 and metric_word:
            parts=[srv._ask(f"Quelle est la {metric_word} du barrage {d['name']} ?",context,use_llm=False) for d in dams]
            rows=[r for p in parts for r in p.table];citations=[c for p in parts for c in p.citations]
            if len(rows)==2:
                calc=compare_values(*rows);answer=make(comparison_text(*rows,calc),rows=rows,citations=citations,presentation='table');answer.calculations=[calc]
    if answer is None and ('anomalie' in eq or ('lacune' in eq and ('donnee' in eq or 'serie' in eq))):
        coverage=srv.get_coverage()
        issues=coverage['issues']
        text='Les contrôles signalent notamment :\n\n'+'\n'.join('- '+r['example'] for r in issues[:8])
        text+='\n\nLes tirets ne sont pas convertis en zéro. Une valeur annuelle publiée peut être consultable alors que sa série quotidienne ne permet pas un recalcul.'
        proofs=[r for issue in issues[:3] for r in srv.get_issues(issue['code'],limit=1) if r.get('source_id')]
        answer=make(text,citations=proofs)
    if answer is None and 'manque' in eq and 'debit' in eq and len(selected)==1:
        from dgre_rag.answers.reference import catalog
        records=(catalog(srv.release_id) or {}).get('hydro_summaries',[])
        record=next((r for r in records if r['code'] in (selected[0].get('codes') or '').split(',')),None)
        if record and record['fields'].get('mean',{}).get('value') is None and 'mean' in record['fields']:
            answer=make(f"La fiche de **{record['name']}** indique : **{record['fields']['mean']['raw']}**. Le débit moyen annuel n’est donc pas publié. Je ne remplace pas les observations manquantes par une estimation.",'unvalidated_data',citations=[record['source']])
    if answer is None and ('disponib' in eq or 'disposent' in eq or 'quelles donnees' in eq):
        metric='discharge_annual_mean' if 'debit' in eq and 'annuel' in eq else None
        if 'station' in eq and metric:
            rows=srv.query_observations(metric_id=metric)
            answer=make(f"{len(rows)} observations de débit moyen annuel sont consultables. Voici les stations et les périodes correspondantes.",rows=rows,citations=srv.get_evidence([r['observation_id'] for r in rows]),presentation='table')
        else:
            coverage=srv.get_coverage();counts=coverage['counts']
            text=f"Les deux annuaires couvrent **2022–2023** : pluie, débits, crues et notices de barrages. **{counts['published']} observations** sont consultables dans la base. Certaines autres informations restent dans les pages des PDF.\n\nVous pouvez demander une valeur, une série, une comparaison, un classement, un graphique ou un export. Les séries incomplètes sont signalées."
            if len(selected)==1:
                series=[r for r in coverage['series'] if r['entity_id']==selected[0]['entity_id']]
                text=f"Pour **{selected[0]['canonical_name']}**, {len(series)} séries sont suivies. "+text
            answer=make(text)
    series_request=any(w in eq for w in ('mensuelles','mensuels','journalieres','journaliers','serie')) or (presentation in ('table','chart','export') and any(w in eq for w in ('pluie','debit'))) or (any(w in eq for w in ('montre','affiche','liste')) and any(w in eq for w in ('pluie','pluv','debit')))
    from dgre_rag.query.planner import controlled_request
    controlled=controlled_request(eq)
    if answer is None and series_request and not controlled:
        all_stations='toutes les stations' in eq or 'tous les postes' in eq
        if len(selected)!=1 and not all_stations:answer=make('Pour quelle station souhaitez-vous consulter les valeurs ?','ambiguous')
        else:
            span=detect_period(effective)
            if not span and context.get('period'):
                from dgre_rag.domain.models import Period
                span=Period.model_validate(context['period'])
            if not span:answer=make('Pour quelle année hydrologique ? Par exemple 2022–2023.','ambiguous')
            else:
                rain=('debit' not in eq) if all_stations else selected[0]['kind']=='rain_station';monthly='mensuel' in eq
                metric=('rainfall_annual' if 'annuel' in eq else 'rainfall_monthly' if monthly else 'rainfall_daily') if rain else ('discharge_annual_mean' if 'annuel' in eq else 'discharge_monthly_mean' if monthly else 'discharge_daily_mean')
                rows=srv.query_observations(None if all_stations else selected[0]['entity_id'],metric,span.start,span.end)
                label='toutes les stations' if all_stations else selected[0]['canonical_name']
                answer=make(f"Voici les {len(rows)} valeurs disponibles pour **{label}**. Les observations manquantes ne sont pas remplacées par zéro.",status='answered' if rows else 'not_found',rows=rows,citations=srv.get_evidence([r['observation_id'] for r in rows]),presentation=presentation if presentation!='text' else 'table')
    if answer is None:answer=srv._ask(effective,context,use_llm,history)
    answer.question=question
    if not answer.temporal_resolution:answer.temporal_resolution=resolution or {}
    if not answer.table and not any(c['formula_id']=='filter' for c in answer.calculations):answer.table=list(answer.facts)
    unresolved={r['observation_id']:r for r in answer.table if r.get('observation_id') and not r.get('evidence_ids')}
    if unresolved:
        with connect(srv.release_id) as db:
            for row in db.execute('SELECT observation_id,source_id FROM observation_evidence'):
                if row['observation_id'] in unresolved:unresolved[row['observation_id']].setdefault('evidence_ids',[]).append(row['source_id'])
    if comparison and len(answer.table)==2 and not answer.calculations and answer.status=='answered':
        try:
            calculation=compare_values(*answer.table)
            answer.text+='\n\n'+comparison_text(*answer.table,calculation)
            answer.calculations=[calculation];answer.presentation='table'
        except ValueError:answer.limits.append('Les deux valeurs sont affichées, mais leur compatibilité ne permet pas de calculer un écart.')
    if presentation!='text' and answer.table:answer.presentation=presentation
    names=[e['canonical_name'] for e in selected]
    if not names and answer.table:names=list(dict.fromkeys(r['canonical_name'] for r in answer.table))
    # Retain previous request through presentation-only turns.
    remembered=state.get('request',effective) if action_only else effective
    remembered_names=state.get('names',[]) if action_only else names
    span=detect_period(effective)
    answer.conversation={'request':remembered,'names':remembered_names,'temporal_resolution':answer.temporal_resolution,'period':span.model_dump(mode='json') if span else context.get('period') or (state.get('period') if action_only else None),
                         'pending':effective if answer.status=='ambiguous' else None}
    if answer.citations and '**Source' not in answer.text:
        from dgre_rag.answers.service import source_reference
        answer.text+='\n\n**Sources :** '+' ; '.join(dict.fromkeys(source_reference(c) for c in answer.citations))+'.'
    dump(data_dir()/'query_logs'/f'{answer.run_id}.conversation.json',answer.model_dump(mode='json'))
    return answer
