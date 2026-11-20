from pathlib import Path
from datetime import date
from decimal import Decimal
import calendar
import json
import re
import sqlite3
import unicodedata
from functools import lru_cache
import pymupdf
from dgre_rag.config import root, data_dir, settings
from dgre_rag.storage.database import initialize, uid, dump, file_hash, integrity, build_fingerprint
from dgre_rag.domain.models import number
from dgre_rag.domain.catalog import METRICS, MONTHS, PILOT


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')


def register():
    spec = root() / 'RAG_DGRE_Plan_Complet/plan_implementation/configuration/corpus_expected.json'
    expected = json.loads(spec.read_text(encoding='utf-8'))['documents']
    records = []
    for item in expected:
        path = root() / settings().corpus_dir / item['original_name']
        if not path.is_file():
            raise ValueError('DOCUMENT_MISSING: ' + item['original_name'])
        sha = file_hash(path)
        with pymupdf.open(path) as pdf:
            count = len(pdf)
        if sha != item['expected_sha256'] or count != item['expected_page_count']:
            raise ValueError('CORPUS_VERSION_MISMATCH: ' + item['original_name'])
        records.append(dict(document_id=item['document_id'], original_name=path.name,
                            relative_path=path.relative_to(root()).as_posix(), sha256=sha, page_count=count))
    dump(data_dir() / 'registry.json', records)
    return records


def registry():
    path = data_dir() / 'registry.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else register()


@lru_cache(maxsize=8)
def _verify_source(path,mtime,size,expected):
    if file_hash(Path(path))!=expected:raise ValueError('SOURCE_FILE_CHANGED')


def source_path(document_id):
    matches = [r for r in registry() if r['document_id'] == document_id]
    if len(matches) != 1:
        raise ValueError('UNKNOWN_DOCUMENT')
    path=(root() / matches[0]['relative_path']).resolve()
    if not path.is_relative_to((root()/settings().corpus_dir).resolve()):raise ValueError('UNAUTHORIZED_SOURCE_PATH')
    stat=path.stat();_verify_source(str(path),stat.st_mtime_ns,stat.st_size,matches[0]['sha256'])
    return path


def campaign(document):
    match=re.search(r'(20\d{2})\D+(20\d{2})',document.get('edition') or document['original_name'])
    if not match or int(match[2])!=int(match[1])+1:
        raise ValueError('CAMPAIGN_REQUIRED')
    return date(int(match[1]),9,1).isoformat(),date(int(match[2]),8,31).isoformat()


def month_period(index, campaign_start=2022):
    month = MONTHS[index]
    year = campaign_start if month >= 9 else campaign_start+1
    return date(year, month, 1).isoformat(), date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def french_date(text):
    numeric = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if numeric:
        d,m,y = map(int,numeric.groups())
        return date(y,m,d).isoformat()
    named = re.search(r'(\d{1,2})\s+([a-zéûôè]+)\s+(\d{4})',text,re.I)
    if named:
        d,m,y=named.groups()
        names=['janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre']
        return date(int(y), names.index(plain(m))+1, int(d)).isoformat()
    return None


