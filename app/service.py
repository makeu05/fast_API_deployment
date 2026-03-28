import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from app.models import Incoherence, Hypothesis, ForensicAction


KB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base.json"


def load_knowledge_base() -> dict:
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Hypothèse generation ─────────────────────────────────────────────────────

INCOHERENCE_TO_HYPOTHESIS = {
    "temporelle": ["manipulation_timeline"],
    "geographique": ["intrusion_systeme", "acces_interne_frauduleux"],
    "factuelle": ["acces_interne_frauduleux", "vol_donnees"],
}


def generate_hypotheses(
    incoherences: List[Incoherence],
    case_type: str,
    kb: dict,
) -> List[Hypothesis]:
    """
    Génère les hypothèses d'investigation à partir des incohérences détectées
    et du type de cas. Combine règles métier + base de connaissances.
    """
    hypothesis_scores: Dict[str, float] = {}

    # 1. Hypothèses issues des incohérences
    for inc in incoherences:
        inc_type = inc.type.lower()
        mapped = INCOHERENCE_TO_HYPOTHESIS.get(inc_type, [])
        weight = {"haute": 0.4, "moyenne": 0.25, "faible": 0.1}.get(
            (inc.severity or "moyenne").lower(), 0.25
        )
        for hyp_id in mapped:
            hypothesis_scores[hyp_id] = hypothesis_scores.get(hyp_id, 0) + weight

    # 2. Hypothèses issues du type de cas
    case_hyps = kb["case_type_to_hypotheses"].get(
        case_type.lower(), kb["case_type_to_hypotheses"]["generic"]
    )
    for hyp_id in case_hyps:
        hypothesis_scores[hyp_id] = hypothesis_scores.get(hyp_id, 0) + 0.3

    # 3. Normaliser et filtrer (garder celles avec score > 0)
    result: List[Hypothesis] = []
    for hyp_id, score in sorted(hypothesis_scores.items(), key=lambda x: -x[1]):
        hyp_data = kb["hypothesis_mapping"].get(hyp_id)
        if not hyp_data:
            continue
        confidence = min(score, 1.0)
        result.append(
            Hypothesis(
                id=hyp_id,
                description=hyp_data["description"],
                indicateurs=hyp_data.get("indicateurs", []),
                confidence=round(confidence, 2),
            )
        )

    return result


# ── Plan méthodologique ───────────────────────────────────────────────────────

def _parse_hours(duree: str) -> float:
    """Extrait la borne haute de la durée estimée (ex: '4-8h' → 8.0)."""
    numbers = re.findall(r"\d+", duree)
    if not numbers:
        return 4.0
    return float(numbers[-1])


def generate_methodology_plan(
    hypotheses: List[Hypothesis],
    kb: dict,
) -> Tuple[List[ForensicAction], str]:
    """
    Construit le plan d'actions forensiques ordonné :
    - Déduplication des outils communs à plusieurs hypothèses
    - Priorité basée sur la confidence de l'hypothèse source
    - Estimation de durée totale
    """
    seen_actions: set = set()
    actions: List[ForensicAction] = []
    priorite = 1
    total_hours_min = 0.0
    total_hours_max = 0.0

    for hyp in hypotheses:
        hyp_data = kb["hypothesis_mapping"].get(hyp.id, {})
        for tool_key in hyp_data.get("outils_associes", []):
            if tool_key in seen_actions:
                continue
            seen_actions.add(tool_key)

            tool_info = kb["forensic_tools"].get(tool_key, {})
            duree = tool_info.get("duree_estimee", "2-4h")

            # Durée totale
            nums = re.findall(r"\d+", duree)
            if len(nums) >= 2:
                total_hours_min += float(nums[0])
                total_hours_max += float(nums[1])
            elif nums:
                total_hours_min += float(nums[0])
                total_hours_max += float(nums[0])

            actions.append(
                ForensicAction(
                    action=tool_key,
                    outils=tool_info.get("outils", []),
                    description=tool_info.get("description", ""),
                    duree_estimee=duree,
                    priorite=priorite,
                    hypothese_source=hyp.id,
                )
            )
            priorite += 1

    duree_totale = f"{int(total_hours_min)}-{int(total_hours_max)}h"
    return actions, duree_totale


# ── Point d'entrée public ─────────────────────────────────────────────────────

def run_methodology_pipeline(
    case_id: str,
    case_type: str,
    incoherences: List[Incoherence],
) -> dict:
    """
    Pipeline complet : incohérences + type de cas → hypothèses + plan.
    Retourne un dict prêt à être sérialisé en MethodologyResponse.
    """
    from datetime import datetime, timezone

    kb = load_knowledge_base()
    hypotheses = generate_hypotheses(incoherences, case_type, kb)
    plan, duree_totale = generate_methodology_plan(hypotheses, kb)

    return {
        "case_id": case_id,
        "hypotheses": [h.model_dump() for h in hypotheses],
        "plan": [a.model_dump() for a in plan],
        "duree_totale_estimee": duree_totale,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
