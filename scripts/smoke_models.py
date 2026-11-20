from dgre_rag.answers.service import Service
from dgre_rag.storage.database import dump
from dgre_rag.config import root
from datetime import datetime,timezone
import requests,time

start=time.perf_counter()
service=Service()
answer=service.ask('Que signifie la couleur grise dans les fiches de pluie ?')
result={'status':answer.status,'text':answer.text,'limits':answer.limits,
        'citation_pages':[(c['document_id'],c['page_pdf']) for c in answer.citations],
        'elapsed_seconds':time.perf_counter()-start,'timestamp':datetime.now(timezone.utc).isoformat(),
        'release_id':service.release_id}
try:
    response=requests.get('http://127.0.0.1:8501/_stcore/health',timeout=5)
    result['streamlit_health']={'status_code':response.status_code,'body':response.text}
except requests.RequestException as exc:result['streamlit_health']={'error':str(exc)}
dump(root()/'reports/model_smoke.json',result)
print(result)