class Extractor:
    def __init__(self, db, document, page, n):
        self.db,self.document,self.page,self.n = db,document,page,n
        self.doc_id=document['document_id']
        self.start,self.end=campaign(document)
        self.printed=None
        self.count=0
        self.drawings=page.get_drawings()

    def source(self, box, text, kind='cell', parent=None):
        rect=pymupdf.Rect(box) & self.page.rect
        if rect.is_empty:
            raise ValueError('INVALID_BBOX')
        coords=tuple(round(v,3) for v in rect)
        sid=uid(self.doc_id,self.n,kind,coords,text)
        self.db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (sid,self.doc_id,self.n,self.printed,parent,kind,*coords,text))
        return sid

    def issue(self,sid,code,detail,oid=None):
        self.db.execute('INSERT OR IGNORE INTO quality_issues VALUES (?,?,?,?,?,?,?,?)',
            (uid(sid,code,oid,detail),sid,oid,code,'warning','open',detail,None))

    def entity(self,code,name,sid,kind):
        normalized=re.sub(r'\s+',' ',re.sub(r"[-’']",' ',plain(name))).strip()
        matches=self.db.execute('''SELECT DISTINCT e.entity_id,e.canonical_name FROM entities e
            JOIN entity_mentions m USING(entity_id) WHERE e.kind=? AND m.source_code=?''',(kind,code)).fetchall()
        same=[r for r in matches if re.sub(r'\s+',' ',re.sub(r"[-’']",' ',plain(r['canonical_name']))).strip()==normalized]
        eid=same[0]['entity_id'] if len(same)==1 else uid('entity-v2',kind,sid,normalized)
        self.db.execute('INSERT OR IGNORE INTO entities VALUES (?,?,?)',(eid,kind,name.strip()))
        self.db.execute('INSERT OR IGNORE INTO entity_mentions VALUES (?,?,?,?,?,?)',
            (uid(eid,sid),eid,sid,code,name.strip(),'code_and_name' if same else 'source_occurrence'))
        if any(r['entity_id']!=eid for r in matches):
            self.issue(sid,'SHARED_CODE','Code partagé par plusieurs noms : '+code+' ; identités conservées séparément.')
        if len(code)!=10:
            self.issue(sid,'ATYPICAL_CODE','Code conservé tel que publié : '+code)
        return eid

    def shaded(self,box):
        rect=pymupdf.Rect(box)
        for drawing in self.drawings:
            fill=drawing.get('fill')
            if fill and max(fill) < .97 and max(fill) > .05:
                intersection=rect & drawing['rect']
                if not intersection.is_empty and intersection.get_area() > rect.get_area()*.55:
                    return True
        return False

    def observation(self,eid,metric,raw,box,table_sid,start=None,end=None,
                    event=None,event_time=None,row=0,col=0,missing=0,force_block=None,note=''):
        start,end=start or self.start,end or self.end
        value,symbol=number(raw)
        if raw.strip()=='.' and metric=='rainfall_daily' and not force_block:
            value,symbol='0','dry_legend_pdf48'
        sid=self.source(box,raw,parent=table_sid)
        cid=uid(sid,row,col,metric,start)
        self.db.execute('INSERT OR IGNORE INTO cells VALUES (?,?,?,?,?,?,?,?)',
            (cid,sid,row,col,json.dumps([metric,start,end]),raw,value,symbol))
        oid=uid(eid,metric,start,end,sid,event)
        quality='candidate' if value is not None and not force_block else 'blocked'
        if value is None and not force_block:
            force_block=symbol
        self.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (oid,eid,metric,start,end,event,event_time,value,METRICS[metric][1],
             str(Decimal(1).scaleb(Decimal(value).as_tuple().exponent)) if value is not None else None,None,
             symbol,quality,'published',None))
        self.db.execute('INSERT OR IGNORE INTO observation_evidence VALUES (?,?,?,?)',(oid,sid,cid,'value'))
        self.db.execute('INSERT OR IGNORE INTO observation_evidence VALUES (?,?,?,?)',(oid,table_sid,None,'context'))
        self.db.execute('INSERT OR IGNORE INTO observation_context VALUES (?,?,?,?)',(oid,missing,note,table_sid))
        if force_block:
            self.issue(sid,str(force_block),'Observation exclue des calculs : '+str(force_block),oid)
        self.count+=1
        return oid

    def raw_table(self,t,index):
        rows=t.extract()
        sid=self.source(t.bbox,'\n'.join(' | '.join(str(c or '') for c in row) for row in rows),'table')
        self.db.execute('INSERT OR IGNORE INTO table_extractions VALUES (?,?,?,?,?)',
            (sid,json.dumps(rows,ensure_ascii=False),json.dumps([r.cells for r in t.rows]),'candidate','Famille à interpréter'))
        return sid,rows

    def grid(self,t,rows,sid,eid,hydro=False):
        header=next((i for i,r in enumerate(rows) if plain(str(r[0] or '')).strip()=='jour'),None)
        if header is None:
            return False
        heads=[str(c).strip() for c in rows[header] if c and str(c).strip()]
        if len(heads)!=13 or not plain(heads[1]).startswith('sep') or not plain(heads[-1]).startswith('aou'):
            return False
        centers=None
        if t.col_count not in (13,25):
            boxes=[b for b in t.rows[header].cells if b]
            rect=pymupdf.Rect(boxes[0])
            for b in boxes[1:]:rect|=pymupdf.Rect(b)
            month_words=[w for w in self.page.get_text('words',clip=rect) if re.match(r'^(sept?|oct|nov|dec|jan|fev|mar|avr|mai|juin|juil|aou)',plain(w[4]))]
            if len(month_words)!=12:return False
            centers=[(w[0]+w[2])/2 for w in sorted(month_words,key=lambda w:w[0])]
        daily='discharge_daily_mean' if hydro else 'rainfall_daily'
        monthly='discharge_monthly_mean' if hydro else 'rainfall_monthly'
        for ri,row in enumerate(rows[header+1:],header+1):
            day=str(row[0] or '').strip()
            is_daily=day.isdigit() and 1<=int(day)<=31
            is_month=plain(day) in (('moy','min','max') if hydro else ('tot','total'))
            if not (is_daily or is_month):
                continue
            for mi in range(12):
                indices=[mi+1] if t.col_count==13 else [mi*2+1,mi*2+2]
                if centers:
                    indices=[]
                    for j,b in enumerate(t.rows[ri].cells):
                        if j==0 or not b:continue
                        words=self.page.get_text('words',clip=pymupdf.Rect(b))
                        x=sum((w[0]+w[2])/2 for w in words)/len(words) if words else (b[0]+b[2])/2
                        if min(range(12),key=lambda k:abs(centers[k]-x))==mi:indices.append(j)
                vals=[str(row[j]).strip() for j in indices if row[j] is not None and str(row[j]).strip()]
                raw=' '.join(vals)
                boxes=[t.rows[ri].cells[j] for j in indices if t.rows[ri].cells[j]]
                if not boxes:
                    continue
                box=pymupdf.Rect(boxes[0])
                for b in boxes[1:]:
                    box |= pymupdf.Rect(b)
                start,end=month_period(mi,int(self.start[:4]))
                if is_daily:
                    try:
                        start=end=date.fromisoformat(start).replace(day=int(day)).isoformat()
                    except ValueError:
                        if raw and raw not in ('-','.'):
                            self.issue(sid,'INVALID_CALENDAR_CELL',f'{day}, mois {MONTHS[mi]} : {raw}')
                        continue
                block='SHADED_CELL_REVIEW' if self.shaded(box) else None
                if not hydro and raw=='.' and not block:
                    # Point explicitly defined by PDF 48; preserve raw cell and attach legend.
                    oid=self.observation(eid,daily if is_daily else monthly,'.',box,sid,start,end,row=ri,col=mi+1)
                    legend=self.db.execute("SELECT source_id FROM sources WHERE document_id=? AND page_pdf=48 AND kind='page'",(self.doc_id,)).fetchone()
                    if legend:self.db.execute('INSERT OR IGNORE INTO observation_evidence VALUES (?,?,?,?)',(oid,legend[0],None,'symbol_legend'))
                else:
                    selected_metric=daily if is_daily else 'discharge_monthly_'+plain(day) if hydro and plain(day) in ('min','max') else monthly
                    self.observation(eid,selected_metric,raw,box,sid,start,end,row=ri,col=mi+1,force_block=block)
        return True

    def rain(self,t,rows,sid):
        text=self.page.get_textbox(pymupdf.Rect(t.bbox))
        match=re.search(r'\b(148\d{6,9})\s+(.+?)\s+'+self.start[:4]+r'\s*[-–]\s*(?:'+self.end[:4]+'|'+self.end[2:4]+')',text,re.S)
        if not match:
            return False
        code,name=match.groups()
        if len(name)>130 or '\nJour' in name:
            return False
        eid=self.entity(code,' '.join(name.split()),sid,'rain_station')
        if not self.grid(t,rows,sid,eid):
            return False
        missing_match=re.search(r'(\d+)\s+Jour\(s\) de Lacune',text,re.I)
        missing=int(missing_match[1]) if missing_match else 0
        summary=[('rainfall_annual',r'Total\s+(?:Annuel|Partiel)\s*=\s*([\d.,]+)\s*mm'),
                 ('rainfall_daily_max',r'Maxi\s+le\s+(\d{2}/\d{2}/\d{4})\s*=\s*([\d.,]+)\s*mm')]
        for metric,pattern in summary:
            m=re.search(pattern,text,re.I)
            if not m:
                continue
            event=french_date(m[1]) if metric.endswith('_max') else None
            value=m[2] if event else m[1]
            boxes=self.page.search_for(m[0],clip=pymupdf.Rect(t.bbox))
            if not boxes:
                # A summary with no precise match remains unvalidated rather than using whole page.
                self.issue(sid,'SUMMARY_GEOMETRY','Résumé à localiser : '+m[0])
                continue
            box=boxes[0]
            for b in boxes[1:]: box |= b
            self.observation(eid,metric,value,box,sid,event=event,missing=missing,
                note=f'{missing} jour(s) de lacune annoncé(s).' if missing else '')
        return True

    def hydro(self,tables,page_sid):
        text=self.page.get_text()
        station=re.search(r'St\s*ati+on\s*:\s*(148\d{6,9})\s+([^\n]+)',self.page.get_text(sort=True),re.I)
        if not station:
            return False
        eid=self.entity(station[1],station[2].strip(),page_sid,'hydro_station')
        for t,sid,rows in tables:
            if self.grid(t,rows,sid,eid,True):
                self.db.execute("UPDATE table_extractions SET state='extracted',reason='' WHERE source_id=?",(sid,))
        patterns=[
            ('discharge_daily_max',r'Max\s+journalier\s*=\s*([\d.,]+)\s*m3/s\s+le\s+([^\n]+)'),
            ('discharge_daily_min',r'Min\s+journalier\s*=\s*([\d.,]+)\s*m3/s\s+le\s+([^\n]+)'),
            ('discharge_instant_max',r'Max\s+Instantan[ée]\s*=\s*([\d.,]+)\s*m3/s\s*-+>\s*([^\n]+)'),
            ('discharge_instant_min',r'Mini?\s+Instantan[ée]\s*=\s*([\d.,]+)\s*m3/s\s*-+>\s*([^\n]+)'),
            ('discharge_annual_mean',r'Débit\s+moyen\s+annuel\s*=\s*([\d.,]+)\s*m3/s'),
            ('volume_annual',r'Volume\s+total\s+écoulé\s+à\s+la\s+station\s*=\s*([\d.,]+)\s*Hm3'),
            ('runoff_depth',r'Hauteur\s+de\s+la\s+lame\s+d.eau\s+écoulée\s*=\s*([\d.,]+)\s*mm'),
            ('discharge_historical_max',r'Crue\s+maximale\s+Observée\s*:\s*([\d.,]+)\s*m3/s[\s\S]{0,100}?\ble\s+([^\n]+)'),
        ]
        for metric,pattern in patterns:
            m=re.search(pattern,text,re.I)
            if not m: continue
            try:
                event=french_date(m[2]) if len(m.groups())>1 else None
            except (ValueError,IndexError):
                self.issue(page_sid,'INVALID_EVENT_DATE',m[0]); continue
            if len(m.groups())>1 and event is None:
                self.issue(page_sid,'UNPARSED_EVENT_DATE',m[0]); continue
            boxes=self.page.search_for(m[0])
            if not boxes:
                self.issue(page_sid,'SUMMARY_GEOMETRY',m[0]); continue
            box=boxes[0]
            for b in boxes[1:]:box |= b
            start,end=self.start,self.end
            if metric=='discharge_historical_max':start=end=event
            time_match=re.search(r'\b\d{2}:\d{2}\b',m[0])
            self.observation(eid,metric,m[1],box,page_sid,start,end,event=event,
                             event_time=time_match[0] if time_match else None)
        return True


