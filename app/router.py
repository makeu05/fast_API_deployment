from fastapi import APIRouter, HTTPException, status
from app.models import MethodologyRequest, MethodologyResponse, HealthResponse
from app.service import run_methodology_pipeline

router = APIRouter(prefix="/api/v1", tags=["Module G – Méthodologie"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", module="G", version="1.0.0")


@router.post(
    "/methodology/generate",
    response_model=MethodologyResponse,
    status_code=status.HTTP_200_OK,
    summary="Génère hypothèses et plan méthodologique forensique",
    description=(
        "À partir des incohérences détectées (Module F) et du type de cas, "
        "ce endpoint génère : (1) une liste d'hypothèses classées par confiance, "
        "(2) un plan d'actions forensiques ordonné avec outils et durées estimées."
    ),
)
def generate_methodology(payload: MethodologyRequest):
    """
    Corps attendu :
    {
      "case_id": "uuid",
      "case_type": "fraude_bancaire | intrusion_reseau | malware | phishing | ...",
      "incoherences": [
        {"type": "temporelle", "description": "...", "severity": "haute"},
        ...
      ]
    }
    """
    try:
        result = run_methodology_pipeline(
            case_id=payload.case_id,
            case_type=payload.case_type,
            incoherences=payload.incoherences,
        )
        return MethodologyResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Base de connaissances introuvable : {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération : {exc}",
        )
