import streamlit as st
from dgre_rag.answers.service import Service


def service():return Service()


def ready():
    if not service().release_id:
        st.info('Les documents ne sont pas encore prêts à être consultés. Leur préparation doit être terminée avant de poser une question.')
        st.stop()


def sources_buttons(citations,key):
    distinct={}
    for c in citations:
        loc=(c['document_id'],c['page_pdf'])
        if loc not in distinct:distinct[loc]=c
    for i,c in enumerate(distinct.values()):
        name='Hydrologique' if c['document_id'].startswith('hydro') else 'Pluviométrique'
        if st.button(f"Voir {name} — page PDF {c['page_pdf']}",key=f'{key}-{i}'):
            st.session_state['selected_source']={'document_id':c['document_id'],'page_pdf':c['page_pdf'],'source_id':c['source_id'],'release_id':c.get('release_id',service().release_id)}
            st.switch_page('pages/sources.py')


def entity_label(entity):
    return f"{entity['canonical_name']} · {entity.get('codes') or entity['entity_id'][:8]}"
