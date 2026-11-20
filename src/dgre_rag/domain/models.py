from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Period(Strict):
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self):
        if self.start > self.end:
            raise ValueError("INVALID_PERIOD")
        return self


class SourceRef(Strict):
    source_id: str
    document_id: str
    page_pdf: int = Field(ge=1)
    page_printed: str | None = None
    bbox: tuple[float, float, float, float]
    raw_text: str
    block_type: str

    @field_validator("bbox")
    @classmethod
    def rectangle(cls, value):
        from math import isfinite
        x0, y0, x1, y1 = value
        if not all(map(isfinite, value)) or min(x0,y0) < 0 or x1 <= x0 or y1 <= y0:
            raise ValueError("INVALID_BBOX")
        return value


class CellCandidate(Strict):
    cell_id: str
    source_id: str
    row_index: int = Field(ge=0)
    col_index: int = Field(ge=0)
    headers: list[str]
    raw_value: str
    value: str | None = None
    symbol_status: str


class EntityResolution(Strict):
    query: str
    candidates: list[str] = Field(default_factory=list)
    entity_id: str | None = None
    status: Literal["exact", "alias", "ambiguous", "not_found"]


class Observation(Strict):
    observation_id: str
    entity_id: str
    metric_id: str
    period: Period
    value: str
    unit: str
    source_ids: list[str] = Field(min_length=1)
    origin: Literal["published", "calculated"] = "published"

    @field_validator("value")
    @classmethod
    def finite(cls, value):
        if not Decimal(value).is_finite():
            raise ValueError("NON_FINITE_VALUE")
        return value


class Coverage(Strict):
    expected: int = Field(ge=0)
    available: int = Field(ge=0)
    valid: int = Field(ge=0)
    unresolved: int = Field(ge=0)

    @model_validator(mode="after")
    def counts(self):
        if self.valid > self.available or self.available > self.expected:
            raise ValueError("INVALID_COVERAGE")
        return self


class SearchFilters(Strict):
    document_id: str | None = None
    entity_id: str | None = None
    basin: str | None = None
    period: Period | None = None
    content_type: Literal['page', 'passage', 'table', 'figure'] | None = None


class CalculationOptions(Strict):
    threshold: Decimal | None = None
    threshold_unit: str | None = None
    comparator: Literal['gt', 'ge', 'lt', 'le', 'eq'] = 'ge'
    group_by: Literal['month', 'season', 'campaign'] | None = None
    descending: bool = True
    target_unit: str | None = None
    allow_partial: bool = True

    @field_validator('threshold')
    @classmethod
    def finite_threshold(cls, value):
        if value is not None and not value.is_finite():
            raise ValueError('NON_FINITE_VALUE')
        return value


class Operation(Strict):
    op: Literal["lookup", "aggregate", "compare", "calculate", "retrieve_text", "get_figure"]
    entity_id: str | None = None
    metric_id: str | None = None
    period: Period | None = None
    other_entity_id: str | None = None
    other_period: Period | None = None
    formula_id: Literal["difference", "ratio_to_baseline", "relative_anomaly", "positive_deficit", "rainfall_sum", "time_weighted_mean", "daily_discharge_volume", "maximum", "minimum", "mean", "count", "threshold_count", "longest_run", "filter", "rank", "convert"] | None = None
    mode: Literal["published", "calculated"] = "published"
    step_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    options: CalculationOptions = Field(default_factory=CalculationOptions)
    evidence_required: bool = True

    @model_validator(mode="after")
    def required(self):
        catalog_selection=self.formula_id in ('rank','filter','count')
        if self.op not in ("retrieve_text", "get_figure") and not (self.metric_id and self.period and (self.entity_id or catalog_selection)):
            raise ValueError("Entité, indicateur et période obligatoires")
        if self.op == "compare" and not all((self.other_entity_id, self.other_period)):
            raise ValueError("Deux opérandes obligatoires")
        if self.op in ("aggregate", "calculate") and not self.formula_id:
            raise ValueError("Formule obligatoire")
        if self.op in ('retrieve_text','get_figure') and any((self.entity_id,self.metric_id,self.other_entity_id,self.formula_id)):
            raise ValueError('Opération documentaire sans opérandes numériques')
        if self.op=='lookup' and (self.formula_id or self.mode!='published'):
            raise ValueError('Une lecture publiée ne remplace pas un calcul')
        if self.op not in ('retrieve_text','get_figure') and self.filters.model_dump(exclude_none=True):
            raise ValueError('UNSUPPORTED_NUMERIC_FILTER: utiliser les opérandes structurés explicites')
        if self.formula_id in ('threshold_count','longest_run','filter') and self.options.threshold is None:
            raise ValueError('THRESHOLD_REQUIRED')
        if self.formula_id=='convert' and not self.options.target_unit:
            raise ValueError('TARGET_UNIT_REQUIRED')
        if not self.evidence_required:
            raise ValueError('EVIDENCE_REQUIRED')
        return self


class QueryPlan(Strict):
    temporal_resolution: dict = Field(default_factory=dict)
    operations: list[Operation] = Field(default_factory=list, max_length=6)
    clarification: str | None = None
    out_of_scope: bool = False
    intent: Literal['documentary','data','calculation','mixed'] | None = None

    @model_validator(mode='after')
    def one_route(self):
        if sum([bool(self.operations),bool(self.clarification),self.out_of_scope])!=1:
            raise ValueError('Le plan doit choisir exécution, clarification ou hors périmètre')
        seen=set()
        for index, operation in enumerate(self.operations):
            key=operation.step_id or f'step-{index+1}'
            if key in seen or not set(operation.depends_on)<=seen:
                raise ValueError('INVALID_DEPENDENCIES')
            seen.add(key)
        return self


class ValidatedPlan(Strict):
    plan: QueryPlan
    release_id: str


class EvidenceBundle(Strict):
    observations: list[dict] = Field(default_factory=list)
    passages: list[dict] = Field(default_factory=list)
    calculations: list[dict] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)


class Answer(Strict):
    temporal_resolution: dict = Field(default_factory=dict)
    status: Literal["answered", "partial", "ambiguous", "not_found", "out_of_scope", "unvalidated_data", "source_conflict", "technical_error"]
    text: str
    facts: list[dict] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    calculations: list[dict] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    release_id: str | None = None
    run_id: str
    question: str
    table: list[dict] = Field(default_factory=list)
    presentation: Literal['text', 'table', 'chart', 'export', 'sources'] = 'text'
    conversation: dict = Field(default_factory=dict)
    claims: list[dict] = Field(default_factory=list)
    coverage: list[dict] = Field(default_factory=list)
    validation: dict = Field(default_factory=dict)
    plan: dict = Field(default_factory=dict)


def number(raw: str) -> tuple[str | None, str]:
    value = raw.strip().replace("\u00a0", "").replace(" ", "")
    if not value:
        return None, "missing"
    if value == ".":
        return None, "dry_symbol_requires_legend"
    if value in ("-", "–", "—"):
        return None, "ambiguous_symbol"
    if value in ("-999", "9999", "PE", "sec", "STAGNANT"):
        return None, "special_code"
    try:
        dec = Decimal(value.replace(",", "."))
        if dec.is_finite() and dec >= 0:
            return format(dec, "f"), "numeric"
    except InvalidOperation:
        pass
    return None, "unparsed"
