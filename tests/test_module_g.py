import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.service import (
    generate_hypotheses,
    generate_methodology_plan,
    load_knowledge_base,
    run_methodology_pipeline,
)
from app.models import Incoherence, Hypothesis

client = TestClient(app)
kb = load_knowledge_base()


# ─────────────────────────────────────────────────────────────────────────────
# Tests service.py
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateHypotheses:

    def test_fraude_bancaire_sans_incoherences(self):
        """Un cas fraude bancaire doit toujours produire des hypothèses."""
        hyps = generate_hypotheses([], "fraude_bancaire", kb)
        assert len(hyps) > 0
        ids = [h.id for h in hyps]
        assert "fraude_bancaire" in ids

    def test_incoherence_temporelle_ajoute_manipulation_timeline(self):
        incs = [Incoherence(type="temporelle", description="Date contradictoire", severity="haute")]
        hyps = generate_hypotheses(incs, "generic", kb)
        ids = [h.id for h in hyps]
        assert "manipulation_timeline" in ids

    def test_incoherence_haute_severity_augmente_confidence(self):
        inc_haute = [Incoherence(type="temporelle", description="...", severity="haute")]
        inc_faible = [Incoherence(type="temporelle", description="...", severity="faible")]
        hyps_haute = generate_hypotheses(inc_haute, "generic", kb)
        hyps_faible = generate_hypotheses(inc_faible, "generic", kb)
        conf_haute = next((h.confidence for h in hyps_haute if h.id == "manipulation_timeline"), 0)
        conf_faible = next((h.confidence for h in hyps_faible if h.id == "manipulation_timeline"), 0)
        assert conf_haute > conf_faible

    def test_hypotheses_triees_par_confidence_decroissante(self):
        incs = [
            Incoherence(type="temporelle", description="...", severity="haute"),
            Incoherence(type="factuelle", description="...", severity="haute"),
        ]
        hyps = generate_hypotheses(incs, "intrusion_reseau", kb)
        confidences = [h.confidence for h in hyps]
        assert confidences == sorted(confidences, reverse=True)

    def test_confidence_entre_0_et_1(self):
        incs = [Incoherence(type="temporelle", description="...", severity="haute")] * 10
        hyps = generate_hypotheses(incs, "fraude_bancaire", kb)
        for h in hyps:
            assert 0.0 <= h.confidence <= 1.0

    def test_cas_type_inconnu_utilise_generic(self):
        hyps = generate_hypotheses([], "cas_inconnu_xyz", kb)
        assert len(hyps) > 0


class TestGeneratePlan:

    def test_plan_non_vide_si_hypotheses(self):
        hyps = generate_hypotheses([], "intrusion_reseau", kb)
        plan, duree = generate_methodology_plan(hyps, kb)
        assert len(plan) > 0

    def test_chaque_action_a_au_moins_deux_outils(self):
        hyps = generate_hypotheses([], "malware", kb)
        plan, _ = generate_methodology_plan(hyps, kb)
        for action in plan:
            assert len(action.outils) >= 2, (
                f"L'action '{action.action}' n'a que {len(action.outils)} outil(s)"
            )

    def test_pas_de_doublons_dans_le_plan(self):
        hyps = generate_hypotheses([], "fraude_bancaire", kb)
        plan, _ = generate_methodology_plan(hyps, kb)
        actions = [a.action for a in plan]
        assert len(actions) == len(set(actions)), "Doublon détecté dans le plan"

    def test_priorites_incrementales(self):
        hyps = generate_hypotheses([], "intrusion_reseau", kb)
        plan, _ = generate_methodology_plan(hyps, kb)
        for i, action in enumerate(plan):
            assert action.priorite == i + 1

    def test_duree_totale_format(self):
        hyps = generate_hypotheses([], "fraude_bancaire", kb)
        _, duree = generate_methodology_plan(hyps, kb)
        assert "h" in duree, f"Format durée inattendu : {duree}"

    def test_hypothese_source_presente(self):
        hyps = generate_hypotheses([], "fraude_bancaire", kb)
        plan, _ = generate_methodology_plan(hyps, kb)
        for action in plan:
            assert action.hypothese_source != ""


