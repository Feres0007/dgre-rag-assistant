"""Extraire les tableaux de synthèse et notices de barrages des PDF originaux.

Ce catalogue ne contient aucune question ni réponse préenregistrée.
"""
import json,re
from decimal import Decimal,InvalidOperation
import pymupdf
from dgre_rag.config import data_dir
from dgre_rag.ingestion.pipeline import source_path,plain
from dgre_rag.storage.database import connect,active_release,dump,file_hash


def numeric(value):
    value=(value or '').replace('%','').replace(' ','').replace(',','.').strip()
    number=Decimal(value)
    if not number.is_finite():raise ValueError('Nombre non fini')
    return str(number)


def build_catalog(db, rid):
    pages={(r['document_id'],r['page_pdf']):dict(r) for r in db.execute("SELECT * FROM sources WHERE kind='page'")}
    tables=[dict(r) for r in db.execute("SELECT s.*,t.rows_json FROM table_extractions t JOIN sources s USING(source_id)")]
    result={'release_id':rid,'version':1,'regions':{},'history':{},'monthly':{},'seasons':{},'governorates':{},'dams':[], 'rain_days':[], 'coordinates':[], 'hydro_summaries':[],'floods':[],'metadata':{},'geography':[]}
    def proof(doc,n):return pages[(doc,n)]
    pluv='pluvio_2022_2023';hydro='hydro_2022_2023'
    for key,doc,n in [('rain_preface',pluv,2),('rain_method',pluv,6),('station_codes',pluv,36),('hydro_network',hydro,11),('hydro_contents',hydro,14),('empty_rain_table',pluv,208)]:
        result['metadata'][key]={'source':proof(doc,n)}
    # Known page families and checked headers define each column, not proximity to a number.
    for t in tables:
        if t['document_id']!=pluv:continue
        rows=json.loads(t['rows_json']);n=t['page_pdf']
        if n==8 and rows[0][0]=='REGION':
            for row in rows[1:]:
                if len(row)==7:
                    result['regions'][row[0]]={'rain':numeric(row[2]),'normal':numeric(row[3]),'deficit':numeric(row[6]),'source':t}
        if n==9 and rows[0][0]=='REGION':
            years=rows[0][3:]
            for row in rows[1:]:
                if row[0] and len(row)==11:
                    result['history'][row[0]]={'years':dict(zip(years,map(numeric,row[3:]))),'source':t}
        if n==10:
            months=None
            for row in rows:
                if len(row)!=14:continue
                if row[0]=='REGIONS':months=[row[c] for c in (2,5,8,11)]
                name=' '.join((row[0] or '').split())
                if name in result['regions'] and months and all(months):
                    record=result['monthly'].setdefault(name,{'months':{},'source':t})
                    for j,month in enumerate(months):
                        offset=2+3*j
                        record['months'][month]={'rain':numeric(row[offset]),'normal':numeric(row[offset+1]),'ratio':numeric(row[offset+2])}
        if n==13 and rows[0][0]=='STATION':
            for row in rows[1:]:
                if row[0] in result['regions']:
                    result['seasons'][row[0]]={'seasons':{name:{'rain':numeric(row[2+i*2]),'share':numeric(row[3+i*2])} for i,name in enumerate(('AUTOMNE','HIVER','PRINTEMPS','ETE'))},'source':t}
        if n>=50:
            header=' '.join(x or '' for x in rows[0]) if rows else ''
            match=re.search(r'\b(\d{9,12})\s+(.+?)\s+2022',header)
            days=re.search(r'(\d+)\s+Pluies\s*>\s*0\s*mm.*?(\d+)\s+Pluies\s*>=\s*0[,.]5\s*mm.*?(\d+)\s+Pluies\s*>=\s*10\s*mm',t['raw_text'],re.S)
            if match and days and 0<=int(days[3])<=int(days[2])<=int(days[1])<=365:
                result['rain_days'].append({'code':match[1],'station':match[2].strip(),'days':int(days[1]),'days05':int(days[2]),'days10':int(days[3]),'source':t})
    with pymupdf.open(source_path(pluv)) as pdf:
        intro=pdf[5].get_text(sort=True)
        counts=re.search(r'total de (\d+) stations.*?(\d+) stations ont été\s+sélectionnées',intro,re.S)
        if counts:result['metadata']['rain_network']={'count':int(counts[1]),'selected':int(counts[2]),'source':proof(pluv,6)}
        for n in (24,25,26):
            governor=None
            for line in pdf[n-1].get_text(sort=True).splitlines():
                m=re.search(r'GOUVERNORATS? DE\s+(.+)',line)
                if m:governor=m[1].strip().removeprefix("L'").replace('SD BOUZID','SIDI BOUZID')
                if governor and re.match(r'\s*MOYENNE\b',line):
                    values=re.findall(r'-?\d+(?:[,.]\d+)?',line)
                    if len(values)==13:result['governorates'][governor]={'monthly':list(map(numeric,values[:12])),'annual':numeric(values[12]),'source':proof(pluv,n)}
        for n in (20,21,22):
            governor=None
            for line in pdf[n-1].get_text(sort=True).splitlines():
                m=re.search(r'GOUVERNORATS? DE\s+(.+)',line)
                if m:governor=m[1].strip().removeprefix("L'").replace('SD BOUZID','SIDI BOUZID')
                if governor in result['governorates'] and re.match(r'\s*MOYENNE\b',line):
                    values=re.findall(r'-?\d+(?:[,.]\d+)?',line)
                    if len(values)==13:result['governorates'][governor]['comparison']={'annual_rounded':numeric(values[8]),'normal':numeric(values[9]),'ratio':numeric(values[12]),'source':proof(pluv,n)}
        for n in range(29,48):
            for line in pdf[n-1].get_text(sort=True).splitlines():
                m=re.match(r'^\s*(\d{9,12})\s+(.+?)\s+(-?\d+[,.]\d+)\s+(-?\d+[,.]\d+)\s+(\d+(?:[,.]\d+)?)\s*$',line)
                if m and -90<=Decimal(numeric(m[3]))<=90 and -180<=Decimal(numeric(m[4]))<=180:
                    result['coordinates'].append({'code':m[1],'station':m[2].strip(),'latitude':numeric(m[3]),'longitude':numeric(m[4]),'altitude':numeric(m[5]),'source':proof(pluv,n)})
    with pymupdf.open(source_path(hydro)) as pdf:
        abbreviations=pdf[8].get_text(sort=True)
        result['metadata']['abbreviations']={'values':dict(re.findall(r'\b([A-Z]{2,3}):\s*([^,\n]+)',abbreviations)),'source':proof(hydro,9)}
        preface=pdf[1].get_text(sort=True)
        for label,pattern in [('author',r'Mme\.\s+([^\n]+?)\s+Sous-directeur'),('validator',r'Mr\.\s+([^\n]+?)\s+le Directeur')]:
            m=re.search(pattern,preface)
            if m:result['metadata'][label]={'name':m[1].strip(),'source':proof(hydro,2)}
        network=pdf[10].get_text(sort=True)
        count=re.search(r'au total\s+(\d+)\s+stations',network)
        frequency=re.search(r'de\s+(\d+)\s+minutes',network)
        if count and frequency:result['metadata']['automatic_network']={'count':int(count[1]),'minutes':int(frequency[1]),'source':proof(hydro,11)}
        station=None
        for i,page in enumerate(pdf):
            text=page.get_text(sort=True)
            station_match=re.search(r'Stati+on\s*:\s*(\d{9,12})\s+([^\n]+)',text,re.I)
            if station_match:
                station={'code':station_match[1],'name':station_match[2].strip(),'source':proof(hydro,i+1),'fields':{}}
                for key,pattern,unit in [('mean',r'Débit Moyen Annuel\s*[=:]\s*([^\n]+)','m³/s'),
                    ('volume',r'Volume total écoulé[^=:\n]*[=:]\s*([^\n]+)','millions de m³'),
                    ('depth',r'Hauteur de la lame d.eau écou[^=:\n]*[=:]\s*([^\n]+)','mm'),
                    ('instant',r'Maxi?\s*Instantané\s*=\s*([^\n]+)','m³/s')]:
                    m=re.search(pattern,text,re.I)
                    if m:
                        number=re.match(r'\s*=*\s*(\d+(?:[,.]\d+)?)\s*(?:m3\s*/s|[HM]m3|mm)\b',m[1],re.I)
                        station['fields'][key]={'value':numeric(number[1]) if number else None,'raw':m[1].strip(),'unit':unit}
                historic=re.search(r'Crue maximale\s+Obse+r?vée\s*:?\s*(\d+(?:[,.]\d+)?)\s*m3/s\s*([^\n]*)(?:\n\s*(\d{4}))?',text,re.I)
                if historic:station['fields']['historical']={'value':numeric(historic[1]),'raw':historic[0].strip(),'unit':'m³/s','when':(historic[2]+' '+(historic[3] or '')).strip()}
                if station['fields']:result['hydro_summaries'].append(station)
            if station and ('caractéristiques des cru' in text.lower()):
                for t in [t for t in tables if t['document_id']==hydro and t['page_pdf']==i+1]:
                    rows=json.loads(t['rows_json'])
                    for row in rows:
                        row=[v for v in row if v is not None]
                        if len(row)==13 and re.search(r'\d{2}/\d{2}/\d{4}',str(row[0])):
                            try:
                                # Wrapped hour fragments may precede the next row's date.
                                # Retain the date on that row, never attach the previous row's hour.
                                start=re.search(r'\d{2}/\d{2}/\d{4}[^\n]*',row[0])[0]
                                end=re.search(r'\d{2}/\d{2}/\d{4}[^\n]*',row[1])
                                if not end:continue
                                result['floods'].append({'station':station['name'],'code':station['code'],'start':start,'end':end[0],
                                    'base_raw':row[2],'rise_raw':row[3],'peak':numeric(row[6]),'volume_raw':row[7],
                                    'header':rows[0],'source':t})
                            except (InvalidOperation,ValueError):pass
            governor=re.findall(r'Gouvernorat de\s+(.+)',text)
            if governor:
                area=re.search(r'superficie totale\s+(?:est de\s+)?(?:\n\s*est de\s+)?(\d+(?:[,.]\d+)?)\s*[kK][mM]',text,re.S)
                absent=re.search(r"Il n'y a aucun barrage[^.]*\.",text)
                if area or absent:result['geography'].append({'name':governor[-1].strip(),'area':numeric(area[1]) if area else None,'no_dam':bool(absent),'source':proof(hydro,i+1)})
            for m in re.finditer(r'Barrage\s+([^:\n]{2,40})\s*:\s*(.*?)(?=\n[^\n]*Barrage\s+[^:\n]+:|\n4-|\n\s*4-|\Z)',text,re.S):
                description=' '.join(m[2].split());name=m[1].strip()
                capacity=re.search(r'capacité\s+(?:initiale\s+)?de\s*(\d+(?:[,.]\d+)?)\s*Mm3',description)
                # Keep capacity and inflow separate. Never infer reservoir storage from annual inflow.
                inflow=re.search(r'2022/202+3\s+.*?(\d+(?:[,.]\d+)?)\s*Mm3\s+contre\s*(\d+(?:[,.]\d+)?)\s*Mm3',description)
                year=re.search(r'\ben\s+(\d{4})\b',description)
                river=re.search(r'(?:oued|Oued)\s+([^,]+)',description)
                if capacity:
                    result['dams'].append({'name':name,'capacity':numeric(capacity[1]),'inflow':numeric(inflow[1]) if inflow else None,
                        'normal':numeric(inflow[2]) if inflow else None,'year':year[1] if year else None,'river':river[1] if river else None,
                        'governorate':governor[-1].strip() if governor else None,'description':description,'source':proof(hydro,i+1)})
    # Strip bulky parser helpers; retain full raw evidence and geometry.
    def strip(value):
        if isinstance(value,dict):return {k:strip(v) for k,v in value.items() if k!='rows_json'}
        if isinstance(value,list):return [strip(v) for v in value]
        return value
    return strip(result)


def main(release_id=None):
    rid=release_id or active_release()
    with connect(rid) as db:
        result=build_catalog(db,rid)
    path=data_dir()/f'reference_catalog_{rid}.json'
    dump(path,result)
    dump(path.with_suffix('.manifest.json'),{'sha256':file_hash(path),'release_id':rid,'extractor_sha256':file_hash(__import__('pathlib').Path(__file__))})
    print({k:len(v) for k,v in result.items() if isinstance(v,(dict,list))})


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--release-id')
    main(parser.parse_args().release_id)
