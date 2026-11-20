"""Conservative family parsers: preserve coordinates, symbols and uncertain units."""
import json
import re
from decimal import Decimal
import pymupdf
from dgre_rag.storage.database import uid
from dgre_rag.domain.models import number


def record(worker,family,payload,sid,status='source_bound'):
    wrapped={'key':uid(family,sid,payload),'record':payload,'container':'list'}
    worker.db.execute('INSERT OR IGNORE INTO structured_records VALUES (?,?,?,?,?,?)',
        (wrapped['key'],family,json.dumps(wrapped,ensure_ascii=False),sid,status,'family_geometry_v2'))


def gauging(worker,t,rows,sid):
    from dgre_rag.ingestion.pipeline import plain,french_date
    if not rows or len(rows[0])!=6:return False
    headers=' '.join(str(c or '') for c in rows[0])
    h=plain(headers).replace(' ','')
    if not all(word in h for word in ('date','heure','debit','rs')):return False
    if not ('m3/s' in h or 'l/s' in h):return False
    before=worker.page.get_textbox(pymupdf.Rect(0,0,worker.page.rect.width,t.bbox[1]))
    matches=list(re.finditer(r'STATION\s*:\s*([^\n]+)',before,re.I))
    if not matches:return False
    name=matches[-1][1].strip();context=before[matches[-1].start():]
    basin=re.search(r'BASSIN\s*:\s*([^\n]+)',context,re.I)
    basin=basin[1].strip() if basin else ''
    eid=uid('gauging_station',worker.doc_id,plain(name),plain(basin))
    worker.db.execute('INSERT OR IGNORE INTO entities VALUES (?,?,?)',(eid,'gauging_station',name))
    worker.db.execute('INSERT OR IGNORE INTO entity_mentions VALUES (?,?,?,?,?,?)',
        (uid(eid,sid),eid,sid,None,name,'name_basin_occurrence'))
    if basin:worker.db.execute('INSERT OR IGNORE INTO entity_assertions VALUES (?,?,?,?,?,?,?,?)',
        (uid(eid,sid,'basin'),eid,'basin',basin,plain(basin),None,sid,'validated'))
    for ri,row in enumerate(rows[1:],1):
        if len(row)!=6:continue
        try:day=french_date(str(row[1] or ''))
        except ValueError:continue
        if not day:continue
        time=str(row[2] or '').strip().replace('.',':')
        if not re.fullmatch(r'(?:[01]?\d|2[0-3]):[0-5]\d',time):time=None
        for col,metric in ((3,'gauging_height'),(4,'gauging_discharge'),(5,'dry_residue')):
            raw=str(row[col] or '').strip();box=t.rows[ri].cells[col]
            if not box:continue
            oid=worker.observation(eid,metric,raw,box,sid,day,day,event=day,event_time=time,row=ri,col=col,
                force_block='TIME_UNRESOLVED' if time is None else None)
            if metric=='gauging_discharge' and 'l/s' in h and 'm3/s' not in h:
                value,status=number(raw)
                if value is not None:
                    normalized=str(Decimal(value)/1000)
                    worker.db.execute('UPDATE observations SET value_decimal=?,precision_decimal=? WHERE observation_id=?',
                        (normalized,str(Decimal(1).scaleb(Decimal(value).as_tuple().exponent)/1000),oid))
                    worker.db.execute('UPDATE cells SET normalized_value=? WHERE cell_id IN (SELECT cell_id FROM observation_evidence WHERE observation_id=?)',(normalized,oid))
                    worker.db.execute("UPDATE observation_context SET note='Débit publié en L/s ; conversion exacte en m³/s par division par 1000.' WHERE observation_id=?",(oid,))
            record(worker,'gauging_states',{'entity_id':eid,'name':name,'date':day,'time':time,'metric_id':metric,'raw':raw,
                'source':dict(worker.db.execute('SELECT * FROM sources WHERE source_id=?',(sid,)).fetchone())},sid)
    return True


