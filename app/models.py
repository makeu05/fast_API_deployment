from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class Incoherence(BaseModel):
    type: str = Field(..., description="Type: temporelle, geographique, factuelle")
    description: str
    severity: Optional[str] = "moyenne"
    pv_references: Optional[List[str]] = []


class MethodologyRequest(BaseModel):
    case_id: str
    case_type: str
    incoherences: List[Incoherence] = []
    description: Optional[str] = ""


class ForensicAction(BaseModel):
    action: str
    outils: List[str]
    description: str
    duree_estimee: str
    priorite: int
    hypothese_source: str


class Hypothesis(BaseModel):
    id: str
    description: str
    indicateurs: List[str]
    confidence: float = Field(ge=0.0, le=1.0)


class MethodologyResponse(BaseModel):
    case_id: str
    hypotheses: List[Hypothesis]
    plan: List[ForensicAction]
    duree_totale_estimee: str
    generated_at: str


class HealthResponse(BaseModel):
    status: str
    module: str
    version: str
