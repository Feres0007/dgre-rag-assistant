import json
import re
import os
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
import numpy as np
from dgre_rag.config import settings
from dgre_rag.storage.database import connect, release_path, dump, file_hash,uid
from dgre_rag.providers.local import embeddings
from dgre_rag.ingestion.pipeline import plain


def build_index(release_id=None,allow_download=False):
    path=release_path(release_id)
    with connect(path.name) as db:
        sources=db.execute("SELECT source_id,raw_text FROM sources WHERE kind='passage' ORDER BY document_id,page_pdf,y0,x0").fetchall()
    rows=[]
    for source in sources:
        text=source['raw_text']
        # Geometric passages retain their page parent. Split only at line boundaries.
        windows=[];current=''
        for line in text.splitlines(keepends=True):
            if current and len(current)+len(line)>1400:windows.append(current);current=''
            current+=line
        if current:windows.append(current)
        for start,window in enumerate(windows):
            if sum(c.isalpha() for c in window)<40:continue
            rows.append({'chunk_id':'v-'+uid(source['source_id'],start),'source_id':source['source_id'],'text':window})
    model=embeddings(allow_download)
    # Trim at input only; full passages remain attached to source records.
    vectors=np.array(list(model.embed([r['text'] for r in rows],batch_size=32)),dtype=np.float32)
    vectors/=np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-12)
    index_id=uid(file_hash(path/'database.sqlite'),settings().embedding_model,'logical-passages-v2')[:16]
    index_file=path/f'vectors-{index_id}.npz'
    with (path/'vectors.tmp').open('wb') as stream:
        np.savez_compressed(stream,vectors=vectors,ids=np.array([r['chunk_id'] for r in rows]),
             source_ids=np.array([r['source_id'] for r in rows]),texts=np.array([r['text'] for r in rows]))
    os.replace(path/'vectors.tmp',index_file)
    dump(path/'index.json',{'release_id':path.name,'database_sha256':file_hash(path/'database.sqlite'),
         'model':settings().embedding_model,'file':index_file.name,'sha256':file_hash(index_file),'count':len(rows),
         'chunking':'logical-passages-v2','dimensions':int(vectors.shape[1])})
    return {'chunks':len(rows),'model':settings().embedding_model}


STOP={'le','la','les','de','des','du','un','une','en','au','aux','et','est','quel','quelle','quels','quelles','pour','dans','a','à','sur','il','elle','que','comment','donne','moi'}


def terms(text):
    return [w[:-1] if w.endswith('s') and len(w)>4 else w for w in re.findall(r'[a-z0-9]+',plain(text)) if w not in STOP and len(w)>1]


@lru_cache(maxsize=3)
def page_catalog(release_id):
    with connect(release_id) as db:
        pages=[dict(p) for p in db.execute("SELECT * FROM sources WHERE kind='page'")]
    counts=[Counter(terms(p['raw_text'])) for p in pages]
    df=Counter(w for c in counts for w in c)
    avg=sum(sum(c.values()) for c in counts)/max(1,len(counts))
    return pages,counts,df,avg


def page_search(question,release_id,allowed=None):
    pages,counts,df,avg=page_catalog(release_id);query=set(terms(question))
    ranked=[]
    for page,counts in zip(pages,counts):
        if allowed is not None and (page['document_id'],page['page_pdf']) not in allowed:continue
        score=0;length=sum(counts.values())
        for word in query:
            frequency=counts.get(word,0)
            if frequency:
                idf=math.log(1+(len(pages)-df[word]+.5)/(df[word]+.5))
                score+=idf*frequency*2.2/(frequency+1.2*(.25+.75*length/max(avg,1)))
        if score:ranked.append((score,page))
    return sorted(ranked,key=lambda item:-item[0])[:30]


def excerpt(text,question):
    query=set(terms(question))
    windows=[text[start:start+1600] for start in range(0,len(text),800)]
    return max(windows,key=lambda window:len(set(terms(window)) & query),default=text)


