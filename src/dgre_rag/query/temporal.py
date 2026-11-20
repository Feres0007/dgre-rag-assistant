"""Deterministic temporal policy shared by conversational and numerical routes."""
import calendar
import json
import re
from datetime import date

from dgre_rag.config import settings
from dgre_rag.domain.models import Period
from dgre_rag.ingestion.pipeline import plain
from dgre_rag.storage.database import release_path

MONTHS = ('janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre').split()


def default_period(release_id):
    if not release_id:
        return None
    manifest = json.loads((release_path(release_id) / 'manifest.json').read_text(encoding='utf-8'))
    value = manifest.get('default_period') or settings().release_periods.get(release_id)
    return Period.model_validate(value) if value else None


def resolve_period(question, release_id, context=None):
    from dgre_rag.query.planner import detect_period
    context = context or {}
    q = plain(question)
    # These requests have a distinct temporal meaning, or no temporal meaning.
    if any(w in q for w in ('historique', 'depuis', 'derniere', 'precedente', 'crue maximale observee', 'date de la crue maximale', 'definition', 'signifie', 'signification', 'comment', 'convention', 'qu’est-ce', "qu'est-ce")):
        return None
    if re.search(r'\bqu[’\']en\s+\d{4}',q) and any(w in q for w in ('plus','moins')):
        return None  # Relative comparison, not a single-period lookup.
    if re.search(r'\bcompar\w*\b',q) and re.search(r'\b(deux periodes|autre periode)\b',q) and len(re.findall(r'\b\d{4}[-–/]\d{4}\b',q))<2:
        return {'clarification':'Quelles sont les deux périodes à comparer ?'}
    if re.search(r'\b(demain|aujourd.hui|hier)\b', q):
        return None
    periods = re.findall(r'\b\d{4}[-–/]\d{4}\b', q)
    if len(periods) > 1:
        return None  # Each operand is resolved by the comparison route.
    span = detect_period(question)
    origin = 'question'
    if span is None:
        # A bare year is explicit, not permission to substitute the corpus year.
        year = re.search(r'\b(?:en|annee)\s+(\d{4})\b', q)
        if year:
            y = int(year[1]); span = Period(start=date(y, 1, 1), end=date(y, 12, 31))
        elif re.search(r'\b\d{4}\b', q):
            return {'clarification': 'Précisez les dates de la période demandée.'}
    if span is None and context.get('period'):
        span = Period.model_validate(context['period']); origin = 'context'
        existing = context.get('temporal_resolution')
        if existing and existing.get('period') == span.model_dump(mode='json'):
            origin = existing['origin']
    if span is None:
        if 'lame' not in q and any(w in q for w in ('tarage', 'interpol', 'hauteur tabulee')):
            return None
        if not (any(w in q for w in ('pluie', 'pluvio', 'precipitation', 'debit', 'annuel', 'cumul', 'volume', 'apport', 'lame', 'jaugeage', 'residu sec', 'salinite', 'seuil', 'consecut')) or re.search(r'\d\s*(?:mm|m3/s|m³/s|l/s)\b',q)):
            return None
        span = default_period(release_id); origin = 'default_campaign'
    if span is None:
        return None
    # Resolve an unqualified month/day inside the selected campaign, never today.
    month = re.search(r'\b(?:(\d{1,2})(?:er)?\s+)?(' + '|'.join(MONTHS) + r')\b(?!\s+\d{4})', q)
    if len(set(re.findall(r'\b('+'|'.join(MONTHS)+r')\b',q)))>1:
        month=None  # Multi-month comparisons retain their common campaign.
    if month and not detect_period(question):
        m = MONTHS.index(month[2]) + 1
        candidates = [y for y in range(span.start.year, span.end.year + 1)
                      if date(y, m, calendar.monthrange(y, m)[1]) >= span.start and date(y, m, 1) <= span.end]
        if len(candidates) != 1:
            return {'clarification': 'Précisez l’année du mois demandé.'}
        y = candidates[0]
        start = date(y, m, int(month[1]) if month[1] else 1)
        end = start if month[1] else date(y, m, calendar.monthrange(y, m)[1])
        span = Period(start=start, end=end); origin = 'question_in_campaign'
    return {'period': span.model_dump(mode='json'), 'origin': origin}


def resolved_context(question, release_id, context=None):
    result = dict(context or {})
    result.setdefault('_period_supplied', bool(result.get('period')))
    resolution = resolve_period(question, release_id, result)
    if resolution and resolution.get('period'):
        result.update(period=resolution['period'], temporal_resolution=resolution)
    return result, resolution
