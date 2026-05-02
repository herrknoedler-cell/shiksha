# main.py Patch für CAMPING.EDITION

## Schritt 1 — Imports

```python
# CAMPING EDITION
from camping_orchestrator import (
    orchestrate as camping_orchestrate_func,
    orchestrate_summary as camping_orchestrate_summary_func,
)
from camping_models import (
    CampingOrchestrateRequest,
    CampingOrchestrateResponse,
    ReservationCreateRequest,
    CheckInRequest,
    UtilityReadingCreateRequest,
    CAMPING_EDITION_PROFILE,
)
```

## Schritt 2 — Router

```python
camping_router = APIRouter(prefix="/camping", tags=["camping"])


@camping_router.get("/profile")
async def camping_profile():
    return CAMPING_EDITION_PROFILE


@camping_router.post("/orchestrate", response_model=CampingOrchestrateResponse)
async def camping_orchestrate(request: CampingOrchestrateRequest):
    signals = await load_camping_signals(request.campsite_id)
    running_stays = await count_running_stays(request.campsite_id)
    total_pitches = await count_pitches(request.campsite_id)
    return camping_orchestrate_func(request, signals, running_stays, total_pitches)


@camping_router.post("/orchestrate/summary")
async def camping_orchestrate_summary(campsite_id: str):
    signals = await load_camping_signals(campsite_id)
    return camping_orchestrate_summary_func(campsite_id, signals)


@camping_router.get("/state")
async def camping_state(campsite_id: str):
    signals = await load_camping_signals(campsite_id)
    running_stays = await count_running_stays(campsite_id)
    total_pitches = await count_pitches(campsite_id)
    request = CampingOrchestrateRequest(campsite_id=campsite_id, focus="overview")
    return camping_orchestrate_func(request, signals, running_stays, total_pitches).camp_state


@camping_router.post("/reservations")
async def camping_create_reservation(req: ReservationCreateRequest):
    raise HTTPException(status_code=501, detail="Not implemented yet — siehe BUILD_PACK V1")


@camping_router.post("/check-in")
async def camping_check_in(req: CheckInRequest):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@camping_router.post("/utility/readings")
async def camping_utility_reading(req: UtilityReadingCreateRequest):
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Helpers (Stubs)
async def load_camping_signals(campsite_id: str):
    return []

async def count_running_stays(campsite_id: str) -> int:
    return 0

async def count_pitches(campsite_id: str) -> int:
    return 0


app.include_router(camping_router)
```

## Schritt 3 — Verifikation

```bash
systemctl restart shiksha
curl http://shiksha.tun.zone/camping/profile
```

## Schritt 4 — Cross-Edition Safeguarding

Wenn das `safeguarding`-Modul mitgedeployt ist, hat der camping-Orchestrator schon die Logik (`adjust_safeguarding_severity`) um Severity zu erhöhen. Die Integration läuft auf Signal-Ebene — keine Code-Änderung in main.py nötig, solange der Safeguarding-Orchestrator seine Signale via `camping_signals`-Tabelle persistiert.