def eligible_pages(db, filters):
    """Intersect metadata BEFORE top-k. Empty eligibility must stay empty."""
    from dgre_rag.domain.models import SearchFilters
    f=filters if isinstance(filters,SearchFilters) else SearchFilters.model_validate(filters or {})
    allowed={(r[0],r[1]) for r in db.execute("SELECT document_id,page_pdf FROM sources WHERE kind='page'")}
    if f.document_id:allowed={r for r in allowed if r[0]==f.document_id}
    if f.entity_id:
        allowed&={(r[0],r[1]) for r in db.execute('''SELECT s.document_id,s.page_pdf FROM entity_mentions m
            JOIN sources s USING(source_id) WHERE m.entity_id=?''',(f.entity_id,))}
    if f.period:
        allowed&={(r[0],r[1]) for r in db.execute('''SELECT s.document_id,s.page_pdf FROM observations o
            JOIN observation_evidence e USING(observation_id) JOIN sources s USING(source_id)
            WHERE o.period_start>=? AND o.period_end<=?''',(str(f.period.start),str(f.period.end)))}
    if f.basin:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='entity_assertions'").fetchone():return set()
        allowed&={(r[0],r[1]) for r in db.execute('''SELECT s.document_id,s.page_pdf FROM entity_assertions a
            JOIN entity_mentions m USING(entity_id) JOIN sources s ON s.source_id=m.source_id
            WHERE a.attribute='basin' AND a.normalized_value=? AND a.status='validated' ''',(f.basin,))}
    if f.content_type:
        allowed&={(r[0],r[1]) for r in db.execute('SELECT document_id,page_pdf FROM sources WHERE kind=?',(f.content_type,))}
    return allowed


