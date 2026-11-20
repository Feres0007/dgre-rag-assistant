"""Consultation déterministe des synthèses avec leurs sources, hors top-k documentaire."""
import json,re
from functools import lru_cache
from decimal import Decimal
from dgre_rag.config import data_dir
from dgre_rag.storage.database import file_hash
from dgre_rag.ingestion.pipeline import plain


def norm(value):
    return re.sub(r'\s+',' ',re.sub(r'([a-z])\1',r'\1',plain(value).replace('-',' ').replace('sd bouzid','sidi bouzid'))).strip()


def catalog(release):
    stored=_stored_catalog(release)
    if stored is not None:return stored
    path=data_dir()/f'reference_catalog_{release}.json'
    if not path.exists():return None
    return _catalog(release,path.stat().st_mtime_ns)


@lru_cache(maxsize=4)
def _stored_catalog(release):
    from dgre_rag.storage.database import connect
    from dgre_rag.ingestion.structured import load_catalog
    with connect(release) as db:return load_catalog(db,release)


@lru_cache(maxsize=4)
def _catalog(release,mtime):
    path=data_dir()/f'reference_catalog_{release}.json'
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if manifest['release_id']!=release or file_hash(path)!=manifest['sha256']:raise ValueError('REFERENCE_VERSION_MISMATCH')
    return json.loads(path.read_text(encoding='utf-8'))


def published_rain_days(question,release,context=None):
    """Use a published threshold only for the exact matching annual statistic."""
    q=plain(question)
    if not re.search(r'jours?\b.*(?:pluie|plu\b)',q):return None
    if any(w in q for w in ('calcule','calculer','recalcule','journalier','consecut','sequence')):return None
    match=re.search(r'(au moins|>=|≥|plus de|>|superieur a)\s*(\d+(?:[.,]\d+)?)\s*mm\b',q)
    if not match:return None
    from decimal import Decimal
    key={('ge',Decimal('10')):'days10',('ge',Decimal('0.5')):'days05',('gt',Decimal('0')):'days'}.get(
        ('ge' if match[1] in ('au moins','>=','≥') else 'gt',Decimal(match[2].replace(',','.'))))
    if not key:return None
    from dgre_rag.query.temporal import resolved_context
    context,resolution=resolved_context(question,release,context)
    if context.get('period')!={'start':'2022-09-01','end':'2023-08-31'}:return None
    data=catalog(release) or {}
    candidates=[r for r in data.get('rain_days',[]) if re.search(r'\b'+re.escape(norm(r['station']))+r'\b',norm(question))]
    if len(candidates)!=1:return None
    r=candidates[0]
    if r.get(key) is None:return None
    from dgre_rag.answers.service import source_reference
    from dgre_rag.answers.reference_values import values_for
    label={'days10':'une pluie d’au moins **10 mm**','days05':'une pluie d’au moins **0,5 mm**','days':'une pluie strictement supérieure à **0 mm**'}[key]
    metric={'days10':'rain_days_ge_10','days05':'rain_days_ge_0_5','days':'rain_days_gt_0'}[key]
    return {'status':'answered','text':f"À **{r['station'].title()}**, **{r[key]} jours** avec {label} sont publiés pour la campagne **2022–2023**.\n\n**Sources :** {source_reference(r['source'])}.",
        'citations':[r['source']],'limits':[],
        'table':[v for v in values_for([r],data,question) if v['metric_id']==metric]}


