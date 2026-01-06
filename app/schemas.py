from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Any

AllowedToolName = Literal[
    "resolve_period",
    "compute_kpis",
    "funnel_breakdown",
    "segment_impact",
    "sanity_check_data",
]

class PeriodSpec(BaseModel):
    label: str = Field(..., description="Human label, e.g. 'current' or 'previous'")
    start_date: str
    end_date: str

class ExecutionStep(BaseModel):
    tool_name: AllowedToolName
    args: dict[str, Any] = Field(default_factory=dict)

class Hypothesis(BaseModel):
    id: str
    title: str
    metric: str
    status: Literal["untested", "supported", "rejected", "inconclusive"] = "untested"

class Plan(BaseModel):
    question: str
    periods: list[PeriodSpec]
    hypotheses: list[Hypothesis]
    segments: list[str] = Field(default_factory=list, description="segment columns, e.g. device/channel/country")
    execution_steps: list[ExecutionStep]

class Evidence(BaseModel):
    kpis: dict[str, Any] = Field(default_factory=dict)
    funnel: dict[str, Any] = Field(default_factory=dict)
    segments: dict[str, Any] = Field(default_factory=dict)
    sanity: dict[str, Any] = Field(default_factory=dict)

class HypothesisVerdict(BaseModel):
    hypothesis_id: str
    status: Literal["supported", "rejected", "inconclusive"]
    reason: str

class FinalResult(BaseModel):
    plan: Plan
    evidence: Evidence
    verdicts: list[HypothesisVerdict]
    next_checks: list[str]