def retrieve(question,release_id=None,limit=None,mode='hybrid',filters=None):
    path=release_path(release_id)
    limit=limit or settings().final_passages
    tokens=[w for w in re.findall(r'[\wÀ-ÿ]+',question.lower()) if w not in STOP and len(w)>1]
    ranks={}; warnings=[];extra={};anchors=[];preferred=[]
    with connect(path.name) as db:
        allowed=eligible_pages(db,filters) if filters else None
        from dgre_rag.domain.models import SearchFilters
        selected_filters=filters if isinstance(filters,SearchFilters) else SearchFilters.model_validate(filters or {})
        if allowed==set():return [],['Aucun passage dans le périmètre demandé ; cela ne prouve pas une absence dans les documents.']
        if selected_filters.content_type in ('table','figure','passage'):
            query=set(terms(question));records=[]
            for record in db.execute('SELECT * FROM sources WHERE kind=?',(selected_filters.content_type,)):
                if allowed is not None and (record['document_id'],record['page_pdf']) not in allowed:continue
                score=len(query & set(terms(record['raw_text'])))
                if score:records.append(dict(record)|{'text':record['raw_text'],'score':score})
            return sorted(records,key=lambda r:-r['score'])[:limit],[]
        if tokens:
            query=' OR '.join('"'+t.replace('"','')+'"' for t in tokens[:30])
            lexical=db.execute('SELECT chunk_id,bm25(chunks_fts) rank FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank'+(' LIMIT 30' if allowed is None else ''),(query,)).fetchall()
        if mode!='vector':
            for rank,(_,page) in enumerate(page_search(question,path.name,allowed)):
                key='page-'+page['source_id'];ranks[key]=1/(60+rank+1)
                extra[key]=page|{'chunk_id':key,'text':excerpt(page['raw_text'],question)}
                if mode=='hybrid' and rank==0:anchors.append(key)
            # FTS5 adds exact-match passages even when their parent has a low length-normalized score.
            for rank,hit in enumerate(lexical if tokens else []):
                record=db.execute('''SELECT p.* FROM chunks c JOIN sources s ON s.source_id=c.source_id
                    JOIN sources p ON p.source_id=s.parent_id WHERE c.chunk_id=?''',(hit['chunk_id'],)).fetchone()
                if record:
                    if allowed is not None and (record['document_id'],record['page_pdf']) not in allowed:continue
                    page=dict(record);key='page-'+page['source_id']
                    ranks[key]=max(ranks.get(key,0),.7/(60+rank+1))
                    if key not in extra:extra[key]=page|{'chunk_id':key,'text':excerpt(page['raw_text'],question)}
        if mode!='lexical':
            try:
                manifest=json.loads((path/'index.json').read_text(encoding='utf-8'))
                if manifest['release_id']!=path.name or manifest['model']!=settings().embedding_model:
                    raise ValueError('INDEX_VERSION_MISMATCH')
                # Database hash is immutable within a release and checked on activation.
                release=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
                if manifest['database_sha256']!=release['database_sha256']:
                    raise ValueError('INDEX_VERSION_MISMATCH')
                with np.load(path/manifest['file'],allow_pickle=False) as index:
                    q=np.array(list(embeddings().query_embed(question))[0]);q/=max(np.linalg.norm(q),1e-12)
                    scores=index['vectors']@q
                    vector_seen=set()
                    positions=np.argsort(-scores)
                    if allowed is not None and 'source_ids' in index:
                        eligible_ids={r['source_id'] for r in db.execute('SELECT source_id,document_id,page_pdf FROM sources') if (r['document_id'],r['page_pdf']) in allowed}
                        positions=[pos for pos in positions if str(index['source_ids'][pos]) in eligible_ids]
                    for rank,pos in enumerate(positions[:60]):
                        key=str(index['ids'][pos])
                        if 'source_ids' in index:
                            sid=str(index['source_ids'][pos])
                            record=db.execute('SELECT * FROM sources WHERE source_id=?',(sid,)).fetchone()
                            key='page-'+sid
                            if key in vector_seen:continue
                            vector_seen.add(key)
                            ranks[key]=ranks.get(key,0)+1/(60+len(vector_seen))
                            if mode=='hybrid' and len(vector_seen)<=2:anchors.append(key)
                            if record and key not in extra:extra[key]=dict(record)|{'chunk_id':key,'text':str(index['texts'][pos])}
                        else:
                            ranks[key]=ranks.get(key,0)+1/(60+rank+1)
            except (OSError,ValueError,RuntimeError) as exc:
                warnings.append('Recherche lexicale seule : index vectoriel indisponible ou incompatible.')
        # Resolve station mentions before semantic ranking; include adjacent source notes.
        from dgre_rag.query.planner import entities
        candidates=entities(question,path.name)
        strong=[e for e in candidates if e.get('match_score',0)>=1]
        if not strong and any(w in plain(question) for w in ('crue','hydrom','etalonn','debit','equipement')):
            strong=[e for e in candidates if e['kind']=='hydro_station' and e.get('match_score',0)>=.4]
        last_requested=any(w in plain(question) for w in ('derniere fiche','derniere page','dernier tableau'))
        if not strong and last_requested:strong=[e for e in candidates if e.get('match_score',0)>=.4]
        locations=set()
        for entity in strong:
            locations.update((r[0],r[1]) for r in db.execute('''SELECT DISTINCT s.document_id,s.page_pdf
              FROM entity_mentions m JOIN sources s USING(source_id) WHERE m.entity_id=?''',(entity['entity_id'],)))
        if last_requested and locations:
            locations={max(locations,key=lambda loc:loc[1])}
        elif locations:
            locations|={(doc,n+1) for doc,n in list(locations) if doc.startswith('hydro')}
        for doc,n in locations:
            if allowed is not None and (doc,n) not in allowed:continue
            record=db.execute("SELECT * FROM sources WHERE kind='page' AND document_id=? AND page_pdf=?",(doc,n)).fetchone()
            if record:
                page=dict(record);key='page-'+page['source_id'];ranks[key]=ranks.get(key,0)+.04
                preferred.append(key)
                if key not in extra:extra[key]=page|{'chunk_id':key,'text':excerpt(page['raw_text'],question)}
        result=[];seen=set()
        order=list(dict.fromkeys(preferred+anchors+[key for key,_ in sorted(ranks.items(),key=lambda pair:-pair[1])]))
        for cid in order:
            score=ranks[cid]
            r=extra.get(cid)
            if r is None:
                record=db.execute('''SELECT c.chunk_id,c.text,s.* FROM chunks c JOIN sources s USING(source_id)
                     WHERE c.chunk_id=?''',(cid,)).fetchone()
                if not record:continue
                r=dict(record)
            key=(r['document_id'],r['page_pdf'],r['raw_text'])
            if allowed is not None and key[:2] not in allowed:continue
            if key in seen:continue
            seen.add(key);result.append(dict(r)|{'score':score})
            if len(result)>=limit:break
    return result,warnings
