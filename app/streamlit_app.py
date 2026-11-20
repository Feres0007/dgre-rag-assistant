import sys
import os
from pathlib import Path
source_root=str(Path(__file__).resolve().parents[1]/'src')
sys.path.insert(0,source_root)
# Streamlit watches the app folder and PYTHONPATH, not arbitrary sys.path entries.
# Include the editable package so page reruns cannot keep stale service modules.
watch_paths=[p for p in os.environ.get('PYTHONPATH','').split(os.pathsep) if p]
if source_root not in watch_paths:
    os.environ['PYTHONPATH']=os.pathsep.join([source_root,*watch_paths])
sys.path.insert(0,str(Path(__file__).resolve().parent))
import streamlit as st
from dgre_rag.answers.service import Service
from design import apply_design

st.set_page_config(page_title='Assistant Eau — Votre conversation',page_icon='💧',layout='centered')
apply_design()
st.sidebar.markdown('''<div class="dgre-brand"><div class="dgre-symbol">≈</div>
    <div><strong>DGRE · Eau</strong><small>Votre assistant IA documentaire</small></div></div>''',unsafe_allow_html=True)
service=Service()
st.session_state['active_release']=service.release_id

@st.cache_data(ttl=15)
def status(release):
    return Service(release).get_status()

current=status(service.release_id)
if service.release_id:
    st.sidebar.markdown('<div class="dgre-status">● Documents prêts à consulter</div>',unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="dgre-status pending">○ Documents en attente de préparation</div>',unsafe_allow_html=True)
if not current['model']['available']:st.sidebar.caption('Les explications rédigées sont momentanément indisponibles.')
with st.sidebar.expander('À propos de cet assistant'):
    st.write('Posez vos questions sur les annuaires hydrologique et pluviométrique 2022–2023. Les réponses s’appuient sur les documents et les données vérifiées disponibles sur cet ordinateur.')
    st.caption('Les sources restent accessibles pour vérifier les réponses.')

navigation=st.navigation([
    st.Page('pages/assistant.py',title='Assistant',icon='💬',default=True),
    st.Page('pages/sources.py',title='Sources',icon='📖'),
])
navigation.run()
