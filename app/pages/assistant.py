import streamlit as st
import pandas as pd
from dgre_rag.answers.conversation import readable,export_table,result_rows
from common import service,ready,sources_buttons,entity_label
from dgre_rag.domain.models import Answer
from dgre_rag.answers.service import display_number,display_date
from dgre_rag.domain.catalog import METRICS
from design import assistant_header

assistant_header()
ready();srv=service()
if 'messages' not in st.session_state:st.session_state.messages=[]
if 'pending_question' not in st.session_state:st.session_state.pending_question=None
if st.sidebar.button('Nouvelle conversation',use_container_width=True):
    st.session_state.messages=[];st.session_state.pending_question=None;st.rerun()

context={}

if not st.session_state.messages:
    examples=['Quel est le maximum journalier de Pont de Bizerte en 2022-2023 ?',
              'Compare les débits moyens annuels de Slouguia et Mejez GP5 en 2022-2023.',
              'Montre les pluies mensuelles à Aïn Draham en 2022-2023.',
              'Quelles données sont disponibles ?']
    st.markdown('<div class="section-kicker">Pour commencer · Choisissez une question</div>',unsafe_allow_html=True)
    labels=['💧 Débits & crues','⇄ Comparer deux stations','☔ Pluies mensuelles','▤ Données disponibles']
    for start in range(0,len(examples),2):
        columns=st.columns(2)
        for offset,column in enumerate(columns):
            i=start+offset
            with column:
                with st.container(border=True):
                    st.markdown(f'**{labels[i]}**')
                    if st.button(examples[i],key=f'example-{i}',use_container_width=True):
                        st.session_state['example_question']=examples[i]
    st.caption('Poursuivez ensuite avec « Compare les deux », « Fais un graphique » ou « Montre les sources ».')

for index,item in enumerate(st.session_state.messages):
    with st.chat_message('user'):st.write(item['question'])
    with st.chat_message('assistant'):
        if item['release_id']!=srv.release_id:st.info('Les documents disponibles ont été mis à jour depuis cette réponse.')
        st.markdown(item['text'])
        if item['status']!='answered':
            st.caption({'partial':'Réponse partielle','ambiguous':'Précision nécessaire','not_found':'Non retrouvé','unvalidated_data':'Données non utilisables','source_conflict':'Conflit de sources','technical_error':'Service indisponible','out_of_scope':'Hors périmètre'}.get(item['status'],item['status']))
        if item['limits']:
            for limit in item['limits']:st.warning(limit)
        if item['calculations']:
            with st.expander('Comment ce résultat a été obtenu'):
                from dgre_rag.answers.service import calculation_sentence
                for calculation in item['calculations']:
                    st.write(calculation_sentence(calculation))
                    coverage=calculation.get('coverage',{})
                    if 'available' in coverage:st.caption(f"{coverage['available']} jours couverts sur {coverage.get('expected',coverage['available'])}.")
        rows=result_rows(item)
        if rows:
            with st.expander('Valeurs lues dans les tableaux'):
                if item.get('presentation','text')=='text':st.dataframe(readable(rows[:500]),hide_index=True)
                st.caption(f'{len(rows)} valeurs disponibles. Les données complètes sont incluses dans le téléchargement.')
            if item.get('presentation') in ('table','chart','export'):
                st.dataframe(readable(rows[:500]),hide_index=True)
            if item.get('presentation')=='chart':
                groups={(r['metric_id'],r['unit']) for r in rows}
                if len(groups)==1:
                    chart=pd.DataFrame([{'Date':r['period_start'],'Station':r['canonical_name'],'Valeur':float(r['value_decimal'])} for r in rows])
                    if chart['Date'].nunique()>1:
                        chart['Date']=pd.to_datetime(chart['Date'])
                        st.scatter_chart(chart,x='Date',y='Valeur',color='Station')
                    else:st.bar_chart(chart,x='Station',y='Valeur')
                    st.caption('Unité : '+rows[0]['unit'].replace('m3','m³')+'. Points disponibles uniquement, sans interpolation des lacunes.')
                else:st.info('Ces mesures utilisent des indicateurs ou des unités différents. Elles restent présentées dans le tableau.')
            st.download_button('Télécharger les valeurs',export_table(rows,item['citations']),file_name='donnees_dgre.csv',mime='text/csv',key=f'csv-{index}')
        if item['citations']:
            with st.expander('Consulter les sources'):
                sources_buttons([c|{'release_id':item['release_id']} for c in item['citations']],f'answer-{index}')
        st.download_button('Exporter cette réponse',srv.export_answer(item),file_name='reponse_dgre.md',mime='text/markdown',key=f'export-{index}')

question=st.chat_input('Une station, une pluie, un débit… posez votre question')
example=st.session_state.pop('example_question',None)
question=question or example
if question:
    with st.spinner('Recherche des informations et vérification des données…'):
        result=srv.ask(question,context,history=st.session_state.messages)
    st.session_state.messages.append(result.model_dump(mode='json'))
    st.rerun()
