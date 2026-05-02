# ============================================================
# SHIKSHA — main.py
# FastAPI Server — erster operativer Endpunkt
# POST /orchestrate → KURS_001 Flow
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from models import OrchestratorRequest, OrchestratorObject
from orchestrator import process_request

app = FastAPI(
    title="SHIKSHA API",
    description="SHIKSHA Orchestrator — V1 Server Sketch",
    version="1.0.0",
)


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "system": "SHIKSHA", "version": "1.0.0"}


# ------------------------------------------------------------
# HAUPT-ENDPUNKT
# POST /orchestrate
# Nimmt einen Request entgegen, gibt ein vollständiges
# Orchestrator-Objekt zurück.
# ------------------------------------------------------------

@app.post("/orchestrate", response_model=OrchestratorObject)
async def orchestrate(req: OrchestratorRequest) -> OrchestratorObject:
    """
    Verarbeitet eine Anfrage durch den SHIKSHA Orchestrator.

    Beispiel-Request für KURS_001:
    {
        "raw_input": "Kannst du den Segelkurs morgen verschieben? Es soll Sturm geben.",
        "edition": "camp.shiksha",
        "user_role": "operator",
        "source_type": "operator",
        "source_id": "op_camp_03",
        "session_id": "sess_operator_camp_20260417_007",
        "active_entity_ids": ["course_sail_042", "booking_221", "loc_lake_02"]
    }
    """
    try:
        result = await process_request(req)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orchestrate/summary")
async def orchestrate_summary(req: OrchestratorRequest) -> dict:
    """
    Wie /orchestrate, aber gibt nur das Wesentliche zurück:
    output_mode, summary, next_steps, review_required.
    """
    try:
        result = await process_request(req)
        return {
            "request_id":      result.request_id,
            "edition":         result.edition,
            "output_mode":     result.output.mode,
            "summary":         result.output.summary,
            "proposal":        result.output.proposal.model_dump() if result.output.proposal else None,
            "next_steps":      [s.model_dump() for s in result.output.next_steps],
            "review_required": result.review_required.model_dump() if result.review_required else None,
            "policy_warnings": [w.model_dump() for w in result.policy_check.warnings],
            "weather":         result.domain_selection.supporting_domain_results[0].result
                               if result.domain_selection.supporting_domain_results else None,
            "learning_candidate": (
                result.learning.learning_candidate.model_dump()
                if result.learning.learning_candidate else None
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
