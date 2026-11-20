from functools import lru_cache
import requests
from dgre_rag.config import settings, data_dir


def model_status():
    config=settings()
    try:
        response=requests.get(config.llm_url+'/api/tags',timeout=3)
        response.raise_for_status()
        names=[m['name'] for m in response.json()['models']]
        selected=next((m for m in response.json()['models'] if m['name']==config.llm_model),{})
        return {'available': config.llm_model in names, 'model':config.llm_model, 'installed':names,
                'digest':selected.get('digest'),'size':selected.get('size')}
    except (requests.RequestException,ValueError,KeyError):
        return {'available':False,'model':config.llm_model,'installed':[]}


def generate(prompt, schema=None, system='', timeout=None, max_tokens=500):
    config=settings()
    payload={'model':config.llm_model,'prompt':prompt,'system':system,'stream':False,
             'options':{'temperature':0,'num_ctx':4096,'num_predict':max_tokens},'keep_alive':'5m'}
    if schema:payload['format']=schema
    try:
        response=requests.post(config.llm_url+'/api/generate',json=payload,timeout=(5,timeout or config.timeout_seconds))
        response.raise_for_status()
        return response.json()['response']
    except (requests.RequestException,KeyError,ValueError) as exc:
        raise RuntimeError('MODEL_UNAVAILABLE') from exc


@lru_cache(maxsize=2)
def embeddings(allow_download=False):
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=settings().embedding_model,cache_dir=str(data_dir()/'models'),
                         local_files_only=not allow_download,threads=4)
