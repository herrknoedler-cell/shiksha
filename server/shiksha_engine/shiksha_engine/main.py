"""SHIKSHA Engine — FastAPI Application Entry Point."""

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .settings import get_settings

logger = logging.getLogger("shiksha")


def create_app() -> FastAPI:
    """Application Factory."""
    settings = get_settings()

    app = FastAPI(
        title="SHIKSHA Engine",
        description=(
            "Backend-Proxy + Developer Portal. Edition-agnostisch.\n\n"
            "Auth: WebAuthn/Passkey via Presence-Switch. Tokens als Bearer-JWT.\n"
            "Rate-Limit: 200 Calls/Operator/Tag (Developer unlimited).\n"
        ),
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        openapi_tags=[
            {"name": "auth",     "description": "Authentifizierung — WebAuthn, JWT, Refresh"},
            {"name": "chat",     "description": "Chat-Endpoints — /respond (block) und /stream (SSE)"},
            {"name": "sessions", "description": "Sessions — Liste mit Filter, Detail mit Messages"},
            {"name": "memory",   "description": "Memory — CRUD über persistente Erinnerungen pro Operator"},
            {"name": "tools",    "description": "Tools — Function-Call-Endpoints (log_observation, log_friction, …)"},
            {"name": "heim",     "description": "Heim — Karten-Liste pro Operator-Rolle + Tenant-Konfiguration"},
            {"name": "bridge",   "description": "Bridge — Auth-Proxy zur alten Welt (Phase-1.5-Übergang)"},
            {"name": "persons",  "description": "Persons — Stammdaten (Kinder, Mitarbeiter, später Teilnehmer/Gäste)"},
            {"name": "calendar", "description": "Calendar — Events, Stats, Geburtstage, Repeat-Reihen"},
            {"name": "attendance", "description": "Attendance — Anwesenheit, Live-Counts, Personalschlüssel"},
            {"name": "dev",      "description": "Developer-Only — Stats, Persona-Editor, Operator-Liste, Audit-Logs"},
            {"name": "meta",     "description": "Meta — Health, Root"},
        ],
    )

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ---- Middleware (Reihenfolge wichtig: Rate-Limit VOR Audit) ----
    from .middleware.audit_log import AuditLogMiddleware  # noqa: E402
    from .middleware.rate_limit import RateLimitMiddleware  # noqa: E402
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # ---- Router ----
    from .routers import attendance, auth, bridge, calendar, chat, dev, heim, memory, persons, sessions, tools  # noqa: E402

    app.include_router(auth.router,       prefix="/api/v1/auth",       tags=["auth"])
    app.include_router(chat.router,       prefix="/api/v1/chat",       tags=["chat"])
    app.include_router(sessions.router,   prefix="/api/v1/sessions",   tags=["sessions"])
    app.include_router(memory.router,     prefix="/api/v1/memory",     tags=["memory"])
    app.include_router(tools.router,      prefix="/api/v1/tools",      tags=["tools"])
    app.include_router(heim.router,       prefix="/api/v1/heim",       tags=["heim"])
    app.include_router(bridge.router,     prefix="/api/v1/bridge",     tags=["bridge"])
    app.include_router(persons.router,    prefix="/api/v1/persons",    tags=["persons"])
    app.include_router(calendar.router,   prefix="/api/v1/calendar",   tags=["calendar"])
    app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["attendance"])
    app.include_router(dev.router,        prefix="/api/v1/dev",        tags=["dev"])

    # ---- Health-Check ----
    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {
            "name": "SHIKSHA Engine",
            "version": __version__,
            "docs": "/docs" if not settings.is_production else "disabled in production",
        }

    logger.info("SHIKSHA Engine started — version %s, env=%s", __version__, settings.app_env)

    return app


# WSGI/ASGI-Application für uvicorn
app = create_app()


def run() -> None:
    """Entry-Point für `shiksha-engine` script."""
    settings = get_settings()
    uvicorn.run(
        "shiksha_engine.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.app_log_level,
        reload=not settings.is_production,
    )


if __name__ == "__main__":
    run()