def station_attributes(worker,page_sid):
    from dgre_rag.ingestion.pipeline import plain
    mentions=worker.db.execute('''SELECT DISTINCT e.entity_id FROM entities e JOIN entity_mentions m USING(entity_id)
        WHERE m.source_id=? AND e.kind='hydro_station' ''',(page_sid,)).fetchall()
    if len(mentions)!=1:return
    eid=mentions[0][0];text=worker.page.get_text()
    for attribute,pattern,unit in (
        ('basin',r'Bassin\s*:\s*([^\n]+)',None),
        ('river',r'Cours d.eau\s*:\s*([^\n]+)',None),
        ('basin_area',r'Superficie Bassin\s*\([^)]*\)\s*:\s*(\d+(?:[.,]\d+)?)','km2'),
        ('altitude',r'Altitude approximative\s*\([^)]*\)\s*:\s*(\d+(?:[.,]\d+)?)','m')):
        match=re.search(pattern,text,re.I)
        if not match:continue
        boxes=worker.page.search_for(match[0])
        if not boxes:continue
        box=boxes[0]
        for b in boxes[1:]:box|=b
        sid=worker.source(box,match[0],'attribute',page_sid)
        raw=match[1].strip();normalized=number(raw)[0] if unit else plain(raw)
        worker.db.execute('INSERT OR IGNORE INTO entity_assertions VALUES (?,?,?,?,?,?,?,?)',
            (uid(eid,attribute,sid),eid,attribute,raw,normalized,unit,sid,'candidate' if unit=='km2' else 'validated'))


def rating(worker,t,rows,sid,page_sid):
    from dgre_rag.ingestion.pipeline import plain,french_date
    mentions=worker.db.execute('SELECT DISTINCT entity_id FROM entity_mentions WHERE source_id=?',(page_sid,)).fetchall()
    if len(mentions)!=1:return False
    handled=False
    for ri,row in enumerate(rows):
        for ci,cell in enumerate(row):
            text=str(cell or '')
            if 'etalonnage' not in plain(text):continue
            # Read the full rating panel, not fragmented sub-tables with shifted headings.
            if not re.search(r'\(cm\).*\(m3/\s*s\)',text,re.S):continue
            validity=re.search(r'Valide du\s*(\d{2}/\d{2}/\d{4})',text,re.I)
            if not validity:continue
            start=french_date(validity[1])
            end_match=re.search(r'(?:au|jusqu.au)\s*(\d{2}/\d{2}/\d{4})',text,re.I)
            end=french_date(end_match[1]) if end_match else worker.end if 'nos' in plain(text) and 'jours' in plain(text) else None
            if not end:continue
            box=t.rows[ri].cells[ci]
            if not box:continue
            psid=worker.source(box,text,'rating_panel',sid);curve=uid(mentions[0][0],psid,start,end)
            for line in text.splitlines():
                tokens=line.split()
                if len(tokens) not in (2,4) or any(number(v)[0] is None for v in tokens):continue
                for offset in range(0,len(tokens),2):
                    height,discharge=map(lambda v:number(v)[0],tokens[offset:offset+2])
                    proof=dict(worker.db.execute('SELECT * FROM sources WHERE source_id=?',(psid,)).fetchone())
                    point={'entity_id':mentions[0][0],'curve_id':curve,'height':str(Decimal(height)/100),'height_raw':tokens[offset],
                        'height_unit':'m','discharge':discharge,'discharge_unit':'m3/s','valid_from':start,'valid_to':end,
                        'validity_note':'Validité limitée au document publié ; aucune validité actuelle supposée.',
                        'quality_status':'validated','evidence_ids':[psid],'source':proof}
                    record(worker,'rating_points',point,psid,'validated');handled=True
    return handled


def figures(worker,page_sid):
    from dgre_rag.ingestion.pipeline import plain
    text=worker.page.get_text(sort=True)
    captions=[line.strip() for line in text.splitlines() if re.match(r'\s*(?:Figure\w*\s*\d+|\d+\s*/\s*Hydrogramme)',line,re.I)]
    for caption in captions:
        sid=worker.source(worker.page.rect,caption,'figure',page_sid)
        worker.db.execute('INSERT OR IGNORE INTO figure_annotations(source_id,caption) VALUES (?,?)',(sid,caption))
        worker.db.execute('INSERT OR IGNORE INTO source_links VALUES (?,?,?)',(sid,page_sid,'caption_on_page'))
        for row in worker.db.execute("SELECT source_id FROM sources WHERE document_id=? AND page_pdf=? AND kind='table'",(worker.doc_id,worker.n)).fetchall():
            worker.db.execute('INSERT OR IGNORE INTO source_links VALUES (?,?,?)',(sid,row[0],'table_on_page'))
