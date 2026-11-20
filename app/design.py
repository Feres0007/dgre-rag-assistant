"""Identité visuelle partagée par la conversation et les preuves documentaires."""
import streamlit as st


def apply_design():
    st.markdown('''<style>
    :root { --water: #087f8c; --deep: #123e50; --ink: #193b4a; }
    .stApp { background: radial-gradient(ellipse at 85% 0%, #dcf2f4 0%, transparent 48%), #f5f9fa; }
    .block-container { max-width: 1060px; padding-top: 2.2rem; padding-bottom: 7rem; }
    h1, h2, h3 { color: var(--deep); letter-spacing: -.035em; }
    [data-testid="stSidebar"] { background: #eaf3f5; border-right: 1px solid #d6e5e9; }
    [data-testid="stSidebar"] .stButton button { border-radius: 12px; }
    .dgre-brand { display: flex; align-items: center; gap: 12px; margin: 8px 0 18px; }
    .dgre-symbol { display: grid; place-items: center; width: 46px; height: 46px; flex-shrink: 0;
        border-radius: 15px; color: white; background: linear-gradient(145deg, #087f8c, #124960);
        font-size: 24px; box-shadow: 0 5px 14px #12566b20; }
    .dgre-brand strong { display: block; font-size: 21px; color: var(--deep); }
    .dgre-brand small { color: #526e7c; font-size: 12px; }
    .dgre-status { padding: 10px 12px; border-radius: 10px; background: #dceee8;
        color: #266553; font-size: 13px; margin-bottom: 16px; }
    .dgre-status.pending { background: #fff0da; color: #875e25; }
    .water-hero { position: relative; overflow: hidden; padding: 34px 38px; border-radius: 26px;
        background: linear-gradient(120deg, #113f53 0%, #096d7c 68%, #0d8b91 100%);
        box-shadow: 0 14px 36px #194c6015; margin-bottom: 24px; color: white; }
    .water-hero::after { content: ''; position: absolute; width: 360px; height: 360px;
        border: 1px solid #ffffff20; border-radius: 50%; right: -130px; top: -120px;
        box-shadow: 0 0 0 38px #ffffff05, 0 0 0 78px #ffffff04; pointer-events: none; }
    .water-eyebrow { font-size: 12px; font-weight: 650; text-transform: uppercase; letter-spacing: .13em;
        color: #a9e8e8; margin-bottom: 14px; position: relative; z-index: 1; }
    .water-hero h1 { color: white; font-size: clamp(28px, 4vw, 40px); font-weight: 700;
        line-height: 1.15; padding: 0; margin: 0 0 14px; position: relative; z-index: 1; }
    .water-hero p { color: #d1e9ee; max-width: 640px; font-size: 16px; line-height: 1.65; margin: 0; }
    .water-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
    .water-tags span { font-size: 12px; color: #e8f8fa; border: 1px solid #ffffff30;
        background: #ffffff0a; border-radius: 100px; padding: 6px 12px; }
    .section-kicker { color: #587582; font-size: 12px; letter-spacing: .09em;
        text-transform: uppercase; font-weight: 650; margin: 8px 0 12px; }
    .stButton button, .stDownloadButton button { border: 1px solid #d4e3e8; border-radius: 13px;
        color: var(--deep); background: #ffffff; transition: border-color .15s, box-shadow .15s; }
    .stButton button:hover, .stDownloadButton button:hover { border-color: #087f8c;
        color: #087f8c; box-shadow: 0 4px 12px #0d657310; }
    .stButton button:focus-visible, .stDownloadButton button:focus-visible { outline: 3px solid #65c6ce; outline-offset: 3px; }
    [data-testid="stChatMessage"] { border: 1px solid #dce8ec; background: #ffffff;
        border-radius: 20px; padding: 1.4rem; margin-bottom: 1rem; box-shadow: 0 4px 16px #153f5205; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: #e7f3f5; border-color: #d0e6e9; }
    [data-testid="stChatMessageAvatarAssistant"] { background: #087f8c; color: white; }
    [data-testid="stChatInput"] { border-radius: 18px; border: 1px solid #a9cdd4;
        box-shadow: 0 6px 24px #164f6010; }
    [data-testid="stBottom"] > div { background: #f5f9fa; }
    [data-testid="stExpander"] { border-radius: 13px; border-color: #d6e5e9; background: #ffffff80; }
    @media (max-width: 640px) {
        .block-container { padding-top: 1rem; }
        .water-hero { padding: 26px 22px; border-radius: 20px; }
        .water-hero p { font-size: 14px; }
        [data-testid="stChatMessage"] { padding: 1rem; }
    }
    @media (prefers-reduced-motion: reduce) { .stButton button, .stDownloadButton button { transition: none; } }
    </style>''', unsafe_allow_html=True)


def assistant_header():
    st.markdown('''<section class="water-hero" aria-label="Assistant DGRE">
        <div class="water-eyebrow">✦ Assistant IA · Ressources en eau</div>
        <h1>Vos données prennent la parole.</h1>
        <p>Explorez les pluies, les débits et les barrages en posant simplement une question.
        Votre assistant retrouve les informations, compare les valeurs et vous montre les sources.</p>
        <div class="water-tags"><span>Hydrologie</span><span>Pluviométrie</span>
        <span>Annuaires 2022–2023</span><span>Sources consultables</span></div>
    </section>''', unsafe_allow_html=True)


def sources_header():
    st.markdown('''<section class="water-hero" aria-label="Sources originales">
        <div class="water-eyebrow">▤ Bibliothèque documentaire · DGRE</div>
        <h1>À la source de chaque réponse.</h1>
        <p>Consultez les annuaires originaux et retrouvez les pages qui justifient les réponses de votre assistant.</p>
        <div class="water-tags"><span>Documents originaux</span><span>Preuves PDF</span></div>
    </section>''', unsafe_allow_html=True)