class TestPipeline:

    def test_pipeline_complet_intrusion_reseau(self):
        incs = [
            Incoherence(type="temporelle", description="Incohérence horaire", severity="haute"),
            Incoherence(type="geographique", description="Lieu impossible", severity="moyenne"),
        ]
        result = run_methodology_pipeline("test-case-001", "intrusion_reseau", incs)
        assert result["case_id"] == "test-case-001"
        assert len(result["hypotheses"]) > 0
        assert len(result["plan"]) > 0
        assert "generated_at" in result

    def test_pipeline_fraude_bancaire(self):
        result = run_methodology_pipeline("test-case-002", "fraude_bancaire", [])
        assert len(result["plan"]) >= 2

    def test_pipeline_malware(self):
        incs = [Incoherence(type="factuelle", description="Contradiction déclarations", severity="haute")]
        result = run_methodology_pipeline("test-case-003", "malware", incs)
        plan_actions = [a["action"] for a in result["plan"]]
        assert any("malware" in a for a in plan_actions)

    def test_pipeline_cas_generique_sans_incoherences(self):
        result = run_methodology_pipeline("test-case-004", "generic", [])
        assert len(result["hypotheses"]) > 0
        assert len(result["plan"]) > 0

    def test_pipeline_phishing(self):
        result = run_methodology_pipeline("test-case-005", "phishing", [])
        plan_actions = [a["action"] for a in result["plan"]]
        assert any("email" in a or "reseau" in a or "log" in a for a in plan_actions)


# ─────────────────────────────────────────────────────────────────────────────
# Tests API (FastAPI TestClient)
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIHealth:

    def test_health_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["module"] == "G"


class TestAPIMethodology:

    PAYLOAD_INTRUSION = {
        "case_id": "550e8400-e29b-41d4-a716-446655440000",
        "case_type": "intrusion_reseau",
        "incoherences": [
            {"type": "temporelle", "description": "Date incohérente entre PV", "severity": "haute"},
            {"type": "geographique", "description": "Lieu impossible", "severity": "moyenne"},
        ],
    }

    def test_status_200(self):
        resp = client.post("/api/v1/methodology/generate", json=self.PAYLOAD_INTRUSION)
        assert resp.status_code == 200

    def test_response_contient_case_id(self):
        resp = client.post("/api/v1/methodology/generate", json=self.PAYLOAD_INTRUSION)
        assert resp.json()["case_id"] == self.PAYLOAD_INTRUSION["case_id"]

    def test_response_contient_hypotheses(self):
        resp = client.post("/api/v1/methodology/generate", json=self.PAYLOAD_INTRUSION)
        data = resp.json()
        assert "hypotheses" in data
        assert len(data["hypotheses"]) > 0

    def test_response_contient_plan(self):
        resp = client.post("/api/v1/methodology/generate", json=self.PAYLOAD_INTRUSION)
        data = resp.json()
        assert "plan" in data
        assert len(data["plan"]) > 0

    def test_chaque_action_a_description_et_duree(self):
        resp = client.post("/api/v1/methodology/generate", json=self.PAYLOAD_INTRUSION)
        for action in resp.json()["plan"]:
            assert action["description"] != ""
            assert action["duree_estimee"] != ""

    def test_validation_case_id_manquant(self):
        resp = client.post(
            "/api/v1/methodology/generate",
            json={"case_type": "malware", "incoherences": []},
        )
        assert resp.status_code == 422

    def test_fraude_bancaire_sans_incoherences(self):
        resp = client.post(
            "/api/v1/methodology/generate",
            json={"case_id": "abc-123", "case_type": "fraude_bancaire", "incoherences": []},
        )
        assert resp.status_code == 200
        assert len(resp.json()["plan"]) > 0

    def test_generated_at_present(self):
        resp = client.post("/api/v1/methodology/generate", json=self.PAYLOAD_INTRUSION)
        assert "generated_at" in resp.json()
        assert resp.json()["generated_at"].endswith("Z")