def extract(scope='pilot'):
    records=register()
    build=build_fingerprint()
    run_id=scope+'-'+uid([r['sha256'] for r in records],build['sha256'])[:12]
    run=data_dir()/'runs'/run_id
    if (run/'database.sqlite').exists():
        with sqlite3.connect(run/'database.sqlite') as db:
            if db.execute("SELECT value FROM run_metadata WHERE key='finished'").fetchone()==('true',):
                return run_id
        # Never overwrite an interrupted run; retain it for diagnosis.
        from datetime import datetime
        run_id+='-'+datetime.now().strftime('%H%M%S')
        run=data_dir()/'runs'/run_id
    db=initialize(run/'database.sqlite')
    db.execute("INSERT INTO run_metadata VALUES ('build',?)",(json.dumps(build),))
    for metric,(definition,unit,kind) in METRICS.items():
        db.execute('INSERT INTO metrics VALUES (?,?,?,?,?)',(metric,definition,unit,kind,json.dumps(['lookup','compare'])))
    inv=[]
    for record in records:
        doc_id=record['document_id']
        start,end=campaign(record)
        db.execute('INSERT INTO documents VALUES (?,?,?,?,?)',(doc_id,record['original_name'],record['sha256'],record['page_count'],start[:4]+'-'+end[:4]))
        with pymupdf.open(root()/record['relative_path']) as pdf:
            for index,page in enumerate(pdf):
                n=index+1
                worker=Extractor(db,record,page,n)
                text=page.get_text(sort=True)
                words=page.get_text('words')
                footer=[w for w in words if w[1]>page.rect.height*.86 and w[4].isdigit() and len(w[4])<=3]
                worker.printed=footer[0][4] if len(footer)==1 else None
                page_sid=worker.source(page.rect,text,'page')
                # Short geometric blocks for retrieval; page is their parent, not a guessed station.
                for bi,b in enumerate(page.get_text('blocks')):
                    if len(b)>6 and b[6]==0 and len(b[4].strip())>30:
                        sid=worker.source(b[:4],b[4],'passage',page_sid)
                        db.execute('INSERT OR IGNORE INTO chunks VALUES (?,?,?,?,?)',
                            (uid(sid),sid,None,b[4],json.dumps({'document_id':doc_id,'page_pdf':n})))
                        db.execute('INSERT INTO chunks_fts VALUES (?,?)',(uid(sid),b[4]))
                selected=scope=='all' or n in PILOT[doc_id]
                family='documentary'
                state='documentary'
                reason='Texte/figure consultable ; aucune mesure structurée attribuée.'
                tables=[]
                if selected:
                    try:
                        finder=page.find_tables()
                        for ti,t in enumerate(finder.tables):
                            sid,rows=worker.raw_table(t,ti)
                            tables.append((t,sid,rows))
                        family='tables' if tables else 'documentary'
                        for t,sid,rows in tables:
                            if doc_id.startswith('pluvio') and n>=50 and worker.rain(t,rows,sid):
                                db.execute("UPDATE table_extractions SET state='extracted',reason='' WHERE source_id=?",(sid,))
                                family='rain_daily'
                        if doc_id.startswith('hydro') and worker.hydro(tables,page_sid):
                            family='hydro_station'
                        from dgre_rag.ingestion.families import gauging,rating,station_attributes,figures
                        if doc_id.startswith('hydro'):
                            station_attributes(worker,page_sid)
                            for t,sid,rows in tables:
                                if gauging(worker,t,rows,sid):
                                    db.execute("UPDATE table_extractions SET state='extracted',reason='' WHERE source_id=?",(sid,))
                                rating(worker,t,rows,sid,page_sid)
                        figures(worker,page_sid)
                        left=db.execute("SELECT count(*) FROM table_extractions t JOIN sources s USING(source_id) WHERE s.document_id=? AND s.page_pdf=? AND t.state='candidate'",(doc_id,n)).fetchone()[0]
                        state='partial' if left else ('processed' if worker.count else 'documentary')
                        reason=f'{left} tableau(x) conservé(s) brut(s), interprétation non validée.' if left else ''
                    except Exception as exc:
                        state='blocked';reason=type(exc).__name__+': '+str(exc)
                        worker.issue(page_sid,'UNSUPPORTED_LAYOUT',reason)
                else:
                    state='inventoried';reason='Hors pilote ; extraction complète à exécuter.'
                row=(doc_id,n,worker.printed,page.rect.width,page.rect.height,page.rotation,family,state,len(tables),worker.count,reason)
                db.execute('INSERT INTO page_inventory VALUES (?,?,?,?,?,?,?,?,?,?,?)',row)
                inv.append(dict(zip(['document_id','page_pdf','page_printed','width','height','rotation','family','state','tables_found','observations','reason'],row)))
                if n%20==0:
                    db.commit()
                    print(f'{doc_id}: {n}/{len(pdf)} pages',flush=True)
    if scope=='all':
        from dgre_rag.ingestion.reference_catalog import build_catalog
        from dgre_rag.ingestion.structured import store_catalog
        store_catalog(db,build_catalog(db,run_id))
    db.execute("INSERT INTO run_metadata VALUES ('finished','true')")
    db.execute("INSERT INTO run_metadata VALUES ('scope',?)",(scope,))
    db.commit();db.close()
    run.mkdir(parents=True,exist_ok=True)
    (run/'page_inventory.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in inv),encoding='utf-8')
    dump(data_dir()/'last_run.json',{'run_id':run_id})
    return run_id


def validate(run_id):
    if not re.fullmatch(r'[\w-]+',run_id):raise ValueError('INVALID_RUN')
    path=data_dir()/'runs'/run_id/'database.sqlite'
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('CREATE INDEX IF NOT EXISTS idx_selections_observation ON observation_selections(observation_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_context_table ON observation_context(table_source_id)')
    db.execute('DELETE FROM observation_selections')
    # Promote only structurally evidenced candidates, not arbitrary numeric cells.
    candidates=db.execute("SELECT * FROM observations WHERE quality_status='candidate'").fetchall()
    for observation in candidates:
        proofs=db.execute('''SELECT e.role,c.headers_json,c.normalized_value FROM observation_evidence e
            LEFT JOIN cells c USING(cell_id) WHERE e.observation_id=?''',(observation['observation_id'],)).fetchall()
        roles={p['role'] for p in proofs}
        cell_ok=any(p['role']=='value' and p['normalized_value']==observation['value_decimal'] and
            json.loads(p['headers_json'])==[observation['metric_id'],observation['period_start'],observation['period_end']] for p in proofs)
        valid=cell_ok and 'context' in roles and observation['unit']==METRICS[observation['metric_id']][1]
        if observation['value_status']=='dry_legend_pdf48':valid=valid and 'symbol_legend' in roles
        db.execute('UPDATE observations SET quality_status=?,validation_method=? WHERE observation_id=?',
            ('validated' if valid else 'blocked','layout_calendar_unit_evidence_v2' if valid else None,observation['observation_id']))
    groups=db.execute('''SELECT entity_id,metric_id,period_start,period_end,unit,baseline_id,event_time,
      group_concat(observation_id) ids FROM observations WHERE quality_status='validated'
      GROUP BY entity_id,metric_id,period_start,period_end,unit,baseline_id,event_time''').fetchall()
    for g in groups:
        ids=g['ids'].split(',')
        rows=[db.execute('SELECT * FROM observations WHERE observation_id=?',(i,)).fetchone() for i in ids]
        distinct={(Decimal(r['value_decimal']),r['event_date'],r['event_time']) for r in rows}
        if len(distinct)>1:
            for r in rows:
                db.execute("UPDATE observations SET quality_status='blocked',validation_method=NULL WHERE observation_id=?",(r['observation_id'],))
                sid=db.execute("SELECT source_id FROM observation_evidence WHERE observation_id=? AND role='value'",(r['observation_id'],)).fetchone()[0]
                db.execute('INSERT OR IGNORE INTO quality_issues VALUES (?,?,?,?,?,?,?,?)',
                    (uid(r['observation_id'],'conflict'),sid,r['observation_id'],'SOURCE_CONFLICT','error','open','Publications divergentes pour la même observation.',None))
        else:
            chosen=sorted(ids)[0]
            db.execute('INSERT INTO observation_selections VALUES (?,?,?,?)',
                (uid(*list(g)[:7]),chosen,'canonical-v2','Même valeur, unité, période et événement ; preuves conservées.'))
            # Preserve evidence of identical publications on the selected observation.
            for i in ids:
                for ev in db.execute('SELECT source_id,cell_id,role FROM observation_evidence WHERE observation_id=?',(i,)).fetchall():
                    db.execute('INSERT OR IGNORE INTO observation_evidence VALUES (?,?,?,?)',(chosen,*ev))
    db.execute('DELETE FROM coverage')
    daily=db.execute("SELECT entity_id,metric_id,min(period_start) first,max(period_end) last,count(DISTINCT period_start) available FROM observations WHERE metric_id IN ('rainfall_daily','discharge_daily_mean') GROUP BY entity_id,metric_id").fetchall()
    for r in daily:
        first=date.fromisoformat(r['first']);last=date.fromisoformat(r['last'])
        start=date(first.year-(first.month<9),9,1)
        end=date(last.year+(last.month>=9),8,31)
        valid=db.execute('SELECT count(*) FROM published_observations WHERE entity_id=? AND metric_id=?',(r['entity_id'],r['metric_id'])).fetchone()[0]
        db.execute('INSERT INTO coverage VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (uid(r['entity_id'],r['metric_id']),r['entity_id'],r['metric_id'],str(start),str(end),'daily',(end-start).days+1,r['available'],valid,r['available']-valid,'Dates distinctes ; symboles ambigus exclus.'))
    # Published totals retain their origin; inconsistencies are attached, never silently corrected.
    for summary in db.execute("SELECT * FROM published_observations WHERE metric_id IN ('rainfall_annual','rainfall_monthly','discharge_daily_max','discharge_daily_min','rainfall_daily_max')").fetchall():
        oid=summary['observation_id'];metric=summary['metric_id']
        child_metric='rainfall_monthly' if metric=='rainfall_annual' else ('rainfall_daily' if metric.startswith('rainfall') else 'discharge_daily_mean')
        children=db.execute('''SELECT * FROM published_observations WHERE entity_id=? AND metric_id=?
          AND period_start>=? AND period_end<=?''',(summary['entity_id'],child_metric,summary['period_start'],summary['period_end'])).fetchall()
        value=Decimal(summary['value_decimal']);values=[Decimal(c['value_decimal']) for c in children]
        note=None
        if metric=='rainfall_annual' and len(children)==12:
            tolerance=sum((Decimal(c['precision_decimal'] or '0')/2 for c in children),Decimal(0))+Decimal(summary['precision_decimal'] or '0')/2
            if abs(sum(values,Decimal(0))-value)>tolerance:
                note='Le total publié diffère de la somme des douze totaux mensuels au-delà de leurs précisions ; aucune correction automatique.'
        elif metric.endswith('_max') and values and max(values)>value+Decimal(summary['precision_decimal'] or '0'):
            note='Au moins une mesure quotidienne extraite dépasse le maximum publié. Comparer la fiche et la série avant interprétation.'
        elif metric.endswith('_min') and values and min(values)<value-Decimal(summary['precision_decimal'] or '0'):
            note='Une mesure quotidienne extraite est inférieure au minimum publié. Comparer la fiche et la série avant interprétation.'
        if metric=='rainfall_monthly':
            missing=db.execute("SELECT count(DISTINCT period_start) FROM observations WHERE entity_id=? AND metric_id='rainfall_daily' AND period_start>=? AND period_end<=? AND value_status='missing'",(summary['entity_id'],summary['period_start'],summary['period_end'])).fetchone()[0]
            if missing:db.execute('UPDATE observation_context SET missing_days=? WHERE observation_id=?',(missing,oid))
        if note:
            sid=db.execute("SELECT source_id FROM observation_evidence WHERE observation_id=? AND role='value'",(oid,)).fetchone()[0]
            db.execute('INSERT OR IGNORE INTO quality_issues VALUES (?,?,?,?,?,?,?,?)',(uid(oid,'SUMMARY_INCONSISTENCY'),sid,oid,'SUMMARY_INCONSISTENCY','warning','open',note,None))
            db.execute('UPDATE observation_context SET note=? WHERE observation_id=?',(note,oid))
    from dgre_rag.ingestion.structured import update_availability
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='availability'").fetchone():update_availability(db)
    integrity(db)
    db.execute("INSERT OR REPLACE INTO run_metadata VALUES ('validated','true')")
    db.commit()
    stats={name:db.execute(sql).fetchone()[0] for name,sql in {
        'pages':'SELECT count(*) FROM page_inventory','tables':'SELECT count(*) FROM table_extractions',
        'observations':'SELECT count(*) FROM observations','published':'SELECT count(*) FROM published_observations',
        'blocked':"SELECT count(*) FROM observations WHERE quality_status='blocked'",
        'conflicts':"SELECT count(*) FROM quality_issues WHERE code='SOURCE_CONFLICT'",
        'pages_partial':"SELECT count(*) FROM page_inventory WHERE state IN ('partial','blocked')"}.items()}
    db.close();dump(path.parent/'validation.json',stats)
    return stats
