FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DGRE_ROOT=/app

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 dgre

COPY requirements.lock.txt ./
RUN python -m pip install -r requirements.lock.txt
COPY pyproject.toml ./
COPY src/ ./src/
RUN python -m pip install --no-deps .
COPY app/ ./app/
COPY config/ ./config/
COPY .streamlit/ ./.streamlit/
COPY RAG_DGRE_Plan_Complet/plan_implementation/configuration/corpus_expected.json ./RAG_DGRE_Plan_Complet/plan_implementation/configuration/corpus_expected.json
RUN mkdir -p data donnees_brutes && chown -R dgre:dgre /app

USER dgre
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"
CMD ["python", "-m", "streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.fileWatcherType=none"]
