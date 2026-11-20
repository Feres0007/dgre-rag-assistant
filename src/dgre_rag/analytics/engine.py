from datetime import date, timedelta
from decimal import Decimal, localcontext
from dgre_rag.storage.database import connect
from dgre_rag.domain.models import Operation


class DataError(ValueError):
    pass


def calculate(formula, rows, period=None, *, allow_partial=False, options=None):
    options=options or {}
    if not rows:raise DataError('NOT_FOUND')
    if any(r.get('quality_status','validated')!='validated' for r in rows):raise DataError('UNVALIDATED_DATA')
    values=[Decimal(r['value_decimal']) for r in rows]
    if not all(v.is_finite() for v in values):raise DataError('NON_FINITE_VALUE')
    if len({r['unit'] for r in rows})!=1:raise DataError('INVALID_UNIT')
    selection=formula in ('filter','rank','count')
    if len({r['entity_id'] for r in rows})!=1 and not selection:raise DataError('SPATIAL_AGGREGATION_FORBIDDEN')
    if len({r['metric_id'] for r in rows})!=1:raise DataError('INCOMPATIBLE_METRICS')
    spans=sorted((date.fromisoformat(r['period_start']),date.fromisoformat(r['period_end'])) for r in rows)
    if any(a[1]>=b[0] for a,b in zip(spans,spans[1:])) and not selection:raise DataError('OVERLAPPING_PERIODS')
    if any(s>e for s,e in spans):raise DataError('INVALID_PERIOD')
    if period and any(s<period.start or e>period.end for s,e in spans):raise DataError('OUTSIDE_PERIOD')
    expected=(period.end-period.start).days+1 if period else sum((e-s).days+1 for s,e in spans)
    available=sum((e-s).days+1 for s,e in spans)-sum(r.get('missing_days',0) or 0 for r in rows)
    if available<=0 or (available>expected and not selection):raise DataError('INVALID_COVERAGE')
    complete=(available==expected and not any(r.get('missing_days',0) for r in rows))
    if period:
        complete=complete and spans[0][0]==period.start and spans[-1][1]==period.end
    unit=rows[0]['unit'];metric=rows[0]['metric_id']
    dates=[];selected_ids=[]
    with localcontext() as context:
        context.prec=32
        if formula in ('rainfall_sum','daily_discharge_volume','time_weighted_mean','mean') and not complete and not allow_partial:
            raise DataError('INCOMPLETE_SERIES')
        if formula in ('time_weighted_mean','mean') and any(r.get('missing_days',0) for r in rows):
            raise DataError('UNKNOWN_MEAN_DURATION')
        if formula=='rainfall_sum':
            if metric not in ('rainfall_daily','rainfall_monthly') or unit!='mm':raise DataError('INVALID_UNIT')
            value=sum(values,Decimal(0))
        elif formula=='daily_discharge_volume':
            if metric!='discharge_daily_mean' or unit!='m3/s' or any(s!=e for s,e in spans):raise DataError('INVALID_UNIT')
            value=sum(values,Decimal(0))*Decimal(86400)/Decimal(1000000);unit='hm3'
        elif formula=='time_weighted_mean':
            if metric not in ('discharge_daily_mean','discharge_monthly_mean'):raise DataError('INVALID_METRIC')
            durations=[(date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days+1 for r in rows]
            value=sum((v*d for v,d in zip(values,durations)),Decimal(0))/sum(durations)
        elif formula in ('maximum','minimum'):
            value=(max if formula=='maximum' else min)(values)
            dates=[r['period_start'] for r,v in zip(rows,values) if v==value]
        elif formula=='mean':
            if any(s!=e for s,e in spans):raise DataError('USE_WEIGHTED_MEAN')
            value=sum(values,Decimal(0))/len(values)
        elif formula in ('threshold_count','longest_run','filter','rank','count'):
            import operator
            compare={'gt':operator.gt,'ge':operator.ge,'lt':operator.lt,'le':operator.le,'eq':operator.eq}
            if formula in ('threshold_count','longest_run') and any(s!=e for s,e in spans):raise DataError('DAILY_VALUES_REQUIRED')
            if formula in ('filter','threshold_count','longest_run'):
                if options.get('threshold') is None:raise DataError('THRESHOLD_REQUIRED')
                if options.get('threshold_unit') and options['threshold_unit']!=unit:raise DataError('INVALID_UNIT')
                threshold=Decimal(str(options['threshold']))
                if not threshold.is_finite():raise DataError('NON_FINITE_VALUE')
                if options.get('comparator','ge') not in compare:raise DataError('INVALID_COMPARATOR')
                selected=[r for r,v in zip(rows,values) if compare[options.get('comparator','ge')](v,threshold)]
            elif formula=='rank':
                selected=sorted(rows,key=lambda r:Decimal(r['value_decimal']),reverse=options.get('descending',True))
            else:selected=list(rows)
            selected_ids=[r['observation_id'] for r in selected]
            if formula=='longest_run':
                best=0;current=[];runs=[];previous=None
                for r in sorted(selected,key=lambda r:r['period_start']):
                    day=date.fromisoformat(r['period_start'])
                    current=current+[day] if previous and day==previous+timedelta(days=1) else [day]
                    previous=day
                    if len(current)>best:best=len(current);runs=[(current[0].isoformat(),day.isoformat())]
                    elif len(current)==best:runs.append((current[0].isoformat(),day.isoformat()))
                value=Decimal(best);dates=runs;unit='jours'
            else:
                value=Decimal(len(selected));unit='jours' if formula=='threshold_count' else 'observations'
        elif formula=='convert':
            target=options.get('target_unit')
            factors={('L/s','m3/s'):Decimal('.001'),('m3/s','L/s'):Decimal('1000'),
                ('hm3','m3'):Decimal('1000000'),('m3','hm3'):Decimal('.000001'),
                ('cm','m'):Decimal('.01'),('m','cm'):Decimal('100'),('hm3','Mm3'):Decimal(1),('Mm3','hm3'):Decimal(1)}
            if len(rows)!=1 or (unit,target) not in factors:raise DataError('INVALID_CONVERSION')
            value=values[0]*factors[(unit,target)];unit=target
        else:raise DataError('INVALID_FORMULA')
    if selection:
        # A catalogue selection is not temporal coverage and cannot claim all stations exist.
        coverage={'available':len(rows),'valid':len(rows),'complete':False,'kind':'available_catalogue'}
    else:coverage={'expected':expected,'available':available,'valid':available,'complete':complete,'missing':expected-available}
    result={'formula_id':formula,'formula_version':'2','value':str(value),'unit':unit,
            'input_ids':[r['observation_id'] for r in rows],
            'dates':dates,'rounding':'Decimal, précision de calcul 32 ; valeur exacte conservée.',
            'selected_ids':selected_ids,'parameters':options,'period':period.model_dump(mode='json') if period else None,
            'coverage':coverage,
            'limits':(['Sélection des seules observations validées disponibles ; exhaustivité du réseau non certifiée.'] if selection else
                [] if complete else [f'Résultat partiel sur {available} jours couverts sur {expected} ; aucune estimation des lacunes.'])}
    if options.get('group_by'):
        if selection or not period:raise DataError('INVALID_GROUPING')
        import calendar
        groups={}
        for r in rows:
            d=date.fromisoformat(r['period_start'])
            if options['group_by']=='month':start=date(d.year,d.month,1);end=date(d.year,d.month,calendar.monthrange(d.year,d.month)[1])
            elif options['group_by']=='campaign':start=date(d.year-(d.month<9),9,1);end=date(start.year+1,8,31)
            elif options['group_by']=='season':
                month=12 if d.month in (12,1,2) else 3 if d.month<=5 else 6 if d.month<=8 else 9
                year=d.year-(month==12 and d.month<3);start=date(year,month,1)
                end=date(year+1,2,calendar.monthrange(year+1,2)[1]) if month==12 else date(year,month+2,calendar.monthrange(year,month+2)[1])
            else:raise DataError('INVALID_GROUPING')
            if date.fromisoformat(r['period_end'])>end:raise DataError('GROUP_BOUNDARY_CROSSING')
            groups.setdefault((max(start,period.start),min(end,period.end)),[]).append(r)
        child_options={k:v for k,v in options.items() if k!='group_by'}
        from dgre_rag.domain.models import Period
        result['groups']=[calculate(formula,items,Period(start=start,end=end),allow_partial=allow_partial,options=child_options) for (start,end),items in sorted(groups.items())]
    return result


def compare_rows(a,b,formula='difference'):
    if any(r.get('quality_status','validated')!='validated' for r in (a,b)):raise DataError('UNVALIDATED_DATA')
    if a['unit']!=b['unit'] or a['metric_id']!=b['metric_id']:raise DataError('INCOMPATIBLE_METRICS')
    if a.get('baseline_id')!=b.get('baseline_id'):raise DataError('INCOMPATIBLE_BASELINE')
    if a.get('missing_days',0) or b.get('missing_days',0):raise DataError('INCOMPLETE_SERIES')
    durations=[(date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days+1 for r in (a,b)]
    if durations[0]!=durations[1]:raise DataError('INCOMPATIBLE_PERIODS')
    av,bv=Decimal(a['value_decimal']),Decimal(b['value_decimal'])
    if not av.is_finite() or not bv.is_finite():raise DataError('NON_FINITE_VALUE')
    if formula!='difference' and bv<=0:raise DataError('INVALID_REFERENCE')
    if formula in ('ratio_to_baseline','relative_anomaly','positive_deficit') and not b.get('baseline_id'):
        raise DataError('BASELINE_REQUIRED')
    choices={'difference':lambda:av-bv,'ratio_to_baseline':lambda:100*av/bv,
             'relative_anomaly':lambda:100*(av-bv)/bv,'positive_deficit':lambda:100*(bv-av)/bv}
    if formula not in choices:raise DataError('INVALID_FORMULA')
    return {'formula_id':formula,'formula_version':'1','value':str(choices[formula]()),
            'unit':a['unit'] if formula=='difference' else '%',
            'input_ids':[a['observation_id'],b['observation_id']],
            'coverage':{'complete':True},'limits':[r['note'] for r in (a,b) if r.get('note')],
            'relative_difference_percent':str(100*(av-bv)/bv) if formula=='difference' and bv>0 else None,
            'definition':'A − B ; écart relatif = 100 × (A − B) / B, référence de comparaison B' if formula=='difference' else formula}


def query_rows(db,entity_id=None,metric_id=None,start=None,end=None,limit=None):
    where=[];args=[]
    for column,value,operator in [('entity_id',entity_id,'='),('metric_id',metric_id,'='),('period_start',start,'>='),('period_end',end,'<=')]:
        if value is not None:where.append(column+operator+'?');args.append(str(value))
    sql='SELECT * FROM published_observations'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY canonical_name,metric_id,period_start'
    if limit is not None:sql+=' LIMIT ?';args.append(limit)
    return [dict(r) for r in db.execute(sql,args).fetchall()]


def execute(op:Operation,release_id):
    with connect(release_id) as db:
        rows=query_rows(db,op.entity_id,op.metric_id,op.period.start,op.period.end)
        if not rows:
            issues=db.execute('''SELECT q.code FROM quality_issues q JOIN observations o USING(observation_id)
              WHERE o.entity_id=? AND o.metric_id=? AND period_start>=? AND period_end<=?''',
              (op.entity_id,op.metric_id,str(op.period.start),str(op.period.end))).fetchall()
            if any(r[0]=='SOURCE_CONFLICT' for r in issues):raise DataError('SOURCE_CONFLICT')
            raise DataError('UNVALIDATED_DATA' if issues else 'NOT_FOUND')
        if op.op=='lookup':
            return rows,None
        if op.op=='compare':
            other=query_rows(db,op.other_entity_id,op.metric_id,op.other_period.start,op.other_period.end)
            if len(rows)!=1 or len(other)!=1:raise DataError('COMPARISON_REQUIRES_TWO_VALUES')
            return rows+other,compare_rows(rows[0],other[0],op.formula_id or 'difference')
        return rows,calculate(op.formula_id,rows,op.period,allow_partial=op.options.allow_partial,options=op.options.model_dump(mode='json'))


def runoff_depth(volume, area):
    """Only explicit proof-backed operands; basin compatibility is mandatory."""
    if volume.get('basin_id') is None or volume.get('basin_id')!=area.get('basin_id'):raise DataError('INCOMPATIBLE_BASIN')
    for row in (volume,area):
        if row.get('quality_status')!='validated' or not row.get('evidence_ids'):raise DataError('UNVALIDATED_DATA')
    if volume['unit'] not in ('hm3','Mm3') or area['unit']!='km2':raise DataError('INVALID_UNIT')
    v,a=Decimal(volume['value_decimal']),Decimal(area['value_decimal'])
    if not v.is_finite() or not a.is_finite() or v<0 or a<=0:raise DataError('INVALID_REFERENCE')
    with localcontext() as context:
        context.prec=32
        value=v*1000/a
    return {'formula_id':'runoff_depth','formula_version':'1','value':str(value),'unit':'mm',
        'input_ids':[volume['observation_id'],area['observation_id']],
        'evidence_ids':list(dict.fromkeys(volume['evidence_ids']+area['evidence_ids'])),
        'definition':'1000 × volume (hm³) / superficie (km²)','coverage':{'complete':True},'limits':[]}


def interpolate_rating(height, points, on_date, curve_id):
    """Linear interpolation within one valid, increasing, sourced curve only."""
    h=Decimal(str(height));day=date.fromisoformat(str(on_date))
    if not h.is_finite():raise DataError('NON_FINITE_VALUE')
    if len(points)<2:raise DataError('INSUFFICIENT_POINTS')
    for p in points:
        if p.get('curve_id')!=curve_id or p.get('quality_status')!='validated' or not p.get('evidence_ids'):raise DataError('UNVALIDATED_CURVE')
        if p.get('height_unit')!='m' or p.get('discharge_unit')!='m3/s':raise DataError('INVALID_UNIT')
        if not date.fromisoformat(p['valid_from'])<=day<=date.fromisoformat(p['valid_to']):raise DataError('CURVE_OUTSIDE_VALIDITY')
    ordered=sorted(points,key=lambda p:Decimal(p['height']))
    pairs=[(Decimal(p['height']),Decimal(p['discharge'])) for p in ordered]
    if not all(a.is_finite() and b.is_finite() and b>=0 for a,b in pairs):raise DataError('NON_FINITE_VALUE')
    if any(a[0]>=b[0] or a[1]>b[1] for a,b in zip(pairs,pairs[1:])):raise DataError('AMBIGUOUS_CURVE')
    if not pairs[0][0]<=h<=pairs[-1][0]:raise DataError('EXTRAPOLATION_FORBIDDEN')
    for i,(x,y) in enumerate(pairs):
        if h==x:return {'value':str(y),'unit':'m3/s','origin':'published','evidence_ids':ordered[i]['evidence_ids']}
        if h<x:
            lo=pairs[i-1]
            with localcontext() as context:
                context.prec=32;value=lo[1]+(y-lo[1])*(h-lo[0])/(x-lo[0])
            return {'value':str(value),'unit':'m3/s','origin':'estimated','formula_id':'linear_interpolation',
                'curve_id':curve_id,'input_points':ordered[i-1:i+1],
                'evidence_ids':list(dict.fromkeys(ordered[i-1]['evidence_ids']+ordered[i]['evidence_ids']))}
