# main.py Patch für SCHULE.EDITION

Diese Änderungen an `/opt/shiksha/main.py` einfügen, um die SCHULE.EDITION zu aktivieren.

## Schritt 1 — Imports am Anfang von main.py

```python
# SCHULE EDITION
from schule_orchestrator import orchestrate as schule_orchestrate_func
from schule_orchestrator import orchestrate_summary as schule_orchestrate_summary_func
from schule_models import (
    OrchestrateRequest as SchuleOrchestrateRequest,
    OrchestrateResponse as SchuleOrchestrateResponse,
    CourseCreateRequest,
    EnrollmentCreateRequest,
    WeatherDecisionRequest,
    SCHULE_EDITION_PROFILE,
)
```

## Schritt 2 — Router hinzufügen (vor `if __name__ == "__main__"`)

```python
from fastapi import APIRouter, HTTPException
from typing import Optional

schule_router = APIRouter(prefix="/schule", tags=["schule"])


@schule_router.get("/profile")
async def schule_profile():
    """Edition-Profil ausliefern (für UI-Boot)."""
    return SCHULE_EDITION_PROFILE


@schule_router.post("/orchestrate", response_model=SchuleOrchestrateResponse)
async def schule_orchestrate(request: SchuleOrchestrateRequest):
    """Vollständige Orchestrierung mit Patterns + Focus."""
    # Lade Signale aus DB (Implementierung folgt im next build)
    signals = await load_schule_signals(request.school_id)
    return schule_orchestrate_func(request, signals)


@schule_router.post("/orchestrate/summary")
async def schule_orchestrate_summary(school_id: str):
    """Kompakte Sprache, ein Satz."""
    signals = await load_schule_signals(school_id)
    return schule_orchestrate_summary_func(school_id, signals)


@schule_router.get("/state")
async def schule_state(school_id: str):
    """Aktueller SchoolState — analog ClubState aus CLUB.EDITION."""
    signals = await load_schule_signals(school_id)
    request = SchuleOrchestrateRequest(school_id=school_id, focus="overview")
    return schule_orchestrate_func(request, signals).school_state


@schule_router.post("/courses")
async def schule_create_course(request: CourseCreateRequest):
    """Kurs anlegen."""
    # TODO: in DB einfügen
    raise HTTPException(status_code=501, detail="Not implemented yet — siehe BUILD_PACK V1")


@schule_router.post("/enrollments")
async def schule_create_enrollment(request: EnrollmentCreateRequest):
    """Anmeldung anlegen — mit Consent-Check für Minderjährige."""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@schule_router.post("/weather/decide")
async def schule_weather_decide(request: WeatherDecisionRequest):
    """Operator-Entscheidung zu Wetter-Window speichern."""
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Helper (Stub)
async def load_schule_signals(school_id: str):
    """Lade SchuleSignals aus DB. Stub — vorerst leer."""
    # TODO: SELECT * FROM schule_signals WHERE school_id=$1 AND status='open'
    return []


app.include_router(schule_router)
```

## Schritt 3 — Optional: Test-Daten beim Boot laden

Für die Pilot-Phase mit fiktiven Schulen — Fixture-Loader (idempotent):

```python
@app.on_event("startup")
async def schule_load_fixtures():
    import os, json
    fixture_dir = "/opt/shiksha/fixtures/schule_edition"
    if os.path.exists(fixture_dir):
        for filename in ["yogaschule_wien.json", "surfschule_sylt.json"]:
            path = os.path.join(fixture_dir, filename)
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                    # TODO: in DB importieren (UPSERT)
                    print(f"[SCHULE] Fixture geladen: {filename}")
```

## Schritt 4 — Verifikation nach Deploy

```bash
# Service neu starten
systemctl restart shiksha
systemctl status shiksha

# Edition-Profil abrufen
curl http://shiksha.tun.zone/schule/profile

# Sollte JSON mit edition: schule.shiksha zurückgeben
```

## Schritt 5 — Swagger-Dokumentation

Nach Restart ist die Dokumentation verfügbar unter:
```
http://shiksha.tun.zone/docs
```

Suche nach `schule` Tag — alle neuen Endpoints sind dort dokumentiert.
