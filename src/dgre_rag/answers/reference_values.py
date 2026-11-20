"""Typed views of already extracted reference values; no fabricated observations."""
import calendar
from datetime import datetime
from dgre_rag.ingestion.pipeline import plain


def values_for(records,data,question):
    q=plain(question);values=[]
    def add(record,name,metric,value,unit,start='2022-09-01',end='2023-08-31',scope='station'):
        if value is not None:
            values.append({'canonical_name':name,'metric_id':metric,'value_decimal':str(value),'unit':unit,
                           'period_start':start,'period_end':end,'scope':scope,'origin':'reference_table',
                           'evidence_ids':[record['source']['source_id']]})
    for r in records:
        name=r.get('name') or r.get('station')
        scope='station'
        for family in ('regions','governorates','monthly','seasons','history'):
            for label,record in data.get(family,{}).items():
                if r is record:name=label.title();scope='governorate' if family=='governorates' else 'region'
        if not name:continue
        if 'days10' in r:
            for key,metric in (('days','rain_days_gt_0'),('days05','rain_days_ge_0_5'),('days10','rain_days_ge_10')):
                add(r,name,metric,r.get(key),'jours')
        elif 'capacity' in r:
            if 'capacite' in q:add(r,name,'Capacité du barrage',r['capacity'],'hm3',scope='dam')
            elif r.get('inflow') is not None:add(r,name,'Apports annuels du barrage',r['inflow'],'hm3',scope='dam')
        elif 'rain' in r:add(r,name,'rainfall_annual',r['rain'],'mm',scope=scope)
        elif 'annual' in r:add(r,name,'rainfall_annual',r['annual'],'mm',scope=scope)
        elif 'months' in r:
            months=['septembre','octobre','novembre','decembre','janvier','fevrier','mars','avril','mai','juin','juillet','aout']
            explicit=[m for m in months if m in q]
            for month,v in r['months'].items():
                if explicit and plain(month) not in explicit:continue
                n=(months.index(plain(month))+8)%12+1;y=2022 if n>=9 else 2023
                add(r,name,'rainfall_monthly',v['rain'],'mm',f'{y}-{n:02d}-01',f'{y}-{n:02d}-{calendar.monthrange(y,n)[1]}',scope)
        elif 'years' in r:
            for year,value in r['years'].items():
                y=int(year[:4]);add(r,name,'rainfall_annual',value,'mm',f'{y}-09-01',f'{y+1}-08-31',scope)
        elif 'fields' in r:
            key='mean' if 'moyen' in q else 'volume' if 'volume' in q else 'depth' if 'lame' in q else None
            if key and key in r['fields']:
                add(r,name,{'mean':'discharge_annual_mean','volume':'volume_annual','depth':'runoff_depth'}[key],r['fields'][key]['value'],{'mean':'m3/s','volume':'hm3','depth':'mm'}[key])
        elif 'peak' in r and 'volume' not in q:
            day=datetime.strptime(r['start'][:10],'%d/%m/%Y').date().isoformat()
            add(r,name,'Débit de pointe de crue',r['peak'],'m3/s',day,day)
    return values