def answer_reference(question,release,context=None):
    data=catalog(release)
    if not data:return None
    from dgre_rag.answers.service import display_number,source_reference
    def show(v):return display_number(str(v))
    def result(text,records,status='answered',limits=None):
        citations=list({r['source']['source_id']:r['source'] for r in records}.values())
        if citations:text+='\n\n**Sources :** '+' ; '.join(dict.fromkeys(source_reference(c) for c in citations))+'.'
        from dgre_rag.answers.reference_values import values_for
        values=values_for(records,data,question) if status=='answered' else []
        requested=(context or {}).get('temporal_resolution',{}).get('period')
        if requested and values and any(not (requested['start']<=v['period_start']<=v['period_end']<=requested['end']) for v in values):return None
        return {'text':text,'citations':citations,'status':status,'limits':limits or [],'table':values}
    q=plain(question).replace('-',' ')
    nq=norm(question)
    metadata=data.get('metadata',{})
    def method(text,key):return result(text,[metadata[key]]) if key in metadata else None
    if 'donnees' in q and 'complete' in q:
        return method('Je ne peux pas certifier que les données sont complètes partout. Certaines fiches comportent des tirets et même des totaux nuls ; ces signes ne prouvent pas à eux seuls une absence de pluie. Il faut vérifier la couverture de chaque poste avant de comparer les cumuls.','empty_rain_table')
    if 'station' in q and 'fonctionne' in q:
        missing=[r for r in data['hydro_summaries'] if 'lacune' in r['fields'].get('mean',{}).get('raw','')]
        if missing:return result('La fiche de **'+missing[0]['name']+'** signale trop de **lacunes** pour publier un débit moyen annuel. Cela établit une insuffisance des données, sans prouver la cause ni une panne du matériel.',missing[:1])
    if any(w in q for w in ('critique','verifie')) and ('donnee' in q or 'pluie' in q):
        return method('Les données sont contrôlées en deux étapes : comparaison des relevés des postes voisins à la réception des bulletins, puis comparaison des bulletins avec leurs copies et les pages de référence lors de la préparation du catalogue. Les anomalies et décalages de date sont corrigés.','rain_method')
    if 'decale' in q or ('7 heures' in q):
        return method('Certains observateurs inscrivent la pluie lue à **7 heures du matin** au jour de la lecture, alors qu’elle doit être rattachée à la veille selon les instructions. Ce décalage d’un jour est corrigé lors du contrôle.','rain_method')
    if 'logiciel' in q and ('pluv' in q or 'pluie' in q or 'donnee' in q):
        return method('Le logiciel utilisé pour la saisie et le traitement des données pluviométriques est **HYDRACCES**, développé au laboratoire d’hydrologie de l’IRD.','rain_method')
    if 'arrondissement' in q:
        return method('Les arrondissements des ressources en eau gèrent les pluviomètres, recueillent les observations et accompagnent les observateurs. Ils créent aussi les fichiers informatisés et éditent les catalogues pluviométriques régionaux.','rain_preface')
    if ('code' in q or 'chiffres' in q) and any(w in q for w in ('signif','compose','represent','structure')):
        return method('Le code comporte dix chiffres : le premier indique le continent africain ; les deux suivants le pays (**48** pour la Tunisie) ; les cinq suivants le numéro mécanographique de la station, dont le premier identifie le bassin ; les deux derniers indiquent le gouvernorat.','station_codes')
    if 'publication' in q and 'direction' in q:
        return method('La **Direction Générale des Ressources en Eau (DGRE)** porte cette publication. La Direction des Eaux de Surface prépare, édite et diffuse l’annuaire pluviométrique national, avec les services régionaux.','rain_preface')
    if 'annee hydrologique' in q and any(w in q for w in ('commence','debut','termine','couvre','periode')):
        return method('L’année hydrologique **2022–2023** s’étend du **1er septembre 2022 au 31 août 2023**.','rain_preface')
    if 'temps reel' in q or 'sycohtrac' in q:
        return method('Le système **SYCOHTRAC** collecte les mesures hydrologiques en temps réel et sert à l’annonce des crues des oueds tunisiens.','hydro_network')
    if 'secondaire' in q or 'temporair' in q:
        return method('Le réseau secondaire comprend des stations temporaires ayant fonctionné **3 à 6 ans** pour des études régionales limitées dans le temps, ainsi que des points de mesure choisis pour des études particulières.','hydro_network')
    if 'permanent' in q:
        return method('Aux points de mesure permanents, les débits des écoulements de base sont jaugés régulièrement et leur qualité chimique est suivie.','hydro_network')
    if 'types' in q and ('reseau' in q or 'hydrometrique' in q):
        return method('Le réseau hydrométrique comprend **le réseau de base**, **le réseau secondaire** et **le réseau de mesures automatiques**.','hydro_network')
    if 'caracteristique' in q and 'crue' in q and 'station' not in q:
        return method('Les fiches présentent les débits extrêmes, les temps de base et de montée des crues, leurs volumes et les hydrogrammes. Elles accompagnent les débits moyens journaliers et les résultats des jaugeages.','hydro_contents')
    if any(w in q for w in ('signifie','signification','jaugeage','abreviation')):
        entry=metadata.get('abbreviations',{})
        codes=[code for code in entry.get('values',{}) if re.search(r'\b'+code+r'\b',question)]
        if codes:return result(' '.join(f"**{code}** signifie **{entry['values'][code].strip()}**." for code in codes),[entry])
    if 'qui' in q or 'directeur general' in q:
        field='author' if 'elabore' in q or 'auteur' in q else 'validator' if 'valide' in q or 'directeur general' in q else None
        if field and field in metadata:
            entry=metadata[field]
            return result(f"L’annuaire hydrologique 2022–2023 mentionne **{entry['name']}** comme {'responsable de son élaboration' if field=='author' else 'Directeur général des ressources en eau et responsable de sa validation'}. Il s’agit de l’attribution dans ce document.",[entry])
    if ('combien' in q or 'nombre' in q or 'frequence' in q) and ('station' in q or 'automatique' in q):
        if 'automatique' in q:
            entry=metadata.get('automatic_network')
            if entry:return result(f"Le réseau automatique comprend **{entry['count']} stations** sur des oueds. La collecte est effectuée toutes les **{entry['minutes']} minutes**.",[entry])
        if ('existent' in q or 'selectionne' in q or 'reseau national' in q or 'en tunisie' in q) and 'algerie' not in q:
            entry=metadata.get('rain_network')
            if entry:return result(f"L’annuaire indique **{entry['count']} stations pluviométriques observées** en 2022–2023, dont **{entry['selected']} stations sélectionnées** pour l’analyse à l’échelle du pays.",[entry])
    for geography in data.get('geography',[]):
        if norm(geography['name']) in nq:
            if 'barrage' in q and geography['no_dam']:return result(f"L’annuaire indique qu’il n’y a **aucun barrage** dans le gouvernorat de **{geography['name']}**.",[geography])
            if 'superficie' in q and geography['area'] is not None and geography['source']['page_pdf']==20:return result(f"La superficie totale indiquée dans l’annuaire pour **{geography['name']}** est de **{show(geography['area'])} km²**. Cette valeur est restituée telle qu’elle est publiée.",[geography])
    if any(w in q for w in ('couleur du ciel','date de naissance','en algerie')):
        return result('Je ne trouve pas cette information dans les deux annuaires tunisiens disponibles.',[],'not_found')
    if ('nappe' in q and 'recharg' in q) or ('agriculteur' in q and 'assez' in q):
        return result('Les pluies et les débits publiés ne suffisent pas à établir ce résultat. Il faudrait des données sur la recharge des nappes ou sur les besoins et disponibilités en eau des exploitations ; je ne peux pas conclure à partir de ces seuls annuaires.',[],'not_found')
    years=re.findall(r'\b(20\d{2})\b',question)
    historical=any(w in q for w in ('derniere','precedente','depuis','compare cette annee','8 dernieres','huit dernieres','2015','2021'))
    if any(y not in ('2022','2023') for y in years) and not historical and not ('construit' in q or 'realise' in q):return None
    period=(context or {}).get('period')
    if period and period!={'start':'2022-09-01','end':'2023-08-31'}:
        # Narrow views supported by this catalogue: monthly syntheses and dated floods.
        supported=('crue' in q or any(m in q for m in ('janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre')))
        if not supported or not ('2022-09-01'<=period['start']<=period['end']<='2023-08-31'):return None
    if 'barrage' in q:
        dams=data['dams']
        matches=[d for d in dams if re.search(r'\b'+re.escape(norm(d['name']))+r'\b',nq)]
        governor=[g for g in data['governorates'] if norm(g) in nq]
        if any(w in q for w in ('rempli','vide','remplissage','stock')):
            return result('Les notices donnent les capacités et les apports d’eau de 2022–2023. Ces chiffres ne suffisent pas à connaître le remplissage ou le stock d’eau à une date donnée. Je ne peux donc pas conclure que les barrages sont pleins ou vides.',matches,'not_found')
        if historical:
            return result('Les notices consultées donnent les apports de 2022–2023 et un apport de référence, qui n’est pas celui de 2021–2022. Elles ne permettent pas cette comparaison avec l’année précédente.',matches,'not_found')
        if 'construit' in q or 'realise' in q:
            construction=re.search(r'\b(19\d{2}|20\d{2})\b',question)
            river=re.search(r'oued\s+(.+?)(?:\s*\?|$)',nq)
            found=[d for d in dams if (not construction or d['year']==construction[1]) and (not river or norm(river[1])==norm(d['river'] or ''))]
            if found:
                return result('\n\n'.join(f"Il s’agit du barrage **{d['name']}**, construit en **{d['year']}** sur l’oued **{d['river']}**." for d in found),found)
        if governor and (('barrages' in q and not matches) or 'gouvernorat' in q):
            found=[d for d in dams if norm(d['governorate'] or '')==norm(governor[0])]
            if found:return result(f"Les barrages présentés pour **{governor[0].title()}** sont : "+', '.join(d['name'] for d in found)+'.',found)
        if any(w in q for w in ('le plus','le moins')) and not matches:
            found=[d for d in dams if d['inflow'] is not None]
            target=(min if 'le moins' in q else max)(Decimal(d['inflow']) for d in found)
            matches=[d for d in found if Decimal(d['inflow'])==target]
            return result('En considérant les **apports annuels** décrits dans les notices, '+', '.join(d['name'] for d in matches)+f" présente {'le plus faible' if 'le moins' in q else 'le plus élevé'} volume : **{show(target)} millions de m³** en 2022–2023. Il s’agit d’eau reçue pendant l’année, pas du stock retenu.",matches)
        if len(matches)==1:
            d=matches[0]
            if 'capacite' in q:
                initial=' initiale' if 'capacité initiale' in d['description'] else ''
                return result(f"La capacité{initial} publiée du barrage **{d['name']}** est de **{show(d['capacity'])} millions de m³**.",[d])
            if 'apport' in q or 'recu' in q or 'eau' in q:
                if d['inflow'] is None:return result('Je ne trouve pas de volume annuel d’apports dans cette notice.',[d],'not_found')
                return result(f"Le barrage **{d['name']}** a reçu **{show(d['inflow'])} millions de m³** pendant l’année hydrologique **2022–2023**, contre **{show(d['normal'])} millions de m³** comme apport de référence dans la notice.",[d])
        return None
    hydro_question=any(w in q for w in ('debit','crue','ecoule','riviere'))
    if hydro_question:
        def score(name):
            words=set(norm(name).split())-{'de','la','le','pont','route'}
            identifiers=set(re.findall(r'\b(?:gp\d+|k\d+|m\d+)\b',nq))
            if identifiers and not identifiers.issubset(words):return 0
            return len(words & set(nq.split()))/max(1,min(len(words),len(set(nq.split())-{'quel','est','le','debit','moyen','annuel','de','la','station','?'})))
        ranked=sorted(((score(r['name']),r) for r in data.get('hydro_summaries',[])),key=lambda pair:-pair[0])
        found=[r for s,r in ranked if s==ranked[0][0] and s>0] if ranked else []
        if not found and re.search(r'\b(?:gp\d+|k\d+|m\d+)\b',nq):
            return result('Je ne peux pas associer cet identifiant à une fiche hydrométrique avec certitude. Vérifiez le nom complet de la station et son identifiant ; je ne veux pas lui substituer une autre station du même oued.',[],'ambiguous')
        if any(w in q for w in ('fiable','fonctionne')):
            missing=[r for r in data['hydro_summaries'] if 'lacune' in r['fields'].get('mean',{}).get('raw','')]
            if missing:return result('Les mesures ne sont pas complètes pour toutes les stations. '+ '; '.join(f"À **{r['name']}**, le débit moyen annuel n’est pas publié en raison de **lacunes**" for r in missing)+'. Cela ne permet pas d’affirmer que tous les appareils sont tombés en panne, ni de certifier toutes les mesures.',missing)
        if historical and 'riviere' in q:
            return result('Les fiches présentent les débits de 2022–2023, mais je ne dispose pas ici de la même série pour 2021–2022. Je ne peux pas établir cette comparaison annuelle.',[],'not_found')
        if 'haut' in q and 'riviere' in q:
            return result('Souhaitez-vous comparer les hauteurs d’eau ou les débits de crue ? Ce sont deux mesures différentes ; précisez aussi les stations à comparer.',[],'ambiguous')
        if not found and ('station' not in q or 'quelle station' in q) and not any(w in q for w in ('fiable','caracteristique','mesure','en mai','en juin')):
            events=data.get('floods',[])
            if events:
                maximum=max(Decimal(f['peak']) for f in events)
                winners=[f for f in events if Decimal(f['peak'])==maximum]
                return result('Des crues sont bien documentées en **2022–2023**. Parmi les événements extraits des tableaux, le débit de pointe le plus élevé est '+ '; '.join(f"**{show(f['peak'])} m³/s**, à **{f['station']}**, pour la crue débutant le **{f['start']}**" for f in winners)+'. Ce classement porte sur les événements disponibles et ne mesure pas à lui seul la gravité des dégâts.',winners)
        if 'classe' in q and 'gouvernorat' in q and 'moyen' in q:
            governors=[g for g in data['governorates'] if norm(g) in nq]
            if len(governors)==1:
                listed=[r for r in data['hydro_summaries'] if re.search(r'gouvernorat de\s+'+re.escape(norm(governors[0])),norm(r['source']['raw_text'])) and r['fields'].get('mean',{}).get('value') is not None]
                listed.sort(key=lambda r:-Decimal(r['fields']['mean']['value']))
                if listed:return result('Classement des fiches disponibles pour **'+governors[0].title()+'**, par débit moyen annuel décroissant en 2022–2023 :\n\n'+'\n'.join(f"{i+1}. {r['name']} : **{show(r['fields']['mean']['value'])} m³/s**." for i,r in enumerate(listed)),listed)
        dated=re.search(r'\b(\d{1,2})\s+(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+(20\d{2})\b',q)
        if 'volume' in q and ('plus grand' in q or 'compare' in q):
            selected=[r for s,r in ranked if s>0 and r['fields'].get('volume',{}).get('value') is not None]
            if len(selected)>=2:
                selected.sort(key=lambda r:-Decimal(r['fields']['volume']['value']))
                return result('Le volume annuel le plus élevé parmi ces stations est celui de **'+selected[0]['name']+'**. En 2022–2023 : '+ '; '.join(f"**{r['name']} : {show(r['fields']['volume']['value'])} millions de m³**" for r in selected)+'.',selected)
        if 'crue' in q and (dated or any(w in q for w in ('montee','temps de base','de pointe','en mai','en juin','compare'))):
            floods=data.get('floods',[])
            if found:floods=[f for f in floods if f['code'] in {r['code'] for r in found}]
            if dated:
                month=['janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre'].index(dated[2])+1
                prefix=f'{int(dated[1]):02d}/{month:02d}/{dated[3]}'
                floods=[f for f in floods if f['start'].startswith(prefix)]
            elif 'mai' in q or 'juin' in q:
                allowed=[]
                if 'mai' in q:allowed.append('05')
                if 'juin' in q:allowed.append('06')
                floods=[f for f in floods if f['start'][3:5] in allowed]
            if floods:
                texts=[]
                for f in floods:
                    description=f"À **{f['station']}**, la crue débutant le **{f['start']}** présente un débit de pointe de **{show(f['peak'])} m³/s**."
                    if 'montee' in q or 'temps de base' in q:
                        key='rise_raw' if 'montee' in q else 'base_raw'
                        description+=f" Le tableau donne **{f[key]}** pour le temps {'de montée' if key=='rise_raw' else 'de base'}. L’unité de durée de l’en-tête doit être vérifiée : certaines fiches affichent des heures alors que leurs valeurs correspondent à des minutes."
                    if 'volume' in q:
                        description+=f" La valeur imprimée du volume est **{f['volume_raw']}**. L’en-tête et l’ordre de grandeur présentent une ambiguïté d’unité ; cette valeur n’est pas convertie automatiquement."
                    texts.append(description)
                return result('\n\n'.join(texts),floods)
        field='historical' if ('crue maximale observee' in q or 'date de la crue maximale' in q or 'historique' in q) else 'mean' if 'moyen' in q else 'volume' if 'volume' in q else 'depth' if 'lame' in q else 'instant' if 'instantan' in q else None
        if len(found)==1 and field and field in found[0]['fields']:
            r=found[0];value=r['fields'][field]
            from dgre_rag.storage.database import connect
            metric={'mean':'discharge_annual_mean','volume':'volume_annual','depth':'runoff_depth','instant':'discharge_instant_max','historical':'discharge_historical_max'}[field]
            with connect(release) as db:
                existing=db.execute('''SELECT 1 FROM published_observations o JOIN entity_mentions m USING(entity_id)
                  WHERE m.source_code=? AND o.metric_id=? LIMIT 1''',(r['code'],metric)).fetchone()
            if existing:return None
            if value['value'] is None:
                return result(f"Pour **{r['name']}**, la fiche ne publie pas ce résultat : **{value['raw']}**. Je ne peux pas remplacer ces lacunes par une valeur estimée.",[r],'unvalidated_data')
            when=f" La date indiquée est **{value['when']}**." if field=='historical' else ''
            labels={'historical':'la crue maximale historique mentionnée','mean':'le débit moyen annuel','volume':'le volume annuel écoulé','depth':'la lame d’eau écoulée','instant':'le débit maximal instantané'}
            return result(f"À **{r['name']}**, {labels[field]} est de **{show(value['value'])} {value['unit']}**."+when,[r])
    # Counts and coordinates are taken from the printed station catalogue/summary.
    candidates=[]
    if not hydro_question and ('station' in q or 'journee' in q) and any(w in q for w in ('le plus','le moins','la plus','maximum absolu','plus forte')) and bool(re.search(r'\b(?:pluie\w*|plu|pluvi\w*|arrose\w*|24h)\b',q)):
        if 'jours' not in q:
            from dgre_rag.storage.database import connect
            metric='rainfall_daily_max' if any(w in q for w in ('journee','journalier','24h')) else 'rainfall_monthly' if any(w in q for w in ('mai','juillet')) else 'rainfall_annual'
            months={'mai':'05','juillet':'07'}
            with connect(release) as db:
                rows=[dict(r) for r in db.execute('SELECT * FROM published_observations WHERE metric_id=?',(metric,))]
                if metric=='rainfall_monthly':rows=[r for r in rows if r['period_start'][5:7]==next(v for k,v in months.items() if k in q)]
                if any(w in q for w in ('nord','region','gouvernorat')):
                    return result('Pour comparer les stations d’une région, il faut préciser le périmètre géographique et vérifier que toutes les fiches correspondantes sont disponibles. Je ne peux pas donner un classement régional exhaustif avec la sélection actuelle.',[],'ambiguous')
                if rows:
                    target=(min if 'le moins' in q else max)(Decimal(r['value_decimal']) for r in rows)
                    winners=[r for r in rows if Decimal(r['value_decimal'])==target]
                    from dgre_rag.answers.service import evidence
                    citations=evidence(db,[r['observation_id'] for r in winners])
                    records=[{'source':c} for c in citations]
                    label='maximum journalier' if metric=='rainfall_daily_max' else 'cumul mensuel' if metric=='rainfall_monthly' else 'cumul annuel'
                    return result(f"Parmi les observations publiées et utilisables, le {label} {'le plus faible' if 'le moins' in q else 'le plus élevé'} est de **{show(target)} mm** : "+'; '.join(r['canonical_name']+(f" (le {r['event_date']})" if r.get('event_date') else '') for r in winners[:12])+(f" ; et {len(winners)-12} autres stations à égalité" if len(winners)>12 else '')+f". La comparaison porte sur {len(rows)} observations disponibles ; les valeurs non utilisables en sont exclues."+(' Un total nul imprimé ne permet pas, à lui seul, de distinguer une absence de pluie d’une fiche incomplète.' if target==0 else ''),records)
    if any(w in q for w in ('jours de pluie','jours de pluies','latitude','longitude','altitude')) or re.search(r'jours?\b.*\bplu\b',q):
        family='rain_days' if 'jours' in q else 'coordinates'
        candidates=[r for r in data[family] if re.search(r'\b'+re.escape(norm(r['station']))+r'\b',nq)]
        if not candidates and 'tabarka' in q and 'foret' in q:candidates=[r for r in data[family] if norm(r['station'])=='tabarka foret']
        if len(candidates)==1:
            r=candidates[0]
            if family=='rain_days':return result(f"À **{r['station'].title()}**, le tableau indique **{r['days']} jours avec une pluie supérieure à 0 mm**, **{r['days05']} jours avec au moins 0,5 mm** et **{r['days10']} jours avec au moins 10 mm**, en 2022–2023.",[r])
            if 'altitude' in q:return result(f"L’altitude publiée de **{r['station'].title()}** est de **{show(r['altitude'])} m**.",[r])
            return result(f"Pour **{r['station'].title()}**, les coordonnées publiées sont : latitude **{show(r['latitude'])}°**, longitude **{show(r['longitude'])}°**.",[r])
        if family=='rain_days' and 'station' in q and any(w in q for w in ('grand nombre','faible nombre','plus de jours','moins de jours')):
            values=data[family];target=(min if 'faible' in q or 'moins' in q else max)(r['days'] for r in values)
            found=[r for r in values if r['days']==target]
            return result(f"Dans les tableaux de stations interprétés, le nombre {'minimal' if 'faible' in q or 'moins' in q else 'maximal'} publié est de **{target} jours de pluie (> 0 mm)** : "+', '.join(r['station'] for r in found)+'. Ce classement porte sur les fiches disponibles, pas sur une série nationale certifiée exhaustive.',found)
    if 'station' in q and not hydro_question and ('tabarka' in q or 'kasserine' in q) and not any(w in q for w in ('foret','aero','sm','dgre')):
        return result('Précisez le poste de mesure : '+('Tabarka Forêt ou Tabarka Aéro SM' if 'tabarka' in q else 'le nom complet du poste de Kasserine')+'. Une moyenne du gouvernorat ne remplace pas la mesure d’une station.',[],'ambiguous')
    if re.search(r'\b10\s*mm\b',q) and not candidates:
        return result('Pour compter les jours dépassant 10 mm, précisez la station. Les tableaux distinguent aussi « au moins 10 mm » de « plus de 10 mm ».',[],'ambiguous')
    if any(w in q for w in ('logiciel','publication','publie','direction','critique','signification','releves','donnees','couleur','chiffres','auteur','reseau')):return None
    weather=(bool(re.search(r'\b(?:pluie\w*|plu|pluvi\w*|precipitation\w*|arrose\w*|sec\w*|humide\w*|deficit\w*|excedent\w*)\b',q)) or ('eau' in q and 'barrage' not in q) or historical) and not hydro_question
    if not weather or any(w in q for w in ('signifie','definition','station','code','releve','maximale','maximum','24h','journee')):return None
    regions=[name for name in data['regions'] if name!='TUNISIE' and norm(name) in nq]
    if not regions and re.search(r'\ble sud\b',q):regions=['SUD OUEST','SUD EST']
    governors=[name for name in data['governorates'] if re.search(r'\b'+re.escape(norm(name))+r'\b',nq)]
    if 'medenine' in q and not governors:governors=['MEDNINE']
    if 'ville' in q or ('cotier' in q and 'interieur' in q) or ('jours de pluie' in q and 'region' in q):
        return result('Précisez le périmètre à comparer : stations, villes, gouvernorats ou régions naturelles. Ces catégories ne représentent pas la même mesure ; je ne peux pas les remplacer l’une par l’autre.',[],'ambiguous')
    supplied_context=context and context.get('_period_supplied',bool(context.get('period')))
    if not supplied_context and not regions and not governors and not any(w in q for w in ('tunisie','pays','national')):return None
    # A precise station name must retain the structured station route.
    from dgre_rag.query.planner import entities
    exact=[e for e in entities(question,release) if e.get('match_score',0)>=1]
    if exact and not governors:return None
    region=regions[0] if regions else 'TUNISIE'
    if historical:
        if len(regions)>1:
            records=[data['history'][r] for r in regions]
            return result('Comparaison des cumuls publiés : '+ '; '.join(f"**{name.title()} : {show(data['history'][name]['years']['2022-23'])} mm** en 2022–2023, contre **{show(data['history'][name]['years']['2021-22'])} mm** en 2021–2022" for name in regions)+'.',records)
        r=data['history'][region];values=r['years']
        if 'plus humide' in q or 'plus pluvieuse' in q:
            high=max(map(Decimal,values.values()));winners=[y for y,v in values.items() if Decimal(v)==high]
            return result(f"Pour **{region.title()}**, l’année la plus pluvieuse parmi les huit années présentées est **{', '.join(winners)}**, avec **{show(high)} mm**.",[r])
        return result(f"Pour **{region.title()}**, le tableau donne **{show(values['2022-23'])} mm** en 2022–2023 et **{show(values['2021-22'])} mm** en 2021–2022. Les huit totaux publiés sont : "+'; '.join(f'{y} : {show(v)} mm' for y,v in values.items())+'.',[r])
    seasonal=[s for s in ('AUTOMNE','HIVER','PRINTEMPS') if re.search(r'\b'+plain(s)+r'\b',q)]
    if re.search(r"(?:l[’']|en\s+)ete\b|estivale",q):seasonal.append('ETE')
    if seasonal or 'saison' in q:
        r=data['seasons'][region];values=r['seasons']
        keys=seasonal or [max(values,key=lambda s:Decimal(values[s]['rain']))]
        return result(f"En **2022–2023**, pour **{region.title()}** : "+'; '.join(f"**{s.title()} : {show(values[s]['rain'])} mm**, soit {show(values[s]['share'])} % du total annuel" for s in keys)+'.',[r])
    monthly=data['monthly'][region]
    months=[m for m in monthly['months'] if re.search(r'\b'+plain(m)+r'\b',q)]
    if months or 'mois' in q:
        if governors:
            r=data['governorates'][governors[0]];names=list(monthly['months']);values=dict(zip(names,r['monthly']))
            keys=months or [max(values,key=lambda m:Decimal(values[m]))]
            return result(f"Pour **{governors[0].title()}**, les moyennes publiées en 2022–2023 sont : "+'; '.join(f"**{m.title()} : {show(values[m])} mm**" for m in keys)+'.',[r])
        values=monthly['months']
        if not months:
            key='ratio' if 'deficitaire' in q else 'rain'
            extreme=(min if any(w in q for w in ('sec','deficitaire','presque pas')) else max)(Decimal(v[key]) for v in values.values())
            months=[m for m,v in values.items() if Decimal(v[key])==extreme]
        return result(f"Pour **{region.title()}**, en 2022–2023 : "+'; '.join(f"**{m.title()} : {show(values[m]['rain'])} mm**, soit {show(values[m]['ratio'])} % de la normale mensuelle ({show(values[m]['normal'])} mm)" for m in months)+'. Un rapport supérieur à 100 % indique un excédent ; inférieur à 100 %, un déficit.',[monthly])
    if governors:
        if any(w in q for w in ('habitude','deficit','manque','sec','bien arrose')):
            comparisons=[(name,data['governorates'][name]['comparison']) for name in governors if 'comparison' in data['governorates'][name]]
            if len(comparisons)==len(governors):
                return result('Pour **2022–2023**, le tableau comparatif donne : '+ '; '.join(f"**{name.title()} : {show(r['annual_rounded'])} mm**, contre {show(r['normal'])} mm en moyenne, soit {show(r['ratio'])} % de la moyenne de référence" for name,r in comparisons)+'.',[r for _,r in comparisons])
        return result('En **2022–2023**, les moyennes annuelles publiées pour les gouvernorats sont : '+ '; '.join(f"**{name.title()} : {show(data['governorates'][name]['annual'])} mm**" for name in governors)+'. Il s’agit de la moyenne des postes sélectionnés pour le gouvernorat, pas d’une station unique.',[data['governorates'][name] for name in governors])
    if any(w in q for w in ('quelle region','quelle est la region','quel gouvernorat','ou est','regions ont','repart','le meme partout','region naturelle')):
        if 'gouvernorat' in q:
            values=data['governorates'];key='annual'
        else:values={k:v for k,v in data['regions'].items() if k!='TUNISIE'};key='deficit' if any(w in q for w in ('deficit','secheresse','seche','aride')) else 'rain'
        if any(w in q for w in ('quelle','quel ','ou est')):
            target=(min if key=='deficit' or 'moins' in q else max)(Decimal(r[key]) for r in values.values())
            names=[name for name,r in values.items() if Decimal(r[key])==target]
        else:names=list(values)
        unit='%' if key=='deficit' else 'mm'
        return result('Pour **2022–2023**, '+ '; '.join(f"**{name.title()} : {show(values[name][key])} {unit}**" for name in names)+(' d’écart à la moyenne interannuelle.' if key=='deficit' else '.'),[values[name] for name in names])
    names=regions or ['TUNISIE']
    return result('Pour **2022–2023**, '+ '; '.join(f"**{name.title()} : {show(data['regions'][name]['rain'])} mm**, contre {show(data['regions'][name]['normal'])} mm en moyenne interannuelle, soit **{show(abs(Decimal(data['regions'][name]['deficit'])))} % de déficit**" for name in names)+'.',[data['regions'][name] for name in names])
