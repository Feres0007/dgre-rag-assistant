import streamlit as st
from common import service,ready
from dgre_rag.answers.service import Service
from dgre_rag.ingestion.pipeline import source_path
from design import sources_header

sources_header()
if st.button('Retour à la conversation'):
    st.switch_page('pages/assistant.py')
ready();selected=st.session_state.get('selected_source',{})
srv=Service(selected.get('release_id')) if selected else service()
if selected and srv.release_id!=service().release_id:st.info('Preuve ouverte dans la release de la réponse d’origine.')
documents=srv.documents();ids=[d['document_id'] for d in documents]
index=ids.index(selected['document_id']) if selected.get('document_id') in ids else 0
document=st.selectbox('Document',documents,index=index,format_func=lambda d:d['original_name'])
default=selected.get('page_pdf',1) if selected.get('document_id')==document['document_id'] else 1
page=int(st.number_input('Numéro de page PDF',min_value=1,max_value=document['page_count'],value=min(default,document['page_count']),step=1,key=f"source-page-{document['document_id']}-{default}"))
sid=selected.get('source_id') if (document['document_id'],page)==(selected.get('document_id'),selected.get('page_pdf')) else None
scale=st.select_slider('Zoom',options=[1.0,1.5,2.0,2.5],value=1.5)
try:
    result=srv.get_source_page(document['document_id'],page,sid,scale)
except (ValueError,OSError):
    st.error('La source demandée est indisponible ou ne correspond plus au document enregistré. Vérifiez le corpus avant de reprendre la consultation.')
    st.stop()
st.caption(f"Page PDF {page}/{document['page_count']} · Page imprimée : {result['page_printed'] or 'non identifiée automatiquement'}")
st.image(result['image'],width='stretch')
if result['source']:
    with st.expander('Détail de la preuve'):
        st.text(result['source']['raw_text']);st.caption('Repère PDF en points, origine en haut à gauche, avant rotation.')
        st.json({k:result['source'][k] for k in ['source_id','x0','y0','x1','y1']})
if st.button('Préparer le téléchargement du PDF original'):
    st.download_button('Télécharger le PDF original',source_path(document['document_id']).read_bytes(),file_name=document['original_name'],mime='application/pdf')
